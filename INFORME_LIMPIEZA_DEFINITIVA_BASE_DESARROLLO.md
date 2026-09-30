# Dry-run de limpieza definitiva de `facturacion`

**Estado:** RED — no se ejecutaron DELETE, UPDATE, TRUNCATE ni limpieza de documentos.  
**Base verificada:** `SELECT current_database()` devolvió `facturacion`.  
**Fecha de revisión:** 2026-09-27 (zona local America/Santiago).

## Backup previo

- **Archivo:** `backup_pre_limpieza_definitiva_20260927_1640.sql`
- **Tamaño:** 6.794.969 bytes (no vacío)
- **Fecha/hora del archivo:** 2026-09-27 16:40:18 -0300
- **SHA-256:** `d66ad1ac9337a181ab6b5a8c819954cdc7c6fd142ecf355d6321d7250ec667d8`
- **Estado:** `pg_dump` terminó con código 0; el dump SQL termina con el marcador de cierre PostgreSQL. La conexión y el nombre de base fueron verificados antes de continuar.

## Conteos exactos y dry-run

Los conteos se obtuvieron con `COUNT(*)` en `facturacion`; no son estimaciones de estadísticas PostgreSQL. “Eliminar candidato” es sólo la diferencia aritmética contra la meta y **no** un conjunto autorizado por dependencias.

| Entidad | Actual | Objetivo | Conservar previsto | Eliminar candidato aritmético |
|---|---:|---:|---:|---:|
| Productos | 15.048 | 70 aprox. | 59 productos referenciados directamente en una primera consulta de documentos retenidos; cierre incompleto | 14.978 si fueran exactamente 70; no calculable con seguridad aún |
| Ventas | 1.904 | 30 | 30 más recientes, excluyendo cotizaciones | 1.874 |
| Cotizaciones | 34 | 30 | 30 más recientes | 4 |
| Órdenes de Compra | 1.715 | 30 | 30 más recientes, más las fuentes que exijan lotes/documentos retenidos | 1.685 antes de dependencias |
| Recepciones | 2.077 | Dependencias | No calculado: incluye fuentes de lotes fuera de las OC retenidas | No calculable aún |
| Movimientos de inventario | 8.389 | Saldo/historia coherentes | No calculado: conservar documentos protegidos y definir saldos iniciales auditables | No calculable aún |
| `lot_stock` | 2.003 | Lotes de productos protegidos | No calculado | No calculable aún |
| Lotes | 2.003 | Orígenes y cantidades coherentes | No calculado: hay restricciones RESTRICT hacia OC, recepciones, OT y ventas | No calculable aún |
| Órdenes de Producción | 2.105 | 10 aprox. | 10 recientes, más OT que sean origen de lotes protegidos | 2.095 antes de dependencias |
| Clientes | 10 | ≤10 | 10 | 0 |
| Proveedores | 1.711 | 10–20 aprox. | Proveedores de OC/facturas/recepciones retenidas más muestra | No calculable aún |
| Cuentas bancarias | 186 | 10 | Cuentas de pagos/deudas/conciliaciones retenidos más muestra | 176 antes de dependencias |
| Deudas | 44 | 10 | 10 recientes con cuotas/pagos/auditoría | 34 |
| Facturas de compra | 518 | Dependencias | No calculado: referencias a OC/recepción/proveedor/cuenta | No calculable aún |
| Movimientos bancarios | 77 | Dependencias | No calculado | No calculable aún |
| Auditorías de conciliación | 55 | Dependencias | No calculado | No calculable aún |
| Cuotas de deuda | 139 | Dependencias | No calculado | No calculable aún |
| Pagos de deuda | 34 | Dependencias | No calculado | No calculable aún |
| Líneas de venta | 305 | Documentos retenidos | No calculado para toda la clausura de producto | No calculable aún |
| Pagos de venta | 723 | Documentos retenidos | No calculado | No calculable aún |
| Líneas de OC | 1.858 | Documentos retenidos | No calculado para la clausura completa | No calculable aún |
| Líneas de producción | 3.950 | OT retenidas y fuentes | No calculado para la clausura completa | No calculable aún |

