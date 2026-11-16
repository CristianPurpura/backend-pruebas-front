
```markdown
# Contratos de Datos y Schemas (Mocks Oficiales)

Este documento define la estructura de intercambio y normalización entre Frontend, Data y Backend.

## 1. Ocupación Individual y Ficha Técnica
* **Ruta:** `GET /api/v1/occupations/{occupation_id}?country={code}`
* **Payload de respuesta:**

```json
{
  "country": {
    "code": "ARG",
    "name": "Argentina"
  },
  "sector": {
    "id": "TEC",
    "name": "Tecnología"
  },
  "occupation": {
    "id": "OCUP_01",
    "name": "Desarrollador de Software y Aplicaciones",
    "isco_code": "2512"
  },
  "indicators": {
    "demand_level": "Muy Alta",
    "annual_growth": 18.5
  },
  "skills": [
    "Python",
    "FastAPI",
    "React",
    "SQL",
    "Git"
  ],
  "traceability": {
    "source": "INDEC-EPH",
    "source_url": "https://www.indec.gob.ar",
    "last_updated": "2025-Q3",
    "retrieved_at": "2026-09-18",
    "data_type": "observed"
  }
}
```

## 2. Catálogos Base (Normalización)

### Países (`countries`)
* `ARG`: Argentina
* `URY`: Uruguay
* `CHL`: Chile

### Sectores (`sectors`)
* `TEC`: Tecnología
* `SAL`: Salud
* `ENE`: Energía
* `TUR`: Turismo
* `ECO`: Economía del Conocimiento

## 3. Formato para Ingesta Manual (CSV / Excel)
Para el parser de carga manual (`POST /api/v1/datasets/upload`), las columnas obligatorias esperadas en la plantilla son:

| Columna | Tipo | Ejemplo | Descripción |
| :--- | :--- | :--- | :--- |
| `country_code` | String(3) | `ARG` | Código ISO-3 del país (`ARG`, `CHL`, `URY`) |
| `sector_id` | String(10) | `TEC` | ID de sector oficial (`TEC`, `SAL`, `ENE`, `TUR`, `ECO`) |
| `occupation_id` | String(20) | `OCUP_01` | Identificador de ocupación del catálogo `OCUP_01`..`OCUP_20` |
| `metric_name` | String(50) | `Tasa de Desocupación Total` | Nombre de la métrica (se homologa contra el catálogo de indicadores) |
| `metric_value` | Float | `18.5` | Valor numérico |
| `period` | String(10) | `2025`, `2025-Q3`, `2025-06` | Período de referencia |
| `source_name` | String(100)| `INDEC-EPH` | Organismo oficial |
| `data_type` | String(20) | `percentage` | Unidad de la métrica: `percentage`, `currency` o `count` |
| `is_projection` | Bool | `false` | **Opcional.** `true` si el dato es una proyección |

> **Cambio de contrato (v2).** `data_type` pasó a describir la **unidad de
> medida** (`percentage` / `currency` / `count`) según la definición aprobada
> por el equipo de Data, y la semántica observado/proyectado pasó a la
> columna opcional `is_projection` (equivale a `is_projection` de
> `normalized_metrics` en la SPEC §6). Los valores `observed` / `projected`
> ya no son válidos.

## 4. Normalización al esquema común (Data)

Cada fila válida se transforma al esquema común aprobado por el equipo de Data
(`ESQUEMA_COLUMNAS` de `etl/cleaner.py` en el repo `DataAnalyst`), más dos
columnas propias del Backend:

| Campo origen (Backend) | Transformación | Campo canónico | Tipo |
| :--- | :--- | :--- | :--- |
| `country_code` | `UPPER` + `TRIM`, resolución contra `PAISES_INFO` | `pais_codigo_iso3` | str (ISO-3) |
| (derivado) | Catálogo institucional de países | `pais_nombre` | str |
| `sector_id` | Resolución contra el catálogo de sectores | `dimension` | str |
| `occupation_id` | Catálogo de ocupaciones (`OCUP_01`..`OCUP_20`) | `occupation_id` *(extra)* | str |
| `metric_name` | Homologación con `INDICADORES_ALIAS` | `indicador_nombre` | str |
| `period` | Extracción del componente anual | `anio` | int |
| `period` | Normalización de granularidad (`Anual`, `Trimestre N`, mes) | `periodo` | str |
| `metric_value` | Casteo a flotante redondeado a 2 decimales | `valor` | float |
| `data_type` | Homologación a la etiqueta canónica de unidad | `unidad_medida` | str |
| `source_name` | Limpieza y validación de fuente oficial | `fuente_oficial` | str |
| (metadata) | `NOW()` en UTC | `fecha_extraccion` | str (ISO-8601) |
| `is_projection` | Booleano (`true`/`false`/`1`/`0`) | `is_projection` *(extra)* | bool |

Equivalencia de unidades: `percentage` → `Porcentaje (%)`, `currency` → `Moneda (USD)`, `count` → `Unidades (conteo)`.

### 4.1 Clasificación de filas (LOAD-006 / LOAD-010 / LOAD-011 / LOAD-012)

| Nivel | Situación | Resultado |
| :--- | :--- | :--- |
| 1 | Campo obligatorio vacío, `metric_value` no numérico, `country_code` fuera del alcance, `data_type` inválido, `period` con formato inválido, `occupation_id` con formato inválido | **HTTP 422**: el archivo se rechaza de forma atómica, con detalle por fila (`row`, `field`, `value`, `cause`). No entra al pipeline. |
| 2 | `sector_id` u `occupation_id` fuera del catálogo → `UNMAPPED_CATALOG`; valor fuera de rango lógico → `OUTLIER_RANGE` | **Cuarentena**: la fila se aísla (con su flag y causa) y el resto del archivo se procesa. |
| 3 | Misma clave natural dentro del mismo lote | **Deduplicación**: se conserva **el último** registro. Si el valor difiere se emite el warning *"Registro sobreescrito por actualización en la misma carga"*. |

* **Clave natural de unicidad:** `pais_codigo_iso3`, `dimension`, `indicador_nombre`, `anio`, `periodo`, `unidad_medida`, `fuente_oficial` **+ `occupation_id`**.
* **Cobertura de referencia (LOAD-009):** 3 países × 45 registros = **135** (5 indicadores × 3 dimensiones × 3 períodos).

### 4.2 Respuesta del endpoint

```json
{
  "filename": "carga_2026.csv",
  "status": "ok_with_warnings",
  "input_schema": "manual",
  "rows_count": 135,
  "rows_valid": 133,
  "rows_rejected": 0,
  "rows_quarantined": 2,
  "duplicates_removed": 1,
  "columns_detected": ["country_code", "sector_id", "..."],
  "normalized_columns": ["pais_codigo_iso3", "pais_nombre", "..."],
  "warnings": ["Registro sobreescrito por actualización en la misma carga (fila 42 reemplaza a la fila 17)"],
  "quarantine": [{"row": 88, "flag": "OUTLIER_RANGE", "cause": "valor 150.0 fuera del rango lógico de un porcentaje (0..100)", "payload": {}}],
  "output_path": "data/processed/2026-10-21/120000_carga_2026.csv",
  "quarantine_path": "data/quarantine/2026-10-21/120000_carga_2026.jsonl",
  "message": "Archivo normalizado: 133 fila(s) válida(s), 2 en cuarentena, 1 duplicado(s) descartado(s)."
}
```

* El dataset normalizado se escribe en `data/processed/{fecha}/` (CSV `utf-8-sig`) y la cuarentena en `data/quarantine/{fecha}/` (JSONL).
* `?persist=false` devuelve el reporte sin escribir en disco.

### 4.3 Ingesta de datasets ya normalizados

Si el archivo ya viene en el esquema común de Data (las 10 columnas
`pais_codigo_iso3` … `fecha_extraccion`), el endpoint lo reconoce
(`input_schema: "common"`) y lo procesa sin transformaciones. Permite
reingerir el golden dataset regional (`dataset_consolidado_regional.csv`) sin
pérdidas: 135 registros, 45 por país.

## 4.4 Brechas de talento y oferta formativa (issue #74)

Los endpoints `GET /api/v1/skills`, `GET /api/v1/skills/{ocupacion_id}` y
`GET /api/v1/gaps` consumen el **módulo de Data Science** del equipo de Data
(`DataAnalyst/etl/data_science.py`, publicado el 02/11) y lo normalizan a un
contrato propio, para que el Frontend no dependa de la forma interna de Data.

### 4.4.1 Correspondencia de campos

| Campo de Data | Campo del contrato | Nota |
| :--- | :--- | :--- |
| `pais_codigo_iso3` | `pais` | Se normaliza a mayúsculas |
| `sector` | `sector` | Nombre canónico del catálogo del Backend |
| `ocupacion_id` / `ocupacion_nombre` | `ocupacion_id` / `ocupacion_nombre` | |
| `codigo_ciuo08_oit` | `ciuo08` | |
| `indice_oportunidad_icol` | `icol` | |
| `score_brecha_talento_100` | `score_brecha` | *Talent Gap Score* (0-100) |
| `coeficiente_cobertura_educativa_cce` | `cce` | Coeficiente de cobertura educativa |
| `score_demanda_mercado` | `score_demanda_100` | Score de demanda del mercado (0-100) |
| `score_crecimiento_estimado` | `score_crecimiento_100` | Score de crecimiento estimado (0-100) |
| (derivado) | `factor_madurez_pais` | `URY 1.05`, `CHL 1.00`, `ARG 0.95` |
| (derivado) | `brecha_cobertura_pct` | `max(0, 1 − CCE) × 100` |
| (derivado) | `tgs_desglose` | Desglose 55/25/20 del TGS (demanda, crecimiento y cobertura) |
| `diagnostico_brecha` / `icono_brecha` / `urgencia_intervencion` | `diagnostico` / `icono` / `urgencia` | |
| `habilidades_tradicionales` | `habilidades_tradicionales` | Lista (Data puede devolver texto separado por comas) |
| `habilidades_emergentes_2026` | `habilidades_emergentes` | Lista |
| `nivel_adopcion_habilidades` / `impacto_ia_automatizacion` / `velocidad_obsolescencia` | `nivel_adopcion` / `impacto_ia` / `obsolescencia` | |
| `egresados_anuales_estimados` | `egresados_anuales` | Estimación (`is_projection: true`) |
| `demanda_anual_puestos_nuevos` | `demanda_anual` | Estimación |
| `brecha_anual_puestos_deficit` | `deficit_anual` | Estimación |
| `crecimiento_matricula_anual` | `crecimiento_matricula_pct` | Se extrae el número de textos como `"+14.2% anual"` |
| `diagnostico_descalce` / `estado_alerta` / `semaforo` | `diagnostico` / `estado` / `semaforo` | |
| `fuentes_oficiales_cruzadas` | `fuentes` | Lista |

### 4.4.2 Envoltura de la respuesta

```json
{
  "meta": { "fuente": "live", "actualizado": null, "detalle": "" },
  "filtros": { "pais": "URY", "sector": "Tecnología" },
  "total": 20,
  "items": [ ... ]
}
```

* `meta.fuente`: `live` (API de Data), `cache` (respuesta reciente en memoria),
  `reference` (snapshot commiteado en `data/reference/`) o **503** si no hay ninguna.
* `meta.actualizado`: fecha del snapshot de referencia (o `null` en `live`).
* `is_projection`: las cifras educativas y de demanda son **estimaciones**.

### 4.4.3 Validaciones

| Situación | Respuesta |
| :--- | :--- |
| `pais` fuera de ARG/CHL/URY | **400** |
| `sector` fuera de los 5 del catálogo (por código, slug o nombre) | **422** |
| `ocupacion_id` con formato inválido (`OCC-1`) | **422** |
| `ocupacion_id` válido pero fuera de catálogo (`OCUP_99`) | **404** |
| Ocupación sin datos de brecha | **404** |
| Data caído, sin caché y sin referencia | **503** |

## 4.5 Agregados para el dashboard (`GET /api/v1/gaps/summary`)

`GET /api/v1/gaps/summary?pais=&sector=` devuelve los totales de oferta,
demanda y brecha, más una fila enriquecida por país × sector. Se calcula
sobre el mismo payload de Data que `/gaps` (degradación `live` → `cache` →
`reference`) y **no modifica** el contrato de `/gaps`.

### 4.5.1 Fórmulas

Para cada país `p` y sector `s`:

- **D** = `demanda_anual_puestos_nuevos`
- **O** = `egresados_anuales_estimados`

```text
Déficit bruto     = Σ max(0, D − O)
Brecha neta       = Σ (D − O)
Superávit total   = Σ max(0, O − D)
CCE               = O / D
CCE ponderado     = Σ O / Σ D        (nunca promedio simple)
Brecha cobertura  = max(0, 1 − CCE) × 100
TGS               = min(100, (0.55·demanda + 0.25·crecimiento
                      + 0.20·max(0, 1 − CCE)·100) · factor_país)
