# Maestro de Gastos Operacionales

## Alcance

Los gastos operacionales se administran como registros independientes en `operational_expenses`. No existe una lista fija de conceptos: el usuario puede crear tantos gastos como necesite, asignarles una categoría libre, monto fijo o estimado, frecuencia, regla de vencimiento, fechas de vigencia, cuenta habitual y beneficiario.

## Estados y acciones

- `Activo`: participa en las proyecciones futuras.
- `Inactivo`: conserva todos los datos y el historial, pero deja de proyectarse.
- Editar actualiza la configuración vigente y nunca modifica ocurrencias históricas.
- Eliminar sólo es físico cuando no existen ocurrencias. Si existe historial, la aplicación rechaza el borrado y ofrece desactivar.
- Todas las operaciones administrativas usan POST y quedan registradas en `operational_expense_audit`.

## Proyección de flujo de caja

`project_operational_expenses()` genera ocurrencias por gasto para el período consultado (semanal, mensual, trimestral o anual), respetando fecha de inicio, fecha de término y día/regla configurados. El reporte mensual y semanal suma esas ocurrencias únicamente en períodos futuros. Los pagos de ocurrencias con estado `Pagado` se incorporan a los gastos reales por su fecha de pago.

## Historial y datos financieros

Las ocurrencias se almacenan separadas del maestro para que cambiar monto, frecuencia o beneficiario no reescriba períodos anteriores. Las cuentas bancarias se referencian por ID al catálogo activo existente; no se crea un catálogo paralelo. El modelo deja preparada la vinculación de una ocurrencia pagada con cuenta y comprobante si el flujo financiero la requiere.

## Seguridad y UX

La pantalla está disponible en Administración → Gastos Operacionales, protegida por el permiso existente `administracion`. Incluye búsqueda, filtros de categoría/estado, alta, vista, edición, eliminación segura y desactivación/reactivación. Las acciones destructivas requieren confirmación y no se ejecutan mediante GET.

## Validación

Se agregaron pruebas de CRUD, auditoría, cambio de estado, proyección, exclusión de inactivos y protección del historial. La suite específica ejecutada fue `tests/integration/test_operational_expenses.py`.
