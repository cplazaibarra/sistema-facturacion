"""
services/bank_reconciliation_excel_service.py
Service for Bank Statement Excel Import/Export and Canonical Round-trip handling.
Strictly adheres to:
- Openpyxl styling with Navy header fill and gridlines.
- Formula injection protection for all text cells.
- Decimal precision for financial amounts.
- Case-insensitive, robust column header detection.
- Exact round-trip consistency: Export -> Re-import results in 0 new, N duplicates, 0 errors.
"""

import io
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from repositories.bank_reconciliation_repo import (
    generate_transaction_fingerprint,
    get_existing_fingerprints,
    list_bank_transaction_categories,
    insert_bank_transactions_bulk,
    log_bank_transaction_import,
    list_bank_transactions,
)
from repositories.finance_repo import get_bank_account


# Definición canónica de columnas de la cartola bancaria
BANK_STATEMENT_COLUMNS = [
    {"key": "transaction_date", "header": "Fecha", "width": 14, "required": True, "description": "YYYY-MM-DD o DD/MM/YYYY"},
    {"key": "value_date", "header": "Fecha Valor", "width": 14, "required": False, "description": "Fecha contable/valor"},
    {"key": "description", "header": "Descripción", "width": 35, "required": True, "description": "Glosa o descripción bancaria"},
    {"key": "reference", "header": "Referencia", "width": 20, "required": False, "description": "Referencia o código TEF"},
    {"key": "doc_number", "header": "N° Documento", "width": 18, "required": False, "description": "N° cheque o comprobante"},
    {"key": "charge", "header": "Cargo", "width": 16, "required": False, "description": "Débito / Salida ($)"},
    {"key": "credit", "header": "Abono", "width": 16, "required": False, "description": "Crédito / Entrada ($)"},
    {"key": "amount", "header": "Monto", "width": 16, "required": False, "description": "Monto con signo (+/-)"},
    {"key": "movement_type", "header": "Tipo Movimiento", "width": 16, "required": False, "description": "ABONO o CARGO"},
    {"key": "balance", "header": "Saldo", "width": 16, "required": False, "description": "Saldo final tras movimiento"},
    {"key": "currency", "header": "Moneda", "width": 10, "required": False, "description": "CLP, USD, etc. (Default CLP)"},
    {"key": "category_name", "header": "Categoría", "width": 24, "required": False, "description": "Nombre de categoría válida"},
    {"key": "notes", "header": "Observaciones", "width": 30, "required": False, "description": "Notas u observaciones internas"},
]

HEADER_MAP = {col["header"].strip().lower(): col for col in BANK_STATEMENT_COLUMNS}
KEY_MAP = {col["key"]: col for col in BANK_STATEMENT_COLUMNS}


def _get_styles():
    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    data_font = Font(name="Calibri", size=10)
    thin_border = Border(
        left=Side(style="thin", color="E2E8F0"),
        right=Side(style="thin", color="E2E8F0"),
        top=Side(style="thin", color="E2E8F0"),
        bottom=Side(style="thin", color="E2E8F0"),
    )
    return header_fill, header_font, data_font, thin_border


def _safe_str(val: Any) -> str:
    if val is None:
        return ""
    s = str(val).strip()
    if s and s[0] in ("=", "+", "-", "@"):
        return f"'{s}"
    return s


