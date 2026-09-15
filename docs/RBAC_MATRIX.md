# Matriz de Control de Acceso Basado en Roles (RBAC)
**Sistema de Facturación / Bodega Miel (ERP Single-Tenant)**  
**Fase 1 — Seguridad Crítica y Control de Acceso**

---

## 1. Arquitectura del Modelo de Permisos

El sistema utiliza un esquema de roles con permisos granulares almacenados en formato JSON en la columna `roles.permissions` de la tabla `roles` en PostgreSQL.

Cada usuario (`users`) tiene asignado un `role_id` foráneo. En el inicio de sesión (`/login`), los permisos del rol son deserializados y cargados en la sesión del usuario (`session['permissions']`), optimizando la verificación en memoria sin generar sobrecarga de consultas SQL repetitivas en cada solicitud.

### 1.1 Llaves de Permisos Estándar
| Permiso | Descripción Operativa |
| :--- | :--- |
| `dashboard` | Visualización del tablero principal de métricas y resumen de negocio. |
| `usuarios` | Gestión de usuarios, perfiles de acceso y configuración de roles. |
| `ventas` | Gestión de ventas, cotizaciones, clientes y seguimiento comercial. |
| `inventario` | Gestión de bodega, movimientos de stock, ingresos de mercadería. |
| `productos` | Catálogo de productos, materias primas, costos y precios. |
| `administracion` | Cuentas bancarias de empresa, listas de precios y ajustes maestros. |
| `reportes` | Visualización y exportación de reportes analíticos y financieros. |
| `configuracion` | Parámetros críticos y configuraciones globales del sistema. |
| `crear_registros` | Capacidad operativa para crear nuevos registros en módulos autorizados. |
| `aprobar_registros` | Autorización para aprobar órdenes de trabajo, compras y pagos. |
| `solo_ver` | Restricción de solo lectura (inhibe botones y mutaciones). |

---

## 2. Matriz de Permisos por Rol

A continuación se detalla la matriz efectiva de permisos configurada en la base de datos:

| Permiso | Administrativo (ID 1) | Gerente (ID 2) | Área Ventas (ID 3) | Contables (ID 4) | Aprobador (ID 237) | Digitador (ID 238) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **`dashboard`** | ✅ Sí | ✅ Sí | ❌ No | ❌ No | ✅ Sí | ✅ Sí |
| **`usuarios`** | ✅ Sí | ❌ No | ❌ No | ❌ No | ❌ No | ❌ No |
| **`ventas`** | ✅ Sí | ✅ Sí | ✅ Sí | ✅ Sí | ✅ Sí | ✅ Sí |
| **`inventario`** | ✅ Sí | ✅ Sí | ❌ No | ❌ No | ✅ Sí | ✅ Sí |
| **`productos`** | ✅ Sí | ✅ Sí | ✅ Sí | ❌ No | ✅ Sí | ✅ Sí |
| **`administracion`**| ✅ Sí | ❌ No | ❌ No | ❌ No | ✅ Sí | ❌ No |
| **`reportes`** | ✅ Sí | ✅ Sí | ❌ No | ✅ Sí | ✅ Sí | ❌ No |
| **`configuracion`** | ✅ Sí | ❌ No | ❌ No | ❌ No | ❌ No | ❌ No |
| **`crear_registros`**| ✅ Sí | ✅ Sí | ✅ Sí | ❌ No | ✅ Sí | ✅ Sí |
| **`aprobar_registros`**| ✅ Sí | ✅ Sí | ❌ No | ❌ No | ✅ Sí | ❌ No |
| **`solo_ver`** | ❌ No | ❌ No | ❌ No | ✅ Sí | ❌ No | ❌ No |

---

## 3. Mapeo de Rutas Protegidas y Políticas de Denegación

El backend aplica la directiva `@require_permission('<nombre_permiso>')` definida en `security.py`:

| Ruta / Módulo | Endpoint / Acción | Permiso Requerido | Comportamiento No Autorizado |
| :--- | :--- | :--- | :--- |
| `/usuarios` | Listar y crear usuarios | `usuarios` | HTTP 403 (renderiza `403.html` o JSON) |
| `/usuarios/<id>/editar` | Modificar datos de usuario | `usuarios` | HTTP 403 |
| `/usuarios/<id>/eliminar` | Eliminar usuario | `usuarios` | HTTP 403 |
| `/roles` | Listar y crear roles | `usuarios` | HTTP 403 |
| `/roles/<id>/editar` | Modificar permisos de rol | `usuarios` | HTTP 403 |
| `/roles/<id>/eliminar` | Eliminar rol | `usuarios` | HTTP 403 |
| `/usuarios/<id>/reasignar-rol` | Cambio rápido de rol | `usuarios` | HTTP 403 |
| `/administracion` | Panel administrativo | `administracion` | HTTP 403 |
| `/administracion/listas-precios` | Configuración de precios/márgenes | `administracion` | HTTP 403 |
| `/administracion/cuentas-bancarias` | Cuentas bancarias de empresa | `administracion` | HTTP 403 |
| `/administracion/cuentas-bancarias/*/editar` | Editar cuenta bancaria | `administracion` | HTTP 403 |
| `/administracion/cuentas-bancarias/*/eliminar`| Eliminar cuenta bancaria | `administracion` | HTTP 403 |

### 3.1 Política de Excepción Administrativa
Los usuarios pertenecientes al rol `Administrativo` (o variantes administrativas directas) poseen acceso de superusuario irrevocable en el decorador para evitar bloqueos por configuraciones erróneas.

### 3.2 Manejo de Respuestas de Error
1. **Peticiones sin sesión iniciada:**
   - Rutas API (`/api/*` o `Accept: application/json`): HTTP 401 `{"status": "error", "message": "Autenticación requerida"}`.
   - Navegación HTML regular: HTTP 302 Redirección a `/login`.
2. **Peticiones autenticadas pero sin permisos suficientes:**
   - Rutas API: HTTP 403 `{"status": "error", "message": "Acceso denegado: permiso '<permiso>' requerido."}`.
   - Navegación HTML regular: HTTP 403 con plantilla de interfaz estilizada `templates/403.html` y registro de auditoría en el log de seguridad.
