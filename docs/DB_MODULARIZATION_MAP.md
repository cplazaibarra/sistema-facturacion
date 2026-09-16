# MAPA DE MODULARIZACIÓN DE `db.py` (FASE 5)

**Fecha:** 2026-09-15  
**Líneas Totales de `db.py`:** ~4,850  
**Funciones Auditadas:** 121  

---

## 1. Clasificación por Dominios

| Dominio | Cantidad de Funciones | Archivo Destino | Riesgo General |
|---|---|---|---|
| **CORE** | 1 (`get_connection`) | `core/database.py` | CRITICAL |
| **MIGRATIONS/SEEDS** | 2 (`init_db`, `seed_data_if_empty`) | `core/database.py` / `tools/` | LOW |
| **UTILITIES** | 2 (`is_valid_email`, `normalize_rut_str`) | `core/utils.py` | LOW |
| **LEGACY** | 4 (`get_page_data`, `set_page_data`, `list_sales_entries`, `insert_sales_entry`) | `repositories/legacy_repo.py` | MEDIUM |
| **AUTH / USERS / RBAC** | 10 (`list_roles`, `get_role`, `insert_role`, `update_role`, `delete_role`, `list_users`, `get_user`, `insert_user`, `update_user`, `delete_user`) | `repositories/auth_repo.py` | MEDIUM |
| **PRODUCTS** | 12 (`list_products`, `insert_product`, `get_product`, `update_product`, `delete_product`, `rename_category`, `delete_category`, `list_product_suppliers`, `list_products_by_supplier`, `add_product_supplier`, `remove_product_supplier`, `get_product_calculated_cost`) | `repositories/products_repo.py` | HIGH (por regla VPP) |
| **SUPPLIERS** | 10 (`list_suppliers`, `get_supplier`, `insert_supplier`, `update_supplier`, `delete_supplier`, `list_supplier_contacts`, `get_supplier_contact`, `insert_supplier_contact`, `update_supplier_contact`, `delete_supplier_contact`) | `repositories/suppliers_repo.py` | LOW |
| **CLIENTS** | 7 (`list_clients`, `get_client_by_id`, `insert_client`, `update_client`, `delete_client`, `get_client_by_rut`, `search_clients`, `upsert_client_by_rut`) | `repositories/clients_repo.py` | LOW |
| **REPORTING** | 8 (`get_sales_metrics`, `get_sales_chart_data`, `get_top_products`, `get_purchase_years`, `get_purchased_products_matrix`, `get_income_report_data`, `get_cash_flow_data`, `get_cash_flow_data_weekly`, `get_system_notifications`) | `repositories/reporting_repo.py` | MEDIUM |
| **PURCHASES** | 13 (`get_next_oc_number`, `create_purchase_order`, `update_purchase_order`, `list_purchase_orders`, `get_purchase_order`, `approve_purchase_order`, `anular_purchase_order`, `get_purchase_order_items`, `list_active_purchase_orders_by_supplier`, `get_purchase_order_entries`, `list_entries_missing_invoice`, `create_purchase_invoice`, `list_purchase_invoices`) | `repositories/purchases_repo.py` | HIGH |
| **FINANCE** | 16 (`list_bank_accounts`, `get_bank_account`, `insert_bank_account`, `update_bank_account`, `delete_bank_account`, `get_sale_payments_map`, `get_sale_payment`, `upsert_sale_payment`, `list_sale_payment_items`, `update_sale_payment_item_approval`, `insert_sale_payment_item`, `update_sale_payment_item_proof`, `update_sale_payment_item_amount_date`, `delete_sale_payment_item`, `get_sale_payment_items_totals`, `count_pending_invoices`, `update_invoice_payment_status`, `register_purchase_payment`, `list_pending_invoice_alerts`, `link_invoice_to_entry`) | `repositories/finance_repo.py` | HIGH |
| **INVENTORY** | 16 (`get_inventory_entry_detail`, `register_inventory_entry`, `get_lot_stock_by_product`, `get_all_lot_stock`, `consume_lots_for_sale`, `get_sale_lot_movements`, `get_lot_traceability`, `record_inventory_movement`, `get_relational_stock`, `get_relational_stock_by_sku`, `consume_fifo_lots`, `get_stock_with_dual_read`, `get_product_available_stock`, `validate_stock_for_sale`, `discount_stock_for_sale`, `list_inventory_entries`) | `repositories/inventory_repo.py` | CRITICAL |
| **SALES** | 9 (`get_next_sale_number`, `list_sales`, `count_sales`, `list_sales_page`, `list_sales_page_light`, `get_sale_payments_for_sales`, `get_sale`, `insert_sale`, `update_sale`, `update_quotation_status`, `delete_sale`) | `repositories/sales_repo.py` | HIGH |
| **PRODUCTION** | 1 (`get_next_ot_number`, + persistencia actualmente dispersa en rutas que se consolidará) | `repositories/production_repo.py` | HIGH |