def parse_date_flexible(val: Any) -> Optional[str]:
    """Parses date from string (YYYY-MM-DD, DD/MM/YYYY, DD-MM-YYYY) or datetime/date object."""
    if not val:
        return None
    if isinstance(val, (datetime, date)):
        return val.strftime("%Y-%m-%d")
    s = str(val).strip()
    if not s:
        return None

    # Handle space separation if time included
    if " " in s:
        s = s.split(" ")[0].strip()

    formats = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d.%m.%Y"]
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def parse_decimal_flexible(val: Any) -> Optional[Decimal]:
    """Parses decimal amount handling formats like 1.250,50 or 1,250.50 or plain 1250."""
    if val is None or val == "":
        return None
    if isinstance(val, (int, float, Decimal)):
        return Decimal(str(val)).quantize(Decimal("0.01"))

    s = str(val).strip().replace("$", "").replace("CLP", "").strip()
    if not s:
        return None

    if "." in s and "," in s:
        if s.rfind(",") > s.rfind("."):  # 1.250,50
            s = s.replace(".", "").replace(",", ".")
        else:  # 1,250.50
            s = s.replace(",", "")
    elif "," in s:  # 1250,50
        s = s.replace(",", ".")

    try:
        return Decimal(s).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def generate_bank_statement_template(bank_account_id: Optional[int] = None) -> io.BytesIO:
    """Generates official canonical template with headers and 2 example rows."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Cartola Bancaria"
    ws.views.sheetView[0].showGridLines = True

    header_fill, header_font, data_font, thin_border = _get_styles()

    for col_idx, col in enumerate(BANK_STATEMENT_COLUMNS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=col["header"])
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border
        col_letter = get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = col["width"]

    ws.row_dimensions[1].height = 28

    sample_rows = [
        {
            "transaction_date": datetime.now().strftime("%Y-%m-%d"),
            "value_date": datetime.now().strftime("%Y-%m-%d"),
            "description": "TRANSFERENCIA RECIBIDA CLIENTE EJEMPLO",
            "reference": "TEF-12345678",
            "doc_number": "00150",
            "charge": 0,
            "credit": 150000,
            "amount": 150000,
            "movement_type": "ABONO",
            "balance": 2500000,
            "currency": "CLP",
            "category_name": "Ventas / Cobranzas",
            "notes": "Abono recibido factura venta",
        },
        {
            "transaction_date": datetime.now().strftime("%Y-%m-%d"),
            "value_date": datetime.now().strftime("%Y-%m-%d"),
            "description": "CARGO AUTOMATICO SERVICIO INTERNET",
            "reference": "PAC-98765432",
            "doc_number": "",
            "charge": 45000,
            "credit": 0,
            "amount": -45000,
            "movement_type": "CARGO",
            "balance": 2455000,
            "currency": "CLP",
            "category_name": "Servicios",
            "notes": "Pago mensual conectividad",
        },
    ]

    for row_idx, data in enumerate(sample_rows, start=2):
        ws.row_dimensions[row_idx].height = 20
        for col_idx, col in enumerate(BANK_STATEMENT_COLUMNS, start=1):
            val = data.get(col["key"])
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.font = data_font
            cell.border = thin_border

            if col["key"] in ("charge", "credit", "amount", "balance"):
                cell.value = float(val) if val is not None else 0.0
                cell.number_format = "$#,##0"
                cell.alignment = Alignment(horizontal="right", vertical="center")
            elif col["key"] in ("transaction_date", "value_date"):
                cell.value = str(val)
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                cell.value = _safe_str(val)
                cell.alignment = Alignment(horizontal="left", vertical="center")

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output


def export_bank_transactions_to_excel(
    bank_account_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    movement_type: Optional[str] = None,
    reconciliation_status: Optional[str] = None,
    category_id: Optional[int] = None,
    search: Optional[str] = None,
) -> io.BytesIO:
    """Exports filtered bank transactions in the exact canonical round-trip format."""
    # Export the full filtered universe independently of screen pagination.
    rows, _ = list_bank_transactions(
        bank_account_id=bank_account_id,
        start_date=start_date,
        end_date=end_date,
        movement_type=movement_type,
        reconciliation_status=reconciliation_status,
        category_id=category_id,
        search=search,
        page=1,
        export_all=True,
    )

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Movimientos Bancarios"
    ws.views.sheetView[0].showGridLines = True

    header_fill, header_font, data_font, thin_border = _get_styles()

    for col_idx, col in enumerate(BANK_STATEMENT_COLUMNS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=col["header"])
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border
        col_letter = get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = col["width"]

    ws.row_dimensions[1].height = 28

    for row_idx, r in enumerate(rows, start=2):
        ws.row_dimensions[row_idx].height = 20
        for col_idx, col in enumerate(BANK_STATEMENT_COLUMNS, start=1):
            k = col["key"]
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.font = data_font
            cell.border = thin_border

            val = r.get(k)
            if k in ("charge", "credit", "amount", "balance"):
                cell.value = float(val) if val is not None else 0.0
                cell.number_format = "$#,##0"
                cell.alignment = Alignment(horizontal="right", vertical="center")
            elif k in ("transaction_date", "value_date"):
                cell.value = str(val) if val else ""
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                cell.value = _safe_str(val)
                cell.alignment = Alignment(horizontal="left", vertical="center")

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output


def parse_and_preview_bank_statement(file_bytes: bytes, bank_account_id: int) -> Dict[str, Any]:
    """
    Parses an uploaded Excel bank statement, validates each row,
    detects duplicates via fingerprint against DB, and returns preview stats.
    """
    account = get_bank_account(bank_account_id)
    if not account:
        return {"error": f"Cuenta bancaria #{bank_account_id} no existe", "status": "error"}

    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    except Exception as e:
        return {"error": f"No se pudo leer el archivo Excel: {str(e)}", "status": "error"}

    ws = wb.active
    rows_iter = ws.iter_rows(values_only=True)

    try:
        header_row = next(rows_iter)
    except StopIteration:
        return {"error": "El archivo Excel está completamente vacío", "status": "error"}

    # Map headers
    col_mapping = {}
    for idx, cell_val in enumerate(header_row):
        if not cell_val:
            continue
        cleaned = str(cell_val).strip().lower()
        if cleaned in HEADER_MAP:
            col_mapping[HEADER_MAP[cleaned]["key"]] = idx

    if "transaction_date" not in col_mapping or "description" not in col_mapping:
        return {
            "error": "El archivo no contiene las columnas mínimas obligatorias ('Fecha' y 'Descripción')",
            "status": "error",
        }

    # Fetch active categories map
    categories = list_bank_transaction_categories(active_only=False)
    cat_by_name = {c["name"].strip().lower(): c["id"] for c in categories}

    parsed_rows: List[Dict[str, Any]] = []
    fingerprints_to_check: List[str] = []
    seen_in_file: set[str] = set()

    row_index = 1
    for row in rows_iter:
        row_index += 1
        # Check if row is empty
        if not any(cell is not None and str(cell).strip() != "" for cell in row):
            continue

        raw_date = row[col_mapping["transaction_date"]] if "transaction_date" in col_mapping and col_mapping["transaction_date"] < len(row) else None
        tx_date = parse_date_flexible(raw_date)

        raw_vdate = row[col_mapping["value_date"]] if "value_date" in col_mapping and col_mapping["value_date"] < len(row) else None
        v_date = parse_date_flexible(raw_vdate)

        raw_desc = row[col_mapping["description"]] if "description" in col_mapping and col_mapping["description"] < len(row) else None
        desc = str(raw_desc).strip() if raw_desc is not None else ""

        ref = str(row[col_mapping["reference"]]).strip() if "reference" in col_mapping and col_mapping["reference"] < len(row) and row[col_mapping["reference"]] is not None else None
        doc = str(row[col_mapping["doc_number"]]).strip() if "doc_number" in col_mapping and col_mapping["doc_number"] < len(row) and row[col_mapping["doc_number"]] is not None else None

        # Clean formula escape prefix
        if desc.startswith("'"):
            desc = desc[1:]
        if ref and ref.startswith("'"):
            ref = ref[1:]
        if doc and doc.startswith("'"):
            doc = doc[1:]

        raw_charge = row[col_mapping["charge"]] if "charge" in col_mapping and col_mapping["charge"] < len(row) else None
        charge = parse_decimal_flexible(raw_charge) or Decimal("0.00")

        raw_credit = row[col_mapping["credit"]] if "credit" in col_mapping and col_mapping["credit"] < len(row) else None
        credit = parse_decimal_flexible(raw_credit) or Decimal("0.00")

        raw_amount = row[col_mapping["amount"]] if "amount" in col_mapping and col_mapping["amount"] < len(row) else None
        amount = parse_decimal_flexible(raw_amount)

        raw_mov_type = row[col_mapping["movement_type"]] if "movement_type" in col_mapping and col_mapping["movement_type"] < len(row) else None
        mov_type = str(raw_mov_type).strip().upper() if raw_mov_type else None

        raw_bal = row[col_mapping["balance"]] if "balance" in col_mapping and col_mapping["balance"] < len(row) else None
        balance = parse_decimal_flexible(raw_bal)

        currency = str(row[col_mapping["currency"]]).strip().upper() if "currency" in col_mapping and col_mapping["currency"] < len(row) and row[col_mapping["currency"]] else "CLP"

        raw_cat = str(row[col_mapping["category_name"]]).strip() if "category_name" in col_mapping and col_mapping["category_name"] < len(row) and row[col_mapping["category_name"]] else None
        cat_id = cat_by_name.get(raw_cat.lower()) if raw_cat else None

        notes = str(row[col_mapping["notes"]]).strip() if "notes" in col_mapping and col_mapping["notes"] < len(row) and row[col_mapping["notes"]] else None
        if notes and notes.startswith("'"):
            notes = notes[1:]

        # Validation logic
        errors = []
        if not tx_date:
            errors.append(f"Fecha inválida o vacía ('{raw_date}')")
        if not desc:
            errors.append("Descripción requerida")

        # Determine Amount and Movement Type
        if amount is None:
            if credit > 0 and charge == 0:
                amount = credit
                mov_type = "ABONO"
            elif charge > 0 and credit == 0:
                amount = -charge
                mov_type = "CARGO"
            elif credit > 0 and charge > 0:
                amount = credit - charge
                mov_type = "ABONO" if amount >= 0 else "CARGO"
            else:
                errors.append("Monto no especificado (Cargo y Abono en 0)")
                amount = Decimal("0.00")
                mov_type = "CARGO"
        else:
            if mov_type is None:
                mov_type = "ABONO" if amount >= 0 else "CARGO"
            if charge == 0 and credit == 0:
                if amount >= 0:
                    credit = amount
                else:
                    charge = abs(amount)

        # Standardize signs: Abono is always positive, Cargo is always negative amount
        if mov_type == "CARGO" and amount > 0:
            amount = -amount
        elif mov_type == "ABONO" and amount < 0:
            amount = abs(amount)

        fingerprint = ""
        if not errors:
            fingerprint = generate_transaction_fingerprint(
                bank_account_id=bank_account_id,
                transaction_date=tx_date,
                value_date=v_date,
                amount=amount,
                movement_type=mov_type,
                reference=ref,
                doc_number=doc,
                description=desc,
            )
            fingerprints_to_check.append(fingerprint)

        parsed_rows.append({
            "row_number": row_index,
            "transaction_date": tx_date,
            "value_date": v_date,
            "description": desc,
            "reference": ref,
            "doc_number": doc,
            "charge": float(charge),
            "credit": float(credit),
            "amount": float(amount),
            "movement_type": mov_type,
            "balance": float(balance) if balance is not None else None,
            "currency": currency,
            "category_id": cat_id,
            "category_name": raw_cat,
            "notes": notes,
            "fingerprint": fingerprint,
            "errors": errors,
            "status": "ERROR" if errors else "NEW",
        })

    # Query DB for duplicate fingerprints
    existing_fp_set = get_existing_fingerprints(fingerprints_to_check)

    total_count = len(parsed_rows)
    new_count = 0
    duplicate_count = 0
    error_count = 0

    valid_transactions_to_insert = []

    for r in parsed_rows:
        if r["status"] == "ERROR":
            error_count += 1
            continue

        fp = r["fingerprint"]
        if fp in existing_fp_set or fp in seen_in_file:
            r["status"] = "DUPLICATE"
            r["errors"].append("Movimiento ya registrado (detectado por huella digital)")
            duplicate_count += 1
        else:
            seen_in_file.add(fp)
            r["status"] = "NEW"
            new_count += 1
            valid_transactions_to_insert.append(r)

    return {
        "status": "success",
        "bank_account": account,
        "summary": {
            "total_rows": total_count,
            "new_rows": new_count,
            "duplicate_rows": duplicate_count,
            "error_rows": error_count,
        },
        "rows": parsed_rows[:100],  # preview max 100 rows
        "valid_transactions": valid_transactions_to_insert,
    }


def commit_bank_statement_import(
    valid_transactions: List[Dict[str, Any]],
    bank_account_id: int,
    filename: str,
    user_name: str,
    summary: Dict[str, int],
) -> Dict[str, Any]:
    """Atomically writes validated non-duplicate transactions into DB and logs import record."""
    import_id = log_bank_transaction_import(
        filename=filename,
        bank_account_id=bank_account_id,
        imported_by=user_name,
        total_rows=summary.get("total_rows", len(valid_transactions)),
        new_rows=summary.get("new_rows", len(valid_transactions)),
        duplicate_rows=summary.get("duplicate_rows", 0),
        error_rows=summary.get("error_rows", 0),
    )

    inserted = insert_bank_transactions_bulk(
        transactions=valid_transactions,
        import_id=import_id,
        bank_account_id=bank_account_id,
    )

    return {
        "success": True,
        "import_id": import_id,
        "inserted_count": inserted,
    }
