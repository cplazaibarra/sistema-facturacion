"""
tests/integration/test_production_order_draft.py

Suite exhaustiva de pruebas para Órdenes de Trabajo en modo Borrador (DRAFT)
conforme a los requerimientos 19 y 20 de la especificación técnica.

Valida:
1. test_create_draft_ot_without_stock: Se puede crear OT en Borrador sin stock de insumos.
2. test_create_draft_ot_with_stock: Se puede crear OT en Borrador con stock suficiente.
3. test_draft_ot_does_not_consume_inventory: OT en Borrador no descuenta inventario.
4. test_draft_ot_does_not_reserve_inventory: OT en Borrador no reserva inventario.
5. test_draft_ot_does_not_create_inventory_movements: Cero filas en inventory_movements.
6. test_draft_ot_does_not_create_genealogy: Cero filas en genealogy / lotes consumidos o producidos.
7. test_draft_ot_material_requirements: Cálculo correcto de insumos requeridos.
8. test_draft_ot_shows_missing_materials: Detección dinámica de faltantes (missing_stock > 0).
9. test_draft_ot_can_be_edited: Edición de producto final, cantidad y notas.
10. test_draft_ot_recalculates_requirements_after_edit: Recálculo automático de requerimientos tras edición.
11. test_activate_draft_ot_with_stock: Activación exitosa (Borrador -> Solicitada) cuando hay stock.
12. test_cannot_activate_draft_ot_without_stock: Rechazo de activación si falta stock de algún insumo.
13. test_failed_activation_keeps_ot_draft: Si falla activación, la OT permanece en Borrador.
14. test_draft_ot_not_visible_as_executable_to_operator: Operario no ve OTs en Borrador en lista ni en detalle.
15. test_activated_ot_visible_to_operator: Al activarse pasa a Solicitada y es visible para operario.
16. test_activation_does_not_prematurely_consume_inventory: Activación NO consume inventario.
17. test_activation_does_not_reserve_inventory: Activación NO genera movimientos ni reserva persistente.
18. test_draft_ot_cancellation: Cancelación/eliminación limpia de OT en Borrador sin residuos de stock o lotes.
19. test_e2e_draft_ot_lifecycle: Ciclo de vida completo descrito en Sección 20.
"""

import pytest
import json
from datetime import datetime, timezone

from app import app
from core.database import get_connection
import repositories.production_repo as production_repo
import repositories.inventory_repo as inventory_repo
import repositories.products_repo as products_repo
import repositories.lot_genealogy_repo as lot_repo
from services.operario_service import OperarioService


@pytest.fixture
def app_client():
    """Client autenticado con CSRF restaurado después del test."""
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
        else:
            sess["user_id"] = 999
            sess["username"] = "operario_test"
            sess["full_name"] = "Operario Bodega Test"
            sess["role_name"] = "Operario de Bodega"
            sess["permissions"] = {"operario_bodega": True, "inventario": True, "productos": True}


