"""Casos QA API-001..API-014 contra la API del equipo Data (repo DataAnalyst).

La matriz docs/Casos_Apis_CargaDatos - 22092026.csv define estos casos para los
endpoints /ocupaciones/*, /consolidado/* y /analytics/*, que viven en el repo
DataAnalyst (no en este backend).

Requisitos:
  * Repo DataAnalyst clonado (env DATA_API_PATH, por defecto /tmp/opencode/DataAnalyst).
    Si no existe, los tests de interfaz se omitten (skip).
  * Si no hay una API corriendo en DATA_API_URL (default http://127.0.0.1:8001),
    el fixture la levanta con uvicorn y la detiene al terminar.

API-010 y API-011 se validan como tests unitarios del ETL de Data
(cliente ILOSTAT con respaldo y cleaner con estructura alterada).
"""

import asyncio
import io
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pandas as pd
import pytest

DATA_API_PATH = Path(os.environ.get("DATA_API_PATH", "/tmp/opencode/DataAnalyst"))
DATA_API_URL = os.environ.get("DATA_API_URL", "http://127.0.0.1:8001").rstrip("/")
SPAWN_PORT = int(DATA_API_URL.rsplit(":", 1)[-1]) if ":" in DATA_API_URL.rsplit("/", 1)[-1] else 8001

CONSOLIDADO_ESQUEMA = [
    "pais_codigo_iso3",
    "pais_nombre",
    "dimension",
    "indicador_nombre",
    "anio",
    "periodo",
    "valor",
    "unidad_medida",
    "fuente_oficial",
    "fecha_extraccion",
]

OCUPACIONES_ESQUEMA = [
    "pais_codigo_iso3",
    "pais_nombre",
    "sector",
    "ocupacion_id",
    "ocupacion_nombre",
    "codigo_ciuo08_oit",
    "nivel_demanda",
    "tendencia_crecimiento_estimada",
    "habilidades_clave",
    "fuentes_oficiales_validadas",
    "contexto_pais",
    "fecha_actualizacion",
]

# Matriz CIUO-08 definida por el equipo Data (README de DataAnalyst).
# Nota: 2149 se repite entre OCUP_09 y OCUP_12; la llave real es pais+ocupacion_id.
MATRIZ_CIUO = {
    "OCUP_01": "2512",
    "OCUP_02": "2511",
    "OCUP_03": "2529",
    "OCUP_04": "2522",
    "OCUP_05": "2211",
    "OCUP_06": "2221",
    "OCUP_07": "2262",
    "OCUP_08": "3211",
    "OCUP_09": "2149",
    "OCUP_10": "2146",
    "OCUP_11": "3113",
    "OCUP_12": "2149",
    "OCUP_13": "1411",
    "OCUP_14": "5113",
    "OCUP_15": "3339",
    "OCUP_16": "3434",
    "OCUP_17": "2166",
    "OCUP_18": "2421",
    "OCUP_19": "2131",
    "OCUP_20": "2413",
}


def _reachable(url: str) -> bool:
    try:
        return httpx.get(url + "/", timeout=2.0).status_code == 200
    except Exception:
        return False


@pytest.fixture(scope="session")
def data_api() -> str:
    if _reachable(DATA_API_URL):
        yield DATA_API_URL
        return

    if not (DATA_API_PATH / "main.py").exists():
        pytest.skip(
            f"API de Data no disponible: clonar DataAnalyst en {DATA_API_PATH} "
            "o definir DATA_API_URL con una instancia corriendo."
        )

    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "main:app",
            "--app-dir",
            str(DATA_API_PATH),
            "--port",
            str(SPAWN_PORT),
            "--log-level",
            "warning",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        for _ in range(60):
            if _reachable(DATA_API_URL):
                break
            if process.poll() is not None:
                output = process.stdout.read().decode(errors="replace") if process.stdout else ""
                pytest.skip(f"uvicorn de Data termino antes de estar listo:\n{output[-800:]}")
            time.sleep(0.5)
        else:
            pytest.skip("La API de Data no respondio en 30s.")
        yield DATA_API_URL
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


@pytest.fixture(scope="session")
def data_repo() -> Path:
    if not (DATA_API_PATH / "main.py").exists():
        pytest.skip(f"Repo DataAnalyst no encontrado en {DATA_API_PATH}.")
    sys.path.insert(0, str(DATA_API_PATH))
    return DATA_API_PATH


def _get(url: str, **kwargs) -> httpx.Response:
    kwargs.setdefault("timeout", 30.0)
    return httpx.get(url, **kwargs)


def _ocupaciones_csv(data_api: str) -> pd.DataFrame:
    response = _get(f"{data_api}/api/v1/ocupaciones/descargar")
    assert response.status_code == 200
    return pd.read_csv(io.BytesIO(response.content), encoding="utf-8-sig")


def _consolidado_csv(data_api: str) -> pd.DataFrame:
    response = _get(f"{data_api}/api/v1/consolidado/descargar")
    assert response.status_code == 200
    return pd.read_csv(io.BytesIO(response.content), encoding="utf-8-sig")