---

## 2. Mapa Detallado de Funciones

| Función | Líneas Aprox. | Dominio | Tablas Utilizadas | Recibe `conn` | Controla Transacción | Riesgo |
|---|---|---|---|---|---|---|
| `get_connection` | 518-526 | CORE | N/A | No | No | CRITICAL |
| `init_db` | 529-540 | MIGRATIONS | `schema_migrations` | No | Sí | LOW |
| `seed_data_if_empty` | 543-816 | SEEDS | Múltiples | No | Sí | LOW |
| `get_page_data` | 820-827 | LEGACY | `page_data` | No | No | MEDIUM |
| `set_page_data` | 830-838 | LEGACY | `page_data` | No | Sí | MEDIUM |
| `list_sales_entries` | 841-853 | LEGACY | `sales_entries` | No | No | LOW |
| `insert_sales_entry` | 856-884 | LEGACY | `sales_entries` | No | Sí | LOW |
| `list_roles` | 1057-1063 | AUTH | `roles` | No | No | LOW |
| `get_role` | 1066-1074 | AUTH | `roles` | No | No | LOW |
| `insert_role` | 1077-1094 | AUTH | `roles` | No | Sí | LOW |
| `update_role` | 1097-1107 | AUTH | `roles` | No | Sí | LOW |
| `delete_role` | 1110-1114 | AUTH | `roles` | No | Sí | LOW |
| `list_users` | 1118-1130 | AUTH | `users`, `roles` | No | No | LOW |
| `get_user` | 1133-1147 | AUTH | `users`, `roles` | No | No | LOW |
| `insert_user` | 1150-1176 | AUTH | `users` | No | Sí | MEDIUM |
| `update_user` | 1179-1216 | AUTH | `users` | No | Sí | MEDIUM |
| `delete_user` | 1219-1223 | AUTH | `users` | No | Sí | LOW |
| `list_products` | 887-903 | PRODUCTS | `products` | No | No | LOW |
| `insert_product` | 906-969 | PRODUCTS | `products` | No | Sí | MEDIUM |
| `get_product` | 972-989 | PRODUCTS | `products` | No | No | LOW |
| `update_product` | 992-1047 | PRODUCTS | `products` | No | Sí | MEDIUM |
| `delete_product` | 1050-1054 | PRODUCTS | `products` | No | Sí | LOW |
| `list_product_suppliers` | 2316-2330 | PRODUCTS | `product_suppliers`, `suppliers` | No | No | LOW |
| `list_products_by_supplier` | 2333-2346 | PRODUCTS | `product_suppliers`, `products` | No | No | LOW |
| `add_product_supplier` | 2349-2364 | PRODUCTS | `product_suppliers` | No | Sí | LOW |
| `remove_product_supplier` | 2367-2377 | PRODUCTS | `product_suppliers` | No | Sí | LOW |
| `rename_category` | 2380-2391 | PRODUCTS | `products` | No | Sí | LOW |
| `delete_category` | 2394-2407 | PRODUCTS | `products` | No | Sí | LOW |
| `get_product_calculated_cost` | 3681-3722 | PRODUCTS | `products`, `inventory_entries`, `inventory_entry_items` | No | No | HIGH (VPP) |
| `list_suppliers` | 2143-2153 | SUPPLIERS | `suppliers` | No | No | LOW |
| `get_supplier` | 2156-2168 | SUPPLIERS | `suppliers` | No | No | LOW |
| `insert_supplier` | 2171-2199 | SUPPLIERS | `suppliers` | No | Sí | LOW |
| `update_supplier` | 2202-2228 | SUPPLIERS | `suppliers` | No | Sí | LOW |
| `delete_supplier` | 2231-2236 | SUPPLIERS | `suppliers` | No | Sí | LOW |
| `list_supplier_contacts` | 2239-2251 | SUPPLIERS | `supplier_contacts` | No | No | LOW |
| `get_supplier_contact` | 2254-2266 | SUPPLIERS | `supplier_contacts` | No | No | LOW |
| `insert_supplier_contact` | 2269-2286 | SUPPLIERS | `supplier_contacts` | No | Sí | LOW |
| `update_supplier_contact` | 2289-2306 | SUPPLIERS | `supplier_contacts` | No | Sí | LOW |
| `delete_supplier_contact` | 2309-2313 | SUPPLIERS | `supplier_contacts` | No | Sí | LOW |
| `is_valid_email` | 4537-4557 | UTILITIES | N/A | No | No | LOW |
| `normalize_rut_str` | 4560-4572 | UTILITIES | N/A | No | No | LOW |
| `list_clients` | 4517-4525 | CLIENTS | `clients` | No | No | LOW |
| `get_client_by_id` | 4527-4531 | CLIENTS | `clients` | No | No | LOW |
| `insert_client` | 4575-4616 | CLIENTS | `clients` | No | Sí | LOW |
| `update_client` | 4618-4652 | CLIENTS | `clients` | No | Sí | LOW |
| `delete_client` | 4654-4658 | CLIENTS | `clients` | No | Sí | LOW |
| `get_client_by_rut` | 4661-4686 | CLIENTS | `clients` | No | No | LOW |
| `search_clients` | 4689-4714 | CLIENTS | `clients` | No | No | LOW |
| `upsert_client_by_rut` | 4717-4767 | CLIENTS | `clients` | No | Sí | LOW |
| `get_sales_metrics` | 1895-2009 | REPORTING | `sales`, `page_data` | No | No | MEDIUM |
| `get_sales_chart_data` | 2012-2060 | REPORTING | `sales` | No | No | LOW |
| `get_top_products` | 2063-2140 | REPORTING | `sales` | No | No | LOW |
| `get_purchase_years` | 2710-2724 | REPORTING | `purchase_orders` | No | No | LOW |
| `get_purchased_products_matrix` | 2726-2828 | REPORTING | `purchase_orders`, `purchase_order_items`, `products` | No | No | MEDIUM |
| `get_income_report_data` | 3748-3863 | REPORTING | `sales` | No | No | MEDIUM |
| `get_cash_flow_data` | 3866-4029 | REPORTING | `sales`, `sale_payments`, `purchase_invoices` | No | No | MEDIUM |
| `get_cash_flow_data_weekly` | 4032-4200 | REPORTING | `sales`, `sale_payments`, `purchase_invoices` | No | No | MEDIUM |
| `get_system_notifications` | 4770-4849 | REPORTING | `purchase_orders`, `sales`, `products` | No | No | LOW |
| `get_next_oc_number` | 2414-2429 | PURCHASES | `purchase_order_number_seq` | Sí (opcional) | Condicional | HIGH |
| `create_purchase_order` | 2467-2496 | PURCHASES | `purchase_orders`, `purchase_order_items` | No | Sí | HIGH |
| `update_purchase_order` | 2498-2528 | PURCHASES | `purchase_orders`, `purchase_order_items` | No | Sí | HIGH |
| `list_purchase_orders` | 2530-2584 | PURCHASES | `purchase_orders`, `suppliers`, `users` | No | No | MEDIUM |
| `get_purchase_order` | 2586-2626 | PURCHASES | `purchase_orders`, `suppliers`, `users` | No | No | MEDIUM |
| `approve_purchase_order` | 2628-2640 | PURCHASES | `purchase_orders` | No | Sí | HIGH |
| `anular_purchase_order` | 2642-2676 | PURCHASES | `purchase_orders` | No | Sí | HIGH |
| `get_purchase_order_items` | 2678-2693 | PURCHASES | `purchase_order_items`, `products` | No | No | LOW |
| `list_active_purchase_orders_by_supplier` | 2695-2708 | PURCHASES | `purchase_orders` | No | No | LOW |
| `get_purchase_order_entries` | 2830-2871 | PURCHASES | `inventory_entries`, `inventory_entry_items` | No | No | MEDIUM |
| `list_entries_missing_invoice` | 4484-4500 | PURCHASES | `inventory_entries`, `purchase_invoices` | No | No | LOW |
| `create_purchase_invoice` | 4207-4249 | PURCHASES | `purchase_invoices` | No | Sí | HIGH |
| `get_purchase_invoice` | 4252-4268 | PURCHASES | `purchase_invoices` | No | No | LOW |
| `get_purchase_invoice_products_detail` | 4271-4342 | PURCHASES | `purchase_invoices`, `inventory_entry_items` | No | No | MEDIUM |
| `list_purchase_invoices` | 4345-4379 | PURCHASES | `purchase_invoices`, `suppliers` | No | No | LOW |
| `list_bank_accounts` | 1522-1532 | FINANCE | `bank_accounts` | No | No | LOW |
| `get_bank_account` | 1535-1547 | FINANCE | `bank_accounts` | No | No | LOW |
| `insert_bank_account` | 1550-1571 | FINANCE | `bank_accounts` | No | Sí | LOW |
| `update_bank_account` | 1574-1595 | FINANCE | `bank_accounts` | No | Sí | LOW |
| `delete_bank_account` | 1598-1602 | FINANCE | `bank_accounts` | No | Sí | LOW |
| `get_sale_payments_map` | 1605-1617 | FINANCE | `sale_payments` | No | No | LOW |
| `get_sale_payment` | 1620-1634 | FINANCE | `sale_payments` | No | No | LOW |
| `upsert_sale_payment` | 1637-1776 | FINANCE | `sale_payments`, `sales`, `sale_payment_items` | Sí (opcional) | Condicional | HIGH |
| `list_sale_payment_items` | 1779-1810 | FINANCE | `sale_payment_items`, `bank_accounts` | No | No | LOW |
| `update_sale_payment_item_approval` | 1813-1824 | FINANCE | `sale_payment_items` | No | Sí | MEDIUM |
| `insert_sale_payment_item` | 1827-1846 | FINANCE | `sale_payment_items` | No | Sí | MEDIUM |
| `update_sale_payment_item_proof` | 1849-1856 | FINANCE | `sale_payment_items` | No | Sí | LOW |
| `update_sale_payment_item_amount_date` | 1859-1866 | FINANCE | `sale_payment_items` | No | Sí | LOW |
| `delete_sale_payment_item` | 1869-1873 | FINANCE | `sale_payment_items` | No | Sí | LOW |
| `get_sale_payment_items_totals` | 1876-1892 | FINANCE | `sale_payment_items` | No | No | LOW |
| `count_pending_invoices` | 4382-4390 | FINANCE | `purchase_invoices` | No | No | LOW |
| `update_invoice_payment_status` | 4393-4407 | FINANCE | `purchase_invoices` | No | Sí | MEDIUM |
| `register_purchase_payment` | 4410-4461 | FINANCE | `purchase_invoices` | Sí (opcional) | Condicional | HIGH |
| `list_pending_invoice_alerts` | 4464-4481 | FINANCE | `purchase_invoices` | No | No | LOW |
| `link_invoice_to_entry` | 4503-4514 | FINANCE | `purchase_invoices` | No | Sí | LOW |
| `get_inventory_entry_detail` | 2873-2918 | INVENTORY | `inventory_entries`, `inventory_entry_items` | No | No | LOW |
| `register_inventory_entry` | 2921-3097 | INVENTORY | `inventory_entries`, `inventory_entry_items`, `lot_stock`, `inventory_movements` | No | Sí | CRITICAL |
| `get_lot_stock_by_product` | 3100-3115 | INVENTORY | `lot_stock` | No | No | LOW |
| `get_all_lot_stock` | 3118-3134 | INVENTORY | `lot_stock`, `products` | No | No | LOW |
| `consume_lots_for_sale` | 3137-3177 | INVENTORY | `lot_stock`, `sale_lot_movements` | Sí (opcional) | Condicional | CRITICAL |
| `get_sale_lot_movements` | 3180-3195 | INVENTORY | `sale_lot_movements` | No | No | LOW |
| `get_lot_traceability` | 3198-3244 | INVENTORY | `lot_stock`, `sale_lot_movements`, `inventory_entries` | No | No | MEDIUM |
| `record_inventory_movement` | 3251-3324 | INVENTORY | `inventory_movements` | Sí (opcional) | Condicional | CRITICAL |
| `get_relational_stock` | 3327-3340 | INVENTORY | `inventory_movements` | Sí (opcional) | No | CRITICAL |
| `get_relational_stock_by_sku` | 3343-3361 | INVENTORY | `inventory_movements`, `products` | Sí (opcional) | No | CRITICAL |
| `consume_fifo_lots` | 3364-3421 | INVENTORY | `lot_stock`, `sale_lot_movements` | Sí (opcional) | Condicional | CRITICAL |
| `get_stock_with_dual_read` | 3424-3475 | INVENTORY | `inventory_movements`, `lot_stock`, `page_data` | No | No | CRITICAL |
| `get_product_available_stock` | 3478-3541 | INVENTORY | `inventory_movements`, `lot_stock` | No | No | CRITICAL |
| `validate_stock_for_sale` | 3544-3575 | INVENTORY | `products`, `lot_stock` | No | No | CRITICAL |
| `discount_stock_for_sale` | 3578-3678 | INVENTORY | `products`, `lot_stock`, `inventory_movements`, `page_data` | Sí (opcional) | Condicional | CRITICAL |
| `list_inventory_entries` | 3724-3745 | INVENTORY | `inventory_entries`, `suppliers` | No | No | LOW |
| `get_next_sale_number` | 2432-2447 | SALES | `sales_number_seq` | Sí (opcional) | Condicional | HIGH |
| `list_sales` | 1228-1273 | SALES | `sales` | No | No | LOW |
| `count_sales` | 1276-1295 | SALES | `sales` | No | No | LOW |
| `list_sales_page` | 1298-1334 | SALES | `sales` | No | No | LOW |
| `list_sales_page_light` | 1337-1367 | SALES | `sales` | No | No | LOW |
| `get_sale_payments_for_sales` | 1370-1387 | SALES | `sale_payments` | No | No | LOW |
| `get_sale` | 1390-1410 | SALES | `sales` | No | No | MEDIUM |
| `insert_sale` | 1413-1456 | SALES | `sales` | Sí (opcional) | Condicional | HIGH |
| `update_sale` | 1459-1493 | SALES | `sales` | No | Sí | MEDIUM |
| `update_quotation_status` | 1496-1510 | SALES | `sales` | No | Sí | MEDIUM |
| `delete_sale` | 1513-1517 | SALES | `sales` | No | Sí | LOW |
| `get_next_ot_number` | 2450-2465 | PRODUCTION | `production_order_number_seq` | Sí (opcional) | Condicional | HIGH |