def _create_test_recipe_and_products(prefix="DRAFT"):
    """Helper que crea Producto Final y 2 Insumos con su receta."""
    ts = int(datetime.now().timestamp() * 1000)
    
    # Insumo 1: MP-A
    p_insumo_a = products_repo.create_product(
        sku=f"{prefix}-MPA-{ts}",
        name=f"Materia Prima A {ts}",
        category="Insumos",
        product_type="Insumo",
        cost=100.0,
        requires_lot=True
    )
    
    # Insumo 2: MP-B
    p_insumo_b = products_repo.create_product(
        sku=f"{prefix}-MPB-{ts}",
        name=f"Materia Prima B {ts}",
        category="Insumos",
        product_type="Insumo",
        cost=200.0,
        requires_lot=True
    )
    
    # Producto Final: PT
    p_final = products_repo.create_product(
        sku=f"{prefix}-PT-{ts}",
        name=f"Producto Terminado {ts}",
        category="Miel",
        product_type="Final",
        cost=500.0,
        requires_lot=True
    )
    
    # Receta: product_recipes + product_recipe_items
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO product_recipes (final_product_id, created_at, recipe_code)
                VALUES (%s, %s, %s)
                RETURNING id
            """, (p_final, now_str, f"REC-{ts}"))
            recipe_id = cur.fetchone()["id"]
            
            cur.execute("""
                INSERT INTO product_recipe_items (recipe_id, input_product_id, quantity_required)
                VALUES (%s, %s, 2.0), (%s, %s, 1.0)
            """, (recipe_id, p_insumo_a, recipe_id, p_insumo_b))
        conn.commit()
            
    return p_final, p_insumo_a, p_insumo_b


def _add_stock_to_product(product_id, quantity, cost=100.0):
    """Helper para ingresar stock mediante lots, lot_stock e inventory_movements."""
    ts = int(datetime.now().timestamp() * 1000)
    lot_code = f"LOT-{product_id}-{ts}"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO lots (product_id, lot_number, lot_type, origin_type, initial_quantity, created_at, status, warehouse)
                VALUES (%s, %s, 'RAW_MATERIAL', 'PURCHASE', %s, NOW(), 'ACTIVE', 'Principal')
                RETURNING id
            """, (product_id, lot_code, quantity))
            lot_id = cur.fetchone()["id"]

            cur.execute("""
                INSERT INTO lot_stock (product_id, lot_number, entry_date, initial_qty, available_qty, warehouse, lot_id)
                VALUES (%s, %s, CURRENT_DATE, %s, %s, 'Principal', %s)
            """, (product_id, lot_code, quantity, quantity, lot_id))

            cur.execute("""
                INSERT INTO inventory_movements (product_id, movement_type, quantity, reference_type, notes, lot_id, warehouse, created_at)
                VALUES (%s, 'IN', %s, 'MANUAL_ENTRY', 'Ingreso test_draft_ot', %s, 'Principal', NOW())
            """, (product_id, quantity, lot_id))
        conn.commit()
            
    return lot_id


# ==============================================================================
# TESTS
# ==============================================================================

def test_create_draft_ot_without_stock():
    """1. test_create_draft_ot_without_stock: Se puede crear OT en Borrador sin stock de insumos."""
    p_final, p_a, p_b = _create_test_recipe_and_products("C1")
    
    # Stock inicial es 0
    assert inventory_repo.get_relational_stock(p_a) == 0.0
    assert inventory_repo.get_relational_stock(p_b) == 0.0
    
    # Crear OT en Borrador para 10 unidades de PT
    ot_id, ot_number = production_repo.create_production_order(
        final_product_id=p_final,
        quantity=10,
        notes="OT de planificación sin stock",
        status="Borrador"
    )
    assert ot_id is not None
    
    ot = production_repo.get_production_order_by_id(ot_id)
    assert ot["status"] == "Borrador"
    assert ot["quantity"] == 10
    assert ot["final_product_id"] == p_final


def test_create_draft_ot_with_stock():
    """2. test_create_draft_ot_with_stock: Se puede crear OT en Borrador con stock suficiente."""
    p_final, p_a, p_b = _create_test_recipe_and_products("C2")
    _add_stock_to_product(p_a, 50.0)
    _add_stock_to_product(p_b, 50.0)
    
    ot_id, ot_number = production_repo.create_production_order(
        final_product_id=p_final,
        quantity=10,
        notes="OT de planificación con stock",
        status="Borrador"
    )
    ot = production_repo.get_production_order_by_id(ot_id)
    assert ot["status"] == "Borrador"


def test_draft_ot_does_not_consume_inventory():
    """3. test_draft_ot_does_not_consume_inventory: OT en Borrador no descuenta inventario."""
    p_final, p_a, p_b = _create_test_recipe_and_products("C3")
    _add_stock_to_product(p_a, 100.0)
    _add_stock_to_product(p_b, 50.0)
    
    stock_a_before = inventory_repo.get_relational_stock(p_a)
    stock_b_before = inventory_repo.get_relational_stock(p_b)
    
    ot_id, _ = production_repo.create_production_order(p_final, 20, "OT borrador", status="Borrador")
    
    stock_a_after = inventory_repo.get_relational_stock(p_a)
    stock_b_after = inventory_repo.get_relational_stock(p_b)
    
    assert stock_a_after == stock_a_before == 100.0
    assert stock_b_after == stock_b_before == 50.0


