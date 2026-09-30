#!/usr/bin/env python3
"""Controlled purge of test products, preserving the oldest deterministic set.

Dry-run is the default.  Execute requires ``--execute --confirm PURGE`` and is
also blocked when APP_ENV/FLASK_ENV indicate production.
"""
from __future__ import annotations
import argparse, json, os, sys
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.database import get_connection

KEEP_SQL = "SELECT id FROM products ORDER BY created_at ASC, id ASC LIMIT %s"


def guard_environment() -> None:
    values = [os.getenv("APP_ENV", ""), os.getenv("FLASK_ENV", "")]
    if any(v.lower() in {"prod", "production", "prd"} for v in values):
        raise RuntimeError("Purge bloqueado: el entorno está marcado como producción")


def prepare(cur, keep_oldest: int) -> list[dict]:
    cur.execute("DROP TABLE IF EXISTS _purge_keep_products")
    cur.execute("DROP TABLE IF EXISTS _purge_products")
    cur.execute("CREATE TEMP TABLE _purge_keep_products AS " + KEEP_SQL, (keep_oldest,))
    cur.execute("CREATE TEMP TABLE _purge_products AS SELECT p.id FROM products p LEFT JOIN _purge_keep_products k ON k.id=p.id WHERE k.id IS NULL")
    cur.execute("SELECT id, sku, name, created_at FROM products WHERE id IN (SELECT id FROM _purge_keep_products) ORDER BY created_at ASC,id ASC")
    return [dict(r) for r in cur.fetchall()]


def counts(cur) -> dict[str, int]:
    tables = {
        "inventory_adjustment_requests": "product_id",
        "inventory_entry_items": "product_id",
        "inventory_movements": "product_id",
        "lot_stock": "product_id",
        "lots": "product_id",
        "product_recipe_items": "input_product_id",
        "product_recipes_final": "final_product_id",
        "product_suppliers": "product_id",
        "production_lot_consumptions": "input_product_id",
        "production_lot_outputs": "output_product_id",
        "production_order_additional_items": "input_product_id",
        "production_order_items": "input_product_id",
        "production_orders_final": "final_product_id",
        "purchase_order_items": "product_id",
        "sale_items": "product_id",
        "sale_lot_movements": "product_id",
        "sale_packaging_items": "product_id",
    }
    result = {}
    for label, column in tables.items():
        table = label.replace("_final", "")
        cur.execute(f"SELECT count(*) AS n FROM {table} WHERE {column} IN (SELECT id FROM _purge_products)")
        result[label] = int(cur.fetchone()["n"])
    return result


def print_plan(cur, keep: list[dict]) -> None:
    cur.execute("SELECT count(*) AS n FROM products")
    total = int(cur.fetchone()["n"])
    print(f"PRODUCTOS TOTALES: {total}")
    print(f"PRODUCTOS A CONSERVAR: {len(keep)}")
    print(f"PRODUCTOS A ELIMINAR: {total-len(keep)}")
    print("KEEP SET:")
    for p in keep:
        print(f"{p['id']}\t{p['sku']}\t{p['name']}\t{p['created_at']}")
    print("DEPENDENCIAS DIRECTAS DEL PURGE SET:")
    for key, value in counts(cur).items():
        print(f"{key}: {value}")


def json_product_ids(value):
    try:
        data = json.loads(value or "[]")
    except Exception:
        return [], None
    if not isinstance(data, list):
        return [], data
    ids = []
    for line in data:
        if isinstance(line, dict) and str(line.get("product_id", "")).isdigit():
            ids.append(int(line["product_id"]))
    return ids, data


