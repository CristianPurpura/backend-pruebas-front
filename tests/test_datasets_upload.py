"""Tests de carga manual de datasets - POST /api/v1/datasets/upload.

Mapeo con docs/Casos_Apis_CargaDatos - 22092026.csv:
  LOAD-001 CSV valido          -> pasa
  LOAD-002 XLSX valido         -> pasa
  LOAD-003 archivo vacio       -> pasa (400)
  LOAD-004 campos obligatorios -> pasa (400)
  LOAD-005 tipos incorrectos   -> pasa (422 con detalle por fila)
  LOAD-006 duplicados         -> pasa
  LOAD-007 codigo de pais      -> pasa (422 con detalle por fila)
  LOAD-008 occupation_id       -> pasa (catalogo: cuarentena UNMAPPED_CATALOG)
  LOAD-009 cobertura           -> pasa (45 por pais / 135 en total)
  LOAD-010 estructura comun    -> pasa (mapeo al esquema de Data)
  LOAD-011 deduplicacion ETL   -> pasa (clave natural)
  LOAD-012 validos/descartados -> pasa (valido / dedupe / cuarentena)
"""

import csv
import json
from pathlib import Path

from app.core.catalogs import OCUPACIONES, SECTORES
from tests.conftest import (
    REQUIRED_COLUMNS,
    build_rows,
    make_common_csv,
    make_csv,
    make_xlsx,
    upload,
)

CODIGO_SECTOR = {nombre: codigo for codigo, nombre in SECTORES.items()}
SECTOR_POR_OCUPACION = {
    ocupacion: CODIGO_SECTOR[ficha["sector"]] for ocupacion, ficha in OCUPACIONES.items()
}

SECTORES_GOLDEN = (
    ("TEC", "OCUP_01"),
    ("SAL", "OCUP_05"),
    ("ENE", "OCUP_09"),
    ("TUR", "OCUP_13"),
    ("ECO", "OCUP_17"),
)


def build_golden_rows() -> list[dict[str, str]]:
    """135 registros: 3 países × 5 sectores × 3 períodos × 3 indicadores."""
    filas: list[dict[str, str]] = []
    for pais in ("ARG", "CHL", "URY"):
        for sector, ocupacion in SECTORES_GOLDEN:
            for periodo in ("2021", "2022", "2023"):
                for indice, indicador in enumerate(
                    ("demanda_laboral", "oferta_formativa", "brecha_habilidades")
                ):
                    filas.append(
                        {
                            "country_code": pais,
                            "sector_id": sector,
                            "occupation_id": ocupacion,
                            "metric_name": indicador,
                            "metric_value": str(1000 + indice * 10 + len(filas)),
                            "period": periodo,
                            "source_name": "INDEC-EPH",
                            "data_type": "count",
                        }
                    )
    return filas


def test_load_001_csv_valido_aceptado(client):
    """LOAD-001: CSV valido con las columnas obligatorias -> 200 y resumen correcto."""
    content = make_csv(build_rows() + build_rows(metric_value="2000.5", occupation_id="OCUP_02"))

    response = upload(client, "valid.csv", content)

    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == "valid.csv"
    assert body["status"] == "ok"
    assert body["rows_count"] == 2
    assert body["rows_valid"] == 2
    assert body["rows_quarantined"] == 0
    assert body["message"].startswith("Archivo normalizado")
    assert body["columns_detected"] == list(REQUIRED_COLUMNS)
    assert body["normalized_columns"][:4] == [
        "pais_codigo_iso3",
        "pais_nombre",
        "dimension",
        "indicador_nombre",
    ]


def test_load_002_xlsx_valido_aceptado(client):
    """LOAD-002: XLSX valido con las columnas obligatorias -> 200 y resumen correcto."""
    content = make_xlsx(build_rows())

    response = upload(client, "valid.xlsx", content)

    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == "valid.xlsx"
    assert body["status"] == "ok"
    assert body["rows_count"] == 1
    assert body["rows_valid"] == 1
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
    """LOAD-005: metric_value no numerico -> 422 con fila, campo y causa."""
    content = make_csv(build_rows(metric_value="no_es_un_numero"))

    response = upload(client, "bad_type.csv", content)

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "rows" in detail
    error = detail["rows"][0]
    assert error["field"] == "metric_value"
    assert error["value"] == "no_es_un_numero"
    assert "numérico" in error["cause"]
    assert error["row"] == 2


