# ROADMAP TÉCNICO DE ESTABILIZACIÓN Y OPTIMIZACIÓN ERP
**Sistema:** ERP Facturación / Bodega Miel (Single-Tenant)  
**Coordinación General:** erp-tech-lead  
**Fecha:** 14 de Septiembre de 2026  
**Estrategia:** Cambios progresivos, verificables, sin big-bang refactoring, con tests previos y capacidad de rollback garantizada.

---

## RESUMEN DE FASES

```text
FASE 0: Baseline y Protección               [COMPLETADA]
   │
   ▼
FASE 1: Seguridad Crítica y Control Acceso  [PRÓXIMA FASE]
   │
   ▼
FASE 2: Consistencia y Unificación de Stock
   │
   ▼
FASE 3: Atomicidad Transaccional y Concurrencia
   │
   ▼
FASE 4: Esquema Reproducible y Migraciones
   │
   ▼
FASE 5: Modularización Progresiva de db.py
   │
   ▼
FASE 6: Rendimiento, UX y Cierre Funcional
```

---

## DETALLE POR FASE

### FASE 0 — Baseline y Protección
* **Objetivo:** Establecer la línea base funcional verificable, asegurar conectividad de base de datos, configurar el arnés de pruebas automatizadas y registrar el estado inicial del sistema sin alterar código productivo.
* **Riesgos:** Ninguno (operación no invasiva de solo lectura y agregado de tests).
* **Dependencias:** Ninguna.
* **Agentes Responsables:** `erp-tech-lead` (coordinador), `erp-security-qa`.
* **Criterios de Entrada:** Repositorio en rama `main` con base de datos PostgreSQL activa.
* **Criterios de Salida:**
  - 5 archivos de especificación de agentes creados en `.agents/agents/`.
  - Arnés de tests configurado con `pytest`.
  - Smoke tests de los 12 módulos críticos ejecutados y pasando al 100%.
  - `docs/BASELINE_REPORT.md` y `docs/OPTIMIZATION_ROADMAP.md` publicados.
* **Tests Necesarios:** Tests unitarios de lógica pura (`test_core_logic.py`), tests de humo integrados (`test_smoke_routes.py`), tests base de autenticación (`test_auth_baseline.py`).
* **Rollback:** Descartar archivos agregados en `tests/` y `docs/`.
* **Estimación de Complejidad:** Baja (1 / 5).
* **Estado:** **COMPLETADA**.

---

### FASE 1 — Seguridad Crítica y Control de Acceso
* **Objetivo:** Eliminar las vulnerabilidades críticas de autenticación y autorización sin interrumpir la operación de los usuarios actuales: hashear contraseñas existentes de forma transparente, forzar `SECRET_KEY` desde entorno, incorporar protección anti-CSRF y activar control de permisos en backend.
* **Riesgos:**
  - Bloqueo de usuarios si la migración de contraseñas no es compatible con las claves actuales en texto plano.
  - Bloqueo de formularios si un token CSRF no se inyecta en alguna plantilla o petición `fetch`.
* **Dependencias:** Fase 0 completada.
* **Agentes Responsables:** `erp-security-qa` (líder técnico), `erp-frontend-ux` (tokens en vistas), `erp-tech-lead` (validación).
* **Criterios de Entrada:** Suite de tests de la Fase 0 pasando al 100%.
* **Criterios de Salida:**
  - `SECRET_KEY` cargada obligatoriamente desde `.env` (fallar si usa el valor por defecto).
  - Contraseñas almacenadas exclusivamente como hashes con `werkzeug.security.generate_password_hash`.
  - Migración al vuelo (on-login upgrade): si el password coincide en texto plano, se hashea y actualiza automáticamente en BD.
  - Protección CSRF activa mediante `Flask-WTF` en todos los formularios POST.
  - Decorador `@require_permission` implementado y aplicado en rutas administrativas y destructivas.
  - Servidor WSGI configurado con `debug=False` para entornos de producción.
