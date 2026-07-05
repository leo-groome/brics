# BRICS — Auditoría, Flujo, Visión a Futuro y Plan de Reestructuración

> Fecha: 2026-07-05 · Estado: aprobado (con enmiendas de auditoría 2026-07-05) · Ventana: 2-3 meses con 2 constructoras piloto pagando

## Enmiendas de auditoría (verificación contra código, 2026-07-05)

Correcciones fácticas:
- Frontend más avanzado que "20%": FrictionView.vue (588 LOC) y DashboardView.vue (435 LOC) ya conectados a la API vía Pinia. Semanas 3-4 son pulido, no construcción.
- `OpenAIClient` ya existe en `llm_client.py` (activable con `BRICS_LLM_BACKEND=openai`); la reescritura es cambiar el default y borrar `CodexCLIClient`.
- `services/prices.py` ya tiene lógica de recencia (código muerto porque `concepts.py` no está montado). §1.3 extiende código real.
- La task Celery se define una vez; lo triplicado es la invocación `.delay()`.

Huecos agregados al plan:
- **Seguridad (pre-commit):** `.gitignore` debe excluir `data/` completo (XLSX con presupuestos reales de clientes). Rotar credencial de Neon expuesta en `apps/backend/.env`.
- **Diseño:** el motor §1.3 requiere campo `family` + `volatility` en `master_concepts` y una clasificación batch de los 3,601 conceptos (~15 familias). Se agrega a Semana 2 como prerequisito.
- **Operativo:** Alembic en Semana 1 (hoy solo `create_all()`). Si Semana 2 se atora, INPP se difiere a Semanas 3-4; el export NO se recorta.

## Contexto

Producto: presupuestos de materiales de construcción en México (2 semanas → <1 día).
Estado real medido al momento de la auditoría:

- Backend FastAPI ~2,240 LOC; frontend Vue ~20% implementado.
- Catálogo: **3,601 conceptos** ingeridos desde 51 archivos históricos (2013-2025).
- **225 sheets fallidos** en normalización, sin razón de fallo registrada.
- Última ingesta murió con `401 Unauthorized` del Codex CLI (`full_ingest3.log`).
- Todo el código untracked en git (1 commit vacío).

---

# PARTE 0 — AUDITORÍA

## Lo que SÍ sirve (el activo real, no tocar)

- **Schema Postgres + pgvector**: `master_concepts` / `concept_prices` / `budgets` / `budget_lines` con índice HNSW (cosine) + pg_trgm. Nivel producción.
- **Matcher semántico** (`services/matcher.py`): cosine top-5, umbral 0.95 auto / friction.
- **ETL histórico**: 51/54 archivos procesados, 3,601 conceptos en catálogo.
- **Modelo de fricción** (pending → auto/friction/missing → resolved): el loop humano correcto para iterar 2-3 meses.

## Fallas críticas (orden de gravedad)

1. **Codex CLI como backend LLM — fatal.** `llm_client.py` shellea a un CLI de suscripción ChatGPT consumer. Ya murió con 401 a mitad de ingesta. No corre en Railway, no es reproducible, viola ToS para producto comercial. Normalizar ~500 sheets vía API cuesta centavos.
2. **No existe el entregable.** Cero código de export Excel/PDF. El piloto no puede llevarle un JSON a su cliente. La feature de mayor ROI no está empezada.
3. **Precios 2013-2025 sin lógica de recencia/inflación.** `observed_at` existe pero nada lo usa. Cotizar con precio de 2018 destruye la confianza en la demo #1. (Solución: §1.3.)
4. **El "agente WhatsApp" es Fase 2 disfrazada de MVP.** Celery + Redis + Evolution API (nunca instanciado) + webhooks stub + regex frágil de precios ≈ 30% de la superficie de código para un problema no confirmado por ningún piloto. Se amputa; el diseño de `suppliers`/`quote_requests` se archiva para Fase 1.
5. **Cero auth, cero tenant.** `user_id` nullable no es aislamiento. 2 constructoras con datos comerciales sensibles. Retrofit de `org_id` después de cargar datos de pilotos = migración dolorosa; se hace ahora.
6. **Git en estado de negligencia.** Todo untracked. Primer paso del plan: commit.
7. Menores: `api/v1/concepts.py` (112 LOC) nunca montado en `main.py`; `HermesClient` stub (NotImplementedError); task Celery duplicada en 3 lugares con `import logging` dentro de except; 1 solo test (`test_matcher.py`).

## Falla lógica central

**No se necesita un "ecosistema de agentes". Se necesita un pipeline con 2 llamadas a modelo.** "Agentes" es narrativa de venta; en código es un LLM con schema Pydantic + un índice vectorial + un humano en el loop. El moat no son los agentes: es el flywheel de datos (§1.4).

