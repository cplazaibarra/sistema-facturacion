"""
repositories/debts_repo.py
Domain repository for Financial Debts (Deudas Financieras).
Handles debts, debt types, installments schedule, partial payments, audits, and metrics.
"""

from decimal import Decimal
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional, Tuple
import json
import psycopg2
import psycopg2.extras

from core.database import get_connection


# ---------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------
def _to_decimal(val: Any) -> Decimal:
    if val is None or val == "":
        return Decimal("0.00")
    return Decimal(str(val)).quantize(Decimal("0.01"))


def _compute_installment_status(due_date_val: Any, balance: Decimal, paid_amount: Decimal) -> str:
    if balance <= Decimal("0.00"):
        return "PAGADA"
    if paid_amount > Decimal("0.00"):
        return "PAGO_PARCIAL"

    today = date.today()
    if isinstance(due_date_val, str):
        d_date = datetime.strptime(due_date_val, "%Y-%m-%d").date()
    elif isinstance(due_date_val, datetime):
        d_date = due_date_val.date()
    else:
        d_date = due_date_val

    if d_date < today:
        return "VENCIDA"
    return "PENDIENTE"


# ---------------------------------------------------------
# Debt Types
# ---------------------------------------------------------
def list_debt_types(active_only: bool = True) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            query = "SELECT id, name, is_active FROM debt_types"
            if active_only:
                query += " WHERE is_active = TRUE"
            query += " ORDER BY id ASC"
            cur.execute(query)
            return [dict(r) for r in cur.fetchall()]


# ---------------------------------------------------------
# Debts & Installments Management
# ---------------------------------------------------------
def create_debt_with_schedule(
    name: str,
    debt_type_id: int,
    creditor_name: str,
    original_amount: Decimal | float,
    start_date: str,
    installments_count: int,
    first_due_date: str,
    currency: str = "CLP",
    periodicity: str = "Mensual",
    interest_rate: Decimal | float = 0.0,
    creditor_rut: Optional[str] = None,
    contract_number: Optional[str] = None,
    bank_account_id: Optional[int] = None,
    notes: Optional[str] = None,
    custom_installments: Optional[List[Dict[str, Any]]] = None,
    created_by: str = "Sistema",
) -> Tuple[bool, str, Optional[int]]:
    """
    Creates a new debt and generates or registers its initial installment schedule.
    If custom_installments is provided, uses it.
    Otherwise, generates an initial clean schedule dividing original_amount evenly.
    """
    clean_name = (name or "").strip()
    clean_creditor = (creditor_name or "").strip()
    if not clean_name:
        return False, "El nombre de la deuda es obligatorio", None
    if not clean_creditor:
        return False, "El nombre del acreedor es obligatorio", None
    if installments_count <= 0:
        return False, "El número de cuotas debe ser mayor a 0", None

    orig_amt = _to_decimal(original_amount)
    if orig_amt <= Decimal("0.00"):
        return False, "El monto original debe ser mayor a cero", None

    try:
        first_dt = datetime.strptime(str(first_due_date).strip(), "%Y-%m-%d").date()
    except Exception:
        return False, "Fecha de primera cuota inválida (formato YYYY-MM-DD)", None

    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1. Insert debt header
            cur.execute(
                """
                INSERT INTO debts (
                    name, debt_type_id, creditor_name, creditor_rut, contract_number,
                    original_amount, currency, start_date, installments_count, periodicity,
                    interest_rate, bank_account_id, first_due_date, status, notes, created_by
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'ACTIVA', %s, %s)
                RETURNING id
                """,
                (
                    clean_name,
                    debt_type_id,
                    clean_creditor,
                    (creditor_rut or "").strip() or None,
                    (contract_number or "").strip() or None,
                    orig_amt,
                    currency.strip().upper(),
                    start_date,
                    installments_count,
                    periodicity.strip(),
                    _to_decimal(interest_rate),
                    bank_account_id or None,
                    first_dt,
                    notes,
                    created_by,
                ),
            )
            debt_id = cur.fetchone()["id"]

            # 2. Insert installments
            if custom_installments and len(custom_installments) > 0:
                for inst in custom_installments:
                    num = int(inst.get("installment_number", 1))
                    d_date = inst.get("due_date")
                    tot = _to_decimal(inst.get("total_amount", 0))
                    cap = _to_decimal(inst.get("capital", 0))
                    inte = _to_decimal(inst.get("interest", 0))
                    fees = _to_decimal(inst.get("fees", 0))
                    ins = _to_decimal(inst.get("insurance", 0))
                    oth = _to_decimal(inst.get("other_charges", 0))
                    st = _compute_installment_status(d_date, tot, Decimal("0.00"))

                    cur.execute(
                        """
                        INSERT INTO debt_installments (
                            debt_id, installment_number, due_date, capital, interest,
                            fees, insurance, other_charges, total_amount, paid_amount,
                            balance, status, notes
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 0.00, %s, %s, %s)
                        """,
                        (debt_id, num, d_date, cap, inte, fees, ins, oth, tot, tot, st, inst.get("notes")),
                    )
            else:
                # Generate standard initial schedule dividing capital evenly
                base_quota = (orig_amt / installments_count).quantize(Decimal("1.00"))
                # Adjust last quota for rounding difference
                running_sum = Decimal("0.00")

                for i in range(1, installments_count + 1):
                    # Month addition handling
                    year = first_dt.year + (first_dt.month + (i - 1) - 1) // 12
                    month = (first_dt.month + (i - 1) - 1) % 12 + 1
                    day = min(first_dt.day, 28 if month == 2 else (30 if month in (4, 6, 9, 11) else 31))
                    inst_date = date(year, month, day)

                    if i == installments_count:
                        quota_amt = orig_amt - running_sum
                    else:
                        quota_amt = base_quota
                        running_sum += quota_amt

                    st = _compute_installment_status(inst_date, quota_amt, Decimal("0.00"))

                    cur.execute(
                        """
                        INSERT INTO debt_installments (
                            debt_id, installment_number, due_date, capital, interest,
                            fees, insurance, other_charges, total_amount, paid_amount,
                            balance, status
                        )
                        VALUES (%s, %s, %s, %s, 0.00, 0.00, 0.00, 0.00, %s, 0.00, %s, %s)
                        """,
                        (debt_id, i, inst_date, quota_amt, quota_amt, quota_amt, st),
                    )

            # Audit record
            cur.execute(
                """
                INSERT INTO debt_audit (debt_id, action, previous_state, new_state, user_name, notes)
                VALUES (%s, 'CREATE_DEBT', NULL, %s, %s, 'Creación de deuda y plan de cuotas')
                """,
                (
                    debt_id,
                    json.dumps({"name": clean_name, "original_amount": str(orig_amt), "installments": installments_count}),
                    created_by,
                ),
            )

        conn.commit()
        return True, "Deuda y plan de cuotas creados exitosamente", debt_id