def test_load_005_data_type_invalido_rechazado(client):
    """LOAD-005: data_type fuera de percentage/currency/count -> 422."""
    content = make_csv(build_rows(data_type="estimado"))

    response = upload(client, "bad_data_type.csv", content)

    assert response.status_code == 422
    error = response.json()["detail"]["rows"][0]
    assert error["field"] == "data_type"
    assert error["value"] == "estimado"
    assert "percentage, currency, count" in error["cause"]


def test_load_007_pais_no_permitido_rechazado(client):
    """LOAD-007: country_code fuera de ARG/CHL/URY -> 422 con detalle por fila."""
    content = make_csv(build_rows(country_code="BRA"))

    response = upload(client, "bad_country.csv", content)

    assert response.status_code == 422
    error = response.json()["detail"]["rows"][0]
    assert error["field"] == "country_code"
    assert error["value"] == "BRA"
    assert "ARG" in error["cause"]


def test_load_008_occupation_id_inexistente_en_cuarentena(client):
    """LOAD-008: occupation_id fuera del catalogo -> cuarentena UNMAPPED_CATALOG."""
    content = make_csv(build_rows(occupation_id="OCUP_99"))

    response = upload(client, "bad_occupation.csv", content)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok_with_warnings"
    assert body["rows_valid"] == 0
    assert body["rows_quarantined"] == 1
    cuarentena = body["quarantine"][0]
    assert cuarentena["flag"] == "UNMAPPED_CATALOG"
    assert "OCUP_99" in cuarentena["cause"]


def test_load_008_occupation_id_formato_invalido_rechazado(client):
    """LOAD-008: occupation_id con formato invalido -> 422 (no llega a cuarentena)."""
    content = make_csv(build_rows(occupation_id="OCC-1"))

    response = upload(client, "bad_occupation_format.csv", content)

    assert response.status_code == 422
    error = response.json()["detail"]["rows"][0]
    assert error["field"] == "occupation_id"
    assert "OCUP_XX" in error["cause"]


def test_load_008_archivo_con_todas_las_ocupaciones_aceptado(client):
    """LOAD-008 (positivo): las 20 ocupaciones del catalogo son validas."""
    filas = []
    for numero in range(1, 21):
        ocupacion = f"OCUP_{numero:02d}"
        sector = SECTOR_POR_OCUPACION[ocupacion]
        filas.append(build_rows(occupation_id=ocupacion, sector_id=sector)[0])
    content = make_csv(filas)

    response = upload(client, "catalogo_completo.csv", content)

    assert response.status_code == 200
    body = response.json()
    assert body["rows_count"] == 20
    assert body["rows_valid"] == 20
    assert body["rows_quarantined"] == 0
    assert body["warnings"] == []


def test_load_006_duplicados_identicos_se_colapsan(client):
    """LOAD-006: filas identicas en el mismo lote -> se conserva una sola."""
    content = make_csv(build_rows() + build_rows())

    response = upload(client, "duplicados.csv", content)

    assert response.status_code == 200
    body = response.json()
    assert body["rows_count"] == 2
    assert body["rows_valid"] == 1
    assert body["duplicates_removed"] == 1
    assert body["warnings"] == []


def test_load_006_duplicados_con_valor_distinto_gana_el_ultimo(client):
    """LOAD-006: misma clave con valores distintos -> gana el ultimo + warning."""
    content = make_csv(build_rows(metric_value="1000") + build_rows(metric_value="2000"))

    response = upload(client, "duplicados_actualizados.csv", content)

    assert response.status_code == 200
    body = response.json()
    assert body["rows_valid"] == 1
    assert body["duplicates_removed"] == 1
    assert body["status"] == "ok_with_warnings"
    assert "sobreescrito por actualización en la misma carga" in body["warnings"][0]


def test_load_011_deduplicacion_por_clave_natural(client, output_dirs):
    """LOAD-011: la clave natural no colapsa ocupaciones distintas del mismo sector."""
    content = make_csv(
        build_rows(occupation_id="OCUP_01")
        + build_rows(occupation_id="OCUP_02")
        + build_rows(occupation_id="OCUP_01")
    )

    response = upload(client, "misma_clave.csv", content)

    assert response.status_code == 200
    body = response.json()
    assert body["rows_valid"] == 2
    assert body["duplicates_removed"] == 1


