# 11. AUDITORÍA DE CALIDAD Y TESTING — SUITES Y COBERTURA

**Fecha de Auditoría:** 17 de Octubre de 2026  
**Suites Auditadas:**
1. Suite Go V2: `tests/isolation/` (81 funciones de prueba de aislamiento e integración).
2. Suite Python V1: `tests/` (62 archivos de prueba pytest con runner aislado `tools/run_isolated_tests.py`).

---

## 1. EVALUACIÓN DE LA SUITE DE PRUEBAS EN GO (V2)

### 1.1 Cobertura de Aislamiento Multitenant
La suite de pruebas en Go destaca por un diseño metodológico riguroso:
- **`multitenant_isolation_test.go` y `http_security_test.go`**:
  - Crean Tenant A y Tenant B de forma paralela.
  - El usuario del Tenant A intenta leer, modificar o eliminar clientes, productos, pedidos y cuentas bancarias del Tenant B.
  - Verifica que cada intento sea bloqueado y retorne `403 Forbidden` o `404 Not Found`.
- **`banking_security_test.go` y `banking_audit_test.go`**:
  - Prueban transferencias concurrentes con detección de race conditions (`go test -race`).
  - Verifican la inmutabilidad de la auditoría y la imposibilidad de manipular saldos sin un registro en `bank_transactions`.
- **Total de pruebas en Go:** 81 tests exhaustivos cubriendo desde la capa de dominio hasta endpoints HTTP reales con servidor de prueba `httptest.Server`.

---

## 2. EVALUACIÓN DE LA SUITE DE PRUEBAS EN PYTHON (V1)

### 2.1 Aislamiento de Base de Datos y Certificación de Doble Pasada
- En V1, el runner `tools/run_isolated_tests.py` implementa una arquitectura de pruebas protegida:
  - Base de datos plantilla persistente e inmutable: `facturacion_cleanup_verify`.
  - Para cada corrida de pruebas, clona una base de datos efímera (`facturacion_test_run_<hex>`), ejecuta los tests y la destruye en el bloque `finally`.
  - Verifica que los conteos de las tablas de la base de datos principal (`facturacion`) y de la plantilla permanezcan con **0 Delta**.
  - Ejecuta la suite dos veces consecutivas (**Doble Pasada**) certificando **565 tests aprobados / 0 fallados**.

### 2.2 Áreas de Riesgo / Pruebas Faltantes en V1
- **Pruebas de Concurrencia Extrema:** Aunque existen pruebas de reserva de stock, faltan pruebas de stress concurrentes con 50 clientes comprando simultáneamente el mismo SKU con stock limitado.
- **Pruebas E2E de Frontend:** Los tests prueban las rutas HTTP y el HTML retornado, pero no ejecutan pruebas en navegador real mediante Playwright/Cypress de forma continua en CI/CD.

---

## 3. COMPARATIVA Y MATRIZ DE MADUREZ DE TESTING

| Criterio | Suite V2 (Go) | Suite V1 (Python) |
|---|:---:|:---:|
| **Tests de Aislamiento Multitenant** | 🟢 100% de módulos cubiertos | 🔴 No aplica (Single-tenant) |
| **Race Detector / Concurrencia** | 🟢 Nativo con `go test -race` | 🟡 Parcial (hilos limitados en pytest) |
| **Tiempo de Ejecución** | 🟢 < 10 segundos | 🟡 ~3 minutos y medio por pasada |
| **Idempotencia de Base de Datos** | 🟢 Validada con rollback/isolation | 🟢 Verificada con clonación efímera |
| **Tests de Rendimiento / Benchmarks**| 🟡 Pendientes de formalizar | 🔴 Inexistentes |

---

## 4. HALLAZGOS Y RECOMENDACIONES DE QA

| ID Hallazgo | Componente | Descripción | Severidad | Recomendación |
|---|---|---|:---:|---|
| **QA-01** | CI / CD | No existe pipeline de GitHub Actions configurado para ejecutar los tests automáticamente ante cada Pull Request en V2. | **P1** | Crear `.github/workflows/test.yml` que levante el contenedor PostgreSQL y ejecute `go test -v -race ./...`. |
| **QA-02** | V2 Reporting | Faltan pruebas unitarias y de integración para la Fase 9 (Flujo de Caja y Gastos Operacionales). | **P1** | Implementar `TestCashFlow_ConsolidatedWithoutDuplicateCounts` y `TestOperationalExpenses_RecurrenceAndTaxes` en la Fase 9. |
| **QA-03** | Pruebas de Carga | No se dispone de scripts de prueba de carga y estrés con herramientas tipo k6 o Locust. | **P2** | Desarrollar suite de pruebas de rendimiento k6 simulando 100 usuarios navegando y realizando pedidos en simultáneo. |