* **Tests Necesarios:**
  - `tests/security/test_password_hashing.py`: verificación de hashes scrypt/pbkdf2.
  - `tests/security/test_csrf_protection.py`: rechazo de POSTs sin token CSRF.
  - `tests/security/test_rbac_enforcement.py`: verificación de 403 Forbidden para usuarios sin permiso.
* **Rollback:** Script de restauración de contraseñas a partir de backup previo y reversión de middleware CSRF.
* **Estimación de Complejidad:** Media (3 / 5).

---

### FASE 2 — Consistencia y Unificación de Stock
* **Objetivo:** Establecer una única fuente de verdad relacional para el inventario, eliminando el antipatrón de stock en la cadena JSON de `page_data(inventory_items)` y sincronizándolo de manera confiable con `lot_stock`.
* **Riesgos:**
  - Discrepancias entre las cantidades físicas actuales registradas en el JSON y las registradas en los lotes.
  - Interrupción temporal del cálculo de stock en cotizaciones o ventas.
* **Dependencias:** Fase 1 completada.
* **Agentes Responsables:** `erp-business-inventory` (reglas funcionales), `erp-backend-database` (modelo relacional), `erp-tech-lead` (aprobación).
* **Criterios de Entrada:**
  - `docs/INVENTORY_MIGRATION_PLAN.md` creado y aprobado.
  - Reporte de diferencias cuantitativas entre `page_data` y `lot_stock`.
* **Criterios de Salida:**
  - Tabla relacional consolidada de stock (ej. `product_stock` o columnas en `products` + `lot_stock`).
  - Lógica de lectura migrada a consultas SQL nativas (`SELECT sum(available_qty)...`).
  - Escrituras sincronizadas y validadas con tests de balance de existencias.
  - Desacople completo del JSON en `page_data`.
* **Tests Necesarios:**
  - `tests/unit/test_stock_calculations.py`: verificación de descuentos FIFO.
  - `tests/integration/test_inventory_flow.py`: ciclo completo compra -> ingreso -> venta -> saldo de stock.
* **Rollback:** Procedimiento de sincronización inversa manteniendo el snapshot de `page_data` antes de la transición.
* **Estimación de Complejidad:** Alta (4 / 5).

---

### FASE 3 — Atomicidad Transaccional y Concurrencia
* **Objetivo:** Garantizar transacciones ACID completas en operaciones compuestas y eliminar colisiones de concurrencia en folios y descuentos de stock.
* **Riesgos:**
  - Deadlocks si el orden de adquisición de bloqueos de fila no es uniforme.
  - Tiempos de espera excesivos si las transacciones abarcan operaciones de red o IO de archivos.
* **Dependencias:** Fase 2 completada.
* **Agentes Responsables:** `erp-backend-database` (líder técnico), `erp-business-inventory`.
* **Criterios de Entrada:** Inventario consolidado en tablas relacionales.
* **Criterios de Salida:**
  - La conversión de cotización a venta se ejecuta en una sola transacción con rollback completo ante fallo.
  - El ingreso de mercadería en bodega y creación de factura es atómico.
  - Se sustituye `SELECT MAX(id)+1` por secuencias nativas de PostgreSQL (`CREATE SEQUENCE oc_seq`, `vta_seq`, `cot_seq`).
  - Bloqueos selectivos (`SELECT ... FOR UPDATE`) al consultar disponibilidad de lote durante la venta.
* **Tests Necesarios:**
  - `tests/integration/test_transactions.py`: simulación de fallos inducidos a mitad de proceso verificando rollback.
  - `tests/integration/test_concurrency.py`: prueba de emisión concurrente de OCs y ventas evitando folios duplicados.
* **Rollback:** Reversión a secuencias basadas en tablas o funciones previas.
* **Estimación de Complejidad:** Media-Alta (3.5 / 5).

---