def test_load_010_transformacion_al_esquema_comun(client, output_dirs):
    """LOAD-010: las 8 columnas de entrada se transforman al esquema comun de Data."""
    content = make_csv(
        [
            {
                "country_code": "arg",
                "sector_id": "TEC",
                "occupation_id": "OCUP_01",
                "metric_name": "Tasa de Desocupación Total (% Fuerza de Trabajo)",
                "metric_value": "7.744",
                "period": "2023-Q2",
                "source_name": "INDEC-EPH",
                "data_type": "percentage",
            }
        ]
    )

    response = upload(client, "transformacion.csv", content)

    assert response.status_code == 200
    body = response.json()
    assert body["rows_valid"] == 1

    salida = Path(body["output_path"])
    assert salida.exists()
    with salida.open(encoding="utf-8-sig") as archivo:
        filas = list(csv.DictReader(archivo))

    fila = filas[0]
    assert fila["pais_codigo_iso3"] == "ARG"
    assert fila["pais_nombre"] == "Argentina"
    assert fila["dimension"] == "Tecnología"
    assert fila["indicador_nombre"] == "Tasa de Desocupación Total"
    assert fila["anio"] == "2023"
    assert fila["periodo"] == "Trimestre 2"
    assert fila["valor"] == "7.74"
    assert fila["unidad_medida"] == "Porcentaje (%)"
    assert fila["fuente_oficial"] == "INDEC-EPH"
    assert fila["fecha_extraccion"].endswith("+00:00")
    assert fila["occupation_id"] == "OCUP_01"
    assert fila["is_projection"] == "False"


def test_load_010_periodos_admitidos(client):
    """LOAD-010: se admiten los tres formatos de periodo (anual, trimestre, mes)."""
    filas = []
    for periodo in ("2023", "2023-Q2", "2023-06"):
        filas.append(build_rows(period=periodo)[0])
    content = make_csv(filas)

    response = upload(client, "periodos.csv", content)

    assert response.status_code == 200
    assert response.json()["rows_valid"] == 3


def test_load_012_cuarentena_por_rango(client, output_dirs):
    """LOAD-012: porcentaje fuera de 0..100 -> cuarentena OUTLIER_RANGE."""
    content = make_csv(build_rows(metric_value="150", data_type="percentage"))

    response = upload(client, "outlier.csv", content)

    assert response.status_code == 200
    body = response.json()
    assert body["rows_valid"] == 0
    assert body["rows_quarantined"] == 1
    cuarentena = body["quarantine"][0]
    assert cuarentena["flag"] == "OUTLIER_RANGE"
    assert "porcentaje" in cuarentena["cause"]


def test_load_012_cuarentena_se_persiste(client, output_dirs):
    """LOAD-012: las filas en cuarentena quedan en un JSONL con su flag."""
    content = make_csv(build_rows(occupation_id="OCUP_99"))

    response = upload(client, "cuarentena.csv", content)

    assert response.status_code == 200
    body = response.json()
    ruta = Path(body["quarantine_path"])
    assert ruta.exists()
    registros = [json.loads(linea) for linea in ruta.read_text(encoding="utf-8").splitlines()]
    assert registros[0]["flag"] == "UNMAPPED_CATALOG"
    assert registros[0]["row"] == 2


def test_load_009_cobertura_135_registros(client, output_dirs):
    """LOAD-009: 3 países × 45 registros -> 135 filas válidas sin pérdidas."""
    filas = build_golden_rows()
    assert len(filas) == 135
    content = make_csv(filas)

    response = upload(client, "golden.csv", content)

    assert response.status_code == 200
    body = response.json()
    assert body["rows_count"] == 135
    assert body["rows_valid"] == 135
    assert body["rows_quarantined"] == 0
    assert body["duplicates_removed"] == 0

    salida = Path(body["output_path"])
    with salida.open(encoding="utf-8-sig") as archivo:
        filas_normalizadas = list(csv.DictReader(archivo))
    conteo = {pais: 0 for pais in ("ARG", "CHL", "URY")}
    for fila in filas_normalizadas:
        conteo[fila["pais_codigo_iso3"]] += 1
    assert conteo == {"ARG": 45, "CHL": 45, "URY": 45}


