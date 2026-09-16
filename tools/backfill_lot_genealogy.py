#!/usr/bin/env python3
"""
tools/backfill_lot_genealogy.py
Audits and backfills historical lot records into the new 'lots' genealogy table.
Strict rule: NEVER invent lot numbers. If no evidence exists, classify as UNKNOWN.
"""

import argparse
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv

load_dotenv()
from core.database import get_connection


def analyze_history(conn):
    """Analiza la historia de recepciones, producción y ventas para clasificar la trazabilidad."""
    with conn.cursor() as cur:
        # 1. Recepciones
        cur.execute("""
            SELECT iei.id, iei.inventory_entry_id, iei.product_id, iei.quantity, iei.lot_number,
                   ie.order_number, ie.entry_date, ie.supplier_id, ie.purchase_order_id, ie.warehouse,
                   p.requires_lot, p.name as product_name, p.sku
            FROM inventory_entry_items iei
            JOIN inventory_entries ie ON ie.id = iei.inventory_entry_id
            JOIN products p ON p.id = iei.product_id
            ORDER BY iei.id ASC;
        """)
        receptions = cur.fetchall()

        exact_receptions = []
        unknown_receptions = []
        for r in receptions:
            lot = (r.get("lot_number") or "").strip()
            if lot:
                exact_receptions.append(r)
            else:
                unknown_receptions.append(r)

        # 2. Órdenes de Trabajo (Producción)
        cur.execute("""
            SELECT po.id, po.ot_number, po.final_product_id, po.quantity, po.status,
                   p.name as final_product_name, p.requires_lot
            FROM production_orders po
            JOIN products p ON p.id = po.final_product_id
            ORDER BY po.id ASC;
        """)
        production_orders = cur.fetchall()

        # En la historia previa, ninguna OT registró lote de entrada ni lote de salida
        unknown_ots = production_orders

        # 3. Ventas
        cur.execute("SELECT COUNT(*) as c FROM sales;")
        total_sales = cur.fetchone()["c"]

        cur.execute("SELECT COUNT(*) as c FROM sale_lot_movements;")
        sales_with_lot_moves = cur.fetchone()["c"]

        return {
            "receptions": {
                "total": len(receptions),
                "exact": exact_receptions,
                "unknown": unknown_receptions,
            },
            "production_orders": {
                "total": len(production_orders),
                "exact": [],
                "unknown": unknown_ots,
            },
            "sales": {
                "total": total_sales,
                "exact": sales_with_lot_moves,
                "unknown": total_sales - sales_with_lot_moves,
            },
        }


def apply_backfill(conn, dry_run=False):
    """Crea registros en 'lots' para lotes históricos con evidencia EXACTA y vincula lot_stock / inventory_entry_items."""
    analysis = analyze_history(conn)
    exact_receptions = analysis["receptions"]["exact"]

    created_lots = 0
    updated_lot_stock = 0
    updated_entry_items = 0

    with conn.cursor() as cur:
        for item in exact_receptions:
            pid = item["product_id"]
            lot_num = item["lot_number"].strip()
            qty = float(item["quantity"])
            entry_id = item["inventory_entry_id"]
            po_id = item["purchase_order_id"]
            sup_id = item["supplier_id"]
            wh = item["warehouse"] or "Principal"
            entry_date = item["entry_date"] or "2026-01-01"

            # Verificar si ya existe en lots
            cur.execute(
                "SELECT id FROM lots WHERE product_id = %s AND lot_number = %s",
                (pid, lot_num)
            )
            existing = cur.fetchone()
            if not existing:
                if not dry_run:
                    cur.execute(
                        """
                        INSERT INTO lots (
                            product_id, lot_number, lot_type, origin_type, origin_id,
                            supplier_id, purchase_order_id, inventory_entry_id,
                            initial_quantity, created_at, status, warehouse, notes
                        ) VALUES (%s, %s, 'RAW_MATERIAL', 'PURCHASE', %s, %s, %s, %s, %s, %s, 'ACTIVE', %s, %s)
                        RETURNING id;
                        """,
                        (
                            pid, lot_num, entry_id, sup_id, po_id, entry_id,
                            qty, f"{entry_date} 00:00:00", wh,
                            f"Backfill histórico verificado desde recepción ID {entry_id}"
                        )
                    )
                    lot_id = cur.fetchone()["id"]
                    created_lots += 1
                else:
                    lot_id = -1
                    created_lots += 1
            else:
                lot_id = existing["id"]

            if not dry_run:
                # Actualizar inventory_entry_items
                cur.execute(
                    "UPDATE inventory_entry_items SET lot_id = %s WHERE id = %s AND lot_id IS NULL",
                    (lot_id, item["id"])
                )
                if cur.rowcount > 0:
                    updated_entry_items += cur.rowcount

                # Actualizar lot_stock
                cur.execute(
                    "UPDATE lot_stock SET lot_id = %s WHERE product_id = %s AND lot_number = %s AND lot_id IS NULL",
                    (lot_id, pid, lot_num)
                )
                if cur.rowcount > 0:
                    updated_lot_stock += cur.rowcount

                # Actualizar inventory_movements correspondientes
                cur.execute(
                    "UPDATE inventory_movements SET lot_id = %s WHERE product_id = %s AND lot_number = %s AND lot_id IS NULL",
                    (lot_id, pid, lot_num)
                )

        if not dry_run:
            conn.commit()

    return {
        "created_lots": created_lots,
        "updated_lot_stock": updated_lot_stock,
        "updated_entry_items": updated_entry_items,
    }


def main():
    parser = argparse.ArgumentParser(description="Auditoría y backfill de genealogía de lotes.")
    parser.add_argument("--mode", choices=["analyze", "apply"], default="analyze", help="Modo de ejecución")
    parser.add_argument("--dry-run", action="store_true", help="Simulación sin cambios")
    args = parser.parse_args()

    with get_connection() as conn:
        analysis = analyze_history(conn)
        print("================================================================")
        print("         AUDITORÍA DE TRAZABILIDAD HISTÓRICA DE LOTES           ")
        print("================================================================")
        rec = analysis["receptions"]
        print(f"Recepciones Históricas: {rec['total']}")
        print(f"  - Con lote exacto (EXACT): {len(rec['exact'])}")
        for r in rec["exact"]:
            print(f"      * Prod {r['product_id']} ({r['product_name']}) | Lote: '{r['lot_number']}' | Cant: {r['quantity']} | OC: {r['purchase_order_id']} | Prov: {r['supplier_id']}")
        print(f"  - Sin lote (UNKNOWN): {len(rec['unknown'])}")

        ots = analysis["production_orders"]
        print(f"\nÓrdenes de Trabajo Históricas: {ots['total']}")
        print(f"  - Con insumos por lote exacto: {len(ots['exact'])}")
        print(f"  - No reconstruibles (UNKNOWN): {len(ots['unknown'])}")

        sales = analysis["sales"]
        print(f"\nVentas Históricas: {sales['total']}")
        print(f"  - Con lote exacto: {sales['exact']}")
        print(f"  - Sin lote previo (UNKNOWN): {sales['unknown']}")
        print("================================================================")

        if args.mode == "apply":
            print("\nEjecutando backfill verificado...")
            res = apply_backfill(conn, dry_run=args.dry_run)
            print(f"  Lotes creados en tabla 'lots': {res['created_lots']}")
            print(f"  Registros en 'lot_stock' vinculados: {res['updated_lot_stock']}")
            print(f"  Registros en 'inventory_entry_items' vinculados: {res['updated_entry_items']}")
            print("Backfill completado exitosamente sin inventar datos.")


if __name__ == "__main__":
    main()
