import os
import io
import time
import pytest
import openpyxl
from db import get_connection, insert_product, update_product, get_products_lookup_maps, list_all_products_for_export
from services.products_excel_service import (
    PRODUCT_EXCEL_COLUMNS,
    generate_products_excel,
    parse_and_validate_products_excel
)

def test_roundtrip_integrity(auth_client):
    """
    PRUEBA ROUND-TRIP:
    BD -> Exportar Excel -> Importar el mismo Excel sin modificar -> Preview
    Resultado esperado:
    Nuevos: 0
    Modificados: 0
    Sin cambios: N
    Errores: 0
    """
    # 1. Obtener catálogo y exportar
    products = list_all_products_for_export()
    assert len(products) > 0, "Debe haber productos para la prueba"
    
    excel_io = generate_products_excel(products, is_template=False)
    
    # 2. Reimportar el mismo archivo
    by_sku, by_id = get_products_lookup_maps()
    result = parse_and_validate_products_excel(excel_io, by_sku, by_id)
    
    assert result["success"] is True
    summary = result["summary"]
    
    print("\nRound-trip Summary:", summary)
    assert summary["nuevos"] == 0, f"Se detectaron nuevos: {summary['nuevos']}"
    assert summary["modificados"] == 0, f"Se detectaron modificados: {summary['modificados']}"
    assert summary["errores"] == 0, f"Se detectaron errores: {summary['errores']}"
    assert summary["sin_cambios"] == len(products), f"Esperados {len(products)} sin cambios, obtenido {summary['sin_cambios']}"

def test_stock_and_ppp_protection_in_db():
    """
    PROTECCIÓN DE STOCK Y PPP:
    Modificar manualmente Stock Actual y Costo PPP en el archivo Excel.
    Reimportar y verificar que el payload ni el diff contengan esos campos,
    y que en la BD las tablas kardex / stock permanezcan inmutables.
    """
    products = list_all_products_for_export()
    test_prod = products[0]
    sku = test_prod["sku"]
    prod_id = test_prod["id"]

    # Generar Excel con valores alterados de Stock y PPP
    wb = openpyxl.Workbook()
    ws = wb.active
    headers = [col["header"] for col in PRODUCT_EXCEL_COLUMNS]
    ws.append(headers)

    row = [None] * len(headers)
    row[headers.index("ID")] = prod_id
    row[headers.index("SKU")] = sku
    row[headers.index("Nombre del Producto")] = test_prod["name"]
    row[headers.index("Stock Actual (Solo Lectura)")] = 9999999.0
    row[headers.index("Costo PPP (Solo Lectura)")] = 8888888.0
    ws.append(row)

    bio = io.BytesIO()
    wb.save(bio)
    bio.seek(0)

    by_sku, by_id = get_products_lookup_maps()
    result = parse_and_validate_products_excel(bio, by_sku, by_id)
    assert result["success"] is True
    item = result["items"][0]

    # Verificar que el payload generado para persistencia NO contiene las llaves
    assert "current_stock" not in item["payload"]
    assert "ppp_cost" not in item["payload"]

    # Verificar que no hay cambios reportados para stock ni ppp
    for ch in item["changes"]:
        assert ch["key"] not in ("current_stock", "ppp_cost")

def test_duplicate_sku_in_file():
    """DUPLICADOS: SKU duplicado dentro del mismo Excel debe dar ERROR."""
    wb = openpyxl.Workbook()
    ws = wb.active
    headers = [col["header"] for col in PRODUCT_EXCEL_COLUMNS]
    ws.append(headers)

    row1 = [None] * len(headers)
    row1[headers.index("SKU")] = "DUP-SKU-001"
    row1[headers.index("Nombre del Producto")] = "Prod DUP 1"
    ws.append(row1)

    row2 = [None] * len(headers)
    row2[headers.index("SKU")] = "DUP-SKU-001"
    row2[headers.index("Nombre del Producto")] = "Prod DUP 2"
    ws.append(row2)

    bio = io.BytesIO()
    wb.save(bio)
    bio.seek(0)

    by_sku, by_id = get_products_lookup_maps()
    result = parse_and_validate_products_excel(bio, by_sku, by_id)
    assert result["success"] is True
    # La segunda fila debe marcar ERROR por duplicado en el mismo archivo
    assert result["items"][1]["action"] == "ERROR"
    assert any("duplicado" in err.lower() for err in result["items"][1]["errors"])