# ---------------------------------------------------------------------------
# API-001..003: catalogo de ocupaciones
# ---------------------------------------------------------------------------
def test_api_001_descarga_catalogo_ocupaciones(data_api):
    """API-001: GET /ocupaciones/descargar devuelve el catalogo en CSV."""
    response = _get(f"{data_api}/api/v1/ocupaciones/descargar")

    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert len(response.content) > 0


def test_api_002_estructura_catalogo_descargado(data_api):
    """API-002: el catalogo tiene todos los campos esperados y sin nulos en claves."""
    df = _ocupaciones_csv(data_api)

    assert list(df.columns) == OCUPACIONES_ESQUEMA
    assert not df.empty
    for column in ("pais_codigo_iso3", "ocupacion_id", "codigo_ciuo08_oit"):
        assert df[column].notna().all()


def test_api_003_20_ocupaciones_y_ciuo08(data_api):
    """API-003: 20 ocupaciones con su CIUO-08 correcto (CIUO puede repetirse)."""
    df = _ocupaciones_csv(data_api)

    assert set(df["ocupacion_id"]) == set(MATRIZ_CIUO)
    assert len(df) == 60  # 20 ocupaciones x 3 paises

    parejas = df[["pais_codigo_iso3", "ocupacion_id"]].drop_duplicates()
    assert len(parejas) == 60  # la llave pais+ocupacion_id es unica

    for ocupacion_id, ciuo in df.groupby("ocupacion_id")["codigo_ciuo08_oit"].first().items():
        assert str(ciuo) == MATRIZ_CIUO[ocupacion_id], f"{ocupacion_id}: CIUO inesperado"


# ---------------------------------------------------------------------------
# API-004..007: consolidado regional
# ---------------------------------------------------------------------------
def test_api_004_descarga_consolidado(data_api):
    """API-004: GET /consolidado/descargar devuelve HTTP 200 y CSV."""
    response = _get(f"{data_api}/api/v1/consolidado/descargar")

    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]


def test_api_005_paises_y_cobertura_consolidado(data_api):
    """API-005: ARG + CHL + URY presentes (45/pais y 135 total es referencia)."""
    df = _consolidado_csv(data_api)

    assert set(df["pais_codigo_iso3"]) == {"ARG", "CHL", "URY"}
    conteo = df["pais_codigo_iso3"].value_counts()
    assert (conteo > 0).all()
    assert len(df) > 0


def test_api_006_estructura_comun_consolidado(data_api):
    """API-006: todos los registros tienen la estructura comun definida."""
    df = _consolidado_csv(data_api)

    assert list(df.columns) == CONSOLIDADO_ESQUEMA
    assert pd.api.types.is_numeric_dtype(df["anio"])
    assert pd.api.types.is_numeric_dtype(df["valor"])
    assert df["indicador_nombre"].notna().all()


def test_api_007_codigos_pais_validos(data_api):
    """API-007: codigos de pais validos (el CIUO-08 se verifica en API-003)."""
    df = _consolidado_csv(data_api)

    assert set(df["pais_codigo_iso3"]) <= {"ARG", "CHL", "URY"}


# ---------------------------------------------------------------------------
# API-008: procesamiento
# ---------------------------------------------------------------------------
def test_api_008_procesar_consolidado(data_api):
    """API-008: /consolidado/procesar procesa los 3 paises y genera archivos."""
    response = _get(f"{data_api}/api/v1/consolidado/procesar", timeout=180.0)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "Pipeline regional completado"
    assert body["total_filas_consolidadas"] > 0
    for pais in ("Argentina", "Chile", "Uruguay"):
        assert pais in body["paises_procesados"]
    assert body["archivo_generado"] == "dataset_consolidado_regional.csv"


# ---------------------------------------------------------------------------
# API-009: catalogo con filtros
# ---------------------------------------------------------------------------
def test_api_009_catalogo_con_filtros(data_api):
    """API-009: sin filtros 60 registros; Tecnologia+ARG -> 4 registros."""
    sin_filtros = _get(f"{data_api}/api/v1/ocupaciones/catalogo")
    assert sin_filtros.status_code == 200
    assert len(sin_filtros.json()) == 60

    filtrado = _get(
        f"{data_api}/api/v1/ocupaciones/catalogo",
        params={"sector": "Tecnología", "pais": "ARG"},
    )
    assert filtrado.status_code == 200
    registros = filtrado.json()
    assert len(registros) == 4
    assert all(r["pais_codigo_iso3"] == "ARG" for r in registros)
    assert all(r["sector"] == "Tecnología" for r in registros)


