# Observatorio Predictivo - Backend API

Servicio backend desarrollado en FastAPI para el **Observatorio Predictivo de Ocupaciones y Brechas de Habilidades** en el Cono Sur (Argentina, Uruguay y Chile).

Provee la ingesta y validación de datos (APIs externas y carga manual de archivos planos), cálculo de indicadores y exposición de endpoints REST para la plataforma.

---

## 1. Stack Tecnológico

* **Framework:** FastAPI
* **Servidor ASGI:** Uvicorn
* **Modelado y Validación:** Pydantic v2
* **Procesamiento de Datos:** Pandas + OpenPyXL
* **Base de Datos / ORM:** PostgreSQL / SQLAlchemy 2.0 (async)
* **Cliente HTTP:** HTTPX

---

## 2. Instalación y Ejecución Local

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

4. Configurar variables de entorno:
```bash
cp .env.example .env
```

5. Iniciar el servidor en modo desarrollo:
```bash
python3 -m uvicorn app.main:app --reload
```

* **API Base:** `http://127.0.0.1:8000`
* **Swagger UI (Documentación interactiva):** `http://127.0.0.1:8000/docs`
* **ReDoc:** `http://127.0.0.1:8000/redoc`

---

## 3. Endpoints Disponibles

| Método | Ruta | Tag | Descripción |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/health` | `Health` | Estado del servicio y chequeo de DB (`200 OK`; `503` si la DB está caída) |
| `GET` | `/api/v1/occupations/{id}` | `Occupations` | Ficha técnica de ocupación según contrato regional |
| `POST` | `/api/v1/datasets/upload` | `Datasets` | Carga y validación estructural de archivos CSV o Excel |

---

## 4. Estructura del Proyecto

```text
app-backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   ├── datasets.py       # Endpoint POST /upload con validación
│   │       │   ├── health.py         # Estado del servicio + chequeo de DB
│   │       │   └── occupations.py    # Fichas técnicas de ocupaciones
│   │       └── router.py             # Enrutador central v1
│   ├── core/
│   │   ├── config.py                 # Settings (pydantic-settings) desde .env
│   │   └── database.py               # Engine async + get_db + healthcheck DB
│   ├── models/                       # Modelos ORM SQLAlchemy
│   ├── schemas/                      # Schemas de validación Pydantic
│   │   ├── dataset.py
│   │   └── occupation.py
│   ├── services/                     # Lógica de negocio y procesamiento
│   │   ├── connectors/               # Clientes HTTPX de fuentes oficiales
│   │   │   ├── base.py               # BaseConnector + ConnectorResponse
│   │   │   ├── banco_mundial.py      # Banco Mundial API v2
│   │   │   ├── datos_argentina.py    # Series de Tiempo datos.gob.ar
│   │   │   └── simel_chile.py        # SIMEL/ENE vía SDMX del INE
│   │   ├── storage/
│   │   │   └── raw_store.py          # Crudos en data/raw/{fuente}/YYYY-MM-DD.jsonl
│   │   ├── ingestor.py               # Flujo: recepción → almacenamiento crudo
│   │   └── parsers/
│   │       └── dataset_parser.py     # Parser Pandas para CSV / Excel
│   └── main.py                       # Instancia FastAPI y middleware CORS
├── tests/                            # Suite Pytest (integración API + conectores)
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

## 5. Formato para Carga Manual de Datasets

El endpoint `POST /api/v1/datasets/upload` valida que los archivos `.csv` o `.xlsx` contengan estrictamente las siguientes columnas:

```text
country_code,sector_id,occupation_id,metric_name,metric_value,period,source_name,data_type
```

Si alguna de estas columnas falta, el endpoint responde con código `400 Bad Request` indicando la lista de campos faltantes.

Además de las columnas, se validan los valores de cada fila (rechazo `400` en cualquier fila inválida):

* `country_code` ∈ `ARG`, `CHL`, `URY`
* `occupation_id` ∈ catálogo `OCUP_01` … `OCUP_20`
* `data_type` ∈ `observed`, `projected`
* `metric_value` numérico

---

## 6. Tests

La suite está construida con **Pytest** + `TestClient` de FastAPI (sin necesidad de servidor corriendo):

```bash
python -m pytest -v
```

* Cobertura actual: `POST /datasets/upload` (casos LOAD-001..008 de la matriz QA, incluyendo validación de país, `data_type`, `metric_value` numérico y catálogo de ocupaciones `OCUP_01..OCUP_20`), `GET /health` (3 estados del chequeo de DB) y `GET /occupations/{id}` (200/404 + trazabilidad).
* Los casos **API-001..API-014** de la matriz QA se ejecutan contra la API del equipo Data (repo `DataAnalyst`): el fixture la levanta con uvicorn desde `DATA_API_PATH` (por defecto `/tmp/opencode/DataAnalyst`) o usa una instancia corriendo en `DATA_API_URL` (default `http://127.0.0.1:8001`). Si no hay repo ni instancia, esos tests se omiten (skip).
* La matriz de casos QA (`docs/Casos_Apis_CargaDatos - 22092026.csv`) mantiene el estado de cada caso.
* `tests/test_connectors.py`, `tests/test_raw_store.py` y `tests/test_ingestor.py` cubren los conectores (unit + en vivo), el almacenamiento crudo y el flujo de ingesta.

---

## 7. Conectores y Datos Crudos

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

## 8. Despliegue (pendiente)

El despliegue del esqueleto en **Railway / Render** está diferido (Sprint 0 → Sprint 1). Pasos previstos:

1. Linkear este repositorio en Railway (`railway link` o dashboard).
2. Variables de entorno: `DATABASE_URL` (Supabase/PostgreSQL), `CORS_ORIGINS`.
3. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.

Mientras `DATABASE_URL` no esté configurada, `GET /api/v1/health` responde `200 {"status": "ok", "db": "not_configured"}`.

---

## 9. Documentación Adicional

Para más detalles sobre la arquitectura y contratos:
* [Especificación Técnica (`docs/SPEC.md`)](docs/SPEC.md)
* [Contratos de Datos (`docs/DATA_CONTRACTS.md`)](docs/DATA_CONTRACTS.md)
* [Roadmap y Sprints Kanban (`docs/ROADMAP_BACKEND.md`)](docs/ROADMAP_BACKEND.md)
* [Mocks JSON para Frontend (`docs/mocks/`)](docs/mocks/)