---

# PARTE 1 — EL FLUJO (de punta a punta)

## 1.1 El flujo del usuario (la constructora)

Lo que vive el residente/costos. Cinco pasos, una sesión:

```
┌────────────────────────────────────────────────────────────────────┐
│  PASO 1: SUBIR                                                     │
│  El usuario arrastra su Excel de cuantificación (el que hoy le     │
│  toma 2 semanas convertir en presupuesto). Formato libre: sus      │
│  columnas, sus nombres de partidas, su desorden.                   │
└──────────────────────────────┬─────────────────────────────────────┘
                               ▼
┌────────────────────────────────────────────────────────────────────┐
│  PASO 2: EXTRACCIÓN (LLM, ~30 seg)                                 │
│  El sistema lee el Excel y extrae líneas estructuradas:            │
│  { concepto_crudo, cantidad, unidad }. Una llamada LLM con         │
│  schema Pydantic. El usuario ve la tabla y corrige si algo         │
│  se leyó mal.                                                      │
└──────────────────────────────┬─────────────────────────────────────┘
                               ▼
┌────────────────────────────────────────────────────────────────────┐
│  PASO 3: MATCH AUTOMÁTICO (embeddings + pgvector, ~5 seg)          │
│  Cada línea se compara semánticamente contra el catálogo maestro   │
│  (conceptos + historial de precios de SU constructora).            │
│    · similitud ≥ 0.95  → AUTO: precio asignado, línea verde        │
│    · similitud media   → FRICTION: top-5 candidatos, línea ámbar   │
│    · sin candidatos    → MISSING: línea roja                       │
└──────────────────────────────┬─────────────────────────────────────┘
                               ▼
┌────────────────────────────────────────────────────────────────────┐
│  PASO 4: MATRIZ DE FRICCIÓN (humano, 10-30 min)                    │
│  El usuario resuelve SOLO las líneas ámbar/rojas:                  │
│    · elige un candidato del top-5 (1 clic, atajos de teclado)      │
│    · o crea el concepto nuevo con precio manual                    │
│  Cada resolución ENTRENA el catálogo: la próxima vez esa línea     │
│  matchea sola. La fricción baja semana a semana.                   │
└──────────────────────────────┬─────────────────────────────────────┘
                               ▼
┌────────────────────────────────────────────────────────────────────┐
│  PASO 5: EXPORT                                                    │
│  Botón "Generar presupuesto" → Excel profesional: partidas,        │
│  cantidades, PU, importes, fecha del precio, flag de precio        │
│  viejo (>18 meses). Listo para entregar a su cliente.              │
└────────────────────────────────────────────────────────────────────┘
```

**Resultado: lo que tomaba 2 semanas toma una sesión de trabajo.** La primera vez con fricción alta (30-40% de líneas); a las 6 semanas, fricción <15% porque el catálogo aprendió.

## 1.2 El flujo técnico (qué pasa por debajo)

```
                        ┌──────────────┐
   XLSX upload ────────▶│  FastAPI     │
                        │  /budgets    │
                        └──────┬───────┘
                               │ etl/extractor.py (ya existe, reusar)
                               ▼
                        texto crudo por sheet
                               │ llm_client.py → API (structured output)
                               ▼
                        [{raw_input, qty, unit}, ...]
                               │ matcher.match_batch() (ya existe)
                               ▼
              ┌────────────────┴────────────────┐
              │     Neon Postgres + pgvector    │
              │  master_concepts (embedding,    │
              │    HNSW cosine + pg_trgm)       │
              │  concept_prices (org_id,        │
              │    observed_at)                 │
              │  budgets / budget_lines(org_id) │
              └────────────────┬────────────────┘
                               │
              auto ≥0.95 ──────┼────── friction/missing
                               │              │
                               │       FrictionView (Vue)
                               │       resolución humana
                               │              │ realimenta catálogo
                               ▼              ▼
                        services/export.py (nuevo, openpyxl)
                               │
                               ▼
                        presupuesto.xlsx
```

Dos llamadas a modelo en todo el sistema:

1. **Extracción** — LLM API con schema Pydantic (reemplaza Codex CLI).
2. **Embeddings** — API de embeddings (reemplaza sentence-transformers local; el contenedor pasa de ~4 GB a ~200 MB, deploys en segundos).

Todo lo demás es determinista: SQL, cosine distance, reglas de umbral, openpyxl. Debuggeable, barato, sin sorpresas.

## 1.3 Motor de resolución de precios (inflación y volatilidad)

**Principio: un precio histórico nunca se "verifica" — se gestiona el riesgo en capas y se transparenta.** Así opera ya la industria (tabuladores tipo Varela/BIMSA = referencias fechadas); BRICS lo hace explícito y automático.

Resolución de precio por línea, en orden:

