"""Tests de carga manual de datasets - POST /api/v1/datasets/upload.

Mapeo con docs/Casos_Apis_CargaDatos - 22092026.csv:
  LOAD-001 CSV valido          -> pasa
  LOAD-002 XLSX valido         -> pasa
  LOAD-003 archivo vacio       -> pasa
  LOAD-004 campos obligatorios -> pasa
  LOAD-005 tipos incorrectos   -> xfail (gap: solo se valida presencia de columnas)
  LOAD-007 codigo de pais      -> xfail (gap: sin catalogo de paises en el parser)
  LOAD-008 occupation_id       -> xfail (gap: sin catalogo de ocupaciones en el parser)
"""

import pytest

from tests.conftest import REQUIRED_COLUMNS, build_rows, make_csv, make_xlsx, upload


def test_load_001_csv_valido_aceptado(client):
    """LOAD-001: CSV valido con las columnas obligatorias -> 200 y resumen correcto."""
    content = make_csv(build_rows() + build_rows(metric_value="2000.5"))

    response = upload(client, "valid.csv", content)

    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == "valid.csv"
    assert body["status"] == "ok"
    assert body["rows_count"] == 2
    assert body["message"] == "Archivo válido"
    assert body["columns_detected"] == list(REQUIRED_COLUMNS)


def test_load_002_xlsx_valido_aceptado(client):
    """LOAD-002: XLSX valido con las columnas obligatorias -> 200 y resumen correcto."""
    content = make_xlsx(build_rows())

    response = upload(client, "valid.xlsx", content)

    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == "valid.xlsx"
    assert body["status"] == "ok"
    assert body["rows_count"] == 1
    assert body["columns_detected"] == list(REQUIRED_COLUMNS)


def test_load_003_archivo_vacio_rechazado(client):
    """LOAD-003: archivo CSV sin datos -> 400, no se procesa como carga valida."""
    response = upload(client, "empty.csv", b"")

    assert response.status_code == 400
    assert response.json()["detail"] == "El archivo está vacío."


def test_load_003_xlsx_vacio_rechazado(client):
    """LOAD-003 (variante XLSX): archivo XLSX sin bytes -> 400."""
    response = upload(client, "empty.xlsx", b"")

    assert response.status_code == 400
    assert response.json()["detail"] == "El archivo está vacío."


def test_load_004_campos_obligatorios_faltantes(client):
    """LOAD-004: CSV sin campos obligatorios -> 400 con la lista de faltantes."""
    columns = [c for c in REQUIRED_COLUMNS if c not in {"metric_value", "source_name"}]
    content = make_csv(build_rows(), columns=columns)

    response = upload(client, "missing_columns.csv", content)

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail.startswith("Faltan columnas obligatorias:")
    assert "metric_value" in detail
    assert "source_name" in detail


def test_extension_no_permitida_rechazada(client):
    """Extra: extension distinta de .csv/.xlsx -> 400."""
    response = upload(client, "archivo.txt", b"a,b\n1,2\n")

    assert response.status_code == 400
    assert "Extensión no permitida" in response.json()["detail"]


def test_sin_campo_file_devuelve_422(client):
    """Extra: peticion sin el campo file -> 422 de validacion de FastAPI."""
    response = client.post("/api/v1/datasets/upload")

    assert response.status_code == 422


@pytest.mark.xfail(
    reason="LOAD-005 gap: el parser solo valida presencia de columnas, no tipos. "
    "El contrato (Data_Contracts.md) define metric_value como Float.",
    strict=True,
)
def test_load_005_metric_value_no_numerico_rechazado(client):
    """LOAD-005: metric_value no numerico -> deberia ser rechazado (hoy devuelve 200)."""
    content = make_csv(build_rows(metric_value="no_es_un_numero"))

    response = upload(client, "bad_type.csv", content)

    assert response.status_code == 400


@pytest.mark.xfail(
    reason="LOAD-007 gap: el parser no valida country_code contra el catalogo "
    "ARG/URY/CHL definido en Data_Contracts.md.",
    strict=True,
)
def test_load_007_pais_no_permitido_rechazado(client):
    """LOAD-007: country_code fuera de ARG/URY/CHL -> deberia ser rechazado (hoy 200)."""
    content = make_csv(build_rows(country_code="BRA"))

    response = upload(client, "bad_country.csv", content)

    assert response.status_code == 400


@pytest.mark.xfail(
    reason="LOAD-008 gap: el parser no valida occupation_id contra el catalogo "
    "de ocupaciones del MVP.",
    strict=True,
)
def test_load_008_occupation_id_inexistente_rechazado(client):
    """LOAD-008: occupation_id inexistente -> deberia ser rechazado (hoy 200)."""
    content = make_csv(build_rows(occupation_id="OCUP_99"))

    response = upload(client, "bad_occupation.csv", content)

    assert response.status_code == 400