def test_draft_ot_does_not_reserve_inventory():
    """4. test_draft_ot_does_not_reserve_inventory: OT en Borrador no reserva inventario."""
    p_final, p_a, p_b = _create_test_recipe_and_products("C4")
    _add_stock_to_product(p_a, 20.0)
    
    # Crear múltiples OTs en borrador que compitan por el mismo stock
    ot1, _ = production_repo.create_production_order(p_final, 10, status="Borrador")
    ot2, _ = production_repo.create_production_order(p_final, 10, status="Borrador")
    
    assert ot1 is not None and ot2 is not None
    assert inventory_repo.get_relational_stock(p_a) == 20.0


def test_draft_ot_does_not_create_inventory_movements():
    """5. test_draft_ot_does_not_create_inventory_movements: Cero filas en inventory_movements."""
    p_final, p_a, p_b = _create_test_recipe_and_products("C5")
    
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as count FROM inventory_movements")
            moves_before = cur.fetchone()["count"]
            
    ot_id, _ = production_repo.create_production_order(p_final, 15, status="Borrador")
    
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as count FROM inventory_movements")
            moves_after = cur.fetchone()["count"]
            
    assert moves_after == moves_before


def test_draft_ot_does_not_create_genealogy():
    """6. test_draft_ot_does_not_create_genealogy: Cero filas en genealogy / lotes consumidos o producidos."""
    p_final, p_a, p_b = _create_test_recipe_and_products("C6")
    
    ot_id, _ = production_repo.create_production_order(p_final, 5, status="Borrador")
    
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as count FROM production_lot_consumptions WHERE production_order_id = %s", (ot_id,))
            cons_ot = cur.fetchone()["count"]
            cur.execute("SELECT COUNT(*) as count FROM production_lot_outputs WHERE production_order_id = %s", (ot_id,))
            out_ot = cur.fetchone()["count"]
            
    assert cons_ot == 0
    assert out_ot == 0


def test_draft_ot_material_requirements():
    """7. test_draft_ot_material_requirements: Cálculo correcto de insumos requeridos."""
    p_final, p_a, p_b = _create_test_recipe_and_products("C7")
    
    ot_id, _ = production_repo.create_production_order(p_final, 10, status="Borrador")
    avail = production_repo.get_ot_material_availability(ot_id)
    
    req_map = {m["product_id"]: m["quantity_required"] for m in avail["materials"]}
    assert req_map[p_a] == 20.0
    assert req_map[p_b] == 10.0


def test_draft_ot_shows_missing_materials():
    """8. test_draft_ot_shows_missing_materials: Detección dinámica de faltantes (missing_stock > 0)."""
    p_final, p_a, p_b = _create_test_recipe_and_products("C8")
    _add_stock_to_product(p_a, 15.0)  # Req es 20, faltan 5
    # MP-B tiene 0
    
    ot_id, _ = production_repo.create_production_order(p_final, 10, status="Borrador")
    avail = production_repo.get_ot_material_availability(ot_id)
    
    assert avail["is_complete"] is False
    assert avail["status_label"] == "Faltan materiales"
    
    missing_map = {m["product_id"]: m["missing_stock"] for m in avail["materials"]}
    assert missing_map[p_a] == 5.0
    assert missing_map[p_b] == 10.0


def test_draft_ot_can_be_edited():
    """9. test_draft_ot_can_be_edited: Edición de producto final, cantidad y notas."""
    p_final, p_a, p_b = _create_test_recipe_and_products("C9")
    ot_id, _ = production_repo.create_production_order(p_final, 5, notes="Original", status="Borrador")
    
    ok, msg = production_repo.update_draft_production_order(
        ot_id=ot_id,
        final_product_id=p_final,
        quantity=12,
        notes="Modificado exitosamente"
    )
    assert ok is True
    
    ot = production_repo.get_production_order_by_id(ot_id)
    assert ot["quantity"] == 12
    assert ot["notes"] == "Modificado exitosamente"


