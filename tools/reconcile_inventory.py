#!/usr/bin/env python3
"""Read-only inventory diagnostics. Stock correction is intentionally disabled.

Usage: ``python tools/reconcile_inventory.py --check [--details] [--json]``.
The legacy ``--fix`` option is rejected until a separately reviewed repair plan
defines the source of truth and per-document rollback strategy.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
TOLERANCE = 0.001
load_dotenv(ROOT / ".env")

PRODUCT_SQL = r"""
WITH legacy_items AS (
    SELECT j.item, j.ordinality,
           j.item->>'code' AS sku,
           CASE
             WHEN j.item ? 'stock' AND j.item->'stock' <> 'null'::jsonb
                  AND (j.item->>'stock') ~ '^[-+]?[0-9]+([.][0-9]+)?$'
             THEN (j.item->>'stock')::numeric
             ELSE NULL
           END AS stock_value
    FROM page_data pd
    CROSS JOIN LATERAL jsonb_array_elements(pd.json::jsonb) WITH ORDINALITY AS j(item, ordinality)
    WHERE pd.key='inventory_items'
), legacy AS (
    SELECT sku, stock_value AS snapshot_stock,
           (item ? 'stock' AND item->'stock' <> 'null'::jsonb) AS snapshot_value_present,
           COUNT(*) OVER (PARTITION BY sku) AS snapshot_rows,
           ROW_NUMBER() OVER (PARTITION BY sku ORDER BY ordinality) AS first_row
    FROM legacy_items
), movement AS (
    SELECT product_id, SUM(quantity)::numeric AS ledger_stock,
           COUNT(*) AS movement_count,
           MAX(created_at::timestamptz) AS last_movement
    FROM inventory_movements
    GROUP BY product_id
), lot AS (
    SELECT product_id, SUM(available_qty)::numeric AS lot_stock,
           SUM(initial_qty)::numeric AS lot_initial,
           COUNT(*) AS lot_rows,
           COUNT(*) FILTER (WHERE available_qty < 0 OR initial_qty < 0) AS invalid_rows
    FROM lot_stock
    GROUP BY product_id
)
SELECT p.id, p.sku, p.name, COALESCE(p.requires_lot,FALSE) AS requires_lot,
       p.cost, (l.sku IS NOT NULL) AS snapshot_present,
       COALESCE(l.snapshot_value_present,FALSE) AS snapshot_value_present,
       l.snapshot_stock, COALESCE(l.snapshot_rows,0) AS snapshot_rows,
       m.ledger_stock, COALESCE(m.movement_count,0) AS movement_count,
       m.last_movement, lot.lot_stock, lot.lot_initial,
       COALESCE(lot.lot_rows,0) AS lot_rows,
       COALESCE(lot.invalid_rows,0) AS invalid_lot_rows
