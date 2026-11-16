import io
from pathlib import Path
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import (
    app,
    CATALOG_DATA,
    CONSOLIDATED_DATA,
    DATA_DIR,
    MVP_OCCUPATIONS,
    REQUIRED_UPLOAD_COLUMNS,
    VALID_COUNTRIES,
    VALID_OCCUPATION_IDS,
    deduplicate_common_records,
    transform_upload_to_common_structure,
)

client = TestClient(app)


def create_csv_bytes(rows: list, columns: list = None) -> bytes:
    df = pd.DataFrame(rows, columns=columns)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")


def create_xlsx_bytes(rows: list, columns: list = None) -> bytes:
    df = pd.DataFrame(rows, columns=columns)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    return buf.getvalue()


VALID_SAMPLE_ROWS = [
    {
        "country_code": "ARG",
        "sector_id": "SEC_TEC",
        "occupation_id": "OCUP_01",
        "metric_name": "tasa_empleo",
        "metric_value": 78.5,
        "period": "2025",
        "source_name": "INDEC",
        "data_type": "observed",
    },
    {
        "country_code": "CHL",
        "sector_id": "SEC_IND",
        "occupation_id": "OCUP_05",
        "metric_name": "ingreso_medio",
        "metric_value": 1250.0,
        "period": "2026",
        "source_name": "INE_CHL",
        "data_type": "projected",
    },
]


# =====================================================================
# PRUEBAS DE ENDPOINTS API (API-001 a API-014)
# =====================================================================

def test_api_001_descarga_catalogo_ocupaciones():
    """API-001: Verificar la descarga del catálogo de ocupaciones."""
    response = client.get("/api/v1/ocupaciones/descargar")
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    df = pd.read_csv(io.StringIO(response.text))
    assert len(df) == 60


def test_api_002_estructura_catalogo_descargado():
    """API-002: Verificar la estructura y tipos de datos del catálogo descargado."""
    response = client.get("/api/v1/ocupaciones/descargar")
    df = pd.read_csv(io.StringIO(response.text), dtype={"ciuo_08": str, "period": str})
    expected_cols = {
        "pais_codigo_iso3",
        "ocupacion_id",
        "ocupacion_uid",
        "nombre_ocupacion",
        "ciuo_08",
        "sector_id",
        "sector",
        "metric_name",
        "metric_value",
        "period",
        "fuente_oficial",
        "fecha_extraccion",
        "data_type",
    }
    assert expected_cols.issubset(set(df.columns))
    assert pd.api.types.is_float_dtype(df["metric_value"]) or pd.api.types.is_numeric_dtype(df["metric_value"])


def test_api_003_verificar_20_ocupaciones_y_ciuo_08():
    """
    API-003: Verificar las 20 ocupaciones del MVP y sus códigos CIUO-08.
    La identificación única utiliza pais_codigo_iso3 + ocupacion_id (CIUO-08 puede repetirse).
    """
    response = client.get("/api/v1/ocupaciones/descargar")
    df = pd.read_csv(io.StringIO(response.text), dtype={"ciuo_08": str})
    unique_occupations = set(df["ocupacion_id"].unique())
    assert len(unique_occupations) == 20
    assert unique_occupations == VALID_OCCUPATION_IDS

    # Verificar que la clave compuesta pais_codigo_iso3 + ocupacion_id sea única en los 60 registros
    composite_keys = df["pais_codigo_iso3"] + "_" + df["ocupacion_id"]
    assert composite_keys.nunique() == 60
    # Verificar que CIUO-08 puede repetirse entre ocupaciones sin romper unicidad
    assert df[df["pais_codigo_iso3"] == "ARG"]["ciuo_08"].nunique() < 20


def test_api_004_descarga_consolidado_regional():
    """API-004: Verificar la descarga del consolidado regional (HTTP 200 y CSV)."""
    response = client.get("/api/v1/consolidado/descargar")
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    df = pd.read_csv(io.StringIO(response.text))
    assert not df.empty


def test_api_005_paises_y_cobertura_consolidado():
    """
    API-005: Verificar países (ARG, CHL, URY) y cobertura del consolidado
    (referencia: 45 registros por país y 135 en total).
    """
    response = client.get("/api/v1/consolidado/descargar")
    df = pd.read_csv(io.StringIO(response.text))
    assert set(df["pais_codigo_iso3"].unique()) == {"ARG", "CHL", "URY"}
    assert len(df) == 135
    for country in ("ARG", "CHL", "URY"):
        assert len(df[df["pais_codigo_iso3"] == country]) == 45


