#!/usr/bin/env python3
"""Read-only planner for the final development-data cleanup.

This tool deliberately has no write path: the database session is READ ONLY.
It emits the planning report and a separate read-only verification SQL file.
"""
from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "INFORME_PLAN_LIMPIEZA_GREEN.md"
VERIFY = ROOT / "scripts" / "verify_cleanup_development_database.sql"
MANIFEST = ROOT / "scripts" / "cleanup_plan_ids.json"
PAGE_SIZE = 30


def connect():
    load_dotenv(ROOT / ".env")
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"), port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "facturacion"), user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"), cursor_factory=psycopg2.extras.RealDictCursor,
        options="-c default_transaction_read_only=on",
    )
    conn.set_session(readonly=True, autocommit=False, isolation_level="REPEATABLE READ")
    return conn


def rows(cur, table, columns="*"):
    cur.execute(f'SELECT {columns} FROM "{table}"')
    return [dict(r) for r in cur.fetchall()]


def parse_timestamp(value, db_tz):
    if value is None or not str(value).strip():
        return None
    raw = str(value).strip()
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
            dt = datetime.fromisoformat(raw)
        else:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            # Text timestamps without offset use the database session timezone.
            # The report records that assumption; no local machine timezone is used.
            dt = dt.replace(tzinfo=ZoneInfo(db_tz))
        return dt.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return None


def choose_recent(records, n, db_tz):
    good, bad, nulls, formats = [], [], 0, defaultdict(int)
    for row in records:
        raw = row.get("created_at")
        if raw is None or not str(raw).strip():
            nulls += 1
        else:
            s = str(raw).strip()
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s): fmt = "date-only"
            elif "T" in s and re.search(r"(?:Z|[+-]\d{2}:?\d{2})$", s): fmt = "ISO-T-with-offset"
            elif "T" in s: fmt = "ISO-T-naive"
            elif re.search(r"[+-]\d{2}:?\d{2}$", s): fmt = "space-with-offset"
            elif " " in s: fmt = "space-naive"
            else: fmt = "other"
            formats[fmt] += 1
        parsed = parse_timestamp(raw, db_tz)
        if parsed is None:
            if raw is not None and str(raw).strip():
                bad.append((row["id"], str(raw)))
        else:
            good.append((parsed, int(row["id"]), row))
    good.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return {x[2]["id"] for x in good[:n]}, {"parseable": len(good), "invalid": bad,
                                           "null_or_blank": nulls, "rows": len(records),
                                           "formats": dict(formats)}


def json_lines(value):
    try:
        decoded = json.loads(value or "[]")
        return decoded if isinstance(decoded, list) else []
    except (ValueError, TypeError):
        return []


