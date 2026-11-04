# Observatorio Predictivo - Backend API

Servicio backend desarrollado en FastAPI para el **Observatorio Predictivo de Ocupaciones y Brechas de Habilidades** en el Cono Sur (Argentina, Uruguay y Chile).

Provee la ingesta y validación de datos (APIs externas y carga manual de archivos planos), cálculo de indicadores y exposición de endpoints REST para la plataforma.

---

## 1. Estado del Proyecto

**Sprint 0 (fundaciones) y Sprint 1 (ingesta y normalización) completados.**

| Área | Estado | Detalle |
| :--- | :--- | :--- |
| Configuración y health | ✅ | Settings desde `.env`, DB async y `/health` con chequeo de conexión |
| Carga manual | ✅ | `POST /datasets/upload` con validación por fila (422), cuarentena con flags y normalización al esquema común de Data |
| Conectores | ✅ | Datos Argentina, Banco Mundial y SIMEL/ENE (SDMX del INE), con tests en vivo |
| Catálogos para el Frontend | ✅ | `GET /countries`, `/sectors` y `/occupations` reemplazan los mocks del repositorio `frontend` |
| Almacenamiento crudo | ✅ | `data/raw/{fuente}/YYYY-MM-DD.jsonl` (esquema `raw_data_logs`) + flujo de ingesta |
| Índice de empleabilidad | ✅ | `GET /employability` con IDELR + ICOL reimplementados y test de paridad contra la API de Data |
| Matriz de casos QA | ✅ **28/28** | API-001..016 (contra la API de Data) + LOAD-001..012 (contra este backend) |
| Base de datos | ✅ | Conexión a **Supabase** (pooler session, `?ssl=require`) + modelos ORM y **Alembic** async: primera tabla `raw_data_logs` |
| Endpoint de indicadores | ⏸ | `GET /indicators` con filtros por país, sector y período |
| Perfil de ocupación | ✅ | `/occupations/{id}` devuelve el perfil de las 20 ocupaciones: ficha del catálogo + ICOL, rankings y comparación entre países |
| Despliegue | ⏸ | Railway/Render diferido (pasos en §10) |

**Pendientes de coordinación con el equipo de Data:**
* Firmar las 4 desviaciones del ETL ([`docs/Data_Contracts.md` §5](docs/Data_Contracts.md)).
* Reflejar en la planilla de QA los cambios de contrato: `400 → 422` en el rechazo por fila y `occupation_id` fuera de catálogo → cuarentena.
* Para el Frontend: los catálogos ya se sirven en `/api/v1/countries`, `/sectors` y `/occupations` (contrato, mapeo de campos y snippet de integración en §4). También quedan disponibles las unidades canónicas y el campo `is_projection`.

### Datos de referencia

El golden dataset regional del equipo de Data (`DataAnalyst`, 135 registros) se reingiere por el mismo endpoint de carga: el Backend detecta que el archivo ya viene en el esquema común y lo procesa sin transformaciones.

```bash
git clone https://github.com/InnovaLab-2C-2026-Equipo-6/DataAnalyst.git /tmp/opencode/DataAnalyst

# Cargar el dataset regional (135 registros, 45 por país)
curl -X POST -F "file=@/tmp/opencode/DataAnalyst/data/processed/dataset_consolidado_regional.csv" \
  http://127.0.0.1:8000/api/v1/datasets/upload

# Índice de empleabilidad con esos datos (serie macro + ranking de 60 ocupaciones)
curl "http://127.0.0.1:8000/api/v1/employability"
```

---

## 2. Stack Tecnológico

* **Framework:** FastAPI
* **Servidor ASGI:** Uvicorn
* **Modelado y Validación:** Pydantic v2
* **Procesamiento de Datos:** Pandas + OpenPyXL
* **Base de Datos / ORM:** PostgreSQL / SQLAlchemy 2.0 (async)
* **Cliente HTTP:** HTTPX

---

## 3. Instalación y Ejecución Local

### Prerrequisitos
* Python 3.11+
* Git

### Pasos

1. Clonar el repositorio y acceder a la carpeta:
```bash
git clone [https://github.com/InnovaLab-2C-2026-Equipo-6/app-backend.git](https://github.com/InnovaLab-2C-2026-Equipo-6/app-backend.git)
cd app-backend
```

2. Crear y activar el entorno virtual:
```bash
# En Linux / macOS
python3 -m venv venv
source venv/bin/activate

# En Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1
```