def test_draft_ot_recalculates_requirements_after_edit():
    """10. test_draft_ot_recalculates_requirements_after_edit: Recálculo automático de requerimientos tras edición."""
    p_final, p_a, p_b = _create_test_recipe_and_products("C10")
    ot_id, _ = production_repo.create_production_order(p_final, 10, status="Borrador")
    
    avail1 = production_repo.get_ot_material_availability(ot_id)
    req1 = {m["product_id"]: m["quantity_required"] for m in avail1["materials"]}
    assert req1[p_a] == 20.0
    assert req1[p_b] == 10.0
    
    ok, _ = production_repo.update_draft_production_order(ot_id, p_final, 25)
    assert ok is True
    
    avail2 = production_repo.get_ot_material_availability(ot_id)
    req2 = {m["product_id"]: m["quantity_required"] for m in avail2["materials"]}
    assert req2[p_a] == 50.0
    assert req2[p_b] == 25.0


def test_activate_draft_ot_with_stock():
    """11. test_activate_draft_ot_with_stock: Activación exitosa (Borrador -> Solicitada) cuando hay stock."""
    p_final, p_a, p_b = _create_test_recipe_and_products("C11")
    _add_stock_to_product(p_a, 40.0)
    _add_stock_to_product(p_b, 20.0)
    
    ot_id, _ = production_repo.create_production_order(p_final, 10, status="Borrador")
    
    ok, msg, detail = production_repo.activate_draft_production_order(ot_id)
    assert ok is True
    assert "activada exitosamente" in msg
    
    ot = production_repo.get_production_order_by_id(ot_id)
    assert ot["status"] == "Solicitada"


def test_cannot_activate_draft_ot_without_stock():
    """12. test_cannot_activate_draft_ot_without_stock: Rechazo de activación si falta stock de algún insumo."""
    p_final, p_a, p_b = _create_test_recipe_and_products("C12")
    _add_stock_to_product(p_a, 20.0) # Suficiente para MP-A (necesita 20)
    # MP-B sin stock (0.0, necesita 10)
    
    ot_id, _ = production_repo.create_production_order(p_final, 10, status="Borrador")
    ok, msg, detail = production_repo.activate_draft_production_order(ot_id)
    
    assert ok is False
    assert ("falta stock" in msg.lower() or "insuficiente" in msg.lower())
    assert detail is not None
    missing_items = [m for m in detail["materials"] if m["missing_stock"] > 1e-6]
    assert len(missing_items) > 0


def test_failed_activation_keeps_ot_draft():
    """13. test_failed_activation_keeps_ot_draft: Si falla activación, la OT permanece en Borrador."""
    p_final, p_a, p_b = _create_test_recipe_and_products("C13")
    ot_id, _ = production_repo.create_production_order(p_final, 10, status="Borrador")
    
    ok, _, _ = production_repo.activate_draft_production_order(ot_id)
    assert ok is False
    
    ot = production_repo.get_production_order_by_id(ot_id)
    assert ot["status"] == "Borrador"


def test_draft_ot_not_visible_as_executable_to_operator(app_client):
    """14. test_draft_ot_not_visible_as_executable_to_operator: Operario no ve OTs en Borrador."""
    _login_as(app_client, "operario")
    p_final, p_a, p_b = _create_test_recipe_and_products("C14")
    ot_id, ot_num = production_repo.create_production_order(p_final, 10, status="Borrador")
    
    # 1. No debe aparecer en list_active_production_orders()
    active_ots = production_repo.list_active_production_orders()
    assert not any(o["id"] == ot_id for o in active_ots)
    
    # 2. No debe aparecer en la vista GET /operario/ot
    res = app_client.get("/operario/ot")
    assert res.status_code == 200
    assert ot_num.encode() not in res.data
    
    # 3. Acceso directo GET /operario/ot/<id> debe ser redirigido
    res_detail = app_client.get(f"/operario/ot/{ot_id}")
    assert res_detail.status_code == 302


