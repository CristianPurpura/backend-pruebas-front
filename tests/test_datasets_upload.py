"""Tests de carga manual de datasets - POST /api/v1/datasets/upload.

Mapeo con docs/Casos_Apis_CargaDatos - 22092026.csv:
  LOAD-001 CSV valido          -> pasa
  LOAD-002 XLSX valido         -> pasa
  LOAD-003 archivo vacio       -> pasa
  LOAD-004 campos obligatorios -> pasa
  LOAD-005 tipos incorrectos   -> pasa (validacion de metric_value y data_type)
  LOAD-007 codigo de pais      -> pasa (catalogo ARG/CHL/URY)
  LOAD-008 occupation_id       -> pasa (catalogo OCUP_01..OCUP_20)
"""

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


def test_load_005_metric_value_no_numerico_rechazado(client):
    """LOAD-005: metric_value no numerico -> 400 con detalle del error."""
    content = make_csv(build_rows(metric_value="no_es_un_numero"))

    response = upload(client, "bad_type.csv", content)

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "metric_value invalido" in detail
    assert "no_es_un_numero" in detail


def test_load_005_data_type_invalido_rechazado(client):
    """LOAD-005: data_type fuera de observed/projected -> 400."""
    content = make_csv(build_rows(data_type="estimado"))

    response = upload(client, "bad_data_type.csv", content)

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "data_type invalido" in detail
    assert "estimado" in detail


def test_load_007_pais_no_permitido_rechazado(client):
    """LOAD-007: country_code fuera de ARG/URY/CHL -> 400."""
    content = make_csv(build_rows(country_code="BRA"))

    response = upload(client, "bad_country.csv", content)

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "country_code invalido" in detail
    assert "BRA" in detail


def test_load_008_occupation_id_inexistente_rechazado(client):
    """LOAD-008: occupation_id fuera del catalogo OCUP_01..OCUP_20 -> 400."""
    content = make_csv(build_rows(occupation_id="OCUP_99"))

    response = upload(client, "bad_occupation.csv", content)

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "occupation_id invalido" in detail
    assert "OCUP_99" in detail


def test_load_008_archivo_con_todas_las_ocupaciones_aceptado(client):
    """LOAD-008 (positivo): las 20 ocupaciones del catalogo son validas."""
    rows = [build_rows(occupation_id=f"OCUP_{n:02d}")[0] for n in range(1, 21)]
    content = make_csv(rows)

    response = upload(client, "catalogo_completo.csv", content)

    assert response.status_code == 200
    assert response.json()["rows_count"] == 20
