# Prototipo MVP/QA (archivado)

Material recibido del equipo el **15/11/2026** y movido acá desde la raíz del
repo (`feat_provincias/`). **No es parte del backend**: quedó archivado como
referencia histórica y de trazabilidad con los casos de QA.

> ⚠️ Estos archivos **no se ejecutan** dentro de este repositorio ni están
> incluidos en la suite (`pytest.ini` usa `testpaths = tests`). Se conservan
> solo como documentación.

## Qué contiene

| Archivo | Descripción |
| --- | --- |
| `app.py` | FastAPI standalone de un solo archivo, **sin base de datos ni conectores**. Genera los datos de forma determinista en memoria (`50.0 + idx*1.25`, `100.0 + count*2.5`) y escribe CSVs en `./data_storage`. Endpoints: `/api/v1/ocupaciones/descargar`, `/api/v1/ocupaciones/catalogo`, `/api/v1/consolidado/descargar`, `/api/v1/consolidado/procesar`, `POST /api/v1/datasets/upload`. |
| `dashboard.py` | UI **Streamlit** que consume ese `app.py` vía `TestClient`. Implementa los 3 flujos de `docs/estructura de la pagina.pdf`: Home → País, Home → País + Sector + Área + Fechas → Ficha, Home → Regional. |
| `test_backend.py` | 26 tests que reproducen los casos **API-001…API-014** y **LOAD-001…LOAD-012** de `docs/Casos_Apis_CargaDatos - 22092026.csv` contra el prototipo. |
| `test_visualizacion.py` | 3 tests de los flujos del dashboard. |

## Qué se tomó y qué no

**No se incorporó código de este prototipo al backend.** La cobertura de sus
casos ya existe en la suite real y con el contrato vigente:

| Casos | Cobertura actual en este repo |
| --- | --- |
| API-001…API-016 | `tests/test_data_api_matrix.py` (contra la API del equipo Data) |
| LOAD-001…LOAD-012 | `tests/test_datasets_upload.py` y `tests/test_normalization.py` |

Lo que sí se rescató fue **conceptual**:

* La matriz de casos QA (API/LOAD) y su mapeo a tests, que confirma que los
  casos están cubiertos con otra implementación.
* Los **3 flujos de navegación** y la idea de **filtros en cascada**
  (`país → sector → área`). Es el molde donde encajaría un selector de
  provincias si se aprobara (ver `docs/FUERA_DE_ALCANCE.md`).

## Por qué no se puede enchufar tal cual

| Aspecto | Prototipo | Backend actual |
| --- | --- | --- |
| Contrato de carga | `data_type = observed \| projected` | `percentage \| currency \| count` + `is_projection` |
| Sectores | `SEC_TEC`, `SEC_IND`, `SEC_AGR`, `SEC_FIN`, `SEC_SAL`, `SEC_COM` (6) | `TEC`, `SAL`, `ENE`, `TUR`, `ECO` (5) |
| Catálogo de ocupaciones | OCUP_01…20 con otra definición (p. ej. OCUP_05 = "Ingeniero Industrial") | OCUP_01…20 del catálogo regional (p. ej. OCUP_05 = "Médico General") |
| Persistencia | listas en memoria + CSV en `./data_storage` | PostgreSQL + Alembic + `data/processed/` |
| Rutas | `/api/v1/ocupaciones/...`, `/api/v1/consolidado/...` | `/api/v1/occupations`, `/api/v1/employability`, `/api/v1/skills`, … |
| Import | `from app import app` (su propio módulo `app.py`) | `app` es el paquete real → `ImportError` |

Además, `dashboard.py` llama a `/api/v1/filtros/opciones` y
`/api/v1/visualizacion/*`, que **no existen** en su propio `app.py`: los
archivos están incompletos entre sí y el dashboard devolvería 404.

> Nota: el filtro "**Área**" del dashboard **no es geográfico**; es área de
> conocimiento (p. ej. `"Ingeniería de Software"`). No hay provincias.

## Cómo ejecutarlo aislado (si hace falta reproducirlo)

Requiere sacarlo de este repo o crear un paquete propio, porque `app.py`
colisiona con el paquete `app/`:

```bash
mkdir -p /tmp/mvp-qa && cp docs/prototipos/mvp-qa/*.py /tmp/mvp-qa/
cd /tmp/mvp-qa
python -m venv .venv && . .venv/bin/activate
pip install fastapi uvicorn pandas openpyxl streamlit pytest
pytest -q test_backend.py
uvicorn app:app --port 8100      # o: streamlit run dashboard.py
```
