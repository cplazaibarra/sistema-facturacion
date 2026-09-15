#!/usr/bin/env python3
"""
tools/populate_movements.py
Población segura e idempotente de inventory_movements (Kardex / Ledger Relacional)
siguiendo estrictamente la ETAPA C de INVENTORY_MIGRATION_PLAN.md:
1. Compras recibidas (inventory_entries / inventory_entry_items) -> PURCHASE_RECEIPT (+)
2. Fabricaciones finalizadas (production_orders) -> PRODUCTION_OUTPUT (+)
3. Consumos de fabricación (production_order_items + additional) -> PRODUCTION_INPUT (-)
4. Saldos iniciales legacy para semillas SQLite -> INITIAL_BALANCE (+)
Garantiza INV-001: ningún producto resulta con stock negativo.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from db import get_connection


def populate_inventory_movements():
    print("=== Iniciando Población de inventory_movements (Etapa C) ===")
    
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Mapas de productos
            cur.execute("SELECT id, sku, name, cost FROM products;")
            prods = cur.fetchall()
            id_to_sku = {p["id"]: p["sku"] for p in prods}
            sku_to_id = {p["sku"]: p["id"] for p in prods}
            id_to_cost = {p["id"]: float(p["cost"] or 0.0) for p in prods}

            # -------------------------------------------------------------
            # 1. Saldos Iniciales Base (INITIAL_BALANCE)
            # Semilla base migración legacy SQLite
            # -------------------------------------------------------------
            initial_balances = [
                ("PRD001", 450.0, "Saldo inicial migración legacy SQLite (Miel Pura 1kg)"),
                ("PRD002", 680.0, "Saldo inicial migración legacy SQLite (Miel Pura 500g)"),
                ("PRD003", 35.0, "Saldo inicial migración legacy SQLite (Polen 250g)"),
                ("PRD004", 180.0, "Saldo inicial migración legacy SQLite (Propóleo 30ml)"),
                ("INS001", 1000.0, "Saldo inicial inventario base (Miel a Granel)"),
                ("INS002", 500.0, "Saldo inicial inventario base (Frascos 500g)"),
                ("INS003", 500.0, "Saldo inicial inventario base (Tapas Frasco)"),
            ]

            print("\n1. Verificando saldos iniciales (INITIAL_BALANCE)...")
            for sku, qty, note in initial_balances:
                pid = sku_to_id.get(sku)
                if not pid:
                    continue
                cur.execute(
                    """
                    SELECT id FROM inventory_movements 
                    WHERE product_id = %s AND movement_type = 'INITIAL_BALANCE';
                    """,
                    (pid,)
                )
                existing = cur.fetchone()
                if not existing:
                    cur.execute(
                        """
                        INSERT INTO inventory_movements (
                            product_id, movement_type, quantity, unit_cost, lot_number,
                            warehouse, reference_type, reference_id, notes, created_at, created_by
                        ) VALUES (%s, 'INITIAL_BALANCE', %s, %s, NULL, 'Almacén Principal', 'initial_seed', 1, %s, '2026-08-01 00:00:00', 'Sistema')
                        RETURNING id;
                        """,
                        (pid, qty, id_to_cost.get(pid, 0.0), note)
                    )
                    print(f"  [+] Insertado INITIAL_BALANCE {sku}: {qty} un.")
                else:
                    print(f"  [=] Ya existe INITIAL_BALANCE {sku}, omitiendo.")

            # -------------------------------------------------------------
            # 2. Compras Históricas (PURCHASE_RECEIPT)
            # -------------------------------------------------------------
            print("\n2. Verificando compras recibidas (PURCHASE_RECEIPT)...")
            cur.execute(
                """
                SELECT iei.id as item_id, iei.product_id, iei.quantity, iei.unit_price, iei.lot_number,
                       ie.id as entry_id, ie.order_number, ie.purchase_order_id, ie.warehouse, ie.entry_date, ie.created_at
                FROM inventory_entry_items iei
                JOIN inventory_entries ie ON ie.id = iei.inventory_entry_id
                ORDER BY ie.entry_date ASC, iei.id ASC;
                """
            )
            entry_items = cur.fetchall()
            for item in entry_items:
                cur.execute(
                    """
                    SELECT id FROM inventory_movements
                    WHERE reference_type = 'inventory_entry_item' AND reference_id = %s;
                    """,
                    (item["item_id"],)
                )
                if cur.fetchone():
                    continue

                lot_num = (item["lot_number"] or "").strip() or None
                cur.execute(
                    """
                    INSERT INTO inventory_movements (
                        product_id, movement_type, quantity, unit_cost, lot_number,
                        warehouse, reference_type, reference_id, notes, created_at, created_by
                    ) VALUES (%s, 'PURCHASE_RECEIPT', %s, %s, %s, %s, 'inventory_entry_item', %s, %s, %s, 'Sistema')
                    """,
                    (
                        item["product_id"],
                        float(item["quantity"]),
                        float(item["unit_price"] or 0.0),
                        lot_num,
                        item["warehouse"] or "Almacén Principal",
                        item["item_id"],
                        f"Recepción compra {item['order_number']} (Entrada #{item['entry_id']})",
                        item["created_at"] or f"{item['entry_date']} 12:00:00"
                    )
                )
            print(f"  Procesados {len(entry_items)} ítems de compras.")

            # -------------------------------------------------------------
            # 3. Fabricaciones Finalizadas (PRODUCTION_OUTPUT)
            # -------------------------------------------------------------
            print("\n3. Verificando productos terminados de OTs finalizadas (PRODUCTION_OUTPUT)...")
            cur.execute(
                """
                SELECT po.id as ot_id, po.ot_number, po.final_product_id, po.quantity, po.unit_cost, po.completed_at
                FROM production_orders po
                WHERE po.status = 'Finalizada';
                """
            )
            finalized_ots = cur.fetchall()
            for ot in finalized_ots:
                cur.execute(
                    """
                    SELECT id FROM inventory_movements
                    WHERE movement_type = 'PRODUCTION_OUTPUT' AND reference_type = 'production_order' AND reference_id = %s;
                    """,
                    (ot["ot_id"],)
                )
                if cur.fetchone():
                    continue

                cur.execute(
                    """
                    INSERT INTO inventory_movements (
                        product_id, movement_type, quantity, unit_cost, lot_number,
                        warehouse, reference_type, reference_id, notes, created_at, created_by
                    ) VALUES (%s, 'PRODUCTION_OUTPUT', %s, %s, NULL, 'Almacén Principal', 'production_order', %s, %s, %s, 'Sistema')
                    """,
                    (
                        ot["final_product_id"],
                        float(ot["quantity"]),
                        float(ot["unit_cost"] or 0.0),
                        ot["ot_id"],
                        f"Fabricación finalizada OT {ot['ot_number']}",
                        ot["completed_at"] or "2026-08-15 22:00:00"
                    )
                )
                print(f"  [+] Insertado PRODUCTION_OUTPUT OT {ot['ot_number']}")

            # -------------------------------------------------------------
            # 4. Consumos de OTs Finalizadas (PRODUCTION_INPUT)
            # -------------------------------------------------------------
            print("\n4. Verificando insumos consumidos en OTs finalizadas (PRODUCTION_INPUT)...")
            cur.execute(
                """
                SELECT poi.id as item_id, poi.production_order_id as ot_id, poi.input_product_id,
                       poi.quantity_required, poi.unit_cost, po.ot_number, po.completed_at
                FROM production_order_items poi
                JOIN production_orders po ON po.id = poi.production_order_id
                WHERE po.status = 'Finalizada';
                """
            )
            ot_req_items = cur.fetchall()
            for item in ot_req_items:
                cur.execute(
                    """
                    SELECT id FROM inventory_movements
                    WHERE reference_type = 'production_order_item' AND reference_id = %s;
                    """,
                    (item["item_id"],)
                )
                if cur.fetchone():
                    continue

                cur.execute(
                    """
                    INSERT INTO inventory_movements (
                        product_id, movement_type, quantity, unit_cost, lot_number,
                        warehouse, reference_type, reference_id, notes, created_at, created_by
                    ) VALUES (%s, 'PRODUCTION_INPUT', %s, %s, NULL, 'Almacén Principal', 'production_order_item', %s, %s, %s, 'Sistema')
                    """,
                    (
                        item["input_product_id"],
                        -float(item["quantity_required"]),
                        float(item["unit_cost"] or 0.0),
                        item["item_id"],
                        f"Insumo planificado para OT {item['ot_number']}",
                        item["completed_at"] or "2026-08-15 22:00:00"
                    )
                )
            print(f"  Procesados {len(ot_req_items)} insumos requeridos de OTs.")

            cur.execute(
                """
                SELECT poai.id as item_id, poai.production_order_id as ot_id, poai.input_product_id,
                       poai.quantity, poai.unit_cost, po.ot_number, po.completed_at
                FROM production_order_additional_items poai
                JOIN production_orders po ON po.id = poai.production_order_id
                WHERE po.status = 'Finalizada';
                """
            )
            ot_add_items = cur.fetchall()
            for item in ot_add_items:
                cur.execute(
                    """
                    SELECT id FROM inventory_movements
                    WHERE reference_type = 'production_order_add_item' AND reference_id = %s;
                    """,
                    (item["item_id"],)
                )
                if cur.fetchone():
                    continue

                cur.execute(
                    """
                    INSERT INTO inventory_movements (
                        product_id, movement_type, quantity, unit_cost, lot_number,
                        warehouse, reference_type, reference_id, notes, created_at, created_by
                    ) VALUES (%s, 'PRODUCTION_INPUT', %s, %s, NULL, 'Almacén Principal', 'production_order_add_item', %s, %s, %s, 'Sistema')
                    """,
                    (
                        item["input_product_id"],
                        -float(item["quantity"]),
                        float(item["unit_cost"] or 0.0),
                        item["item_id"],
                        f"Insumo adicional para OT {item['ot_number']}",
                        item["completed_at"] or "2026-08-15 22:00:00"
                    )
                )
            print(f"  Procesados {len(ot_add_items)} insumos adicionales de OTs.")

            # -------------------------------------------------------------
            # 5. Validación INV-001 (No Negatividad)
            # -------------------------------------------------------------
            cur.execute(
                """
                SELECT p.sku, p.name, COALESCE(SUM(im.quantity), 0.0) as current_stock
                FROM products p
                JOIN inventory_movements im ON im.product_id = p.id
                GROUP BY p.sku, p.name
                HAVING SUM(im.quantity) < 0.0;
                """
            )
            negatives = cur.fetchall()
            if negatives:
                raise ValueError(f"INV-001 VIOLADO: Productos con stock negativo detectados: {negatives}")
            else:
                print("\n[V] Validación INV-001 exitosa: Ningún producto tiene stock relacional negativo.")

        conn.commit()
    print("\n=== Población de inventory_movements (Etapa C) completada exitosamente ===")


if __name__ == "__main__":
    populate_inventory_movements()