def test_carga_de_esquema_comun_aceptada(client):
    """Extra: un CSV ya normalizado (esquema común de Data) entra por la misma vía."""
    content = make_common_csv(
        [
            {
                "pais_codigo_iso3": "ARG",
                "pais_nombre": "Argentina",
                "dimension": "Economía",
                "indicador_nombre": "Tasa de Desocupación Total",
                "anio": "2023",
                "periodo": "Anual",
                "valor": "7.7",
                "unidad_medida": "Porcentaje (%)",
                "fuente_oficial": "ILOSTAT - OIT",
                "fecha_extraccion": "2026-10-21",
            }
        ]
    )

    response = upload(client, "comun.csv", content)

    assert response.status_code == 200
    body = response.json()
    assert body["input_schema"] == "common"
    assert body["rows_valid"] == 1
    assert body["rows_quarantined"] == 0


def test_rechazo_422_no_persiste_nada(client, output_dirs):
    """Extra: un rechazo de entrada (422) no deja archivos en disco."""
    processed, quarantine = output_dirs
    content = make_csv(build_rows(metric_value="no_es_un_numero"))

    response = upload(client, "rechazado.csv", content)

    assert response.status_code == 422
    assert not processed.exists()
    assert not quarantine.exists()


def test_persist_false_no_escribe_archivos(client, output_dirs):
    """Extra: ?persist=false devuelve el reporte sin tocar el disco."""
    processed, quarantine = output_dirs
    content = make_csv(build_rows())

    response = client.post(
        "/api/v1/datasets/upload?persist=false",
        files={"file": ("sin_persistir.csv", content, "text/csv")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["rows_valid"] == 1
    assert body["output_path"] is None
    assert not processed.exists()
    assert not quarantine.exists()


# ---------------------------------------------------------------------------
# Snapshot automático post-carga (#65)
# ---------------------------------------------------------------------------
def test_upload_programa_snapshot_si_hay_db(client, monkeypatch):
    """Con DB configurada, la carga encola el snapshot sin bloquear la respuesta."""
    from app.api.v1.endpoints import datasets as datasets_endpoint
    from app.core.config import get_settings

    llamadas: list[bool] = []

    async def _snapshot():
        llamadas.append(True)

    monkeypatch.setenv("AUTO_SNAPSHOT_AFTER_UPLOAD", "true")
    get_settings.cache_clear()
    monkeypatch.setattr(datasets_endpoint.database, "is_db_configured", lambda: True)
    monkeypatch.setattr(
        datasets_endpoint.snapshot_service,
        "generar_snapshot_seguro",
        _snapshot,
    )

    response = upload(client, "con_snapshot.csv", make_csv(build_rows()))

    assert response.status_code == 200
    assert response.json()["snapshot_programado"] is True
    assert llamadas == [True]


def test_upload_no_programa_snapshot_sin_db(client, monkeypatch):
    """Sin DB la carga sigue funcionando y no intenta generar snapshots."""
    from app.api.v1.endpoints import datasets as datasets_endpoint
    from app.core.config import get_settings

    llamadas: list[bool] = []

    async def _snapshot():
        llamadas.append(True)

    monkeypatch.setenv("AUTO_SNAPSHOT_AFTER_UPLOAD", "true")
    get_settings.cache_clear()
    monkeypatch.setattr(datasets_endpoint.database, "is_db_configured", lambda: False)
    monkeypatch.setattr(
        datasets_endpoint.snapshot_service,
        "generar_snapshot_seguro",
        _snapshot,
    )

    response = upload(client, "sin_db.csv", make_csv(build_rows()))

    assert response.status_code == 200
    assert response.json()["snapshot_programado"] is False
    assert llamadas == []


def test_persist_false_no_programa_snapshot(client, monkeypatch):
    """`?persist=false` no escribe datos ni tiene sentido que actualice snapshots."""
    from app.api.v1.endpoints import datasets as datasets_endpoint
    from app.core.config import get_settings

    llamadas: list[bool] = []

    async def _snapshot():
        llamadas.append(True)

    monkeypatch.setenv("AUTO_SNAPSHOT_AFTER_UPLOAD", "true")
    get_settings.cache_clear()
    monkeypatch.setattr(datasets_endpoint.database, "is_db_configured", lambda: True)
    monkeypatch.setattr(
        datasets_endpoint.snapshot_service,
        "generar_snapshot_seguro",
        _snapshot,
    )

    response = client.post(
        "/api/v1/datasets/upload?persist=false",
        files={"file": ("sin_persistir.csv", make_csv(build_rows()), "text/csv")},
    )

    assert response.status_code == 200
    assert response.json()["snapshot_programado"] is False
    assert llamadas == []