3. Instalar dependencias:
```bash
pip install -r requirements.txt
```

> **Nota sobre `sqlalchemy[asyncio]`**: el extra es obligatorio, no cosmético.
> El backend trabaja con `sqlalchemy.ext.asyncio` (`create_async_engine`,
> `async_sessionmaker`) y ese extra es el que instala **`greenlet`**, el puente
> sync/async de SQLAlchemy. Sin él, una instalación limpia falla al importar el
> módulo asíncrono. Si ya tenés el entorno armado y te falta:
> ```bash
> python -m pip install "sqlalchemy[asyncio]"
> ```

> **Windows 11 + Smart App Control (SAC):** si al importar `pandas` aparece
> `ImportError: DLL load failed ... Una directiva de Control de aplicaciones
> bloqueó este archivo` (o el toast *"Parte de esta aplicación se ha bloqueado"*
> con error `0x11C7`), no es un problema del repo: SAC está bloqueando `.pyd`
> sin firma y sin reputación en la nube (en pandas 3.1.0 afecta a 8 de 45
> binarios: `groupby`, `join`, `properties`, `nattype`, `offsets`, `strptime`,
> `tzconversion`, `aggregations`). Workaround temporal mientras Microsoft les
> da reputación: `pip install "pandas==2.2.3"` (satisface `pandas>=2.2.0`).
> Verificación rápida de qué binarios están bloqueados: mirar los eventos
> `3033`/`3077` del log *Microsoft-Windows-CodeIntegrity/Operational*.

4. Configurar variables de entorno:
```bash
cp .env.example .env
```

### Base de datos (Supabase)

Completar `DATABASE_URL` en `.env` (el archivo está en `.gitignore`: **nunca** se commitea):

```dotenv
DATABASE_URL=postgresql+asyncpg://postgres.[PROJECT-REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:5432/postgres?ssl=require
```

* **Pooler en modo Session** (puerto `5432`). El modo Transaction (`6543`) no sirve con
  `asyncpg` ni con Alembic: rompe los *prepared statements* y las transacciones de sesión.
  Se cambia en Supabase → *Settings → Database → Connection pooling*.
* El host directo `db.<project-ref>.supabase.co` es **IPv6-only**: desde redes sin IPv6 no
  conecta. Usar siempre el **pooler**.
* `?ssl=require` cifra la conexión sin validar el certificado: Supabase emite los certs del
  pooler con una **CA propia** (`Supabase Intermediate 2021 CA`) que no está en los trust
  stores públicos, por lo que `verify-full` falla.
* **Redes institucionales/campus**: suelen tener bloqueado el puerto de salida `5432`.
  Si el healthcheck devuelve `"db": "error"` (no `"not_configured"`), verificar desde otra
  red (p. ej. hotspot móvil) antes de investigar la app.

Verificación:

```bash
curl http://127.0.0.1:8000/api/v1/health   # → {"status":"ok","db":"ok"}
```

#### Migraciones (Alembic)

Las migraciones viven en `migrations/` y leen `DATABASE_URL` desde las settings del backend
(mismo `.env` que la app, template async):

```bash
python -m alembic revision --autogenerate -m "descripcion del cambio"
python -m alembic upgrade head          # aplica pendientes
python -m alembic current               # versión aplicada
python -m alembic history               # historial
```

Modelos ORM en `app/models/` (`Base` + `RawDataLog`, esquema `raw_data_logs` de SPEC §6).

5. Iniciar el servidor en modo desarrollo:
```bash
python3 -m uvicorn app.main:app --reload
```

* **API Base:** `http://127.0.0.1:8000`
* **Swagger UI (Documentación interactiva):** `http://127.0.0.1:8000/docs`
* **ReDoc:** `http://127.0.0.1:8000/redoc`

---

## 4. Endpoints Disponibles

