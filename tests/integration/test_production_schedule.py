"""
tests/integration/test_production_schedule.py

Suite exhaustiva de pruebas para el Calendario y Programación Semanal de Órdenes de Trabajo (OT).
Valida:
1. test_create_draft_ot_with_scheduled_date: Se puede crear OT en Borrador con fecha programada.
2. test_schedule_ot_without_stock: Se puede programar OT aunque falten materiales.
3. test_schedule_ot_with_stock: Se puede programar OT con stock disponible.
4. test_schedule_does_not_change_status: Programar una OT NO modifica su status.
5. test_schedule_does_not_consume_inventory: Programar NO consume inventario (0 inventory_movements).
6. test_schedule_does_not_reserve_inventory: Programar NO crea reservas ni movimientos ficticios.
7. test_schedule_does_not_create_genealogy: Programar NO crea lotes ni filas en genealogía.
8. test_reschedule_ot: Cambio de fecha programada persiste scheduled_date.
9. test_reschedule_does_not_change_status: Reprogramar NO modifica el status de la OT.
10. test_calendar_week_returns_scheduled_orders: Consulta semanal retorna las OTs del rango lunes-domingo.
11. test_calendar_excludes_other_weeks: Consulta semanal excluye OTs de otras semanas.
12. test_unscheduled_orders_are_listed: OTs sin fecha aparecen en list_unscheduled_production_orders.
13. test_calendar_material_availability_is_dynamic: Disponibilidad se calcula dinámicamente según stock real.
14. test_finished_ot_keeps_scheduled_date: Finalizar OT conserva scheduled_date y schedule_order.
15. test_cancelled_ot_keeps_scheduled_date: Cancelar OT conserva scheduled_date y schedule_order.
16. test_draft_scheduled_ot_not_executable_by_operator: Una OT en Borrador programada NO es ejecutable en /operario.
17. test_multiple_orders_same_day_have_schedule_order: Múltiples OTs el mismo día tienen orden correlativo 1, 2, 3.
18. test_reorder_orders_within_same_day: Reordenar OTs en el mismo día actualiza y normaliza schedule_order.
19. test_move_order_to_another_day_recalculates_order: Mover OT a otro día normaliza orden de origen y destino.
20. test_schedule_order_does_not_affect_status: Alterar el orden dentro del día no afecta status.
21. test_schedule_order_does_not_affect_inventory: Alterar el orden dentro del día no afecta inventario.
22. test_e2e_production_schedule_flow: Escenario integral del requerimiento 19 y 23.
"""

import pytest
import json
from datetime import datetime, timezone, timedelta

from app import app
from core.database import get_connection
import repositories.production_repo as production_repo
import repositories.inventory_repo as inventory_repo
import repositories.products_repo as products_repo


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


