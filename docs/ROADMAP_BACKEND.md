# Roadmap Backend: Sprints y Tareas Kanban

Este plan vincula las tarjetas del Kanban de GitHub (`observatorio-predictivo`) con el alcance semanal del proyecto[cite: 1].

> **Estado al 04/11/2026:** Sprint 0 y Sprint 1 cerrados; Sprint 2 cerrado en su
> parte de cálculos (suite **147 tests, 0 omitidos**, ver `docs/QA_ISSUE_58_CONSISTENCIA.md`);
> Sprint 3 y 4 pendientes. El equipo de Data publicó el 02/11 el módulo de
> brechas, habilidades y alertas (`/api/v1/ds/*`), que es el insumo de S3/S4.

## Sprint 0: Configuración y Fundaciones (Semana 0)
* [x] **Issue #8 (En Ready):** Configurar backend, base de datos y estructura inicial de APIs internas[cite: 1] — *parcial: DB diferida a Sprint 1.*
  * Configurar proyecto base en FastAPI (`pyproject.toml` o `requirements.txt`).[cite: 1]
  * Levantar PostgreSQL en Supabase / Docker y probar conexión asíncrona[cite: 1] — *código listo (`app/core/database.py`); conexión real pendiente de `DATABASE_URL` (Sprint 1).*
  * Crear endpoint `/api/v1/health` — *con chequeo de DB: `ok` / `error` / `not_configured`.*
* [x] **Issue #9 (En Ready):** Definir mecanismo de carga manual de datasets[cite: 1].
  * Definir arquitectura de subida (FastAPI `UploadFile`) y parseo base con Pandas[cite: 1].
* [ ] Desplegar esqueleto inicial en Railway o Render para pruebas conjuntas con QA y Frontend[cite: 1] — *diferido; pasos documentados en README §10.*
* [x] Publicar mocks/contratos JSON iniciales para descolgar el trabajo de Frontend[cite: 1] — *`docs/mocks/`.*

## Sprint 1: Exploración e Ingesta Base (Semanas 1 y 2)
* [x] **Issue #18 (Backlog):** Probar conexión con APIs seleccionadas (Datos Argentina, Banco Mundial, SIMEL)[cite: 1] — *conectores en `app/services/connectors/` (registry `CONNECTORS`) + tests en vivo en `tests/test_connectors.py`; SIMEL/ENE vía SDMX del INE porque `www.simel.gob.cl` responde 418.*
  * Implementar clientes HTTP asíncronos con HTTPX[cite: 1].
* [x] **Issue #19 (Backlog):** Preparar flujo inicial para recepción y almacenamiento de datos[cite: 1] — *`app/services/ingestor.py` (`ingest`) + `app/services/storage/raw_store.py`.*
  * Tablas intermedias de staging o guardado de datos crudos (raw data)[cite: 1] — *JSONL en `data/raw/{fuente}/YYYY-MM-DD.jsonl` con esquema `raw_data_logs`; DB diferida.*