| Método | Ruta | Tag | Descripción |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/health` | `Health` | Estado del servicio y chequeo de DB (`200 OK`; `503` si la DB está caída) |
| `GET` | `/api/v1/countries` | `Catalogs` | Países del alcance regional (`id` ISO-3, `nombre`, `iso2`, `iso3`) |
| `GET` | `/api/v1/sectors` | `Catalogs` | Sectores productivos (`id` canónico, `slug` para el frontend, `nombre`) |
| `GET` | `/api/v1/occupations` | `Catalogs` | Catálogo de ocupaciones (CIUO-08, demanda, crecimiento y habilidades). Filtro `?sector=TEC` o `?sector=economia-conocimiento` |
| `GET` | `/api/v1/occupations/{id}` | `Occupations` | Perfil de la ocupación: ficha del catálogo + ICOL con rankings y comparación entre países. `?pais=ARG` (default) |
| `POST` | `/api/v1/datasets/upload` | `Datasets` | Carga, validación y normalización de archivos CSV o Excel |
| `GET` | `/api/v1/employability` | `Employability` | Índice de empleabilidad: serie macro (IDELR) y ranking por ocupación (ICOL) |
| `POST` | `/api/v1/employability/snapshot` | `Snapshots` | Calcula los índices y **guarda** el resultado en la base para poder mirar el pasado (idempotente) |
| `GET` | `/api/v1/employability/history` | `Snapshots` | Histórico de resultados guardados. Filtros: `tipo`, `pais`, `ocupacion`, `anio_desde`, `anio_hasta`, `limite` |
| `GET` | `/api/v1/skills` | `Data Science` | Brechas de talento con habilidades emergentes. Filtros: `pais`, `sector` |
| `GET` | `/api/v1/skills/{ocupacion_id}` | `Data Science` | Brecha de una ocupación en los 3 países. `?pais=ARG` |
| `GET` | `/api/v1/gaps` | `Data Science` | Oferta formativa: demanda laboral vs. egresados por sector. Filtro: `pais` |

### Catálogos para el Frontend

Los tres endpoints de `Catalogs` existen para reemplazar los mocks del repositorio `frontend`
(`src/mocks/paises.json`, `sectores.json`, `ocupaciones.json`).

* `countries` y `sectors` devuelven **exactamente** la misma forma que los mocks: el swap es directo.
* `occupations` usa los nombres propios del Backend. El mapeo contra el mock actual es de tres
  campos (`ocupacion` → `nombre`, `nivelDemanda` → `demanda`,
  `crecimientoAnualEstPct` → `crecimiento_anual_pct`) y el `sector` pasa a ser objeto
  `{id, slug, nombre}` en lugar del nombre suelto.

```jsonc
// GET /api/v1/countries  →  [{ "id": "ARG", "nombre": "Argentina", "iso2": "AR", "iso3": "ARG" }]
// GET /api/v1/sectors    →  [{ "id": "ECO", "slug": "economia-conocimiento", "nombre": "Economía del Conocimiento" }]
// GET /api/v1/occupations?sector=TEC
[
  {
    "id": "OCUP_01",
    "nombre": "Desarrollador de Software y Aplicaciones",
    "sector": { "id": "TEC", "slug": "tecnologia", "nombre": "Tecnología" },
    "ciuo08": "2512",
    "demanda": "Muy Alta",
    "crecimiento_anual_pct": 18.5,
    "habilidades": ["Python", "JavaScript", "FastAPI", "React", "SQL", "Git"]
  }
]
```

El parámetro `sector` acepta el código (`TEC`), el slug (`economia-conocimiento`) o el nombre
completo (`Economía del Conocimiento`); si no existe devuelve `422`.

Cambio mínimo en el frontend (`src/services/AppServices.js`), sin librerías nuevas:

```js
const API_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

const getJson = async (path) => {
  const respuesta = await fetch(`${API_URL}${path}`);
  if (!respuesta.ok) throw new Error(`GET ${path} → ${respuesta.status}`);
  return respuesta.json();
};

