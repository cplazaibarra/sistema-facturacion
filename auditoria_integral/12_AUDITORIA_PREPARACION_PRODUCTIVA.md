# 12. AUDITORÍA DE PREPARACIÓN PRODUCTIVA — INFRAESTRUCTURA Y DEVOPS

**Fecha de Auditoría:** 17 de Octubre de 2026  
**Objetivo:** Determinar la brecha técnica y operativa requerida para operar la plataforma con clientes reales en producción.

---

## 1. ESTADO DE INFRAESTRUCTURA Y DESPLIEGUE

### 1.1 Entorno Actual
- **Servidor:** Instancia Linux local (`cplazaia`).
- **Exposición Externa:** Proxy inverso mediante **Tailscale Funnel** (`https://cplazaia.taile13f71.ts.net`), funcional pero dependiente de la máquina de desarrollo encendida.
- **Bases de Datos:** PostgreSQL en host local (puerto 5432) y PostgreSQL en Docker para V2 (puerto 5439).
- **Contenedores:** Existe archivo `docker-compose.yml` para la base de datos de V2, pero **no existe Dockerfile ni configuración de contenedor para la aplicación Go ni para V1**.

### 1.2 Brechas Críticas para Producción (Checklist de Despliegue)
- [ ] **Dockerización de la App:** Falta crear un `Dockerfile` multi-stage para compilar la aplicación Go en un binario estático ligero (imagen final basada en `scratch` o `alpine` de <25 MB).
- [ ] **Reverse Proxy y TLS:** Se requiere un proxy de borde dedicado (Nginx, Traefik o Caddy) con certificados SSL Let's Encrypt automatizados, fuera de Tailscale, para acceso corporativo abierto.
- [ ] **Estrategia de Respaldos (Backups):**
  - Actualmente los backups se realizan mediante scripts manuales (`pg_dump`).
  - No existe automatización periódica con rotación diaria/semanal ni réplica externa fuera del disco local (ej. a AWS S3 o Wasabi).
- [ ] **Plan de Recuperación ante Desastres (Disaster Recovery):** No está documentado ni probado el tiempo de recuperación (RTO) ni el punto objetivo de recuperación (RPO) ante fallo del disco físico NVMe.

---

## 2. OBSERVABILIDAD, LOGS Y MONITOREO

- **Logs:** Go y Flask emiten logs en stdout/stderr. No están centralizados en un stack de gestión de logs (Loki, Grafana, OpenSearch o Datadog).
- **Métricas:** No hay instrumentación de Prometheus en la aplicación ni paneles de Grafana para alertar sobre:
  - Uso de CPU y memoria.
  - Latencia de respuesta en endpoints HTTP.
  - Conexiones saturadas en el pool de PostgreSQL.
  - Errores 5xx o intentos de login sospechosos (ataques de fuerza bruta).
- **Healthchecks:** V2 implementa un ping básico a la base de datos al iniciar, pero no expone endpoints `/healthz` y `/readyz` estandarizados para orquestadores tipo Kubernetes o balanceadores de carga.

---

## 3. GESTIÓN DE CONFIGURACIÓN Y SECRETOS

- **Variables de Entorno:** Se utiliza archivo `.env` local.
- **Riesgo:** En entornos de producción con múltiples desarrolladores o servidores, los secretos (como `JWT_SECRET` y contraseñas de base de datos) deben gestionarse mediante gestores de secretos dedicados (HashiCorp Vault, AWS Secrets Manager o Kubernetes Secrets), evitando archivos `.env` en servidores accesibles.

---

## 4. HALLAZGOS Y RECOMENDACIONES DE PRODUCCIÓN

| ID Hallazgo | Componente | Descripción | Severidad | Recomendación |
|---|---|---|:---:|---|
| **PROD-01** | Infraestructura | Falta Dockerfile de la aplicación Go y orquestación para producción. | **P1** | Crear `Dockerfile` multi-stage optimizado para Go y `docker-compose.prod.yml` con reinicio automático y healthchecks. |
| **PROD-02** | Continuidad | Ausencia de respaldos automáticos programados fuera de la máquina local. | **P1** | Implementar cron con script automatizado de `pg_dump` cifrado y subida diaria a un bucket cloud seguro. |
| **PROD-03** | Monitoreo | Falta de endpoints de salud (`/healthz`, `/readyz`) y monitoreo de uptime. | **P2** | Agregar endpoints de salud en Chi y configurar monitoreo externo (ej. UptimeKuma o BetterStack). |
| **PROD-04** | Seguridad Red | La exposición actual depende de Tailscale Funnel en una PC de desarrollo. | **P1** | Para un entorno comercial, desplegar en un VPS/Cloud dedicado (Hetzner, AWS, DigitalOcean) con firewall estricto. |
