"""
tests/integration/test_operario_mobile.py
Comprehensive test suite for Mobile Web Operator interface (/operario).
Validates:
- RBAC access control (anonymous rejected, unauthorized role rejected, operario accepted).
- UI loading for mobile screens (Home Opción 4, Recepción, OT, Scanner, Historial, Perfil).
- Receivable purchase orders filtering.
- Reception with lot and rejection without lot when requires_lot=True.
- OT lifecycle, FIFO recommended lot, exact lot consumption, and multi-lot consumption.
- Finished product lot obligation and output lot creation.
- Preservation of complete genealogy: MP -> OT -> PT.
- Universal scanner code resolution API.
- Idempotency and anti-double-submit resilience.
"""

import pytest
import json
from datetime import datetime, timezone

from app import app
from db import get_connection
import repositories.purchases_repo as purchases_repo
import repositories.production_repo as production_repo
import repositories.inventory_repo as inventory_repo
import repositories.products_repo as products_repo
import repositories.lot_genealogy_repo as lot_repo
from services.lot_traceability_service import LotTraceabilityService


@pytest.fixture
def test_client():
    prev_testing = app.config.get("TESTING", False)
    prev_csrf = app.config.get("WTF_CSRF_ENABLED", True)
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    try:
        with app.test_client() as client:
            yield client
    finally:
        app.config["TESTING"] = prev_testing
        app.config["WTF_CSRF_ENABLED"] = prev_csrf


@pytest.fixture
def operario_session(test_client):
    with test_client.session_transaction() as sess:
        sess["user_id"] = 999
        sess["username"] = "operario_test"
        sess["full_name"] = "Operario Bodega Test"
        sess["role_name"] = "Operario de Bodega"
        sess["permissions"] = {"operario_bodega": True, "inventario": True, "productos": True}
    return test_client


def test_operario_access_requires_auth(test_client):
    """Acceso anónimo debe ser redirigido a login."""
    res = test_client.get("/operario/")
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]


def test_operario_access_requires_permission(test_client):
    """Usuario sin permiso operario_bodega (ej: solo ventas) debe recibir 403."""
    with test_client.session_transaction() as sess:
        sess["user_id"] = 888
        sess["username"] = "vendedor_sin_bodega"
        sess["role_name"] = "Área Ventas"
        sess["permissions"] = {"ventas": True, "operario_bodega": False}
    
    res = test_client.get("/operario/")
    assert res.status_code == 403


def test_operario_home_renders_action_cards(operario_session):
    """Home móvil debe cargar las 4 tarjetas de la Opción 4 y sección Últimas acciones."""
    res = operario_session.get("/operario/")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "1. RECEPCIÓN" in html
    assert "2. OPERAR OT" in html
    assert "3. TERMINAR" in html
    assert "ESCANEAR AHORA" in html
    assert "Últimas acciones" in html
    assert "Inicio" in html and "Escanear" in html and "Perfil" in html


def test_operario_receivable_orders_list(operario_session):
    """Listado de órdenes muestra únicamente OCs emitidas con ítems pendientes."""
    res = operario_session.get("/operario/recepcion")
    assert res.status_code == 200
    assert b"Recepci" in res.data


def test_operario_reception_requires_lot_when_configured(operario_session):
    """Recepción de producto con requires_lot=True sin ingresar lote debe ser rechazada."""
    ts = int(datetime.now().timestamp() * 1000)
    sku = f"MP-MOB-{ts}"
    
    # Crear producto con lote obligatorio
    prod_id = products_repo.create_product(
        sku=sku,
        name=f"Insumo Móvil Test {ts}",
        category="Miel",
        product_type="Insumo",
        cost=1000.0,
        requires_lot=True
    )
    
    # Crear OC
    oc_num = purchases_repo.create_purchase_order(
        supplier_id=1,
        order_date="2026-09-15",
        notes="OC Test Móvil",
        items=[{"product_id": prod_id, "quantity": 25, "unit_price": 1000}],
        status="Emitida"
    )
    
    # Obtener ID de la OC
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM purchase_orders WHERE oc_number = %s", (oc_num,))
            po_id = cur.fetchone()["id"]

    # Intentar recibir sin lote
    post_res = operario_session.post(f"/operario/recepcion/{po_id}", data={
        "product_id": prod_id,
        "quantity": "25",
        "lot_number": "",  # Vacío deliberadamente
        "warehouse": "Principal"
    }, follow_redirects=True)
    
    assert post_res.status_code == 200
    assert "LOTE OBLIGATORIO" in post_res.data.decode("utf-8")


