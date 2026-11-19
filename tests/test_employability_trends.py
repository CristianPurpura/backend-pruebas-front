"""Tests de la clasificación de tendencias (issue #64).

Verifica que `/employability/trends` reutilice `clasificar_tendencia` con la
misma banda muerta (`epsilon`) que publica `GET /employability`.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.v1.endpoints import employability
from app.main import app
from app.services.calculators.employability import VARIABLES_IDELR
from app.services.normalization.store import write_normalized


def panel_sintetico(creciente: bool = True) -> list[dict]:
    """Panel macro de 2 años; con `creciente=False` el índice no cambia."""
    base = {
        "Variación Anual del PIB Real": 2.0,
        "Índice de Salario Real": 95.0,
        "Tasa de Ocupación": 55.0,
        "Tasa de Finalización de Educación Secundaria": 70.0,
        "Tasa de Desocupación Total": 7.0,
    }
    mejorado = {
        "Variación Anual del PIB Real": 5.0,
        "Índice de Salario Real": 110.0,
        "Tasa de Ocupación": 60.0,
        "Tasa de Finalización de Educación Secundaria": 80.0,
        "Tasa de Desocupación Total": 4.0,
    }
    valores_2023 = mejorado if creciente else base

    filas: list[dict] = []
    for pais in ("ARG", "CHL", "URY"):
        for anio, valores in ((2022, base), (2023, valores_2023)):
            for indicador, valor in valores.items():
                filas.append(
                    {
                        "pais_codigo_iso3": pais,
                        "pais_nombre": pais,
                        "dimension": VARIABLES_IDELR[indicador]["dimension"],
                        "indicador_nombre": indicador,
                        "anio": anio,
                        "periodo": "Anual",
                        "valor": valor,
                        "unidad_medida": "Porcentaje (%)",
                        "fuente_oficial": "TEST",
                        "fecha_extraccion": "2026-11-18",
                    }
                )
    return filas


class SesionFalsa:
    def __init__(self, filas):
        self._filas = filas

    async def scalars(self, consulta):  # noqa: ANN001
        return self._filas


@pytest.fixture()
def client_con_snapshots():
    filas = [
        SimpleNamespace(
            tipo="ICOL",
            pais="URY",
            anio=2024,
            ocupacion_id="OCUP_01",
            valor=80.0,
            categoria="Alta Oportunidad",
            cobertura_pct=None,
            metodologia_version="test-v1",
            calculado_en=datetime(2026, 11, 4, tzinfo=timezone.utc),
            payload={},
        ),
        SimpleNamespace(
            tipo="ICOL",
            pais="URY",
            anio=2024,
            ocupacion_id="OCUP_01",
            valor=92.0,
            categoria="Oportunidad Excepcional",
            cobertura_pct=None,
            metodologia_version="test-v1",
            calculado_en=datetime(2026, 11, 4, tzinfo=timezone.utc) + timedelta(days=1),
            payload={},
        ),
    ]

    async def _db():
        yield SesionFalsa(filas)

    app.dependency_overrides[employability.get_db_opcional] = _db
    try:
        with TestClient(app) as cliente:
            yield cliente
    finally:
        app.dependency_overrides.pop(employability.get_db_opcional, None)


def test_trends_idelr_detecta_crecimiento(client, output_dirs):
    write_normalized(panel_sintetico(creciente=True), "panel.csv")

    response = client.get("/api/v1/employability/trends")

    assert response.status_code == 200
    cuerpo = response.json()
    assert cuerpo["tipo"] == "IDELR"
    assert cuerpo["epsilon_pct"] == 1.0
    assert cuerpo["total"] == 3  # un registro por país
    assert all(fila["tendencia"] == "CRECIMIENTO" for fila in cuerpo["tendencias"])
    assert all(fila["icono"] == "🟢" for fila in cuerpo["tendencias"])
    assert all(fila["periodo_actual"] == "2023" for fila in cuerpo["tendencias"])
    assert all(fila["periodo_previo"] == "2022" for fila in cuerpo["tendencias"])


def test_trends_usa_banda_muerta_para_estabilidad(client, output_dirs):
    write_normalized(panel_sintetico(creciente=False), "panel.csv")

    response = client.get("/api/v1/employability/trends")

    assert response.status_code == 200
    cuerpo = response.json()
    assert all(fila["tendencia"] == "ESTABILIDAD" for fila in cuerpo["tendencias"])
    assert all(fila["variacion_pct"] == 0.0 for fila in cuerpo["tendencias"])


def test_trends_epsilon_es_configurable(client, output_dirs):
    write_normalized(panel_sintetico(creciente=True), "panel.csv")

    response = client.get("/api/v1/employability/trends?epsilon=100")

    assert response.status_code == 200
    cuerpo = response.json()
    assert cuerpo["epsilon_pct"] == 100.0
    assert all(fila["tendencia"] == "ESTABILIDAD" for fila in cuerpo["tendencias"])


def test_trends_sin_punto_previo_es_base(client, output_dirs):
    solo_2022 = [fila for fila in panel_sintetico() if fila["anio"] == 2022]
    write_normalized(solo_2022, "panel.csv")

    response = client.get("/api/v1/employability/trends")

    assert response.status_code == 200
    cuerpo = response.json()
    assert cuerpo["total"] == 3
    assert all(fila["tendencia"] == "BASE" for fila in cuerpo["tendencias"])
    assert all(fila["valor_previo"] is None for fila in cuerpo["tendencias"])


def test_epsilon_de_trends_coincide_con_la_metodologia(client, output_dirs):
    write_normalized(panel_sintetico(creciente=True), "panel.csv")

    empleabilidad = client.get("/api/v1/employability").json()
    tendencias = client.get("/api/v1/employability/trends").json()

    assert tendencias["epsilon_pct"] == empleabilidad["metodologia"]["epsilon_pct"]


def test_trends_icol_desde_snapshots(client_con_snapshots):
    response = client_con_snapshots.get(
        "/api/v1/employability/trends?tipo=ICOL&pais=URY&ocupacion=OCUP_01"
    )

    assert response.status_code == 200
    cuerpo = response.json()
    assert cuerpo["fuente"] == "database"
    assert cuerpo["total"] == 1
    entrada = cuerpo["tendencias"][0]
    assert entrada["periodo_previo"] == "2026-11-04"
    assert entrada["periodo_actual"] == "2026-11-05"
    assert entrada["valor_previo"] == 80.0
    assert entrada["valor_actual"] == 92.0
    assert entrada["variacion_pct"] == 15.0
    assert entrada["tendencia"] == "CRECIMIENTO"


def test_trends_rechaza_ocupacion_con_idelr(client):
    response = client.get("/api/v1/employability/trends?tipo=IDELR&ocupacion=OCUP_01")

    assert response.status_code == 400
    assert "solo aplica a tipo=ICOL" in response.json()["detail"]
