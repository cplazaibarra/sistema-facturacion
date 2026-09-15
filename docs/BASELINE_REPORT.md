# INFORME DE LÍNEA BASE (BASELINE REPORT)
**Proyecto:** ERP Sistema de Facturación / Bodega Miel  
**Fecha de Emisión:** 14 de Septiembre de 2026  
**Coordinador:** erp-tech-lead  
**Commit Git:** `140039451f9b4c9d84bb05c2b9001a6c3a9e9341` (Rama: `main`)  
**Modalidad de Operación:** SINGLE-TENANT (Empresa única)

---

## 1. Stack Tecnológico Detectado
- **Backend:** Python 3.14.4 (Runtime local venv) / Python 3.11-slim (Contenedor Docker), Flask 3.0.0, Werkzeug 3.0.1, Jinja2 3.1.6.
- **Base de Datos:** PostgreSQL 16.14 (Alpine Linux x86_64-pc-linux-musl), Driver `psycopg2-binary` 2.9.12 con `RealDictCursor`.
- **Frontend:** Jinja2 Server-Side Rendering (SSR), HTML5, CSS3 vanilla (44 KB en `static/css/style.css`), JavaScript ES6 vanilla sin frameworks SPA.
- **Librerías de UI (CDN):** FontAwesome 6.4.0, Chart.js 4.4.1, Flatpickr (con localización español `es.js`), Google Fonts (Outfit / Inter).
- **Documentos Comerciales:** ReportLab 5.0.0 y Pillow 12.3.0 para generación de órdenes de compra en PDF.
- **Contenerización y Despliegue:** Docker con `docker-compose.yml` (servicios: `facturacion-app` en puerto 5001 y `facturacion-db` en puerto 5432).
- **Testing:** `pytest` 9.1.1 integrado en `./venv/bin/pytest` con configuración `pytest.ini`.

---

## 2. Estado Actual de la Base de Datos
- **Conectividad:** Verificada y operativa vía socket localhost:5432.
- **Esquema:** Esquema `public` en PostgreSQL con **29 tablas activas**.
- **Volumen de datos registrado:**
  - `products`: 112 registros (catálogo de materias primas, insumos y productos terminados).
  - `product_recipes`: 55 recetas de fabricación (BOM).
  - `product_recipe_items`: 188 insumos formulados en recetas.
  - `sales`: 59 registros (ventas y cotizaciones históricas).
  - `purchase_orders`: 17 órdenes de compra emitidas.
  - `purchase_order_items`: 28 ítems comprados en OCs.
  - `inventory_entries`: 20 recepciones físicas registradas en bodega.
  - `inventory_entry_items`: 33 líneas de productos recibidos en bodega.
  - `purchase_invoices`: 10 facturas y guías de proveedores en cuentas por pagar.
  - `production_orders`: 6 órdenes de trabajo (OT) ejecutadas.
  - `clients`: 9 clientes comerciales registrados.
  - `suppliers`: 3 proveedores registrados.
  - `bank_accounts`: 1 cuenta bancaria corporativa activa.
  - `users`: 6 usuarios (admin, gerente, vendedor, digitador, contables, aprobador).
  - `roles`: 6 roles de sistema configurados.
  - `lot_stock`: 2 lotes físicos activos con stock disponible.
  - `page_data`: 25 registros clave-valor (incluyendo el JSON `inventory_items` con 124 productos).
  - `sales_entries`: 0 registros (tabla legacy no utilizada).

---

## 3. Estado del Testing

### Tests Existentes Previos
- **0 pruebas automatizadas** en el repositorio. Cero suites de prueba formales previo al inicio de esta fase.

### Tests Agregados en la Fase 0 (Total: 24 tests)
Se estructuró la carpeta `tests/` con configuración `pytest.ini` y fixtures reutilizables en `tests/conftest.py`:
1. **Tests Unitarios (`tests/unit/test_core_logic.py` - 6 tests):**
   - Normalización de RUT estándar con guión y puntos (`test_normalize_rut_standard_hyphen`).
   - Normalización de RUT con dígito verificador 'K' (`test_normalize_rut_with_k`).
   - Normalización de RUT con cuerpo y DV separados (`test_normalize_rut_separate_dv`).
   - Manejo de RUT vacío (`test_normalize_rut_empty`).
   - Validación de formato de email (`test_is_valid_email`).
   - Validación de estructura de correlativo OC (`test_get_next_oc_number_format`).
2. **Tests de Integración y Rutas Críticas (`tests/integration/test_smoke_routes.py` - 14 tests):**
   - Redirección de usuario no autenticado a `/login` (`test_unauthenticated_redirect`).
   - Carga de pantalla de login (`test_login_page_loads`).
   - Carga de Dashboard autenticado (`test_dashboard_authenticated`).
   - Carga de Productos (`test_productos_loads`).
   - Carga de Proveedores (`test_proveedores_loads`).
   - Carga de Clientes (`test_clientes_loads`).
   - Carga de Compras / OC (`test_compras_oc_loads`).
   - Carga de Inventario (`test_inventario_loads`).
   - Carga de Cotizaciones (`test_cotizaciones_loads`).
   - Carga de Ventas (`test_ventas_loads`).
   - Carga de Producción / OTs (`test_produccion_loads`).
   - Carga de Cuentas por Pagar / Facturas (`test_cuentas_por_pagar_loads`).
   - Carga de Cuentas por Cobrar (`test_cuentas_por_cobrar_loads`).
   - Carga de Cuentas Bancarias (`test_cuentas_bancarias_loads`).