* [x] Endpoint básico de subida de CSV/Excel con validación de columnas mínimas[cite: 1] — *hecho en Sprint 0 (ref #9).*
* [x] Coordinar con equipo de Data Analytics la tabla de normalización definitiva[cite: 1] — *cerrado: el equipo de Data publicó las definiciones aprobadas (`DataAnalyst/DEFINICIONES_CASOS_CARGA_QA.md`) y el Backend implementó el ETL en `app/services/normalization/` (mapeo al esquema común, cuarentena y deduplicación).*

## Sprint 2: Core de Métricas e Índice (Semanas 3 y 4)
* [ ] Exponer endpoints para alimentar el dashboard general con filtros por país, sector y período[cite: 1].
* [x] Robustecer la carga manual: reportar filas erróneas sin interrumpir la ejecución[cite: 1] — *hecho: `POST /datasets/upload` clasifica cada fila (rechazo 422 con detalle por fila, cuarentena con flag o deduplicación) y devuelve el reporte (`rows_valid`, `rows_quarantined`, `duplicates_removed`, `warnings`) sin abortar el archivo.*
* [x] Implementar la fórmula matemática del Índice de Empleabilidad (provista por Data)[cite: 1] — *hecho: reimplementación local de IDELR e ICOL en `app/services/calculators/employability.py` a partir de `DataAnalyst/INFORME_METODOLOGICO_INDICES.md`, con test de paridad contra la API de Data (mismos valores).*
* [x] Exponer endpoint `/api/v1/employability` con desglose de dimensiones evaluadas[cite: 1] — *hecho: `GET /api/v1/employability` (filtros por país, sector, ocupación y período) con serie macro, ranking por ocupación y desglose de variables.*
* [x] **Issue #54:** almacenar los resultados históricos de los índices[cite: 1] — *hecho: tabla `indicator_results` (migración `4565d593028e`) + `POST /api/v1/employability/snapshot` (guardado idempotente por día) + `GET /api/v1/employability/history` (filtros por tipo, país, ocupación y rango de años). El `GET /employability` sigue siendo de solo lectura.*
* [x] **Issue #74:** preparar endpoints para habilidades y oferta formativa[cite: 1] — *hecho: `GET /api/v1/skills`, `GET /api/v1/skills/{ocupacion_id}` y `GET /api/v1/gaps`, que consumen el módulo de Data Science (`DataAnalyst/etl/data_science.py`) con degradación `live` → `cache` → `reference` → `503`.*

## Sprint 3: Series Temporales y Habilidades (Semanas 5 y 6)
* [ ] Crear endpoints de series históricas optimizados para alimentar gráficos de líneas/barras[cite: 1].
* [ ] Lógica para clasificar ocupaciones en tendencia: alza, estabilidad o caída[cite: 1] — *base lista: `clasificar_tendencia(delta, epsilon=1.0)` en `app/services/calculators/employability.py`; falta exponerla como endpoint (#67).*
* [x] Exponer modelo relacional de brechas de habilidades (oferta formativa vs. demanda)[cite: 1] — *hecho (#74 y #75): `GET /api/v1/skills`, `GET /api/v1/skills/{ocupacion_id}` y `GET /api/v1/gaps` consumen el módulo de Data Science con cache y fallback (`live` → `cache` → `reference` → 503), y `GET /api/v1/occupations/{id}` integra el bloque `brechas` (TGS, habilidades emergentes y comparación por país) reutilizando el mismo `SkillItem`, con degradación `unavailable`.*
* [ ] Asegurar trazabilidad completa en cada respuesta (fuente oficial y fecha de actualización)[cite: 1] — *parcial: `fuente_datos`, `metodologia.fuente_metodologia` y `trazabilidad` ya están en las respuestas actuales; falta extenderlo a los endpoints nuevos.*

## Sprint 4: Automatización y Alertas (Semanas 7 y 8)
* [ ] Implementar tareas programadas (schedulers) para sincronización automática de APIs oficiales[cite: 1].
* [ ] Desarrollar motor de detección de variaciones drásticas en indicadores clave[cite: 1] — *reglas R1-R4 ya definidas por Data (`GET /api/v1/ds/reglas-deteccion`); falta el motor propio del backend (#86/#87).*
* [ ] Exponer `/api/v1/alerts` clasificado por severidad (baja, media, alta)[cite: 1] — *Data ya expone `GET /api/v1/ds/alertas-tendencias` con severidades CRÍTICA/ALTA/MODERADA (#84/#87).*
* [ ] Registrar logs de ejecuciones automáticas y fallos de red[cite: 1].

## Sprint 5: Optimización y Estabilización (Semanas 9 y 10)
* [ ] Indexación y optimización de consultas SQL complejas en PostgreSQL.
* [ ] Cacheo de agregaciones para aliviar carga de la base de datos.
* [ ] Manejo de resiliencia (reintentos, circuit breaker y fallbacks ante APIs caídas)[cite: 1].
* [ ] Resolver tickets de bugs reportados por QA[cite: 1].

## Fuera de alcance del MVP

* **Filtro / selector de provincias (post-MVP):** deseable, pero los datos y el
  contrato con el equipo de Data solo tienen dimensión `país` (ARG, CHL, URY).
  Requiere ampliar el contrato, el esquema de normalización, la persistencia y
  las fuentes antes de implementarse. Ver
  [`docs/FUERA_DE_ALCANCE.md`](FUERA_DE_ALCANCE.md). Seguimiento: issue
  [#16](https://github.com/InnovaLab-2C-2026-Equipo-6/app-backend/issues/16).

## Sprint 6: Cierre y Demo Day (Semanas 11 y 12)
* [ ] Congelamiento de código (*feature freeze*)[cite: 1].
* [ ] Carga de datasets de respaldo validados en producción para garantizar una demo fluida[cite: 1].
* [ ] Documentación OpenAPI (Swagger) terminada y README técnico con instrucciones de despliegue[cite: 1].