def test_api_006_estructura_comun_consolidado():
    """API-006: Verificar la estructura común del consolidado regional."""
    response = client.get("/api/v1/consolidado/descargar")
    df = pd.read_csv(io.StringIO(response.text), dtype={"period": str})
    common_cols = {
        "pais_codigo_iso3",
        "sector_id",
        "ocupacion_id",
        "metric_name",
        "metric_value",
        "period",
        "fuente_oficial",
        "fecha_extraccion",
        "data_type",
    }
    assert common_cols.issubset(set(df.columns))
    assert df["metric_value"].notna().all()


def test_api_007_codigos_pais_y_ciuo_08():
    """
    API-007: Verificar que ARG, CHL y URY son válidos en ambos datasets
    y que CIUO-08 se verifica en el catálogo de ocupaciones.
    """
    cat_resp = client.get("/api/v1/ocupaciones/descargar")
    cons_resp = client.get("/api/v1/consolidado/descargar")
    df_cat = pd.read_csv(io.StringIO(cat_resp.text), dtype={"ciuo_08": str})
    df_cons = pd.read_csv(io.StringIO(cons_resp.text))

    assert set(df_cat["pais_codigo_iso3"].unique()) == VALID_COUNTRIES
    assert set(df_cons["pais_codigo_iso3"].unique()) == VALID_COUNTRIES
    assert "ciuo_08" in df_cat.columns
    assert df_cat["ciuo_08"].str.match(r"^\d{4}$").all()


def test_api_008_procesamiento_consolidado():
    """API-008: Verificar que GET /api/v1/consolidado/procesar procesa los 3 países y genera archivos."""
    response = client.get("/api/v1/consolidado/procesar")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "processed"
    assert set(body["countries_processed"]) == {"ARG", "CHL", "URY"}
    for country in ("ARG", "CHL", "URY"):
        assert Path(body["files"][country]).exists()
    assert Path(body["files"]["consolidado"]).exists()


def test_api_009_consulta_catalogo_con_filtros():
    """
    API-009: Verificar consulta del catálogo con y sin filtros.
    Con sector=Tecnología y pais=ARG se esperan 4 registros.
    """
    resp_all = client.get("/api/v1/ocupaciones/catalogo")
    assert resp_all.status_code == 200
    assert resp_all.json()["count"] == 60

    resp_filtered = client.get("/api/v1/ocupaciones/catalogo", params={"sector": "Tecnología", "pais": "ARG"})
    assert resp_filtered.status_code == 200
    data = resp_filtered.json()
    assert data["count"] == 4
    for item in data["items"]:
        assert item["pais_codigo_iso3"] == "ARG"
        assert item["sector"] == "Tecnología"


def test_api_010_resiliencia_ilostat_no_disponible():
    """API-010: Verificar que si ILOSTAT no está disponible continúa usando el respaldo disponible."""
    response = client.get("/api/v1/consolidado/procesar", params={"simulate_ilostat_down": True})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "processed_with_backup"
    assert body["total_records"] == 135


def test_api_011_cambio_estructura_fuente_externa():
    """API-011: Verificar que si cambia la estructura de la fuente el sistema no incorpora datos corruptos ni falla sin control."""
    response = client.get("/api/v1/consolidado/procesar", params={"simulate_schema_change": True})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "rejected_invalid_source_schema"
    assert body["data_incorporated"] is False


def test_api_012_trazabilidad_fuente_y_fecha():
    """API-012: Verificar origen y fecha de los datos (fuente_oficial, fecha_extraccion y traceability)."""
    response = client.get("/api/v1/ocupaciones/catalogo", params={"pais": "ARG"})
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) > 0
    for item in items:
        assert item.get("fuente_oficial") == "ILOSTAT"
        assert item.get("fecha_extraccion") is not None
        trace = item.get("traceability", {})
        assert trace.get("source") == "ILOSTAT"
        assert trace.get("retrieved_at") is not None
        assert trace.get("last_updated") is not None


def test_api_013_identificacion_datos_fuente_y_calculados():
    """API-013: Verificar diferenciación entre dato observado (observed) y proyectado (projected)."""
    response = client.get("/api/v1/ocupaciones/catalogo")
    items = response.json()["items"]
    data_types = {item["data_type"] for item in items}
    assert data_types == {"observed", "projected"}
    for item in items:
        assert item["traceability"]["data_type"] in {"observed", "projected"}