FROM products p
LEFT JOIN legacy l ON l.sku=p.sku AND l.first_row=1
LEFT JOIN movement m ON m.product_id=p.id
LEFT JOIN lot ON lot.product_id=p.id
WHERE p.is_deleted IS NOT TRUE
ORDER BY p.id
"""

REFERENCE_SQL = r"""
WITH classified AS (
 SELECT im.reference_type, im.reference_id,
 CASE
   WHEN im.reference_type='reconciliation_orphan' THEN 'orphan'
   WHEN im.reference_type IS NULL OR btrim(im.reference_type)=''
        OR im.reference_type IN ('MANUAL_ENTRY','reconciliation','initial_seed') THEN 'legacy_generic'
   WHEN im.reference_id IS NULL THEN 'reference_absent'
   WHEN im.reference_type='sale' AND EXISTS(SELECT 1 FROM sales x WHERE x.id=im.reference_id) THEN 'valid'
   WHEN im.reference_type='sale_cancellation' AND EXISTS(SELECT 1 FROM sales x WHERE x.id=im.reference_id) THEN 'valid'
   WHEN im.reference_type='purchase_order' AND EXISTS(SELECT 1 FROM purchase_orders x WHERE x.id=im.reference_id) THEN 'valid'
   WHEN im.reference_type='inventory_entry_item' AND EXISTS(SELECT 1 FROM inventory_entry_items x WHERE x.id=im.reference_id) THEN 'valid'
   WHEN im.reference_type='production_order' AND EXISTS(SELECT 1 FROM production_orders x WHERE x.id=im.reference_id) THEN 'valid'
   WHEN im.reference_type='production_order_item' AND EXISTS(SELECT 1 FROM production_order_items x WHERE x.id=im.reference_id) THEN 'valid'
   WHEN im.reference_type IN ('production_order_add_item','production_order_additional_item')
        AND EXISTS(SELECT 1 FROM production_order_additional_items x WHERE x.id=im.reference_id) THEN 'valid'
   WHEN im.reference_type='inventory_adjustment' AND EXISTS(SELECT 1 FROM inventory_adjustment_requests x WHERE x.id=im.reference_id) THEN 'valid'
   WHEN im.reference_type IN ('sale','sale_cancellation','purchase_order','inventory_entry_item',
        'production_order','production_order_item','production_order_add_item',
        'production_order_additional_item','inventory_adjustment') THEN 'orphan'
   ELSE 'unverifiable'
 END AS reference_status
 FROM inventory_movements im
)
SELECT COALESCE(reference_type,'<NULL>') AS reference_type,
       COUNT(*) AS movements,
       COUNT(*) FILTER(WHERE reference_status='valid') AS valid_references,
       COUNT(*) FILTER(WHERE reference_status='reference_absent') AS references_absent,
       COUNT(*) FILTER(WHERE reference_status='orphan') AS orphan_references,
       COUNT(*) FILTER(WHERE reference_status='legacy_generic') AS legacy_generic,
       COUNT(*) FILTER(WHERE reference_status='unverifiable') AS unverifiable
