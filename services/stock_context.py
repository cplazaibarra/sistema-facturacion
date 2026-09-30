"""Canonical, read-only inventory balance semantics.

Physical stock is sourced from lot_stock for lot-controlled products and from
the inventory movement ledger otherwise. Reservations are commitments, not
physical stock: available = max(physical - reserved, 0).
"""
import re
import logging

from core.database import get_connection


def calculate_stock_balance(physical, reserved=0):
    """Pure domain calculation used by operational reads and tests."""
    physical = float(physical or 0)
    # Reserved is the full committed demand, including backorders. It may exceed
    # physical stock so purchasing can see what must be replenished. Availability
    # never promises negative stock to a new operation.
    reserved = max(0.0, float(reserved or 0))
    physical_reserved = min(reserved, max(physical, 0.0))
    return {
        "physical_stock": physical,
        "reserved_stock": reserved,
        "physical_reserved_stock": physical_reserved,
        "available_stock": max(physical - reserved, 0.0),
    }


def _resolve_product(line, products_by_id, products_by_sku, products_by_name, diagnostics):
    if not isinstance(line, dict):
        return None
    pid = line.get("product_id") or line.get("id")
    if pid is not None:
        try:
            product = products_by_id.get(int(pid))
        except (TypeError, ValueError):
            product = None
        if product:
            return product, "product_id"

    sku = (line.get("sku") or line.get("product_sku") or "").strip().lower()
    if sku and sku in products_by_sku:
        return products_by_sku[sku], "sku_exact"

    name = (line.get("product_name") or line.get("name") or "").strip().lower()
    if not name:
        return None
    if name in products_by_name:
        exact = products_by_name[name]
        if len(exact) == 1:
            return exact[0], "name_exact"
        diagnostics.append({
            "code": "RESERVA_AMBIGUA",
            "document_id": line.get("sale_id"),
            "product_name": name,
            "candidate_product_ids": sorted(p["id"] for p in exact),
        })
        return None

    candidates = [p for product_name, rows in products_by_name.items()
                  if product_name and (product_name in name or name in product_name)
                  for p in rows]
    if len(candidates) == 1:
        return candidates[0], "name_partial_legacy"
    if len(candidates) > 1:
        diagnostics.append({
            "code": "RESERVA_AMBIGUA",
            "document_id": line.get("sale_id"),
            "product_name": name,
            "candidate_product_ids": sorted({p["id"] for p in candidates}),
        })
    return None


