# Issue #58 — Verificar consistencia de cálculos y visualizaciones

> Diagnóstico y plan de continuación (30/10/2026)
> **Cierre del backend (04/11/2026):** suite completa ejecutada contra la API de
> Data — **147 passed, 0 skipped**. Ver "Resultado 04/11/2026" al final.

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

## Diagnóstico (app-backend, rama feature/bloque-a-integración, 9de5bf5) — *histórico*

> Este diagnóstico describe el estado del 30/10. Está **resuelto** en la parte de
> backend; ver "Resultado 04/11/2026" al final del documento.

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

---

# Resultado 04/11/2026 — cierre de la parte de backend

## Qué se hizo

### Fase 0 · Entorno

`DataAnalyst` clonado en `/tmp/opencode/DataAnalyst` y fijado en el commit
`45abdfc` (merge del 02/11, que ya incluye el módulo de Data Science).
La API de Data se levanta sola desde el fixture `data_api` de la suite.

La versión de Data auditada es la que **incorpora los cambios del 02/11**
(`etl/data_science.py`, 5 endpoints `/api/v1/ds/*`, matriz QA de 16 casos).
Su propia suite pasa **16/16**:

```bash
cd /tmp/opencode/DataAnalyst
.venv/bin/python -m unittest discover tests -v   # Ran 16 tests ... OK
```

### Fase 1 · Verificación de cálculos

Los **19 tests que estaban skipped ahora se ejecutan y pasan**. La paridad
numérica se mantiene después de los cambios del 02/11: el diff de Data sobre
`main.py` es **aditivo** (80 líneas agregadas, 0 borradas) y no toca los
endpoints `/analytics/*` que consume la paridad.

| Bloque | Tests | Estado |
| :--- | :--- | :--- |
| Suite base del backend (sin Data) | 110 | ✅ |
| Paridad IDELR vs `/analytics/indice-sintetico` | 1 | ✅ |
| Paridad ICOL vs `/analytics/ocupaciones/ranking` | 1 | ✅ |
| Matriz QA API-001..016 contra la API de Data | 16 | ✅ |
| Golden dataset de Data se ingiere completo | 1 | ✅ |
| Metodología visible (nuevo) | 18 | ✅ |
| **Total** | **147** | ✅ **0 skipped** |

Comprobación del antes/después: sin el clon de Data la suite da
**128 passed, 19 skipped** (16 de `test_data_api_matrix.py`, 2 de paridad en
`test_employability.py`, 1 de golden dataset en `test_normalization.py`); con
el clon, **147 passed, 0 skipped**.

### Metodología visible — `tests/test_employability_metodologia.py`

Se agrega el test que faltaba para el entregable *"dimensiones y ponderaciones
visibles"*:

* los pesos de las 5 variables del **IDELR** suman `1.0`;
* los pesos de las 3 componentes del **ICOL** suman `1.0`;
* `GET /employability` expone las 5 dimensiones declaradas
  (`Economía`, `Salarios`, `Empleo`, `Educación`);
* `metodologia.variables_idelr` es **idéntico** a `VARIABLES_IDELR` y
  `metodologia.ponderaciones_icol` a `DEFAULT_ICOL_WEIGHTS` (espejo, no copia);
* `epsilon_pct`, método de normalización y fuente de la metodología se
  publican;
* los umbrales de `clasificar_categoria_oportunidad` se verifican en el borde
  exacto (85 / 84.99 / 70 / 69.99 / 55 / 54.99) y coinciden con la
  implementación de Data (`etl/analytics.py`);
* cada fila del ranking expone la categoría que corresponde a su score.

> Nota: los umbrales de categoría del ICOL son **85 / 70 / 55**. Los valores
> 82 / 68 / 50 que aparecen en `INFORME_DATA_SCIENCE_BRECHAS_ALERTAS.md`
> pertenecen a la escala del *Talent Gap Score* (brechas), que es un índice
> distinto y no se expone en este endpoint.

## Qué queda pendiente

| Ámbito | Pendiente | Issue |
| :--- | :--- | :--- |
| Backend | Persistencia de resultados históricos (solo existe `raw_data_logs`) | #54, #65 |
| Backend | Series históricas, indicadores y tendencias | #64, #42, #67 |
| Backend | Habilidades, brechas y alertas (contrato ya publicado por Data) | #74, #75, #84, #85 |
| Frontend | Verificar que el dashboard muestre exactamente los valores de la API | — |
| QA | Re-ejecutar la matriz de la planilla con el contrato v2 vigente | — |

## Reproducir

```bash
git clone https://github.com/InnovaLab-2C-2026-Equipo-6/DataAnalyst.git \
  /tmp/opencode/DataAnalyst
cd /tmp/opencode/DataAnalyst && git checkout 45abdfc
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

cd ~/Code/Innova-Lab/app-backend
./venv/bin/python -m pytest -q -rs     # 147 passed
```
