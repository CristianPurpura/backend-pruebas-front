# Roadmap Backend: Sprints y Tareas Kanban

Este plan vincula las tarjetas del Kanban de GitHub (`observatorio-predictivo`) con el alcance semanal del proyecto[cite: 1].

## Sprint 0: Configuración y Fundaciones (Semana 0)
* [x] **Issue #8 (En Ready):** Configurar backend, base de datos y estructura inicial de APIs internas[cite: 1] — *parcial: DB diferida a Sprint 1.*
  * Configurar proyecto base en FastAPI (`pyproject.toml` o `requirements.txt`).[cite: 1]
  * Levantar PostgreSQL en Supabase / Docker y probar conexión asíncrona[cite: 1] — *código listo (`app/core/database.py`); conexión real pendiente de `DATABASE_URL` (Sprint 1).*
  * Crear endpoint `/api/v1/health` — *con chequeo de DB: `ok` / `error` / `not_configured`.*
* [x] **Issue #9 (En Ready):** Definir mecanismo de carga manual de datasets[cite: 1].
  * Definir arquitectura de subida (FastAPI `UploadFile`) y parseo base con Pandas[cite: 1].
* [ ] Desplegar esqueleto inicial en Railway o Render para pruebas conjuntas con QA y Frontend[cite: 1] — *diferido; pasos documentados en README §8.*
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
* [ ] Implementar la fórmula matemática del Índice de Empleabilidad (provista por Data)[cite: 1].
* [ ] Exponer endpoint `/api/v1/employability` con desglose de dimensiones evaluadas[cite: 1].

## Sprint 3: Series Temporales y Habilidades (Semanas 5 y 6)
* [ ] Crear endpoints de series históricas optimizados para alimentar gráficos de líneas/barras[cite: 1].
* [ ] Lógica para clasificar ocupaciones en tendencia: alza, estabilidad o caída[cite: 1].
* [ ] Exponer modelo relacional de brechas de habilidades (oferta formativa vs. demanda)[cite: 1].
* [ ] Asegurar trazabilidad completa en cada respuesta (fuente oficial y fecha de actualización)[cite: 1].

## Sprint 4: Automatización y Alertas (Semanas 7 y 8)
* [ ] Implementar tareas programadas (schedulers) para sincronización automática de APIs oficiales[cite: 1].
* [ ] Desarrollar motor de detección de variaciones drásticas en indicadores clave[cite: 1].
* [ ] Exponer `/api/v1/alerts` clasificado por severidad (baja, media, alta)[cite: 1].
* [ ] Registrar logs de ejecuciones automáticas y fallos de red[cite: 1].

## Sprint 5: Optimización y Estabilización (Semanas 9 y 10)
* [ ] Indexación y optimización de consultas SQL complejas en PostgreSQL.
* [ ] Cacheo de agregaciones para aliviar carga de la base de datos.
* [ ] Manejo de resiliencia (reintentos, circuit breaker y fallbacks ante APIs caídas)[cite: 1].
* [ ] Resolver tickets de bugs reportados por QA[cite: 1].

## Sprint 6: Cierre y Demo Day (Semanas 11 y 12)
* [ ] Congelamiento de código (*feature freeze*)[cite: 1].
* [ ] Carga de datasets de respaldo validados en producción para garantizar una demo fluida[cite: 1].
* [ ] Documentación OpenAPI (Swagger) terminada y README técnico con instrucciones de despliegue[cite: 1].