# 05. AUDITORÍA MULTITENANT Y SEGURIDAD — CONTROL DE ACCESO Y RLS

**Fecha de Auditoría:** 17 de Octubre de 2026  
**Enfoque de Seguridad:** Prevención de fugas de datos entre inquilinos (Cross-Tenant Data Leakage), Broken Object Level Authorization (BOLA/IDOR), RBAC y Autenticación.

---

## 1. MECANISMO DE AISLAMIENTO MULTITENANT EN V2

### 1.1 Resolución del Tenant en Request HTTP
El middleware `AuthMiddleware` en `internal/platform/middleware/auth_middleware.go` ejecuta una verificación rigurosa de 4 capas:
1. **Extracción y Validación de Token JWT**: Firma verificada con clave simétrica de 256 bits, validación de caducidad (`exp`), emisor y sujeto (`user_id`).
2. **Extracción del Header `X-Tenant-ID`**: Verifica que el header esté presente y sea un entero positivo.
3. **Comprobación de Membresía (User <-> Tenant)**:
   ```go
   membership, err := identitySvc.GetMembership(r.Context(), claims.UserID, tenantID)
   if err != nil || !membership.IsActive {
       renderError(w, http.StatusForbidden, "TENANT_ACCESS_DENIED", "User is not an active member of this tenant")
       return
   }
   ```
   *Garantía:* Si un usuario válido del Tenant 1 intenta enviar `X-Tenant-ID: 2`, el middleware rechaza la petición con `403 Forbidden` antes de llegar a cualquier servicio o base de datos.
4. **Inyección en Contexto**: El `UserContext` enriquecido se añade al contexto del request de Go.

### 1.2 Capa de Base de Datos: Doble Barrera (Defensa en Profundidad)
El sistema no se confía únicamente del filtro en el código Go. Implementa una arquitectura de **doble barrera**:
- **Barrera 1 (Código de la Aplicación):** Todas las consultas SQL en los repositorios incluyen explícitamente `WHERE tenant_id = $1`.
- **Barrera 2 (Motor PostgreSQL RLS):** Cada transacción ejecuta `SET LOCAL app.current_tenant_id = '<id>'`. Aunque un desarrollador olvide incluir el `WHERE tenant_id = ...` en una consulta nueva, el motor PostgreSQL filtra automáticamente los registros mediante la política RLS restrictiva y rechaza cualquier `INSERT` o `UPDATE` con un `tenant_id` ajeno.

---

## 2. AUDITORÍA DE VULNERABILIDADES IDOR / BOLA

### 2.1 Uso de Identificadores Públicos vs Internos
- En las URLs y payloads del API se utilizan UUIDs (`public_id`) o códigos alfanuméricos de cara al usuario en lugar de secuencias de enteros incrementales predecibles (`id SERIAL`).
- Ejemplo: `/api/v1/sales/orders/550e8400-e29b-41d4-a716-446655440000`.
- En caso de que un atacante intente enumerar pedidos cambiando el ID, la combinación de UUID no predecible + RLS por tenant genera un `404 Not Found` inmediato.

### 2.2 Validación de Claves Foráneas Cruzadas (Cross-Tenant Entity Injection)
Al crear una orden de venta o de compra, se validan las entidades secundarias dentro del mismo tenant:
- Si el usuario del Tenant 1 intenta crear una venta asociando un `customer_id` perteneciente al Tenant 2, la consulta `SELECT id FROM customers WHERE tenant_id = $1 AND id = $2` no encuentra la fila y retorna `400/404 El cliente no existe`.

---

## 3. AUDITORÍA DE AUTENTICACIÓN, CONTRASEÑAS Y SESIONES

| Parámetro de Seguridad | Implementación en V2 | Implementación en V1 | Evaluación |
|---|---|---|:---:|
| **Algoritmo de Hash** | **Argon2id** (m=64MB, t=3 iteraciones, p=2 hilos) | PBKDF2 / Scrypt (migrado desde SQLite legado) | 🟢 **ÓPTIMO (V2)** |
| **Generación de Salt** | Criptográficamente seguro (`crypto/rand`, 16 bytes) | Estándar Werkzeug | 🟢 **SEGURO** |
| **Comparación de Hashes** | `subtle.ConstantTimeCompare` (previene timing attacks) | `hmac.compare_digest` | 🟢 **SEGURO** |
| **Gestión de Sesiones** | JWT Bearer Tokens sin estado (Stateless) | Sesión en cookies de servidor cifradas | 🟢 **ADECUADO** |
| **Auditoría de Seguridad** | Tabla `security_audit_logs` con IP, User-Agent y evento | Log de seguridad de eventos en base de datos | 🟢 **SEGURO** |

---

## 4. RIESGOS DETECTADOS Y PLAN DE REMEDIACIÓN

| ID Hallazgo | Componente | Descripción | Prioridad | Remediación Recomendada |
|---|---|---|:---:|---|
| **SEC-MT-01** | Plataforma V1 | **V1 no posee aislamiento multitenant**. Si se expone el V1 al exterior, cualquier usuario registrado comparte el maestro único. | **P0 (en V1)** | Mantener V1 como aplicación privada interna de única empresa. Prohibir el aprovisionamiento de nuevos clientes en V1. |
| **SEC-MT-02** | `cmd/api` | Falta mecanismo de revocación inmediata de JWT (Token Blacklist / Refresh Token Rotation). | **P2** | Reducir el tiempo de expiración del Access Token a 15 minutos e implementar Refresh Tokens en Redis con revocación. |
| **SEC-MT-03** | `internal/auth` | No se exige actualmente complejidad mínima estricta de contraseñas ni bloqueo temporal tras N intentos fallidos (Account Lockout). | **P1** | Implementar política de bloqueo de cuenta por 15 minutos tras 5 intentos fallidos y exigir mínimo 10 caracteres con mayúsculas/números. |
| **SEC-MT-04** | Almacenamiento Archivos | Subida de facturas/comprobantes se almacena en disco local sin aislamiento por carpetas tenant en V1. | **P1** | Migrar almacenamiento documental a MinIO/S3 estructurando rutas por bucket/carpeta: `s3://erp-documents/tenant_<id>/<modulo>/<uuid>.pdf`. |
