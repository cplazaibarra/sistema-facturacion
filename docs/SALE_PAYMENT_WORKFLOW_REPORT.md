# Flujo de registro de pagos de ventas

## Modelo reutilizado

El ERP ya disponía de `sale_payments` para el encabezado financiero y
`sale_payment_items` para transacciones y pagos parciales. Se amplió
`sale_payment_items` mediante la migración `000017_sale_payment_workflow` con
medio de pago, usuario/fecha de registro, snapshot de banco, observación y una
clave de idempotencia única. No se creó un catálogo bancario nuevo.

## Flujo implementado

En `/ventas`, el badge Pendiente/Retrasada abre el modal **Registrar Pago**.
Transferencia exige una cuenta activa del catálogo de cuentas bancarias, fecha,
monto y comprobante PDF/JPG/JPEG/PNG de hasta 10 MB. Efectivo exige fecha y
monto, sin cuenta ni comprobante.

El endpoint bloquea la venta con `FOR UPDATE`, valida saldo y cuenta activa,
inserta un único movimiento formal, actualiza el encabezado `sale_payments`,
registra historial y marca `sales.payment_status = 'Pagado'` sólo cuando el
acumulado de pagos alcanza el total. Un pago parcial permanece Pendiente.
La clave de idempotencia y el bloqueo protegen replay y doble submit.

Los comprobantes nuevos se almacenan en `uploads/comprobantes_pago_ventas`,
fuera de la ruta pública, y se entregan sólo mediante una ruta autenticada y
autorizada. Los comprobantes históricos mantienen compatibilidad con sus URLs
existentes.

## Integraciones

`sale_payments` continúa siendo la fuente financiera usada por CxC y flujo de
caja. No se generan ingresos paralelos. La fecha real indicada por el usuario
se conserva como `payment_date`; la fecha de vencimiento histórica no se
sobrescribe.

## Validación

- Transferencia válida, cuenta activa, comprobante, snapshot y acceso protegido.
- Efectivo sin cuenta ni comprobante.
- Pago completo, fecha, usuario, historial e idempotencia.
- Usuario sin permiso recibe HTTP 403.
- Pruebas específicas: **3 passed, 0 failed**; específicas más smoke:
  **17 passed, 0 failed**.
- Suite completa final: **285 passed, 1 failed**. La única falla es la prueba
  preexistente `test_sales_pagination_cases_a_to_u`, en una métrica global de
  ventas que ya no coincide con el universo de datos de prueba; no toca el
  endpoint ni el modelo de pagos.