def main():
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database() db, current_setting('TimeZone') tz, current_setting('transaction_read_only') ro")
            meta = dict(cur.fetchone())
            if meta["db"] != "facturacion" or meta["ro"] != "on":
                raise RuntimeError(f"Refused: expected read-only facturacion, got {meta}")

            cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
            tables = [r["tablename"] for r in cur.fetchall()]
            cur.execute("""
                SELECT tc.table_name, kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name=kcu.constraint_name AND tc.constraint_schema=kcu.constraint_schema
                WHERE tc.constraint_type='PRIMARY KEY' AND tc.constraint_schema='public'
                ORDER BY tc.table_name,kcu.ordinal_position
            """)
            pk_columns = defaultdict(list)
            for r in cur.fetchall(): pk_columns[r["table_name"]].append(r["column_name"])
            counts = {}
            for table in tables:
                cur.execute(f'SELECT count(*) n FROM "{table}"')
                counts[table] = int(cur.fetchone()["n"])

            cur.execute("""
                SELECT tc.table_name child, kcu.column_name child_col,
                       ccu.table_name parent, ccu.column_name parent_col,
                       rc.delete_rule
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name=kcu.constraint_name AND tc.constraint_schema=kcu.constraint_schema
                JOIN information_schema.constraint_column_usage ccu
                  ON ccu.constraint_name=tc.constraint_name AND ccu.constraint_schema=tc.constraint_schema
                JOIN information_schema.referential_constraints rc
                  ON rc.constraint_name=tc.constraint_name AND rc.constraint_schema=tc.constraint_schema
                WHERE tc.constraint_type='FOREIGN KEY' AND tc.constraint_schema='public'
                ORDER BY ccu.table_name, tc.table_name, kcu.ordinal_position
            """)
            fks = [dict(r) for r in cur.fetchall()]

            sales = rows(cur, "sales", "id,status,created_at,products_json,sale_number,customer_name,seller_name,notes")
            current_real_sales_count = sum(1 for r in sales if r.get("status") != "Cotización")
            current_quotes_count = sum(1 for r in sales if r.get("status") == "Cotización")
            pos = rows(cur, "purchase_orders")
            ots = rows(cur, "production_orders")
            debts = rows(cur, "debts", "id,created_at,bank_account_id")
            products = rows(cur, "products", "id,sku,name,category,product_type,unit_of_measure,requires_lot,cost,is_deleted")
            byid = {int(p["id"]): p for p in products}
            bysku = {str(p["sku"]).strip().lower(): p["id"] for p in products if p.get("sku")}

            roots = {}
            chronology = {}
            for name, dataset, limit, predicate in (
                ("sales", sales, 30, lambda r: r.get("status") != "Cotización"),
                ("quotes", sales, 30, lambda r: r.get("status") == "Cotización"),
                ("purchase_orders", pos, 30, lambda r: True),
                ("production_orders", ots, 10, lambda r: True),
                ("debts", debts, 10, lambda r: True),
            ):
                subset = [r for r in dataset if predicate(r)]
                roots[name], chronology[name] = choose_recent(subset, limit, meta["tz"])
            original_roots = {name: set(ids) for name, ids in roots.items()}

            # Fetch relations once, inside this repeatable-read, read-only snapshot.
            # Complete snapshot of public rows is bounded (current DB is ~50k rows)
            # and permits a real all-FK simulation instead of extrapolating from a
            # hand-picked subset. No row is written or exported from this planner.
            data = {t: rows(cur, t) for t in tables}
            def index(table, col):
                out = defaultdict(list)
                for r in data.get(table, []):
                    out[r.get(col)].append(r)
                return out
            ix = {
                "sale_items": index("sale_items", "sale_id"),
                "sale_lot": index("sale_lot_movements", "sale_id"),
                "sale_pack": index("sale_packaging_items", "sale_id"),
                "sale_pay_items": index("sale_payment_items", "sale_id"),
                "po_items": index("purchase_order_items", "purchase_order_id"),
                "entries_po": index("inventory_entries", "purchase_order_id"),
                "entry_items": index("inventory_entry_items", "inventory_entry_id"),
                "invoices_po": index("purchase_invoices", "purchase_order_id"),
                "invoices_entry": index("purchase_invoices", "inventory_entry_id"),
                "ot_items": index("production_order_items", "production_order_id"),
                "ot_add": index("production_order_additional_items", "production_order_id"),
                "ot_cons": index("production_lot_consumptions", "production_order_id"),
                "ot_out": index("production_lot_outputs", "production_order_id"),
                "lots_po": index("lots", "purchase_order_id"),
                "lots_entry": index("lots", "inventory_entry_id"),
                "lots_ot": index("lots", "production_order_id"),
                "lots_product": index("lots", "product_id"),
                "stock_product": index("lot_stock", "product_id"),
                "stock_lot": index("lot_stock", "lot_id"),
                "recipe_final": index("product_recipes", "final_product_id"),
                "recipe_items": index("product_recipe_items", "recipe_id"),
                "adjust_product": index("inventory_adjustment_requests", "product_id"),
            }
            keep = {t: set() for t in tables}
            policy_tables = set()
            keep_all_tables = set()
            keep["sales"] = set(roots["sales"] | roots["quotes"])
            policy_tables.add("sales")
            keep["purchase_orders"] = set(roots["purchase_orders"])
            policy_tables.add("purchase_orders")
            keep["production_orders"] = set(roots["production_orders"])
            policy_tables.add("production_orders")
            keep["debts"] = set(roots["debts"])
            policy_tables.add("debts")
            keep["clients"] = {int(r["id"]) for r in data.get("clients", [])}
            policy_tables.add("clients")

            # Treat legacy product identities conservatively; ambiguity is diagnostic,
            # never resolved to an arbitrary product.
            name_index = defaultdict(list)
            for p in products:
                if p.get("name"):
                    name_index[str(p["name"]).strip().lower()].append(int(p["id"]))
            ambiguous_json = []
            def product_id_for_line(line, sale_id):
                if isinstance(line, str):
                    match = re.match(r"^(.*?)\s*\((\d+(?:\.\d+)?)\)$", line.strip())
                    if not match: return None
                    name = match.group(1).strip().lower()
                    exact = name_index.get(name, [])
                    if len(exact) == 1: return exact[0]
                    partial = {pid for n, ids in name_index.items() if n and (n in name or name in n) for pid in ids}
                    if len(partial) == 1: return next(iter(partial))
                    if len(partial) > 1 or len(exact) > 1:
                        ambiguous_json.append({"sale_id": sale_id, "name": name, "candidate_ids": sorted(partial or set(exact))})
                    return None
                if not isinstance(line, dict):
                    return None
                for key in ("product_id", "id"):
                    try:
                        pid = int(line.get(key))
                        if pid in byid:
                            return pid
                    except (TypeError, ValueError):
                        pass
                sku = str(line.get("sku") or line.get("product_sku") or "").strip().lower()
                if sku in bysku:
                    return int(bysku[sku])
                name = str(line.get("product_name") or line.get("name") or "").strip().lower()
                exact = name_index.get(name, [])
                if len(exact) == 1:
                    return exact[0]
                partial = {pid for n, ids in name_index.items() if n and (n in name or name in n) for pid in ids} if name else set()
                if len(partial) == 1:
                    return next(iter(partial))
                if len(partial) > 1 or len(exact) > 1:
                    ambiguous_json.append({"sale_id": sale_id, "name": name, "candidate_ids": sorted(partial or set(exact))})
                return None

            # Fixture markers are evidence, not an automatic exclusion rule. A
            # marked document may still be useful in a development sample when
            # its date, product identities and inventory graph are coherent.
            # Reject only actual structural/quantitative risks below.
            fixture_doc = re.compile(
                r"(?:TEST|E2E|FIXTURE|SEED|DBG|DEBUG|MOCK|CONCURRENT|CONCILI|PRUEBA|RUT\s*MALO|CLINETE|"
                r"CLIENTE\s+(?:PRUEBA|TEST|DEMO|SIN\s+STOCK|\d+)|CLIENTE-AA|\bEEE\b|DEMO|"
                r"ESCENARIO|PARA\s+PDF|HERENCIA|OVERRIDE|HISTORICA|RECEPCION|NOLOT|MP-A-|SEMI-A-|FINAL-A-|"
                r"MP-OT-|PT-OT-|C\d+-MP[AB]-|S\d+-MP[AB]-|PROD\d+-[0-9a-f]{6}|"
                r"SKU-[0-9a-f]{6}|CANT-[0-9a-f]{6}|PART-[AB]-[0-9a-f]{6}|SUPP-[0-9a-f]{6}|DOC-[0-9a-f]{6}|TOTA[AB]?-[0-9a-f]{6})",
                re.I)
            now_utc = datetime.now(timezone.utc)
            ledger_net = defaultdict(float)
            for movement in data.get("inventory_movements", []):
                if movement.get("product_id") is not None:
                    ledger_net[int(movement["product_id"])] += float(movement.get("quantity") or 0)
            lot_net = defaultdict(float)
            for stock in data.get("lot_stock", []):
                if stock.get("product_id") is not None:
                    lot_net[int(stock["product_id"])] += float(stock.get("available_qty") or 0)
            mismatch_product_ids = {int(p["id"]) for p in products if not p.get("is_deleted") and p.get("requires_lot")
                                    and abs(ledger_net[int(p["id"])]-lot_net[int(p["id"])]) > 0.001}
            product_fixture_ids = {int(p["id"]) for p in products
                                   if fixture_doc.search(f"{p.get('sku') or ''} {p.get('name') or ''}")}
            supplier_by_id = {int(r["id"]): r for r in data.get("suppliers", [])}
            rejected_root_reasons = defaultdict(dict)
            rejected_root_counts = defaultdict(lambda: defaultdict(int))
            root_substitutions = defaultdict(list)

            def root_products(kind, row):
                ids, unresolved = set(), False
                if kind in ("sales", "quotes"):
                    for item in ix["sale_items"].get(int(row["id"]), []):
                        if item.get("product_id") is not None: ids.add(int(item["product_id"]))
                    for line in json_lines(row.get("products_json")):
                        pid = product_id_for_line(line, int(row["id"]))
                        if pid is not None: ids.add(pid)
                        elif line not in (None, "", {}): unresolved = True
                elif kind == "purchase_orders":
                    ids.update(int(x["product_id"]) for x in ix["po_items"].get(int(row["id"]), []) if x.get("product_id") is not None)
                elif kind == "production_orders":
                    if row.get("final_product_id") is not None: ids.add(int(row["final_product_id"]))
                    for table in ("ot_items", "ot_add"):
                        for x in ix[table].get(int(row["id"]), []):
                            pid = x.get("input_product_id")
                            if pid is not None: ids.add(int(pid))
                return ids, unresolved

            def has_quote_snapshot(row):
                """A quote is a stored commercial snapshot; it need not reserve stock.

                Permit legacy lines whose product identity cannot be resolved as long
                as the document has non-empty, displayable line snapshots. This does
                not infer a product FK or pull a product into the inventory closure.
                """
                lines = json_lines(row.get("products_json"))
                if not lines:
                    return False
                for line in lines:
                    if isinstance(line, str) and line.strip():
                        continue
                    if isinstance(line, dict) and any(str(line.get(k) or "").strip()
                                                      for k in ("name", "product_name", "sku", "product_sku")):
                        continue
                    return False
                return True

            docs_by_kind = {"sales": sales_by_id if "sales_by_id" in locals() else {int(x["id"]): x for x in sales},
                            "quotes": {int(x["id"]): x for x in sales},
                            "purchase_orders": {int(x["id"]): x for x in pos},
                            "production_orders": {int(x["id"]): x for x in ots}}
            roots_clean = {}
            for kind, dataset, limit, predicate in (
                ("sales", sales, 30, lambda r: r.get("status") != "Cotización"),
                ("quotes", sales, 30, lambda r: r.get("status") == "Cotización"),
                ("purchase_orders", pos, 30, lambda r: True),
                ("production_orders", ots, 10, lambda r: True),
            ):
                eligible = []
                for row in dataset:
                    if not predicate(row): continue
                    doc_id = int(row["id"])
                    text_values = " ".join(str(v) for v in row.values() if isinstance(v, (str, int, float)))
                    parsed_date = parse_timestamp(row.get("created_at"), meta["tz"])
                    reason = None
                    if parsed_date is None: reason = "fecha no parseable"
                    elif parsed_date > now_utc: reason = "fecha futura; probable fixture"
                    pids, unresolved = root_products(kind, row)
                    if kind == "quotes":
                        if reason is None and not has_quote_snapshot(row): reason = "sin snapshot de líneas de cotización utilizable"
                    else:
                        if reason is None and not pids: reason = "sin productos identificables"
                        if reason is None and unresolved: reason = "líneas de producto legacy ambiguas/no resueltas"
                    if reason is None and pids & mismatch_product_ids: reason = "producto involucrado en delta ledger-vs-lotes"
                    if reason:
                        rejected_root_counts[kind][reason] += 1
                        if doc_id in original_roots[kind]: rejected_root_reasons[kind][doc_id] = reason
                        continue
                    eligible.append(row)
                roots_clean[kind], _eligible_chronology = choose_recent(eligible, limit, meta["tz"])
                removed = sorted(original_roots[kind] - roots_clean[kind])
                added = sorted(roots_clean[kind] - original_roots[kind])
                for old_id, new_id in zip(removed, added):
                    root_substitutions[kind].append({"old_id": old_id, "reason": rejected_root_reasons[kind].get(old_id, "reemplazado por criterio de coherencia"), "new_id": new_id})
            roots.update(roots_clean)
            keep["sales"] = set(roots["sales"] | roots["quotes"])
            keep["purchase_orders"] = set(roots["purchase_orders"])
            keep["production_orders"] = set(roots["production_orders"])

            sales_by_id = {int(r["id"]): r for r in sales}
            po_by_id = {int(r["id"]): r for r in pos}
            ot_by_id = {int(r["id"]): r for r in ots}
            debt_by_id = {int(r["id"]): r for r in debts}
            kept_lots, kept_entries, kept_invoices = set(), set(), set()
            products_keep = set()
            suppliers_keep = set()
            iteration_log = []
            previous_signature = None

            # Financial roots are exact semantic references; account targets may be
            # expanded if protected payments/debts require more than ten.
            debt_account_roots = {int(d["bank_account_id"]) for d in debts
                                  if int(d["id"]) in keep["debts"] and d.get("bank_account_id") is not None}
            protected_sales = keep["sales"]
            sale_payment_accounts = {int(r["bank_account_id"]) for r in data.get("sale_payment_items", [])
                                     if int(r.get("sale_id") or -1) in protected_sales and r.get("bank_account_id") is not None}
            protected_sale_payments = {int(r["id"]) for r in data.get("sale_payments", [])
                                       if int(r.get("sale_id") or -1) in protected_sales}
            debt_payment_accounts = {int(r["bank_account_id"]) for r in data.get("debt_payments", [])
                                     if int(r.get("debt_id") or -1) in keep["debts"] and r.get("bank_account_id") is not None}
            installment_to_debt = {int(r["id"]): int(r["debt_id"]) for r in data.get("debt_installments", [])
                                   if r.get("debt_id") is not None}
            debt_payment_accounts = {int(r["bank_account_id"]) for r in data.get("debt_payments", [])
                                     if installment_to_debt.get(int(r.get("debt_installment_id") or -1)) in keep["debts"]
                                     and r.get("bank_account_id") is not None}
            root_po_ids = roots["purchase_orders"]
            invoice_accounts = {int(r["bank_account_id"]) for r in data.get("purchase_invoices", [])
                                if int(r.get("purchase_order_id") or -1) in root_po_ids
                                and r.get("bank_account_id") is not None}
            required_accounts = debt_account_roots | sale_payment_accounts | debt_payment_accounts | invoice_accounts
            account_rows = data.get("bank_accounts", [])
            account_extras = [r for r in account_rows if int(r["id"]) not in required_accounts]
            account_recent, account_chrono = choose_recent(account_extras, max(0, 10-len(required_accounts)), meta["tz"])
            keep["bank_accounts"] = required_accounts | account_recent
            policy_tables.add("bank_accounts")
            chronology["bank_accounts"] = account_chrono

            # Compute a document/product/lot closure to a fixed point. The direction
            # is semantic: a protected product does not pull every historical sale.
            for iteration in range(1, 100):
                before = (frozenset(products_keep), frozenset(keep["purchase_orders"]),
                          frozenset(kept_entries), frozenset(keep["production_orders"]),
                          frozenset(kept_lots), frozenset(kept_invoices), frozenset(suppliers_keep),
                          frozenset(keep["inventory_movements"]))
                for sid in list(protected_sales):
                    sale = sales_by_id[sid]
                    for item in ix["sale_items"].get(sid, []):
                        if item.get("product_id") is not None: products_keep.add(int(item["product_id"]))
                    for line in json_lines(sale.get("products_json")):
                        pid = product_id_for_line(line, sid)
                        if pid is not None: products_keep.add(pid)
                    for item in ix["sale_pack"].get(sid, []):
                        if item.get("product_id") is not None: products_keep.add(int(item["product_id"]))
                    for rel in ix["sale_lot"].get(sid, []):
                        if rel.get("lot_id") is not None: kept_lots.add(int(rel["lot_id"]))

                for poid in list(keep["purchase_orders"]):
                    po = po_by_id.get(poid)
                    if po and po.get("supplier_id") is not None: suppliers_keep.add(int(po["supplier_id"]))
                    for item in ix["po_items"].get(poid, []):
                        if item.get("product_id") is not None: products_keep.add(int(item["product_id"]))
                    for entry in ix["entries_po"].get(poid, []): kept_entries.add(int(entry["id"]))
                    for inv in ix["invoices_po"].get(poid, []): kept_invoices.add(int(inv["id"]))
                    for lot in ix["lots_po"].get(poid, []):
                        # A kept purchase graph retains all its lot rows, including
                        # exhausted lots that remain part of document traceability.
                        if lot.get("id") is not None: kept_lots.add(int(lot["id"]))

                for entry_id in list(kept_entries):
                    entry = next((e for e in data.get("inventory_entries", []) if int(e["id"]) == entry_id), None)
                    if entry:
                        if entry.get("purchase_order_id") is not None: keep["purchase_orders"].add(int(entry["purchase_order_id"]))
                        if entry.get("supplier_id") is not None: suppliers_keep.add(int(entry["supplier_id"]))
                    for item in ix["entry_items"].get(entry_id, []):
                        if item.get("product_id") is not None: products_keep.add(int(item["product_id"]))
                        if item.get("lot_id") is not None: kept_lots.add(int(item["lot_id"]))
                    for lot in ix["lots_entry"].get(entry_id, []):
                        kept_lots.add(int(lot["id"]))
                    for inv in ix["invoices_entry"].get(entry_id, []): kept_invoices.add(int(inv["id"]))

                for otid in list(keep["production_orders"]):
                    ot = ot_by_id.get(otid)
                    if ot and ot.get("final_product_id") is not None: products_keep.add(int(ot["final_product_id"]))
                    for table in ("ot_items", "ot_add"):
                        for item in ix[table].get(otid, []):
                            pid = item.get("input_product_id")
                            if pid is not None: products_keep.add(int(pid))
                    for table in ("ot_cons", "ot_out"):
                        for rel in ix[table].get(otid, []):
                            lot_id = rel.get("input_lot_id") if table == "ot_cons" else rel.get("output_lot_id")
                            if lot_id is not None: kept_lots.add(int(lot_id))
                    for lot in ix["lots_ot"].get(otid, []):
                        # Preserve exhausted output lots too when their OT is kept.
                        kept_lots.add(int(lot["id"]))

                for product_id in list(products_keep):
                    p = byid.get(product_id)
                    if not p: continue
                    for stock in ix["stock_product"].get(product_id, []):
                        if float(stock.get("available_qty") or 0) > 0 and stock.get("lot_id") is not None:
                            kept_lots.add(int(stock["lot_id"]))
                        if float(stock.get("available_qty") or 0) > 0 and stock.get("entry_id") is not None:
                            kept_entries.add(int(stock["entry_id"]))
                    for recipe in ix["recipe_final"].get(product_id, []):
                        rid = int(recipe["id"])
                        keep["product_recipes"].add(rid)
                        for item in ix["recipe_items"].get(rid, []):
                            if item.get("input_product_id") is not None: products_keep.add(int(item["input_product_id"]))
                    for adj in ix["adjust_product"].get(product_id, []):
                        keep["inventory_adjustment_requests"].add(int(adj["id"]))
                    # A product-supplier catalog association is removable with the
                    # association row; it alone does not retain an otherwise unused supplier.

                for lot_id in list(kept_lots):
                    lot = next((l for l in data.get("lots", []) if int(l["id"]) == lot_id), None)
                    if not lot: continue
                    if lot.get("product_id") is not None: products_keep.add(int(lot["product_id"]))
                    for col, table in (("purchase_order_id", "purchase_orders"),
                                       ("inventory_entry_id", "inventory_entries"),
                                       ("production_order_id", "production_orders")):
                        if lot.get(col) is not None: keep[table].add(int(lot[col]))
                    if lot.get("supplier_id") is not None: suppliers_keep.add(int(lot["supplier_id"]))

                kept_entry_item_ids = {int(i["id"]) for entry_id in kept_entries for i in ix["entry_items"].get(entry_id, [])}
                kept_ot_item_ids = {int(i["id"]) for otid in keep["production_orders"] for i in ix["ot_items"].get(otid, [])}
                kept_ot_add_ids = {int(i["id"]) for otid in keep["production_orders"] for i in ix["ot_add"].get(otid, [])}
                movement_keep_ids = set()
                for movement in data.get("inventory_movements", []):
                    rt, ref = movement.get("reference_type"), movement.get("reference_id")
                    try: ref = int(ref) if ref is not None else None
                    except (TypeError, ValueError): ref = None
                    if ((rt in ("sale", "sale_cancellation") and ref in keep["sales"])
                        or (rt == "purchase_order" and ref in keep["purchase_orders"])
                        or (rt == "inventory_entry_item" and ref in kept_entry_item_ids)
                        or (rt == "production_order" and ref in keep["production_orders"])
                        or (rt == "production_order_item" and ref in kept_ot_item_ids)
                        or (rt in ("production_order_add_item", "production_order_additional_item") and ref in kept_ot_add_ids)
                        or (rt == "inventory_adjustment" and ref in keep["inventory_adjustment_requests"])):
                        movement_keep_ids.add(int(movement["id"]))
                        if movement.get("product_id") is not None: products_keep.add(int(movement["product_id"]))
                for adjustment in data.get("inventory_adjustment_requests", []):
                    if int(adjustment["id"]) in keep["inventory_adjustment_requests"] and adjustment.get("movement_id") is not None:
                        movement_keep_ids.add(int(adjustment["movement_id"]))
                keep["inventory_movements"] = movement_keep_ids

                # Reconcile child rows for every retained financial/document root.
                for inv in data.get("purchase_invoices", []):
                    if int(inv["id"]) in kept_invoices and inv.get("supplier_id") is not None:
                        suppliers_keep.add(int(inv["supplier_id"]))
                after = (frozenset(products_keep), frozenset(keep["purchase_orders"]),
                         frozenset(kept_entries), frozenset(keep["production_orders"]),
                         frozenset(kept_lots), frozenset(kept_invoices), frozenset(suppliers_keep),
                         frozenset(keep["inventory_movements"]))
                iteration_log.append({"iteration": iteration, "products": len(products_keep),
                                      "sales": len(keep["sales"]), "purchase_orders": len(keep["purchase_orders"]),
                                      "receipts": len(kept_entries), "production_orders": len(keep["production_orders"]),
                                      "lots": len(kept_lots), "movements": len(keep["inventory_movements"]),
                                      "suppliers": len(suppliers_keep), "clients": len(keep["clients"]),
                                      "accounts": len(keep["bank_accounts"]), "invoices": len(kept_invoices),
                                      "debts": len(keep["debts"])})
                if after == before:
                    break
            else:
                raise RuntimeError("Document closure did not converge in 99 iterations")

            # Financial dependencies and chosen account/supplier sample.
            for row in data.get("debt_installments", []):
                if int(row.get("debt_id") or -1) in keep["debts"]: keep["debt_installments"].add(int(row["id"]))
            for row in data.get("debt_payments", []):
                if installment_to_debt.get(int(row.get("debt_installment_id") or -1)) in keep["debts"]:
                    keep["debt_payments"].add(int(row["id"]))
            for row in data.get("debt_audit", []):
                if row.get("debt_id") is not None and int(row["debt_id"]) in keep["debts"]:
                    keep["debt_audit"].add(int(row["id"]))
            for row in data.get("bank_transactions", []):
                if int(row.get("bank_account_id") or -1) in keep["bank_accounts"]:
                    keep["bank_transactions"].add(int(row["id"]))
                    if row.get("import_id") is not None: keep["bank_transaction_imports"].add(int(row["import_id"]))
            for row in data.get("bank_reconciliation_audit", []):
                if int(row.get("bank_transaction_id") or -1) in keep["bank_transactions"]:
                    keep["bank_reconciliation_audit"].add(int(row["id"]))
            for row in data.get("sale_payments", []):
                if int(row.get("sale_id") or -1) in keep["sales"]: keep["sale_payments"].add(int(row["id"]))
            for table, col in (("sale_payment_items", "sale_id"), ("sales_status_history", "sale_id"),
                               ("sales_payment_history", "sale_id"), ("sale_items", "sale_id"),
                               ("sale_lot_movements", "sale_id"), ("sale_packaging_items", "sale_id"),
                               ("collection_actions", "sale_id")):
                for row in data.get(table, []):
                    if int(row.get(col) or -1) in keep["sales"]: keep[table].add(int(row["id"]))
            for row in data.get("inventory_entries", []):
                if int(row["id"]) in kept_entries: keep["inventory_entries"].add(int(row["id"]))
            for table, col, parents in (("purchase_order_items", "purchase_order_id", keep["purchase_orders"]),
                                        ("inventory_entries", "purchase_order_id", keep["purchase_orders"]),
                                        ("purchase_invoices", "purchase_order_id", keep["purchase_orders"])):
                for row in data.get(table, []):
                    if row.get(col) is not None and int(row[col]) in parents:
                        keep[table].add(int(row["id"]))
                        if table == "inventory_entries": kept_entries.add(int(row["id"]))
                        if table == "purchase_invoices": kept_invoices.add(int(row["id"]))
            for row in data.get("inventory_entry_items", []):
                if int(row.get("inventory_entry_id") or -1) in kept_entries: keep["inventory_entry_items"].add(int(row["id"]))
            for row in data.get("purchase_invoices", []):
                if int(row["id"]) in kept_invoices: keep["purchase_invoices"].add(int(row["id"]))
            for table, col in (("production_order_items", "production_order_id"),
                               ("production_order_additional_items", "production_order_id"),
                               ("production_lot_consumptions", "production_order_id"),
                               ("production_lot_outputs", "production_order_id")):
                for row in data.get(table, []):
                    if int(row.get(col) or -1) in keep["production_orders"]: keep[table].add(int(row["id"]))
            for row in data.get("lots", []):
                lid = int(row["id"])
                if lid in kept_lots: keep["lots"].add(lid)
            for row in data.get("lot_stock", []):
                if int(row.get("lot_id") or -1) in kept_lots or (
                    int(row.get("product_id") or -1) in products_keep and float(row.get("available_qty") or 0) > 0
                ):
                    keep["lot_stock"].add(int(row["id"]))
            for table, col, parent in (("inventory_adjustment_audit", "adjustment_id", keep["inventory_adjustment_requests"]),):
                for row in data.get(table, []):
                    if int(row.get(col) or -1) in parent: keep[table].add(int(row["id"]))

            # Account and supplier counts are lower bounds plus a recent sample.
            account_req = set(required_accounts | debt_payment_accounts)
            for invoice in data.get("purchase_invoices", []):
                if int(invoice["id"]) in kept_invoices and invoice.get("bank_account_id") is not None:
                    account_req.add(int(invoice["bank_account_id"]))
            account_extras = [r for r in account_rows if int(r["id"]) not in account_req]
            account_candidates, account_chrono = choose_recent(account_extras, max(0, 10-len(account_req)), meta["tz"])
            keep["bank_accounts"] = account_req | account_candidates
            suppliers_all = data.get("suppliers", [])
            supplier_required = set(suppliers_keep)
            supplier_extras = [r for r in suppliers_all if int(r["id"]) not in supplier_required]
            supp_recent, supplier_chrono = choose_recent(supplier_extras, max(0, 15-len(supplier_required)), meta["tz"])
            suppliers_keep |= supp_recent
            keep["suppliers"] = suppliers_keep
            # Product optional set: validated masters only, outside noisy test families.
            optional = []
            pattern = re.compile(r"(?:TEST|E2E|FIXTURE|SEED|DBG|DEBUG|MP-A-|SEMI-A-|MP-OT-|PT-OT-|C\d+-MP[AB]-|S\d+-MP[AB]-)", re.I)
            for p in products:
                pid = int(p["id"])
                if pid in products_keep or p.get("is_deleted") is True: continue
                if not p.get("sku") or not str(p.get("sku")).strip() or not p.get("name") or not str(p.get("name")).strip(): continue
                if not p.get("category") or not p.get("unit_of_measure"): continue
                if pattern.search(" ".join(str(p.get(k) or "") for k in ("sku", "name"))): continue
                # Optional master products must not introduce unclosed positive
                # inventory. Stock-bearing products enter only through document,
                # lot, or production roots and their full source graph.
                if any(float(s.get("available_qty") or 0) > 0 for s in ix["stock_product"].get(pid, [])): continue
                if abs(sum(float(m.get("quantity") or 0) for m in data.get("inventory_movements", [])
                           if int(m.get("product_id") or -1) == pid)) > 0.001: continue
                optional.append(pid)
            optional.sort()
            final_products = set(products_keep)
            groups = set()
            ranked = []
            for pid in optional:
                p = byid[pid]
                group = (p.get("category"), p.get("product_type"), p.get("unit_of_measure"))
                if group not in groups:
                    ranked.append(pid)
                    groups.add(group)
            ranked.extend(pid for pid in optional if pid not in set(ranked))
            if len(final_products) < 70: final_products.update(ranked[:70-len(final_products)])
            keep["products"] = final_products

            # Logical movement closure and opening-balance simulation. Movements
            # tied to a retained business document are protected; all other old
            # movements for kept products would be replaced by an explicit opening
            # event, subject to a defensible-cost check.
            kept_sales = keep["sales"]
            kept_po = keep["purchase_orders"]
            kept_ot = keep["production_orders"]
            kept_entry_ids = kept_entries | {int(r["id"]) for r in data.get("inventory_entries", [])
                                              if r.get("purchase_order_id") is not None and int(r["purchase_order_id"]) in kept_po}
            kept_sale_line_ids = keep.get("sale_items", set())
            movements = data.get("inventory_movements", [])
            # Match stock_context.get_operational_balance(): only Pendiente sales
            # reserve stock; approved production orders reserve their inputs.
            pending_statuses = {"Pendiente"}
            products_by_sku = {str(p.get("sku") or ""): p for p in products}
            reserved_before, reserved_after = defaultdict(float), defaultdict(float)
            reservation_ambiguous_before, reservation_ambiguous_after = [], []
            for sale in sales:
                if sale.get("status") not in pending_statuses: continue
                sid = int(sale["id"])
                for line in json_lines(sale.get("products_json")):
                    pid = product_id_for_line(line, sid)
                    if isinstance(line, dict):
                        qty = float(line.get("quantity") or 0)
                        line_name = str(line.get("name") or line.get("product_name") or "")
                    elif isinstance(line, str):
                        match = re.match(r"^(.*?)\s*\((\d+(?:\.\d+)?)\)$", line.strip())
                        qty = float(match.group(2)) if match else 0
                        line_name = match.group(1).strip() if match else line.strip()
                    else:
                        qty, line_name = 0, ""
                    if pid is not None and qty > 0:
                        reserved_before[pid] += qty
                        if sid in kept_sales: reserved_after[pid] += qty
                    elif line_name:
                        # Keep unresolved legacy lines visible in diagnostics; they
                        # never reserve stock against an arbitrary candidate.
                        reservation_ambiguous_before.append((sid, line_name))
                        if sid in kept_sales: reservation_ambiguous_after.append((sid, line_name))
            approved_ot_ids = {int(o["id"]) for o in ots if o.get("status") == "Aprobada"}
            for row in data.get("production_order_items", []):
                if int(row.get("production_order_id") or -1) in approved_ot_ids and row.get("input_product_id") is not None:
                    pid = int(row["input_product_id"]); qty = float(row.get("quantity_required") or 0)
                    reserved_before[pid] += qty
                    if int(row["production_order_id"]) in kept_ot: reserved_after[pid] += qty
            for row in data.get("production_order_additional_items", []):
                if int(row.get("production_order_id") or -1) in approved_ot_ids and row.get("input_product_id") is not None:
                    pid = int(row["input_product_id"]); qty = float(row.get("quantity") or 0)
                    reserved_before[pid] += qty
                    if int(row["production_order_id"]) in kept_ot: reserved_after[pid] += qty

            def ppp_for(pid, product):
                rows_for_product = sorted((m for m in movements if int(m.get("product_id") or -1) == pid),
                                          key=lambda m: (parse_timestamp(m.get("created_at"), meta["tz"]) or datetime.min.replace(tzinfo=timezone.utc), int(m["id"])))
                q, value, ppp = 0.0, 0.0, float(product.get("cost") or 0)
                zero_in = 0
                for m in rows_for_product:
                    qty = float(m.get("quantity") or 0); cost = float(m.get("unit_cost") or 0)
                    if qty > 0:
                        if not m.get("unit_cost") or cost == 0: zero_in += 1
                        q += qty; value += qty * cost
                        if q > 1e-9: ppp = value / q
                    elif qty < 0 and q > 1e-9:
                        used = min(q, abs(qty)); q = max(0.0, q-abs(qty)); value = max(0.0, value-used*ppp)
                        if q <= 1e-9: q, value = 0.0, 0.0
                return ppp, q, value, zero_in

            inventory_sim = []
            opening_rows = []
            for pid in sorted(final_products):
                p = byid[pid]
                ledger_before = sum(float(m.get("quantity") or 0) for m in movements if int(m.get("product_id") or -1) == pid)
                lot_before = sum(float(s.get("available_qty") or 0) for s in ix["stock_product"].get(pid, []))
                physical_before = lot_before if p.get("requires_lot") else ledger_before
                r_before, r_after = reserved_before[pid], reserved_after[pid]
                kept_move = [m for m in movements if int(m.get("product_id") or -1) == pid
                             and int(m["id"]) in keep["inventory_movements"]]
                ledger_after_kept = sum(float(m.get("quantity") or 0) for m in kept_move)
                opening_qty = physical_before - ledger_after_kept
                ppp_before, _, _, zeros_before = ppp_for(pid, p)
                ppp_kept, qty_kept, value_kept, zeros_kept = ppp_for(pid, p)
                # Replay only movements in the protected document set.
                saved_movements = movements
                movements = kept_move
                ppp_kept, qty_kept, value_kept, zeros_kept = ppp_for(pid, p)
                movements = saved_movements
                cost_source = "COSTO_NO_DETERMINABLE"
                trusted_cost = None
                positive_rows = [m for m in movements if int(m.get("product_id") or -1) == pid and float(m.get("quantity") or 0) > 0]
                all_costed = bool(positive_rows) and all(float(m.get("unit_cost") or 0) > 0 for m in positive_rows)
                if all_costed and ppp_before > 0:
                    cost_source = "COSTO_CONFIABLE — PPP ledger sin entradas cero/nulas"
                positive_lots = [s for s in ix["stock_product"].get(pid, []) if float(s.get("available_qty") or 0) > 0]
                if p.get("requires_lot") and positive_lots and all_costed and ppp_before > 0:
                    cost_source = "COSTO_CONFIABLE — PPP ledger sin entradas cero/nulas"
                if abs(opening_qty) > 1e-9 and opening_qty > 0 and cost_source.startswith("COSTO_CONFIABLE") and physical_before > 0:
                    trusted_cost = (ppp_before * physical_before - value_kept) / opening_qty
                    if trusted_cost < 0:
                        trusted_cost = None
                        cost_source = "COSTO_NO_DETERMINABLE — derivación requeriría costo negativo"
                    else:
                        cost_source = "COSTO_DERIVABLE — preserva PPP antes desde ledger documentado"
                ppp_after = ppp_kept
                if opening_qty > 0 and trusted_cost is not None and physical_before > 0:
                    ppp_after = (value_kept + opening_qty*trusted_cost) / physical_before
                elif opening_qty < 0 and qty_kept > 0:
                    ppp_after = ppp_kept
                if abs(opening_qty) > 1e-9:
                    opening_rows.append((pid, p.get("sku"), bool(p.get("requires_lot")), physical_before,
                                         opening_qty, trusted_cost, cost_source, len(kept_move), ledger_before, lot_before))
                inventory_sim.append({"id": pid, "sku": p.get("sku"), "requires_lot": bool(p.get("requires_lot")),
                                      "physical_before": physical_before, "reserved_before": r_before,
                                      "available_before": max(physical_before-r_before, 0),
                                      "ledger_before": ledger_before, "lots_before": lot_before,
                                      "ledger_after_kept": ledger_after_kept,
                                      "physical_after_simulated": physical_before,
                                      "reserved_after": r_after,
                                      "available_after": max(physical_before-r_after, 0),
                                      "ppp_before": ppp_before, "zero_cost_inbound": zeros_before,
                                      "ppp_after_simulated": ppp_after,
                                      "opening_qty": opening_qty, "opening_cost": trusted_cost,
                                      "cost_class": cost_source,
                                      "opening_reason": "saldo físico actual menos movimientos de documentos protegidos"})

            # Baseline PPP zero-cost totals and retained-vs-removable split.
            zeros_total = [m for m in movements if float(m.get("quantity") or 0) > 0 and (m.get("unit_cost") is None or float(m.get("unit_cost") or 0) == 0)]
            zero_survivors = []
            for m in zeros_total:
                try: rid = int(m.get("reference_id")) if m.get("reference_id") is not None else None
                except (ValueError, TypeError): rid = None
                rt = m.get("reference_type") or ""
                keep_ref = ((rt in ("sale", "sale_cancellation") and rid in kept_sales)
                            or (rt == "purchase_order" and rid in kept_po)
                            or (rt.startswith("production_order") and rid in kept_ot))
                if int(m.get("id") or -1) in keep["inventory_movements"] and keep_ref:
                    zero_survivors.append(m)

            # Fill the ID keep sets for the retained roots and their direct children.
            keep["products"] = final_products
            keep["suppliers"] = suppliers_keep
            for row in data.get("product_suppliers", []):
                if (int(row.get("product_id") or -1) in final_products
                        and int(row.get("supplier_id") or -1) in suppliers_keep):
                    keep["product_suppliers"].add(int(row["id"]))
            for row in data.get("supplier_contacts", []):
                if int(row.get("supplier_id") or -1) in suppliers_keep: keep["supplier_contacts"].add(int(row["id"]))
            for row in data.get("product_recipes", []):
                if int(row.get("final_product_id") or -1) in products_keep: keep["product_recipes"].add(int(row["id"]))
            for row in data.get("product_recipe_items", []):
                if int(row.get("recipe_id") or -1) in keep.get("product_recipes", set()): keep["product_recipe_items"].add(int(row["id"]))
            final_skus = {str(byid[pid].get("sku")) for pid in final_products if byid[pid].get("sku")}
            keep["product_margins"] = {str(r.get("product_sku")) for r in data.get("product_margins", [])
                                       if str(r.get("product_sku") or "") in final_skus}
            # Safe configuration/master tables are retained as complete reference sets.
            for t in ("roles", "users", "client_categories", "bank_transaction_categories", "expense_categories",
                      "debt_types", "schema_migrations", "excel_import_previews"):
                if t in tables:
                    keep_all_tables.add(t)
            for row in data.get("bank_transactions", []):
                if int(row.get("bank_account_id") or -1) in keep["bank_accounts"]: keep["bank_transactions"].add(int(row["id"]))
            for row in data.get("bank_reconciliation_audit", []):
                if int(row.get("bank_transaction_id") or -1) in keep["bank_transactions"]: keep["bank_reconciliation_audit"].add(int(row["id"]))
            for row in data.get("bank_transaction_imports", []):
                if int(row.get("id") or -1) in {int(x.get("import_id") or -1) for x in data.get("bank_transactions", []) if int(x.get("id") or -1) in keep["bank_transactions"]}:
                    keep["bank_transaction_imports"].add(int(row["id"]))

            # Remaining tables have no cleanup policy and are conservatively kept.
            # This is deliberate: a partial graph must never imply a DELETE set.
            policy_tables.update({
                "sales", "sale_items", "sale_payments", "sale_payment_items", "sale_lot_movements",
                "sale_packaging_items", "sales_status_history", "sales_payment_history", "collection_actions",
                "purchase_orders", "purchase_order_items", "inventory_entries", "inventory_entry_items",
                "purchase_invoices", "production_orders", "production_order_items",
                "production_order_additional_items", "production_lot_consumptions", "production_lot_outputs",
                "debts", "debt_installments", "debt_payments", "debt_audit", "bank_accounts",
                "bank_transactions", "bank_transaction_imports", "bank_reconciliation_audit",
                "products", "product_suppliers", "product_recipes", "product_recipe_items", "product_margins",
                "suppliers", "supplier_contacts", "lots", "lot_stock", "inventory_movements",
                "inventory_adjustment_requests", "inventory_adjustment_audit", "clients"
            })
            # Operational expenses are not roots of this cleanup. Keep only complete
            # expense graphs. Occurrences may reference a different bank account,
            # so include that account before freezing bank rows; never retain a
            # parent while silently dropping one of its occurrences.
            for row in data.get("operational_expenses", []):
                if row.get("bank_account_id") is None or int(row["bank_account_id"]) in keep["bank_accounts"]:
                    keep["operational_expenses"].add(int(row["id"]))
            expense_account_ids = {int(r["bank_account_id"]) for r in data.get("operational_expense_occurrences", [])
                                   if int(r.get("expense_id") or -1) in keep["operational_expenses"]
                                   and r.get("bank_account_id") is not None}
            keep["bank_accounts"].update(expense_account_ids)
            account_req.update(expense_account_ids)
            for row in data.get("operational_expense_occurrences", []):
                if int(row.get("expense_id") or -1) in keep["operational_expenses"]:
                    keep["operational_expense_occurrences"].add(int(row["id"]))
            for row in data.get("operational_expense_audit", []):
                if int(row.get("expense_id") or -1) in keep["operational_expenses"]:
                    keep["operational_expense_audit"].add(int(row["id"]))
            for row in data.get("bank_transactions", []):
                if int(row.get("bank_account_id") or -1) in keep["bank_accounts"]:
                    keep["bank_transactions"].add(int(row["id"]))
                    if row.get("import_id") is not None: keep["bank_transaction_imports"].add(int(row["import_id"]))
            for row in data.get("bank_reconciliation_audit", []):
                if int(row.get("bank_transaction_id") or -1) in keep["bank_transactions"]:
                    keep["bank_reconciliation_audit"].add(int(row["id"]))
            policy_tables.update({"operational_expenses", "operational_expense_occurrences", "operational_expense_audit"})

            def row_key(table, row):
                cols = pk_columns.get(table, [])
                if len(cols) == 1: return row.get(cols[0])
                if len(cols) > 1: return tuple(row.get(c) for c in cols)
                return None
            def retained(table, row):
                if table in keep_all_tables or table not in policy_tables: return True
                return row_key(table, row) in keep.get(table, set())

            child_edges = {
                "SALES": [(t, "sale_id", keep["sales"]) for t in (
                    "sale_items", "sale_payments", "sale_payment_items", "sale_lot_movements",
                    "sale_packaging_items", "sales_payment_history", "sales_status_history", "collection_actions")],
                "PURCHASE": [("purchase_order_items", "purchase_order_id", keep["purchase_orders"]),
                             ("inventory_entries", "purchase_order_id", keep["purchase_orders"]),
                             ("purchase_invoices", "purchase_order_id", keep["purchase_orders"]),
                             ("inventory_entry_items", "inventory_entry_id", kept_entries),
                             ("purchase_invoices", "inventory_entry_id", kept_entries),
                             ("lots", "purchase_order_id", keep["purchase_orders"]),
                             ("lots", "inventory_entry_id", kept_entries)],
                "PRODUCTION": [(t, "production_order_id", keep["production_orders"]) for t in (
                    "production_order_items", "production_order_additional_items", "production_lot_consumptions",
                    "production_lot_outputs", "lots")],
                "RECIPES": [("product_recipes", "final_product_id", final_products),
                            ("product_recipe_items", "recipe_id", keep["product_recipes"])],
                "FINANCE": [("debt_installments", "debt_id", keep["debts"]),
                            ("debt_audit", "debt_id", keep["debts"]),
                            ("debt_payments", "debt_installment_id", keep["debt_installments"]),
                            ("bank_transactions", "bank_account_id", keep["bank_accounts"]),
                            ("bank_reconciliation_audit", "bank_transaction_id", keep["bank_transactions"]),
                            ("bank_transaction_imports", "id", {int(r.get("import_id")) for r in data.get("bank_transactions", [])
                                                                    if int(r.get("id") or -1) in keep["bank_transactions"] and r.get("import_id") is not None}),
                            ("operational_expense_occurrences", "expense_id", keep["operational_expenses"]),
                            ("operational_expense_audit", "expense_id", keep["operational_expenses"])],
                "LOT STOCK": [("lot_stock", "lot_id", kept_lots)],
            }
            child_gaps = defaultdict(list)
            for group, edges in child_edges.items():
                for child_table, fk_column, protected_parent_ids in edges:
                    for child_row in data.get(child_table, []):
                        parent_id = child_row.get(fk_column)
                        try: parent_id = int(parent_id) if parent_id is not None else None
                        except (ValueError, TypeError): pass
                        if parent_id in protected_parent_ids and not retained(child_table, child_row):
                            child_gaps[group].append((child_table, row_key(child_table, child_row), fk_column, parent_id))

            # Simulate FK orphaning: every retained child referencing a removed parent
            # is a blocker. Composite FK constraints are separately reported.
            fk_issues = []
            for fk in fks:
                child, cc, parent, pc = fk["child"], fk["child_col"], fk["parent"], fk["parent_col"]
                if child not in keep or parent not in keep: continue
                childrows = data.get(child)
                parentrows = data.get(parent)
                if childrows is None or parentrows is None: continue
                pmap = {r.get(pc) for r in parentrows}
                for cr in childrows:
                    cid = row_key(child, cr)
                    if not retained(child, cr): continue
                    value = cr.get(cc)
                    if value is not None and value not in pmap:
                        fk_issues.append((child, cc, parent, pc, cid, value, "preexisting_orphan"))
                    elif value is not None and not any(row.get(pc) == value and retained(parent, row) for row in parentrows):
                        fk_issues.append((child, cc, parent, pc, cid, value, "would_orphan"))

            # Inventory reference rows that lack FK constraints are audited too.
            movement_refs = defaultdict(int)
            retained_movement_ref_issues = []
            movement_ref_type_counts = defaultdict(lambda: {"total": 0, "retained": 0})
            for m in movements:
                rt, rid = m.get("reference_type"), m.get("reference_id")
                ref_bucket = movement_ref_type_counts[str(rt) if rt is not None else "<NULL>"]
                ref_bucket["total"] += 1
                if int(m.get("id") or -1) in keep["inventory_movements"]:
                    ref_bucket["retained"] += 1
                if rt in ("sale", "sale_cancellation") and rid is not None and int(rid) not in keep["sales"]:
                    movement_refs["sale movement refs to deleted docs"] += 1
                elif rt == "purchase_order" and rid is not None and int(rid) not in keep["purchase_orders"]:
                    movement_refs["PO movement refs to deleted docs"] += 1
                elif rt == "production_order" and rid is not None and int(rid) not in keep["production_orders"]:
                    movement_refs["OT movement refs to deleted docs"] += 1
                if int(m.get("id") or -1) not in keep["inventory_movements"]:
                    continue
                try:
                    ref_id = int(rid) if rid is not None else None
                except (TypeError, ValueError):
                    ref_id = None
                valid = None
                if rt in ("sale", "sale_cancellation"):
                    valid = ref_id in keep["sales"]
                elif rt == "purchase_order":
                    valid = ref_id in keep["purchase_orders"]
                elif rt == "production_order":
                    valid = ref_id in keep["production_orders"]
                elif rt == "inventory_entry_item":
                    valid = ref_id in keep["inventory_entry_items"]
                elif rt == "production_order_item":
                    valid = ref_id in keep["production_order_items"]
                elif rt in ("production_order_add_item", "production_order_additional_item"):
                    valid = ref_id in keep["production_order_additional_items"]
                elif rt == "inventory_adjustment":
                    valid = ref_id in keep["inventory_adjustment_requests"]
                if valid is False:
                    retained_movement_ref_issues.append((m.get("id"), rt, rid, "origen fuera del KEEP_SET"))
                elif valid is None:
                    retained_movement_ref_issues.append((m.get("id"), rt, rid, "tipo legacy/genérico sin regla de cierre"))

            # Approximate DELETE_SET from explicit keep-ID sets; unspecified tables
            # remain wholly retained and therefore expose missing semantic decisions.
            tables_without_policy = [t for t in tables if t not in policy_tables and t not in keep_all_tables]
            delete_summary = []
            for t in tables:
                if t in keep_all_tables or t not in policy_tables:
                    delete_summary.append((t, counts[t], counts[t], 0,
                                           "sin política de eliminación; se conserva para no inferir DELETE"))
                else:
                    k = keep.get(t, set())
                    delete_summary.append((t, counts[t], len(k), counts[t]-len(k), "KEEP_SET simulado"))

            def row_key(table, row):
                cols = pk_columns.get(table, [])
                if len(cols) == 1: return row.get(cols[0])
                if len(cols) > 1: return tuple(row.get(c) for c in cols)
                return None
            def json_key(value):
                return value if value is None or isinstance(value, (str, int, float, bool)) else str(value)
            def retained(table, row):
                if table in keep_all_tables or table not in policy_tables: return True
                return row_key(table, row) in keep.get(table, set())
            manifest = {"database": meta["db"], "read_only": meta["ro"],
                        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                        "ready_to_execute": False,
                        "warning": "Provisional simulation; never execute these candidate IDs directly.",
                        "tables": {}}
            for t in tables:
                keep_ids, delete_ids = [], []
                for row in data.get(t, []):
                    value = json_key(row_key(t, row))
                    if retained(t, row): keep_ids.append(value)
                    elif t in policy_tables: delete_ids.append(value)
                manifest["tables"][t] = {"total": counts[t], "primary_key": pk_columns.get(t, []),
                                         "policy": "keep_set" if t in policy_tables else ("keep_all" if t in keep_all_tables else "undecided_keep_all"),
                                         "keep_ids": keep_ids, "delete_candidate_ids": delete_ids}
            MANIFEST.parent.mkdir(parents=True, exist_ok=True)
            MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, default=str)+"\n", encoding="utf-8")

            graph = {t: set() for t in tables}
            for fk in fks: graph.setdefault(fk["child"], set()).add(fk["parent"])
            indegree = {t: 0 for t in graph}
            for parents in graph.values():
                for parent in parents: indegree[parent] += 1
            ready = sorted(t for t,n in indegree.items() if n == 0)
            delete_order = []
            while ready:
                child = ready.pop(0); delete_order.append(child)
                for parent in sorted(graph[child]):
                    indegree[parent] -= 1
                    if indegree[parent] == 0: ready.append(parent); ready.sort()
            fk_cycles = sorted(t for t,n in indegree.items() if n > 0)

            snapshot_total = snapshot_stale = 0
            final_skus = {str(byid[pid].get("sku")) for pid in final_products if byid[pid].get("sku")}
            for pd in data.get("page_data", []):
                if pd.get("key") != "inventory_items": continue
                try: snap = json.loads(pd.get("json") or "[]")
                except (ValueError, TypeError): snap = []
                if isinstance(snap, list):
                    snapshot_total = len(snap)
                    snapshot_stale = sum(1 for x in snap if isinstance(x, dict) and x.get("code") not in final_skus)

            ledger_by_product = defaultdict(float)
            for movement in movements:
                if movement.get("product_id") is not None:
                    ledger_by_product[int(movement["product_id"])] += float(movement.get("quantity") or 0)
            lot_by_product = defaultdict(float)
            for stock in data.get("lot_stock", []):
                if stock.get("product_id") is not None:
                    lot_by_product[int(stock["product_id"])] += float(stock.get("available_qty") or 0)
            v2_mismatches = {int(p["id"]): abs(ledger_by_product[int(p["id"])]-lot_by_product[int(p["id"])])
                             for p in products if not p.get("is_deleted") and p.get("requires_lot")
                             and abs(ledger_by_product[int(p["id"])]-lot_by_product[int(p["id"])]) > 0.001}
            sim_by_id = {r["id"]: r for r in inventory_sim}
            root_product_sources = defaultdict(list)
            root_datasets = {"sales": data.get("sales", []), "purchase_orders": data.get("purchase_orders", []),
                             "production_orders": data.get("production_orders", [])}
            for kind, ids in (("VENTA/COTIZACIÓN", roots["sales"] | roots["quotes"]),
                              ("OC", roots["purchase_orders"]), ("OT", roots["production_orders"])):
                table = "sales" if kind == "VENTA/COTIZACIÓN" else ("purchase_orders" if kind == "OC" else "production_orders")
                records = {int(x["id"]): x for x in data.get(table, [])}
                for doc_id in ids:
                    record = records.get(int(doc_id))
                    if record is None: continue
                    root_kind = ("quotes" if kind == "VENTA/COTIZACIÓN" and record.get("status") == "Cotización" else
                                 "sales" if kind == "VENTA/COTIZACIÓN" else
                                 "purchase_orders" if kind == "OC" else "production_orders")
                    pids, _ = root_products(root_kind, record)
                    for pid in pids:
                        root_product_sources[pid].append((kind, int(doc_id), record.get("created_at"), record))

            root_change_lines = []
            root_table_rows = {"sales": {int(x["id"]): x for x in data.get("sales", [])},
                               "purchase_orders": {int(x["id"]): x for x in data.get("purchase_orders", [])},
                               "production_orders": {int(x["id"]): x for x in data.get("production_orders", [])}}
            for kind in ("sales", "quotes", "purchase_orders", "production_orders"):
                original_ids, final_ids = original_roots[kind], roots[kind]
                table = "sales" if kind in ("sales", "quotes") else kind
                records = root_table_rows[table]
                def chronological_ids(ids):
                    return sorted(ids, key=lambda doc_id: (
                        parse_timestamp(records.get(int(doc_id), {}).get("created_at"), meta["tz"])
                        or datetime.min.replace(tzinfo=timezone.utc), int(doc_id)), reverse=True)
                removed, added = chronological_ids(original_ids-final_ids), chronological_ids(final_ids-original_ids)
                for old_id, new_id in zip(removed, added):
                    old = records.get(int(old_id), {})
                    new = records.get(int(new_id), {})
                    label = {"sales":"VENTA", "quotes":"COTIZACIÓN", "purchase_orders":"OC", "production_orders":"OT"}[kind]
                    root_change_lines.append(f"| {label} | {old_id} | {rejected_root_reasons[kind].get(old_id, 'fixture/no pasa filtros de coherencia')} | {new_id} | {new.get('created_at','')} |")
                for old_id in removed[len(added):]:
                    old = records.get(int(old_id), {})
                    label = {"sales":"VENTA", "quotes":"COTIZACIÓN", "purchase_orders":"OC", "production_orders":"OT"}[kind]
                    root_change_lines.append(f"| {label} | {old_id} | {rejected_root_reasons[kind].get(old_id, 'fixture/no pasa filtros de coherencia')} | SIN SUSTITUTO COHERENTE | {old.get('created_at','')} |")

            opening_attribution = []
            lot_records_by_product = defaultdict(list)
            for lot in data.get("lots", []):
                if lot.get("product_id") is not None:
                    lot_records_by_product[int(lot["product_id"])].append(lot)
            for opening in opening_rows:
                pid = int(opening[0]); sim = sim_by_id.get(pid, {}); product = byid.get(pid, {})
                sources = root_product_sources.get(pid, [])
                source_text = "; ".join(f"{kind} {doc_id} ({created_at})" for kind,doc_id,created_at,_ in sources) or "sin referencia directa a raíz"
                marker_text = "sí" if fixture_doc.search(str(product.get("sku") or "")+" "+str(product.get("name") or "")) else "no"
                lot_origins = []
                for lot in lot_records_by_product.get(pid, []):
                    if int(lot["id"]) in kept_lots:
                        origin = f"lote {lot['id']} {lot.get('origin_type')}:{lot.get('origin_id')} PO:{lot.get('purchase_order_id')} entrada:{lot.get('inventory_entry_id')} OT:{lot.get('production_order_id')}"
                        lot_origins.append(origin)
                if lot_origins and not sources: source_text = "; ".join(lot_origins)
                opening_attribution.append(f"| {pid} | {product.get('sku','')} | {source_text} | {marker_text} | {sim.get('physical_before',0):.4f} | {sim.get('ledger_before',0):.4f} | {sim.get('lots_before',0):.4f} | {opening[4]:.4f} | {sim.get('ppp_before',0):.4f} | {opening[5] if opening[5] is not None else 'sin costo apertura defendible'} | {opening[6]} |")
            lot_audit_lines = []
            lot_by_id = {int(x["id"]): x for x in data.get("lots", [])}
            for lot_id in sorted(kept_lots):
                lot = lot_by_id.get(int(lot_id), {})
                stock_rows = ix["stock_lot"].get(lot_id, [])
                available = sum(float(x.get("available_qty") or 0) for x in stock_rows)
                source_values = []
                for col, table, keep_table in (("purchase_order_id", "OC", "purchase_orders"),
                                               ("inventory_entry_id", "RECEPCIÓN", "inventory_entries"),
                                               ("production_order_id", "OT", "production_orders")):
                    source_id = lot.get(col)
                    if source_id is not None:
                        source_values.append(f"{table} {source_id} ({'KEEP' if int(source_id) in keep.get(keep_table, set()) else 'ELIMINAR'})")
                if not source_values and lot.get("origin_type"):
                    source_values.append(f"{lot.get('origin_type')}:{lot.get('origin_id')} (polimórfico/no resuelto)")
                sku = byid.get(int(lot.get("product_id") or -1), {}).get("sku", "")
                cost_sources = []
                for source_name, source_row in [("lots", lot)] + [("lot_stock", x) for x in stock_rows]:
                    for field, value in source_row.items():
                        try: cost_value = float(value or 0)
                        except (TypeError, ValueError): continue
                        if value is not None and "cost" in field.lower() and cost_value > 0:
                            cost_sources.append((source_name + "." + field, value))
                entry_id = lot.get("inventory_entry_id")
                if entry_id is not None:
                    for entry_item in data.get("inventory_entry_items", []):
                        if int(entry_item.get("inventory_entry_id") or -1) == int(entry_id) and int(entry_item.get("product_id") or -1) == int(lot.get("product_id") or -2):
                            for field, value in entry_item.items():
                                try: cost_value = float(value or 0)
                                except (TypeError, ValueError): continue
                                if value is not None and "cost" in field.lower() and cost_value > 0:
                                    cost_sources.append(("inventory_entry_items." + field, value))
                cost = "; ".join(f"{value} ({field})" for field, value in cost_sources) or "—"
                lot_audit_lines.append(f"| {lot_id} | {lot.get('product_id','')} | {sku} | {available:.4f} | {cost} | {'; '.join(source_values) or 'sin origen explícito'} |")
            child_audit_lines = []
            sales_children_ok = True
            for sid in sorted(keep["sales"]):
                row = sales_by_id.get(sid, {})
                item_count = sum(1 for x in data.get("sale_items", []) if int(x.get("sale_id") or -1) == sid)
                pay_count = sum(1 for x in data.get("sale_payments", []) if int(x.get("sale_id") or -1) == sid)
                status_count = sum(1 for x in data.get("sales_status_history", []) if int(x.get("sale_id") or -1) == sid)
                snapshot_count = len(json_lines(row.get("products_json")))
                complete = (snapshot_count > 0 if row.get("status") == "Cotización"
                            else (item_count > 0 or snapshot_count > 0))
                sales_children_ok = sales_children_ok and complete
                child_audit_lines.append(f"| {sid} | {row.get('status','')} | {item_count} | {snapshot_count} | {pay_count} | {status_count} |")
            ledger_lot_classes = defaultdict(list)
            fixture_marker = re.compile(r"(?:TEST|E2E|FIXTURE|SEED|DBG|DEBUG|MP-A-|SEMI-A-|MP-OT-|PT-OT-|C\d+-MP[AB]-|S\d+-MP[AB]-)", re.I)
            for pid, delta in v2_mismatches.items():
                if pid not in final_products:
                    p = byid.get(pid, {})
                    marker = " ".join(str(p.get(k) or "") for k in ("sku", "name"))
                    category = ("A — fuera del KEEP_SET y con marcador fixture explícito; candidato a desaparecer con su grafo"
                                if fixture_marker.search(marker) else
                                "D — fuera del KEEP_SET pero sin marcador concluyente; requiere clasificación manual")
                else:
                    sim = sim_by_id.get(pid)
                    if sim and sim["cost_class"].startswith("COSTO_DERIVABLE") and sim["opening_qty"] >= 0:
                        category = "C — protegido; apertura derivable propuesta, no ejecutada"
                    elif sim and sim["cost_class"].startswith("COSTO_NO_DETERMINABLE"):
                        category = "D — protegido; investigación manual de costo/origen"
                    else:
                        category = "B — protegido; diferencia permanece y requiere decisión"
                ledger_lot_classes[category].append((pid, delta))

            # Render report.
            def fmt_rows(vals, maxn=20):
                if not vals: return "Ninguno."
                return ", ".join(f"id={i}: `{v}`" for i,v in vals[:maxn]) + (f" (y {len(vals)-maxn} más)" if len(vals)>maxn else "")
            lines = [
                "# Plan de limpieza de `facturacion` — simulación READ ONLY", "",
                f"**Fecha UTC:** {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
                f"**Base verificada:** `{meta['db']}`; transacción read-only `{meta['ro']}`; timezone PostgreSQL `{meta['tz']}`.",
                "**No se ejecutaron INSERT, UPDATE, DELETE, TRUNCATE ni DDL.**", "",
                "## ROOT SET", "",
                f"- Ventas: {len(roots['sales'])} (no cotizaciones), escogidas por `created_at` parseado DESC, `id` DESC.",
                f"- Cotizaciones: {len(roots['quotes'])}, escogidas por `created_at` parseado DESC, `id` DESC.",
                f"- OC raíz: {len(roots['purchase_orders'])}; OT raíz: {len(roots['production_orders'])}; deudas raíz: {len(roots['debts'])}.",
                f"- Clientes: todos los {len(keep['clients'])} existentes (máximo 10).",
                f"- Cuentas raíz: {len(keep['bank_accounts'])}; mínimo observado requerido por pagos/deudas/facturas protegidos: {len(account_req)} (por encima del objetivo 10).",
                "",
                "## Cronología normalizada", "",
                "El parser usa `datetime.fromisoformat`, interpreta los valores naive en la zona PostgreSQL de la sesión, normaliza a UTC y nunca ordena TEXT lexicográficamente.",
                "| Fuente | Filas | Parseables | NULL/vacíos | No parseables | Formatos encontrados | Muestras no parseables |", "|---|---:|---:|---:|---|---|---|",
            ]
            for name, st in chronology.items():
                formats = ", ".join(f"{k}: {v}" for k,v in sorted(st.get("formats", {}).items())) or "—"
                lines.append(f"| `{name}.created_at` | {st['rows']} | {st['parseable']} | {st['null_or_blank']} | {len(st['invalid'])} | {formats} | {fmt_rows(st['invalid'], 5)} |")
            lines += ["", "### IDs exactos de ROOT_SET", "",
                      "El manifiesto `scripts/cleanup_plan_ids.json` contiene los IDs del snapshot para raíces y KEEP_SET parciales. Marca `ready_to_execute=false`; sus `delete_candidate_ids` son sólo candidatos de tablas con regla parcial y no autorizan ejecución.",
                      f"- Ventas raíz: `{','.join(map(str, sorted(roots['sales'])))}`",
                      f"- Cotizaciones raíz: `{','.join(map(str, sorted(roots['quotes'])))}`",
                      f"- OC raíz: `{','.join(map(str, sorted(roots['purchase_orders'])))}`",
                      f"- OT raíz: `{','.join(map(str, sorted(roots['production_orders'])))}`",
                      f"- Deudas raíz: `{','.join(map(str, sorted(roots['debts'])))}`",
                      f"- Pares documento/línea con identidad de producto ambigua al leer JSON: {len({(x['sale_id'], x['name'], tuple(x['candidate_ids'])) for x in ambiguous_json})}; no se asociaron arbitrariamente.",
                      f"- Raíces que pasan cronología/identidad y filtros cuantitativos: ventas {len(roots['sales'])}/30, cotizaciones {len(roots['quotes'])}/30, OC {len(roots['purchase_orders'])}/30, OT {len(roots['production_orders'])}/10. Los marcadores de fixture no se excluyen por sí solos.",
                      "", "### Roots descartados y sustituciones", "",
                      "| Tipo | Root original | Motivo | Sustituto | Fecha del sustituto/root descartado |", "|---|---:|---|---:|---|"]
            if root_change_lines:
                lines.extend(root_change_lines)
            else:
                lines.append("| — | — | No hubo sustituciones | — | — |")
            lines += ["", "### Candidatos rechazados por causa", "",
                      "Los marcadores TEST/E2E/FIXTURE se reportan como indicios y por sí solos no descartan un documento.",
                      "| Tipo | Motivo objetivo de rechazo | Documentos |", "|---|---|---:|"]
            for kind in ("sales", "quotes", "purchase_orders", "production_orders"):
                for reason, amount in sorted(rejected_root_counts[kind].items()):
                    lines.append(f"| {kind} | {reason} | {amount} |")
            if not any(rejected_root_counts.values()):
                lines.append("| — | Ninguno | 0 |")
            lines += ["", "## Cierre recursivo", "", "| Iteración | Productos | Ventas | OC | Recepciones | OT | Lotes | Movimientos | Proveedores | Clientes | Cuentas | Facturas | Deudas |", "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
            for it in iteration_log:
                lines.append("| " + " | ".join(str(it[k]) for k in ("iteration","products","sales","purchase_orders","receipts","production_orders","lots","movements","suppliers","clients","accounts","invoices","debts")) + " |")
            lines += ["", f"Punto fijo alcanzado en {len(iteration_log)} iteraciones. El cierre documenta productos/lotes/orígenes seleccionados; movimientos genéricos y snapshots legacy no se convierten en documentos fuente.",
                      f"Productos obligatorios del cierre calculado: **{len(products_keep)}**. Productos opcionales elegibles: {len(optional)}. Productos simulados finales: **{len(final_products)}**.",
                      "La selección opcional usa sólo maestros válidos y no eliminados, excluye marcadores de fixtures y exige que no introduzcan stock positivo sin su grafo documental.", "",
                      "## Inventario por producto protegido", "",
                      "La cantidad física simulada se conserva en su fuente actual (lotes para `requires_lot`, ledger para el resto); las reservas se recalculan sólo con ventas pendientes y OT aprobadas retenidas.",
                      "| ID | SKU | Lote | Físico antes/objetivo | Reservado antes → simulado | Disponible antes → simulado | Ledger antes | Lotes antes | Ledger tras docs protegidos | Opening requerido | PPP antes | Costo apertura | Clase |",
                      "|---:|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
            for r in inventory_sim:
                lines.append(f"| {r['id']} | {r['sku']} | {'sí' if r['requires_lot'] else 'no'} | {r['physical_before']:.4f} | {r['reserved_before']:.4f} → {r['reserved_after']:.4f} | {r['available_before']:.4f} → {r['available_after']:.4f} | {r['ledger_before']:.4f} | {r['lots_before']:.4f} | {r['ledger_after_kept']:.4f} | {r['opening_qty']:.4f} | {r['ppp_before']:.4f} | {r['opening_cost'] if r['opening_cost'] is not None else '—'} | {r['cost_class']} |")
            lines += ["", f"Opening balances de cantidad requeridos: {len(opening_rows)}; positivos: {sum(1 for x in opening_rows if x[4] > 0)}; negativos (no representables como apertura): {sum(1 for x in opening_rows if x[4] < 0)}. Con costo derivable: {sum(1 for x in opening_rows if str(x[6]).startswith('COSTO_DERIVABLE'))}; con fuente marcada confiable pero apertura aún no resuelta: {sum(1 for x in opening_rows if str(x[6]).startswith('COSTO_CONFIABLE'))}; sin costo defendible: {sum(1 for x in opening_rows if str(x[6]).startswith('COSTO_NO_DETERMINABLE'))}.",
                      "| Producto | SKU | Root que lo introduce/origen del lote | Marcador fixture | Físico | Ledger | Lotes | Opening | PPP | Costo disponible/estado | Diagnóstico |", "|---:|---|---|:---:|---:|---:|---:|---:|---:|---|---|"]
            lines.extend(opening_attribution)
            lines += [
                      "Los costos mostrados son sólo diagnósticos; no se usó `products.cost` como sustituto. La simulación de PPP no es completa porque requiere reproducir por orden cronológico los movimientos retenidos y la apertura al final; el planner marca este punto como bloqueador si no hay una fuente valorizada.", "",
                      "## Ledger vs lotes", "",
                      "| Caso | Productos | Delta absoluto | Clasificación del plan |", "|---|---:|---:|---|",
                      f"| V2 recalculado en snapshot actual | {len(v2_mismatches)} | {sum(v2_mismatches.values()):.4f} | Productos activos `requires_lot`; comparar con informe V2 anterior si cambió el universo. |"]
            for category, cases in ledger_lot_classes.items():
                lines.append(f"| {category} | {len(cases)} | {sum(x[1] for x in cases):.4f} | Provisional, no altera cantidades. |")
            lines += ["| Diferencia protegida | Ver productos de inventario arriba | — | Requiere decisión de origen/apertura antes de redactar SQL. |", "",
                      "## Lotes protegidos y origen documental", "",
                      f"Lotes protegidos en el cierre simulado: {len(kept_lots)}. Cada lote debe tener cantidad/costo y un origen retenido o una referencia polimórfica resuelta antes de autorizar borrado.",
                      "| Lote | Producto | SKU | Disponible | Costo unitario | Documento origen y estado |", "|---:|---:|---|---:|---:|---|"]
            lines.extend(lot_audit_lines or ["| — | — | — | — | — | No hay lotes protegidos |"])
            lines += ["", "## Ventas protegidas y documentos hijos", "",
                      "En cotizaciones se valida el snapshot JSON de líneas (no existe obligación de reserva/movimiento de stock); en ventas se valida línea relacional o snapshot. Los hijos de pago, empaque, lote e historial que existen se verifican en la cobertura del grafo siguiente.",
                      "| Documento | Estado | Items relacionales | Líneas snapshot | Pagos | Historial estado |", "|---:|---|---:|---:|---:|---:|"]
            lines.extend(child_audit_lines or ["| — | — | — | — | No hay ventas/cotizaciones protegidas |"])
            lines += ["", "## Cobertura de hijos por grafo", "",
                      "Comprobación fila a fila: cada hijo existente que referencia a un padre protegido debe pertenecer también al KEEP_SET.",
                      "| Grafo | Hijos omitidos de padres protegidos |", "|---|---:|"]
            for group in child_edges:
                lines.append(f"| {group} | {len(child_gaps[group])} |")
            for group, gaps in child_gaps.items():
                if gaps:
                    lines.append(f"| Muestras {group} | " + ", ".join(f"{t}#{key}->{fk}#{parent}" for t,key,fk,parent in gaps[:20]) + " |")
            lines += ["", "## Referencias polimórficas de movimientos conservados", "",
                      f"Movimientos retenidos con referencia inválida/eliminada o tipo genérico sin política explícita: {len(retained_movement_ref_issues)}.",
                      "| Movimiento | reference_type | reference_id | Diagnóstico |", "|---:|---|---:|---|"]
            lines.extend(f"| {mid} | {rtype or 'NULL'} | {rid if rid is not None else 'NULL'} | {diagnostic} |"
                         for mid, rtype, rid, diagnostic in retained_movement_ref_issues[:300])
            if len(retained_movement_ref_issues) > 300:
                lines.append(f"| … | … | … | más {len(retained_movement_ref_issues)-300} |")
            lines += ["", "### Universo de reference_type", "",
                      "| reference_type | Movimientos actuales | Conservados en simulación |", "|---|---:|---:|"]
            for rtype, values in sorted(movement_ref_type_counts.items(), key=lambda x: (-x[1]["total"], x[0])):
                lines.append(f"| {rtype} | {values['total']} | {values['retained']} |")
            lines += ["", "## Legacy snapshots", "",
                      f"`page_data.inventory_items`: {snapshot_total} items parseados; {snapshot_stale} no coinciden por SKU con el catálogo protegido simulado. La fila completa se conserva en esta simulación; filtrarla requiere una operación JSON específica pendiente.", "",
                      "## PPP y reservas", "",
                      f"- Entradas de costo cero/nulo antes: {len(zeros_total)}.",
                      f"- Movimientos de costo cero/nulo retenidos por referencia documental identificable: {len(zero_survivors)}; el resto sólo es candidato a borrar tras resolver la apertura.",
                      f"- Líneas de reserva ambiguas antes: {len(reservation_ambiguous_before)}; simuladas en ventas/OT retenidas: {len(reservation_ambiguous_after)}. Reservas resueltas por producto: {len(reserved_before)} productos antes, {len(reserved_after)} después.",
                      "- El valor PPP posterior no se declara definitivo: no se simularon completamente lotes valorizados ni reejecución oficial del motor PPP.", "",
                      "## KEEP_SET / DELETE_SET por tabla", "",
                      "El KEEP_SET cuantificado abajo es parcial por diseño. Tablas sin política explícita se mantienen enteras; no se presentan como DELETE_SET final.",
                      "| Tabla | Total | Keep simulado | Delete candidato | Motivo |", "|---|---:|---:|---:|---|"]
            for t,total,k,d,reason in delete_summary:
                lines.append(f"| `{t}` | {total} | {k} | {d} | {reason} |")
            lines += ["", "## Simulación de claves foráneas", "",
                      f"Claves foráneas inspeccionadas: {len(fks)}.",
                      f"Referencias que quedarían huérfanas según KEEP_SET parcial: {len(fk_issues)} (preexistentes: {sum(x[-1]=='preexisting_orphan' for x in fk_issues)}; nuevas: {sum(x[-1]=='would_orphan' for x in fk_issues)}).",
                      "| Hija.columna | Padre.columna | ID hijo | ID padre | Estado |", "|---|---|---:|---:|---|"]
            for issue in fk_issues[:250]:
                lines.append(f"| `{issue[0]}.{issue[1]}` | `{issue[2]}.{issue[3]}` | {issue[4]} | {issue[5]} | {issue[6]} |")
            if len(fk_issues)>250: lines.append(f"| … | … | … | … | más {len(fk_issues)-250} |")
            lines += ["", "Las referencias polimórficas de `inventory_movements.reference_type/reference_id` no tienen FK; requieren conservar origen o reemplazo explícito. Conteos candidatos: " + ", ".join(f"{k}: {v}" for k,v in movement_refs.items()) + ".", "",
                      "## Conteos finales simulados", "",
                      "No se consideran finales hasta cerrar movimientos, apertura/valuación, finanzas y referencias polimórficas.",
                      "| Entidad | Actual | Simulado en cierre actual |", "|---|---:|---:|"]
            entity_tables = [("Productos","products","products"),("Ventas","sales","sales"),("Cotizaciones","sales","quotes"),
                             ("OC","purchase_orders","purchase_orders"),("Recepciones","inventory_entries","inventory_entries"),
                             ("Movimientos","inventory_movements","inventory_movements"),("Lotes","lots","lots"),
                             ("lot_stock","lot_stock","lot_stock"),("OT","production_orders","production_orders"),
                             ("Clientes","clients","clients"),("Proveedores","suppliers","suppliers"),
                             ("Cuentas","bank_accounts","bank_accounts"),("Deudas","debts","debts")]
            for label,t,key in entity_tables:
                if key == "sales":
                    val = len(roots["sales"])
                    actual = current_real_sales_count
                elif key == "quotes":
                    val = len(roots["quotes"])
                    actual = current_quotes_count
                elif t in keep: val = len(keep[t])
                else: val = "sin política de borrado completa"
                if key not in ("sales", "quotes"): actual = counts[t]
                lines.append(f"| {label} | {actual} | {val} |")
            lines += ["", "## Orden de borrado", "",
                      f"Orden topológico candidato hijo→padre calculado sobre el grafo FK completo: {', '.join(delete_order) if delete_order else 'ninguno'}.",
                      f"Tablas bloqueadas por ciclos en el grafo FK: {', '.join(fk_cycles) if fk_cycles else 'ninguna'}.",
                      "No se generó `scripts/cleanup_development_database.sql`: el DELETE_SET no está completo ni la simulación de negocio/valuación está cerrada. Un orden parcial topológico sería engañoso frente a 82 FK, referencias polimórficas y relaciones de inventario con RESTRICT.",
                      "Orden conceptual que deberá concretarse antes de generar el SQL: acciones/auditorías hijas → pagos/items/historiales → movimientos y lotes no protegidos → entradas/facturas/OT/OC/ventas/deudas descartadas → productos/proveedores/cuentas descartados; nunca deshabilitar FK. Los ciclos polimórficos se deben resolver con orden explícito por grafo, no con constraints desactivadas.", "",
                      "## Bloqueadores y semáforo", "",
                      "- CRONOLOGÍA: " + ("GREEN" if not any(v["invalid"] or v["null_or_blank"] for v in chronology.values()) else "RED — valores NULL/no parseables requieren decisión"),
                      f"- ROOT SET: {'GREEN' if len(roots['sales']) >= 30 and len(roots['quotes']) >= 30 and len(roots['purchase_orders']) >= 30 and len(roots['production_orders']) >= 10 else 'RED'} — disponibles ventas {len(roots['sales'])}/30, cotizaciones {len(roots['quotes'])}/30, OC {len(roots['purchase_orders'])}/30, OT {len(roots['production_orders'])}/10 tras criterio de coherencia.",
                      f"- GRAPH CLOSURE: RED — el cierre técnico llega a punto fijo en {len(iteration_log)} iteraciones, pero movimientos/orígenes y grafos hijos aún no están completos.",
                      f"- INVENTARIO: {'GREEN' if not opening_rows else 'RED'} — openings positivos {sum(1 for x in opening_rows if x[4] > 1e-9)}, negativos {sum(1 for x in opening_rows if x[4] < -1e-9)}, sin costo defendible {sum(1 for x in opening_rows if str(x[6]).startswith('COSTO_NO_DETERMINABLE'))}; inventario/PPP no certificados.",
                      f"- LOTES: {'GREEN' if all('ELIMINAR' not in line and 'sin origen explícito' not in line and 'no resuelto' not in line and line.split('|')[5].strip() != '—' for line in lot_audit_lines) else 'RED'} — se requiere origen retenido y costo de lote identificable para los {len(kept_lots)} lotes protegidos.",
                      "- PPP: RED — no se reprodujo el motor oficial completo ni se certificó costo de apertura.",
                      f"- FINANZAS: {'GREEN' if not child_gaps['FINANCE'] and not fk_issues else 'RED'} — hijos financieros de las cuentas/deudas protegidas revisados.",
                      f"- SALES CHILDREN: {'GREEN' if sales_children_ok and not child_gaps['SALES'] else 'RED'} — líneas/snapshot y todos los hijos existentes de las raíces.",
                      f"- PURCHASE CHILDREN: {'GREEN' if not child_gaps['PURCHASE'] and not fk_issues else 'RED'} — items, recepciones, facturas y lotes de padres protegidos.",
                      f"- PRODUCTION CHILDREN: {'GREEN' if not child_gaps['PRODUCTION'] and not child_gaps['RECIPES'] and not fk_issues else 'RED'} — items, consumos, salidas, lotes y recetas requeridas.",
                      "- PAGE_DATA: RED — {0} snapshots no corresponden al catálogo simulado y la mutación JSON segura aún no está definida.".format(snapshot_stale),
                      f"- POLYMORPHIC REFERENCES: {'GREEN' if not retained_movement_ref_issues else 'RED'} — referencias inválidas/genéricas retenidas: {len(retained_movement_ref_issues)}.",
                      f"- FK: {'GREEN' if not fk_issues else 'RED'} — {len(fk_issues)} referencias problemáticas en la simulación parcial.",
                      "- DELETE PLAN: RED — no se generan DELETEs mientras cualquier gate esté RED.", "", "**READY TO EXECUTE: NO**.", "",
                      "No se generó SQL de limpieza, porque el propio criterio de aceptación exige un plan determinístico GREEN. Sí se genera un verificador READ ONLY separado.", ""]
            REPORT.write_text("\n".join(lines), encoding="utf-8")
            write_verify_sql(cur, tables, fks, roots)
            print(f"DATABASE={meta['db']} READ_ONLY={meta['ro']}")
            print(f"ROOTS sales={len(roots['sales'])} quotes={len(roots['quotes'])} PO={len(roots['purchase_orders'])} OT={len(roots['production_orders'])} debts={len(roots['debts'])}")
            print(f"CLOSURE iterations={len(iteration_log)} products={len(products_keep)} lots={len(kept_lots)} POs={len(keep['purchase_orders'])} receipts={len(kept_entries)} OTs={len(keep['production_orders'])}")
            print(f"FK issues={len(fk_issues)} opening={len(opening_rows)} no_cost={sum(x[6]=='COSTO_NO_DETERMINABLE' for x in opening_rows)} zero_cost_inbound={len(zeros_total)} retained={len(zero_survivors)}")
            print(f"WROTE {REPORT} and {VERIFY}")
        conn.rollback()
    finally:
        conn.close()


def write_verify_sql(cur, tables, fks, roots):
    # Static read-only verifier from the exact FK catalog captured by the planner.
    q = lambda s: '"' + s.replace('"', '""') + '"'
    parts = [
        "-- READ ONLY: generated from facturacion schema; does not change data.",
        "BEGIN TRANSACTION READ ONLY;",
        "DO $$ BEGIN IF current_database() <> 'facturacion' THEN RAISE EXCEPTION 'Verifier only allowed on facturacion'; END IF; IF current_setting('transaction_read_only') <> 'on' THEN RAISE EXCEPTION 'Verifier requires READ ONLY transaction'; END IF; END $$;",
        "SELECT current_database() AS database_name, current_setting('transaction_read_only') AS read_only;",
        "SELECT 'products' entity,count(*) FROM products UNION ALL SELECT 'sales',count(*) FROM sales UNION ALL SELECT 'purchase_orders',count(*) FROM purchase_orders UNION ALL SELECT 'inventory_entries',count(*) FROM inventory_entries UNION ALL SELECT 'inventory_movements',count(*) FROM inventory_movements UNION ALL SELECT 'lots',count(*) FROM lots UNION ALL SELECT 'lot_stock',count(*) FROM lot_stock UNION ALL SELECT 'production_orders',count(*) FROM production_orders UNION ALL SELECT 'clients',count(*) FROM clients UNION ALL SELECT 'suppliers',count(*) FROM suppliers UNION ALL SELECT 'bank_accounts',count(*) FROM bank_accounts UNION ALL SELECT 'debts',count(*) FROM debts ORDER BY 1;",
        "SELECT 'real_sales' entity,count(*) FROM sales WHERE status IS DISTINCT FROM 'Cotización' UNION ALL SELECT 'quotes',count(*) FROM sales WHERE status='Cotización';",
        "SELECT 'debt_installments' entity,count(*) FROM debt_installments UNION ALL SELECT 'debt_payments',count(*) FROM debt_payments UNION ALL SELECT 'bank_transactions',count(*) FROM bank_transactions UNION ALL SELECT 'bank_reconciliation_audit',count(*) FROM bank_reconciliation_audit;",
        "SELECT p.id,p.sku,p.requires_lot,CASE WHEN p.requires_lot THEN COALESCE(l.qty,0) ELSE COALESCE(m.qty,0) END AS physical_qty,COALESCE(m.qty,0) AS ledger_qty,COALESCE(l.qty,0) AS lot_qty FROM products p LEFT JOIN (SELECT product_id,SUM(quantity) qty FROM inventory_movements GROUP BY product_id) m ON m.product_id=p.id LEFT JOIN (SELECT product_id,SUM(available_qty) qty FROM lot_stock GROUP BY product_id) l ON l.product_id=p.id WHERE p.is_deleted IS DISTINCT FROM TRUE ORDER BY p.id;",
        "SELECT product_id, SUM(quantity) AS ledger_qty FROM inventory_movements GROUP BY product_id ORDER BY product_id;",
        "SELECT product_id, SUM(available_qty) AS lot_qty FROM lot_stock GROUP BY product_id ORDER BY product_id;",
        "SELECT reference_type,count(*) FROM inventory_movements GROUP BY reference_type ORDER BY count(*) DESC;",
        "SELECT status,count(*) FROM sales GROUP BY status ORDER BY status;",
    ]
    for name, table, ids in (("protected_sales", "sales", roots["sales"]),
                             ("protected_quotes", "sales", roots["quotes"]),
                             ("protected_purchase_orders", "purchase_orders", roots["purchase_orders"]),
                             ("protected_production_orders", "production_orders", roots["production_orders"]),
                             ("protected_debts", "debts", roots["debts"])):
        id_sql = ",".join(str(int(x)) for x in sorted(ids)) or "NULL"
        parts.append(f"SELECT '{name}' entity,count(*) AS found, {len(ids)} AS expected FROM {q(table)} WHERE id IN ({id_sql});")
    fk_selects = []
    for fk in fks:
        fk_selects.append(
            f"SELECT '{fk['child']}.{fk['child_col']} -> {fk['parent']}.{fk['parent_col']}' AS fk, count(*) AS orphan_rows "
            f"FROM {q(fk['child'])} c LEFT JOIN {q(fk['parent'])} p ON c.{q(fk['child_col'])}=p.{q(fk['parent_col'])} "
            f"WHERE c.{q(fk['child_col'])} IS NOT NULL AND p.{q(fk['parent_col'])} IS NULL"
        )
    parts.append("SELECT * FROM (" + " UNION ALL ".join(fk_selects) + ") q WHERE orphan_rows>0 ORDER BY fk;")
    parts += [
        "SELECT product_id, SUM(available_qty) AS lot_stock, (SELECT SUM(m.quantity) FROM inventory_movements m WHERE m.product_id=l.product_id) AS ledger, SUM(available_qty)-(SELECT SUM(m.quantity) FROM inventory_movements m WHERE m.product_id=l.product_id) AS delta FROM lot_stock l GROUP BY product_id HAVING ABS(SUM(available_qty)-(SELECT COALESCE(SUM(m.quantity),0) FROM inventory_movements m WHERE m.product_id=l.product_id))>0.001 ORDER BY ABS(SUM(available_qty)-(SELECT COALESCE(SUM(m.quantity),0) FROM inventory_movements m WHERE m.product_id=l.product_id)) DESC;",
        "SELECT count(*) AS zero_or_null_cost_inbounds FROM inventory_movements WHERE quantity>0 AND (unit_cost IS NULL OR unit_cost=0);",
        "ROLLBACK;",
    ]
    VERIFY.parent.mkdir(parents=True, exist_ok=True)
    VERIFY.write_text("\n\n".join(parts) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
