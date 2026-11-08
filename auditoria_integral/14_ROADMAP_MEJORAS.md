# 14. ROADMAP DE MEJORAS Y EVOLUCIÓN POR FASES

**Fecha de Auditoría:** 17 de Octubre de 2026  
**Estrategia:** Plan de ejecución progresivo, controlado y sin disrupción de la operación actual de la empresa.

---

## FASE A — CORRECCIONES CRÍTICAS Y BLINDAJE DE SEGURIDAD
**Objetivo:** Eliminar riesgos de aislamiento y asegurar la continuidad operativa inmediata.
- **Acciones:**
  1. Formalizar la restricción de que ERP V1 opera en modo monolito privado (empresa única), prohibiendo dar de alta tenants adicionales en V1 (`SEC-MT-01`).
  2. Implementar respaldo automatizado diario de las bases de datos `facturacion` y `erp_multitenant_v2` con cifrado y copia remota (`PROD-02`).
  3. Agregar Rate Limiting a los endpoints de login y registro en la API Go (`GO-ARCH-02`).
- **Criterio de Aprobación:** Respaldo probado con restauración en ambiente temporal; cero fugas posibles en V1.

---

## FASE B — PARIDAD FUNCIONAL FINANCIERA EN V2 (FASE 9)
**Objetivo:** Completar el último bloque de negocio pendiente en el backend Go según el diseño aprobado en `PLAN_FASE_9.md`.
- **Acciones:**
  1. Implementar migración `000009_operational_expenses_and_cashflow.up.sql` con RLS forzado.
  2. Desarrollar paquetes `internal/expenses` (maestro, recurrencia, ocurrencias, tratamiento IVA) e `internal/cashflow` (consolidación neutral de fuentes).
  3. Crear endpoints REST paginados en Chi para gastos y flujo de caja con filtros por cuenta, fecha y estado.
  4. Implementar tests de aislamiento e invariantes financieras en `tests/isolation/`.
- **Criterio de Aprobación:** Suite Go verde con `go test -race ./...`, verificación de que el flujo de caja consolida sin duplicaciones.

---

## FASE C — CAPA DE INTERFAZ DE USUARIO (FRONTEND V2)
**Objetivo:** Habilitar una experiencia visual moderna, intuitiva y rápida para que los operadores utilicen el ERP Multitenant V2.
- **Acciones:**
  1. Definir la tecnología de frontend (Recomendación: SPA con React/TypeScript + Tailwind CSS o Vue 3 + Vite).
  2. Implementar layout corporativo con selector de Tenant activo, control de sesión JWT y menús por roles RBAC.
  3. Construir pantallas operativas:
     - Catálogo de Productos y Existencias por Bodega/Lote.
     - Mesa de Ventas y Emisión de Cotizaciones.
     - Recepción de Compras y Control de Facturas (CxP).
     - Tesorería: Cuentas Bancarias, Conciliación de Cartolas y Flujo de Caja interactivo.
- **Criterio de Aprobación:** Flujo end-to-end completado desde la interfaz web sin errores en consola y tiempo de carga < 1 segundo.

---

## FASE D — OBSERVABILIDAD, RENDIMIENTO Y ESTABILIDAD
**Objetivo:** Preparar la plataforma para soportar decenas de empresas concurrentes con monitoreo en tiempo real.
- **Acciones:**
  1. Desacoplar `cmd/api/main.go` en paquetes de transporte HTTP limpios (`GO-ARCH-01`).
  2. Instrumentar métricas Prometheus (`/metrics`) y trazas OpenTelemetry (`GO-ARCH-03`, `PROD-03`).
  3. Desplegar PgBouncer para gestión de pool de conexiones PostgreSQL frente a picos de tráfico (`PERF-02`).
  4. Optimizar las consultas de reportes en SQL agregando window functions y paginación en base de datos (`PERF-01`).
- **Criterio de Aprobación:** Dashboard en Grafana mostrando latencia, requests por segundo y conexiones activas; p95 < 50ms.

---

## FASE E — PREPARACIÓN PRODUCTIVA Y FACTURACIÓN ELECTRÓNICA
**Objetivo:** Habilitar la comercialización y puesta en marcha definitiva como SaaS empresarial.
- **Acciones:**
  1. Generar `Dockerfile` multi-stage optimizado y configuración de despliegue en servidor en la nube con Nginx/Caddy y SSL automático (`PROD-01`, `PROD-04`).
  2. Diseñar el conector DTE para facturación electrónica oficial chilena (SII) (`VEN-01`).
  3. Configurar almacenamiento de archivos en bucket seguro MinIO/S3 con prefijos por tenant (`SEC-MT-04`).
  4. Ejecutar auditoría de seguridad final y pruebas de carga con k6 para certificar 100 usuarios simultáneos por tenant.
- **Criterio de Aprobación:** Piloto controlado con la primera empresa operando 100% sobre V2 en producción.
