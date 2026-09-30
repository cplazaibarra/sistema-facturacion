# Informe de aislamiento de base de tests

**Fecha:** 2026-09-30T02:25:36+00:00
**Base normal:** `facturacion`
**Base de plantilla test (persistente, inmutable durante suites):** `facturacion_cleanup_verify`
**Aislamiento por suite:** copia PostgreSQL efímera `facturacion_test_run_<12 hex>`; se elimina en `finally`.
**Protección:** pytest requiere URLs iguales, `APP_ENV=testing`, `ERP_TEST_MODE=1`, host/DB_NAME coincidentes y COMMENT de PostgreSQL con ID del run; cada conexión de app revalida configuración.

Los conteos normal/template se toman con transacción `READ ONLY`. Cada suite clona la plantilla, ejecuta tests que pueden hacer commit/concurrencia y elimina la copia completa al finalizar. No hay rollback forzado sobre tests transaccionales.

## Base normal antes

| Entidad | Cantidad |
|---|---:|
| Productos | 82 |
| Ventas | 28 |
| Órdenes de Compra | 9 |
| Recepciones | 14 |
| Movimientos | 41 |
| Lotes | 12 |
| OT | 4 |
| Clientes | 16 |
| Proveedores | 14 |
| Cuentas | 15 |
| Deudas | 4 |
| Revaluaciones | 1 |
| Cotizaciones | 14 |

## Suites y comparación de conteos

### Suite completa #1: GREEN

| Entidad | Antes | Después | Delta |
|---|---:|---:|---:|
| Productos | 82 | 82 | 0 |
| Ventas | 28 | 28 | 0 |
| Órdenes de Compra | 9 | 9 | 0 |
| Recepciones | 14 | 14 | 0 |
| Movimientos | 41 | 41 | 0 |
| Lotes | 12 | 12 | 0 |
| OT | 4 | 4 | 0 |
| Clientes | 16 | 16 | 0 |
| Proveedores | 14 | 14 | 0 |
| Cuentas | 15 | 15 | 0 |
| Deudas | 4 | 4 | 0 |
| Revaluaciones | 1 | 1 | 0 |
| Cotizaciones | 14 | 14 | 0 |

### Suite completa #2: GREEN

| Entidad | Antes | Después | Delta |
|---|---:|---:|---:|
| Productos | 82 | 82 | 0 |
| Ventas | 28 | 28 | 0 |
| Órdenes de Compra | 9 | 9 | 0 |
| Recepciones | 14 | 14 | 0 |
| Movimientos | 41 | 41 | 0 |
| Lotes | 12 | 12 | 0 |
| OT | 4 | 4 | 0 |
| Clientes | 16 | 16 | 0 |
| Proveedores | 14 | 14 | 0 |
| Cuentas | 15 | 15 | 0 |
| Deudas | 4 | 4 | 0 |
| Revaluaciones | 1 | 1 | 0 |
| Cotizaciones | 14 | 14 | 0 |

## Base persistente de test

| Entidad | Antes suites | Después suite #2 | Delta |
|---|---:|---:|---:|
| Productos | 13378 | 13378 | 0 |
| Ventas | 1725 | 1725 | 0 |
| Órdenes de Compra | 1580 | 1580 | 0 |
| Recepciones | 1975 | 1975 | 0 |
| Movimientos | 7469 | 7469 | 0 |
| Lotes | 1778 | 1778 | 0 |
| OT | 1883 | 1883 | 0 |
| Clientes | 10 | 10 | 0 |
| Proveedores | 1578 | 1578 | 0 |
| Cuentas | 54 | 54 | 0 |
| Deudas | 17 | 17 | 0 |
| Revaluaciones | 0 | 0 | 0 |
| Cotizaciones | 35 | 35 | 0 |

## Auditoría del harness

- `tests/conftest.py` anterior cargaba `.env` y luego importaba `app`; `app.py` inicializa esquema en import y podía conectarse a `facturacion`.
- Muchas integraciones hacen `commit()` en varias conexiones y limpian sólo parte de sus documentos; rollback global no sería seguro.
- Las pruebas de concurrencia, idempotencia, transacciones y migraciones conservan commits reales dentro de la DB efímera.
- Unit/integration/security todas corren en la copia temporal. Browser/E2E externos no se encontraron como tests ejecutables en el árbol; scripts que usen pytest heredan el guard.
- Fábricas siguen distribuidas; el aislamiento de DB por suite contiene fixtures heredados incluso cuando el teardown local es incompleto.
- Tests nuevos del guard cubren permitido, development/production bloqueado, URL ausente, configuración ambigua y marker incorrecto.
- La suite de migraciones crea `facturacion_test_phase4_auto` y tiene teardown explícito; queda dentro del proceso ya autorizado y se destruye al terminar el módulo.

No se ejecutaron `TRUNCATE`, deletes ni limpieza de datos de la base normal. Los datos preexistentes permanecen intactos.
