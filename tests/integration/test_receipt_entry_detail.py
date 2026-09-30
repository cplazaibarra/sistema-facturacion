"""
tests/integration/test_receipt_entry_detail.py

Suite de validación para la consulta y modal interactivo de DETALLE DE ÚLTIMOS INGRESOS:
1. test_inventory_entry_detail_returns_received_items: Retorna exactamente los productos recibidos.
2. test_inventory_entry_detail_returns_actual_received_quantities: Retorna cantidades reales recibidas.
3. test_partial_receipts_are_not_mixed: Verifica que dos recepciones parciales de la misma OC (OC-TEST con A=100, B=50; Recepción 1 con A=40; Recepción 2 con A=60, B=50) no mezclen sus ítems ni cantidades.
4. test_inventory_entry_detail_correct_supplier: Retorna información correcta del proveedor.
5. test_inventory_entry_detail_correct_document: Muestra Guía de Despacho o Factura de Compra adecuadamente.
6. test_inventory_entry_detail_requires_authentication: 401 si no hay sesión activa.
7. test_inventory_entry_detail_respects_rbac: 403 para usuarios sin permisos de inventario/compras.
8. test_inventory_entry_detail_totals: Calcula correctamente Neto, IVA (19%) y Total.
"""

import pytest
import uuid
from datetime import datetime, timezone

from app import app
from core.database import get_connection
import repositories.products_repo as products_repo
import repositories.purchases_repo as purchases_repo
import repositories.inventory_repo as inventory_repo


@pytest.fixture
def app_client():
    old_csrf = app.config.get("WTF_CSRF_ENABLED", True)
    old_testing = app.config.get("TESTING", False)
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    try:
        with app.test_client() as client:
            yield client
    finally:
        app.config["WTF_CSRF_ENABLED"] = old_csrf
        app.config["TESTING"] = old_testing


def _login_as(client, role="admin"):
    with client.session_transaction() as sess:
        if role == "admin":
            sess["user_id"] = 1
            sess["username"] = "admin"
            sess["role_name"] = "Administrativo"
            sess["full_name"] = "Administrador Sistema"
            sess["permissions"] = {
                "dashboard": True, "ventas": True, "inventario": True,
                "productos": True, "reportes": True, "compras": True,
                "produccion": True, "trazabilidad": True, "administracion": True,
            }
        elif role == "operario":
            sess["user_id"] = 999
            sess["username"] = "operario_sin_permiso"
            sess["role_name"] = "Operario"
            sess["full_name"] = "Operario Test"
            sess["permissions"] = {
                "dashboard": False, "ventas": False, "inventario": False,
                "productos": False, "reportes": False, "compras": False,
            }


def _create_test_supplier():
    u = uuid.uuid4().hex[:6]
    import repositories.suppliers_repo as suppliers_repo
    s_id = suppliers_repo.insert_supplier({
        "name": f"Proveedor Test {u}",
        "phone": "+56911111111",
        "email": f"test_{u}@supplier.com",
        "default_payment_terms": "NET_30"
    })
    return s_id


def _create_test_product(sku_prefix="ITEM", cost=1000.0):
    u = uuid.uuid4().hex[:6]
    sku = f"{sku_prefix}-{u}"
    p_id = products_repo.create_product(
        sku=sku,
        name=f"Producto {sku}",
        category="Insumos",
        product_type="Insumo",
        cost=cost,
        requires_lot=False
    )
    return p_id, sku


def test_inventory_entry_detail_returns_received_items(app_client):
    """1. Retorna exactamente los productos recibidos en el ingreso."""
    _login_as(app_client, "admin")
    s_id = _create_test_supplier()
    p_id1, sku1 = _create_test_product("PROD1", 1500.0)
    p_id2, sku2 = _create_test_product("PROD2", 2000.0)

    # Crear OC con 2 productos
    items_oc = [
        {"product_id": p_id1, "quantity": 100, "unit_price": 1500.0},
        {"product_id": p_id2, "quantity": 50, "unit_price": 2000.0},
    ]
    oc_num = purchases_repo.create_purchase_order(s_id, "2026-09-18", "OC Test Detalle", items_oc)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM purchase_orders WHERE oc_number = %s", (oc_num,))
            po_id = cur.fetchone()["id"]

    # Registrar ingreso
    items_received = [
        {"product_id": p_id1, "quantity": 100, "unit_price": 1500.0, "lot_number": ""},
        {"product_id": p_id2, "quantity": 50, "unit_price": 2000.0, "lot_number": ""},
    ]
    entry_id = inventory_repo.register_inventory_entry(
        po_id,
        order_number=f"REC-{uuid.uuid4().hex[:6]}",
        entry_date="2026-09-18",
        warehouse="Almacén Principal",
        notes="Recepción completa",
        items=items_received,
        document_type="guia_despacho",
        document_number="GD-12345"
    )

    detail = inventory_repo.get_inventory_entry_detail(entry_id)
    assert detail is not None
    assert len(detail["items"]) == 2
    skus = [it["sku"] for it in detail["items"]]
    assert sku1 in skus
    assert sku2 in skus


