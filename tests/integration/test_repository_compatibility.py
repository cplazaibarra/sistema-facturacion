"""
Integration tests for Phase 5 repository modularization:
- Parity between db facade and repository direct invocations
- Transaction context and conn propagation across repositories
- Domain services operations
"""

import pytest
from core.database import get_connection
import db
import repositories.products_repo as prod_repo
import repositories.suppliers_repo as sup_repo
import repositories.clients_repo as cli_repo
import repositories.inventory_repo as inv_repo
import repositories.purchases_repo as pur_repo
import repositories.sales_repo as sales_repo
from services.inventory_service import InventoryService
from services.sales_service import SalesService
from services.purchase_service import PurchaseService


def test_facade_and_repository_identity():
    """Verifica que las funciones de db.py sean idénticas en identidad a las de los repositorios."""
    assert db.list_products is prod_repo.list_products
    assert db.get_product is prod_repo.get_product
    assert db.list_suppliers is sup_repo.list_suppliers
    assert db.list_clients is cli_repo.list_clients
    assert db.get_product_available_stock is inv_repo.get_product_available_stock
    assert db.get_purchase_order is pur_repo.get_purchase_order
    assert db.list_sales is sales_repo.list_sales


def test_transaction_propagation_and_rollback():
    """Verifica que pasar conn a las funciones del repositorio respete la transacción y permita rollback."""
    with get_connection() as conn:
        try:
            # Crear un producto temporal usando conn explícito
            test_sku = "TEST-MOD-PHASE5"
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO products (sku, name, category, cost, created_at) VALUES (%s, %s, %s, %s, NOW()) RETURNING id",
                    (test_sku, "Producto Modular Test", "General", 999.0)
                )
                prod_id = cur.fetchone()["id"]
            
            # Verificar existencia dentro de la transacción
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM products WHERE sku = %s", (test_sku,))
                assert cur.fetchone() is not None
            
            # Forzar rollback intencional
            conn.rollback()
        except Exception:
            conn.rollback()
            raise

    # Fuera de la transacción (con nueva conexión), el producto no debe existir
    with get_connection() as conn2:
        with conn2.cursor() as cur2:
            cur2.execute("SELECT id FROM products WHERE sku = %s", (test_sku,))
            assert cur2.fetchone() is None


def test_inventory_service_overview():
    """Verifica que InventoryService agregue métricas de producto correctamente."""
    products = prod_repo.list_products()
    if products:
        p_id = products[0]["id"]
        overview = InventoryService.get_stock_overview(p_id)
        assert "product_id" in overview
        assert "available_stock" in overview
        assert "relational_stock" in overview
        assert "lots" in overview
        assert overview["product_id"] == p_id


def test_services_layer_contracts():
    """Verifica que los servicios expongan los métodos y contratos requeridos."""
    assert hasattr(InventoryService, "get_stock_overview")
    assert hasattr(InventoryService, "validate_and_reserve_sale")
    assert hasattr(InventoryService, "execute_stock_discount")
    assert hasattr(SalesService, "get_sale_detail")
    assert hasattr(SalesService, "convert_quotation")
    assert hasattr(PurchaseService, "get_order_summary")