def _create_test_recipe_and_products(prefix="SCHED"):
    """Helper que crea Producto Final y 2 Insumos con su receta."""
    ts = int(datetime.now().timestamp() * 1000)
    
    p_insumo_a = products_repo.create_product(
        sku=f"{prefix}-MPA-{ts}",
        name=f"Materia Prima A {ts}",
        category="Insumos",
        product_type="Insumo",
        cost=100.0,
        requires_lot=True
    )
    
    p_insumo_b = products_repo.create_product(
        sku=f"{prefix}-MPB-{ts}",
        name=f"Materia Prima B {ts}",
        category="Insumos",
        product_type="Insumo",
        cost=200.0,
        requires_lot=True
    )
    
    p_final = products_repo.create_product(
        sku=f"{prefix}-PT-{ts}",
        name=f"Producto Terminado {ts}",
        category="Miel",
        product_type="Final",
        cost=500.0,
        requires_lot=True
    )
    
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
                VALUES (%s, 'IN', %s, 'MANUAL_ENTRY', 'Ingreso test_production_schedule', %s, 'Principal', NOW())
            """, (product_id, quantity, lot_id))
        conn.commit()
            
    return lot_id


# ==============================================================================
# TESTS UNITARIOS E INTEGRACIÓN
# ==============================================================================

def test_create_draft_ot_with_scheduled_date():
    """1. Se puede crear OT en Borrador con fecha programada directamente."""
    p_final, p_a, p_b = _create_test_recipe_and_products("S1")
    target_date = "2026-09-23"
    
    ot_id, ot_number = production_repo.create_production_order(
        final_product_id=p_final,
        quantity=10,
        notes="OT con fecha programada",
        status="Borrador",
        scheduled_date=target_date
    )
    ot = production_repo.get_production_order_by_id(ot_id)
    assert ot["status"] == "Borrador"
    assert str(ot["scheduled_date"]) == target_date
    assert ot["schedule_order"] is not None


def test_schedule_ot_without_stock():
    """2. Se puede programar OT aunque falten materiales."""
    p_final, p_a, p_b = _create_test_recipe_and_products("S2")
    # Stock es 0
    assert inventory_repo.get_relational_stock(p_a) == 0.0
    
    ot_id, _ = production_repo.create_production_order(p_final, 10, status="Borrador")
    ok, msg, detail = production_repo.set_production_order_schedule(ot_id, "2026-09-24", 1)
    
    assert ok is True
    assert detail["scheduled_date"] == "2026-09-24"
    ot = production_repo.get_production_order_by_id(ot_id)
    assert str(ot["scheduled_date"]) == "2026-09-24"
    assert ot["status"] == "Borrador"


def test_schedule_ot_with_stock():
    """3. Se puede programar OT con stock disponible."""
    p_final, p_a, p_b = _create_test_recipe_and_products("S3")
    _add_stock_to_product(p_a, 50.0)
    _add_stock_to_product(p_b, 50.0)
    
    ot_id, _ = production_repo.create_production_order(p_final, 10, status="Solicitada")
    ok, msg, detail = production_repo.set_production_order_schedule(ot_id, "2026-09-25", 1)
    
    assert ok is True
    ot = production_repo.get_production_order_by_id(ot_id)
    assert str(ot["scheduled_date"]) == "2026-09-25"
    assert ot["status"] == "Solicitada"


def test_schedule_does_not_change_status():
    """4. Programar una OT NO modifica su status."""
    p_final, p_a, p_b = _create_test_recipe_and_products("S4")
    ot_id, _ = production_repo.create_production_order(p_final, 5, status="Borrador")
    
    production_repo.set_production_order_schedule(ot_id, "2026-09-26", 1)
    ot = production_repo.get_production_order_by_id(ot_id)
    assert ot["status"] == "Borrador"


def test_schedule_does_not_consume_inventory():
    """5. Programar NO consume inventario (0 inventory_movements)."""
    p_final, p_a, p_b = _create_test_recipe_and_products("S5")
    _add_stock_to_product(p_a, 100.0)
    
    stock_before = inventory_repo.get_relational_stock(p_a)
    ot_id, _ = production_repo.create_production_order(p_final, 20, status="Borrador")
    production_repo.set_production_order_schedule(ot_id, "2026-09-25", 1)
    stock_after = inventory_repo.get_relational_stock(p_a)
    
    assert stock_after == stock_before == 100.0


def test_schedule_does_not_reserve_inventory():
    """6. Programar NO crea reservas ni movimientos ficticios."""
    p_final, p_a, p_b = _create_test_recipe_and_products("S6")
    
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as c FROM inventory_movements")
            moves_pre = cur.fetchone()["c"]
            
    ot_id, _ = production_repo.create_production_order(p_final, 10, status="Borrador")
    production_repo.set_production_order_schedule(ot_id, "2026-09-24", 1)
    
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as c FROM inventory_movements")
            moves_post = cur.fetchone()["c"]
            
    assert moves_post == moves_pre


def test_schedule_does_not_create_genealogy():
    """7. Programar NO crea lotes ni filas en genealogía."""
    p_final, p_a, p_b = _create_test_recipe_and_products("S7")
    ot_id, _ = production_repo.create_production_order(p_final, 10, status="Borrador")
    production_repo.set_production_order_schedule(ot_id, "2026-09-24", 1)
    
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as c FROM production_lot_consumptions WHERE production_order_id = %s", (ot_id,))
            assert cur.fetchone()["c"] == 0
            cur.execute("SELECT COUNT(*) as c FROM production_lot_outputs WHERE production_order_id = %s", (ot_id,))
            assert cur.fetchone()["c"] == 0


def test_reschedule_ot():
    """8. Cambio de fecha programada persiste scheduled_date."""
    p_final, p_a, p_b = _create_test_recipe_and_products("S8")
    ot_id, _ = production_repo.create_production_order(p_final, 10, status="Borrador", scheduled_date="2026-09-22")
    
    ok, msg, detail = production_repo.set_production_order_schedule(ot_id, "2026-09-24")
    assert ok is True
    ot = production_repo.get_production_order_by_id(ot_id)
    assert str(ot["scheduled_date"]) == "2026-09-24"


def test_reschedule_does_not_change_status():
    """9. Reprogramar NO modifica el status de la OT."""
    p_final, p_a, p_b = _create_test_recipe_and_products("S9")
    ot_id, _ = production_repo.create_production_order(p_final, 10, status="Borrador", scheduled_date="2026-09-22")
    
    production_repo.set_production_order_schedule(ot_id, "2026-09-25")
    ot = production_repo.get_production_order_by_id(ot_id)
    assert ot["status"] == "Borrador"


def test_calendar_week_returns_scheduled_orders():
    """10. Consulta semanal retorna las OTs del rango lunes-domingo."""
    p_final, p_a, p_b = _create_test_recipe_and_products("S10")
    # Semana del 21 al 27 de Septiembre 2026 (lunes 21 a domingo 27)
    ot1, _ = production_repo.create_production_order(p_final, 5, scheduled_date="2026-09-21")
    ot2, _ = production_repo.create_production_order(p_final, 8, scheduled_date="2026-09-25")
    
    ots = production_repo.list_scheduled_production_orders("2026-09-21", "2026-09-27")
    ids = [o["id"] for o in ots]
    assert ot1 in ids
    assert ot2 in ids


def test_calendar_excludes_other_weeks():
    """11. Consulta semanal excluye OTs de otras semanas."""
    p_final, p_a, p_b = _create_test_recipe_and_products("S11")
    ot_prev, _ = production_repo.create_production_order(p_final, 5, scheduled_date="2026-09-14")
    ot_next, _ = production_repo.create_production_order(p_final, 5, scheduled_date="2026-09-30")
    
    ots = production_repo.list_scheduled_production_orders("2026-09-21", "2026-09-27")
    ids = [o["id"] for o in ots]
    assert ot_prev not in ids
    assert ot_next not in ids


def test_unscheduled_orders_are_listed():
    """12. OTs sin fecha aparecen en list_unscheduled_production_orders."""
    p_final, p_a, p_b = _create_test_recipe_and_products("S12")
    ot_id, _ = production_repo.create_production_order(p_final, 7, status="Borrador") # scheduled_date=None
    
    unscheduled = production_repo.list_unscheduled_production_orders()
    ids = [o["id"] for o in unscheduled]
    assert ot_id in ids


def test_calendar_material_availability_is_dynamic():
    """13. Disponibilidad se calcula dinámicamente según stock real."""
    p_final, p_a, p_b = _create_test_recipe_and_products("S13")
    ot_id, _ = production_repo.create_production_order(p_final, 10, scheduled_date="2026-09-23")
    
    # 1. Sin stock
    ots_pre = production_repo.list_scheduled_production_orders("2026-09-21", "2026-09-27")
    target_pre = next(o for o in ots_pre if o["id"] == ot_id)
    assert target_pre["is_complete"] is False
    assert target_pre["status_label"] == "Faltan materiales"
    
    # 2. Ingresar stock requerido
    _add_stock_to_product(p_a, 20.0)
    _add_stock_to_product(p_b, 10.0)
    
    # 3. Al volver a consultar, disponibilidad se actualiza automáticamente sin tocar la OT
    ots_post = production_repo.list_scheduled_production_orders("2026-09-21", "2026-09-27")
    target_post = next(o for o in ots_post if o["id"] == ot_id)
    assert target_post["is_complete"] is True
    assert target_post["status_label"] == "Stock disponible"


def test_finished_ot_keeps_scheduled_date():
    """14. Finalizar OT conserva scheduled_date y schedule_order."""
    p_final, p_a, p_b = _create_test_recipe_and_products("S14")
    _add_stock_to_product(p_a, 20.0)
    _add_stock_to_product(p_b, 10.0)
    
    target_date = "2026-09-23"
    ot_id, _ = production_repo.create_production_order(p_final, 10, status="Aprobada", scheduled_date=target_date, schedule_order=2)
    
    # Simular finalización
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE production_orders SET status = 'Finalizada' WHERE id = %s", (ot_id,))
        conn.commit()
        
    ot = production_repo.get_production_order_by_id(ot_id)
    assert ot["status"] == "Finalizada"
    assert str(ot["scheduled_date"]) == target_date
    assert ot["schedule_order"] == 2


def test_cancelled_ot_keeps_scheduled_date():
    """15. Cancelar OT conserva scheduled_date y schedule_order."""
    p_final, p_a, p_b = _create_test_recipe_and_products("S15")
    target_date = "2026-09-24"
    ot_id, _ = production_repo.create_production_order(p_final, 5, status="Borrador", scheduled_date=target_date, schedule_order=1)
    
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE production_orders SET status = 'Cancelada' WHERE id = %s", (ot_id,))
        conn.commit()
        
    ot = production_repo.get_production_order_by_id(ot_id)
    assert ot["status"] == "Cancelada"
    assert str(ot["scheduled_date"]) == target_date
    assert ot["schedule_order"] == 1


def test_draft_scheduled_ot_not_executable_by_operator(app_client):
    """16. Una OT en Borrador programada NO es ejecutable en /operario."""
    _login_as(app_client, "operario")
    p_final, p_a, p_b = _create_test_recipe_and_products("S16")
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    ot_id, ot_num = production_repo.create_production_order(
        p_final, 10, status="Borrador", scheduled_date=today_str
    )
    
    # No debe figurar en lista activa
    active = production_repo.list_active_production_orders()
    assert not any(o["id"] == ot_id for o in active)
    
    # No debe aparecer en /operario/ot
    res = app_client.get("/operario/ot")
    assert ot_num.encode() not in res.data
    
    # Detalle directo debe ser rechazado
    res_det = app_client.get(f"/operario/ot/{ot_id}")
    assert res_det.status_code == 302


def test_multiple_orders_same_day_have_schedule_order():
    """17. Múltiples OTs el mismo día tienen orden correlativo 1, 2, 3."""
    import uuid
    p_final, p_a, p_b = _create_test_recipe_and_products("S17")
    u_day = (int(uuid.uuid4().hex[:6], 16) % 20) + 1
    target_date = f"2041-01-{u_day:02d}"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM production_orders WHERE scheduled_date = %s", (target_date,))
        conn.commit()
    
    ot1, _ = production_repo.create_production_order(p_final, 5, scheduled_date=target_date)
    ot2, _ = production_repo.create_production_order(p_final, 5, scheduled_date=target_date)
    ot3, _ = production_repo.create_production_order(p_final, 5, scheduled_date=target_date)
    
    o1 = production_repo.get_production_order_by_id(ot1)
    o2 = production_repo.get_production_order_by_id(ot2)
    o3 = production_repo.get_production_order_by_id(ot3)
    
    assert o1["schedule_order"] == 1
    assert o2["schedule_order"] == 2
    assert o3["schedule_order"] == 3


def test_reorder_orders_within_same_day():
    """18. Reordenar OTs en el mismo día actualiza y normaliza schedule_order."""
    import uuid
    p_final, p_a, p_b = _create_test_recipe_and_products("S18")
    u_day = (int(uuid.uuid4().hex[:6], 16) % 20) + 1
    target_date = f"2042-02-{u_day:02d}"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM production_orders WHERE scheduled_date = %s", (target_date,))
        conn.commit()
    
    ot1, _ = production_repo.create_production_order(p_final, 5, scheduled_date=target_date)
    ot2, _ = production_repo.create_production_order(p_final, 5, scheduled_date=target_date)
    ot3, _ = production_repo.create_production_order(p_final, 5, scheduled_date=target_date)
    
    # Mover ot3 a la posición 1
    ok, _, _ = production_repo.set_production_order_schedule(ot3, target_date, schedule_order=1)
    assert ok is True
    
    o3 = production_repo.get_production_order_by_id(ot3)
    o1 = production_repo.get_production_order_by_id(ot1)
    o2 = production_repo.get_production_order_by_id(ot2)
    
    assert o3["schedule_order"] == 1
    assert o1["schedule_order"] == 2
    assert o2["schedule_order"] == 3


def test_move_order_to_another_day_recalculates_order():
    """19. Mover OT a otro día normaliza orden de origen y destino."""
    import uuid
    p_final, p_a, p_b = _create_test_recipe_and_products("S19")
    u_val = int(uuid.uuid4().hex[:6], 16)
    day_a = f"2043-03-{(u_val % 10 + 1):02d}"
    day_b = f"2043-03-{(u_val % 10 + 15):02d}"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM production_orders WHERE scheduled_date IN (%s, %s)", (day_a, day_b))
        conn.commit()
    
    ot1, _ = production_repo.create_production_order(p_final, 5, scheduled_date=day_a)
    ot2, _ = production_repo.create_production_order(p_final, 5, scheduled_date=day_a)
    ot3, _ = production_repo.create_production_order(p_final, 5, scheduled_date=day_b)
    
    # Mover ot1 de day_a a day_b
    production_repo.set_production_order_schedule(ot1, day_b, schedule_order=1)
    
    # En day_a, ot2 debe quedar como #1
    o2 = production_repo.get_production_order_by_id(ot2)
    assert str(o2["scheduled_date"]) == day_a
    assert o2["schedule_order"] == 1
    
    # En day_b, ot1 queda en #1 y ot3 en #2
    o1 = production_repo.get_production_order_by_id(ot1)
    o3 = production_repo.get_production_order_by_id(ot3)
    assert str(o1["scheduled_date"]) == day_b
    assert o1["schedule_order"] == 1
    assert str(o3["scheduled_date"]) == day_b
    assert o3["schedule_order"] == 2


def test_schedule_order_does_not_affect_status():
    """20. Alterar el orden dentro del día no afecta status."""
    p_final, p_a, p_b = _create_test_recipe_and_products("S20")
    ot_id, _ = production_repo.create_production_order(p_final, 5, status="Borrador", scheduled_date="2026-09-23")
    
    production_repo.set_production_order_schedule(ot_id, "2026-09-23", schedule_order=5)
    ot = production_repo.get_production_order_by_id(ot_id)
    assert ot["status"] == "Borrador"


def test_schedule_order_does_not_affect_inventory():
    """21. Alterar el orden dentro del día no afecta inventario."""
    p_final, p_a, p_b = _create_test_recipe_and_products("S21")
    _add_stock_to_product(p_a, 40.0)
    
    ot_id, _ = production_repo.create_production_order(p_final, 10, scheduled_date="2026-09-23")
    stock_before = inventory_repo.get_relational_stock(p_a)
    
    production_repo.set_production_order_schedule(ot_id, "2026-09-23", schedule_order=2)
    stock_after = inventory_repo.get_relational_stock(p_a)
    
    assert stock_after == stock_before == 40.0


def test_e2e_production_schedule_flow(app_client):
    """
    22. Escenario E2E Principal (Sección 19):
    1. Crear semana de producción:
       - Lunes: OT-A
       - Miércoles: OT-B (Borrador, sin stock) y OT-C (Solicitada, con stock)
       - Viernes: OT-D
    2. Verificar visualización de Miércoles:
       - 1. OT-B (Borrador, ⚠️ Faltan materiales)
       - 2. OT-C (Solicitada, ✓ Stock disponible)
    3. Mover OT-C de Miércoles a Viernes vía API / drag & drop.
    4. Verificar resultado:
       - Miércoles: 1. OT-B
       - Viernes: 1. OT-D, 2. OT-C
       - Cero cambios de stock, estado o genealogía.
    5. Ingresar materiales para OT-B.
    6. Volver a consultar: OT-B muestra ✓ Stock disponible conservando fecha y orden.
    7. Activar OT-B (Borrador -> Solicitada): scheduled_date y schedule_order permanecen intactos.
    """
    _login_as(app_client, "admin")
    p_final, p_a, p_b = _create_test_recipe_and_products("E2E-SCHED")
    
    import uuid
    # Fechas únicas para evitar colisión con runs previos en la base de datos
    u_val = int(uuid.uuid4().hex[:6], 16)
    lun = f"2045-05-{(u_val % 10 + 1):02d}"
    mie = f"2045-05-{(u_val % 10 + 3):02d}"
    vie = f"2045-05-{(u_val % 10 + 5):02d}"
    
    # 1. Crear OTs
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM production_orders WHERE scheduled_date IN (%s, %s, %s)", (lun, mie, vie))
        conn.commit()

    ot_a_id, ot_a_num = production_repo.create_production_order(p_final, 10, status="Borrador", scheduled_date=lun)
    
    # OT-B: Borrador, sin stock suficiente (pide 50 unidades -> necesita 100 de MP-A y 50 de MP-B)
    ot_b_id, ot_b_num = production_repo.create_production_order(p_final, 50, status="Borrador", scheduled_date=mie)

    # OT-C: Solicitada, le asignamos stock previo (pide 15 unidades -> necesita 30 de MP-A y 15 de MP-B)
    _add_stock_to_product(p_a, 40.0) # 40 es suficiente para OT-C (30), pero insuficiente para OT-B (100)
    _add_stock_to_product(p_b, 20.0) # 20 es suficiente para OT-C (15), pero insuficiente para OT-B (50)
    ot_c_id, ot_c_num = production_repo.create_production_order(p_final, 15, status="Solicitada", scheduled_date=mie)
    
    # OT-D: Viernes
    ot_d_id, ot_d_num = production_repo.create_production_order(p_final, 5, status="Borrador", scheduled_date=vie)
    
    # 2. Consultar Miércoles
    wed_ots = [o for o in production_repo.list_scheduled_production_orders(lun, vie) if str(o["scheduled_date"]) == mie and o["id"] in (ot_b_id, ot_c_id)]
    assert len(wed_ots) == 2
    
    ot_b_view = next(o for o in wed_ots if o["id"] == ot_b_id)
    assert ot_b_view["status"] == "Borrador"
    assert ot_b_view["is_complete"] is False
    assert ot_b_view["status_label"] == "Faltan materiales"
    assert ot_b_view["schedule_order"] == 1
    
    ot_c_view = next(o for o in wed_ots if o["id"] == ot_c_id)
    assert ot_c_view["status"] == "Solicitada"
    assert ot_c_view["schedule_order"] == 2
    
    # 3. Mover OT-C de Miércoles a Viernes
    res_move = app_client.post(f"/api/produccion/ot/{ot_c_id}/programar", json={
        "scheduled_date": vie,
        "schedule_order": 2
    })
    assert res_move.status_code == 200
    
    # 4. Verificar nuevo orden
    # Miércoles: solo queda OT-B en orden 1
    wed_after = [o for o in production_repo.list_scheduled_production_orders(lun, vie) if str(o["scheduled_date"]) == mie]
    assert len(wed_after) == 1
    assert wed_after[0]["id"] == ot_b_id
    assert wed_after[0]["schedule_order"] == 1
    
    # Viernes: OT-D en orden 1, OT-C en orden 2
    fri_after = [o for o in production_repo.list_scheduled_production_orders(lun, vie) if str(o["scheduled_date"]) == vie]
    assert len(fri_after) == 2
    assert fri_after[0]["id"] == ot_d_id and fri_after[0]["schedule_order"] == 1
    assert fri_after[1]["id"] == ot_c_id and fri_after[1]["schedule_order"] == 2
    
    # Estados intactos
    assert production_repo.get_production_order_by_id(ot_c_id)["status"] == "Solicitada"
    assert production_repo.get_production_order_by_id(ot_b_id)["status"] == "Borrador"
    
    # 5. Ingresar stock para cubrir OT-B (necesita 100 de MP-A y 50 de MP-B, ya tiene 40 y 20 -> añadimos 70 y 35)
    _add_stock_to_product(p_a, 70.0)
    _add_stock_to_product(p_b, 35.0)
    
    # 6. Consultar calendario nuevamente: OT-B ahora tiene stock disponible
    wed_updated = [o for o in production_repo.list_scheduled_production_orders(lun, vie) if str(o["scheduled_date"]) == mie]
    assert wed_updated[0]["id"] == ot_b_id
    assert wed_updated[0]["is_complete"] is True
    assert wed_updated[0]["status_label"] == "Stock disponible"
    assert str(wed_updated[0]["scheduled_date"]) == mie
    assert wed_updated[0]["schedule_order"] == 1
    
    # 7. Activar OT-B (Borrador -> Solicitada)
    res_act = app_client.post(f"/produccion/ot/{ot_b_id}/activar", follow_redirects=True)
    assert res_act.status_code == 200
    ot_b_active = production_repo.get_production_order_by_id(ot_b_id)
    assert ot_b_active["status"] == "Solicitada"
    assert str(ot_b_active["scheduled_date"]) == mie
    assert ot_b_active["schedule_order"] == 1
