"""
repositories/cash_flow_repo.py
Motor central de consolidación financiera para FLUJO DE CAJA del ERP.

Consolida fuentes oficiales:
1. Saldos Bancarios: `bank_accounts`, `bank_transactions` (saldo inicial acumulado y saldo actual por cuenta).
2. Ingresos Reales: `sale_payment_items` (cobranzas aprobadas) + `bank_transactions` tipo ABONO no conciliadas (y no transferencias internas).
3. Ingresos Proyectados: `sales` no canceladas con saldo pendiente > 0 en fecha esperada/vencimiento.
4. Egresos Reales: `purchase_invoices` (pagadas) + `operational_expense_occurrences` (pagadas) + `debt_payments` (pagadas) + `bank_transactions` tipo CARGO no conciliadas (y no transferencias internas).
5. Egresos Proyectados: `purchase_invoices` (pendientes) + `operational_expense_occurrences` (proyectadas/pendientes) + `debt_installments` (pendientes balance > 0).
6. Transferencias Internas: Por cuenta individual afectan cada banco (+/-), pero en el Consolidado su efecto neto es estrictamente $0.
7. Anti-duplicación estricta: Una obligación con pago parcial proyecta solo el saldo pendiente. Si se paga completa, la proyección se extingue.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from core.database import get_connection


# The detail grid is deliberately bounded while the consolidation itself keeps
# the complete filtered universe for KPIs, projections and exports.
PAGE_SIZE = 30


def paginate_movements(movements: List[Dict[str, Any]], page: int = 1, page_size: int = PAGE_SIZE) -> Dict[str, Any]:
    """Return one bounded detail page and its navigation metadata.

    This helper clamps invalid/out-of-range pages so a stale bookmark or a
    filter change never produces an error page.  ``movements`` remains the
    complete filtered dataset used by financial calculations and exports;
    only ``items`` is sent to the detail table.
    """
    try:
        requested_page = int(page)
    except (TypeError, ValueError):
        requested_page = 1
    requested_page = max(1, requested_page)
    page_size = max(1, int(page_size))
    total = len(movements)
    total_pages = max(1, (total + page_size - 1) // page_size)
    current_page = min(requested_page, total_pages)
    start = (current_page - 1) * page_size
    items = movements[start:start + page_size]
    return {
        "items": items,
        "page": current_page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
        "start": start + 1 if items else 0,
        "end": start + len(items),
    }


def _to_decimal(val: Any) -> Decimal:
    if val is None:
        return Decimal("0.00")
    try:
        return Decimal(str(val)).quantize(Decimal("0.01"))
    except Exception:
        return Decimal("0.00")


def _format_date(val: Any) -> Optional[str]:
    if not val:
        return None
    if isinstance(val, (date, datetime)):
        return val.strftime("%Y-%m-%d")
    s = str(val).strip()
    return s[:10] if len(s) >= 10 else s


def get_bank_initial_balances(as_of_date: str, bank_account_id: Optional[int] = None) -> Dict[int, Decimal]:
    """
    Calcula el saldo acumulado en cartolas bancarias estrictamente antes de `as_of_date`.
    Retorna un diccionario {bank_account_id: saldo_acumulado_decimal}.
    """
    balances: Dict[int, Decimal] = {}
    where_clauses = ["transaction_date < %s"]
    params: List[Any] = [as_of_date]

    if bank_account_id:
        where_clauses.append("bank_account_id = %s")
        params.append(bank_account_id)

    with get_connection() as conn:
        with conn.cursor() as cur:
            acc_query = "SELECT id FROM bank_accounts WHERE status = 'Activa'"
            if bank_account_id:
                acc_query += f" AND id = {bank_account_id}"
            cur.execute(acc_query)
            for r in cur.fetchall():
                balances[r["id"]] = Decimal("0.00")

            query = f"""
                SELECT bank_account_id, COALESCE(SUM(amount), 0) AS net_sum
                FROM bank_transactions
                WHERE {' AND '.join(where_clauses)}
                GROUP BY bank_account_id
            """
            cur.execute(query, params)
            for r in cur.fetchall():
                balances[r["bank_account_id"]] = _to_decimal(r["net_sum"])

    return balances


def calculate_cash_flow_consolidation(
    start_date: str,
    end_date: str,
    bank_account_id: Optional[int] = None,
    grouping: str = "semanal",  # 'diario', 'semanal', 'mensual'
    filter_type: str = "todos",  # 'todos', 'real', 'proyectado'
    filter_origin: str = "todos",  # 'todos', 'cxc', 'cxp', 'gasto', 'deuda', 'banco', 'transferencia'
    filter_reconciliation: str = "todos",  # 'todos', 'conciliado', 'pendiente'
    page: int = 1,
    page_size: int = PAGE_SIZE,
) -> Dict[str, Any]:
    """
    Genera el flujo de caja consolidado, los KPIs y el detalle de movimientos.
    """
    clean_grouping = grouping.lower() if grouping in ("diario", "semanal", "mensual") else "semanal"
    start_d = date.fromisoformat(start_date)
    end_d = date.fromisoformat(end_date)
    today_d = date.today()
    persisted_expense_dates = set()

    # 1. Saldo Inicial
    account_initials = get_bank_initial_balances(start_date, bank_account_id)
    if bank_account_id:
        initial_balance = account_initials.get(bank_account_id, Decimal("0.00"))
    else:
        initial_balance = sum(account_initials.values(), Decimal("0.00"))

    # 2. Recolección de Movimientos
    movements: List[Dict[str, Any]] = []

    with get_connection() as conn:
        with conn.cursor() as cur:
            # ─────────────────────────────────────────────────────────────
            # A. REAL: Cobranzas de Ventas (sale_payment_items)
            # ─────────────────────────────────────────────────────────────
            cur.execute(
                """
                SELECT 
                    spi.id,
                    spi.sale_id,
                    spi.payment_amount,
                    spi.payment_date,
                    spi.bank_account_id,
                    s.sale_number,
                    s.customer_name,
                    ba.bank_name,
                    ba.account_number,
                    bt.id AS bt_id,
                    bt.reconciliation_status
                FROM sale_payment_items spi
                JOIN sales s ON spi.sale_id = s.id
                LEFT JOIN bank_accounts ba ON spi.bank_account_id = ba.id
                LEFT JOIN bank_transactions bt ON (bt.reconciled_type = 'SALE_PAYMENT' AND bt.reconciled_id = spi.id AND bt.reconciliation_status = 'CONCILIADO')
                WHERE spi.payment_date IS NOT NULL
                  AND spi.payment_date != ''
                  AND COALESCE(spi.accounting_approved, 1) = 1
                """
            )
            for r in cur.fetchall():
                p_date = _format_date(r["payment_date"])
                if not p_date:
                    continue
                acc_id = r["bank_account_id"]
                if bank_account_id and acc_id != bank_account_id:
                    continue
                amt = _to_decimal(r["payment_amount"])
                is_conc = (r["reconciliation_status"] == "CONCILIADO")

                movements.append({
                    "date": p_date,
                    "flow_nature": "REAL",
                    "origin": "Pago Venta",
                    "origin_code": "cxc",
                    "doc_number": r["sale_number"] or f"VTA-{r['sale_id']}",
                    "entity_name": r["customer_name"] or "Cliente",
                    "bank_account_id": acc_id,
                    "bank_label": f"{r['bank_name']} ({r['account_number']})" if r["bank_name"] else "Sin cuenta",
                    "description": f"Cobro Venta {r['sale_number']}",
                    "inflow": amt,
                    "outflow": Decimal("0.00"),
                    "net_amount": amt,
                    "status": "Cobrado",
                    "reconciliation_status": "CONCILIADO" if is_conc else "PENDIENTE",
                    "source_id": r["id"],
                    "link_url": f"/ventas/{r['sale_id']}",
                    "is_internal_transfer": False,
                })

            # ─────────────────────────────────────────────────────────────
            # B. PROYECTADO: Cuentas por Cobrar (sales con saldo pendiente > 0)
            # ─────────────────────────────────────────────────────────────
            cur.execute(
                """
                SELECT 
                    s.id,
                    s.sale_number,
                    s.customer_name,
                    s.sale_date,
                    s.total_amount,
                    s.payment_status,
                    sp.invoice_due_date,
                    sp.payment_amount AS header_paid,
                    COALESCE(spi_agg.total_paid, 0.0) AS items_paid
                FROM sales s
                LEFT JOIN sale_payments sp ON sp.sale_id = s.id
                LEFT JOIN (
                    SELECT sale_id, SUM(payment_amount) AS total_paid
                    FROM sale_payment_items
                    WHERE COALESCE(accounting_approved, 1) = 1
                    GROUP BY sale_id
                ) spi_agg ON spi_agg.sale_id = s.id
                WHERE s.status NOT IN ('Cancelada', 'Cancelado', 'Cotización')
                  AND s.sale_number NOT LIKE 'COT-%%'
                  AND s.payment_status NOT IN ('Pagado', 'Pagada')
                """
            )
            for r in cur.fetchall():
                total = _to_decimal(r["total_amount"])
                paid = _to_decimal(r["items_paid"] if r["items_paid"] > 0 else (r["header_paid"] or 0))
                balance = max(Decimal("0.00"), total - paid)
                if balance <= Decimal("0.00"):
                    continue

                due_str = _format_date(r["invoice_due_date"]) or _format_date(r["sale_date"]) or today_d.isoformat()
                is_overdue = due_str < today_d.isoformat()
                movements.append({
                    "date": due_str,
                    "flow_nature": "PROYECTADO",
                    "origin": "Cuenta por Cobrar",
                    "origin_code": "cxc",
                    "doc_number": r["sale_number"] or f"VTA-{r['id']}",
                    "entity_name": r["customer_name"] or "Cliente",
                    "bank_account_id": None,
                    "bank_label": "Por Definir",
                    "description": f"Saldo por Cobrar {r['sale_number']} (Total ${total:,.0f} - Pagado ${paid:,.0f})",
                    "inflow": balance,
                    "outflow": Decimal("0.00"),
                    "net_amount": balance,
                    "status": "Vencida" if is_overdue else ("Parcial" if paid > 0 else "Pendiente"),
                    "reconciliation_status": "NO_APLICA",
                    "source_id": r["id"],
                    "link_url": f"/ventas/{r['id']}",
                    "is_internal_transfer": False,
                })

            # ─────────────────────────────────────────────────────────────
            # C. REAL: Pagos Facturas Proveedores (purchase_invoices pagadas)
            # ─────────────────────────────────────────────────────────────
            cur.execute(
                """
                SELECT 
                    pi.id,
                    pi.invoice_number,
                    pi.invoice_amount,
                    pi.payment_amount,
                    pi.payment_date,
                    pi.bank_account_id,
                    sup.name AS supplier_name,
                    ba.bank_name,
                    ba.account_number,
                    bt.id AS bt_id,
                    bt.reconciliation_status
                FROM purchase_invoices pi
                LEFT JOIN suppliers sup ON pi.supplier_id = sup.id
                LEFT JOIN bank_accounts ba ON pi.bank_account_id = ba.id
                LEFT JOIN bank_transactions bt ON (bt.reconciled_type = 'PURCHASE_PAYMENT' AND bt.reconciled_id = pi.id AND bt.reconciliation_status = 'CONCILIADO')
                WHERE pi.payment_date IS NOT NULL
                  AND pi.payment_date != ''
                  AND pi.payment_status IN ('Pagada', 'Pagado')
                """
            )
            for r in cur.fetchall():
                p_date = _format_date(r["payment_date"])
                if not p_date:
                    continue
                acc_id = r["bank_account_id"]
                if bank_account_id and acc_id != bank_account_id:
                    continue
                amt = _to_decimal(r["payment_amount"] if r["payment_amount"] is not None else r["invoice_amount"])
                is_conc = (r["reconciliation_status"] == "CONCILIADO")

                movements.append({
                    "date": p_date,
                    "flow_nature": "REAL",
                    "origin": "Pago Proveedor",
                    "origin_code": "cxp",
                    "doc_number": r["invoice_number"] or f"FAC-{r['id']}",
                    "entity_name": r["supplier_name"] or "Proveedor",
                    "bank_account_id": acc_id,
                    "bank_label": f"{r['bank_name']} ({r['account_number']})" if r["bank_name"] else "Sin cuenta",
                    "description": f"Pago Factura {r['invoice_number']}",
                    "inflow": Decimal("0.00"),
                    "outflow": amt,
                    "net_amount": -amt,
                    "status": "Pagada",
                    "reconciliation_status": "CONCILIADO" if is_conc else "PENDIENTE",
                    "source_id": r["id"],
                    "link_url": f"/compras/facturas/{r['id']}",
                    "is_internal_transfer": False,
                })

            # ─────────────────────────────────────────────────────────────
            # D. PROYECTADO: Facturas Proveedores Pendientes
            # ─────────────────────────────────────────────────────────────
            cur.execute(
                """
                SELECT 
                    pi.id,
                    pi.invoice_number,
                    pi.invoice_amount,
                    pi.payment_amount,
                    pi.invoice_date,
                    pi.due_date,
                    pi.bank_account_id,
                    pi.payment_status,
                    sup.name AS supplier_name,
                    ba.bank_name,
                    ba.account_number
                FROM purchase_invoices pi
                LEFT JOIN suppliers sup ON pi.supplier_id = sup.id
                LEFT JOIN bank_accounts ba ON pi.bank_account_id = ba.id
                WHERE pi.payment_status IN ('Pendiente', 'Vencida')
                   OR (pi.payment_status NOT IN ('Pagada', 'Pagado', 'Anulada') AND pi.payment_date IS NULL)
                """
            )
            for r in cur.fetchall():
                tot = _to_decimal(r["invoice_amount"])
                paid = _to_decimal(r["payment_amount"] or 0)
                bal = max(Decimal("0.00"), tot - paid)
                if bal <= Decimal("0.00"):
                    continue

                acc_id = r["bank_account_id"]
                if bank_account_id and acc_id and acc_id != bank_account_id:
                    continue

                due_str = _format_date(r["due_date"]) or _format_date(r["invoice_date"]) or today_d.isoformat()
                is_overdue = due_str < today_d.isoformat()

                movements.append({
                    "date": due_str,
                    "flow_nature": "PROYECTADO",
                    "origin": "Factura Compra",
                    "origin_code": "cxp",
                    "doc_number": r["invoice_number"] or f"FAC-{r['id']}",
                    "entity_name": r["supplier_name"] or "Proveedor",
                    "bank_account_id": acc_id,
                    "bank_label": f"{r['bank_name']} ({r['account_number']})" if r["bank_name"] else "Por Definir",
                    "description": f"Factura Pendiente {r['invoice_number']} (Saldo ${bal:,.0f})",
                    "inflow": Decimal("0.00"),
                    "outflow": bal,
                    "net_amount": -bal,
                    "status": "Vencida" if is_overdue else "Pendiente",
                    "reconciliation_status": "NO_APLICA",
                    "source_id": r["id"],
                    "link_url": f"/compras/facturas/{r['id']}",
                    "is_internal_transfer": False,
                })

            # ─────────────────────────────────────────────────────────────
            # E. REAL: Pagos Gastos Operacionales (operational_expense_occurrences pagadas)
            # ─────────────────────────────────────────────────────────────
            cur.execute(
                """
                SELECT 
                    oeo.id,
                    oeo.due_date,
                    oeo.paid_date,
                    oeo.amount,
                    oeo.payment_amount,
                    oeo.bank_account_id,
                    oe.name AS expense_name,
                    oe.beneficiary,
                    ba.bank_name,
                    ba.account_number,
                    bt.id AS bt_id,
                    bt.reconciliation_status
                FROM operational_expense_occurrences oeo
                JOIN operational_expenses oe ON oeo.expense_id = oe.id
                LEFT JOIN bank_accounts ba ON oeo.bank_account_id = ba.id
                LEFT JOIN bank_transactions bt ON (bt.reconciled_type = 'EXPENSE' AND bt.reconciled_id = oeo.id AND bt.reconciliation_status = 'CONCILIADO')
                WHERE oeo.status = 'Pagado'
                  AND oeo.paid_date IS NOT NULL
                """
            )
            for r in cur.fetchall():
                p_date = _format_date(r["paid_date"])
                if not p_date:
                    continue
                acc_id = r["bank_account_id"]
                if bank_account_id and acc_id != bank_account_id:
                    continue
                amt = _to_decimal(r["payment_amount"] if r["payment_amount"] is not None else r["amount"])
                is_conc = (r["reconciliation_status"] == "CONCILIADO")

                movements.append({
                    "date": p_date,
                    "flow_nature": "REAL",
                    "origin": "Pago Gasto Operacional",
                    "origin_code": "gasto",
                    "doc_number": f"GASTO-{r['id']}",
                    "entity_name": r["beneficiary"] or "Beneficiario",
                    "bank_account_id": acc_id,
                    "bank_label": f"{r['bank_name']} ({r['account_number']})" if r["bank_name"] else "Sin cuenta",
                    "description": f"Gasto: {r['expense_name']}",
                    "inflow": Decimal("0.00"),
                    "outflow": amt,
                    "net_amount": -amt,
                    "status": "Pagado",
                    "reconciliation_status": "CONCILIADO" if is_conc else "PENDIENTE",
                    "source_id": r["id"],
                    "link_url": "/reporteria/gastos",
                    "is_internal_transfer": False,
                })

            # ─────────────────────────────────────────────────────────────
            # F. PROYECTADO: Gastos Operacionales Pendientes/Proyectados
            # ─────────────────────────────────────────────────────────────
            cur.execute(
                """
                SELECT 
                    oeo.id,
                    oeo.due_date,
                    oeo.amount,
                    oeo.bank_account_id,
                    oe.name AS expense_name,
                    oe.beneficiary,
                    ba.bank_name,
                    ba.account_number
                FROM operational_expense_occurrences oeo
                JOIN operational_expenses oe ON oeo.expense_id = oe.id
                LEFT JOIN bank_accounts ba ON oeo.bank_account_id = ba.id
                WHERE oeo.status IN ('Proyectado', 'Pendiente')
                """
            )
            for r in cur.fetchall():
                due_str = _format_date(r["due_date"])
                if not due_str:
                    continue
                acc_id = r["bank_account_id"]
                if bank_account_id and acc_id and acc_id != bank_account_id:
                    continue
                amt = _to_decimal(r["amount"])
                is_overdue = due_str < today_d.isoformat()

                movements.append({
                    "date": due_str,
                    "flow_nature": "PROYECTADO",
                    "origin": "Gasto Operacional",
                    "origin_code": "gasto",
                    "doc_number": f"GASTO-{r['id']}",
                    "entity_name": r["beneficiary"] or "Beneficiario",
                    "bank_account_id": acc_id,
                    "bank_label": f"{r['bank_name']} ({r['account_number']})" if r["bank_name"] else "Por Definir",
                    "description": f"Gasto Proyectado: {r['expense_name']}",
                    "inflow": Decimal("0.00"),
                    "outflow": amt,
                    "net_amount": -amt,
                    "status": "Vencida" if is_overdue else "Proyectado",
                    "reconciliation_status": "NO_APLICA",
                    "source_id": r["id"],
                    "link_url": "/reporteria/gastos",
                    "is_internal_transfer": False,
                })

            # Active recurring expense masters are forecasts, not persisted
            # obligations. Add their future due dates to cash flow without
            # materializing rows or duplicating an occurrence already recorded
            # for that expense/date.
            cur.execute(
                """SELECT expense_id, due_date
                   FROM operational_expense_occurrences
                   WHERE due_date BETWEEN %s AND %s""",
                (max(start_d, today_d), end_d),
            )
            persisted_expense_dates = {
                (int(r["expense_id"]), _format_date(r["due_date"]))
                for r in cur.fetchall()
            }

            # ─────────────────────────────────────────────────────────────
            # G. REAL: Pagos Deudas Financieras (debt_payments)
            # ─────────────────────────────────────────────────────────────
            cur.execute(
                """
                SELECT 
                    dp.id,
                    dp.payment_date,
                    dp.payment_amount,
                    dp.bank_account_id,
                    d.id AS debt_id,
                    d.name AS debt_name,
                    d.creditor_name,
                    di.installment_number,
                    ba.bank_name,
                    ba.account_number,
                    bt.id AS bt_id,
                    bt.reconciliation_status
                FROM debt_payments dp
                JOIN debt_installments di ON dp.debt_installment_id = di.id
                JOIN debts d ON di.debt_id = d.id
                LEFT JOIN bank_accounts ba ON dp.bank_account_id = ba.id
                LEFT JOIN bank_transactions bt ON (bt.reconciled_type = 'DEBT_PAYMENT' AND bt.reconciled_id = dp.id AND bt.reconciliation_status = 'CONCILIADO')
                WHERE dp.payment_date IS NOT NULL
                  AND dp.payment_amount > 0
                """
            )
            for r in cur.fetchall():
                p_date = _format_date(r["payment_date"])
                if not p_date:
                    continue
                acc_id = r["bank_account_id"]
                if bank_account_id and acc_id != bank_account_id:
                    continue
                amt = _to_decimal(r["payment_amount"])
                is_conc = (r["reconciliation_status"] == "CONCILIADO")

                movements.append({
                    "date": p_date,
                    "flow_nature": "REAL",
                    "origin": "Pago Deuda",
                    "origin_code": "deuda",
                    "doc_number": f"CUOTA-{r['debt_id']}/{r['installment_number']}",
                    "entity_name": r["creditor_name"] or "Acreedor",
                    "bank_account_id": acc_id,
                    "bank_label": f"{r['bank_name']} ({r['account_number']})" if r["bank_name"] else "Sin cuenta",
                    "description": f"Pago Cuota {r['installment_number']} - {r['debt_name']}",
                    "inflow": Decimal("0.00"),
                    "outflow": amt,
                    "net_amount": -amt,
                    "status": "Pagada",
                    "reconciliation_status": "CONCILIADO" if is_conc else "PENDIENTE",
                    "source_id": r["id"],
                    "link_url": f"/reporteria/deudas/{r['debt_id']}",
                    "is_internal_transfer": False,
                })

            # ─────────────────────────────────────────────────────────────
            # H. PROYECTADO: Cuotas Deudas Pendientes (debt_installments con balance > 0)
            # ─────────────────────────────────────────────────────────────
            cur.execute(
                """
                SELECT 
                    di.id,
                    di.installment_number,
                    di.due_date,
                    di.balance,
                    d.id AS debt_id,
                    d.name AS debt_name,
                    d.creditor_name,
                    d.bank_account_id,
                    ba.bank_name,
                    ba.account_number
                FROM debt_installments di
                JOIN debts d ON di.debt_id = d.id
                LEFT JOIN bank_accounts ba ON d.bank_account_id = ba.id
                WHERE di.status IN ('PENDIENTE', 'PAGO_PARCIAL', 'VENCIDA')
                  AND di.balance > 0
                """
            )
            for r in cur.fetchall():
                due_str = _format_date(r["due_date"])
                if not due_str:
                    continue
                acc_id = r["bank_account_id"]
                if bank_account_id and acc_id and acc_id != bank_account_id:
                    continue
                bal = _to_decimal(r["balance"])
                is_overdue = due_str < today_d.isoformat()

                movements.append({
                    "date": due_str,
                    "flow_nature": "PROYECTADO",
                    "origin": "Cuota Deuda",
                    "origin_code": "deuda",
                    "doc_number": f"CUOTA-{r['debt_id']}/{r['installment_number']}",
                    "entity_name": r["creditor_name"] or "Acreedor",
                    "bank_account_id": acc_id,
                    "bank_label": f"{r['bank_name']} ({r['account_number']})" if r["bank_name"] else "Por Definir",
                    "description": f"Cuota {r['installment_number']} Proyectada - {r['debt_name']}",
                    "inflow": Decimal("0.00"),
                    "outflow": bal,
                    "net_amount": -bal,
                    "status": "Vencida" if is_overdue else "Pendiente",
                    "reconciliation_status": "NO_APLICA",
                    "source_id": r["id"],
                    "link_url": f"/reporteria/deudas/{r['debt_id']}",
                    "is_internal_transfer": False,
                })

            # ─────────────────────────────────────────────────────────────
            # I. MOVIMIENTOS BANCARIOS REALES SIN OPERACIÓN ERP / TRANSFERENCIAS INTERNAS
            # ─────────────────────────────────────────────────────────────
            cur.execute(
                """
                SELECT 
                    bt.id,
                    bt.bank_account_id,
                    bt.transaction_date,
                    bt.movement_type,
                    bt.amount,
                    bt.charge,
                    bt.credit,
                    bt.description,
                    bt.doc_number,
                    bt.reconciliation_status,
                    bt.reconciled_type,
                    bt.reconciled_id,
                    ba.bank_name,
                    ba.account_number
                FROM bank_transactions bt
                JOIN bank_accounts ba ON bt.bank_account_id = ba.id
                WHERE (
                    bt.reconciliation_status = 'PENDIENTE'
                    OR bt.reconciled_type = 'INTERNAL_TRANSFER'
                )
                """
            )
            for r in cur.fetchall():
                t_date = _format_date(r["transaction_date"])
                if not t_date:
                    continue
                acc_id = r["bank_account_id"]
                if bank_account_id and acc_id != bank_account_id:
                    continue

                m_type = r["movement_type"]
                amt = _to_decimal(abs(r["amount"]))
                is_internal = (r["reconciled_type"] == "INTERNAL_TRANSFER")
                
                inflow = amt if m_type == "ABONO" else Decimal("0.00")
                outflow = amt if m_type == "CARGO" else Decimal("0.00")
                net = inflow - outflow

                origin_label = "Transferencia Interna" if is_internal else "Movimiento Bancario"
                origin_code = "transferencia" if is_internal else "banco"

                movements.append({
                    "date": t_date,
                    "flow_nature": "REAL",
                    "origin": origin_label,
                    "origin_code": origin_code,
                    "doc_number": r["doc_number"] or f"BCO-{r['id']}",
                    "entity_name": "Movimiento Bancario",
                    "bank_account_id": acc_id,
                    "bank_label": f"{r['bank_name']} ({r['account_number']})",
                    "description": r["description"] or "Sin descripción bancaria",
                    "inflow": inflow,
                    "outflow": outflow,
                    "net_amount": net,
                    "status": "Movimiento Real",
                    "reconciliation_status": r["reconciliation_status"],
                    "source_id": r["id"],
                    "link_url": f"/reporteria/conciliacion-bancaria?bank_account_id={acc_id}&search={r['id']}",
                    "is_internal_transfer": is_internal,
                })

    # Recurring master expenses are forecast-only. The pro-rata date
    # generator is shared with the operational expense projections used by
    # the other reporting views; no payment/occurrence is created here.
    if end_d >= today_d:
        from repositories.operational_expenses_repo import project_operational_expenses

        projection_start = max(start_d, today_d)
        for occurrence in project_operational_expenses(projection_start, end_d):
            due_date = occurrence["due_date"].isoformat()
            expense_id = int(occurrence["expense_id"])
            if (expense_id, due_date) in persisted_expense_dates:
                continue
            acc_id = occurrence.get("bank_account_id")
            if bank_account_id and acc_id != bank_account_id:
                continue
            amount = _to_decimal(occurrence["amount"])
            movements.append({
                "date": due_date,
                "flow_nature": "PROYECTADO",
                "origin": "Gasto Operacional",
                "origin_code": "gasto",
                "doc_number": f"GOP-{expense_id}-{due_date}",
                "entity_name": occurrence.get("beneficiary") or occurrence["name"],
                "bank_account_id": acc_id,
                "bank_label": (
                    f"{occurrence['bank_name']} ({occurrence['account_number']})"
                    if occurrence.get("bank_name") else "Por Definir"
                ),
                "description": f"Gasto recurrente proyectado: {occurrence['name']}",
                "inflow": Decimal("0.00"),
                "outflow": amount,
                "net_amount": -amount,
                "status": "Proyectado",
                "reconciliation_status": "NO_APLICA",
                "source_id": f"expense-{expense_id}-{due_date}",
                "link_url": "/administracion/gastos-operacionales",
                "is_internal_transfer": False,
            })

    # 3. Aplicar Filtros de Usuario
    filtered_movements: List[Dict[str, Any]] = []
    for m in movements:
        if not (start_date <= m["date"] <= end_date):
            continue

        if bank_account_id is not None:
            if m["bank_account_id"] != bank_account_id:
                continue

        if filter_type != "todos":
            if filter_type.upper() != m["flow_nature"]:
                continue

        if filter_origin != "todos":
            if filter_origin.lower() != m["origin_code"]:
                continue

        if filter_reconciliation != "todos":
            if filter_reconciliation.upper() != m["reconciliation_status"]:
                continue

        filtered_movements.append(m)

    # Keep the established chronological order, with origin and source ID as
    # deterministic tie-breakers when several movements share a date/document.
    filtered_movements.sort(
        key=lambda x: (
            x.get("date") or "",
            x.get("doc_number") or "",
            x.get("origin_code") or "",
            str(x.get("source_id") or ""),
        )
    )

    detail_page = paginate_movements(filtered_movements, page=page, page_size=page_size)

    # 4. Agrupación por Períodos
    def get_period_key(d_str: str) -> Tuple[str, str]:
        dt = date.fromisoformat(d_str)
        if clean_grouping == "diario":
            return d_str, dt.strftime("%d/%m/%Y")
        elif clean_grouping == "mensual":
            return dt.strftime("%Y-%m"), dt.strftime("%b %Y")
        else:
            iso = dt.isocalendar()
            monday = dt - timedelta(days=dt.weekday())
            return f"{iso[0]}-W{iso[1]:02d}", f"Sem {iso[1]} ({monday.strftime('%d/%m')})"

    periods_dict: Dict[str, Dict[str, Any]] = {}
    curr_d = start_d
    while curr_d <= end_d:
        p_key, p_label = get_period_key(curr_d.isoformat())
        if p_key not in periods_dict:
            periods_dict[p_key] = {
                "period_key": p_key,
                "label": p_label,
                "initial_balance": Decimal("0.00"),
                "real_inflows": Decimal("0.00"),
                "projected_inflows": Decimal("0.00"),
                "real_outflows": Decimal("0.00"),
                "projected_outflows": Decimal("0.00"),
                "internal_transfers_net": Decimal("0.00"),
                "total_inflows": Decimal("0.00"),
                "total_outflows": Decimal("0.00"),
                "net_period": Decimal("0.00"),
                "final_balance": Decimal("0.00"),
                "has_deficit": False,
                "is_future": False,
            }
        curr_d += timedelta(days=1)

    for m in filtered_movements:
        p_key, _ = get_period_key(m["date"])
        if p_key not in periods_dict:
            continue
        p = periods_dict[p_key]

        is_transf = m["is_internal_transfer"]
        if not bank_account_id and is_transf:
            p["internal_transfers_net"] += m["net_amount"]
            continue

        if m["flow_nature"] == "REAL":
            p["real_inflows"] += m["inflow"]
            p["real_outflows"] += m["outflow"]
        else:
            p["projected_inflows"] += m["inflow"]
            p["projected_outflows"] += m["outflow"]

    # 5. Cálculo de Carry-Forward de Saldos y Detección de Déficit
    sorted_period_keys = sorted(periods_dict.keys())
    running_balance = initial_balance
    min_projected_balance = initial_balance
    deficit_detected_anywhere = False

    period_rows: List[Dict[str, Any]] = []
    total_real_inflows = Decimal("0.00")
    total_projected_inflows = Decimal("0.00")
    total_real_outflows = Decimal("0.00")
    total_projected_outflows = Decimal("0.00")

    for k in sorted_period_keys:
        p = periods_dict[k]
        p["initial_balance"] = running_balance
        p["total_inflows"] = p["real_inflows"] + p["projected_inflows"]
        p["total_outflows"] = p["real_outflows"] + p["projected_outflows"]

        transfer_effect = p["internal_transfers_net"] if bank_account_id else Decimal("0.00")
        p["net_period"] = p["total_inflows"] - p["total_outflows"] + transfer_effect
        running_balance += p["net_period"]
        p["final_balance"] = running_balance

        if running_balance < min_projected_balance:
            min_projected_balance = running_balance

        if running_balance < Decimal("0.00"):
            p["has_deficit"] = True
            deficit_detected_anywhere = True

        total_real_inflows += p["real_inflows"]
        total_projected_inflows += p["projected_inflows"]
        total_real_outflows += p["real_outflows"]
        total_projected_outflows += p["projected_outflows"]

        period_rows.append(p)

    final_projected_balance = running_balance

    # 6. Datos del Gráfico
    chart_labels = [p["label"] for p in period_rows]
    chart_balances = [float(p["final_balance"]) for p in period_rows]
    chart_inflows = [float(p["total_inflows"]) for p in period_rows]
    chart_outflows = [float(p["total_outflows"]) for p in period_rows]

    return {
        "kpis": {
            "initial_balance": initial_balance,
            "current_balance": initial_balance + (total_real_inflows - total_real_outflows),
            "projected_inflows": total_projected_inflows,
            "projected_outflows": total_projected_outflows,
            "total_expected_inflows": total_real_inflows + total_projected_inflows,
            "total_expected_outflows": total_real_outflows + total_projected_outflows,
            "final_projected_balance": final_projected_balance,
            "min_projected_balance": min_projected_balance,
            "deficit_alert": deficit_detected_anywhere,
            "real_inflows": total_real_inflows,
            "real_outflows": total_real_outflows,
            "net_flow": (total_real_inflows + total_projected_inflows) - (total_real_outflows + total_projected_outflows),
        },
        "period_rows": period_rows,
        "movements": filtered_movements,
        "movements_page": detail_page["items"],
        "page": detail_page["page"],
        "page_size": detail_page["page_size"],
        "total_movements": detail_page["total"],
        "total_pages": detail_page["total_pages"],
        "page_start": detail_page["start"],
        "page_end": detail_page["end"],
        "chart": {
            "labels": chart_labels,
            "balances": chart_balances,
            "inflows": chart_inflows,
            "outflows": chart_outflows,
        },
        "filters": {
            "start_date": start_date,
            "end_date": end_date,
            "bank_account_id": bank_account_id,
            "grouping": clean_grouping,
            "filter_type": filter_type,
            "filter_origin": filter_origin,
            "filter_reconciliation": filter_reconciliation,
        },
    }