def test_api_014_comparar_dataset_procesado_con_api():
    """API-014: Comparar dataset procesado en disco con la respuesta de la API usando pais_codigo_iso3 + ocupacion_id."""
    df_disk = pd.read_csv(DATA_DIR / "catalogo_ocupaciones.csv", dtype={"ciuo_08": str, "period": str})
    api_items = client.get("/api/v1/ocupaciones/catalogo").json()["items"]

    disk_map = {f"{r['pais_codigo_iso3']}_{r['ocupacion_id']}": r for _, r in df_disk.iterrows()}
    api_map = {f"{r['pais_codigo_iso3']}_{r['ocupacion_id']}": r for r in api_items}

    assert set(disk_map.keys()) == set(api_map.keys())
    for key, api_row in api_map.items():
        disk_row = disk_map[key]
        assert api_row["ciuo_08"] == disk_row["ciuo_08"]
        assert float(api_row["metric_value"]) == float(disk_row["metric_value"])


# =====================================================================
# PRUEBAS DE CARGA Y ETL (LOAD-001 a LOAD-012)
# =====================================================================

def test_load_001_csv_valido_aceptado():
    """LOAD-001: Verificar carga de CSV válido mediante POST /api/v1/datasets/upload."""
    csv_bytes = create_csv_bytes(VALID_SAMPLE_ROWS)
    response = client.post(
        "/api/v1/datasets/upload",
        files={"file": ("datos_validos.csv", csv_bytes, "text/csv")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "accepted"
    assert body["records_valid"] == 2


def test_load_002_xlsx_valido_aceptado():
    """LOAD-002: Verificar carga de XLSX válido mediante POST /api/v1/datasets/upload."""
    xlsx_bytes = create_xlsx_bytes(VALID_SAMPLE_ROWS)
    response = client.post(
        "/api/v1/datasets/upload",
        files={
            "file": (
                "datos_validos.xlsx",
                xlsx_bytes,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "accepted"
    assert body["records_valid"] == 2


def test_load_003_archivo_vacio_rechazado():
    """LOAD-003: Verificar que un archivo CSV o XLSX vacío es rechazado con HTTP 400."""
    # Variante CSV vacío (0 bytes)
    resp_csv = client.post(
        "/api/v1/datasets/upload",
        files={"file": ("vacio.csv", b"", "text/csv")},
    )
    assert resp_csv.status_code == 400

    # Variante XLSX con encabezados pero sin filas
    empty_xlsx = create_xlsx_bytes([], columns=REQUIRED_UPLOAD_COLUMNS)
    resp_xlsx = client.post(
        "/api/v1/datasets/upload",
        files={"file": ("vacio.xlsx", empty_xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp_xlsx.status_code == 400


def test_load_004_campos_obligatorios_faltantes():
    """LOAD-004: Verificar que si faltan columnas obligatorias responde HTTP 400 e informa los campos faltantes."""
    incomplete_rows = [
        {
            "country_code": "ARG",
            "sector_id": "SEC_TEC",
            # Falta occupation_id y data_type
            "metric_name": "tasa_empleo",
            "metric_value": 80.0,
            "period": "2025",
            "source_name": "INDEC",
        }
    ]
    csv_bytes = create_csv_bytes(incomplete_rows)
    response = client.post(
        "/api/v1/datasets/upload",
        files={"file": ("incompleto.csv", csv_bytes, "text/csv")},
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "occupation_id" in detail["missing_fields"]
    assert "data_type" in detail["missing_fields"]


def test_load_005_datos_con_formato_o_tipo_incorrecto():
    """
    LOAD-005: Verificar rechazo HTTP 400 cuando metric_value no es Float
    o data_type no pertenece a {observed, projected}.
    """
    invalid_type_rows = [
        {
            **VALID_SAMPLE_ROWS[0],
            "metric_value": "NO_ES_UN_FLOAT",
        }
    ]
    resp1 = client.post(
        "/api/v1/datasets/upload",
        files={"file": ("tipo_invalido.csv", create_csv_bytes(invalid_type_rows), "text/csv")},
    )
    assert resp1.status_code == 400
    assert resp1.json()["detail"]["invalid_field"] == "metric_value"

    invalid_dtype_rows = [
        {
            **VALID_SAMPLE_ROWS[0],
            "data_type": "inventado",
        }
    ]
    resp2 = client.post(
        "/api/v1/datasets/upload",
        files={"file": ("dtype_invalido.csv", create_csv_bytes(invalid_dtype_rows), "text/csv")},
    )
    assert resp2.status_code == 400
    assert resp2.json()["detail"]["invalid_field"] == "data_type"


def test_load_006_registros_duplicados_detectados():
    """LOAD-006: Verificar que los registros duplicados en carga manual se detectan y deduplican."""
    duplicated_rows = [VALID_SAMPLE_ROWS[0], VALID_SAMPLE_ROWS[0], VALID_SAMPLE_ROWS[1]]
    response = client.post(
        "/api/v1/datasets/upload",
        files={"file": ("duplicados.csv", create_csv_bytes(duplicated_rows), "text/csv")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["records_received"] == 3
    assert body["records_valid"] == 2
    assert body["duplicates_removed"] == 1


def test_load_007_codigo_pais_no_permitido():
    """LOAD-007: Verificar rechazo de códigos de país distintos de ARG, URY y CHL."""
    invalid_country_rows = [
        {
            **VALID_SAMPLE_ROWS[0],
            "country_code": "BRA",
        }
    ]
    response = client.post(
        "/api/v1/datasets/upload",
        files={"file": ("pais_invalido.csv", create_csv_bytes(invalid_country_rows), "text/csv")},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["invalid_field"] == "country_code"


def test_load_008_identificador_ocupacion_invalido():
    """LOAD-008: Verificar rechazo cuando occupation_id no existe en el catálogo de ocupaciones."""
    invalid_occ_rows = [
        {
            **VALID_SAMPLE_ROWS[0],
            "occupation_id": "OCUP_999_INEXISTENTE",
        }
    ]
    response = client.post(
        "/api/v1/datasets/upload",
        files={"file": ("ocup_invalida.csv", create_csv_bytes(invalid_occ_rows), "text/csv")},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["invalid_field"] == "occupation_id"


def test_load_009_cobertura_datasets_procesados():
    """
    LOAD-009: Verificar cobertura de datasets procesados:
    3 países (45 por país / 135 en consolidado) y 60 registros en catálogo de ocupaciones.
    """
    client.get("/api/v1/consolidado/procesar")
    df_cons = pd.read_csv(DATA_DIR / "consolidado_regional.csv")
    df_cat = pd.read_csv(DATA_DIR / "catalogo_ocupaciones.csv")

    nacionales = []
    for country in ("ARG", "CHL", "URY"):
        df_nac = pd.read_csv(DATA_DIR / f"consolidado_{country}.csv")
        assert len(df_nac) == 45
        nacionales.append(df_nac)

    df_sum = pd.concat(nacionales, ignore_index=True)
    assert len(df_cons) == 135
    assert len(df_sum) == len(df_cons)
    assert len(df_cat) == 60


def test_load_010_transformacion_estructura_comun():
    """LOAD-010: Verificar transformación del contrato de carga manual a la estructura común."""
    df_input = pd.DataFrame(VALID_SAMPLE_ROWS)
    transformed = transform_upload_to_common_structure(df_input)
    assert len(transformed) == 2
    first = transformed[0]
    assert first["pais_codigo_iso3"] == "ARG"
    assert first["sector_id"] == "SEC_TEC"
    assert first["ocupacion_id"] == "OCUP_01"
    assert first["metric_name"] == "tasa_empleo"
    assert first["metric_value"] == 78.5
    assert first["period"] == "2025"
    assert first["fuente_oficial"] == "INDEC"
    assert first["data_type"] == "observed"
    assert "fecha_extraccion" in first


def test_load_011_etl_no_genera_duplicados():
    """LOAD-011: Verificar que el ETL elimina duplicados por clave compuesta y usa pais_codigo_iso3 + ocupacion_id."""
    raw = CONSOLIDATED_DATA + [CONSOLIDATED_DATA[0], CONSOLIDATED_DATA[1]]
    deduped, removed = deduplicate_common_records(raw)
    assert removed == 2
    assert len(deduped) == len(CONSOLIDATED_DATA)

    # En ocupaciones, validar que pais_codigo_iso3 + ocupacion_id mantiene las 60 filas aunque CIUO-08 se repita
    occ_keys = {(r["pais_codigo_iso3"], r["ocupacion_id"]) for r in CATALOG_DATA}
    assert len(occ_keys) == 60


def test_load_012_no_se_pierden_registros_validos():
    """LOAD-012: Verificar que todos los registros válidos ingresados permanecen íntegros en la salida."""
    valid_batch = [
        {
            "country_code": "ARG",
            "sector_id": "SEC_TEC",
            "occupation_id": f"OCUP_{i:02d}",
            "metric_name": "tasa_empleo",
            "metric_value": float(60 + i),
            "period": "2025",
            "source_name": "ILOSTAT",
            "data_type": "observed",
        }
        for i in range(1, 11)
    ]
    response = client.post(
        "/api/v1/datasets/upload",
        files={"file": ("lote_valido.csv", create_csv_bytes(valid_batch), "text/csv")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["records_received"] == 10
    assert body["records_valid"] == 10
    assert len(body["data"]) == 10