```

`factor_país`: URY `1.05`, CHL `1.00`, ARG `0.95`.

Las filas sin demanda u oferta **no entran** en los agregados. Si `D = 0`,
`cce_ponderado` y `brecha_cobertura_pct` viajan en `null`.

### 4.5.2 Umbrales

**CCE (cobertura educativa):**

| Rango CCE | Diagnóstico | Estado | Semáforo |
| :--- | :--- | :---: | :---: |
| `< 0.60` | Déficit Formativo Severo | `CRITICA` | 🔴 |
| `0.60 – 0.85` | Déficit Formativo Moderado | `ALERTA` | 🟡 |
| `0.85 – 1.20` | Equilibrio Formativo-Laboral | `ESTABLE` | 🟢 |
| `> 1.20` | Superávit / Riesgo de subempleo | `ATENCION` | 🔵 |

**TGS (brecha de talento):**

| Rango TGS | Diagnóstico | Prioridad |
| :--- | :--- | :--- |
| `≥ 82.0` | Déficit Crítico de Talento | 1 — Formación acelerada |
| `68.0 – 82.0` | Déficit Moderado de Especialistas | 2 — Actualización curricular |
| `50.0 – 68.0` | Equilibrio Oferta-Demanda | 3 — Monitoreo regular |
| `< 50.0` | Superávit Relativo / Saturación | 4 — Reconversión |

La regla de alerta **R3** de Data dispara con `CCE < 0.60` o `CCE > 1.40`;
el semáforo del dashboard usa `1.20` como corte de superávit.

### 4.5.3 Respuesta (extracto)

```json
{
  "meta": { "fuente": "reference", "actualizado": "2026-11-04T16:33:36+00:00", "detalle": "" },
  "filtros": { "pais": null, "sector": null },
  "total_sectores": 15,
  "totales": {
    "demanda_anual": 165250.0,
    "egresados_anuales": 113450.0,
    "deficit_bruto": 51800.0,
    "brecha_neta": 51800.0,
    "superavit_total": 0.0,
    "cce_ponderado": 0.687,
    "brecha_cobertura_pct": 31.3
  },
  "por_pais": [ ... ],
  "por_sector": [
    {
      "pais": "ARG",
      "sector": "Tecnología",
      "demanda_anual": 22000.0,
      "egresados_anuales": 12500.0,
      "deficit_anual": 9500.0,
      "cce": 0.568,
      "brecha_cobertura_pct": 43.2,
      "crecimiento_matricula_pct": 14.2,
      "estado_cce": "CRITICA",
      "semaforo": "🔴",
      "is_projection": true
    }
  ]
}
```

El ejemplo completo y copiable está en `docs/mocks/gaps_summary.json`.

### 4.5.4 Trazabilidad y notas

- Fórmulas y umbrales: `DataAnalyst/etl/data_science.py`, commit `45abdfc`.
- Snapshot de referencia: `data/reference/comparativa.json`.
- Todas las cifras son estimaciones (`is_projection: true`).
- La rama `BranchDaniel_ft_76-77-78` de Data (sin mergear) agrega un ETL de
  egresados por áreas OECD. Si se adopta, **pueden cambiar los valores de
  oferta**; las fórmulas de este contrato no cambian.

## 4.6 Bloque de brechas en el perfil de ocupación (issue #75)

`GET /api/v1/occupations/{occupation_id}` incluye un bloque `brechas` con el
*Talent Gap Score* (TGS) de la ocupación. Reutiliza el mismo `SkillItem` de
`GET /api/v1/skills/{ocupacion_id}`, así que **ambas respuestas son
intercambiables** para el Frontend.

```jsonc
// GET /api/v1/occupations/OCUP_01?pais=ARG
{
  "pais": { "codigo": "ARG", "nombre": "Argentina" },
  "ocupacion": { "id": "OCUP_01", "...": "..." },
  "indicadores": { "icol": 70.67, "...": "..." },
  "brechas": {
    "meta": {
      "fuente": "live",          // live | cache | reference | unavailable
      "actualizado": null,
      "detalle": ""
    },
    "actual": { "pais": "ARG", "score_brecha": 84.5, "...": "..." },
    "por_pais": [
      { "pais": "ARG", "score_brecha": 84.5, "...": "..." },
      { "pais": "CHL", "score_brecha": 79.1, "...": "..." },
      { "pais": "URY", "score_brecha": 87.8, "...": "..." }
    ],
    "brecha_disponible": true
  }
}
```

Reglas del bloque:

| Situación | `meta.fuente` | `brecha_disponible` | `actual` / `por_pais` |
| :--- | :--- | :--- | :--- |
| API de Data disponible | `live` | `true` | filas de la ocupación |
| Data caído, cache vigente | `cache` | `true` | filas de la ocupación |
| Data caído, sin cache | `reference` | `true` | filas del snapshot |
| Data caído, sin cache ni snapshot | `unavailable` | `false` | `null` / `[]` |
| Payload sin esa ocupación | fuente real | `false` | `null` / `[]` |

Notas:

- El endpoint **nunca** responde `503` por brechas: el perfil sigue siendo
  válido y la degradación se informa en el bloque.
- `por_pais` ordena primero el país consultado y luego el orden del catálogo
  (`ARG`, `CHL`, `URY`).
- La consulta se hace en el mismo request; el cliente de Data aplica su cache
  TTL (`DATA_CACHE_TTL`, 300 s por defecto).
- Snapshot de referencia: `data/reference/brechas.json`.
- Ejemplo completo: `docs/mocks/ocupacion_OCUP_01.json`.

## 5. Desviaciones respecto de la definición aprobada

Las desviaciones están acordadas con el equipo de Data y quedan pendientes de
firma en la definición oficial (`DEFINICIONES_CASOS_CARGA_QA.md`):

| # | Desviación | Motivo |
| :--- | :--- | :--- |
| 1 | La clave de deduplicación suma `occupation_id` a los 7 campos canónicos | Sin él, dos ocupaciones del mismo sector con la misma métrica, año y fuente se colapsarían en una sola fila (pérdida de datos real). |
| 2 | El corte por rango no es "valor < 0" genérico | El golden dataset regional incluye variaciones negativas legítimas del PIB. Solo sePonenen en cuarentena los valores negativos de indicadores que no los admiten (desempleo, ocupación, población, etc.). |
| 3 | `unidad_medida` y `periodo` usan etiquetas canónicas propias (`Porcentaje (%)`, `Anual`) | La definición aprobada usa el vocabulario literal (`percentage`, `ANUAL`) y el golden dataset real usa etiquetas en texto (`% del PIB`, `Índice (Base 100)`). El Backend elige un vocabulario canónico y homogéneo, documentado en §4. |
| 4 | `data_type` sigue siendo obligatorio en la carga manual | Coherente con el contrato aprobado de 8 campos; la semántica proyectada viaja en `is_projection`. |

```
