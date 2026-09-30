# Clientes y cotizaciones: dirección de despacho y categoría

## Resultado

Se incorporó `clients.delivery_address` para separar el lugar habitual de
despacho de la dirección comercial (`direccion`). La categoría existente del
cliente (`clients.category_id`, alimentada por el catálogo de configuración de
listas de precios) se reutiliza; no se creó un catálogo paralelo.

La migración `000016_client_delivery_quote_snapshot` agrega ambos campos como
compatibles con datos existentes y dos columnas nullable en `sales`:

- `customer_delivery_address`
- `customer_category_snapshot`

Las cotizaciones históricas sin estos datos permanecen en `NULL` y se muestran
como “No informado”.

## Flujo

Al seleccionar un cliente en una cotización, la interfaz carga RUT, correo,
categoría y dirección de despacho desde `/api/clientes/buscar`. El POST vuelve a
resolver el cliente en backend por `customer_id` (o RUT como compatibilidad) y
guarda el snapshot; los valores enviados por el navegador no son autoridad para
un cliente ya existente.

Los borradores actualizan su snapshot si cambia el cliente. Una cotización
emitida conserva sus columnas snapshot y el detalle/impresión del modal usa esos
valores, sin consultar dinámicamente el maestro para documentos históricos.

La categoría mantiene el comportamiento comercial de precios que ya existía en
el ERP; esta funcionalidad no agrega reglas nuevas de precio, descuento, IVA o
margen.

## Archivos principales

- `migrations/000016_client_delivery_quote_snapshot.{up,down}.sql`
- `repositories/clients_repo.py`
- `repositories/sales_repo.py`
- `routes/ventas.py`
- `templates/clientes.html`
- `templates/nueva_cotizacion.html`
- `templates/cotizaciones.html`
- `templates/ventas.html`
- `tests/integration/test_client_quotation_customer_data.py`

## Validación

- Migración aplicada y registrada como `000016`.
- E2E controlada: cliente con dirección A y categoría `cat_1`; POST de
  cotización con dirección manipulada; el backend persistió dirección A y el
  nombre histórico “Mayorista”. Los datos temporales fueron eliminados.
- Pruebas específicas y smoke: **16 passed, 0 failed**.
- Suite completa ejecutada: **280 passed, 3 failed**. Las tres fallas son
  preexistentes y ajenas a este cambio, en paginación de órdenes de producción
  (2) y métricas/paginación de ventas (1). Las pruebas específicas y las rutas
  de clientes/cotizaciones permanecieron en verde.