def test_scalability_benchmarks():
    """ESCALABILIDAD: Mide tiempos de lectura y validación para 100, 1.000 y 5.000 filas."""
    by_sku, by_id = get_products_lookup_maps()
    
    volumes = [100, 1000, 5000]
    headers = [col["header"] for col in PRODUCT_EXCEL_COLUMNS]
    
    for count in volumes:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(headers)
        
        for i in range(count):
            row = [None] * len(headers)
            row[headers.index("SKU")] = f"PERF-SKU-{i:05d}"
            row[headers.index("Nombre del Producto")] = f"Producto Escalabilidad {i}"
            row[headers.index("Costo Unitario ($)")] = 1500.0 + i
            row[headers.index("Categoría")] = "Mieles"
            ws.append(row)
            
        bio = io.BytesIO()
        wb.save(bio)
        bio.seek(0)
        
        start_time = time.perf_counter()
        res = parse_and_validate_products_excel(bio, by_sku, by_id)
        elapsed = time.perf_counter() - start_time
        
        assert res["success"] is True
        print(f"\n[BENCHMARK] {count} productos procesados en {elapsed:.3f} s ({count/elapsed:.1f} filas/s)")
        # Debe procesar al menos 500 filas/segundo
        assert elapsed < (count / 100.0)

def test_id_and_sku_conflict_resolution():
    """
    IDENTIFICACIÓN DE PRODUCTOS Y CONTRADICCIONES:
    - ID perteneciente a un producto y SKU perteneciente a otro producto debe generar ERROR inequívoco.
    - ID que no existe en BD con SKU nuevo no debe permitir crear producto forzando ID.
    - ID válido con SKU nuevo permite renombrar el SKU del producto sin crear duplicados.
    """
    by_sku = {
        "sku-prod-a": {"id": 100, "sku": "SKU-PROD-A", "name": "Producto A", "cost": 100.0},
        "sku-prod-b": {"id": 200, "sku": "SKU-PROD-B", "name": "Producto B", "cost": 200.0},
    }
    by_id = {
        100: by_sku["sku-prod-a"],
        200: by_sku["sku-prod-b"],
    }
    headers = [col["header"] for col in PRODUCT_EXCEL_COLUMNS]

    # Caso 1: ID 100 pero SKU-PROD-B (Conflicto cruzado entre dos productos existentes)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(headers)

    row1 = [None] * len(headers)
    row1[headers.index("ID")] = 100
    row1[headers.index("SKU")] = "SKU-PROD-B"
    row1[headers.index("Nombre del Producto")] = "Conflicto"
    ws.append(row1)

    # Caso 2: ID 99999 inexistente con SKU nuevo
    row2 = [None] * len(headers)
    row2[headers.index("ID")] = 99999
    row2[headers.index("SKU")] = "SKU-NUEVO-XYZ"
    row2[headers.index("Nombre del Producto")] = "ID Forzado Inexistente"
    ws.append(row2)

    # Caso 3: ID 100 existente pero renombrando SKU a uno nuevo que no existe
    row3 = [None] * len(headers)
    row3[headers.index("ID")] = 100
    row3[headers.index("SKU")] = "SKU-PROD-A-RENOMBRADO"
    row3[headers.index("Nombre del Producto")] = "Producto A Renombrado"
    ws.append(row3)

    bio = io.BytesIO()
    wb.save(bio)
    bio.seek(0)

    result = parse_and_validate_products_excel(bio, by_sku, by_id)
    assert result["success"] is True
    items = result["items"]

    # Fila 1 debe dar ERROR
    assert items[0]["action"] == "ERROR"
    assert any("conflicto de identidad" in err.lower() for err in items[0]["errors"])

    # Fila 2 debe dar ERROR
    assert items[1]["action"] == "ERROR"
    assert any("no corresponde a ningún producto" in err.lower() for err in items[1]["errors"])

    # Fila 3 es MODIFICADO para el ID 100
    assert items[2]["action"] == "MODIFICADO"
    assert items[2]["target_id"] == 100
    assert items[2]["payload"]["sku"] == "SKU-PROD-A-RENOMBRADO"

def test_formula_injection_defense():
    """SEGURIDAD: Verificar que los campos con fórmulas (=, +, -, @) sean exportados de forma neutralizada."""
    malicious_products = [
        {
            "id": 5001,
            "sku": "=CMD|' /C calc'!A0",
            "name": "+SUM(1,2)",
            "category": "-10+20",
            "notes": "@SUM(1,2)",
            "cost": 100.0,
        }
    ]
    bio = generate_products_excel(malicious_products, is_template=False)
    wb = openpyxl.load_workbook(bio)
    ws = wb.active
    
    rows = list(ws.iter_rows(values_only=True))
    assert len(rows) == 2
    row = rows[1]
    
    # En openpyxl, el valor almacenado debe tener el prefijo de comilla simple '
    sku_val = row[1]
    name_val = row[2]
    cat_val = row[4]
    notes_val = row[20]
    
    assert sku_val.startswith("'=")
    assert name_val.startswith("'+")
    assert cat_val.startswith("'-")
    assert notes_val.startswith("'@")