# ---------------------------------------------------------------------------
# API-010: caida de ILOSTAT (unitario, sobre el cliente de Data)
# ---------------------------------------------------------------------------
def test_api_010_ilostat_no_disponible_usa_respaldo(data_repo, monkeypatch):
    """API-010: si ILOSTAT no responde, se usa el respaldo y no hay datos invalidos."""
    import httpx as httpx_module
    from etl.ilostat_client import fetch_ilostat_data

    async def _sin_red(*args, **kwargs):
        raise httpx_module.ConnectError("ILOSTAT caido (simulado)")

    monkeypatch.setattr(httpx_module.AsyncClient, "get", _sin_red)

    registros = asyncio.run(fetch_ilostat_data("ARG"))

    assert registros, "el respaldo debe producir registros"
    assert all(r["fuente_oficial"] == "ILOSTAT - OIT" for r in registros)
    assert not any("API SDMX" in r["fuente_oficial"] for r in registros)
    anios_desempleo = {
        r["anio"] for r in registros if r["indicador_nombre"] == "Tasa de Desocupación Total"
    }
    assert anios_desempleo == set(range(2015, 2025))
    assert all(r["pais_codigo_iso3"] == "ARG" for r in registros)
    assert all(isinstance(r["valor"], float) for r in registros)


# ---------------------------------------------------------------------------
# API-011: estructura de fuente alterada (unitario, sobre el cleaner de Data)
# ---------------------------------------------------------------------------
def test_api_011_fuente_con_campos_faltantes_no_falla(data_repo):
    """API-011: con campos faltantes/cambiados no se incorporan datos incorrectos ni falla."""
    from etl.cleaner import ESQUEMA_COLUMNAS, depurar_y_estructurar

    registros = [
        {
            "pais_codigo_iso3": "ARG",
            "pais_nombre": "Argentina",
            "dimension": "Economía",
            "indicador_nombre": "Inflación Anual",
            "anio": 2021,
            "periodo": "Anual",
            "valor": 50.9,
            "unidad_medida": "Porcentaje (%)",
            "fuente_oficial": "CEPALSTAT",
            "fecha_extraccion": "2026-09-10",
        },
        # Sin fuente_oficial ni fecha_extraccion: se completan con la columna
        {
            "pais_codigo_iso3": "CHL",
            "pais_nombre": "Chile",
            "dimension": "Economía",
            "indicador_nombre": "PIB Real",
            "anio": 2020,
            "periodo": "Anual",
            "valor": -6.1,
            "unidad_medida": "Porcentaje (%)",
        },
        # Estructura alterada: campo desconocido y valor nulo -> fila descartada
        {
            "pais_codigo_iso3": "URY",
            "pais_nombre": "Uruguay",
            "dimension": "Economía",
            "indicador_nombre": "PIB Real",
            "anio": 2020,
            "periodo": "Anual",
            "valor": None,
            "unidad_medida": "Porcentaje (%)",
            "campo_desconocido": "x",
            "fuente_oficial": "CEPALSTAT",
            "fecha_extraccion": "2026-09-10",
        },
    ]

    df = depurar_y_estructurar(registros)

    assert list(df.columns) == ESQUEMA_COLUMNAS
    assert len(df) == 2  # la fila con valor nulo no se incorpora
    assert "campo_desconocido" not in df.columns
    assert df["valor"].notna().all()


# ---------------------------------------------------------------------------
# API-012..014: trazabilidad y consistencia
# ---------------------------------------------------------------------------
def test_api_012_origen_y_fecha_de_los_datos(data_api):
    """API-012: cada registro indica fuente_oficial y fecha_extraccion."""
    df = _consolidado_csv(data_api)

    assert df["fuente_oficial"].notna().all()
    assert (df["fuente_oficial"].astype(str).str.len() > 0).all()
    assert df["fecha_extraccion"].notna().all()
    pd.to_datetime(df["fecha_extraccion"], format="%Y-%m-%d", errors="raise")


def test_api_013_dato_fuente_vs_calculado(data_api):
    """API-013: el indice sintetico es calculado; el consolidado trae datos fuente."""
    indicadores = _consolidado_csv(data_api)
    assert "fuente_oficial" in indicadores.columns
    assert "valor" in indicadores.columns

    response = _get(f"{data_api}/api/v1/analytics/indice-sintetico")
    assert response.status_code == 200
    serie = response.json()["serie_historica"]
    assert serie, "la serie del indice debe tener registros"
    assert "indice_sintetico" in serie[0]
    assert "tendencia" in serie[0]
    assert "fuente_oficial" not in serie[0]


def test_api_014_consistencia_dataset_vs_api(data_api):
    """API-014: los registros del catalogo (API) y del CSV descargado coinciden."""
    df_csv = _ocupaciones_csv(data_api)

    response = _get(f"{data_api}/api/v1/ocupaciones/catalogo")
    assert response.status_code == 200
    df_api = pd.DataFrame(response.json())

    llaves_csv = set(zip(df_csv["pais_codigo_iso3"], df_csv["ocupacion_id"]))
    llaves_api = set(zip(df_api["pais_codigo_iso3"], df_api["ocupacion_id"]))

    assert len(df_csv) == len(df_api)
    assert llaves_csv == llaves_api