def test_activated_ot_visible_to_operator(app_client):
    """15. test_activated_ot_visible_to_operator: Al activarse pasa a Solicitada y es visible para operario."""
    _login_as(app_client, "operario")
    p_final, p_a, p_b = _create_test_recipe_and_products("C15")
    _add_stock_to_product(p_a, 20.0)
    _add_stock_to_product(p_b, 10.0)
    
    ot_id, _ = production_repo.create_production_order(p_final, 10, status="Borrador")
    ok, _, _ = production_repo.activate_draft_production_order(ot_id)
    assert ok is True
    
    # Ahora sí debe figurar en active_ots
    active_ots = production_repo.list_active_production_orders()
    assert any(o["id"] == ot_id for o in active_ots)
    
    # Y debe ser accesible para el operario
    res = app_client.get(f"/operario/ot/{ot_id}")
    assert res.status_code == 200


def test_activation_does_not_prematurely_consume_inventory():
    """16. test_activation_does_not_prematurely_consume_inventory: Activación NO consume inventario."""
    p_final, p_a, p_b = _create_test_recipe_and_products("C16")
    _add_stock_to_product(p_a, 50.0)
    _add_stock_to_product(p_b, 50.0)
    
    ot_id, _ = production_repo.create_production_order(p_final, 10, status="Borrador")
    
    stock_a_pre = inventory_repo.get_relational_stock(p_a)
    stock_b_pre = inventory_repo.get_relational_stock(p_b)
    
    ok, _, _ = production_repo.activate_draft_production_order(ot_id)
    assert ok is True
    
    stock_a_post = inventory_repo.get_relational_stock(p_a)
    stock_b_post = inventory_repo.get_relational_stock(p_b)
    
    assert stock_a_post == stock_a_pre == 50.0
    assert stock_b_post == stock_b_pre == 50.0


def test_activation_does_not_reserve_inventory():
    """17. test_activation_does_not_reserve_inventory: Activación NO genera movimientos ni reservas ficticias."""
    p_final, p_a, p_b = _create_test_recipe_and_products("C17")
    _add_stock_to_product(p_a, 20.0)
    _add_stock_to_product(p_b, 10.0)
    
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as count FROM inventory_movements")
            count_pre = cur.fetchone()["count"]
            
    ot_id, _ = production_repo.create_production_order(p_final, 10, status="Borrador")
    ok, _, _ = production_repo.activate_draft_production_order(ot_id)
    assert ok is True
    
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as count FROM inventory_movements")
            count_post = cur.fetchone()["count"]
            
    assert count_post == count_pre


def test_draft_ot_cancellation():
    """18. test_draft_ot_cancellation: Cancelación/eliminación de OT en borrador."""
    p_final, p_a, p_b = _create_test_recipe_and_products("C18")
    ot_id, _ = production_repo.create_production_order(p_final, 5, status="Borrador")
    
    ok, msg = production_repo.cancel_draft_production_order(ot_id)
    assert ok is True
    
    ot = production_repo.get_production_order_by_id(ot_id)
    assert ot is None


