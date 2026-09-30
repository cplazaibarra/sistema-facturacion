"""
services/report_export_service.py
Generación y exportación de reportes financieros a Excel con openpyxl:
- Reporte Consolidado: Facturas de Compra y Gastos
- Reporte Operacional: Cuentas por Pagar
Formatos numéricos en moneda, encabezados congelados, auto-ancho de columnas,
autofiltro y mitigación de inyección de fórmulas.
"""

import io
from datetime import datetime
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from db import (
    get_purchases_and_expenses_report_data,
    get_accounts_payable_report_data,
    get_accounts_receivable_report_data,
)


def _safe_excel_str(val) -> str:
    """Escapa fórmulas maliciosas de Excel (DDE injection: =, +, -, @)."""
    if val is None:
        return ""
    s = str(val).strip()
    if s and s[0] in ("=", "+", "-", "@"):
        return f"'{s}"
    return s


def export_purchases_and_expenses_to_excel(filter_params: dict) -> io.BytesIO:
    """
    Exporta el reporte consolidado de Facturas de Compra y Gastos a un archivo Excel (.xlsx).
    Incluye TODOS los registros filtrados (no sólo la página actual).
    """
    data = get_purchases_and_expenses_report_data(
        date_from=filter_params.get("date_from"),
        date_to=filter_params.get("date_to"),
        doc_type=filter_params.get("doc_type"),
        supplier_beneficiary=filter_params.get("supplier_beneficiary"),
        category=filter_params.get("category"),
        payment_status=filter_params.get("payment_status"),
        search=filter_params.get("search"),
        page=1,
        per_page=None,
        sort_by=filter_params.get("sort_by", "date"),
        sort_order=filter_params.get("sort_order", "desc"),
    )

    items = data.get("all_filtered_items", [])
    metrics = data.get("metrics", {})

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Facturas y Gastos"
    ws.views.sheetView[0].showGridLines = True

    # Estilos
    font_title = Font(name="Calibri", size=14, bold=True, color="1E293B")
    font_subtitle = Font(name="Calibri", size=10, italic=True, color="64748B")
    font_kpi_label = Font(name="Calibri", size=9, bold=True, color="475569")
    font_kpi_value = Font(name="Calibri", size=11, bold=True, color="0F172A")
    font_header = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    font_data = Font(name="Calibri", size=10, color="1E293B")
    font_bold = Font(name="Calibri", size=10, bold=True, color="1E293B")

    fill_header = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")  # Azul corporativo oscuro
    fill_kpi = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
    fill_total = PatternFill(start_color="E2E8F0", end_color="E2E8F0", fill_type="solid")

    thin_border_side = Side(style="thin", color="CBD5E1")
    thin_border = Border(left=thin_border_side, right=thin_border_side, top=thin_border_side, bottom=thin_border_side)
    thick_bottom = Border(bottom=Side(style="medium", color="1E293B"), top=thin_border_side)

    # 1. Título y Subtítulo
    ws.merge_cells("A1:G1")
    ws["A1"] = "REPORTE CONSOLIDADO: FACTURAS DE COMPRA Y GASTOS"
    ws["A1"].font = font_title
    ws["A1"].alignment = Alignment(vertical="center")
    ws.row_dimensions[1].height = 24

    ws.merge_cells("A2:G2")
    ws["A2"] = f"Generado el: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Total Documentos: {metrics.get('total_documentos', 0)}"
    ws["A2"].font = font_subtitle
    ws["A2"].alignment = Alignment(vertical="center")
    ws.row_dimensions[2].height = 18

    # 2. Resumen KPI superior
    ws.row_dimensions[4].height = 18
    ws.row_dimensions[5].height = 22

    kpis = [
        ("Total Documentos", metrics.get("total_documentos", 0), "int", "A", "B"),
        ("Total Neto", metrics.get("total_neto", 0.0), "currency", "C", "D"),
        ("Total IVA", metrics.get("total_iva", 0.0), "currency", "E", "F"),
        ("Total General", metrics.get("total_general", 0.0), "currency", "G", "H"),
        ("Pendiente Pago", metrics.get("total_pendiente", 0.0), "currency", "I", "J"),
        ("Total Pagado", metrics.get("total_pagado", 0.0), "currency", "K", "L"),
    ]

    for label, val, val_type, col1, col2 in kpis:
        ws.merge_cells(f"{col1}4:{col2}4")
        ws.merge_cells(f"{col1}5:{col2}5")
        
        c_lbl = ws[f"{col1}4"]
        c_lbl.value = label
        c_lbl.font = font_kpi_label
        c_lbl.fill = fill_kpi
        c_lbl.alignment = Alignment(horizontal="center", vertical="center")
        
        c_val = ws[f"{col1}5"]
        c_val.value = val
        c_val.font = font_kpi_value
        c_val.fill = fill_kpi
        c_val.alignment = Alignment(horizontal="center", vertical="center")
        if val_type == "currency":
            c_val.number_format = '"$"#,##0'
        elif val_type == "int":
            c_val.number_format = '#,##0'

    # 3. Encabezados de tabla
    headers = [
        ("Fecha", 13, "center"),
        ("Vencimiento", 13, "center"),
        ("Tipo Origen", 20, "left"),
        ("N° Documento", 16, "left"),
        ("Proveedor / Beneficiario", 32, "left"),
        ("RUT", 15, "center"),
        ("Categoría", 22, "left"),
        ("Concepto / Glosa", 36, "left"),
        ("N° OC", 14, "center"),
        ("Total Neto ($)", 16, "right"),
        ("Total IVA ($)", 15, "right"),
        ("Total General ($)", 17, "right"),
        ("Monto Pagado ($)", 16, "right"),
        ("Saldo Pendiente ($)", 17, "right"),
        ("Estado Pago", 15, "center"),
        ("Fecha Pago", 13, "center"),
        ("Medio Pago", 18, "left"),
        ("Banco Egreso", 20, "left"),
    ]

    header_row = 7
    ws.row_dimensions[header_row].height = 26

    for col_idx, (h_title, width, align) in enumerate(headers, start=1):
        cell = ws.cell(row=header_row, column=col_idx, value=h_title)
        cell.font = font_header
        cell.fill = fill_header
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border
        col_letter = get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = width

    # 4. Filas de Datos
    curr_row = header_row + 1
    for it in items:
        ws.row_dimensions[curr_row].height = 20
        row_vals = [
            (it.get("doc_date") or "", "center", "str"),
            (it.get("due_date") or "", "center", "str"),
            (_safe_excel_str(it.get("origin_type")), "left", "str"),
            (_safe_excel_str(it.get("doc_number")), "left", "str"),
            (_safe_excel_str(it.get("party_name")), "left", "str"),
            (_safe_excel_str(it.get("party_rut")), "center", "str"),
            (_safe_excel_str(it.get("category_name")), "left", "str"),
            (_safe_excel_str(it.get("description")), "left", "str"),
            (_safe_excel_str(it.get("oc_number")), "center", "str"),
            (it.get("neto") or 0.0, "right", "currency"),
            (it.get("iva") or 0.0, "right", "currency"),
            (it.get("total") or 0.0, "right", "currency"),
            (it.get("paid_amount") or 0.0, "right", "currency"),
            (it.get("pending_amount") or 0.0, "right", "currency"),
            (_safe_excel_str(it.get("payment_status")), "center", "str"),
            (it.get("payment_date") or "", "center", "str"),
            (_safe_excel_str(it.get("payment_method")), "left", "str"),
            (_safe_excel_str(it.get("bank_name")), "left", "str"),
        ]

        for col_idx, (val, align, vtype) in enumerate(row_vals, start=1):
            cell = ws.cell(row=curr_row, column=col_idx, value=val)
            cell.font = font_data
            cell.alignment = Alignment(horizontal=align, vertical="center")
            cell.border = thin_border
            if vtype == "currency":
                cell.number_format = '"$"#,##0'
        curr_row += 1

    # 5. Fila de Totales
    ws.row_dimensions[curr_row].height = 22
    ws.merge_cells(start_row=curr_row, start_column=1, end_row=curr_row, end_column=9)
    lbl_total = ws.cell(row=curr_row, column=1, value="TOTALES GENERALES")
    lbl_total.font = font_bold
    lbl_total.alignment = Alignment(horizontal="right", vertical="center")
    lbl_total.fill = fill_total

    for c in range(1, 10):
        ws.cell(row=curr_row, column=c).border = thick_bottom
        ws.cell(row=curr_row, column=c).fill = fill_total

    totals = [
        (10, metrics.get("total_neto", 0.0)),
        (11, metrics.get("total_iva", 0.0)),
        (12, metrics.get("total_general", 0.0)),
        (13, metrics.get("total_pagado", 0.0)),
        (14, metrics.get("total_pendiente", 0.0)),
    ]
    for col_idx, tot_val in totals:
        cell = ws.cell(row=curr_row, column=col_idx, value=tot_val)
        cell.font = font_bold
        cell.fill = fill_total
        cell.alignment = Alignment(horizontal="right", vertical="center")
        cell.border = thick_bottom
        cell.number_format = '"$"#,##0'

    for c in range(15, 19):
        cell = ws.cell(row=curr_row, column=c, value="")
        cell.fill = fill_total
        cell.border = thick_bottom

    # 6. Autofilter y Freeze Panes
    last_col_letter = get_column_letter(len(headers))
    ws.auto_filter.ref = f"A{header_row}:{last_col_letter}{curr_row - 1}"
    ws.freeze_panes = f"A{header_row + 1}"

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output