export const observatorioService = {
  getCountries: () => getJson("/api/v1/countries"),
  getSectors: () => getJson("/api/v1/sectors"),
  getOccupations: async () => {
    const filas = await getJson("/api/v1/occupations");
    return filas.map((f) => ({
      id: f.id,
      sector: f.sector.nombre,
      ocupacion: f.nombre,
      ciuo08: f.ciuo08,
      nivelDemanda: f.demanda,
      crecimientoAnualEstPct: f.crecimiento_anual_pct,
      habilidades: f.habilidades,
    }));
  },
  // Sin datos todavía: ningún repo del equipo tiene catálogo geográfico.
  getGeographicAreas: async () => [],
};
```

Ninguno de estos endpoints requiere base de datos: los catálogos viven en
`app/core/catalogs.py` y se sirven desde memoria.

### Ficha de ocupación

`GET /api/v1/occupations/{id}` combina la ficha técnica del catálogo con el índice de
oportunidad (ICOL). Es el mismo cálculo que devuelve `/employability`, así que los valores
coinciden exactamente.

```jsonc
// GET /api/v1/occupations/OCUP_01?pais=ARG   (también CHL y URY)
{
  "pais":      { "codigo": "ARG", "nombre": "Argentina" },
  "sector":    { "id": "TEC", "slug": "tecnologia", "nombre": "Tecnología" },
  "ocupacion": { "id": "OCUP_01", "nombre": "Desarrollador de Software y Aplicaciones", "ciuo08": "2512" },
  "indicadores": {
    "nivel_demanda": "Muy Alta",
    "crecimiento_anual_pct": 18.5,
    "icol": 70.67,
    "categoria_oportunidad": "Alta Oportunidad",
    "icono": "🟢",
    "prioridad_formacion": "Alta Demanda",
    "scores":  { "demanda": 100.0, "crecimiento": 61.67, "entorno_macro": 54.2 },
    "rankings": { "regional": 24, "pais": 4, "sector": 10 }
  },
  "habilidades": ["Python", "JavaScript", "FastAPI", "React", "SQL", "Git"],
  "comparacion_paises": [
    { "codigo": "ARG", "nombre": "Argentina", "icol": 70.67, "ranking_pais": 4, "categoria_oportunidad": "Alta Oportunidad" },
    { "codigo": "CHL", "nombre": "Chile",     "icol": 79.36, "ranking_pais": 4, "categoria_oportunidad": "Alta Oportunidad" },
    { "codigo": "URY", "nombre": "Uruguay",   "icol": 84.83, "ranking_pais": 4, "categoria_oportunidad": "Alta Oportunidad" }
  ],
  "trazabilidad": {
    "fuente": "Catálogo regional de ocupaciones (DataAnalyst)",
    "fuente_url": "https://github.com/InnovaLab-2C-2026-Equipo-6/DataAnalyst",
    "actualizado": "2026-10-15",
    "is_projection": true,
    "origen_indice": "fallback",
    "datasets": []
  }
}
```

* `trazabilidad.origen_indice` avisa si el índice salió de datasets cargados (`processed`)
  o de los valores de referencia del entorno macro (`fallback`).
* `trazabilidad.is_projection` es `true` porque la demanda y el crecimiento del catálogo
  son estimaciones, no mediciones. En este bloque ya no existe `data_type` (contrato v2).
* Validación: `OCC-1` → `422` (formato), `OCUP_99` → `404` (fuera de catálogo),
  `?pais=XXX` → `400` (alcance regional).

---

## 5. Estructura del Proyecto

```text
app-backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   ├── catalog.py        # Catálogos para Frontend (países, sectores, ocupaciones)
│   │       │   ├── datasets.py       # Endpoint POST /upload con validación y normalización
│   │       │   ├── employability.py  # Índice de empleabilidad (IDELR + ICOL)
│   │       │   ├── health.py         # Estado del servicio + chequeo de DB
│   │       │   └── occupations.py    # Fichas técnicas de ocupaciones
│   │       └── router.py             # Enrutador central v1
│   ├── core/
│   │   ├── config.py                 # Settings (pydantic-settings) desde .env
│   │   ├── catalogs.py               # Catálogos canónicos (países, sectores, ocupaciones, unidades)
│   │   └── database.py               # Engine async + get_db + healthcheck DB
│   ├── models/                       # Modelos ORM SQLAlchemy (Base + raw_data_logs)
│   ├── schemas/                      # Schemas de validación Pydantic
│   │   ├── catalog.py
│   │   ├── dataset.py
│   │   ├── employability.py
│   │   └── occupation.py
│   ├── services/                     # Lógica de negocio y procesamiento
│   │   ├── calculators/              # IDELR / ICOL (Índice de Empleabilidad)
│   │   │   ├── employability.py       # Fórmula publicada por el equipo de Data
│   │   │   └── datasets.py           # Lectura de los datasets normalizados
│   │   ├── connectors/               # Clientes HTTPX de fuentes oficiales
│   │   │   ├── base.py               # BaseConnector + ConnectorResponse
│   │   │   ├── banco_mundial.py      # Banco Mundial API v2
│   │   │   ├── datos_argentina.py    # Series de Tiempo datos.gob.ar
│   │   │   └── simel_chile.py        # SIMEL/ENE vía SDMX del INE
│   │   ├── normalization/             # ETL: mapeo al esquema común, cuarentena y deduplicación
│   │   │   ├── mapper.py             # 8 columnas de entrada → ESQUEMA_COLUMNAS de Data
│   │   │   ├── pipeline.py           # 3 niveles: rechazo 422 / cuarentena / dedupe
│   │   │   ├── store.py              # Dataset normalizado (CSV) y cuarentena (JSONL)
│   │   │   └── errors.py             # Errores de ingesta con detalle por fila
│   │   ├── storage/
│   │   │   └── raw_store.py          # Crudos en data/raw/{fuente}/YYYY-MM-DD.jsonl
│   │   ├── ingestor.py               # Flujo: recepción → almacenamiento crudo
│   │   ├── occupation_profile.py   # Perfil de ocupación: catálogo + ICOL
│   │   └── parsers/
│   │       └── dataset_parser.py     # Parser Pandas para CSV / Excel
│   └── main.py                       # Instancia FastAPI y middleware CORS
├── tests/                            # Suite Pytest (integración API + conectores + ETL)
├── migrations/                       # Migraciones Alembic (template async)
├── alembic.ini                       # Configuración de Alembic
├── pytest.ini                        # Configuración de Pytest
├── docs/
│   ├── mocks/                        # Contratos JSON de ejemplo para Frontend
│   ├── Casos_Apis_CargaDatos*.csv    # Matriz de casos QA
│   ├── DATA_CONTRACTS.md
│   ├── ROADMAP_BACKEND.md
│   ├── SPEC.md
│   └── STRUCTURE.md
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## 6. Formato para Carga Manual de Datasets