### FASE 4 — Esquema Reproducible y Migraciones
* **Objetivo:** Crear un mecanismo formal, versionado y liviano de migraciones que permita levantar la base de datos desde cero en cualquier entorno sin inconsistencias.
* **Riesgos:**
  - Diferencias entre esquemas de desarrollo y producción si las migraciones no son deterministas.
* **Dependencias:** Fase 3 completada.
* **Agentes Responsables:** `erp-backend-database`.
* **Criterios de Entrada:** Esquema transaccional consolidado.
* **Criterios de Salida:**
  - Creación de carpeta `migrations/` con scripts SQL versionados (`001_initial_schema.sql`, etc.).
  - Incorporación del DDL formal de `purchase_invoices`, `client_categories`, índices y secuencias.
  - Comando CLI simple o función `apply_migrations()` que registre migraciones aplicadas en una tabla `schema_migrations`.
  - Verificación exitosa de instalación en base de datos PostgreSQL limpia en prueba automatizada.
* **Tests Necesarios:**
  - `tests/integration/test_clean_install.py`: levantamiento completo de base de datos desde cero sin errores.
* **Rollback:** Scripts de `down` para cada migración aplicada.
* **Estimación de Complejidad:** Media (2.5 / 5).

---

### FASE 5 — Modularización Progresiva de db.py
* **Objetivo:** Desacoplar el archivo monolítico `db.py` (5,000 líneas) en módulos de repositorio por dominio, manteniendo total compatibilidad con las funciones existentes.
* **Riesgos:**
  - Ruptura de imports o referencias circulares.
* **Dependencias:** Fases 1 a 4 completadas con amplia cobertura de tests.
* **Agentes Responsables:** `erp-backend-database` (desacople), `erp-tech-lead` (revisión de interfaces).
* **Criterios de Entrada:** Cobertura de pruebas superior al 70% en funciones de acceso a datos.
* **Criterios de Salida:**
  - Creación del paquete `repositories/`:
    - `repositories/products.py`
    - `repositories/purchases.py`
    - `repositories/sales.py`
    - `repositories/inventory.py`
    - `repositories/users.py`
  - `db.py` actúa como fachada (facade) reexportando las funciones para no romper ningún controlador existente.
* **Tests Necesarios:**
  - Ejecución de la suite completa de tests de integración sin una sola modificación requerida en `routes/`.
* **Rollback:** `git revert` simple al ser una refactorización de estructura sin cambios funcionales.
* **Estimación de Complejidad:** Media (3 / 5).

---

### FASE 6 — UX, Rendimiento y Cierre Funcional
* **Objetivo:** Optimizar tiempos de respuesta, eliminar queries N+1, agregar paginación en módulos pesados, conectar reportes mockeados a datos reales y robustecer la experiencia de usuario.
* **Riesgos:**
  - Alteración visual no deseada en tablas existentes.
* **Dependencias:** Fases 1 a 5 completadas.
* **Agentes Responsables:** `erp-frontend-ux`, `erp-business-inventory`, `erp-backend-database`.
* **Criterios de Entrada:** Sistema estructuralmente estable y modular.
* **Criterios de Salida:**
  - Paginación server-side en Órdenes de Compra, Cuentas por Pagar y Ventas.
  - Eliminación de queries N+1 en el listado de Órdenes de Trabajo (`routes/produccion.py`).
  - Índices de rendimiento aplicados a columnas de fecha y claves foráneas.
  - Vistas de Reportes de Ventas, Compras y Gastos conectadas a datos reales agregados de PostgreSQL.
  - Protección contra doble clic en botones de envío en todas las plantillas.
  - Implementación de logging estructurado con rotación de archivos.
* **Tests Necesarios:**
  - `tests/integration/test_reports_data.py`: validación de cifras de reportes contra datos reales.
  - Pruebas de rendimiento y tiempo de respuesta en endpoints de listados.
* **Rollback:** Reversión individual por plantilla o query optimizada.
* **Estimación de Complejidad:** Media (3 / 5).
