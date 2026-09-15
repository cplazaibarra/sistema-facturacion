# Informe Técnico y Auditoría de Seguridad — Fase 1
**Proyecto:** Sistema de Facturación / Bodega Miel (ERP Monolito Flask)  
**Agente Responsable:** `erp-security-qa`  
**Supervisión y Aprobación:** `erp-tech-lead`  
**Fecha de Ejecución:** Septiembre 2026  
**Estado:** `PHASE_1_COMPLETE`

---

## 1. Resumen Ejecutivo

Durante la Fase 1 se abordaron y resolvieron de forma exhaustiva las vulnerabilidades críticas de seguridad de la plataforma identificadas en la auditoría inicial de Fase 0:
1. Eliminación del hardcoding de `SECRET_KEY` y validación estricta de entropía y rechazo de valores por defecto.
2. Criptografía de contraseñas mediante algoritmo Scrypt/PBKDF2 (`werkzeug.security`) con **migración transparente on-login** para salvaguardar la experiencia de los usuarios existentes sin invalidar accesos previos.
3. Control de Acceso Basado en Roles (RBAC) con decorador `@require_permission` en endpoints administrativos y destructivos, con respuestas diferenciadas (HTTP 403 / 401).
4. Protección integral contra ataques CSRF mediante `Flask-WTF` con sincronización automática en frontend para formularios POST y llamadas asíncronas (`fetch` / `XMLHttpRequest`).
5. Blindaje de subida de archivos mediante validación de extensiones permitidas (`png, jpg, jpeg, webp, pdf`), sanitización con `secure_filename` y comprobación de rutas canónicas contra ataques de Path Traversal (`../../`).
6. Hardening de cookies de sesión (`HttpOnly`, `SameSite=Lax`, `Secure` condicional al entorno de producción).
7. Preparación para despliegue productivo WSGI con `gunicorn` en `requirements.txt`, `Dockerfile` y `docker-compose.yml`.
8. Registro de auditoría de seguridad estructurado (Python standard `logging`) para autenticaciones, denegaciones 403 y mutaciones administrativas.

---

## 2. Inventario de Modificaciones Implementadas

### 2.1 Archivos Creados
- `security.py`: Módulo central de validaciones criptográficas, RBAC, auditoría y mitigación de path traversal.
- `templates/403.html`: Interfaz amigable y corporativa de acceso denegado (HTTP 403).
- `templates/csrf_error.html`: Interfaz independiente y estilizada para token CSRF inválido o expirado (HTTP 400).
- `.env.example`: Plantilla de variables de entorno seguras sin credenciales reales.
- `docs/RBAC_MATRIX.md`: Especificación técnica del modelo de roles y permisos.
- `docs/SECURITY_PHASE1_REPORT.md`: El presente reporte formal.
- `tests/security/test_phase1_security.py`: Suite de 15 pruebas automatizadas de seguridad crítica.

### 2.2 Archivos Modificados
- `app.py`:
  - Validación de `SECRET_KEY` con rechazo de `'tu-clave-secreta-aqui'` y longitud mínima de 24 caracteres.
  - Soporte de `APP_ENV` (`development`, `testing`, `production`).
  - Configuración de cookies: `SESSION_COOKIE_HTTPONLY=True`, `SESSION_COOKIE_SAMESITE='Lax'`, `SESSION_COOKIE_SECURE=True` en producción.
  - Inicialización de `CSRFProtect(app)` y manejador `@app.errorhandler(CSRFError)` con status 400.
  - Enrutamiento dinámico de modo depuración condicionado a `APP_ENV != 'production'`.
- `db.py`:
  - Inclusión de `generate_password_hash` en `insert_user()` y `update_user()`.
  - Garantía de que cualquier usuario nuevo o actualizado persista exclusivamente contraseñas hasheadas.
- `routes/auth.py`:
  - Verificación segura con `verify_and_upgrade_password()`.
  - Migración on-login en tiempo real: al loguearse con contraseña legacy en texto plano, se valida y actualiza de inmediato el hash en PostgreSQL.
  - Carga de `session['permissions']` para evaluación RBAC eficiente.
  - Registro de eventos: `LOGIN_SUCCESS`, `LOGIN_FAILED`, `LOGOUT`, `PASSWORD_MIGRATED`.
- `routes/usuarios.py`:
  - Decoración con `@require_permission('usuarios')` en endpoints de usuarios y roles.
  - Decoración con `@require_permission('administracion')` en panel de administración, listas de precios y cuentas bancarias.
  - Hasheo automático de contraseñas de usuarios creados en el formulario.
  - Auditoría de mutaciones: `USER_CREATED`, `USER_UPDATED`, `USER_DELETED`, `ROLE_CREATED`, `ROLE_UPDATED`, `ROLE_DELETED`.
- `routes/inventario.py`:
  - Control de subida de imágenes de producto y documentos de compra (`documentos_compra`) con `allowed_file` y validación de rutas canónicas contra path traversal.