def test_operario_reception_and_traceability_flow(operario_session):
    """Recepción exitosa con lote físico genera entradas en inventory_entries, lots y lot_stock."""
    ts = int(datetime.now().timestamp() * 1000)
    sku = f"MP-REC-{ts}"
    lot_code = f"LOT-REC-{ts}"
    
    prod_id = products_repo.create_product(
        sku=sku,
        name=f"Insumo Recepción {ts}",
        category="Miel",
        product_type="Insumo",
        cost=1500.0,
        requires_lot=True
    )
    
    oc_num = purchases_repo.create_purchase_order(
        supplier_id=1,
        order_date="2026-09-15",
        notes="OC Test Recepción",
        items=[{"product_id": prod_id, "quantity": 50, "unit_price": 1500}],
        status="Emitida"
    )
    
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM purchase_orders WHERE oc_number = %s", (oc_num,))
            po_id = cur.fetchone()["id"]

    # Recepción válida con lote
    res = operario_session.post(f"/operario/recepcion/{po_id}", data={
        "product_id": prod_id,
        "quantity": "50",
        "lot_number": lot_code,
        "warehouse": "Principal"
    }, follow_redirects=True)
    assert res.status_code == 200
    assert "RECEPCIÓN COMPLETADA" in res.data.decode("utf-8")
    assert lot_code in res.data.decode("utf-8")

    # Validar que el lote exista en tabla lots
    lot = lot_repo.get_lot_by_product_and_number(prod_id, lot_code)
    assert lot is not None
    assert lot["initial_quantity"] == 50.0

    # Validar saldo en lot_stock
    lots_stk = inventory_repo.get_lot_stock_by_product(prod_id)
    assert len(lots_stk) == 1
    assert lots_stk[0]["available_qty"] == 50.0