def export_accounts_payable_to_excel(filter_params: dict) -> io.BytesIO:
    """
    Exporta el reporte operacional de CUENTAS POR PAGAR a un archivo Excel (.xlsx).
    Muestra exclusivamente obligaciones con Saldo Pendiente > 0.
    """
    data = get_accounts_payable_report_data(
        date_from=filter_params.get("date_from"),
        date_to=filter_params.get("date_to"),
        due_date_from=filter_params.get("due_date_from"),
        due_date_to=filter_params.get("due_date_to"),
        doc_type=filter_params.get("doc_type"),
        supplier_beneficiary=filter_params.get("supplier_beneficiary"),
        category=filter_params.get("category"),
        status=filter_params.get("status"),
        search=filter_params.get("search"),
        page=1,
        per_page=None,
        sort_by=filter_params.get("sort_by", "due_date"),
        sort_order=filter_params.get("sort_order", "asc"),
    )

    items = data.get("all_filtered_items", [])
    metrics = data.get("metrics", {})

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Cuentas por Pagar"
    ws.views.sheetView[0].showGridLines = True

    # Estilos
    font_title = Font(name="Calibri", size=14, bold=True, color="1E293B")
    font_subtitle = Font(name="Calibri", size=10, italic=True, color="64748B")
    font_kpi_label = Font(name="Calibri", size=9, bold=True, color="475569")
    font_kpi_value = Font(name="Calibri", size=11, bold=True, color="0F172A")
    font_header = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    font_data = Font(name="Calibri", size=10, color="1E293B")
    font_bold = Font(name="Calibri", size=10, bold=True, color="1E293B")

    fill_header = PatternFill(start_color="991B1B", end_color="991B1B", fill_type="solid")  # Rojo sobrio
    fill_kpi = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
    fill_total = PatternFill(start_color="E2E8F0", end_color="E2E8F0", fill_type="solid")

    thin_border_side = Side(style="thin", color="CBD5E1")
    thin_border = Border(left=thin_border_side, right=thin_border_side, top=thin_border_side, bottom=thin_border_side)
    thick_bottom = Border(bottom=Side(style="medium", color="1E293B"), top=thin_border_side)

    # 1. Título y Subtítulo
    ws.merge_cells("A1:G1")
    ws["A1"] = "REPORTE OPERACIONAL: CUENTAS POR PAGAR (OBLIGACIONES ACTIVAS)"
    ws["A1"].font = font_title
    ws["A1"].alignment = Alignment(vertical="center")
    ws.row_dimensions[1].height = 24

    ws.merge_cells("A2:G2")
    ws["A2"] = f"Generado el: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Obligaciones pendientes: {metrics.get('count_obligaciones', 0)}"
    ws["A2"].font = font_subtitle
    ws["A2"].alignment = Alignment(vertical="center")
    ws.row_dimensions[2].height = 18

    # 2. Resumen KPI superior (calculados estrictamente sobre Saldo Pendiente)
    ws.row_dimensions[4].height = 18
    ws.row_dimensions[5].height = 22

    kpis = [
        ("Total Por Pagar", metrics.get("total_por_pagar", 0.0), "currency", "A", "C"),
        ("Total Vencido", metrics.get("total_vencido", 0.0), "currency", "D", "F"),
        ("Vence Próx. 7 Días", metrics.get("vence_7_dias", 0.0), "currency", "G", "I"),
        ("Vence Próx. 30 Días", metrics.get("vence_30_dias", 0.0), "currency", "J", "L"),
    ]

    for label, val, val_type, col1, col2 in kpis:
        ws.merge_cells(f"{col1}4:{col2}4")
        ws.merge_cells(f"{col1}5:{col2}5")
        
        c_lbl = ws[f"{col1}4"]
        c_lbl.value = label
        c_lbl.font = font_kpi_label
        c_lbl.fill = fill_kpi
        c_lbl.alignment = Alignment(horizontal="center", vertical="center")
        
        c_val = ws[f"{col1}5"]
        c_val.value = val
        c_val.font = font_kpi_value
        c_val.fill = fill_kpi
        c_val.alignment = Alignment(horizontal="center", vertical="center")
        if val_type == "currency":
            c_val.number_format = '"$"#,##0'
        elif val_type == "int":
            c_val.number_format = '#,##0'

    # 3. Encabezados de tabla
    headers = [
        ("Vencimiento", 13, "center"),
        ("Días Venc.", 12, "center"),
        ("Fecha Doc.", 13, "center"),
        ("Tipo Obligación", 20, "left"),
        ("N° Documento", 16, "left"),
        ("Proveedor / Beneficiario", 32, "left"),
        ("RUT", 15, "center"),
        ("Categoría", 22, "left"),
        ("Concepto / Glosa", 34, "left"),
        ("N° OC", 14, "center"),
        ("Total Doc. ($)", 16, "right"),
        ("Total Pagado ($)", 16, "right"),
        ("Saldo Pendiente ($)", 18, "right"),
        ("Estado", 14, "center"),
    ]

    header_row = 7
    ws.row_dimensions[header_row].height = 26

    for col_idx, (h_title, width, align) in enumerate(headers, start=1):
        cell = ws.cell(row=header_row, column=col_idx, value=h_title)
        cell.font = font_header
        cell.fill = fill_header
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border
        col_letter = get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = width

    # 4. Filas de Datos
    curr_row = header_row + 1
    for it in items:
        ws.row_dimensions[curr_row].height = 20
        dias_val = it.get("dias_vencimiento")

        row_vals = [
            (it.get("due_date") or "", "center", "str"),
            (dias_val if dias_val is not None else "", "center", "int" if dias_val is not None else "str"),
            (it.get("doc_date") or "", "center", "str"),
            (_safe_excel_str(it.get("origin_type")), "left", "str"),
            (_safe_excel_str(it.get("doc_number")), "left", "str"),
            (_safe_excel_str(it.get("party_name")), "left", "str"),
            (_safe_excel_str(it.get("party_rut")), "center", "str"),
            (_safe_excel_str(it.get("category_name")), "left", "str"),
            (_safe_excel_str(it.get("description")), "left", "str"),
            (_safe_excel_str(it.get("oc_number")), "center", "str"),
            (it.get("total") or 0.0, "right", "currency"),
            (it.get("paid_amount") or 0.0, "right", "currency"),
            (it.get("pending_amount") or 0.0, "right", "currency"),
            (_safe_excel_str(it.get("computed_status")), "center", "str"),
        ]

        for col_idx, (val, align, vtype) in enumerate(row_vals, start=1):
            cell = ws.cell(row=curr_row, column=col_idx, value=val)
            cell.font = font_data
            cell.alignment = Alignment(horizontal=align, vertical="center")
            cell.border = thin_border
            if vtype == "currency":
                cell.number_format = '"$"#,##0'
            elif vtype == "int":
                cell.number_format = '#,##0'
        curr_row += 1

    # 5. Fila de Totales
    ws.row_dimensions[curr_row].height = 22
    ws.merge_cells(start_row=curr_row, start_column=1, end_row=curr_row, end_column=10)
    lbl_total = ws.cell(row=curr_row, column=1, value="TOTAL POR PAGAR CONSOLIDADO")
    lbl_total.font = font_bold
    lbl_total.alignment = Alignment(horizontal="right", vertical="center")
    lbl_total.fill = fill_total

    for c in range(1, 11):
        ws.cell(row=curr_row, column=c).border = thick_bottom
        ws.cell(row=curr_row, column=c).fill = fill_total

    tot_doc_sum = round(sum(it.get("total", 0.0) for it in items), 2)
    tot_pag_sum = round(sum(it.get("paid_amount", 0.0) for it in items), 2)
    tot_pen_sum = metrics.get("total_por_pagar", 0.0)

    cell_td = ws.cell(row=curr_row, column=11, value=tot_doc_sum)
    cell_td.font = font_bold
    cell_td.fill = fill_total
    cell_td.alignment = Alignment(horizontal="right", vertical="center")
    cell_td.border = thick_bottom
    cell_td.number_format = '"$"#,##0'

    cell_tp = ws.cell(row=curr_row, column=12, value=tot_pag_sum)
    cell_tp.font = font_bold
    cell_tp.fill = fill_total
    cell_tp.alignment = Alignment(horizontal="right", vertical="center")
    cell_tp.border = thick_bottom
    cell_tp.number_format = '"$"#,##0'

    cell_pen = ws.cell(row=curr_row, column=13, value=tot_pen_sum)
    cell_pen.font = font_bold
    cell_pen.fill = fill_total
    cell_pen.alignment = Alignment(horizontal="right", vertical="center")
    cell_pen.border = thick_bottom
    cell_pen.number_format = '"$"#,##0'

    cell_last = ws.cell(row=curr_row, column=14, value="")
    cell_last.fill = fill_total
    cell_last.border = thick_bottom

    # 6. Autofilter y Freeze Panes
    last_col_letter = get_column_letter(len(headers))
    ws.auto_filter.ref = f"A{header_row}:{last_col_letter}{curr_row - 1}"
    ws.freeze_panes = f"A{header_row + 1}"

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output