El endpoint `POST /api/v1/datasets/upload` valida que los archivos `.csv` o `.xlsx` contengan estrictamente las siguientes columnas:

```text
country_code,sector_id,occupation_id,metric_name,metric_value,period,source_name,data_type
```

Si alguna de estas columnas falta, el endpoint responde con código `400 Bad Request` indicando la lista de campos faltantes.

Además de las columnas, se validan los valores de cada fila:

* `country_code` ∈ `ARG`, `CHL`, `URY`
* `occupation_id` ∈ catálogo `OCUP_01` … `OCUP_20` (formato `OCUP_XX`)
* `data_type` ∈ `percentage`, `currency`, `count` (unidad de la métrica)
* `metric_value` numérico
* `period` ∈ `2025`, `2025-Q3`, `2025-06`

Una fila inválida produce **`422 Unprocessable Entity`** con el detalle de cada problema (`row`, `field`, `value`, `cause`) y el archivo completo se rechaza sin entrar al pipeline.

### 5.1 Normalización al esquema común

Las filas válidas se transforman al **esquema común aprobado por el equipo de Data** (`ESQUEMA_COLUMNAS` de `etl/cleaner.py`) más dos columnas propias (`occupation_id`, `is_projection`):

```text
pais_codigo_iso3,pais_nombre,dimension,indicador_nombre,anio,periodo,valor,unidad_medida,fuente_oficial,fecha_extraccion,occupation_id,is_projection
```

La clasificación de filas sigue los tres niveles de la definición aprobada (`DataAnalyst/DEFINICIONES_CASOS_CARGA_QA.md`):

| Nivel | Situación | Resultado |
| :--- | :--- | :--- |
| 1 | Campo obligatorio vacío, valor no numérico, país/unidad/período/ocupación con formato inválido | **HTTP 422** (rechazo atómico, con detalle por fila) |
| 2 | Sector u ocupación fuera del catálogo (`UNMAPPED_CATALOG`), valor fuera de rango lógico (`OUTLIER_RANGE`) | **Cuarentena**: la fila se aísla con su flag y el resto se procesa |
| 3 | Misma clave natural dentro del lote | **Deduplicación**: gana el último registro (con warning si el valor difiere) |

* Clave natural: `pais_codigo_iso3`, `dimension`, `indicador_nombre`, `anio`, `periodo`, `unidad_medida`, `fuente_oficial` **+ `occupation_id`**.
* Salidas: dataset normalizado en `data/processed/{fecha}/` (CSV `utf-8-sig`) y cuarentena en `data/quarantine/{fecha}/` (JSONL). `?persist=false` devuelve el reporte sin escribir.
* Si el archivo ya viene en el esquema común de Data, el endpoint lo reconoce (`input_schema: "common"`) y lo procesa sin transformaciones (útil para reingerir el golden dataset regional de 135 registros).

El detalle completo del contrato, el mapeo campo a campo y las desviaciones acordadas con el equipo de Data están en [`docs/Data_Contracts.md`](docs/Data_Contracts.md).

---

## 7. Índice de Empleabilidad (IDELR + ICOL)

