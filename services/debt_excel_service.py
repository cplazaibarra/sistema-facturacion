"""
services/debt_excel_service.py
Service for importing and exporting debt installment plans in Excel (.xlsx).
Follows canonical schema with formula injection mitigation and exact decimal handling.
"""

import io
from decimal import Decimal
from datetime import datetime, date
from typing import Any, Dict, List, Tuple
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


def _safe_str(val: Any) -> str:
    s = str(val) if val is not None else ""
    if s.startswith(("=", "+", "-", "@")):
        return "'" + s
    return s


def export_debt_schedule_excel(debt: Dict[str, Any], installments: List[Dict[str, Any]]) -> bytes:
    """
    Generates an Excel file with the full installment schedule of a debt.
    Round-trip compatible for re-importing.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Plan de Cuotas"

    # Header Styles
    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    meta_font = Font(name="Calibri", size=10, bold=True, color="1E293B")
    border_thin = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1"),
    )

    # Debt Summary Header
    debt_title = f"DEUDA: {_safe_str(debt.get('name'))}"
    ws.cell(row=1, column=1, value=_safe_str(debt_title) if not debt_title.startswith("'") else debt_title).font = Font(size=14, bold=True, color="1E3A8A")
    ws.cell(row=2, column=1, value=_safe_str(f"Acreedor: {_safe_str(debt.get('creditor_name'))} | Contrato: {_safe_str(debt.get('contract_number') or '-')} | Moneda: {debt.get('currency', 'CLP')}")).font = meta_font
    ws.cell(row=3, column=1, value=_safe_str(f"Monto Original: ${Decimal(str(debt.get('original_amount', 0))):,.0f} | Cuotas: {debt.get('installments_count')}")).font = meta_font

    headers = [
        "N° Cuota",
        "Fecha Vencimiento (YYYY-MM-DD)",
        "Capital",
        "Interés",
        "Comisiones",
        "Seguros",
        "Otros Cargos",
        "Total Cuota",
        "Monto Pagado",
        "Saldo",
        "Estado",
        "Observaciones",
    ]

    header_row = 5
    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=header_row, column=col_idx, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for row_idx, inst in enumerate(installments, header_row + 1):
        ws.cell(row=row_idx, column=1, value=inst.get("installment_number")).alignment = Alignment(horizontal="center")
        ws.cell(row=row_idx, column=2, value=_safe_str(str(inst.get("due_date")))).alignment = Alignment(horizontal="center")
        ws.cell(row=row_idx, column=3, value=float(Decimal(str(inst.get("capital") or 0))))
        ws.cell(row=row_idx, column=4, value=float(Decimal(str(inst.get("interest") or 0))))
        ws.cell(row=row_idx, column=5, value=float(Decimal(str(inst.get("fees") or 0))))
        ws.cell(row=row_idx, column=6, value=float(Decimal(str(inst.get("insurance") or 0))))
        ws.cell(row=row_idx, column=7, value=float(Decimal(str(inst.get("other_charges") or 0))))
        ws.cell(row=row_idx, column=8, value=float(Decimal(str(inst.get("total_amount") or 0))))
        ws.cell(row=row_idx, column=9, value=float(Decimal(str(inst.get("paid_amount") or 0))))
        ws.cell(row=row_idx, column=10, value=float(Decimal(str(inst.get("balance") or 0))))
        ws.cell(row=row_idx, column=11, value=_safe_str(inst.get("status", "PENDIENTE"))).alignment = Alignment(horizontal="center")
        ws.cell(row=row_idx, column=12, value=_safe_str(inst.get("notes") or ""))

        # Format number columns
        for c in range(3, 11):
            ws.cell(row=row_idx, column=c).number_format = "#,##0.00"

        for c in range(1, 13):
            ws.cell(row=row_idx, column=c).border = border_thin

    # Column widths
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            val_str = str(cell.value or "")
            if len(val_str) > max_len:
                max_len = len(val_str)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def parse_and_validate_debt_schedule_excel(file_bytes: bytes) -> Tuple[bool, str, List[Dict[str, Any]]]:
    """
    Parses an uploaded Excel file for debt installment schedule.
    Validates structure, dates, and amounts without formula injections.
    """
    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
        ws = wb.active
    except Exception as e:
        return False, f"El archivo no es un Excel válido: {str(e)}", []

    # Find the header row (look for 'N° Cuota' or 'Cuota' or 'Fecha Vencimiento')
    header_row_idx = None
    for r in range(1, 15):
        row_vals = [str(ws.cell(row=r, column=c).value or "").strip().lower() for c in range(1, 10)]
        if any("cuota" in v for v in row_vals) and any("vencimiento" in v for v in row_vals):
            header_row_idx = r
            break

    if not header_row_idx:
        return False, "No se encontró la fila de encabezados con 'N° Cuota' y 'Fecha Vencimiento'", []

    installments = []
    for r in range(header_row_idx + 1, ws.max_row + 1):
        num_raw = ws.cell(row=r, column=1).value
        date_raw = ws.cell(row=r, column=2).value

        if num_raw is None and date_raw is None:
            continue

        try:
            num = int(num_raw)
        except Exception:
            continue

        # Parse date
        if isinstance(date_raw, (datetime, date)):
            due_d = date_raw.strftime("%Y-%m-%d")
        else:
            d_str = str(date_raw or "").strip()
            if not d_str:
                return False, f"Fila {r}: Fecha de vencimiento vacía para la cuota #{num}", []
            try:
                due_d = datetime.strptime(d_str[:10], "%Y-%m-%d").strftime("%Y-%m-%d")
            except Exception:
                try:
                    due_d = datetime.strptime(d_str[:10], "%d/%m/%Y").strftime("%Y-%m-%d")
                except Exception:
                    return False, f"Fila {r}: Formato de fecha inválido '{d_str}' (usar YYYY-MM-DD o DD/MM/YYYY)", []

        def _get_dec(col_idx):
            v = ws.cell(row=r, column=col_idx).value
            if v is None:
                return Decimal("0.00")
            try:
                return Decimal(str(v).replace("$", "").replace(",", "").strip()).quantize(Decimal("0.01"))
            except Exception:
                return Decimal("0.00")

        cap = _get_dec(3)
        inte = _get_dec(4)
        fees = _get_dec(5)
        ins = _get_dec(6)
        oth = _get_dec(7)
        tot = _get_dec(8)

        if tot <= Decimal("0.00"):
            tot = cap + inte + fees + ins + oth

        if tot <= Decimal("0.00"):
            return False, f"Fila {r}: El monto total de la cuota #{num} debe ser mayor a cero", []

        notes = str(ws.cell(row=r, column=12).value or "").strip()

        installments.append({
            "installment_number": num,
            "due_date": due_d,
            "capital": cap,
            "interest": inte,
            "fees": fees,
            "insurance": ins,
            "other_charges": oth,
            "total_amount": tot,
            "notes": notes,
        })

    if not installments:
        return False, "No se encontraron filas de cuotas válidas en el archivo", []

    # Sort by installment number
    installments.sort(key=lambda x: x["installment_number"])
    return True, f"Se validaron {len(installments)} cuotas correctamente", installments
