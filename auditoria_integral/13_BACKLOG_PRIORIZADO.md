# 13. BACKLOG PRIORIZADO DE HALLAZGOS Y MEJORAS

**Fecha de Auditoría:** 17 de Octubre de 2026  
**Criterio de Priorización:** Matriz de Impacto en el Negocio, Riesgo de Seguridad/Integridad, Complejidad y Dependencias.

---

## 1. TABLA CONSOLIDADA DE HALLAZGOS Y ACCIONES

| ID | Prioridad | Módulo | Título del Hallazgo / Tarea | Complejidad | Dependencias | Beneficio Esperado |
|---|:---:|---|---|:---:|---|---|
| **SEC-MT-01** | **P0** | Seguridad | **Prohibir uso multitenant en V1 Legacy**. Restringir V1 exclusivamente a la empresa actual. | Baja | Ninguna | Elimina el riesgo absoluto de fuga de datos entre empresas. |
| **FIN-01** | **P1** | Finanzas V2 | **Implementar Fase 9 en Go (Gastos Operacionales y Flujo de Caja)**. | Alta | Migraciones 000008, `PLAN_FASE_9.md` | Logra paridad financiera completa y habilita el apagado de V1. |
| **UX-01** | **P1** | Frontend V2 | **Desarrollar Capa de Interfaz de Usuario para V2 (Web UI)**. | Alta | Endpoints API V2 | Permite a los usuarios operar el nuevo backend multitenant de forma gráfica. |
| **PROD-01** | **P1** | DevOps | **Dockerizar backend Go y crear pipeline de CI/CD en GitHub Actions**. | Media | Código Go V2 | Garantiza calidad continua, compilación estandarizada y tests en cada PR. |
| **PROD-02** | **P1** | DevOps | **Implementar política de Backups Automáticos cifrados y réplica externa**. | Media | PostgreSQL | Resiliencia operacional y recuperación garantizada ante desastres. |
| **SEC-MT-04**| **P1** | Seguridad | **Aislar almacenamiento documental de facturas/comprobantes por tenant (S3/MinIO)**. | Media | Almacenamiento local | Cumplimiento de privacidad e imposibilidad de acceso cruzado a PDFs. |
| **VEN-01** | **P1** | Ventas | **Diseño del conector de Facturación Electrónica DTE (SII Chile)**. | Alta | Fase 6 Ventas | Capacidad de operar legalmente en Chile sin procesos manuales externos. |
| **GO-ARCH-01**| **P2** | Arquitectura | **Modularizar `cmd/api/main.go` en paquetes de transporte HTTP independientes**. | Media | `cmd/api` | Facilita el mantenimiento, testeo unitario de handlers y trabajo en equipo. |
| **GO-ARCH-02**| **P2** | Seguridad | **Incorporar Rate Limiting y Throttling en API Go**. | Baja | Router Chi | Protección contra ataques de fuerza bruta y saturación de peticiones. |
| **PERF-01** | **P2** | Rendimiento | **Migrar agregaciones de reportes V1 a SQL nativo (erradicar `fetchall` en memoria)**. | Media | `reporting_repo.py` | Evita bloqueos y consumo excesivo de RAM con bases de datos grandes. |
| **SEC-MT-02**| **P2** | Seguridad | **Implementar rotación de Refresh Tokens y lista de revocación en Redis**. | Media | `internal/auth` | Capacidad de revocar accesos inmediatamente ante bajas de usuarios. |
| **PROD-03** | **P2** | DevOps | **Instrumentar métricas Prometheus y endpoints `/healthz` y `/readyz`**. | Baja | `cmd/api` | Visibilidad en tiempo real del estado del sistema y salud de conexiones. |
| **INV-01** | **P2** | UX / Bodega | **Alertas visuales de caducidad de lotes (<30 días) en listados de inventario**. | Baja | Templates V1 / UI V2 | Prevención de mermas por vencimiento de materias primas o PT. |
| **INV-02** | **P2** | Producción | **Registro y control de mermas y desperdicios en cierre de OTs**. | Media | `internal/production` | Precisión exacta en el rendimiento de recetas y costos de fabricación. |
| **FIN-02** | **P2** | Finanzas | **Manejo explícito de diferencias de cambio y redondeo en conciliación**. | Baja | `internal/banking` | Cierre contable perfecto sin descuadres por centavos o decimales. |
| **FIN-03** | **P2** | Finanzas | **Soporte multi-divisa (USD, EUR, UF) con tabla de tipos de cambio**. | Alta | `internal/banking` | Permite compras internacionales y valorización de inventario importado. |
| **UX-02** | **P2** | UX | **Persistencia de filtros y paginación en search params de URL**. | Baja | Frontend | Permite recargar o compartir URLs de listados manteniendo la búsqueda activa. |
| **UX-03** | **P2** | UX | **Alerta de confirmación de salida en formularios con cambios no guardados**. | Baja | JavaScript | Evita que el usuario pierda tiempo si cierra una pestaña accidentalmente. |
| **PG-DB-02** | **P2** | Base Datos | **Diseño de particionamiento de tablas de alta concurrencia para >100 tenants**. | Alta | Esquema PostgreSQL | Escalabilidad garantizada a largo plazo sin degradación de velocidad. |
| **GO-ARCH-03**| **P3** | Observabilidad| **Agregar OpenTelemetry Tracing Context a los logs estructurados**. | Media | `internal/platform` | Facilita el rastreo de llamadas y diagnóstico de errores en micro-pasos. |
| **PG-DB-01** | **P3** | Base Datos | **Índices parciales en membresías activas**. | Baja | Esquema PostgreSQL | Optimización milimétrica del tiempo de autenticación. |
| **UX-04** | **P3** | UX | **Ajuste de `z-index` de notificaciones flotantes frente a modales**. | Baja | CSS | Mejora cosmética y de usabilidad en alertas del sistema. |
| **COM-01** | **P3** | Compras | **Badge explícito de "Recepción sin Factura" en Cuentas por Pagar**. | Baja | Vistas de Compras | Claridad operativa para el departamento de contabilidad. |