`GET /api/v1/employability` expone el índice de empleabilidad reimplementado **localmente** a partir de la metodología publicada por el equipo de Data (`DataAnalyst/INFORME_METODOLOGICO_INDICES.md`), de modo que el Backend no dependa de la disponibilidad de su API:

* **IDELR** (Índice de Desarrollo Económico-Laboral Regional): normalización Min-Max acotada `[0, 100]` y agregación lineal ponderada sobre 5 indicadores (PIB 25 %, salario real 25 %, ocupación 20 %, finalización secundaria 15 %, desempleo 15 %), con tendencia por banda muerta (ε = 1 %).
* **ICOL** (Índice Compuesto de Oportunidad Laboral): `0.35 · IDELR + 0.40 · demanda + 0.25 · crecimiento`, ajustado por el factor de madurez del país (URY 1.05 / CHL 1.00 / ARG 0.95) y acotado a `[0, 100]`.

Filtros: `pais` (ARG/CHL/URY), `sector`, `ocupacion` (OCUP_01..OCUP_20), `anio_inicio`, `anio_fin`.

* Los datos macro salen de los datasets normalizados en `data/processed/`; si todavía no hay ninguno, el ICOL usa los valores de referencia y la respuesta lo explicita en `fuente_datos.tipo = "fallback"`.
* La respuesta incluye el **desglose de dimensiones evaluadas** (`desglose_variables` con valor original, valor normalizado, peso asignado y contribución al índice) y la trazabilidad completa (fuente, fecha y metodología aplicada).
* `tests/test_employability.py` incluye un **test de paridad**: nuestros valores coinciden exactamente con `/api/v1/analytics/indice-sintetico` y `/api/v1/analytics/ocupaciones/ranking` del repo `DataAnalyst`.

## 7.b Persistencia histórica de resultados (Issue #54)

El índice se recalcula en cada consulta, pero **el resultado no se guardaba**: solo existían los datos crudos (`raw_data_logs`). Con `POST /api/v1/employability/snapshot` el Backend calcula los índices y **persiste el resultado**, para poder mirar el pasado, comparar días y reproducir un cálculo.

### Cómo funciona

| Concepto | Detalle |
| :--- | :--- |
| Tabla | `indicator_results` (migración `4565d593028e`) |
| Qué guarda | Un snapshot por combinación: tipo (`IDELR`/`ICOL`), país, año, ocupación, valor, categoría, cobertura, versión de metodología, payload completo y fecha del cálculo |
| Idempotencia | `dedupe_key = tipo\|país\|año\|ocupación\|fecha`: guardar dos veces el **mismo día** actualiza la fila en lugar de duplicarla; otro día crea un snapshot nuevo y conserva el histórico |
| Guardado | **Explícito por POST**: `GET /employability` sigue siendo de solo lectura y no escribe nada |
| Sin base de datos | `503` con un mensaje claro (`DATABASE_URL` no configurada) |

```bash
# Guardar el snapshot de hoy
curl -X POST http://localhost:8000/api/v1/employability/snapshot

# Consultar el histórico
curl "http://localhost:8000/api/v1/employability/history?tipo=ICOL&pais=URY"
curl "http://localhost:8000/api/v1/employability/history?tipo=IDELR&anio_desde=2020"
```

```jsonc
// POST /api/v1/employability/snapshot  →  200 OK
{
  "generated_at": "2026-11-04T12:13:51+00:00",
  "fecha_snapshot": "2026-11-04",
  "metodologia_version": "idelr-icol-2026-11",
  "fuente_datos": "processed",          // "fallback" si no hay datasets cargados
  "anio_referencia": 2024,
  "guardado": { "idelr": 30, "icol": 60, "insertados": 90, "actualizados": 0 }
}
```

> `metodologia_version` permite distinguir snapshots comparables: si cambia la fórmula o los
> pesos, se incrementa la versión y los históricos de cada versión siguen siendo distinguibles.

## 7.c Brechas de talento y oferta formativa (Issue #74)

Consume el **módulo de Data Science** del equipo de Data (`DataAnalyst/etl/data_science.py`),
publicado el 02/11, a través de un cliente con cache y fallback.

| Endpoint | Qué responde |
| :--- | :--- |
| `GET /api/v1/skills?pais=&sector=` | Ranking de brechas de talento: *Talent Gap Score* (0-100), diagnóstico, habilidades tradicionales y emergentes 2026+ |
| `GET /api/v1/skills/{ocupacion_id}?pais=` | Brecha de una ocupación en los 3 países (o en el pedido) |
| `GET /api/v1/gaps?pais=` | **Oferta formativa**: egresados vs. demanda de nuevos puestos por sector, déficit anual, CCE y semáforo |