- `routes/compras.py`:
  - Validación de extensiones permitidas y path traversal en subida de facturas de compra y comprobantes de pago.
- `templates/base.html`:
  - Inyección de `<meta name="csrf-token" content="{{ csrf_token() }}">`.
  - Script global interceptor para adjuntar automáticamente tokens CSRF a formularios POST y cabeceras `X-CSRFToken` a `fetch` y `XMLHttpRequest`.
- `templates/login.html`:
  - Inclusión de `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">`.
- `requirements.txt`:
  - Adición de `Flask-WTF==1.3.0` y `gunicorn==26.2.0`.
- `Dockerfile`:
  - Comando de ejecución productiva: `CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", "app:app"]`.
- `docker-compose.yml`:
  - Integración de variables `APP_ENV=production` y `SECRET_KEY=${SECRET_KEY}`.
- `tests/conftest.py` & `tests/security/test_auth_baseline.py`:
  - Helper `get_csrf_token` para simulación fidedigna de clientes en pruebas automatizadas.
  - Permisos agregados a la fixture `auth_client`.

---

## 3. Resultados de Pruebas Automatizadas

Se ejecutó la suite completa con `pytest` en el entorno virtual del proyecto:

```
============================= test session starts ==============================
platform linux -- Python 3.14.4, pytest-9.1.1, pluggy-1.6.0
rootdir: /home/cplaza/Desarrollo/Proeycto-Gestion-Negocio/sistema-facturacion
configfile: pytest.ini
testpaths: tests
collected 39 items

tests/integration/test_smoke_routes.py ..............                    [ 35%]
tests/security/test_auth_baseline.py ....                                [ 46%]
tests/security/test_phase1_security.py ...............                   [ 84%]
tests/unit/test_core_logic.py ......                                     [100%]

======================== 39 passed, 6 warnings in 3.30s ========================
```

### 3.1 Detalle de Validación de Pruebas
- **Baseline Fase 0:** 24/24 PASSED (100% preservado).
- **Pruebas Fase 1 (15 nuevas pruebas):**
  1. `test_secret_key_required`: PASSED
  2. `test_insecure_default_secret_rejected`: PASSED
  3. `test_secret_key_loaded_from_environment`: PASSED
  4. `test_legacy_password_login`: PASSED
  5. `test_legacy_password_upgraded_after_login`: PASSED
  6. `test_hashed_password_login`: PASSED
  7. `test_wrong_password_does_not_upgrade`: PASSED
  8. `test_password_not_stored_plaintext_for_new_user`: PASSED
  9. `test_unauthorized_user_cannot_access_admin_routes`: PASSED (HTTP 403 verificado)
  10. `test_authorized_user_can_access_allowed_routes`: PASSED
  11. `test_post_without_csrf_is_rejected`: PASSED (HTTP 400 verificado)
  12. `test_post_with_valid_csrf_is_accepted`: PASSED (HTTP 302 verificado)
  13. `test_upload_invalid_extension_rejected`: PASSED
  14. `test_upload_path_traversal_prevented`: PASSED
  15. `test_upload_valid_file_accepted`: PASSED

---

## 4. Estado de los 12 Módulos Funcionales (Smoke Test)

| # | Módulo ERP | Ruta | Estado HTTP | Resultado |
| :-: | :--- | :--- | :-: | :--- |
| 1 | Dashboard | `/dashboard` | 200 OK | Operativo |
| 2 | Productos | `/productos` | 200 OK | Operativo |
| 3 | Proveedores | `/proveedores` | 200 OK | Operativo |
| 4 | Clientes | `/ventas/clientes` | 200 OK | Operativo |
| 5 | Compras (OC) | `/compras/oc` | 200 OK | Operativo |
| 6 | Inventario / Bodega | `/inventario` | 200 OK | Operativo |
| 7 | Cotizaciones | `/ventas/cotizaciones` | 200 OK | Operativo |
| 8 | Ventas | `/ventas` | 200 OK | Operativo |
| 9 | Producción (OTs) | `/produccion` | 200 OK | Operativo |
| 10 | Cuentas por Pagar (CxP) | `/compras/cuentas-por-pagar` | 200 OK | Operativo |
| 11 | Cuentas por Cobrar (CxC) | `/ventas?filter=pendiente` | 200 OK | Operativo |
| 12 | Cuentas Bancarias | `/administracion/cuentas-bancarias` | 200 OK | Operativo |

---

## 5. Dictamen Técnico y Próximos Pasos

El sistema ha superado con éxito todos los criterios técnicos exigidos para la **Fase 1**.  
No se realizaron modificaciones estructurales en inventario, ventas, compras ni en la modularización general de `db.py`, respetando estrictamente los límites del alcance.

**Dictamen:** `PHASE_1_COMPLETE`  
**Siguiente Paso:** Listo para revisión del usuario y posterior aprobación para iniciar la **FASE 2 — MODULARIZACIÓN GRADUAL DEL BACKEND (DIVISIÓN DE DB.PY)**.
