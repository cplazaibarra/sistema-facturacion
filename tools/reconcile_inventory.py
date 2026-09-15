#!/usr/bin/env python3
"""
Herramienta READ-ONLY de reconciliación de inventario.
Compara el stock entre page_data(inventory_items) y lot_stock por producto (SKU).
NO realiza modificaciones de datos bajo ninguna circunstancia.
"""

import os
import sys
import json

# Asegurar path al directorio del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from db import get_connection, get_page_data


def reconcile_inventory():
    """
    Compara el inventario registrado en page_data('inventory_items')
    con el stock consolidado de la tabla lot_stock.
    """
    # 1. Obtener datos de page_data
    page_items = get_page_data("inventory_items") or []
    page_data_map = {}
    for item in page_items:
        sku = (item.get("code") or "").strip()
        if sku:
            name = (item.get("name") or "").strip()
            stock = float(item.get("stock", 0.0) or 0.0)
            page_data_map[sku] = {
                "name": name,
                "stock": stock,
                "raw_item": item
            }

    # 2. Obtener datos de products y lot_stock
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Todos los productos del catálogo
            cur.execute("""
                SELECT p.id, p.sku, p.name, p.requires_lot, p.status, p.cost,
                       COALESCE(SUM(ls.available_qty), 0.0) as lot_stock_qty,
                       COUNT(ls.id) as lot_count
                FROM products p
                LEFT JOIN lot_stock ls ON ls.product_id = p.id
                WHERE p.is_deleted = FALSE OR p.is_deleted IS NULL
                GROUP BY p.id, p.sku, p.name, p.requires_lot, p.status, p.cost
                ORDER BY p.id ASC;
            """)
            db_products = cur.fetchall()

    # Consolidar todos los SKUs conocidos
    all_skus = set(p["sku"].strip() for p in db_products if p.get("sku"))
    all_skus.update(page_data_map.keys())

    db_by_sku = {p["sku"].strip(): p for p in db_products if p.get("sku")}

    results = []
    
    total_products = len(all_skus)
    count_ok = 0
    count_difference = 0
    count_only_page_data = 0
    count_only_lot_stock = 0
    count_no_stock = 0
    total_diff_abs = 0.0

    for sku in sorted(all_skus):
        db_prod = db_by_sku.get(sku)
        pdata_prod = page_data_map.get(sku)

        prod_name = (
            (db_prod["name"] if db_prod else None) or 
            (pdata_prod["name"] if pdata_prod else None) or 
            "Sin Nombre"
        )
        requires_lot = db_prod.get("requires_lot", False) if db_prod else False

        stock_page = pdata_prod["stock"] if pdata_prod else 0.0
        stock_lot = float(db_prod["lot_stock_qty"]) if db_prod else 0.0
        diff = round(stock_page - stock_lot, 4)

        has_page = pdata_prod is not None and stock_page > 0
        has_lot = stock_lot > 0

        if stock_page == 0.0 and stock_lot == 0.0:
            status = "NO_STOCK"
            count_no_stock += 1
        elif diff == 0.0:
            status = "OK"
            count_ok += 1
        elif has_page and not has_lot:
            status = "ONLY_PAGE_DATA"
            count_only_page_data += 1
            count_difference += 1
            total_diff_abs += abs(diff)
        elif has_lot and not has_page:
            status = "ONLY_LOT_STOCK"
            count_only_lot_stock += 1
            count_difference += 1
            total_diff_abs += abs(diff)
        else:
            status = "DIFFERENCE"
            count_difference += 1
            total_diff_abs += abs(diff)

        results.append({
            "sku": sku,
            "product": prod_name,
            "stock_page_data": stock_page,
            "stock_lot_stock": stock_lot,
            "diff": diff,
            "status": status,
            "requires_lot": requires_lot,
            "in_catalog": db_prod is not None
        })

    summary = {
        "total_skus": total_products,
        "total_catalog_products": len(db_products),
        "products_with_any_stock": sum(1 for r in results if r["stock_page_data"] > 0 or r["stock_lot_stock"] > 0),
        "coincident_ok": count_ok,
        "differences": count_difference,
        "absolute_difference_sum": total_diff_abs,
        "only_page_data": count_only_page_data,
        "only_lot_stock": count_only_lot_stock,
        "no_stock": count_no_stock,
    }

    return summary, results


if __name__ == "__main__":
    summary, results = reconcile_inventory()
    print("================================================================")
    print("       REPORTE DE RECONCILIACIÓN DE INVENTARIO (READ-ONLY)       ")
    print("================================================================")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    print("================================================================")
    print("\n--- PRODUCTOS CON DISCREPANCIAS O STOCK ---")
    header = f"{'SKU':<15} | {'PRODUCTO':<30} | {'PAGE_DATA':>10} | {'LOT_STOCK':>10} | {'DELTA':>10} | {'ESTADO':<15}"
    print(header)
    print("-" * len(header))
    for r in results:
        if r["status"] != "NO_STOCK":
            print(f"{r['sku']:<15} | {r['product'][:30]:<30} | {r['stock_page_data']:>10.2f} | {r['stock_lot_stock']:>10.2f} | {r['diff']:>10.2f} | {r['status']:<15}")