def get_debt_detail(debt_id: int) -> Optional[Dict[str, Any]]:
    """
    Retrieves full detail of a debt including totals, balances, and next installment.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 
                    d.id, d.name, d.debt_type_id, dt.name as debt_type_name,
                    d.creditor_name, d.creditor_rut, d.contract_number,
                    d.original_amount, d.currency, d.start_date, d.installments_count,
                    d.periodicity, d.interest_rate, d.bank_account_id,
                    ba.bank_name, ba.account_number as bank_account_number,
                    d.first_due_date, d.status, d.notes, d.created_at, d.created_by
                FROM debts d
                JOIN debt_types dt ON d.debt_type_id = dt.id
                LEFT JOIN bank_accounts ba ON d.bank_account_id = ba.id
                WHERE d.id = %s
                """,
                (debt_id,),
            )
            debt = cur.fetchone()
            if not debt:
                return None
            res = dict(debt)

            # Summary metrics from installments
            cur.execute(
                """
                SELECT
                    COUNT(*) as total_installments,
                    COUNT(*) FILTER (WHERE status = 'PAGADA') as paid_installments_count,
                    COUNT(*) FILTER (WHERE status = 'VENCIDA') as overdue_installments_count,
                    COUNT(*) FILTER (WHERE status IN ('PENDIENTE', 'PAGO_PARCIAL')) as pending_installments_count,
                    COALESCE(SUM(total_amount) FILTER (WHERE status != 'ANULADA'), 0) as total_obligations,
                    COALESCE(SUM(paid_amount), 0) as total_paid,
                    COALESCE(SUM(balance) FILTER (WHERE status != 'ANULADA'), 0) as total_balance
                FROM debt_installments
                WHERE debt_id = %s
                """,
                (debt_id,),
            )
            sums = cur.fetchone()
            res.update({
                "total_installments": sums["total_installments"],
                "paid_installments_count": sums["paid_installments_count"],
                "overdue_installments_count": sums["overdue_installments_count"],
                "pending_installments_count": sums["pending_installments_count"],
                "total_obligations": Decimal(str(sums["total_obligations"])),
                "total_paid": Decimal(str(sums["total_paid"])),
                "total_balance": Decimal(str(sums["total_balance"])),
            })

            # Next pending installment
            cur.execute(
                """
                SELECT id, installment_number, due_date, total_amount, balance
                FROM debt_installments
                WHERE debt_id = %s AND status IN ('PENDIENTE', 'PAGO_PARCIAL', 'VENCIDA')
                ORDER BY due_date ASC, installment_number ASC
                LIMIT 1
                """,
                (debt_id,),
            )
            next_inst = cur.fetchone()
            res["next_installment"] = dict(next_inst) if next_inst else None

            return res