def test_inventory_entry_detail_returns_actual_received_quantities(app_client):
    """2. Retorna las cantidades reales efectivamente recibidas."""
    _login_as(app_client, "admin")
    s_id = _create_test_supplier()
    p_id, sku = _create_test_product("CANT", 1200.0)

    items_oc = [{"product_id": p_id, "quantity": 80, "unit_price": 1200.0}]
    oc_num = purchases_repo.create_purchase_order(s_id, "2026-09-18", "OC Cant", items_oc)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM purchase_orders WHERE oc_number = %s", (oc_num,))
            po_id = cur.fetchone()["id"]

    # Recepción de 45 unidades (diferente a la cantidad pedida en la OC de 80)
    entry_id = inventory_repo.register_inventory_entry(
        po_id,
        order_number=f"REC-{uuid.uuid4().hex[:6]}",
        entry_date="2026-09-18",
        warehouse="Almacén Secundario",
        notes="Recepción parcial",
        items=[{"product_id": p_id, "quantity": 45, "unit_price": 1200.0, "lot_number": ""}],
        document_type="guia_despacho",
        document_number="GD-999"
    )

    detail = inventory_repo.get_inventory_entry_detail(entry_id)
    assert detail["total_quantity"] == 45
    assert detail["items"][0]["quantity"] == 45
    assert detail["items"][0]["quantity"] != 80


def test_partial_receipts_are_not_mixed(app_client):
    """
    3. TEST CRÍTICO: Recepciones parciales de una misma OC no se mezclan.
    OC-TEST: Producto A = 100, Producto B = 50
    Primera recepción: Producto A = 40
    Segunda recepción: Producto A = 60, Producto B = 50
    Verificar que:
    - Ingreso 1: contiene exclusivamente Producto A = 40
    - Ingreso 2: contiene exclusivamente Producto A = 60 y Producto B = 50
    """
    _login_as(app_client, "admin")
    s_id = _create_test_supplier()
    p_a, sku_a = _create_test_product("PART-A", 1000.0)
    p_b, sku_b = _create_test_product("PART-B", 2000.0)

    # OC con A=100 y B=50
    items_oc = [
        {"product_id": p_a, "quantity": 100, "unit_price": 1000.0},
        {"product_id": p_b, "quantity": 50, "unit_price": 2000.0},
    ]
    oc_num = purchases_repo.create_purchase_order(s_id, "2026-09-18", "OC Parciales Test", items_oc)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM purchase_orders WHERE oc_number = %s", (oc_num,))
            po_id = cur.fetchone()["id"]

    # Recepción 1: Solo Producto A = 40
    entry1_id = inventory_repo.register_inventory_entry(
        po_id,
        order_number=f"REC1-{uuid.uuid4().hex[:6]}",
        entry_date="2026-09-18",
        warehouse="Almacén Principal",
        notes="Primera entrega parcial",
        items=[{"product_id": p_a, "quantity": 40, "unit_price": 1000.0, "lot_number": "LOTE-A1"}],
        document_type="guia_despacho",
        document_number="GD-001"
    )

    # Recepción 2: Producto A = 60 y Producto B = 50
    entry2_id = inventory_repo.register_inventory_entry(
        po_id,
        order_number=f"REC2-{uuid.uuid4().hex[:6]}",
        entry_date="2026-09-19",
        warehouse="Almacén Principal",
        notes="Segunda entrega completando pedido",
        items=[
            {"product_id": p_a, "quantity": 60, "unit_price": 1000.0, "lot_number": "LOTE-A2"},
            {"product_id": p_b, "quantity": 50, "unit_price": 2000.0, "lot_number": "LOTE-B1"},
        ],
        document_type="factura",
        document_number="FAC-888"
    )

    # Consultar Ingreso 1
    d1 = inventory_repo.get_inventory_entry_detail(entry1_id)
    assert len(d1["items"]) == 1
    assert d1["items"][0]["sku"] == sku_a
    assert d1["items"][0]["quantity"] == 40
    assert d1["total_quantity"] == 40
    # No contiene Producto B
    assert not any(it["sku"] == sku_b for it in d1["items"])

    # Consultar Ingreso 2
    d2 = inventory_repo.get_inventory_entry_detail(entry2_id)
    assert len(d2["items"]) == 2
    d2_map = {it["sku"]: it["quantity"] for it in d2["items"]}
    assert d2_map[sku_a] == 60
    assert d2_map[sku_b] == 50
    assert d2["total_quantity"] == 110


