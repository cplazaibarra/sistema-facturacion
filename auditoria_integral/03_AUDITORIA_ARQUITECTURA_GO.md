# 03. AUDITORÍA DE ARQUITECTURA GO — BACKEND V2

**Fecha de Auditoría:** 17 de Octubre de 2026  
**Componente Evaluado:** `github.com/cplazaibarra/erp-multitenant-v2`  
**Tecnología Base:** Go 1.22+, Chi Router v5, pgxpool v5, Argon2id, Google UUID.

---

## 1. EVALUACIÓN ESTRUCTURAL Y ORGANIZACIÓN DEL CÓDIGO

### 1.1 Estructura de Paquetes
El backend sigue estrictamente las directrices del **Standard Go Project Layout**:
- `cmd/api/main.go`: Punto de entrada del servidor HTTP, configuración, inicialización de dependencias y registro de rutas Chi.
- `cmd/migrate/main.go`: Herramienta CLI de migraciones idempotentes usando `golang-migrate`.
- `internal/<domain>/`: Encapsulamiento estricto por dominios de negocio:
  - `domain/`: Entidades puras, DTOs de request/response, enums y tipos de valor (DDD ligero).
  - `service/`: Casos de uso y reglas de orquestación transaccional.
  - `repository/`: Capa de persistencia con SQL explícito y transacciones con contexto de tenant.
- `internal/platform/`: Componentes transversales de infraestructura (Database pgxpool, Config, Logger estructurado, Middlewares).

### 1.2 Separación de Capas y Acoplamiento
- **Evaluación:** 🟢 **EXCELENTE**.
- La capa HTTP (`cmd/api/main.go`) no contiene lógica de persistencia directa; delega inmediatamente a los servicios de dominio.
- Los repositorios reciben interfaces `pgx.Tx` o ejecutan mediante `WithTenantTx`, lo que permite componer múltiples operaciones dentro de una misma transacción atómica.

---

## 2. MANEJO DE CONCURRENCIA Y TRANSACCIONES

### 2.1 Aislamiento Transaccional y Pool de Conexiones
En `internal/platform/database/database.go`:
```go
func (p *Pool) WithTenantTx(ctx context.Context, tenantID int64, fn func(tx pgx.Tx) error) error {
    tx, err := p.Begin(ctx)
    if err != nil { return err }
    defer tx.Rollback(ctx)

    // Aislamiento RLS en sesión local a la transacción
    setQuery := fmt.Sprintf("SET LOCAL app.current_tenant_id = '%d'", tenantID)
    if _, err := tx.Exec(ctx, setQuery); err != nil { return err }

    if err := fn(tx); err != nil { return err }
    return tx.Commit(ctx)
}
```
**Puntos Fuertes:**
- `SET LOCAL` garantiza que cuando la conexión se devuelve al pool (`pgxpool`), el parámetro `app.current_tenant_id` se destruye inmediatamente. No hay fuga de contexto entre requests concurrentes.
- El uso de `defer tx.Rollback(ctx)` asegura que cualquier panic o retorno anticipado por error libere los locks de base de datos de manera determinista.

### 2.2 Bloqueos Concurrenciales en Inventario y Dinero
- En operaciones críticas como el consumo FIFO (`internal/sales/repository`) o el desembolso de cuotas de deuda (`internal/debts/repository`), se implementa `SELECT ... FOR UPDATE` sobre los registros padre o lotes físicos.
- Esto elimina race conditions en escenarios donde dos vendedores compiten por el último saldo de un lote o una venta compite por una cuota de crédito.

---

## 3. GESTIÓN DE ERRORES Y TIPADO

- No existen `panic()` no recuperados en handlers.
- Los errores de dominio se transforman en respuestas JSON uniformes (`{"error": "CODE", "message": "Detalle"}`) con códigos HTTP adecuados (400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found, 409 Conflict, 422 Unprocessable Entity).
- Tipado monetario estricto: se evitan operaciones flotantes `float64` en cálculos críticos de saldo acumulado, utilizando strings formateados o enteros en base cents donde la precisión es obligatoria.

---

## 4. OPORTUNIDADES DE MEJORA Y DEUDA TÉCNICA EN GO

| ID Hallazgo | Componente | Descripción | Severidad | Recomendación |
|---|---|---|:---:|---|
| **GO-ARCH-01** | `cmd/api/main.go` | Tamaño excesivo de `main.go` (>1800 líneas) debido a la definición en línea de todos los handlers HTTP. | **P2** | Desacoplar los handlers HTTP en subpaquetes `internal/<domain>/delivery/http` o `api/handlers`. |
| **GO-ARCH-02** | `cmd/api/main.go` | Falta middleware de Rate Limiting global y por IP/Tenant. | **P1** | Incorporar middleware de token bucket (ej. `chi/middleware/throttle` o Redis-based rate limiter). |
| **GO-ARCH-03** | `internal/platform/logger` | Los logs estructurados no incluyen tracing ID distribuido (OpenTelemetry trace_id). | **P2** | Integrar `opentelemetry-go` para propagar el `X-Request-ID` en los headers de spans de traza y métricas. |
| **GO-ARCH-04** | `cmd/api` | Ausencia de métricas Prometheus `/metrics` expuestas. | **P2** | Agregar exporter de métricas para conteo de requests, latencia p99 y conexiones activas de pgxpool. |