def list_debt_installments(debt_id: int) -> List[Dict[str, Any]]:
    """
    Returns all installments for a specific debt.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 
                    id, debt_id, installment_number, due_date, capital, interest,
                    fees, insurance, other_charges, total_amount, paid_amount,
                    balance, status, paid_date, notes
                FROM debt_installments
                WHERE debt_id = %s
                ORDER BY installment_number ASC, due_date ASC
                """,
                (debt_id,),
            )
            rows = [dict(r) for r in cur.fetchall()]
            today = date.today()
            # Dynamic check on overdue status if pending and due_date < today
            for r in rows:
                if r["status"] in ("PENDIENTE", "PAGO_PARCIAL"):
                    d_date = r["due_date"]
                    if isinstance(d_date, str):
                        d_date = datetime.strptime(d_date, "%Y-%m-%d").date()
                    if d_date < today and r["paid_amount"] == 0:
                        r["status"] = "VENCIDA"
            return rows


def list_debts(
    debt_type_id: Optional[int] = None,
    status: Optional[str] = None,
    creditor: Optional[str] = None,
    bank_account_id: Optional[int] = None,
    search: Optional[str] = None,
    page: Optional[int] = None,
) -> List[Dict[str, Any]] | Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Lists debts with calculated balances and next installment data; optional UI page uses SQL LIMIT."
    """
    where_clauses = ["1=1"]
    params: List[Any] = []

    if debt_type_id:
        where_clauses.append("d.debt_type_id = %s")
        params.append(debt_type_id)
    if status and status.strip() and status != "all":
        where_clauses.append("d.status = %s")
        params.append(status.strip().upper())
    if creditor and creditor.strip():
        where_clauses.append("d.creditor_name ILIKE %s")
        params.append(f"%{creditor.strip()}%")
    if bank_account_id:
        where_clauses.append("d.bank_account_id = %s")
        params.append(bank_account_id)
    if search and search.strip():
        q = f"%{search.strip()}%"
        where_clauses.append("(d.name ILIKE %s OR d.creditor_name ILIKE %s OR d.contract_number ILIKE %s OR d.creditor_rut ILIKE %s)")
        params.extend([q, q, q, q])

    where_str = " AND ".join(where_clauses)

    with get_connection() as conn:
        with conn.cursor() as cur:
            pagination = None
            if page is not None:
                from core.pagination import PAGE_SIZE, pagination_meta
                cur.execute(f"SELECT COUNT(*) AS n FROM debts d WHERE {where_str}", params)
                pagination = pagination_meta(cur.fetchone()["n"], page)
            query = f"""
                SELECT 
                    d.id, d.name, d.debt_type_id, dt.name as debt_type_name,
                    d.creditor_name, d.creditor_rut, d.contract_number,
                    d.original_amount, d.currency, d.start_date, d.installments_count,
                    d.periodicity, d.interest_rate, d.bank_account_id,
                    ba.bank_name, ba.account_number as bank_account_number,
                    d.first_due_date, d.status, d.notes, d.created_at,
                    COALESCE(sums.total_paid, 0) as total_paid,
                    COALESCE(sums.total_balance, d.original_amount) as total_balance,
                    COALESCE(sums.paid_count, 0) as paid_count,
                    COALESCE(sums.total_count, d.installments_count) as total_count,
                    next_inst.next_due_date,
                    next_inst.next_amount
                FROM debts d
                JOIN debt_types dt ON d.debt_type_id = dt.id
                LEFT JOIN bank_accounts ba ON d.bank_account_id = ba.id
                LEFT JOIN (
                    SELECT 
                        debt_id,
                        SUM(paid_amount) as total_paid,
                        SUM(balance) FILTER (WHERE status != 'ANULADA') as total_balance,
                        COUNT(*) FILTER (WHERE status = 'PAGADA') as paid_count,
                        COUNT(*) as total_count
                    FROM debt_installments
                    GROUP BY debt_id
                ) sums ON d.id = sums.debt_id
                LEFT JOIN LATERAL (
                    SELECT due_date as next_due_date, total_amount as next_amount
                    FROM debt_installments
                    WHERE debt_id = d.id AND status IN ('PENDIENTE', 'PAGO_PARCIAL', 'VENCIDA')
                    ORDER BY due_date ASC, installment_number ASC
                    LIMIT 1
                ) next_inst ON TRUE
                WHERE {where_str}
                ORDER BY (d.status = 'ACTIVA') DESC, d.id DESC
            """
            query_params=list(params)
            if pagination is not None:
                query += " LIMIT %s OFFSET %s"
                query_params.extend([PAGE_SIZE,pagination["offset"]])
            cur.execute(query, query_params)
            rows=[dict(r) for r in cur.fetchall()]
            return (rows,pagination) if pagination is not None else rows


def get_debts_kpis() -> Dict[str, Any]:
    """
    Calculates summary KPIs across all debts and installments.
    """
    today = date.today()
    in_7_days = today + timedelta(days=7)
    in_30_days = today + timedelta(days=30)
    next_month_start = (today.replace(day=28) + timedelta(days=4)).replace(day=1)
    # End of next month
    next_month_end = (next_month_start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COALESCE(SUM(balance) FILTER (WHERE status != 'ANULADA'), 0) as total_pending_debt,
                    COALESCE(SUM(balance) FILTER (WHERE status = 'VENCIDA' OR (status IN ('PENDIENTE', 'PAGO_PARCIAL') AND due_date < %s)), 0) as overdue_debt,
                    COALESCE(SUM(balance) FILTER (WHERE status IN ('PENDIENTE', 'PAGO_PARCIAL', 'VENCIDA') AND due_date BETWEEN %s AND %s), 0) as due_next_7_days,
                    COALESCE(SUM(balance) FILTER (WHERE status IN ('PENDIENTE', 'PAGO_PARCIAL', 'VENCIDA') AND due_date BETWEEN %s AND %s), 0) as due_next_30_days,
                    COALESCE(SUM(balance) FILTER (WHERE status IN ('PENDIENTE', 'PAGO_PARCIAL') AND due_date BETWEEN %s AND %s), 0) as projected_next_month,
                    COUNT(DISTINCT debt_id) FILTER (WHERE status != 'ANULADA' AND balance > 0) as active_debts_count
                FROM debt_installments
                """,
                (today, today, in_7_days, today, in_30_days, next_month_start, next_month_end),
            )
            row = cur.fetchone()
            return {
                "total_pending_debt": Decimal(str(row["total_pending_debt"] or 0)),
                "overdue_debt": Decimal(str(row["overdue_debt"] or 0)),
                "due_next_7_days": Decimal(str(row["due_next_7_days"] or 0)),
                "due_next_30_days": Decimal(str(row["due_next_30_days"] or 0)),
                "projected_next_month": Decimal(str(row["projected_next_month"] or 0)),
                "active_debts_count": row["active_debts_count"] or 0,
            }