def execute(cur) -> dict[str, int]:
    summary = {}
    purge = "(SELECT id FROM _purge_products)"
    # Remove audit rows before adjustment requests and movements.
    cur.execute(f"DELETE FROM inventory_adjustment_audit WHERE adjustment_id IN (SELECT id FROM inventory_adjustment_requests WHERE product_id IN {purge})")
    summary["inventory_adjustment_audit"] = cur.rowcount
    cur.execute(f"DELETE FROM inventory_adjustment_requests WHERE product_id IN {purge}")
    summary["inventory_adjustment_requests"] = cur.rowcount
    # All product-linked operational rows, including lot genealogy.
    for table, column in [
        ("production_lot_consumptions", "input_product_id"), ("production_lot_outputs", "output_product_id"),
        ("sale_lot_movements", "product_id"), ("sale_packaging_items", "product_id"),
        ("inventory_entry_items", "product_id"), ("inventory_movements", "product_id"),
        ("lot_stock", "product_id"), ("lots", "product_id"),
        ("product_recipe_items", "input_product_id"), ("product_suppliers", "product_id"),
    ]:
        cur.execute(f"DELETE FROM {table} WHERE {column} IN {purge}")
        summary[table] = cur.rowcount
    # Mixed commercial documents: remove only purge lines. Empty documents are
    # removed after their dependent payment/history rows.
    for table in ("purchase_order_items", "sale_items", "production_order_items", "production_order_additional_items"):
        column = "product_id" if table in ("purchase_order_items", "sale_items") else "input_product_id"
        cur.execute(f"DELETE FROM {table} WHERE {column} IN {purge}")
        summary[table] = cur.rowcount
    # Recipes whose final product is purged can be deleted after their items.
    cur.execute(f"DELETE FROM product_recipes WHERE final_product_id IN {purge}")
    summary["product_recipes"] = cur.rowcount
    # Orders with purged final products or no remaining input lines are invalid.
    cur.execute(f"SELECT id FROM production_orders WHERE final_product_id IN {purge} OR id NOT IN (SELECT production_order_id FROM production_order_items UNION SELECT production_order_id FROM production_order_additional_items)")
    order_ids = [r["id"] for r in cur.fetchall()]
    if order_ids:
        cur.execute("DELETE FROM production_lot_consumptions WHERE production_order_id = ANY(%s)", (order_ids,))
        cur.execute("DELETE FROM production_lot_outputs WHERE production_order_id = ANY(%s)", (order_ids,))
        cur.execute("DELETE FROM lot_stock WHERE lot_id IN (SELECT id FROM lots WHERE production_order_id = ANY(%s))", (order_ids,))
        cur.execute("DELETE FROM lots WHERE production_order_id = ANY(%s)", (order_ids,))
        cur.execute("DELETE FROM production_orders WHERE id = ANY(%s)", (order_ids,))
    summary["production_orders"] = len(order_ids)
    # Purchase orders with no remaining lines can be removed; their entries are
    # retained only when they still contain a valid product line.
    cur.execute("SELECT id FROM purchase_orders WHERE id NOT IN (SELECT purchase_order_id FROM purchase_order_items)")
    po_ids = [r["id"] for r in cur.fetchall()]
    if po_ids:
        cur.execute("DELETE FROM lot_stock WHERE lot_id IN (SELECT id FROM lots WHERE purchase_order_id = ANY(%s))", (po_ids,))
        cur.execute("DELETE FROM lots WHERE purchase_order_id = ANY(%s)", (po_ids,))
        cur.execute("DELETE FROM purchase_orders WHERE id = ANY(%s)", (po_ids,))
    summary["purchase_orders"] = len(po_ids)
    # Sales JSON is a second representation used by the ERP.  Preserve mixed
    # sales and remove exclusive sales with their dependent rows.
    cur.execute("SELECT id, products_json FROM sales FOR UPDATE")
    sale_delete = []
    for row in cur.fetchall():
        ids, data = json_product_ids(row["products_json"])
        if not ids or not any(i in set(ids) for i in ids):
            continue
        purge_ids = set(ids)
        cur.execute("SELECT id FROM products WHERE id IN (SELECT id FROM _purge_products) AND id = ANY(%s)", (list(purge_ids),))
        bad = {r["id"] for r in cur.fetchall()}
        if not bad:
            continue
        if all(i in bad for i in ids):
            sale_delete.append(row["id"])
        elif isinstance(data, list):
            kept = [line for line in data if not (isinstance(line, dict) and str(line.get("product_id", "")).isdigit() and int(line["product_id"]) in bad)]
            cur.execute("UPDATE sales SET products_json=%s WHERE id=%s", (json.dumps(kept, ensure_ascii=False), row["id"]))
            summary["sales_mixed"] = summary.get("sales_mixed", 0) + 1
    if sale_delete:
        cur.execute("DELETE FROM sale_payments WHERE sale_id = ANY(%s)", (sale_delete,))
        cur.execute("DELETE FROM sale_payment_items WHERE sale_id = ANY(%s)", (sale_delete,))
        cur.execute("DELETE FROM sales WHERE id = ANY(%s)", (sale_delete,))
    summary["sales_exclusive"] = len(sale_delete)
    # Nunca conservar documentos comerciales vacíos.
    cur.execute("SELECT id FROM sales WHERE jsonb_array_length(products_json::jsonb)=0")
    empty_sales = [r["id"] for r in cur.fetchall()]
    if empty_sales:
        for table in ("sale_packaging_items", "sale_lot_movements", "sale_payment_items", "sale_payments", "sales_status_history", "sales_payment_history"):
            cur.execute(f"DELETE FROM {table} WHERE sale_id = ANY(%s)", (empty_sales,))
        cur.execute("DELETE FROM sales WHERE id = ANY(%s)", (empty_sales,))
    summary["empty_sales_removed"] = len(empty_sales)
    # Legacy inventory JSON must not retain removed SKUs.
    cur.execute("SELECT json FROM page_data WHERE key='inventory_items' FOR UPDATE")
    row = cur.fetchone()
    if row and row.get("json"):
        data = json.loads(row["json"])
        cur.execute("SELECT sku FROM products WHERE id IN (SELECT id FROM _purge_products)")
        purge_skus = {r["sku"] for r in cur.fetchall()}
        filtered = [x for x in data if x.get("code") not in purge_skus]
        cur.execute("UPDATE page_data SET json=%s WHERE key='inventory_items'", (json.dumps(filtered, ensure_ascii=False),))
        summary["page_data_inventory_items"] = len(data)-len(filtered)
    cur.execute("DELETE FROM products WHERE id IN (SELECT id FROM _purge_products)")
    summary["products"] = cur.rowcount
    return summary


def main() -> int:
    # Importing this command from pytest must never overwrite its explicit
    # isolated DB configuration with the normal .env values.
    load_dotenv(ROOT / '.env')
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm")
    parser.add_argument("--keep-oldest", type=int, default=70)
    args = parser.parse_args()
    if args.execute:
        guard_environment()
        if args.confirm != "PURGE":
            raise SystemExit("Para ejecutar se requiere --confirm PURGE")
    elif not args.dry_run:
        args.dry_run = True
    with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                keep = prepare(cur, args.keep_oldest)
                print_plan(cur, keep)
                if args.execute:
                    summary = execute(cur)
                    conn.commit()
                    print("EJECUTADO:")
                    for key, value in summary.items(): print(f"{key}: {value}")
                else:
                    conn.rollback()
                    print("DRY-RUN: no se modificaron datos")
        except Exception:
            conn.rollback()
            raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
