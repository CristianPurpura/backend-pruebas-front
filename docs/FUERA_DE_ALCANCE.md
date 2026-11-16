# Funcionalidades fuera del alcance del MVP

Documento de registro de features **evaluadas y descartadas para el MVP** (o
diferidas a post-MVP). No son bugs ni deuda técnica: son decisiones de alcance.

---

## Filtro / selector de provincias

**Estado:** ⛔ Fuera de alcance (post-MVP)
**Evaluado:** 16/11/2026
**Issue de seguimiento:** [#16](https://github.com/InnovaLab-2C-2026-Equipo-6/app-backend/issues/16)
**Origen:** aparece como necesidad de producto en
`docs/Observatorio_predictivo.txt:354` ("Análisis territorial: incorporar
provincias, departamentos, regiones o ciudades…") y fue consultado por el
equipo de Frontend.

### Qué se pedía

Poder filtrar el Observatorio por provincia (y eventualmente por
departamento/ciudad) dentro de cada país, para ver diferencias territoriales.

### Por qué queda fuera de alcance

No es una limitación del backend: **los datos y el contrato acordado con el
equipo de Data no tienen dimensión territorial subnacional**. Implementar el
filtro hoy daría un selector que no filtra nada o, peor, datos inventados.

| Evidencia | Detalle |
| --- | --- |
| `docs/SPEC.md:42-52` | El modelo `normalized_metrics` solo tiene `country_code` |
| `docs/Data_Contracts.md:62-80` | La plantilla de carga manual no tiene columna de provincia |
| `docs/Data_Contracts.md:86-100` | El esquema común de Data no tiene campo territorial |
| `docs/Data_Contracts.md:114` | La clave natural de unicidad es país + dimensión + indicador + período + … |
| `docs/Data_Contracts.md:120` | Cobertura de referencia declarada: "3 países × 45 registros = 135" |
| `app/core/catalogs.py` | Único catálogo geográfico: `PAISES_INFO` = ARG, CHL, URY |
| `data/reference/*.json` | Sin campos geográficos subnacionales |
| `docs/mocks/*.json` | Ídem (el campo `regional` es ranking entre países) |
| `app/models/indicator_result.py` | Índices por `pais`, `anio`, `ocupacion_id`; sin territorio |

Salvedad técnica: `data/raw/simel_chile/*.jsonl` trae `AREA_REF` (código de
región de Chile, 01–16), pero `app/services/connectors/simel_chile.py:66-75`
solo lee `TIME_PERIOD` y `OBS_VALUE`, así que se descarta. Y la serie de
`datos.gob.ar` configurada (`148.3_INIVELNAL_DICI_M_26`) es un índice
**nacional**. Es decir, tampoco hay desagregado provincial en las fuentes
elegidas.

### Impacto si se implementara sobre el estado actual

* El selector devolvería provincias pero todos los valores serían idénticos al
  total país (o vacíos).
* Rompería la clave natural de deduplicación del ETL (dos filas de la misma
  provincia colapsarían en una).
* Requeriría migración de esquema y reingesta completa del golden dataset.

### Qué haría falta para promoverla a "in scope"

1. **Contrato de datos (con equipo Data)**
   - Nuevas columnas `provincia_codigo` (ISO 3166-2, p. ej. `AR-B`) y
     `provincia_nombre`.
   - Definir si son obligatorias u opcionales (nullable cuando la fuente es
     nacional) y cómo se agrega a nivel país.
   - Actualizar la clave natural de unicidad y la cobertura de referencia.
2. **Catálogo**
   - `PROVINCIAS` en `app/core/catalogs.py`, vinculado a `PAISES_INFO`.
   - `ProvinceOut` en `app/schemas/catalog.py` y
     `GET /api/v1/provinces?pais=ARG`.
3. **Ingesta y normalización**
   - `provincia_codigo` / `provincia_nombre` en `NORMALIZED_COLUMNS`
     (`app/services/normalization/mapper.py`) y en el mapeo/parser.
   - Validación `provincia ∈ país` (cuarentena si no coincide).
   - Aprovechar `AREA_REF` en el conector SIMEL si se confirma su semántica.
4. **API**
   - Parámetro opcional `provincia` en `/api/v1/employability`,
     `/api/v1/employability/history`, `/api/v1/skills` y `/api/v1/gaps`.
   - Extender `EmployabilityFilters` con `provincia`.
   - Regla de compatibilidad: sin `provincia` se devuelve el agregado país
     (comportamiento actual, sin breaking changes).
5. **Persistencia**
   - Columna + índice en `indicator_results`, migración Alembic nueva y ajuste
     de `dedupe_key`.
6. **Datos**
   - Series provinciales reales por fuente (INDEC/EPH por provincia, INE
     Chile por región, INE Uruguay por departamento) o dataset del equipo Data.
7. **Frontend**
   - Selector en cascada país → provincia, siguiendo el patrón de filtros ya
     usado en el prototipo archivado (`docs/prototipos/mvp-qa/`).

### Decisión

Se mantiene **país** como única dimensión geográfica del MVP. El filtro de
provincias queda documentado como mejora post-MVP y no se implementa hasta que
exista el contrato de datos y las fuentes con desagregado territorial.

> No confundir con el filtro "**Área**" del prototipo
> (`docs/prototipos/mvp-qa/dashboard.py`): es área de conocimiento
> (p. ej. "Ingeniería de Software"), no una división geográfica.

---

## Otros ítems diferidos

El resto de las mejoras listadas en `docs/Observatorio_predictivo.txt`
(más países, más sectores, más ocupaciones, nuevas fuentes, modelos
predictivos, alertas personalizadas, perfiles institucionales, reportes
automáticos, IA) también está fuera del alcance del MVP y se rastrea en
`docs/ROADMAP_BACKEND.md`.