def get_reserved_stock_by_sku(products_db, pending_sales, diagnostics=None):
    """Resolve sale reservations by stable identity first; flag ambiguous legacy names.

    The optional diagnostics list is appended to in-place. Existing callers keep
    receiving the legacy SKU -> quantity mapping.
    """
    diagnostics = diagnostics if diagnostics is not None else []
    diagnostics_start = len(diagnostics)
    products_by_id = {}
    products_by_sku = {}
    products_by_name = {}
    for product in products_db:
        products_by_id[int(product["id"])] = product
        if product.get("sku"):
            products_by_sku[str(product["sku"]).strip().lower()] = product
        name = (product.get("name") or "").strip().lower()
        if name:
            products_by_name.setdefault(name, []).append(product)

    reserved = {}
    match_counts = {"product_id": 0, "sku_exact": 0, "name_exact": 0, "name_partial_legacy": 0, "unmatched": 0}
    pending_sale_ids = sorted({
        int(sale["id"])
        for sale in pending_sales
        if isinstance(sale, dict) and sale.get("id") is not None
    })
    discounted_sale_ids = set()
    # Keep the domain's existing production commitment policy: approved OT inputs.
    with get_connection() as conn:
        with conn.cursor() as cur:
            # A pending sale may already have consumed its stock (e.g. quotation
            # conversion). Such units are absent from physical stock and must not
            # also reduce availability as a reservation. Use one batch lookup to
            # avoid counting the same demand twice.
            if pending_sale_ids:
                cur.execute(
                    "SELECT DISTINCT sale_id FROM sale_items WHERE sale_id = ANY(%s)",
                    (pending_sale_ids,),
                )
                discounted_sale_ids.update(int(row["sale_id"]) for row in cur.fetchall())

            for sale in pending_sales:
                try:
                    if int(sale.get("id")) in discounted_sale_ids:
                        continue
                except (TypeError, ValueError, AttributeError):
                    pass
                for line in sale.get("products", []) or []:
                    quantity, normalized = 0, line
                    if isinstance(line, str):
                        match = re.match(r"^(.*?)\s*\((\d+(?:\.\d+)?)\)$", line.strip())
                        if match:
                            normalized = {"product_name": match.group(1), "quantity": match.group(2), "sale_id": sale.get("id")}
                    if isinstance(normalized, dict):
                        quantity = normalized.get("quantity", 0) or 0
                        normalized = dict(normalized)
                        normalized.setdefault("sale_id", sale.get("id"))
                    try:
                        quantity = float(quantity)
                    except (TypeError, ValueError):
                        quantity = 0
                    if quantity <= 0:
                        continue
                    resolved = _resolve_product(normalized, products_by_id, products_by_sku, products_by_name, diagnostics)
                    if not resolved:
                        match_counts["unmatched"] += 1
                        diagnostics.append({"code": "RESERVA_SIN_PRODUCTO", "document_id": sale.get("id"), "line": normalized})
                        continue
                    product, method = resolved
                    match_counts[method] += 1
                    sku = product.get("sku")
                    reserved[sku] = reserved.get(sku, 0.0) + quantity

            cur.execute("""
                SELECT p.sku, SUM(x.quantity) AS quantity
                FROM (
                    SELECT poi.input_product_id AS product_id, poi.quantity_required AS quantity
                    FROM production_order_items poi JOIN production_orders po ON po.id=poi.production_order_id
                    WHERE po.status='Aprobada'
                    UNION ALL
                    SELECT poai.input_product_id, poai.quantity
                    FROM production_order_additional_items poai JOIN production_orders po ON po.id=poai.production_order_id
                    WHERE po.status='Aprobada'
                ) x JOIN products p ON p.id=x.product_id
                GROUP BY p.sku
            """)
            for row in cur.fetchall():
                sku = row["sku"]
                reserved[sku] = reserved.get(sku, 0.0) + float(row["quantity"] or 0)

            # Keep full outstanding demand, even when there is not enough stock
            # on hand. Physical allocation happens when an operator executes a
            # chosen document; pending demand is not an exclusive allocation.
    ambiguous_count = sum(row.get("code") == "RESERVA_AMBIGUA" for row in diagnostics[diagnostics_start:])
    if ambiguous_count:
        logging.getLogger(__name__).warning(
            "RESERVA_AMBIGUA: %s líneas legacy no se asignaron a un producto", ambiguous_count
        )
    diagnostics.append({"code": "RESERVA_RESOLUCION_RESUMEN", "matches": match_counts,
                        "ambiguous_lines": ambiguous_count})
    return reserved


def get_operational_balance(sku):
    """Return canonical physical/reserved/available values for a SKU."""
    from repositories.inventory_repo import get_product_physical_stock
    from repositories.products_repo import get_product_by_sku
    from repositories.sales_repo import list_sales

    product = get_product_by_sku(sku)
    if product is None:
        return None
    reserved = get_reserved_stock_by_sku([product], list_sales({"status": "Pendiente"})).get(sku, 0)
    balance = calculate_stock_balance(get_product_physical_stock(product["id"]), reserved)
    # Legacy key aliases used by existing inventory diagnostics.
    balance.update({"physical": balance["physical_stock"], "reserved": balance["reserved_stock"],
                    "available": balance["available_stock"]})
    return balance


def get_product_stock_balance(product_id, lot_number=None, diagnostics=None):
    """Canonical balance for one product; reservations remain separate from on-hand."""
    from repositories.inventory_repo import get_product_physical_stock
    from repositories.products_repo import get_product
    from repositories.sales_repo import list_sales

    product = get_product(product_id)
    if not product:
        return None
    reservation_diagnostics = diagnostics if diagnostics is not None else []
    reserved = get_reserved_stock_by_sku(
        [product], list_sales({"status": "Pendiente"}), reservation_diagnostics
    ).get(product.get("sku"), 0)
    return calculate_stock_balance(
        get_product_physical_stock(product_id, lot_number), reserved
    )