### Degradación en tres niveles

El frontend nunca se queda sin datos:

| Nivel | Cuándo | `meta.fuente` |
| :--- | :--- | :--- |
| **live** | La API de Data responde | `live` |
| **cache** | Data falló, pero hay una respuesta reciente en memoria (TTL 300 s) | `cache` |
| **reference** | Data falló y no hay cache → snapshot commiteado en `data/reference/` | `reference` |
| — | Ninguna fuente disponible | **503** con mensaje claro |

### Configuración

| Variable | Default | Para qué |
| :--- | :--- | :--- |
| `DATA_API_URL` | `http://127.0.0.1:8001` | Base de la API de Data |
| `DATA_API_TIMEOUT` | `5.0` | Timeout de la llamada (segundos) |
| `DATA_CACHE_TTL` | `300` | TTL de la caché en memoria (segundos) |

### Regenerar los snapshots de referencia

```bash
# Con la API de Data levantada en :8001
python scripts/generar_referencia.py
```

```jsonc
// GET /api/v1/skills?pais=URY  →  200 OK
{
  "meta": { "fuente": "live", "actualizado": null, "detalle": "" },
  "filtros": { "pais": "URY", "sector": null },
  "total": 20,
  "items": [
    {
      "pais": "URY",
      "ocupacion_id": "OCUP_02",
      "ocupacion_nombre": "Ingeniero de Datos y Machine Learning",
      "icol": 88.19,
      "score_brecha": 87.76,
      "cce": 0.571,
      "diagnostico": "Déficit Crítico de Talento",
      "icono": "🔴",
      "habilidades_emergentes": ["Arquitecturas RAG", "Edge AI", "LLMOps & Model Governance"],
      "is_projection": true
    }
  ]
}
```

> Las cifras educativas y de demanda son **estimaciones** (`is_projection: true`): por eso cada
> ítem incluye el semáforo y las fuentes oficiales que reporta Data.

## 8. Tests

La suite está construida con **Pytest** + `TestClient` de FastAPI (sin necesidad de servidor corriendo):

```bash
python -m pytest -v
```

* Cobertura actual (**183 tests**, 0 omitidos con el repo de Data disponible): `POST /datasets/upload` (casos **LOAD-001..LOAD-012** de la matriz QA: validación de columnas, de país, de unidad, de período, de `metric_value`, catálogo de ocupaciones `OCUP_01..20`, duplicados, cobertura 45/135, transformación al esquema común y cuarentena), `GET /countries` / `sectors` / `occupations` (conteos, slugs, filtro por sector y `422` ante sector desconocido), `GET /health` (3 estados del chequeo de DB), `GET /occupations/{id}` (perfil de las 20 ocupaciones, validaciones `404`/`422`/`400`, comparación de países, origen `processed` vs `fallback` y coherencia del ICOL con `/employability`), `GET /employability` (filtros, invariantes del índice y **paridad exacta con la API de Data**), `POST /employability/snapshot` + `GET /employability/history` (persistencia histórica) y `GET /skills` / `skills/{id}` / `gaps` (brechas y oferta formativa).
* `tests/test_datascience.py` cubre el módulo de brechas **sin usar la red** (`httpx.MockTransport`): normalización del payload de Data, filtros de país y sector, validaciones, y toda la cadena de degradación (`live` → `cache` → `reference` → `503`).
* `tests/test_employability_metodologia.py` verifica la **metodología visible**: los pesos del IDELR y del ICOL suman `1.0`, el endpoint expone las 5 dimensiones y es espejo exacto de `VARIABLES_IDELR` / `DEFAULT_ICOL_WEIGHTS`, y los umbrales de categoría se comprueban en su borde exacto (85 / 70 / 55).
* Los tests escriben siempre en `tmp_path`: el fixture `output_dirs` es `autouse`, así que la suite no ensucia `data/processed/` ni `data/quarantine/`.
* Los casos **API-001..API-016** de la matriz QA se ejecutan contra la API del equipo Data (repo `DataAnalyst`): el fixture la levanta con uvicorn desde `DATA_API_PATH` (por defecto `/tmp/opencode/DataAnalyst`) o usa una instancia corriendo en `DATA_API_URL` (default `http://127.0.0.1:8001`). Si no hay repo ni instancia, esos tests se omiten (skip).
* `tests/test_normalization.py` cubre el ETL de forma unitaria y verifica que el golden dataset regional de Data entra por el esquema común sin perder registros (135 filas, 45 por país).
* La matriz de casos QA (`docs/Casos_Apis_CargaDatos - 22092026.csv`) mantiene el estado de cada caso: **28/28 automatizados**.
* `tests/test_connectors.py`, `tests/test_raw_store.py` y `tests/test_ingestor.py` cubren los conectores (unit + en vivo), el almacenamiento crudo y el flujo de ingesta.