3. **Tests de Seguridad Base (`tests/security/test_auth_baseline.py` - 4 tests):**
   - Rechazo de login con contraseña incorrecta (`test_login_invalid_credentials`).
   - Aceptación de login con credenciales válidas (`test_login_valid_credentials`).
   - Cierre de sesión y revocación de acceso (`test_logout_clears_session`).
   - Bloqueo de endpoints `/api/*` sin sesión retornando HTTP 401 JSON (`test_api_unauthenticated_returns_401`).

**Resultado de ejecución de pruebas:** **24 PASSED, 0 FAILED** (Tiempo: 1.81s).

---

## 4. Módulos y Funcionalidades Operativas Verificadas
Las siguientes funcionalidades se encuentran actualmente **operativas y verificadas**:
- **Autenticación:** Inicio y cierre de sesión con control de acceso en frontend y redirección automática si no existe sesión.
- **Dashboard:** Panel interactivo con métricas diarias calculadas en tiempo real desde `sales` e `inventory_items`, gráfico mensual con Chart.js y sistema de alertas.
- **Catálogo de Productos:** Alta, edición y baja lógica de productos con categorización, asignación de proveedor y requerimiento de lote.
- **Proveedores y Contactos:** Directorio de empresas proveedoras y múltiples contactos comerciales por proveedor.
- **Compras (OC):** Ciclo de vida completo de Orden de Compra (Borrador -> Aprobación -> Emisión -> Recepción -> Anulación controlada) con cálculo de totales y exportación PDF vía ReportLab.
- **Recepción en Bodega:** Ingreso de mercadería por OC con captura de factura o guía, desglose de ítems, actualización de costo ponderado y registro de lote.
- **Cuentas por Pagar (CxP):** Listado de facturas de proveedores, alertas de vencimiento a 7 días, vinculación de facturas a guías previas y registro de pagos bancarios con comprobante adjunto.
- **Cotizaciones y Ventas:** Confección de cotizaciones con cálculo automático de margen según categoría de cliente (A, B, C, D) sobre VPP, conversión a venta con validación de stock y seguimiento de cobranza.
- **Cuentas por Cobrar (CxC):** Registro de cuotas y abonos de clientes, carga de comprobante de transferencia y aprobación contable.
- **Fabricación (BOM / OTs):** Configuración de recetas de insumos, emisión de órdenes de trabajo con validación de stock de insumos, insumos adicionales por merma y costeo unitario final.
- **Reportería Analítica:** Flujo de caja dinámico (semanal y mensual) e inventario valorizado por lotes y bodegas.
- **Proyección de Ventas:** Motor estadístico (`proyeccion_engine.py`) con cálculo de medias móviles y tendencias por SKU.

---

## 5. Errores, Deficiencias y Discrepancias Confirmadas

### Críticas (P0)
1. **Contraseñas en texto plano:** En `users.password`, las claves se guardan sin algoritmo de hash criptográfico.
2. **SECRET_KEY hardcodeada:** `app.config['SECRET_KEY'] = 'tu-clave-secreta-aqui'` en `app.py:16`.
3. **DDL incompleto en `init_db()`:** Las tablas `purchase_invoices` y `client_categories` no son creadas por `init_db()`. Un despliegue en limpio sobre una base de datos vacía arroja error fatal `UndefinedTable`.
4. **Stock híbrido con riesgo de sobreescritura (Race Condition):** El inventario general reside en una cadena serializada JSON en `page_data(key='inventory_items')`, lo que genera colisiones de concurrencia al vender o recibir simultáneamente.

### Altas (P1)
5. **Ausencia total de CSRF Protection:** No existe validación de tokens anti-CSRF en ningún formulario POST del sistema.
6. **Bypass de RBAC en Backend:** Los permisos JSON de la tabla `roles` no son auditados en los controladores; cualquier usuario con sesión activa puede consumir endpoints destructivos (`/roles/<id>/eliminar`, etc.).
7. **Falta de atomicidad en operaciones de negocio:** La conversión de cotización a venta y la recepción de mercadería ejecutan inserciones y descuentos de stock en pasos separados no agrupados en una transacción unificada.
8. **Correlativos generados con `MAX(id)`:** `get_next_oc_number` y los folios de venta consultan `MAX(id)` desde la aplicación en lugar de secuencias de base de datos.
9. **Servidor de desarrollo Werkzeug en Docker:** El contenedor corre `CMD ["python", "app.py"]` con `debug=True`, no apto para tráfico real.

### Medias (P2)
10. **Archivo monolítico `db.py`:** Contiene 4,968 líneas mezclando DDL, DML y lógica de negocio.
11. **Fechas almacenadas como `TEXT`:** Múltiples tablas guardan fechas como strings `YYYY-MM-DD` sin tipo `DATE` nativo.
12. **Queries N+1 en Producción:** `routes/produccion.py:29-52` consulta insumos dentro de un bucle por cada orden de trabajo.
13. **Vistas de Reportería estáticas (Mocks):** Las plantillas de reporte de ventas, compras y gastos contienen tablas y totales fijos en HTML.
14. **Inexistencia de logging estructurado:** Ausencia del módulo `logging`. Errores silenciados o dependientes de `print()`.

### Bajas (P3)
15. **Doble registro de endpoint `/uploads/<filename>`:** Definido simultáneamente en `app.py` y en `routes/inventario.py`.
16. **Validación de tipos MIME incompleta:** Carga de comprobantes y fotos sin validación de contenido binario real.
17. **Archivos residuales en git:** `cookies.txt` presente en el directorio de trabajo.
