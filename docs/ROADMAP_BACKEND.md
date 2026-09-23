# Roadmap Backend: Sprints y Tareas Kanban

Este plan vincula las tarjetas del Kanban de GitHub (`observatorio-predictivo`) con el alcance semanal del proyecto[cite: 1].

## Sprint 0: Configuración y Fundaciones (Semana 0)
* [ ] **Issue #8 (En Ready):** Configurar backend, base de datos y estructura inicial de APIs internas[cite: 1].
  * Configurar proyecto base en FastAPI (`pyproject.toml` o `requirements.txt`).
  * Levantar PostgreSQL en Supabase / Docker y probar conexión asíncrona[cite: 1].
  * Crear endpoint `/api/v1/health`.
* [ ] **Issue #9 (En Ready):** Definir mecanismo de carga manual de datasets[cite: 1].
  * Definir arquitectura de subida (FastAPI `UploadFile`) y parseo base con Pandas[cite: 1].
* [ ] Desplegar esqueleto inicial en Railway o Render para pruebas conjuntas con QA y Frontend[cite: 1].
* [ ] Publicar mocks/contratos JSON iniciales para descolgar el trabajo de Frontend[cite: 1].

## Sprint 1: Exploración e Ingesta Base (Semanas 1 y 2)
* [ ] **Issue #18 (Backlog):** Probar conexión con APIs seleccionadas (Datos Argentina, Banco Mundial, SIMEL)[cite: 1].
  * Implementar clientes HTTP asíncronos con HTTPX[cite: 1].
* [ ] **Issue #19 (Backlog):** Preparar flujo inicial para recepción y almacenamiento de datos[cite: 1].
  * Tablas intermedias de staging o guardado de datos crudos (raw data)[cite: 1].
* [ ] Endpoint básico de subida de CSV/Excel con validación de columnas mínimas[cite: 1].
* [ ] Coordinar con equipo de Data Analytics la tabla de normalización definitiva[cite: 1].

## Sprint 2: Core de Métricas e Índice (Semanas 3 y 4)
* [ ] Exponer endpoints para alimentar el dashboard general con filtros por país, sector y período[cite: 1].
* [ ] Robustecer la carga manual: reportar filas erróneas sin interrumpir la ejecución[cite: 1].
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