> **Para correr la matriz API completa** hay que clonar el repo del equipo Data:
> ```bash
> git clone https://github.com/InnovaLab-2C-2026-Equipo-6/DataAnalyst.git /tmp/opencode/DataAnalyst
> cd /tmp/opencode/DataAnalyst && git checkout 45abdfc   # versión auditada del 02/11
> ```
> Sin el clon, la suite da **128 passed, 19 skipped**; con el clon, **147 passed, 0 skipped**.

---

## 9. Conectores y Datos Crudos

### Conectores HTTP (Issue #18)

Clientes HTTPX asíncronos en `app/services/connectors/`:

| `source_id` | Fuente | Endpoint | Serie por defecto |
|---|---|---|---|
| `datos_argentina` | Datos Argentina (Series de Tiempo) | `apis.datos.gob.ar/series/api/series/` | IPC nacional (`DATOS_AR_SERIES_IDS`, configurable) |
| `banco_mundial` | Banco Mundial API v2 | `api.worldbank.org/v2/...` | `SL.UEM.TOTL.ZS` (desempleo) para ARG/CHL/URY |
| `simel_chile` | SIMEL/ENE vía SDMX del INE | `sdmx.ine.gob.cl/rest/data/...` | `CL01,DF_DES_SEXO` (desocupación por sexo, fuente ENE) |

* `www.simel.gob.cl` responde `418` a clientes automatizados; las series ENE se consumen por el SDMX oficial del INE (misma fuente).
* Cada conector expone `await fetch(...) -> ConnectorResponse(source_id, ok, fetched_at, payload, points, error)`: `payload` conserva la respuesta cruda y `points` trae `(periodo, valor)`.
* Registry: `CONNECTORS` en `app/services/connectors/__init__.py`.

### Almacenamiento crudo (Issue #19)

`app/services/storage/raw_store.py` appenda registros con el esquema `raw_data_logs` (SPEC §6):

```json
{"source_id": "datos_argentina", "raw_payload": {"...": "..."}, "status": "ok", "error": null, "created_at": "2026-10-07T00:00:00+00:00"}
```

* Archivos: `data/raw/{source_id}/YYYY-MM-DD.jsonl` (un registro por línea; directorio configurable con `RAW_DIR`).
* Flujo de recepción: `await ingest(conector, **params)` (`app/services/ingestor.py`) hace fetch y guarda el registro (ok o error) → `IngestReport`.
* `read_raw(source_id, limit)` devuelve los últimos registros para el consumo posterior (normalización pendiente de coordinar con Data).

### Prueba de conexión

`tests/test_connectors.py` incluye tests **en vivo** (una llamada real por fuente): sin salida a internet se omiten con *skip*; los tests unitarios cubren parseo y errores sin red.

---

## 10. Despliegue (pendiente)

El despliegue del esqueleto en **Railway / Render** está diferido (Sprint 0 → Sprint 1). Pasos previstos:

1. Linkear este repositorio en Railway (`railway link` o dashboard).
2. Variables de entorno: `DATABASE_URL` (Supabase/PostgreSQL), `CORS_ORIGINS`.
3. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.

Mientras `DATABASE_URL` no esté configurada, `GET /api/v1/health` responde `200 {"status": "ok", "db": "not_configured"}`.

---

## 11. Documentación Adicional

Para más detalles sobre la arquitectura y contratos:
* [Especificación Técnica (`docs/SPEC.md`)](docs/SPEC.md)
* [Contratos de Datos (`docs/DATA_CONTRACTS.md`)](docs/DATA_CONTRACTS.md)
* [Runbook de conexión a Supabase (`docs/CONEXION_SUPABASE.md`)](docs/CONEXION_SUPABASE.md)
* [Roadmap y Sprints Kanban (`docs/ROADMAP_BACKEND.md`)](docs/ROADMAP_BACKEND.md)
* [Mocks JSON para Frontend (`docs/mocks/`)](docs/mocks/)