```
1. RECENCIA    precio observado ≤ 6 meses → usar directo         [observado]
2. AJUSTE      precio viejo × (INPP_hoy / INPP_fecha) del        [ajustado-INPP]
               subíndice de su familia (INEGI, CSV mensual,
               materiales de construcción desagregados)
3. VOLATILIDAD familia commodity (varilla/acero/cobre/aluminio)  [cotizar]
               → el ajuste NO basta, marcar "cotizar siempre";
               semi-estables (cemento/block/agregados) → INPP ok;
               mano de obra → tabulador regional
4. PARETO      líneas con importe alto (top ~20% ≈ 80% del       [cotizar]
               costo) Y precio stale/volátil → cola de
               cotización dirigida (Fase 1). Se verifican las
               ~15 líneas que mueven el dinero, no las 500.
```

**Export transparente:** cada precio sale con fecha + fuente + método (`observado | ajustado-INPP | cotizado | manual`). El constructor decide su colchón — la confianza se destruye con precios viejos presentados como actuales, no con referencias honestas.

**El flywheel corrige la staleness sola:** cada presupuesto cerrado y cada cotización respondida refresca `observed_at`; la capa 1 crece con el uso.

Implementación: tabla `inpp_indices` (familia, mes, índice — carga mensual del CSV de INEGI), campo `volatility` por familia, lógica en `services/prices.py` (módulo existente, se extiende). Cero LLM: determinista y auditable.

## 1.4 El flywheel de datos (por qué esto retiene)

```
  presupuesto nuevo ──▶ match ──▶ friction resuelta ──▶ catálogo crece
         ▲                                                    │
         │                                                    ▼
  siguiente presupuesto ◀── más auto-match, menos fricción ◀──┘
```

- Cada friction resuelta = un concepto/alias nuevo en el catálogo del tenant.
- Cada presupuesto cerrado = precios frescos en `concept_prices` con `observed_at` de hoy.
- **A los 2 meses, el catálogo de cada constructora contiene SU forma de nombrar las cosas y SUS precios reales.** Irse de BRICS = perder eso. Ese es el lock-in, no los agentes.

---

# PARTE 2 — VISIÓN A FUTURO (por fases, con puertas)

## Fase 0 — MVP "Motor de Presupuestación" (mes 1-3, AHORA)

Lo descrito en Parte 1. Un solo objetivo: **presupuesto en <1 día con >70% auto-match**. Sin agentes, sin WhatsApp, sin Celery. Éxito = los 2 pilotos generan ≥1 presupuesto/semana solos y renuevan.

## Fase 1 — "Cotización Asistida" (mes 3-5, solo con evidencia de demanda)

Cuando los pilotos digan "los precios históricos no me bastan para X partidas":

- El sistema genera automáticamente la **lista de partidas a cotizar** por familia y el mensaje sugerido por proveedor.
- **V1 Wizard-of-Oz**: un humano manda los WhatsApps y captura respuestas en la UI. Cero infra nueva.
- **V2**: si el volumen duele (>50 cotizaciones/semana), se automatiza el envío vía WhatsApp Business API. El schema `suppliers`/`quote_requests` ya existe y se reactiva aquí — por eso se archiva su diseño, no se borra.
- Aquí nace el segundo activo: **base de proveedores con precios de respuesta fechados por región**.

## Fase 2 — "Matriz Nacional de Precios" (mes 6-12)

Con N constructoras alimentando precios reales fechados y regionalizados:

- Precio de referencia por concepto × región × fecha, ajustado por índice.
- Predicción simple de tendencia (estadística, no LLM).
- Este dataset es el producto vendible a escala nacional — y lo que justifica salir del país en dic 2026: la matriz de precios es replicable por país, el motor no cambia.

## Fase 3 — "Plano → BOM" (mes 9+, la apuesta grande)

Ingesta de planos arquitectónicos → cuantificación automática → BOM → pipeline de Fase 0. El santo grial del PRD y el diferenciador real frente a Opus/Neodata. **No se toca antes** porque: (a) es investigación, no producto; (b) sin el motor de Fase 0 maduro, un BOM automático no tiene dónde aterrizar; (c) el dolor actual de los pilotos es el precio, no la cuantificación.

> **Regla de progresión: no se abre una fase sin que la anterior tenga métricas de uso real que la pidan.** Cada fase reusa el motor de la anterior; nada se construye especulativamente.

---

# PARTE 3 — PLAN MVP (semana a semana)

## Semana 1 — Cirugía y base ✅ EJECUTADA 2026-07-05