def test_e2e_draft_ot_lifecycle(app_client):
    """
    19. test_e2e_draft_ot_lifecycle:
    Escenario integral de Sección 20:
    1. Crear productos MP-A, MP-B y PT con receta (PT = 2 MP-A + 1 MP-B).
    2. Ingresar stock: MP-A = 100, MP-B = 0.
    3. Crear OT en Borrador para 20 PT (necesita 40 MP-A y 20 MP-B).
    4. Verificar estado Borrador, no consumo de stock, faltante dinámico = 20 MP-B.
    5. Intentar activar -> Rechazado por falta de MP-B. OT permanece en Borrador.
    6. No visible en móvil operario.
    7. Ingresar stock de MP-B = 20 unidades.
    8. Verificar que el cálculo dinámico ahora marca is_complete = True.
    9. Activar OT -> Pasa a Solicitada exitosamente. Stock aún intacto (no reserva/no consume).
    10. Visible en interfaz de operario.
    11. Aprobar y finalizar OT -> Stock descontado exactamente aquí.
    """
    ts = int(datetime.now().timestamp() * 1000)
    p_final, p_a, p_b = _create_test_recipe_and_products(f"E2E-{ts}")
    
    # 2. Stock inicial: MP-A = 100, MP-B = 0
    _add_stock_to_product(p_a, 100.0, cost=150.0)
    assert inventory_repo.get_relational_stock(p_a) == 100.0
    assert inventory_repo.get_relational_stock(p_b) == 0.0
    
    # 3. Crear OT en Borrador vía endpoint web como Admin
    _login_as(app_client, "admin")
    res_create = app_client.post("/produccion/nueva", data={
        "final_product_id": p_final,
        "quantity": 20,
        "notes": "Planificacion E2E",
        "action": "draft"
    }, follow_redirects=True)
    assert res_create.status_code == 200
    
    # Obtener la OT creada
    all_ots = production_repo.list_production_orders()
    draft_ot = next(o for o in all_ots if o["final_product_id"] == p_final and o["status"] == "Borrador")
    ot_id = draft_ot["id"]
    
    # 4. Verificar estado y faltantes
    assert draft_ot["status"] == "Borrador"
    assert inventory_repo.get_relational_stock(p_a) == 100.0
    assert inventory_repo.get_relational_stock(p_b) == 0.0
    
    avail = production_repo.get_ot_material_availability(ot_id)
    assert avail["is_complete"] is False
    missing_b = next(m for m in avail["materials"] if m["product_id"] == p_b)
    assert missing_b["missing_stock"] == 20.0
    
    # 5. Intentar activar -> Rechazo
    res_act_fail = app_client.post(f"/produccion/ot/{ot_id}/activar", follow_redirects=True)
    assert res_act_fail.status_code == 200
    ot_check = production_repo.get_production_order_by_id(ot_id)
    assert ot_check["status"] == "Borrador"
    
    # 6. Operario no la ve
    _login_as(app_client, "operario")
    res_op = app_client.get(f"/operario/ot/{ot_id}")
    assert res_op.status_code in (302, 400)
    
    # 7. Ingresar stock de MP-B = 20
    _add_stock_to_product(p_b, 20.0, cost=250.0)
    assert inventory_repo.get_relational_stock(p_b) == 20.0
    
    # 8. Cálculo dinámico
    avail_after = production_repo.get_ot_material_availability(ot_id)
    assert avail_after["is_complete"] is True
    
    # 9. Activar OT -> Pasa a Solicitada (como admin)
    _login_as(app_client, "admin")
    res_act_ok = app_client.post(f"/produccion/ot/{ot_id}/activar", follow_redirects=True)
    assert res_act_ok.status_code == 200
    ot_active = production_repo.get_production_order_by_id(ot_id)
    assert ot_active["status"] == "Solicitada"
    
    # Stock aún intacto
    assert inventory_repo.get_relational_stock(p_a) == 100.0
    assert inventory_repo.get_relational_stock(p_b) == 20.0
    
    # 10. Operario la ve
    _login_as(app_client, "operario")
    res_op_ok = app_client.get(f"/operario/ot/{ot_id}")
    assert res_op_ok.status_code == 200
    
    # 11. Aprobar y finalizar OT (como admin)
    _login_as(app_client, "admin")
    app_client.post(f"/produccion/ot/{ot_id}/aprobar", follow_redirects=True)
    ot_aprobada = production_repo.get_production_order_by_id(ot_id)
    assert ot_aprobada["status"] == "Aprobada"
    
    app_client.post(f"/produccion/ot/{ot_id}/finalizar", follow_redirects=True)
    ot_fin = production_repo.get_production_order_by_id(ot_id)
    assert ot_fin["status"] == "Finalizada"
    
    # Consumo real de inventario verificado
    # Se consumieron 40 de MP-A (quedan 60) y 20 de MP-B (quedan 0)
    assert inventory_repo.get_relational_stock(p_a) == 60.0
    assert inventory_repo.get_relational_stock(p_b) == 0.0
    # Y se fabricaron 20 de PT
    assert inventory_repo.get_relational_stock(p_final) == 20.0
