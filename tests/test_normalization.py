"""Tests unitarios del pipeline de normalización (LOAD-006..LOAD-012).

Cubre el mapeo al esquema común de Data, la homologación de indicadores, la
clave natural de deduplicación, la cuarentena y el rechazo sincrónico.
"""

import io
from collections import Counter

import httpx
import pandas as pd
import pytest

from app.services.normalization import (
    COMMON_COLUMNS,
    DEDUPE_KEY,
    NORMALIZED_COLUMNS,
    DatasetRowRejectionError,
    normalize_common_rows,
    normalize_manual_rows,
)
from tests.conftest import build_rows

# El fixture de la API de Data vive en el módulo de la matriz QA; se importa
# para reutilizarlo (levanta la API de DataAnalyst si está disponible).
from tests.test_data_api_matrix import data_api  # noqa: F401


def fila(**overrides: str) -> dict[str, str]:
    return {**build_rows()[0], **overrides}


def test_mapeo_al_esquema_comun():
    """LOAD-010: las 8 columnas de entrada se mapean a las 10 columnas comunes."""
    resultado = normalize_manual_rows([fila()])

    assert resultado.rows_valid == 1
    fila_normalizada = resultado.valid[0]
    assert list(fila_normalizada) == NORMALIZED_COLUMNS
    assert fila_normalizada["pais_codigo_iso3"] == "ARG"
    assert fila_normalizada["pais_nombre"] == "Argentina"
    assert fila_normalizada["dimension"] == "Tecnología"
    assert fila_normalizada["anio"] == 2025
    assert fila_normalizada["periodo"] == "Anual"
    assert fila_normalizada["valor"] == 1500.0
    assert fila_normalizada["unidad_medida"] == "Unidades (conteo)"
    assert fila_normalizada["fuente_oficial"] == "INDEC-EPH"
    assert fila_normalizada["occupation_id"] == "OCUP_01"
    assert fila_normalizada["is_projection"] is False


def test_homologacion_de_indicadores():
    """LOAD-010: el nombre de la métrica se homologa contra el catálogo de Data."""
    resultado = normalize_manual_rows(
        [fila(metric_name="Tasa de Ocupación / Empleo")]
    )

    assert resultado.valid[0]["indicador_nombre"] == "Tasa de Ocupación"


def test_unidades_canonicas():
    """LOAD-010: data_type se traduce a la etiqueta canónica de unidad."""
    for data_type, esperado in (
        ("percentage", "Porcentaje (%)"),
        ("currency", "Moneda (USD)"),
        ("count", "Unidades (conteo)"),
    ):
        resultado = normalize_manual_rows([fila(data_type=data_type, metric_value="50")])
        assert resultado.rows_valid == 1
        assert resultado.valid[0]["unidad_medida"] == esperado


def test_is_projection_opcional():
    """El campo opcional is_projection se interpreta como booleano."""
    resultado = normalize_manual_rows([fila(is_projection="true")])

    assert resultado.valid[0]["is_projection"] is True


def test_clave_natural_incluye_occupation_id():
    """LOAD-011: la clave de deduplicación incluye occupation_id."""
    assert "occupation_id" in DEDUPE_KEY
    assert len(DEDUPE_KEY) == 8


def test_deduplicacion_conserva_el_ultimo_registro():
    """LOAD-006 / LOAD-011: en la misma clave gana el último registro del lote."""
    resultado = normalize_manual_rows(
        [fila(metric_value="1000"), fila(metric_value="2000")]
    )

    assert resultado.rows_valid == 1
    assert resultado.duplicates_removed == 1
    assert resultado.valid[0]["valor"] == 2000.0
    assert "sobreescrito" in resultado.warnings[0]


def test_deduplicacion_de_registros_identificados():
    """LOAD-006: filas idénticas se colapsan sin aviso de sobrescritura."""
    resultado = normalize_manual_rows([fila(), fila()])

    assert resultado.rows_valid == 1
    assert resultado.duplicates_removed == 1
    assert resultado.warnings == []


def test_deduplicacion_no_colapsa_ocupaciones_distintas():
    """LOAD-011: dos ocupaciones del mismo sector no se colapsan entre sí."""
    resultado = normalize_manual_rows(
        [fila(occupation_id="OCUP_01"), fila(occupation_id="OCUP_02")]
    )

    assert resultado.rows_valid == 2
    assert resultado.duplicates_removed == 0


def test_cuarentena_por_catalogo():
    """LOAD-012: sector u ocupación fuera del catálogo -> cuarentena."""
    resultado = normalize_manual_rows([fila(sector_id="XXX")])

    assert resultado.rows_valid == 0
    assert resultado.rows_quarantined == 1
    assert resultado.quarantine[0].flag == "UNMAPPED_CATALOG"
    assert "XXX" in resultado.quarantine[0].cause


def test_cuarentena_por_rango():
    """LOAD-012: porcentaje fuera de rango o indicador que no admite negativos."""
    resultado = normalize_manual_rows(
        [
            fila(metric_value="150", data_type="percentage"),
            fila(metric_name="Tasa de Desocupación Total", metric_value="-1"),
        ]
    )

    assert resultado.rows_valid == 0
    assert resultado.rows_quarantined == 2
    assert {registro.flag for registro in resultado.quarantine} == {"OUTLIER_RANGE"}


def test_rechazo_sincronico_agrega_todos_los_errores():
    """LOAD-012: el rechazo de entrada lista el detalle de cada fila inválida."""
    with pytest.raises(DatasetRowRejectionError) as excinfo:
        normalize_manual_rows(
            [
                fila(country_code="BRA"),
                fila(metric_value="n/d"),
                fila(period="2023-13"),
            ]
        )

    error = excinfo.value
    assert error.status_code == 422
    assert len(error.rows) == 3
    campos = {row.field for row in error.rows}
    assert campos == {"country_code", "metric_value", "period"}


def test_normalizacion_de_esquema_comun():
    """El esquema común de Data entra sin transformaciones ni pérdidas."""
    resultado = normalize_common_rows(
        [
            {
                "pais_codigo_iso3": "ARG",
                "pais_nombre": "Argentina",
                "dimension": "Economía",
                "indicador_nombre": "Inflación Anual (IPC acumulado)",
                "anio": "2021",
                "periodo": "Anual",
                "valor": "50.9",
                "unidad_medida": "Porcentaje (%)",
                "fuente_oficial": "CEPALSTAT",
                "fecha_extraccion": "2026-10-21",
            }
        ]
    )

    assert resultado.rows_valid == 1
    assert resultado.quarantine == []
    fila_normalizada = resultado.valid[0]
    assert fila_normalizada["valor"] == 50.9
    assert fila_normalizada["pais_nombre"] == "Argentina"
    assert fila_normalizada["fecha_extraccion"] == "2026-10-21"


def test_golden_dataset_de_data_se_ingiere_completo(data_api):
    """LOAD-009: el golden dataset regional de Data entra sin perder registros."""
    response = httpx.get(f"{data_api}/api/v1/consolidado/descargar", timeout=60.0)
    assert response.status_code == 200

    df = pd.read_csv(io.BytesIO(response.content), encoding="utf-8-sig")
    resultado = normalize_common_rows(df.to_dict(orient="records"))

    assert resultado.rows_read == 135
    assert resultado.rows_valid == 135
    assert resultado.rows_quarantined == 0

    conteo = Counter(fila["pais_codigo_iso3"] for fila in resultado.valid)
    assert conteo == {"ARG": 45, "CHL": 45, "URY": 45}
    assert set(COMMON_COLUMNS).issubset(resultado.valid[0])