# ---------------------------------------------------------
# Installment Payment Processing
# ---------------------------------------------------------
def register_debt_installment_payment(
    installment_id: int,
    payment_amount: Decimal | float,
    payment_date: str,
    bank_account_id: int,
    payment_method: str = "Transferencia",
    reference: Optional[str] = None,
    proof_file: Optional[str] = None,
    notes: Optional[str] = None,
    user_name: str = "Sistema",
) -> Tuple[bool, str, Optional[int]]:
    """
    Registers a full or partial payment against a debt installment.
    Locks installment row with SELECT FOR UPDATE to prevent concurrency bugs.
    Guarantees no overpayment: rejects if payment_amount > balance.
    Updates installment balance and status, plus overall debt status if completed.
    """
    pay_amt = _to_decimal(payment_amount)
    if pay_amt <= Decimal("0.00"):
        return False, "El monto del pago debe ser mayor a cero", None

    try:
        pay_dt = datetime.strptime(str(payment_date).strip(), "%Y-%m-%d").date()
    except Exception:
        return False, "Fecha de pago inválida (formato YYYY-MM-DD)", None

    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1. Lock installment row
            cur.execute(
                """
                SELECT 
                    di.id, di.debt_id, di.installment_number, di.due_date,
                    di.total_amount, di.paid_amount, di.balance, di.status,
                    d.name as debt_name
                FROM debt_installments di
                JOIN debts d ON di.debt_id = d.id
                WHERE di.id = %s
                FOR UPDATE
                """,
                (installment_id,),
            )
            inst = cur.fetchone()
            if not inst:
                return False, "Cuota no encontrada", None

            current_balance = Decimal(str(inst["balance"]))
            current_paid = Decimal(str(inst["paid_amount"]))
            debt_id = inst["debt_id"]

            if inst["status"] == "PAGADA" or current_balance <= Decimal("0.00"):
                return False, "La cuota ya se encuentra totalmente pagada", None

            if inst["status"] == "ANULADA":
                return False, "No se puede registrar pago en una cuota anulada", None

            # Strict overpayment rejection
            if pay_amt > current_balance:
                return False, f"Sobrepago rechazado: El monto a pagar (${pay_amt:,.0f}) excede el saldo pendiente (${current_balance:,.0f})", None

            new_paid = current_paid + pay_amt
            new_balance = current_balance - pay_amt
            new_status = "PAGADA" if new_balance == Decimal("0.00") else "PAGO_PARCIAL"

            # 2. Insert payment record
            cur.execute(
                """
                INSERT INTO debt_payments (
                    debt_installment_id, payment_date, payment_amount,
                    bank_account_id, payment_method, reference, proof_file, notes, created_by
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    installment_id,
                    pay_dt,
                    pay_amt,
                    bank_account_id,
                    payment_method.strip(),
                    (reference or "").strip() or None,
                    proof_file,
                    notes,
                    user_name,
                ),
            )
            payment_id = cur.fetchone()["id"]

            # 3. Update installment
            cur.execute(
                """
                UPDATE debt_installments
                SET paid_amount = %s, balance = %s, status = %s,
                    paid_date = CASE WHEN %s = 'PAGADA' THEN %s ELSE paid_date END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (new_paid, new_balance, new_status, new_status, pay_dt, installment_id),
            )

            # 4. Check if all valid installments in debt are paid
            cur.execute(
                """
                SELECT COUNT(*) as pending_count
                FROM debt_installments
                WHERE debt_id = %s AND status != 'ANULADA' AND balance > 0
                """,
                (debt_id,),
            )
            pending_count = cur.fetchone()["pending_count"]
            if pending_count == 0:
                cur.execute(
                    """
                    UPDATE debts SET status = 'PAGADA', updated_at = CURRENT_TIMESTAMP WHERE id = %s
                    """,
                    (debt_id,),
                )

            # 5. Audit record
            cur.execute(
                """
                INSERT INTO debt_audit (debt_id, installment_id, action, previous_state, new_state, user_name, notes)
                VALUES (%s, %s, 'PAYMENT', %s, %s, %s, %s)
                """,
                (
                    debt_id,
                    installment_id,
                    json.dumps({"status": inst["status"], "balance": str(current_balance), "paid": str(current_paid)}),
                    json.dumps({"status": new_status, "balance": str(new_balance), "paid": str(new_paid), "payment_id": payment_id}),
                    user_name,
                    f"Pago registrado por ${pay_amt:,.0f} el {pay_dt}",
                ),
            )

        conn.commit()
        return True, "Pago de cuota registrado exitosamente", payment_id


