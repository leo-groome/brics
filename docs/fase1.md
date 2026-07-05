# Fase 1 — Cotización Asistida (diseño archivado)

> Archivado 2026-07-05 durante la reestructuración. Este código/schema se AMPUTÓ del MVP
> (Fase 0) y se reactiva SOLO cuando los pilotos pidan cotización de precios que el
> histórico no cubre. Ver regla de progresión en PLAN_REESTRUCTURACION.md.

## Qué existía y dónde quedó

| Pieza | Estado | Recuperación |
|---|---|---|
| `workers/celery_app.py` + `workers/tasks.py` (Celery, task `quote_line`) | borrado | `git log` — commit "chore: commit codebase completo pre-reestructuración" (2e750e7) |
| `api/v1/webhooks.py` (webhook Evolution API, Bearer token) | borrado | mismo commit |
| `api/v1/suppliers.py` (CRUD suppliers) | borrado | mismo commit |
| `SuppliersView.vue` + ruta `/suppliers` | borrado | mismo commit |
| Redis en docker-compose + `REDIS_URL` | borrado | mismo commit |
| Tablas `suppliers` / `quote_requests` (`models/domain.py`) | **CONSERVADAS** en el schema | se reactivan aquí |

## Schema conservado

- `suppliers`: name, whatsapp_number (unique), families (ARRAY), active, created_at.
  - Pendiente al reactivar: `active` es Integer → migrar a Boolean; agregar `org_id` y `region`.
- `quote_requests`: budget_line_id (FK CASCADE), supplier_id (FK), sent_at, response_text,
  response_price, status (queued→sent→responded), created_at.
  - Pendiente al reactivar: `org_id`, `requested_price_at` para alimentar `concept_prices.observed_at`.

## Flujo diseñado (V1 Wizard-of-Oz — SIN infra nueva)

1. El motor de precios (§1.3 del plan) marca líneas `[cotizar]` (familia volátil o Pareto top-20% stale).
2. Endpoint genera lista de partidas a cotizar agrupada por familia + mensaje sugerido por proveedor.
3. **Un humano** manda los WhatsApps y captura respuestas en una UI mínima (reactivar `quote_requests` con captura manual).
4. Cada respuesta escribe a `concept_prices` con `observed_at` = hoy → alimenta el flywheel.

## Flujo V2 (solo si >50 cotizaciones/semana)

- Envío automático vía **WhatsApp Business API oficial** (NO Evolution API — era wrapper no oficial,
  riesgo de ban y dependencia frágil).
- Cola: en ese momento evaluar si basta un background task de FastAPI o si Celery/Redis se justifica.
  No reinstalar Celery por default.
- Parser de respuesta de precio: LLM con schema Pydantic (`llm_client.structured_extract`),
  NO el regex frágil que tenía `workers/tasks.py`.

## Activo que nace aquí

Base de proveedores con precios de respuesta fechados por región — el insumo de la
Fase 2 (Matriz Nacional de Precios).