def test_inventory_entry_detail_correct_supplier(app_client):
    """4. Retorna el proveedor exacto asociado al ingreso."""
    _login_as(app_client, "admin")
    s_id = _create_test_supplier()
    p_id, _ = _create_test_product("SUPP", 500.0)

    oc_num = purchases_repo.create_purchase_order(s_id, "2026-09-18", "OC Supp", [{"product_id": p_id, "quantity": 10, "unit_price": 500.0}])
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM purchase_orders WHERE oc_number = %s", (oc_num,))
            po_id = cur.fetchone()["id"]

    entry_id = inventory_repo.register_inventory_entry(
        po_id,
        order_number=f"REC-{uuid.uuid4().hex[:6]}",
        entry_date="2026-09-18",
        warehouse="Almacén Principal",
        notes="",
        items=[{"product_id": p_id, "quantity": 10, "unit_price": 500.0, "lot_number": ""}]
    )

    detail = inventory_repo.get_inventory_entry_detail(entry_id)
    assert detail["entry"]["supplier_id"] == s_id
    assert "Proveedor Test" in detail["entry"]["supplier_name"]


def test_inventory_entry_detail_correct_document(app_client):
    """5. Identifica y formatea correctamente Guía de Despacho y Factura."""
    _login_as(app_client, "admin")
    s_id = _create_test_supplier()
    p_id, _ = _create_test_product("DOC", 800.0)

    oc_num = purchases_repo.create_purchase_order(s_id, "2026-09-18", "OC Doc", [{"product_id": p_id, "quantity": 10, "unit_price": 800.0}])
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM purchase_orders WHERE oc_number = %s", (oc_num,))
            po_id = cur.fetchone()["id"]

    # Ingreso con Guía
    entry_guia = inventory_repo.register_inventory_entry(
        po_id,
        order_number=f"REC-G-{uuid.uuid4().hex[:6]}",
        entry_date="2026-09-18",
        warehouse="Almacén Principal",
        notes="",
        items=[{"product_id": p_id, "quantity": 5, "unit_price": 800.0, "lot_number": ""}],
        document_type="guia_despacho",
        document_number="12345"
    )
    d_guia = inventory_repo.get_inventory_entry_detail(entry_guia)
    assert "Guía de Despacho N° 12345" in d_guia["entry"]["document_label"]

    # Ingreso con Factura
    entry_fac = inventory_repo.register_inventory_entry(
        po_id,
        order_number=f"REC-F-{uuid.uuid4().hex[:6]}",
        entry_date="2026-09-18",
        warehouse="Almacén Principal",
        notes="",
        items=[{"product_id": p_id, "quantity": 5, "unit_price": 800.0, "lot_number": ""}],
        document_type="factura",
        document_number="98765"
    )
    d_fac = inventory_repo.get_inventory_entry_detail(entry_fac)
    assert "Factura de Compra N° 98765" in d_fac["entry"]["document_label"]


def test_inventory_entry_detail_requires_authentication(app_client):
    """6. Requiere autenticación (retorna 401 si no hay sesión activa)."""
    # Sin sesión de usuario
    res = app_client.get("/api/recepciones/1")
    assert res.status_code == 401


def test_inventory_entry_detail_respects_rbac(app_client):
    """7. Respeta RBAC (403 para usuarios sin permisos de inventario o compras)."""
    _login_as(app_client, "operario")
    res = app_client.get("/api/recepciones/1")
    assert res.status_code == 403


def test_inventory_entry_detail_totals(app_client):
    """
    8. Cálculo fiel de totales del ingreso:
    Ejemplo del requerimiento:
    Producto A = 100 un a $1.500 = $150.000
    Producto B =  50 un a $2.000 = $100.000
    Neto: $250.000
    IVA (19%): $47.500
    TOTAL: $297.500
    """
    _login_as(app_client, "admin")
    s_id = _create_test_supplier()
    p_a, _ = _create_test_product("TOTA", 1500.0)
    p_b, _ = _create_test_product("TOTB", 2000.0)

    items_oc = [
        {"product_id": p_a, "quantity": 100, "unit_price": 1500.0},
        {"product_id": p_b, "quantity": 50, "unit_price": 2000.0},
    ]
    oc_num = purchases_repo.create_purchase_order(s_id, "2026-09-18", "OC Totales", items_oc)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM purchase_orders WHERE oc_number = %s", (oc_num,))
            po_id = cur.fetchone()["id"]

    entry_id = inventory_repo.register_inventory_entry(
        po_id,
        order_number=f"REC-TOT-{uuid.uuid4().hex[:6]}",
        entry_date="2026-09-18",
        warehouse="Almacén Principal",
        notes="Prueba totales",
        items=items_oc,
        document_type="factura",
        document_number="FAC-TOT-1"
    )

    # Consultar vía endpoint API
    res = app_client.get(f"/api/recepciones/{entry_id}")
    assert res.status_code == 200
    payload = res.get_json()
    assert payload["status"] == "success"
    data = payload["data"]

    assert data["neto"] == 250000.0
    assert data["iva"] == 47500.0
    assert data["total"] == 297500.0
    assert data["total_quantity"] == 150