def list_debt_payment_history(debt_id: Optional[int] = None, installment_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Retrieves chronological payment history for a debt or a specific installment.
    """
    where_clauses = ["1=1"]
    params: List[Any] = []

    if debt_id:
        where_clauses.append("di.debt_id = %s")
        params.append(debt_id)
    if installment_id:
        where_clauses.append("dp.debt_installment_id = %s")
        params.append(installment_id)

    where_str = " AND ".join(where_clauses)

    with get_connection() as conn:
        with conn.cursor() as cur:
            query = f"""
                SELECT 
                    dp.id, dp.debt_installment_id, di.debt_id, di.installment_number,
                    d.name as debt_name, d.creditor_name,
                    dp.payment_date, dp.payment_amount, dp.bank_account_id,
                    ba.bank_name, ba.account_number as bank_account_number,
                    dp.payment_method, dp.reference, dp.proof_file, dp.notes,
                    dp.created_by, dp.created_at
                FROM debt_payments dp
                JOIN debt_installments di ON dp.debt_installment_id = di.id
                JOIN debts d ON di.debt_id = d.id
                JOIN bank_accounts ba ON dp.bank_account_id = ba.id
                WHERE {where_str}
                ORDER BY dp.payment_date DESC, dp.id DESC
            """
            cur.execute(query, params)
            return [dict(r) for r in cur.fetchall()]


def update_installment_details(
    installment_id: int,
    due_date: str,
    capital: Decimal | float,
    interest: Decimal | float,
    fees: Decimal | float,
    insurance: Decimal | float,
    other_charges: Decimal | float,
    notes: Optional[str] = None,
    user_name: str = "Sistema",
) -> Tuple[bool, str]:
    """
    Edits an installment schedule if it has not been fully paid.
    Calculates total_amount = capital + interest + fees + insurance + other_charges.
    Adjusts balance = total_amount - paid_amount.
    Prevents modifying fully paid installments.
    """
    cap = _to_decimal(capital)
    inte = _to_decimal(interest)
    fe = _to_decimal(fees)
    ins = _to_decimal(insurance)
    oth = _to_decimal(other_charges)
    tot = cap + inte + fe + ins + oth

    if tot <= Decimal("0.00"):
        return False, "El monto total de la cuota debe ser mayor a cero"

    try:
        d_date = datetime.strptime(str(due_date).strip(), "%Y-%m-%d").date()
    except Exception:
        return False, "Fecha de vencimiento inválida (formato YYYY-MM-DD)"

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, debt_id, installment_number, total_amount, paid_amount, balance, status, due_date
                FROM debt_installments
                WHERE id = %s
                FOR UPDATE
                """,
                (installment_id,),
            )
            inst = cur.fetchone()
            if not inst:
                return False, "Cuota no encontrada"

            if inst["status"] == "PAGADA":
                return False, "No se puede modificar una cuota que ya está totalmente pagada"

            paid = Decimal(str(inst["paid_amount"]))
            if tot < paid:
                return False, f"El nuevo total (${tot:,.0f}) no puede ser menor a lo ya pagado (${paid:,.0f})"

            new_balance = tot - paid
            new_status = _compute_installment_status(d_date, new_balance, paid)

            cur.execute(
                """
                UPDATE debt_installments
                SET due_date = %s, capital = %s, interest = %s, fees = %s,
                    insurance = %s, other_charges = %s, total_amount = %s,
                    balance = %s, status = %s, notes = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (d_date, cap, inte, fe, ins, oth, tot, new_balance, new_status, notes, installment_id),
            )

            # Audit
            cur.execute(
                """
                INSERT INTO debt_audit (debt_id, installment_id, action, previous_state, new_state, user_name, notes)
                VALUES (%s, %s, 'UPDATE_INSTALLMENT', %s, %s, %s, %s)
                """,
                (
                    inst["debt_id"],
                    installment_id,
                    json.dumps({"total": str(inst["total_amount"]), "due_date": str(inst["due_date"])}),
                    json.dumps({"total": str(tot), "due_date": str(d_date), "balance": str(new_balance)}),
                    user_name,
                    f"Modificación cuota #{inst['installment_number']}",
                ),
            )

        conn.commit()
        return True, "Cuota actualizada exitosamente"