FROM classified
GROUP BY reference_type
ORDER BY movements DESC, reference_type
"""


def connect():
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "postgres"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "postgres"),
        options="-c default_transaction_read_only=on",
    )
    conn.set_session(readonly=True, autocommit=False, isolation_level="REPEATABLE READ")
    return conn


def _resolve_sku(product: Any, id_to_sku: dict, sku_to_sku: dict, name_to_skus: dict):
    def resolve_name(name):
        name = (name or "").strip().lower()
        exact = name_to_skus.get(name, [])
        if len(exact) == 1:
            return exact[0], "exact_name"
        if len(exact) > 1:
            return None, "ambiguous"
        candidates = {sku for candidate, skus in name_to_skus.items()
                      if candidate and (candidate in name or name in candidate)
                      for sku in skus}
        if len(candidates) == 1:
            return next(iter(candidates)), "partial_name_legacy"
        return (None, "ambiguous") if candidates else (None, "unresolved")

    if not isinstance(product, dict):
        if isinstance(product, str):
            match = re.match(r"^(.*?)\s*\((\d+)\)$", product.strip())
            if not match:
                return None, "unresolved"
            return resolve_name(match.group(1))
        return None, "unresolved"

    product_id = product.get("product_id")
    try:
        product_id = int(product_id) if product_id is not None else None
    except (TypeError, ValueError):
        product_id = None
    if product_id and product_id in id_to_sku:
        return id_to_sku[product_id], "product_id"
    sku = (product.get("sku") or product.get("product_sku") or "").strip().lower()
    if sku and sku in sku_to_sku:
        return sku_to_sku[sku], "sku_exact"
    return resolve_name(product.get("product_name") or product.get("name") or "")


def calculate_reservations(products, pending_sales, production_reservations):
    """Mirror services.stock_context.get_reserved_stock_by_sku without N+1 SQL."""
    id_to_sku = {p["id"]: p["sku"] for p in products}
    sku_to_sku = {p["sku"].strip().lower(): p["sku"] for p in products if p.get("sku")}
    name_to_skus = defaultdict(list)
    for p in products:
        if p.get("name"):
            name_to_skus[p["name"].strip().lower()].append(p["sku"])
    reserved = defaultdict(float)
    source_counts = defaultdict(int)
    unresolved = 0
    ambiguous = 0
    for sale in pending_sales:
        for item in sale.get("products", []):
            sku, source = _resolve_sku(item, id_to_sku, sku_to_sku, name_to_skus)
            if sku is None:
                if source == "ambiguous":
                    ambiguous += 1
                else:
                    unresolved += 1
                continue
            if isinstance(item, dict):
                qty = item.get("quantity", 0)
            else:
                match = re.match(r"^.*?\s*\((\d+)\)$", item.strip()) if isinstance(item, str) else None
                qty = int(match.group(1)) if match else 0
            try:
                qty = float(qty or 0)
            except (TypeError, ValueError):
                qty = 0
            if qty > 0:
                reserved[sku] += qty
                source_counts[source] += 1
    for row in production_reservations:
        try:
            qty = float(row["quantity"] or 0)
        except (TypeError, ValueError):
            qty = 0
        if row.get("sku") and qty > 0:
            reserved[row["sku"]] += qty
            source_counts["approved_production"] += 1
    return dict(reserved), {"unresolved_sale_lines": unresolved, "ambiguous_sale_lines": ambiguous,
                            "matched_sale_lines": dict(source_counts)}


def classify_product(product: dict, reserved: float = 0.0, reference_flags=()) -> dict:
    """Classify independent source comparisons; never coerce absent snapshot to zero."""
    snapshot_present = bool(product.get("snapshot_present"))
    snapshot_value_present = bool(product.get("snapshot_value_present"))
    snapshot = product.get("snapshot_stock") if snapshot_value_present else None
    ledger = product.get("ledger_stock")
    ledger = float(ledger) if ledger is not None else 0.0  # empty ledger is its additive identity
    lots = product.get("lot_stock")
    lots = float(lots) if lots is not None else 0.0
    reservation_demand = max(float(reserved or 0.0), 0.0)
    requires_lot = bool(product.get("requires_lot"))
    physical_source = "lot_stock" if requires_lot else "ledger"
    physical = lots if requires_lot else ledger
    # Keep the full commercial commitment visible as reserved demand. Split the
    # portion backed by physical units from the uncovered part for diagnostics.
    physical_reserved = min(reservation_demand, max(physical, 0.0))
    uncovered_demand = max(reservation_demand - physical_reserved, 0.0)
    reserved = reservation_demand
    available = max(physical - reserved, 0.0)

    # This is observational only: reproduce current getter semantics for comparison,
    # not as a validation rule. A missing snapshot is recorded as absent and the
    # getter falls back to ledger/lots.
    if requires_lot:
        erp_stock_lookup = lots
    else:
        snapshot_for_getter = float(snapshot) if snapshot_value_present and snapshot is not None else 0.0
        snapshot_is_found = snapshot_present
        if lots > 0 and snapshot_is_found and snapshot_for_getter > 0:
            erp_stock_lookup = max(lots, snapshot_for_getter, ledger)
        elif lots > 0:
            erp_stock_lookup = max(lots, ledger)
        elif snapshot_is_found:
            # The application getter treats a found item without a usable stock
            # value as zero. We preserve presence/value separately for diagnosis.
            erp_stock_lookup = max(snapshot_for_getter, ledger)
        else:
            erp_stock_lookup = ledger

    classes = []
    if not snapshot_present:
        classes.append("SNAPSHOT_AUSENTE")
    elif not snapshot_value_present:
        classes.append("SNAPSHOT_VALOR_AUSENTE")
    elif snapshot is None:
        classes.append("SNAPSHOT_VALOR_INVALIDO")

    delta_ledger_lots = ledger - lots
    delta_snapshot_ledger = None
    delta_snapshot_lots = None
    if requires_lot and abs(delta_ledger_lots) > TOLERANCE:
        classes.append("LEDGER_VS_LOTES")
    if snapshot_value_present and snapshot is not None:
        # The legacy stock field is exposed as available by stock_context; compare
        # physical sources to snapshot + reserve, keeping all terms explicit.
        expected_physical = float(snapshot) + physical_reserved
        delta_snapshot_ledger = expected_physical - ledger
        if requires_lot or int(product.get("lot_rows") or 0) > 0:
            delta_snapshot_lots = expected_physical - lots
        if abs(delta_snapshot_ledger) > TOLERANCE:
            classes.append("SNAPSHOT_VS_LEDGER")
        if delta_snapshot_lots is not None and abs(delta_snapshot_lots) > TOLERANCE:
            classes.append("SNAPSHOT_VS_LOTES")
    if reserved < -TOLERANCE or available < -TOLERANCE:
        classes.append("RESERVA_INCONSISTENTE")
    movement_count = int(product.get("movement_count") or 0)
    snapshot_qty = float(snapshot) if snapshot_value_present and snapshot is not None else 0.0
    if movement_count == 0 and (abs(snapshot_qty) > TOLERANCE or abs(lots) > TOLERANCE):
        classes.append("SIN_MOVIMIENTOS_CON_STOCK")
    if "legacy_generic" in reference_flags or "reference_absent" in reference_flags:
        classes.append("MOVIMIENTOS_SIN_ORIGEN")
    if "orphan" in reference_flags:
        classes.append("REFERENCIAS_HUERFANAS")
    if "unverifiable" in reference_flags:
        classes.append("REFERENCIAS_NO_VERIFICABLES")
    operational_flags = {"LEDGER_VS_LOTES", "RESERVA_INCONSISTENTE", "SIN_MOVIMIENTOS_CON_STOCK",
                         "MOVIMIENTOS_SIN_ORIGEN", "REFERENCIAS_HUERFANAS", "REFERENCIAS_NO_VERIFICABLES"}
    legacy_flags = {"SNAPSHOT_VS_LEDGER", "SNAPSHOT_VS_LOTES", "SNAPSHOT_AUSENTE",
                    "SNAPSHOT_VALOR_AUSENTE", "SNAPSHOT_VALOR_INVALIDO"}

    is_operational_inconsistent = any(flag in classes for flag in operational_flags)
    has_legacy_warning = any(flag in classes for flag in legacy_flags)

    if is_operational_inconsistent:
        classes.append("REQUIERE_REVISION")
    elif has_legacy_warning:
        classes.append("ALERTA_LEGACY")

    if not classes:
        classes.append("OK")

    quantity_flags = {"LEDGER_VS_LOTES", "RESERVA_INCONSISTENTE", "SIN_MOVIMIENTOS_CON_STOCK"}
    trace_flags = {"MOVIMIENTOS_SIN_ORIGEN", "REFERENCIAS_HUERFANAS", "REFERENCIAS_NO_VERIFICABLES"}
    return {
        **product,
        "ledger_stock": ledger,
        "lot_stock": lots,
        "snapshot_present": snapshot_present,
        "snapshot_value_present": snapshot_value_present,
        "snapshot_stock": snapshot,
        "reserved_stock": reserved,
        "physical_reserved_stock": physical_reserved,
        "reservation_demand": reservation_demand,
        "uncovered_demand": uncovered_demand,
        "physical_stock": physical,
        "physical_source": physical_source,
        "available_stock": available,
        "erp_stock_lookup": erp_stock_lookup,
        "erp_display_physical_if_adds_reserve": erp_stock_lookup + reserved,
        "delta_ledger_lots": delta_ledger_lots,
        "delta_snapshot_ledger": delta_snapshot_ledger,
        "delta_snapshot_lots": delta_snapshot_lots,
        "classifications": classes,
        "operational_inconsistent": is_operational_inconsistent,
        "has_legacy_warning": has_legacy_warning,
        "quantity_investigation": any(x in quantity_flags for x in classes),
        "traceability_investigation": any(x in trace_flags for x in classes),
    }


def classify_reference_type(reference_type: str | None, reference_id: int | None,
                            valid: bool | None) -> str:
    if reference_type == "reconciliation_orphan":
        return "orphan"
    if reference_type in (None, "", "MANUAL_ENTRY", "reconciliation", "initial_seed"):
        return "legacy_generic"
    if reference_id is None:
        return "reference_absent"
    if valid is None:
        return "unverifiable"
    return "valid" if valid else "orphan"


def is_analyzable_product(is_deleted: bool | None) -> bool:
    """Match SQL: NULL and FALSE are active; only TRUE is soft-deleted."""
    return is_deleted is not True


def _load_snapshot_rows(cur):
    cur.execute(PRODUCT_SQL)
    return [dict(r) for r in cur.fetchall()]


def run_audit(include_details=False):
    with connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            rows = _load_snapshot_rows(cur)
            cur.execute("""SELECT id,sku,name FROM products
                           WHERE is_deleted IS NOT TRUE ORDER BY id DESC""")
            products = [dict(r) for r in cur.fetchall()]
            # A reservation belongs to a sale, never to each of its payment rows.
            cur.execute("""SELECT s.products_json
                FROM sales s WHERE s.status='Pendiente'""")
            pending_sales = []
            for row in cur.fetchall():
                try:
                    pending_sales.append({"products": json.loads(row["products_json"] or "[]")})
                except (TypeError, ValueError):
                    pending_sales.append({"products": []})
            cur.execute("""SELECT p.sku,poi.quantity_required AS quantity
                FROM production_order_items poi
                JOIN production_orders po ON po.id=poi.production_order_id
                JOIN products p ON p.id=poi.input_product_id WHERE po.status='Aprobada'
                UNION ALL
                SELECT p.sku,poai.quantity AS quantity
                FROM production_order_additional_items poai
                JOIN production_orders po ON po.id=poai.production_order_id
                JOIN products p ON p.id=poai.input_product_id WHERE po.status='Aprobada'""")
            production_reservations = [dict(r) for r in cur.fetchall()]
            reservations, reservation_summary = calculate_reservations(
                products, pending_sales, production_reservations)
            cur.execute(REFERENCE_SQL)
            reference_summary = [dict(r) for r in cur.fetchall()]
            cur.execute("""SELECT im.product_id, CASE
                WHEN im.reference_type='reconciliation_orphan' THEN 'orphan'
                WHEN im.reference_type IS NULL OR btrim(im.reference_type)=''
                     OR im.reference_type IN ('MANUAL_ENTRY','reconciliation','initial_seed') THEN 'legacy_generic'
                WHEN im.reference_id IS NULL THEN 'reference_absent'
                WHEN im.reference_type='sale' AND EXISTS(SELECT 1 FROM sales x WHERE x.id=im.reference_id) THEN 'valid'
                WHEN im.reference_type='sale_cancellation' AND EXISTS(SELECT 1 FROM sales x WHERE x.id=im.reference_id) THEN 'valid'
                WHEN im.reference_type='purchase_order' AND EXISTS(SELECT 1 FROM purchase_orders x WHERE x.id=im.reference_id) THEN 'valid'
                WHEN im.reference_type='inventory_entry_item' AND EXISTS(SELECT 1 FROM inventory_entry_items x WHERE x.id=im.reference_id) THEN 'valid'
                WHEN im.reference_type='production_order' AND EXISTS(SELECT 1 FROM production_orders x WHERE x.id=im.reference_id) THEN 'valid'
                WHEN im.reference_type='production_order_item' AND EXISTS(SELECT 1 FROM production_order_items x WHERE x.id=im.reference_id) THEN 'valid'
                WHEN im.reference_type IN ('production_order_add_item','production_order_additional_item')
                     AND EXISTS(SELECT 1 FROM production_order_additional_items x WHERE x.id=im.reference_id) THEN 'valid'
                WHEN im.reference_type='inventory_adjustment' AND EXISTS(SELECT 1 FROM inventory_adjustment_requests x WHERE x.id=im.reference_id) THEN 'valid'
                WHEN im.reference_type IN ('sale','sale_cancellation','purchase_order','inventory_entry_item',
                     'production_order','production_order_item','production_order_add_item',
                     'production_order_additional_item','inventory_adjustment') THEN 'orphan'
                ELSE 'unverifiable' END AS reference_status
                FROM inventory_movements im""")
            reference_flags = defaultdict(set)
            product_reference_counts = defaultdict(lambda: defaultdict(int))
            for ref in cur.fetchall():
                status = ref["reference_status"]
                product_reference_counts[ref["product_id"]][status] += 1
                reference_flags[ref["product_id"]].add(status)
            cur.execute("SELECT COUNT(*) AS n FROM products WHERE is_deleted IS TRUE")
            soft_deleted_products = int(cur.fetchone()["n"])
            cur.execute("SELECT COUNT(*) AS n FROM inventory_movements WHERE quantity=0")
            zero_movements = int(cur.fetchone()["n"])
            cur.execute("SELECT COUNT(*) AS n FROM lot_stock WHERE available_qty<0 OR initial_qty<0")
            invalid_lots = int(cur.fetchone()["n"])

    details = []
    for raw in rows:
        row = dict(raw)
        diagnostic = classify_product(
            row, reservations.get(row["sku"], 0),
            reference_flags.get(row["id"], set()))
        diagnostic["reference_counts"] = dict(product_reference_counts.get(row["id"], {}))
        for key in ("cost", "snapshot_stock", "ledger_stock", "lot_stock", "lot_initial",
                    "reserved_stock", "physical_reserved_stock", "physical_stock", "available_stock", "uncovered_demand", "reservation_demand", "erp_stock_lookup",
                    "erp_display_physical_if_adds_reserve", "delta_ledger_lots",
                    "delta_snapshot_ledger", "delta_snapshot_lots"):
            value = diagnostic.get(key)
            if value is not None:
                diagnostic[key] = float(value)
        if diagnostic.get("last_movement") is not None:
            diagnostic["last_movement"] = diagnostic["last_movement"].isoformat()
        details.append(diagnostic)

    total = len(details)
    snapshot_present = sum(bool(row["snapshot_present"]) for row in details)
    quantity_candidates = [row for row in details if row["quantity_investigation"]]
    trace_products = [row for row in details if row["traceability_investigation"]]
    all_review = [row for row in details if row["quantity_investigation"] or row["traceability_investigation"]]
    by_class = defaultdict(int)
    for row in details:
        for label in row["classifications"]:
            by_class[label] += 1
    references = {
        "by_type": reference_summary,
        "movements": sum(int(row["movements"]) for row in reference_summary),
        "valid": sum(int(row["valid_references"]) for row in reference_summary),
        "references_absent": sum(int(row["references_absent"]) for row in reference_summary),
        "references_missing_type_or_id": sum(int(row["references_absent"]) for row in reference_summary)
            + sum(int(row["movements"]) for row in reference_summary if row["reference_type"] == "<NULL>"),
        "orphan": sum(int(row["orphan_references"]) for row in reference_summary),
        "legacy_generic": sum(int(row["legacy_generic"]) for row in reference_summary),
        "unverifiable": sum(int(row["unverifiable"]) for row in reference_summary),
    }
    lot_controlled = [row for row in details if row["requires_lot"]]
    snapshot_comparable = [row for row in details
                           if row["snapshot_value_present"] and row["delta_snapshot_ledger"] is not None]
    snapshot_lot_comparable = [row for row in details if row["delta_snapshot_lots"] is not None]
    summary = {
        "products_analyzed": total,
        "soft_deleted_excluded": soft_deleted_products,
        "snapshot_present": snapshot_present,
        "snapshot_missing": total - snapshot_present,
        "snapshot_value_absent_or_invalid": sum(row["snapshot_present"] and not row["snapshot_value_present"] for row in details),
        "snapshot_coverage_pct": round(snapshot_present * 100 / total, 3) if total else 0.0,
        "snapshot_duplicate_sku_products": sum(int(row["snapshot_rows"]) > 1 for row in details),
        "ledger_vs_lots": sum(abs(row["delta_ledger_lots"]) > TOLERANCE for row in lot_controlled),
        "ledger_vs_lots_absolute_delta": round(sum(abs(row["delta_ledger_lots"]) for row in lot_controlled), 4),
        "snapshot_vs_ledger": sum(abs(row["delta_snapshot_ledger"]) > TOLERANCE for row in snapshot_comparable),
        "snapshot_vs_ledger_absolute_delta": round(sum(abs(row["delta_snapshot_ledger"]) for row in snapshot_comparable), 4),
        "snapshot_vs_lots": sum(abs(row["delta_snapshot_lots"]) > TOLERANCE for row in snapshot_lot_comparable),
        "snapshot_vs_lots_absolute_delta": round(sum(abs(row["delta_snapshot_lots"]) for row in snapshot_lot_comparable), 4),
        "reservation_inconsistent": by_class["RESERVA_INCONSISTENTE"],
        "uncovered_demand_products": sum(row.get("uncovered_demand", 0) > TOLERANCE for row in details),
        "uncovered_demand_units": round(sum(row.get("uncovered_demand", 0) for row in details), 4),
        "reservation_lines_unresolved": reservation_summary["unresolved_sale_lines"],
        "reservation_lines_ambiguous": reservation_summary["ambiguous_sale_lines"],
        "reservation_match_methods": reservation_summary["matched_sale_lines"],
        "operational_integrity": "REQUIRES_REVIEW" if len(all_review) > 0 else "OK",
        "legacy_status": "LEGACY_WARNING" if (by_class["ALERTA_LEGACY"] > 0 or by_class["SNAPSHOT_VS_LEDGER"] > 0 or by_class["SNAPSHOT_VS_LOTES"] > 0 or by_class["SNAPSHOT_AUSENTE"] > 0) else "OK",
        "quantity_investigation_candidates": len(quantity_candidates),
        "traceability_products": len(trace_products),
        "products_requiring_review_union": len(all_review),
        "legacy_warning_products_count": sum(bool(row.get("has_legacy_warning")) for row in details),
        "classifications": dict(sorted(by_class.items())),
        "invalid_lot_stock_rows": invalid_lots,
        "zero_quantity_movements": zero_movements,
        "reference_orphan_movements": references["orphan"],
        "reference_missing_type_or_id": references["references_missing_type_or_id"],
        "reference_generic_movements": references["legacy_generic"],
        "references": references,
        "automatic_quantity_corrections_identified": 0,
    }
    return summary, details if include_details else []


def audit():
    """Backward-compatible summary entry point; now reports classified checks."""
    return run_audit(include_details=False)[0]


def reconcile_inventory():
    """Compatibility API returning the V2 summary and per-product diagnostics."""
    return run_audit(include_details=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Auditoría read-only de fuentes de inventario")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="ejecuta auditoría read-only")
    group.add_argument("--fix", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--details", action="store_true", help="incluye diagnóstico por producto")
    parser.add_argument("--json", action="store_true", help="emite salida JSON estructurada")
    args = parser.parse_args(argv)
    if args.fix:
        parser.error("--fix está deshabilitado en esta versión diagnóstica; no se modificará inventario")
    summary, details = run_audit(include_details=args.details)
    if args.json:
        print(json.dumps({"mode": "check", "summary": summary,
                          **({"products": details} if args.details else {})}, indent=2, ensure_ascii=False, default=str))
    else:
        print("MODO: CHECK (READ ONLY)")
        for key, label in (
            ("operational_integrity", "Integridad operacional"),
            ("legacy_status", "Estado advertencias legacy"),
            ("products_analyzed", "Productos analizados"),
            ("snapshot_present", "Snapshot presente"),
            ("snapshot_missing", "Snapshot ausente"),
            ("snapshot_coverage_pct", "Cobertura legacy (%)"),
            ("quantity_investigation_candidates", "Candidatos de cantidad a investigar (operacionales)"),
            ("ledger_vs_lots", "Ledger vs lotes"),
            ("snapshot_vs_ledger", "Snapshot vs ledger"),
            ("snapshot_vs_lots", "Snapshot vs lotes"),
            ("reservation_inconsistent", "Reservas inconsistentes"),
            ("uncovered_demand_products", "Productos con demanda no cubierta (ventas sin stock)"),
            ("uncovered_demand_units", "Unidades de demanda no cubierta"),
            ("traceability_products", "Productos con alertas de trazabilidad"),
            ("reference_orphan_movements", "Referencias huérfanas"),
            ("reference_missing_type_or_id", "Movimientos sin tipo o ID de referencia"),
            ("reference_generic_movements", "Referencias genéricas/sin origen"),
        ):
            print(f"{label}: {summary[key]}")
        if args.details:
            print(json.dumps(details, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
