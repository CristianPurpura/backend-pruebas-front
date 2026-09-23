# Technical Specification: Observatorio Predictivo Backend

## 1. Contexto y Propósito
Plataforma web orientada a gobiernos, instituciones educativas y tomadores de decisiones para el análisis de tendencias socioeconómicas, laborales y educativas en Argentina, Uruguay y Chile[cite: 1].
El backend es responsable de la ingesta de datos (APIs públicas y carga de archivos), normalización, almacenamiento relacional, cálculo del Índice de Empleabilidad, detección de brechas y exposición de una API REST documentada[cite: 1].

## 2. Alcance del MVP
* **Geografía inicial:** Argentina, Uruguay y Chile[cite: 1].
* **Sectores (5):** Tecnología, Salud, Energía, Turismo, Economía del Conocimiento[cite: 1].
* **Ocupaciones:** ~20 perfiles estratégicos[cite: 1].
* **Flujo general:** Fuentes oficiales / Cargas -> Ingesta -> Normalización -> Métricas / Alertas -> API REST -> Frontend / QA[cite: 1].

## 3. Stack Tecnológico Sugerido (Sujeto a Brainstorming)
* **Lenguaje:** Python 3.11+[cite: 1]
* **Framework Web:** FastAPI (documentación Swagger nativa, alta velocidad y validaciones automáticas)[cite: 1]
* **Validación & Schemas:** Pydantic v2
* **ORM & Migraciones:** SQLAlchemy 2.0 (async) / SQLModel + Alembic
* **Base de Datos:** PostgreSQL / Supabase[cite: 1]
* **Cliente HTTP:** HTTPX (asíncrono para ingesta de APIs)[cite: 1]
* **Procesamiento de Archivos:** Pandas + OpenPyXL (lectura y validación de CSV y Excel)[cite: 1]
* **Automatización / Schedulers:** APScheduler / BackgroundTasks (para actualización periódica)[cite: 1]
* **Testing:** Pytest + Postman[cite: 1]
* **Hosting preliminar:** Railway / Render[cite: 1]

## 4. Fuentes Oficiales Objetivo (Ingesta Inicial)
* **Argentina:** API de Series de Tiempo (Datos Argentina), datasets INDEC / Trabajo, Banco Mundial, CEPALSTAT, ILOSTAT[cite: 1].
* **Uruguay:** Catálogo Nacional de Datos Abiertos (AGESIC), INE Uruguay, Banco Mundial, CEPALSTAT, ILOSTAT[cite: 1].
* **Chile:** SIMEL Chile (API INE), Banco Central de Chile WS, SABE (SENCE), Banco Mundial, CEPALSTAT, ILOSTAT[cite: 1].

## 5. Arquitectura del Sistema
1. **Módulo de Conectores (Ingesta):** Clientes HTTP específicos por fuente y parser de carga manual de archivos planos[cite: 1].
2. **Módulo de Normalización & Almacenamiento:** Tablas para métricas unificadas, metadatos y trazabilidad (fuente y fecha)[cite: 1].
3. **Módulo Analítico:** Lógica de cálculo del Índice de Empleabilidad, cálculo de tendencias/variaciones y generador de alertas[cite: 1].
4. **Módulo API REST:** Endpoints versionados (`/api/v1`) con filtros dinámicos y respuestas serializadas para el frontend[cite: 1].

## 6. Modelo de Datos Tentativo (Entidades Core)
* `countries`: `code` (ARG, URY, CHL), `name`, `currency`.
* `sectors`: `id`, `code`, `name` (Tecnología, Salud, etc.)[cite: 1].
* `occupations`: `id`, `sector_id`, `name`, `code_ciuo`.
* `data_sources`: `id`, `name`, `type` (API/MANUAL), `url`, `frequency`, `last_synced_at`[cite: 1].
* `raw_data_logs`: `id`, `source_id`, `raw_payload`, `status`, `created_at`.
* `normalized_metrics`:
  * `id`
  * `country_code`
  * `sector_id`
  * `occupation_id` (nullable)
  * `metric_name` (ej. `salario_promedio_usd`, `tasa_empleo`, `puestos_vacantes`)
  * `value` (float)
  * `period` (YYYY-MM o YYYY-QQ)
  * `is_projection` (boolean)[cite: 1]
  * `source_id`, `updated_at`[cite: 1]
* `employability_scores`: `occupation_id`, `country_code`, `period`, `overall_score`, `dimensions_json`[cite: 1].
* `skill_gaps`: `occupation_id`, `skill_name`, `demand_level`, `educational_offer_level`, `gap_score`[cite: 1].
* `system_alerts`: `id`, `severity`, `title`, `description`, `trigger_metric_id`, `created_at`[cite: 1].

## 7. Contratos de Endpoints (Fase Inicial)
* `GET /api/v1/health` -> Chequeo de conexión a DB y estado general.
* `GET /api/v1/indicators` -> Filtros: `country`, `sector`, `occupation`, `period_from`, `period_to`[cite: 1].
* `POST /api/v1/datasets/upload` -> Carga manual de archivos con validación previa de headers y tipos[cite: 1].
* `GET /api/v1/employability` -> Índice general y ponderaciones por ocupación[cite: 1].
* `GET /api/v1/alerts` -> Listado de variaciones y advertencias recientes[cite: 1].

* `GET /api/v1/occupations/{occupation_id}`:
  Retorna la ficha consolidada de ocupación según el esquema acordado:
  - `country`: `{ code: str, name: str }`
  - `sector`: `{ id: str, name: str }`
  - `occupation`: `{ id: str, name: str, isco_code: str }`
  - `indicators`: `{ demand_level: str, annual_growth: float }`
  - `skills`: `list[str]`
  - `traceability`: `{ source: str, source_url: str, last_updated: str, retrieved_at: str, data_type: str }`