- [x] **`.gitignore`: excluir `data/` completo** (XLSX de clientes) ANTES de cualquier `git add`.
- [ ] **Rotar credencial de Neon** (password en claro en `apps/backend/.env`). ← ÚNICO PENDIENTE (manual, consola Neon) + poner `OPENAI_API_KEY` real.
- [x] **Commit todo a git** antes de tocar nada. (2e750e7)
- [x] **Alembic init** — migración 0001 (orgs + org_id) aplicada en Neon. `create_all()` sigue en lifespan por ahora; retirarlo cuando el schema estabilice.
- [x] Amputar: `workers/` (Celery), `api/v1/webhooks.py`, `api/v1/suppliers.py` + SuppliersView, Redis del docker-compose, `HermesClient`. Diseño archivado en `docs/fase1.md`. `api/v1/concepts.py` montado. (38df772)
- [x] Reescribir `services/llm_client.py`: solo OpenAIClient (structured outputs + retry + logging). Codex CLI muerto. (38df772)
- [x] Multi-tenant: tabla `orgs` (API key hasheada SHA-256), `org_id` en budgets (NOT NULL) y concept_prices (NULL = catálogo semilla), header `X-API-Key` en todos los routers, alta con `scripts/create_org.py`. (6c1763b)
- [x] Normalizer: campo `error` en failures. (38df772)
- [x] **Auditoría de seguridad post-Semana-1 (subagente): PASA CON OBSERVACIONES — todas corregidas**: filtro org en queries de precios (fuga cross-tenant latente), API key hasheada en DB, `API_BASE` y CORS configurables por env, límites en `limit`, `--reload` fuera del compose, `GET /budgets` (lista) agregado. **Riesgo aceptado Fase 0**: la API key del tenant viaja en el bundle del frontend (`VITE_BRICS_API_KEY`) — aceptable con 2 pilotos controlados; migrar a sesión server-side (Clerk o JWT httpOnly) antes de acceso externo/self-serve.

**Hallazgo de datos (afecta Semana 2):** la DB real tenía 1,622 conceptos (no 3,601 — la ingesta murió a la mitad; los 3,601 están en `data/_extracted/_normalized/*.json`) y `concept_prices` no existía: hay CERO precios en DB. La ingesta nunca extrajo precios, solo conceptos. Semana 2 es re-ingesta completa (conceptos + precios), no solo re-embed.

## Semana 2 — Datos confiables + entregable

- [ ] Re-correr normalización completa vía API, incluidos los 225 sheets fallidos; medir tasa real de éxito.
- [ ] Re-embed catálogo (3,601 conceptos) con API de embeddings; retirar sentence-transformers del contenedor.
- [ ] **Clasificar familia + volatilidad**: campos `family`/`volatility` en `master_concepts`, clasificación batch de los 3,601 conceptos (~15 familias, LLM por lote o reglas keyword). Prerequisito del motor de precios.
- [ ] Motor de resolución de precios (§1.3) en `services/prices.py`: recencia → ajuste INPP → volatilidad → Pareto. Tabla `inpp_indices` + carga del CSV de INEGI. Campo `volatility` por familia.
- [ ] **`services/export.py`**: Excel del presupuesto (openpyxl ya es dependencia). Partidas, PU, importes, fecha de precio, método, flags. EL entregable.

## Semanas 3-4 — End-to-end + piloto 1

- [ ] Endpoint upload XLSX → `etl/extractor.py` (reusar) → LLM → bulk lines → `matcher.match_batch()`.
- [ ] Terminar FrictionView (Vue): elegir candidato, crear concepto, atajos de teclado. Nada más de UI.
- [ ] Deploy: Railway (backend) + Vercel (front) + Neon. CI por GitHub.
- [ ] Ingerir históricos del **piloto 1** en su org. Sesión en vivo: su Excel real → presupuesto exportado. **Cronometrar.**

## Mes 2 — Iteración con uso real

- [ ] Piloto 2 onboarded con el mismo playbook.
- [ ] Flywheel activo: friction resuelta y presupuestos cerrados escriben a catálogo/precios.
- [ ] Métricas semanales (el argumento de renovación): % auto-match, líneas friction/presupuesto, tiempo total/presupuesto, presupuestos/semana.
- [ ] Tests de los 3 caminos críticos: upload→match, friction resolve, export.

## Mes 3 — Puerta a Fase 1

- [ ] Solo si los pilotos lo piden: lista de partidas a cotizar + captura manual de respuestas (Wizard-of-Oz). Cero automatización de WhatsApp todavía.

## Verificación y criterios de éxito

| Hito | Criterio |
|---|---|
| Semana 4 (E2E) | Excel real de piloto → presupuesto Excel exportado con precios fechados, en una sesión, cronometrado |
| Mes 2 | Presupuesto en <1 día; >70% auto-match; pilotos generando ≥1 presupuesto/semana sin asistencia |
| Mes 3 (renovación) | Pilotos renuevan con las métricas en la mano |