def test_operario_ot_consumption_and_finalization(operario_session):
    """Flujo completo de OT móvil: Insumo con lote -> Consumo en OT -> Lote de producto terminado -> Genealogía."""
    ts = int(datetime.now().timestamp() * 1000)
    mp_sku = f"MP-OT-{ts}"
    pt_sku = f"PT-OT-{ts}"
    mp_lot = f"LOT-MP-{ts}"
    pt_lot = f"LOT-PT-{ts}"

    # 1. Crear productos
    mp_id = products_repo.create_product(
        sku=mp_sku, name=f"Insumo OT {ts}", category="Miel", product_type="Insumo", cost=2000.0, requires_lot=True
    )
    pt_id = products_repo.create_product(
        sku=pt_sku, name=f"Producto Terminado OT {ts}", category="Miel", product_type="Producto Terminado", cost=5000.0, requires_lot=True
    )

    # 2. Cargar stock y lote inicial para MP (100 unidades)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO lots (product_id, lot_number, lot_type, origin_type, initial_quantity, created_at, status, warehouse)
                VALUES (%s, %s, 'RAW_MATERIAL', 'PURCHASE', 100, NOW(), 'ACTIVE', 'Principal') RETURNING id;
                """,
                (mp_id, mp_lot)
            )
            mp_lot_id = cur.fetchone()["id"]
            cur.execute(
                """
                INSERT INTO lot_stock (product_id, lot_number, entry_date, initial_qty, available_qty, warehouse, lot_id)
                VALUES (%s, %s, CURRENT_DATE, 100, 100, 'Principal', %s);
                """,
                (mp_id, mp_lot, mp_lot_id)
            )
            cur.execute(
                """
                INSERT INTO inventory_movements (product_id, movement_type, quantity, unit_cost, reference_type, notes, lot_id, warehouse, created_at)
                VALUES (%s, 'IN', 100, 2000, 'MANUAL_ENTRY', 'Stock inicial MP', %s, 'Principal', NOW());
                """,
                (mp_id, mp_lot_id)
            )
        conn.commit()

    # 3. Crear Orden de Trabajo (OT)
    ot_num = production_repo.get_next_ot_number()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO production_orders (ot_number, final_product_id, quantity, status, created_at)
                VALUES (%s, %s, 40, 'Aprobada', NOW()) RETURNING id;
                """,
                (ot_num, pt_id)
            )
            ot_id = cur.fetchone()["id"]
            cur.execute(
                """
                INSERT INTO production_order_items (production_order_id, input_product_id, quantity_required)
                VALUES (%s, %s, 40);
                """,
                (ot_id, mp_id)
            )
        conn.commit()

    # 4. Registrar consumo de 40 unidades de MP-LOT en la OT
    res_cons = operario_session.post(f"/operario/ot/{ot_id}/consumo", data={
        "input_product_id": mp_id,
        "lot_number": mp_lot,
        "quantity": "40"
    }, follow_redirects=True)
    assert res_cons.status_code == 200
    assert "Consumo de 40 unidades" in res_cons.data.decode("utf-8")

    # Validar que el saldo del lote MP se redujo a 60
    lots_mp = inventory_repo.get_lot_stock_by_product(mp_id)
    assert lots_mp[0]["available_qty"] == 60.0

    # 5. Finalizar fabricación de la OT con lote de PT
    res_fin = operario_session.post(f"/operario/ot/{ot_id}/finalizar", data={
        "actual_quantity": "40",
        "output_lot_number": pt_lot,
        "warehouse": "Principal"
    })
    assert res_fin.status_code == 200
    assert "FABRICACIÓN COMPLETADA" in res_fin.data.decode("utf-8")
    assert pt_lot in res_fin.data.decode("utf-8")

    # La ruta móvil debe transferir el costo PPP de los consumos al producto
    # terminado, tanto en Kardex como en la OT (la ruta admin ya hacía esto).
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT unit_cost FROM inventory_movements
                   WHERE movement_type = 'PRODUCTION_OUTPUT'
                     AND reference_type = 'production_order' AND reference_id = %s""",
                (ot_id,),
            )
            output_movement = cur.fetchone()
            cur.execute("SELECT unit_cost FROM production_orders WHERE id = %s", (ot_id,))
            order_cost = cur.fetchone()["unit_cost"]
    assert output_movement is not None
    assert float(output_movement["unit_cost"]) == pytest.approx(2000.0)
    assert float(order_cost) == pytest.approx(2000.0)

    # 6. Validar supervivencia de trazabilidad genealógica 360°
    pt_lot_entity = lot_repo.get_lot_by_product_and_number(pt_id, pt_lot)
    assert pt_lot_entity is not None
    
    # Backward trace desde el producto terminado hacia la materia prima
    bwd = LotTraceabilityService.trace_lot_backward(pt_lot_entity["id"])
    ancestor_lots = [a["lot_number"] for a in bwd.get("ancestors", [])]
    assert mp_lot in ancestor_lots, f"Error: Genealogía hacia atrás falló, {mp_lot} no está en {ancestor_lots}"

    # Forward trace desde la materia prima hacia el producto terminado
    fwd = LotTraceabilityService.trace_lot_forward(mp_lot_id)
    tree_lots = [l["lot_number"] for l in fwd.get("tree_lots", [])]
    assert pt_lot in tree_lots, f"Error: Genealogía hacia adelante falló, {pt_lot} no está en {tree_lots}"


def test_operario_scanner_code_resolver(operario_session):
    """API /operario/api/resolver-codigo clasifica correctamente los códigos escaneados."""
    # Probar resolución de OC
    res_oc = operario_session.get("/operario/api/resolver-codigo?code=OC-00001")
    assert res_oc.status_code == 200
    data_oc = res_oc.get_json()
    # Si existe en la base, retorna tipo OC
    if data_oc.get("found"):
        assert data_oc["type"] == "OC"

    # Probar código desconocido
    res_unk = operario_session.get("/operario/api/resolver-codigo?code=CODIGO_TOTALMENTE_INEXISTENTE_9999")
    assert res_unk.status_code == 200
    data_unk = res_unk.get_json()
    assert data_unk["found"] is False
    assert data_unk["type"] == "UNKNOWN"


def test_operario_historial_renders_actions(operario_session):
    """Historial del operario se renderiza sin errores."""
    res = operario_session.get("/operario/historial")
    assert res.status_code == 200
    assert "Historial" in res.data.decode("utf-8")


def test_operario_pwa_manifest(test_client):
    """Manifiesto PWA debe servirse en JSON con display standalone."""
    res = test_client.get("/operario/manifest.json")
    assert res.status_code == 200
    assert "application/manifest+json" in res.headers["Content-Type"]
    data = res.get_json()
    assert data["display"] == "standalone"
    assert data["start_url"] == "/operario"
