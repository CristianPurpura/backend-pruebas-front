"""Tests de contrato de los mocks de series y tendencias.

Blindan la forma que consume el Frontend: si cambia un schema, el mock deja
de validar y el test falla antes de romper la integración.
"""

import json
from pathlib import Path

from app.schemas.indicator_result import LatestResponse
from app.schemas.indicator_series import SeriesResponse, TrendsResponse

RAIZ = Path(__file__).resolve().parents[1]
MOCKS = RAIZ / "docs" / "mocks"


def _leer(nombre: str) -> dict:
    return json.loads((MOCKS / nombre).read_text(encoding="utf-8"))


def test_mock_series_idelr_valida_contra_el_schema():
    respuesta = SeriesResponse.model_validate(_leer("series_idelr.json"))

    assert respuesta.tipo == "IDELR"
    assert respuesta.total == len(respuesta.puntos)
    assert respuesta.fuente in {"processed", "database", "live", "fallback"}
    assert all(punto.periodo == str(punto.anio) for punto in respuesta.puntos)


def test_mock_series_icol_valida_contra_el_schema():
    respuesta = SeriesResponse.model_validate(_leer("series_icol.json"))

    assert respuesta.tipo == "ICOL"
    assert respuesta.total == len(respuesta.puntos)
    assert respuesta.fuente == "database"
    assert all(punto.ocupacion_id for punto in respuesta.puntos)
    assert all(punto.fecha_calculo is not None for punto in respuesta.puntos)


def test_mock_trends_valida_contra_el_schema():
    respuesta = TrendsResponse.model_validate(_leer("trends.json"))

    assert respuesta.total == len(respuesta.tendencias)
    assert respuesta.epsilon_pct == 1.0
    for tendencia in respuesta.tendencias:
        assert tendencia.tendencia in {"BASE", "CRECIMIENTO", "ESTABILIDAD", "DISMINUCION"}
        assert tendencia.periodo_actual


def test_mock_latest_valida_contra_el_schema_y_no_expone_payload():
    respuesta = LatestResponse.model_validate(_leer("latest.json"))

    assert respuesta.total == len(respuesta.resultados)
    assert respuesta.fecha_snapshot is not None
    crudo = _leer("latest.json")
    assert all("payload" not in fila for fila in crudo["resultados"])