def export_accounts_receivable_to_excel(filter_params: dict) -> io.BytesIO:
    """
    Exporta el reporte operacional de CUENTAS POR COBRAR a un archivo Excel (.xlsx).
    Muestra exclusivamente ventas no canceladas con Saldo Pendiente > 0.
    """
    data = get_accounts_receivable_report_data(
        date_from=filter_params.get("date_from"),
        date_to=filter_params.get("date_to"),
        due_date_from=filter_params.get("due_date_from"),
        due_date_to=filter_params.get("due_date_to"),
        customer=filter_params.get("customer"),
        payment_status=filter_params.get("payment_status"),
        sale_status=filter_params.get("sale_status"),
        quick_filter=filter_params.get("quick_filter"),
        filter_gestion=filter_params.get("filter_gestion"),
        filter_antiguedad_gestion=filter_params.get("filter_antiguedad_gestion"),
        filter_tipo_gestion=filter_params.get("filter_tipo_gestion"),
        search=filter_params.get("search"),
        page=1,
        per_page=None,
        sort_by=filter_params.get("sort_by", "due_date"),
        sort_order=filter_params.get("sort_order", "asc"),
    )

    items = data.get("all_filtered_items", [])
    metrics = data.get("metrics", {})

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Cuentas por Cobrar"
    ws.views.sheetView[0].showGridLines = True

    # Estilos
    font_title = Font(name="Calibri", size=14, bold=True, color="1E293B")
    font_subtitle = Font(name="Calibri", size=10, italic=True, color="64748B")
    font_kpi_label = Font(name="Calibri", size=9, bold=True, color="475569")
    font_kpi_value = Font(name="Calibri", size=11, bold=True, color="0F172A")
    font_header = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    font_data = Font(name="Calibri", size=10, color="1E293B")
    font_bold = Font(name="Calibri", size=10, bold=True, color="1E293B")

    # Paleta azul corporativo para Cuentas por Cobrar
    fill_header = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    fill_kpi = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
    fill_total = PatternFill(start_color="E2E8F0", end_color="E2E8F0", fill_type="solid")

    thin_border_side = Side(style="thin", color="CBD5E1")
    thin_border = Border(left=thin_border_side, right=thin_border_side, top=thin_border_side, bottom=thin_border_side)
    thick_bottom = Border(bottom=Side(style="medium", color="1E293B"), top=thin_border_side)

    # 1. Título y Subtítulo
    ws.merge_cells("A1:G1")
    ws["A1"] = "REPORTE OPERACIONAL: CUENTAS POR COBRAR (CLIENTES Y COBRANZAS)"
    ws["A1"].font = font_title
    ws["A1"].alignment = Alignment(vertical="center")
    ws.row_dimensions[1].height = 24

    ws.merge_cells("A2:G2")
    ws["A2"] = f"Generado el: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Cuentas activas: {metrics.get('count_cuentas', 0)} | Clientes con deuda: {metrics.get('clientes_con_deuda', 0)}"
    ws["A2"].font = font_subtitle
    ws["A2"].alignment = Alignment(vertical="center")
    ws.row_dimensions[2].height = 18

    # 2. Resumen KPI superior (calculados estrictamente sobre Saldo Pendiente)
    ws.row_dimensions[4].height = 18
    ws.row_dimensions[5].height = 22

    kpis = [
        ("Total Por Cobrar", metrics.get("total_por_cobrar", 0.0), "currency", "A", "C"),
        ("Total Vencido", metrics.get("total_vencido", 0.0), "currency", "D", "F"),
        ("Vence Próx. 7 Días", metrics.get("vence_7_dias", 0.0), "currency", "G", "I"),
        ("Vence Próx. 30 Días", metrics.get("vence_30_dias", 0.0), "currency", "J", "L"),
        ("Clientes con Deuda", metrics.get("clientes_con_deuda", 0), "int", "M", "N"),
    ]

    for label, val, val_type, col1, col2 in kpis:
        ws.merge_cells(f"{col1}4:{col2}4")
        ws.merge_cells(f"{col1}5:{col2}5")
        
        c_lbl = ws[f"{col1}4"]
        c_lbl.value = label
        c_lbl.font = font_kpi_label
        c_lbl.fill = fill_kpi
        c_lbl.alignment = Alignment(horizontal="center", vertical="center")
        
        c_val = ws[f"{col1}5"]
        c_val.value = val
        c_val.font = font_kpi_value
        c_val.fill = fill_kpi
        c_val.alignment = Alignment(horizontal="center", vertical="center")
        if val_type == "currency":
            c_val.number_format = '"$"#,##0'
        elif val_type == "int":
            c_val.number_format = '#,##0'

    # 3. Encabezados de tabla
    headers = [
        ("Vencimiento", 13, "center"),
        ("Días Venc.", 12, "center"),
        ("Fecha Venta", 13, "center"),
        ("N° Venta", 14, "center"),
        ("Documento", 16, "left"),
        ("Cliente", 30, "left"),
        ("RUT", 15, "center"),
        ("Condición / Medio", 18, "left"),
        ("Total Venta ($)", 16, "right"),
        ("Total Pagado ($)", 16, "right"),
        ("Saldo por Cobrar ($)", 18, "right"),
        ("Último Pago", 13, "center"),
        ("Estado Pago", 14, "center"),
        ("Estado Venta", 16, "center"),
        ("Última Gestión", 15, "center"),
        ("Tipo Gestión", 16, "left"),
        ("Días sin Gestión", 15, "center"),
        ("Próxima Gestión", 15, "center"),
    ]

    header_row = 7
    ws.row_dimensions[header_row].height = 26

    for col_idx, (h_title, width, align) in enumerate(headers, start=1):
        cell = ws.cell(row=header_row, column=col_idx, value=h_title)
        cell.font = font_header
        cell.fill = fill_header
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border
        col_letter = get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = width

    # 4. Filas de Datos
    curr_row = header_row + 1
    for it in items:
        ws.row_dimensions[curr_row].height = 20
        dias_val = it.get("dias_vencimiento")
        dsg_val = it.get("dias_sin_gestion")

        row_vals = [
            (it.get("due_date") or "", "center", "str"),
            (dias_val if dias_val is not None else "", "center", "int" if dias_val is not None else "str"),
            (it.get("sale_date") or "", "center", "str"),
            (_safe_excel_str(it.get("sale_number")), "center", "str"),
            (_safe_excel_str(it.get("doc_number")), "left", "str"),
            (_safe_excel_str(it.get("customer_name")), "left", "str"),
            (_safe_excel_str(it.get("customer_rut")), "center", "str"),
            (_safe_excel_str(it.get("payment_method")), "left", "str"),
            (it.get("total_amount") or 0.0, "right", "currency"),
            (it.get("paid_amount") or 0.0, "right", "currency"),
            (it.get("pending_amount") or 0.0, "right", "currency"),
            (it.get("last_payment_date") or "", "center", "str"),
            (_safe_excel_str(it.get("computed_status")), "center", "str"),
            (_safe_excel_str(it.get("sale_status")), "center", "str"),
            (it.get("last_action_date") or "Sin gestión", "center", "str"),
            (_safe_excel_str(it.get("last_action_type")) if it.get("last_action_type") else "—", "left", "str"),
            (dsg_val if dsg_val is not None else "Sin gestión", "center", "int" if dsg_val is not None else "str"),
            (it.get("last_next_action_date") or "—", "center", "str"),
        ]

        for col_idx, (val, align, vtype) in enumerate(row_vals, start=1):
            cell = ws.cell(row=curr_row, column=col_idx, value=val)
            cell.font = font_data
            cell.alignment = Alignment(horizontal=align, vertical="center")
            cell.border = thin_border
            if vtype == "currency":
                cell.number_format = '"$"#,##0'
            elif vtype == "int":
                cell.number_format = '#,##0'
        curr_row += 1

    # 5. Fila de Totales
    ws.row_dimensions[curr_row].height = 22
    ws.merge_cells(start_row=curr_row, start_column=1, end_row=curr_row, end_column=8)
    lbl_total = ws.cell(row=curr_row, column=1, value="TOTAL POR COBRAR CONSOLIDADO")
    lbl_total.font = font_bold
    lbl_total.alignment = Alignment(horizontal="right", vertical="center")
    lbl_total.fill = fill_total

    for c in range(1, 9):
        ws.cell(row=curr_row, column=c).border = thick_bottom
        ws.cell(row=curr_row, column=c).fill = fill_total

    tot_venta_sum = round(sum(it.get("total_amount", 0.0) for it in items), 2)
    tot_pagado_sum = round(sum(it.get("paid_amount", 0.0) for it in items), 2)
    tot_cobrar_sum = metrics.get("total_por_cobrar", 0.0)

    cell_tv = ws.cell(row=curr_row, column=9, value=tot_venta_sum)
    cell_tv.font = font_bold
    cell_tv.fill = fill_total
    cell_tv.alignment = Alignment(horizontal="right", vertical="center")
    cell_tv.border = thick_bottom
    cell_tv.number_format = '"$"#,##0'

    cell_tp = ws.cell(row=curr_row, column=10, value=tot_pagado_sum)
    cell_tp.font = font_bold
    cell_tp.fill = fill_total
    cell_tp.alignment = Alignment(horizontal="right", vertical="center")
    cell_tp.border = thick_bottom
    cell_tp.number_format = '"$"#,##0'

    cell_tc = ws.cell(row=curr_row, column=11, value=tot_cobrar_sum)
    cell_tc.font = font_bold
    cell_tc.fill = fill_total
    cell_tc.alignment = Alignment(horizontal="right", vertical="center")
    cell_tc.border = thick_bottom
    cell_tc.number_format = '"$"#,##0'

    for c in range(12, len(headers) + 1):
        cell_last = ws.cell(row=curr_row, column=c, value="")
        cell_last.fill = fill_total
        cell_last.border = thick_bottom

    # 6. Autofilter y Freeze Panes
    last_col_letter = get_column_letter(len(headers))
    ws.auto_filter.ref = f"A{header_row}:{last_col_letter}{curr_row - 1}"
    ws.freeze_panes = f"A{header_row + 1}"

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output

