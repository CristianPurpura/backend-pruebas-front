"""Tests de contrato y paridad de los agregados de brechas.

Blindan los números que consume el dashboard:

* `CCE = O / D` y `déficit = D − O` en el snapshot de referencia;
* el TGS recalculado coincide con el que publica Data;
* los totales de `/gaps/summary` son la suma de sus filas;
* el CCE agregado es ponderado por demanda, no un promedio simple;
* el mock de `docs/mocks/gaps_summary.json` no se desactualiza.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.datascience import DataSourceMeta, GapItem
from app.services.datascience import client as data_client
from app.services.datascience import mapper
from app.services.datascience.metrics import calcular_tgs
from app.services.datascience.summary import construir_resumen

RAIZ = Path(__file__).resolve().parents[1]
REFERENCIA_COMPARATIVA = RAIZ / "data" / "reference" / "comparativa.json"
REFERENCIA_BRECHAS = RAIZ / "data" / "reference" / "brechas.json"
MOCK_RESUMEN = RAIZ / "docs" / "mocks" / "gaps_summary.json"


def _comparativa() -> list[dict]:
    return json.loads(REFERENCIA_COMPARATIVA.read_text(encoding="utf-8"))[
        "comparativa_educativo_laboral"
    ]


def _items():
    return [mapper.mapear_comparativa(fila) for fila in _comparativa()]


# ---------------------------------------------------------------------------
# 1. Invariantes de la referencia
# ---------------------------------------------------------------------------
def test_invariantes_de_oferta_y_demanda():
    """En las 15 filas se cumple `CCE = O/D` y `déficit = D − O`."""
    filas = _comparativa()

    assert len(filas) == 15
    for fila in filas:
        demanda = fila["demanda_anual_puestos_nuevos"]
        egresados = fila["egresados_anuales_estimados"]

        assert fila["brecha_anual_puestos_deficit"] == pytest.approx(
            demanda - egresados, abs=0.01
        )
        assert fila["coeficiente_cobertura_educativa_cce"] == pytest.approx(
            egresados / demanda, abs=0.001
        )


def test_tgs_calculado_coincide_con_la_referencia():
    """El TGS local reproduce los 60 valores que publica Data."""
    filas = json.loads(REFERENCIA_BRECHAS.read_text(encoding="utf-8"))[
        "brechas_y_habilidades"
    ]

    assert len(filas) == 60
    for fila in filas:
        calculado = calcular_tgs(
            fila["score_demanda_mercado"],
            fila["score_crecimiento_estimado"],
            fila["coeficiente_cobertura_educativa_cce"],
            fila["pais_codigo_iso3"],
        )
        assert calculado == pytest.approx(fila["score_brecha_talento_100"], abs=0.01)


def test_crecimiento_matricula_es_numerico():
    """El parser de BE-1 deja de perder el porcentaje que envía Data."""
    items = _items()

    assert all(item.crecimiento_matricula_pct is not None for item in items)
    assert next(i for i in items if i.pais == "ARG" and i.sector == "Energía").crecimiento_matricula_pct == 9.1


# ---------------------------------------------------------------------------
# 2. Agregados
# ---------------------------------------------------------------------------
def test_los_totales_son_la_suma_de_las_filas():
    """Los agregados se construyen sobre las mismas filas que `/gaps`."""
    items = _items()
    resumen = construir_resumen(items, DataSourceMeta(fuente="reference"))

    demanda = sum(float(item.demanda_anual) for item in items)
    egresados = sum(float(item.egresados_anuales) for item in items)
    deficit = sum(
        max(0.0, float(item.demanda_anual) - float(item.egresados_anuales))
        for item in items
    )

    assert resumen.totales.demanda_anual == pytest.approx(demanda)
    assert resumen.totales.egresados_anuales == pytest.approx(egresados)
    assert resumen.totales.deficit_bruto == pytest.approx(deficit)
    assert resumen.totales.cce_ponderado == round(egresados / demanda, 3)


def test_el_cce_agregado_no_es_un_promedio_simple():
    """El CCE ponderado por demanda difiere del promedio de los 15 CCE."""
    items = _items()
    resumen = construir_resumen(items, DataSourceMeta(fuente="reference"))

    simple = sum(float(item.cce) for item in items if item.cce is not None) / len(items)

    assert resumen.totales.cce_ponderado is not None
    assert abs(resumen.totales.cce_ponderado - simple) > 0.01


def test_el_resumen_no_divide_por_cero():
    """Una demanda nula no rompe los agregados."""
    items = [
        GapItem(pais="ARG", sector="X", demanda_anual=0, egresados_anuales=100, cce=None)
    ]

    resumen = construir_resumen(items, DataSourceMeta(fuente="reference"))

    assert resumen.totales.cce_ponderado is None
    assert resumen.totales.brecha_cobertura_pct is None
    assert resumen.totales.superavit_total == 100


# ---------------------------------------------------------------------------
# 3. Mock del contrato
# ---------------------------------------------------------------------------
def test_el_mock_coincide_con_la_referencia():
    """`docs/mocks/gaps_summary.json` se puede regenerar desde la referencia."""
    payload = json.loads(REFERENCIA_COMPARATIVA.read_text(encoding="utf-8"))
    esperado = construir_resumen(
        [mapper.mapear_comparativa(fila) for fila in payload["comparativa_educativo_laboral"]],
        DataSourceMeta(
            fuente="reference",
            actualizado=str(payload.get("_actualizado") or ""),
        ),
        {"pais": None, "sector": None},
    ).model_dump(mode="json")

    assert MOCK_RESUMEN.exists()
    assert json.loads(MOCK_RESUMEN.read_text(encoding="utf-8")) == esperado


# ---------------------------------------------------------------------------
# 4. Endpoint
# ---------------------------------------------------------------------------
@pytest.fixture()
def referencia_mock(monkeypatch):
    """Sirve el snapshot de referencia sin salir a la red."""
    payload = json.loads(REFERENCIA_COMPARATIVA.read_text(encoding="utf-8"))

    async def _consultar(ruta, params=None, client=None):
        return data_client.RespuestaData(
            datos=payload,
            fuente="reference",
            actualizado=str(payload.get("_actualizado") or ""),
        )

    monkeypatch.setattr(data_client, "consultar_data", _consultar)
    return payload


def test_endpoint_summary_filtra_por_sector(referencia_mock):
    response = TestClient(app).get(
        "/api/v1/gaps/summary", params={"sector": "Tecnología"}
    )

    assert response.status_code == 200
    cuerpo = response.json()
    assert cuerpo["total_sectores"] == 3
    assert {fila["sector"] for fila in cuerpo["por_sector"]} == {"Tecnología"}
    assert cuerpo["filtros"]["sector"] == "Tecnología"


@pytest.mark.parametrize("fuente", ["live", "cache", "reference"])
def test_endpoint_summary_propaga_la_fuente(monkeypatch, fuente):
    payload = json.loads(REFERENCIA_COMPARATIVA.read_text(encoding="utf-8"))

    async def _consultar(ruta, params=None, client=None):
        return data_client.RespuestaData(datos=payload, fuente=fuente)

    monkeypatch.setattr(data_client, "consultar_data", _consultar)

    response = TestClient(app).get("/api/v1/gaps/summary")

    assert response.status_code == 200
    assert response.json()["meta"]["fuente"] == fuente


def test_endpoint_summary_sin_fuentes_responde_503(monkeypatch):
    async def _sin_datos(ruta, params=None, client=None):
        return None

    monkeypatch.setattr(data_client, "consultar_data", _sin_datos)

    response = TestClient(app).get("/api/v1/gaps/summary")

    assert response.status_code == 503
    assert "Data" in response.json()["detail"]