## Dependencias y hallazgos que bloquean una eliminación segura

- El catálogo de `public` tiene 53 tablas y se inspeccionaron 82 claves foráneas. Varias relaciones relevantes usan `RESTRICT` o `NO ACTION`; borrar solamente las filas padre no es seguro ni basta con confiar en `CASCADE`.
- La primera unión de referencias directas de ventas, cotizaciones, OC, recepciones y 10 OT recientes identifica 59 productos. La meta de 70 parece posible en esa primera capa, pero el cierre de lotes añade orígenes fuera de los conjuntos recientes: en una medición parcial de 29 productos asociados se encontraron 16 lotes positivos, 3 OC fuente, 4 recepciones y 7 OT fuente. Esas dependencias requieren ampliar recursivamente los productos y documentos protegidos; no se terminó esa clausura y no se debe tratar el 59 como lista final.
- Los campos `sales.created_at`, `purchase_orders.created_at` y `production_orders.created_at` son `text`, no timestamps tipados. Se observaron formatos distintos en las muestras (`2026-10-05 10:00:00` y `2026-09-27T18:48:50+00:00`). No se fijó el conjunto “más reciente” hasta validar la conversión cronológica de todos los valores y resolver inválidos; ordenar texto puede seleccionar mal el documento.
- El reconciliador V2, antes de cualquier cambio, reporta: 15.047 productos activos; 229 candidatos cuantitativos; 182 diferencias ledger/lotes (delta absoluto 3.485); 90 snapshot/ledger; 45 snapshot/lotes; 4 reservas inconsistentes; 406 líneas de reserva ambiguas; 26 referencias huérfanas; 5.234 referencias genéricas/legacy y 3.887 movimientos sin tipo de referencia. Estos valores son la línea base de esta captura, no efectos de una limpieza.
- El estado actual contiene 8.389 movimientos. Sin cerrar primero los orígenes de los lotes retenidos y diseñar los saldos iniciales por producto, eliminar historia podría cambiar stock físico, disponibilidad, PPP o trazabilidad. No se usó el costo de catálogo como sustituto de `unit_cost` ni se actualizó cantidad alguna.
- Se verificó el objetivo de base exacto `facturacion`; no se consultó ni modificó `facturacion_cleanup_verify` ni bases `facturacion_test_run_*` durante el dry-run.

## Estado de ejecución y conteos posteriores

No hubo escritura de datos en la base. Por lo tanto, los conteos posteriores son idénticos a los anteriores y el delta de este trabajo es cero:

| Entidad | Antes | Después del dry-run | Delta |
|---|---:|---:|---:|
| Productos | 15.048 | 15.048 | 0 |
| Ventas | 1.904 | 1.904 | 0 |
| Cotizaciones | 34 | 34 | 0 |
| OC | 1.715 | 1.715 | 0 |
| Recepciones | 2.077 | 2.077 | 0 |
| Movimientos | 8.389 | 8.389 | 0 |
| Lotes / `lot_stock` | 2.003 / 2.003 | 2.003 / 2.003 | 0 |
| OT | 2.105 | 2.105 | 0 |
| Clientes | 10 | 10 | 0 |
| Proveedores | 1.711 | 1.711 | 0 |
| Cuentas | 186 | 186 | 0 |
| Deudas | 44 | 44 | 0 |

Suite de tests: no se volvió a ejecutar porque no hubo cambio de base/código en esta fase; la última línea base registrada sigue siendo 484 passed / 0 failed. No se generó backup post-limpieza, pues no se realizó limpieza.

## Resultado

La limpieza queda **DETENIDA ANTES DE DELETE**. Hacer ahora la poda por conteo, SKU/prefijo o relaciones directas no cumple el requisito de conservar grafos completos ni permite afirmar stock/PPP/Kardex coherentes. El backup está listo para la ejecución posterior, pero antes hace falta completar y revisar el cierre recursivo de los grafos (incluidos lotes fuente) y definir saldos iniciales con su valuación por producto; cualquier plan de borrado debe ejecutarse en una transacción con estas comprobaciones como condiciones de commit.
