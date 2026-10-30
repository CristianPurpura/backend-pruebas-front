# Issue #58 — Verificar consistencia de cálculos y visualizaciones

> Diagnóstico y plan de continuación (30/10/2026)

## Referencias

- **Issue:** https://github.com/InnovaLab-2C-2026-Equipo-6/observatorio-predictivo/issues/58
- **Project:** https://github.com/orgs/InnovaLab-2C-2026-Equipo-6/projects/1?pane=issue&itemId=263865373&issue=InnovaLab-2C-2026-Equipo-6%7Cobservatorio-predictivo%7C58
- **Prioridad:** 🔴 high (marcada manualmente en el Project)
- **Labels:** QA · frontend · backend | Estado: open | Sin cuerpo ni comentarios en GitHub
- **Origen:** plan de trabajo, Sprint 2 · Semana 4 (QA) — "Verificar consistencia de
  cálculos y visualizaciones". Depende de: datos normalizados, metodología del índice
  definida, variables mínimas cubiertas. Entregable semanal: primera versión del Índice
  de Empleabilidad funcionando · dimensiones y ponderaciones visibles · comparaciones
  iniciales · resultados históricos almacenados.

## Diagnóstico (app-backend, rama feature/bloque-a-integración, 9de5bf5)

### Cálculos — cubierto, con un agujero

- ✅ 110 tests passing: normalización Min-Max acotada, IDELR (por país/año, cobertura,
  desglose, filtros), ICOL (60 combinaciones, rango [0,100], rankings método 'min' con
  empates), perfil de ocupaciones coherente con `/employability`, filtros y validaciones 400.
- 🔴 **19 tests SKIPPADOS**: la paridad numérica contra la API de Data
  (`tests/test_employability.py::test_paridad_idelr_con_la_api_de_data` y
  `test_paridad_icol_con_la_api_de_data`, más la matriz QA de `tests/test_data_api_matrix.py`)
  no se ejecuta porque no hay instancia de `DataAnalyst` corriendo en `:8001` ni clonado en
  `/tmp/opencode/DataAnalyst`. La verificación central de la issue está escrita pero **no corre**.
- ⚠️ Falta test de **metodología visible**: que `metodologia` del endpoint exponga pesos que
  suman 1.0, las 5 dimensiones, y que endpoint ↔ calculador (`VARIABLES_IDELR`,
  `DEFAULT_ICOL_WEIGHTS`) estén espejados; umbrales de categoría coherentes.
  (Requisito explícito del entregable: "dimensiones y ponderaciones visibles".)

### Visualizaciones — fuera de este repo

- Verificar que el dashboard (repo `frontend`) muestra exactamente los valores de la API:
  ICOL, categorías, tendencias 🟢🟡🔴, rankings, dimensiones/ponderaciones.

### Dependencias

- **#54** (backend, abierta): almacenamiento de resultados históricos — hoy no se persisten
  los índices, solo existe `raw_data_logs`.
- Relacionadas del mismo bloque: #55 (cálculo inicial), #56 (ponderaciones y reglas),
  #57 (validar con ocupaciones/países), #53 (exponer índice vía API).

## Plan de continuación

1. **Levantar la API de Data**: clonar `DataAnalyst` en `/tmp/opencode/DataAnalyst`,
   servirlo en `:8001` → correr la suite completa para que los 19 skipped pasen a
   *executed* (paridad IDELR/ICOL + matriz QA).
2. **Tests de metodología**: pesos suman 1.0, 5 dimensiones, espejo endpoint ↔ calculador,
   umbrales de `clasificar_categoria_oportunidad`.
3. **Evidencia en la issue #58** (repo `observatorio-predictivo`): comentario con la
   cobertura alcanzada, tests ejecutados y pendientes restantes.
4. *(Opcional)* Revisión de la parte frontend, o dejarla anotada como pendiente a coordinar.

## Comandos útiles

```bash
# Suite completa con skips visibles
./venv/bin/python -m pytest -q -rs

# Correr solo la paridad (requiere API de Data en :8001)
./venv/bin/python -m pytest tests/test_employability.py -q

# API de Data (si el repo está clonado)
cd /tmp/opencode/DataAnalyst && python main.py --port 8001
```
