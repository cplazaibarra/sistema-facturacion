"""
services/products_excel_service.py
Servicio centralizado y fuente única de la verdad para:
- Definición de columnas de productos en Excel.
- Generación de plantilla vacía con ejemplos.
- Exportación del catálogo completo o filtrado.
- Parseo, normalización, validación y diffing para importación de productos.
- Salvaguarda de datos transaccionales (Stock y PPP marcados estrictamente como SOLO LECTURA).
"""

import io
import math
from datetime import datetime, timezone
import openpyxl
import uuid
import time
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# Almacenamiento temporal en base de datos para previews de importación Excel (soporta multi-worker Gunicorn)
_PREVIEW_EXPIRATION_SECONDS = 1800  # 30 minutos

def _clean_expired_previews(conn):
    """Elimina registros expirados de manera proactiva sin bloquear."""
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM excel_import_previews WHERE expires_at < CURRENT_TIMESTAMP")
    except Exception:
        pass

def store_preview_cache(user_id: int | str, items: list, summary: dict) -> str:
    """Almacena el preview en PostgreSQL asociado a un import_id criptográfico y al usuario."""
    import json
    from datetime import timedelta
    from db import get_connection

    import_id = str(uuid.uuid4())
    user_str = str(user_id)

    with get_connection() as conn:
        _clean_expired_previews(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO excel_import_previews (import_id, user_id, items, summary, expires_at)
                VALUES (%s, %s, %s::jsonb, %s::jsonb, CURRENT_TIMESTAMP + INTERVAL '%s seconds')
                """,
                (
                    import_id,
                    user_str,
                    json.dumps(items, ensure_ascii=False),
                    json.dumps(summary, ensure_ascii=False),
                    _PREVIEW_EXPIRATION_SECONDS
                )
            )
        conn.commit()

    return import_id

def pop_preview_cache(import_id: str, user_id: int | str) -> dict | None:
    """Recupera y remueve de forma atómica de un solo uso (single-use) el preview validando ownership y expiración en PostgreSQL."""
    import json
    from db import get_connection

    if not import_id:
        return None

    try:
        val_uuid = str(uuid.UUID(str(import_id).strip()))
    except (ValueError, AttributeError):
        return None

    user_str = str(user_id)

    with get_connection() as conn:
        _clean_expired_previews(conn)
        with conn.cursor() as cur:
            # Atómicamente recuperamos y eliminamos SOLO si coincide el import_id, user_id y NO ha expirado
            cur.execute(
                """
                DELETE FROM excel_import_previews
                WHERE import_id = %s
                  AND user_id = %s
                  AND expires_at >= CURRENT_TIMESTAMP
                RETURNING items, summary, created_at
                """,
                (val_uuid, user_str)
            )
            row = cur.fetchone()
        conn.commit()

    if not row:
        return None

    items = row["items"] if isinstance(row["items"], list) else json.loads(row["items"])
    summary = row["summary"] if isinstance(row["summary"], dict) else json.loads(row["summary"])

    return {
        "user_id": user_str,
        "items": items,
        "summary": summary
    }

# Definición única de esquema de columnas
# key: clave interna en BD / diccionario
# header: etiqueta exacta en la fila 1 de Excel
# width: ancho de columna sugerido
# readonly: si es True, se exporta como informativo y se ignora al importar
# required: obligatorio para crear producto
# data_type: 'int', 'float', 'str', 'bool'
PRODUCT_EXCEL_COLUMNS = [
    {
        "key": "id",
        "header": "ID",
        "width": 10,
        "readonly": False,
        "required": False,
        "data_type": "int",
        "description": "ID interno (opcional para nuevos, referencial para existentes)",
    },
    {
        "key": "sku",
        "header": "SKU",
        "width": 18,
        "readonly": False,
        "required": True,
        "data_type": "str",
        "description": "Código SKU único de negocio (Obligatorio)",
    },
    {
        "key": "name",
        "header": "Nombre del Producto",
        "width": 32,
        "readonly": False,
        "required": True,
        "data_type": "str",
        "description": "Nombre comercial del producto (Obligatorio)",
    },
    {
        "key": "product_type",
        "header": "Tipo de Producto",
        "width": 22,
        "readonly": False,
        "required": False,
        "data_type": "str",
        "description": "Producto Terminado, Insumo o Servicio",
    },
    {
        "key": "category",
        "header": "Categoría",
        "width": 18,
        "readonly": False,
        "required": False,
        "data_type": "str",
        "description": "Categoría de inventario (ej. Miel, Envases)",
    },
    {
        "key": "subcategory_material",
        "header": "Subcategoría / Material",
        "width": 24,
        "readonly": False,
        "required": False,
        "data_type": "str",
        "description": "Material o subtipo (ej. Vidrio, PET, Miel Cruda)",
    },
    {
        "key": "line",
        "header": "Línea",
        "width": 18,
        "readonly": False,
        "required": False,
        "data_type": "str",
        "description": "Línea comercial (ej. Clásica, Selva Valdiviana)",
    },
    {
        "key": "variety",
        "header": "Variedad",
        "width": 18,
        "readonly": False,
        "required": False,
        "data_type": "str",
        "description": "Variedad floral (ej. Ulmo, Multiflora, Tiaca)",
    },
    {
        "key": "format_capacity",
        "header": "Formato o Capacidad",
        "width": 20,
        "readonly": False,
        "required": False,
        "data_type": "str",
        "description": "Formato (ej. 500 g, 1 Kg, Tineta)",
    },
    {
        "key": "associated_kg",
        "header": "Kilos Asociados (Kg)",
        "width": 20,
        "readonly": False,
        "required": False,
        "data_type": "float",
        "description": "Kilos netos equivalentes",
    },
    {
        "key": "unit_of_measure",
        "header": "Unidad de Medida",
        "width": 18,
        "readonly": False,
        "required": False,
        "data_type": "str",
        "description": "UN, KG, LT, MT o Viaje (default UN)",
    },
    {
        "key": "cost",
        "header": "Costo Unitario ($)",
        "width": 18,
        "readonly": False,
        "required": False,
        "data_type": "float",
        "description": "Costo maestro base",
    },
    {
        "key": "min_stock",
        "header": "Stock Mínimo",
        "width": 16,
        "readonly": False,
        "required": False,
        "data_type": "float",
        "description": "Nivel de stock mínimo de alerta",
    },
    {
        "key": "internal_code",
        "header": "Código Interno",
        "width": 18,
        "readonly": False,
        "required": False,
        "data_type": "str",
        "description": "Código interno legacy",
    },
    {
        "key": "barcode",
        "header": "Código de Barra",
        "width": 18,
        "readonly": False,
        "required": False,
        "data_type": "str",
        "description": "Código EAN / barras",
    },
    {
        "key": "bom_recipe",
        "header": "Receta BOM",
        "width": 18,
        "readonly": False,
        "required": False,
        "data_type": "str",
        "description": "Código de receta asociada",
    },
    {
        "key": "labeling",
        "header": "Etiquetado",
        "width": 16,
        "readonly": False,
        "required": False,
        "data_type": "str",
        "description": "Nuevo, Antiguo o N/A",
    },
    {
        "key": "requires_lot",
        "header": "Requiere Lote",
        "width": 16,
        "readonly": False,
        "required": False,
        "data_type": "bool",
        "description": "SÍ o NO (obligatoriedad en bodega)",
    },
    {
        "key": "status",
        "header": "Estado",
        "width": 18,
        "readonly": False,
        "required": False,
        "data_type": "str",
        "description": "Activo, Inactivo, etc.",
    },
    {
        "key": "description",
        "header": "Descripción",
        "width": 30,
        "readonly": False,
        "required": False,
        "data_type": "str",
        "description": "Descripción general",
    },
    {
        "key": "notes",
        "header": "Observaciones",
        "width": 30,
        "readonly": False,
        "required": False,
        "data_type": "str",
        "description": "Notas internas y trazabilidad",
    },
    # Columnas informativas de solo lectura (Kardex / Existencias)
    {
        "key": "current_stock",
        "header": "Stock Actual (Solo Lectura)",
        "width": 26,
        "readonly": True,
        "required": False,
        "data_type": "float",
        "description": "Informativo. No se modifica mediante importación.",
    },
    {
        "key": "ppp_cost",
        "header": "Costo PPP (Solo Lectura)",
        "width": 24,
        "readonly": True,
        "required": False,
        "data_type": "float",
        "description": "Informativo. Costo Promedio Ponderado del Kardex.",
    },
]

# Mapa de encabezados a especificación de columna
HEADER_TO_SPEC = {col["header"].strip().lower(): col for col in PRODUCT_EXCEL_COLUMNS}
KEY_TO_SPEC = {col["key"]: col for col in PRODUCT_EXCEL_COLUMNS}


def parse_flexible_float(val) -> float | None:
    """Convierte de forma segura números, strings con coma decimal o punto decimal a float."""
    if val is None or val == "":
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().replace("$", "").strip()
    if not s:
        return None
    if "." in s and "," in s:
        if s.rfind(",") > s.rfind("."):  # Ej: 1.250,50
            s = s.replace(".", "").replace(",", ".")
        else:  # Ej: 1,250.50
            s = s.replace(",", "")
    elif "," in s:  # Ej: 1250,50 o 0,5
        s = s.replace(",", ".")
    return float(s)


def _get_styles():
    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    readonly_fill = PatternFill(start_color="475569", end_color="475569", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    
    thin_border = Border(
        left=Side(style="thin", color="E2E8F0"),
        right=Side(style="thin", color="E2E8F0"),
        top=Side(style="thin", color="E2E8F0"),
        bottom=Side(style="thin", color="E2E8F0")
    )
    return header_fill, readonly_fill, header_font, thin_border


def generate_products_excel(products: list[dict], is_template: bool = False) -> io.BytesIO:
    """
    Genera un archivo Excel (.xlsx) con el formato unificado oficial.
    - is_template=True: Genera plantilla vacía con 2 filas de ejemplo.
    - is_template=False: Exporta el catálogo con los productos suministrados.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Plantilla Productos" if is_template else "Catálogo Productos"
    ws.views.sheetView[0].showGridLines = True

    header_fill, readonly_fill, header_font, thin_border = _get_styles()

    # 1. Escribir Encabezados
    for col_idx, col in enumerate(PRODUCT_EXCEL_COLUMNS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=col["header"])
        cell.font = header_font
        cell.fill = readonly_fill if col["readonly"] else header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border
        col_letter = get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = col["width"]

    ws.row_dimensions[1].height = 28

    # 2. Filas de datos
    data_rows = []
    if is_template:
        # 2 filas de ejemplo
        data_rows = [
            {
                "id": "",
                "sku": "MIE-500-001",
                "name": "Miel Ulmo 500g",
                "product_type": "Producto Terminado",
                "category": "Miel",
                "subcategory_material": "Vidrio",
                "line": "Clásica",
                "variety": "Ulmo",
                "format_capacity": "500 g",
                "associated_kg": 0.5,
                "unit_of_measure": "UN",
                "cost": 2500,
                "min_stock": 20,
                "internal_code": "ULM-500",
                "barcode": "7801234567890",
                "bom_recipe": "REC-ULM-500",
                "labeling": "Nuevo",
                "requires_lot": True,
                "status": "Activo",
                "description": "Miel pura de ulmo en frasco de vidrio 500g",
                "notes": "Almacenar en lugar fresco",
                "current_stock": "",
                "ppp_cost": ""
            },
            {
                "id": "",
                "sku": "INS-ENV-001",
                "name": "Frasco Vidrio Hexagonal 500g",
                "product_type": "Insumo",
                "category": "Envases",
                "subcategory_material": "Vidrio",
                "line": "",
                "variety": "",
                "format_capacity": "500 g",
                "associated_kg": 0.0,
                "unit_of_measure": "UN",
                "cost": 450,
                "min_stock": 500,
                "internal_code": "ENV-HEX-500",
                "barcode": "",
                "bom_recipe": "",
                "labeling": "N/A",
                "requires_lot": False,
                "status": "Activo",
                "description": "Frasco de vidrio para miel con tapa twist off",
                "notes": "",
                "current_stock": "",
                "ppp_cost": ""
            }
        ]
    else:
        data_rows = products

    for row_idx, p in enumerate(data_rows, start=2):
        ws.row_dimensions[row_idx].height = 20
        for col_idx, col in enumerate(PRODUCT_EXCEL_COLUMNS, start=1):
            k = col["key"]
            val = p.get(k)
            
            # Formateos específicos
            if k == "requires_lot":
                if val is True or str(val).strip().lower() in ("true", "1", "sí", "si"):
                    cell_val = "SÍ"
                else:
                    cell_val = "NO"
            elif col["data_type"] == "float" and val is not None:
                try:
                    cell_val = float(val)
                except (ValueError, TypeError):
                    cell_val = val
            elif col["data_type"] == "int" and val is not None and val != "":
                try:
                    cell_val = int(val)
                except (ValueError, TypeError):
                    cell_val = val
            else:
                raw_str = "" if val is None else str(val)
                # Mitigación Formula Injection (DDE): si un texto comienza con =, +, -, @, escapar con '
                if raw_str and raw_str[0] in ("=", "+", "-", "@"):
                    cell_val = f"'{raw_str}"
                else:
                    cell_val = raw_str

            cell = ws.cell(row=row_idx, column=col_idx, value=cell_val)
            cell.border = thin_border
            
            # Alineación según tipo
            if col["data_type"] in ("float", "int"):
                cell.alignment = Alignment(horizontal="right", vertical="center")
            elif k in ("sku", "requires_lot", "unit_of_measure", "status", "id"):
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output


def parse_and_validate_products_excel(file_stream, current_products_dict_by_sku: dict, current_products_dict_by_id: dict) -> dict:
    """
    Lee un archivo Excel subido por el usuario, valida la estructura y compara con
    los productos actuales para clasificar cada fila en:
    - NUEVO
    - MODIFICADO (con detalle de diferencias campo por campo)
    - SIN CAMBIOS
    - ERROR
    """
    try:
        wb = openpyxl.load_workbook(file_stream, data_only=True)
    except Exception as e:
        return {
            "success": False,
            "error": f"El archivo proporcionado no es un archivo Excel (.xlsx) válido: {str(e)}",
            "items": [],
            "summary": {"total": 0, "new": 0, "modified": 0, "unchanged": 0, "error": 1}
        }

    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows or len(rows) < 1:
        return {
            "success": False,
            "error": "La hoja de cálculo está completamente vacía.",
            "items": [],
            "summary": {"total": 0, "new": 0, "modified": 0, "unchanged": 0, "error": 0}
        }

    header_row = rows[0]
    col_mapping = {}  # index in row -> spec
    found_headers = []
    
    for idx, cell_value in enumerate(header_row):
        if cell_value is None:
            continue
        h_clean = str(cell_value).strip().lower()
        found_headers.append(h_clean)
        if h_clean in HEADER_TO_SPEC:
            col_mapping[idx] = HEADER_TO_SPEC[h_clean]

    # Validar que al menos existan columnas indispensables: SKU y Nombre
    has_sku = any(spec["key"] == "sku" for spec in col_mapping.values())
    has_name = any(spec["key"] == "name" for spec in col_mapping.values())

    if not has_sku or not has_name:
        return {
            "success": False,
            "error": "El archivo no contiene las columnas requeridas 'SKU' y 'Nombre del Producto'. Por favor descargue la plantilla oficial.",
            "items": [],
            "summary": {"total": 0, "new": 0, "modified": 0, "unchanged": 0, "error": 0}
        }

    items_result = []
    seen_skus_in_file = set()

    for row_num, row_data in enumerate(rows[1:], start=2):
        # Omitir filas totalmente vacías
        if not row_data or all(v is None or str(v).strip() == "" for v in row_data):
            continue

        raw_row = {}
        for col_idx, spec in col_mapping.items():
            val = row_data[col_idx] if col_idx < len(row_data) else None
            raw_row[spec["key"]] = val

        item_analysis = _analyze_product_row(
            row_num=row_num,
            row_data=raw_row,
            by_sku=current_products_dict_by_sku,
            by_id=current_products_dict_by_id,
            seen_skus=seen_skus_in_file
        )
        items_result.append(item_analysis)

    summary = {
        "total": len(items_result),
        "total_rows": len(items_result),
        "new": sum(1 for it in items_result if it["action"] == "NUEVO"),
        "nuevos": sum(1 for it in items_result if it["action"] == "NUEVO"),
        "modified": sum(1 for it in items_result if it["action"] == "MODIFICADO"),
        "modificados": sum(1 for it in items_result if it["action"] == "MODIFICADO"),
        "unchanged": sum(1 for it in items_result if it["action"] in ("SIN CAMBIOS", "SIN_CAMBIOS")),
        "sin_cambios": sum(1 for it in items_result if it["action"] in ("SIN CAMBIOS", "SIN_CAMBIOS")),
        "error": sum(1 for it in items_result if it["action"] == "ERROR"),
        "errores": sum(1 for it in items_result if it["action"] == "ERROR"),
    }

    return {
        "success": True,
        "items": items_result,
        "summary": summary
    }


def _analyze_product_row(row_num: int, row_data: dict, by_sku: dict, by_id: dict, seen_skus: set) -> dict:
    """Clasifica una fila individual del Excel y genera diffing."""
    sku_val = str(row_data.get("sku") or "").strip()
    name_val = str(row_data.get("name") or "").strip()
    id_val_raw = row_data.get("id")

    errors = []

    # Validar SKU
    if not sku_val:
        errors.append("El campo SKU es obligatorio y no puede estar vacío.")
    else:
        if sku_val.lower() in seen_skus:
            errors.append(f"El SKU '{sku_val}' aparece duplicado en el mismo archivo Excel.")
        seen_skus.add(sku_val.lower())

    # Validar Nombre
    if not name_val:
        errors.append("El campo Nombre del Producto es obligatorio.")

    # Validar tipos numéricos maestros
    cost_val = 0.0
    if row_data.get("cost") not in (None, ""):
        parsed_c = parse_flexible_float(row_data["cost"])
        if parsed_c is None:
            errors.append(f"El valor de Costo '{row_data.get('cost')}' no es numérico.")
        elif parsed_c < 0:
            errors.append("El costo no puede ser negativo.")
        else:
            cost_val = parsed_c

    min_stock_val = 0.0
    if row_data.get("min_stock") not in (None, ""):
        parsed_ms = parse_flexible_float(row_data["min_stock"])
        if parsed_ms is None:
            errors.append(f"El valor de Stock Mínimo '{row_data.get('min_stock')}' no es numérico.")
        elif parsed_ms < 0:
            errors.append("El stock mínimo no puede ser negativo.")
        else:
            min_stock_val = parsed_ms

    associated_kg_val = None
    if row_data.get("associated_kg") not in (None, ""):
        parsed_ak = parse_flexible_float(row_data["associated_kg"])
        if parsed_ak is None:
            errors.append(f"El valor de Kilos Asociados '{row_data.get('associated_kg')}' no es numérico.")
        elif parsed_ak < 0:
            errors.append("Los kilos asociados no pueden ser negativos.")
        else:
            associated_kg_val = parsed_ak

    # Parsear requires_lot
    req_lot_raw = str(row_data.get("requires_lot") or "").strip().lower()
    requires_lot = True if req_lot_raw in ("sí", "si", "true", "1", "yes", "s") else False

    # Validar ID técnico y SKU de negocio
    target_existing_product = None
    target_by_id = None
    target_by_sku = None

    if id_val_raw not in (None, ""):
        try:
            target_id = int(id_val_raw)
            target_by_id = by_id.get(target_id)
            if not target_by_id:
                errors.append(f"El ID {target_id} no corresponde a ningún producto registrado.")
        except (ValueError, TypeError):
            errors.append(f"El ID '{id_val_raw}' no es un número entero válido.")

    if sku_val:
        target_by_sku = by_sku.get(sku_val.lower())

    # Regla de Consistencia de Identidad:
    # 1. Si vienen tanto ID como SKU:
    if target_by_id and target_by_sku:
        if target_by_id["id"] != target_by_sku["id"]:
            errors.append(
                f"Conflicto de identidad: El ID {target_by_id['id']} pertenece a '{target_by_id['sku']}', "
                f"pero el SKU ingresado '{sku_val}' pertenece a otro producto (ID {target_by_sku['id']})."
            )
        else:
            target_existing_product = target_by_id
    elif target_by_id and not target_by_sku:
        # El ID existe, pero el SKU cambió a uno que NO existe en BD -> Permite renombrar SKU de este producto
        target_existing_product = target_by_id
    elif not target_by_id and target_by_sku:
        if id_val_raw not in (None, ""):
            # Traía un ID inválido/inexistente pero el SKU ya existe -> Conflicto
            errors.append(
                f"El SKU '{sku_val}' ya existe en el sistema (ID {target_by_sku['id']}), "
                f"pero el archivo especificó un ID diferente/inválido ({id_val_raw})."
            )
        else:
            # No traía ID, pero el SKU ya existe -> Actualizar por SKU
            target_existing_product = target_by_sku
    else:
        # Ni ID ni SKU existen -> Producto NUEVO (siempre que no haya traído un ID inexistente)
        if id_val_raw not in (None, ""):
            errors.append(f"No se puede crear un producto nuevo forzando un ID que no existe ({id_val_raw}).")
        target_existing_product = None

    # Si existe el producto previo, preservar sus valores exactos si en el Excel vienen vacíos
    if target_existing_product:
        clean_prod_type = str(row_data.get("product_type")).strip() if row_data.get("product_type") not in (None, "") else target_existing_product.get("product_type")
        clean_uom = str(row_data.get("unit_of_measure")).strip() if row_data.get("unit_of_measure") not in (None, "") else target_existing_product.get("unit_of_measure")
        clean_status = str(row_data.get("status")).strip() if row_data.get("status") not in (None, "") else target_existing_product.get("status")
        if row_data.get("cost") in (None, ""):
            cost_val = target_existing_product.get("cost")
        if row_data.get("min_stock") in (None, ""):
            min_stock_val = target_existing_product.get("min_stock")
        if row_data.get("associated_kg") in (None, ""):
            associated_kg_val = target_existing_product.get("associated_kg")
    else:
        clean_prod_type = str(row_data.get("product_type") or "Insumo").strip() or "Insumo"
        clean_uom = str(row_data.get("unit_of_measure") or "UN").strip() or "UN"
        clean_status = str(row_data.get("status") or "Activo").strip() or "Activo"

    clean_product_payload = {
        "sku": sku_val,
        "name": name_val,
        "product_type": clean_prod_type,
        "category": str(row_data.get("category") or (target_existing_product.get("category") if target_existing_product else "") or "").strip() or None,
        "subcategory_material": str(row_data.get("subcategory_material") or (target_existing_product.get("subcategory_material") if target_existing_product else "") or "").strip() or None,
        "line": str(row_data.get("line") or (target_existing_product.get("line") if target_existing_product else "") or "").strip() or None,
        "variety": str(row_data.get("variety") or (target_existing_product.get("variety") if target_existing_product else "") or "").strip() or None,
        "format_capacity": str(row_data.get("format_capacity") or (target_existing_product.get("format_capacity") if target_existing_product else "") or "").strip() or None,
        "associated_kg": associated_kg_val,
        "weight_kg": associated_kg_val,
        "unit_of_measure": clean_uom,
        "cost": float(cost_val or 0.0),
        "min_stock": float(min_stock_val or 0.0),
        "internal_code": str(row_data.get("internal_code") or (target_existing_product.get("internal_code") if target_existing_product else "") or "").strip() or None,
        "barcode": str(row_data.get("barcode") or (target_existing_product.get("barcode") if target_existing_product else "") or "").strip() or None,
        "bom_recipe": str(row_data.get("bom_recipe") or (target_existing_product.get("bom_recipe") if target_existing_product else "") or "").strip() or None,
        "labeling": str(row_data.get("labeling") or (target_existing_product.get("labeling") if target_existing_product else "") or "").strip() or None,
        "requires_lot": requires_lot if row_data.get("requires_lot") is not None else (bool(target_existing_product.get("requires_lot")) if target_existing_product else False),
        "status": clean_status,
        "description": str(row_data.get("description") or (target_existing_product.get("description") if target_existing_product else "") or "").strip() or None,
        "notes": str(row_data.get("notes") or (target_existing_product.get("notes") if target_existing_product else "") or "").strip() or None,
    }

    if errors:
        return {
            "row_num": row_num,
            "sku": sku_val or "(Sin SKU)",
            "name": name_val or "(Sin Nombre)",
            "action": "ERROR",
            "errors": errors,
            "changes": [],
            "payload": clean_product_payload,
            "target_id": None
        }

    # Si no existe -> NUEVO
    if not target_existing_product:
        return {
            "row_num": row_num,
            "sku": sku_val,
            "name": name_val,
            "action": "NUEVO",
            "errors": [],
            "changes": [
                {"field": "Registro", "old": "(No existe)", "new": "Nuevo producto a crear"}
            ],
            "payload": clean_product_payload,
            "target_id": None
        }

    # Si existe -> Comparar campos maestros para detectar MODIFICADO o SIN CAMBIOS
    target_id = target_existing_product["id"]
    changes = []

    fields_to_compare = [
        ("sku", "SKU"),
        ("name", "Nombre"),
        ("product_type", "Tipo de Producto"),
        ("category", "Categoría"),
        ("subcategory_material", "Subcategoría/Material"),
        ("line", "Línea"),
        ("variety", "Variedad"),
        ("format_capacity", "Formato"),
        ("associated_kg", "Kilos Asociados"),
        ("unit_of_measure", "Unidad de Medida"),
        ("cost", "Costo"),
        ("min_stock", "Stock Mínimo"),
        ("internal_code", "Código Interno"),
        ("barcode", "Código de Barra"),
        ("bom_recipe", "Receta BOM"),
        ("labeling", "Etiquetado"),
        ("requires_lot", "Requiere Lote"),
        ("status", "Estado"),
        ("description", "Descripción"),
        ("notes", "Observaciones"),
    ]

    for f_key, f_label in fields_to_compare:
        old_val = target_existing_product.get(f_key)
        new_val = clean_product_payload.get(f_key)

        # Normalización para comparación justa
        if f_key in ("cost", "min_stock", "associated_kg"):
            old_num = float(old_val or 0.0) if old_val is not None else (0.0 if f_key != "associated_kg" else None)
            new_num = float(new_val or 0.0) if new_val is not None else (0.0 if f_key != "associated_kg" else None)
            is_diff = False
            if old_num is None and new_num is None:
                is_diff = False
            elif old_num is None or new_num is None:
                is_diff = True
            elif not math.isclose(old_num, new_num, rel_tol=1e-7, abs_tol=1e-5):
                is_diff = True

            if is_diff:
                changes.append({
                    "key": f_key,
                    "field": f_label,
                    "label": f_label,
                    "old": f"{old_num:g}" if old_num is not None else "-",
                    "new": f"{new_num:g}" if new_num is not None else "-"
                })
        elif f_key == "requires_lot":
            old_bool = bool(old_val)
            new_bool = bool(new_val)
            if old_bool != new_bool:
                changes.append({
                    "key": f_key,
                    "field": f_label,
                    "label": f_label,
                    "old": "SÍ" if old_bool else "NO",
                    "new": "SÍ" if new_bool else "NO"
                })
        else:
            old_str = (str(old_val or "")).strip()
            new_str = (str(new_val or "")).strip()
            if old_str != new_str:
                changes.append({
                    "key": f_key,
                    "field": f_label,
                    "label": f_label,
                    "old": old_str or "(Vacío)",
                    "new": new_str or "(Vacío)"
                })

    if changes:
        return {
            "row_num": row_num,
            "sku": sku_val,
            "name": name_val,
            "action": "MODIFICADO",
            "errors": [],
            "changes": changes,
            "payload": clean_product_payload,
            "target_id": target_id
        }
    else:
        return {
            "row_num": row_num,
            "sku": sku_val,
            "name": name_val,
            "action": "SIN_CAMBIOS",
            "errors": [],
            "changes": [],
            "payload": clean_product_payload,
            "target_id": target_id
        }
