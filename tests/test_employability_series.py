"""Tests de las series históricas chart-ready (issue #64).

Cubre `GET /employability/series` en sus dos fuentes:

* IDELR calculado desde los datasets normalizados (`data/processed/`).
* ICOL leído de snapshots persistidos, con degradación al cálculo en vivo
  cuando no hay base de datos ni histórico.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.v1.endpoints import employability
from app.main import app
from app.services.calculators.employability import VARIABLES_IDELR
from app.services.normalization.store import write_normalized


def panel_sintetico() -> list[dict]:
    """Panel macro: 3 países × 2 años × 5 indicadores."""
    valores = {
        "Variación Anual del PIB Real": 2.0,
        "Índice de Salario Real": 95.0,
        "Tasa de Ocupación": 55.0,
        "Tasa de Finalización de Educación Secundaria": 70.0,
        "Tasa de Desocupación Total": 7.0,
    }
    filas: list[dict] = []
    for pais in ("ARG", "CHL", "URY"):
        for anio in (2022, 2023):
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


def fila_snapshot(
    *,
    ocupacion: str = "OCUP_01",
    valor: float = 80.0,
    fecha: datetime | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        tipo="ICOL",
        pais="URY",
        anio=2024,
        ocupacion_id=ocupacion,
        valor=valor,
        categoria="Alta Oportunidad",
        cobertura_pct=None,
        metodologia_version="test-v1",
        calculado_en=fecha or datetime(2026, 11, 4, tzinfo=timezone.utc),
        payload={"ocupacion_id": ocupacion, "indice_oportunidad_icol": valor},
    )


class SesionFalsa:
    """Sesión mínima: devuelve filas ya armadas para `results_store`."""

    def __init__(self, filas: list[SimpleNamespace]) -> None:
        self._filas = filas

    async def scalars(self, consulta):  # noqa: ANN001 - firma de SQLAlchemy
        return self._filas


@pytest.fixture()
def client_con_snapshots():
    """Cliente con una sesión falsa que devuelve dos snapshots ICOL."""
    filas = [
        fila_snapshot(fecha=datetime(2026, 11, 4, tzinfo=timezone.utc), valor=80.0),
        fila_snapshot(
            fecha=datetime(2026, 11, 4, tzinfo=timezone.utc) + timedelta(days=1),
            valor=90.0,
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


@pytest.fixture()
def client_sin_db():
    """Cliente sin base de datos: fuerza la degradación a cálculo en vivo."""

    async def _db():
        yield None

    app.dependency_overrides[employability.get_db_opcional] = _db
    try:
        with TestClient(app) as cliente:
            yield cliente
    finally:
        app.dependency_overrides.pop(employability.get_db_opcional, None)


# ---------------------------------------------------------------------------
# IDELR
# ---------------------------------------------------------------------------
def test_series_idelr_desde_datasets(client, output_dirs):
    write_normalized(panel_sintetico(), "panel.csv")

    response = client.get("/api/v1/employability/series")

    assert response.status_code == 200
    cuerpo = response.json()
    assert cuerpo["tipo"] == "IDELR"
    assert cuerpo["fuente"] == "processed"
    assert cuerpo["total"] == 6
    assert len(cuerpo["puntos"]) == 6
    primer_punto = cuerpo["puntos"][0]
    assert primer_punto["pais"] == "ARG"
    assert primer_punto["periodo"] in {"2022", "2023"}
    assert primer_punto["anio"] == int(primer_punto["periodo"])
    assert primer_punto["fecha_calculo"] is None
    assert primer_punto["tendencia"] in {"BASE", "CRECIMIENTO", "ESTABILIDAD", "DISMINUCION"}


def test_series_idelr_filtra_pais_y_anios(client, output_dirs):
    write_normalized(panel_sintetico(), "panel.csv")

    response = client.get(
        "/api/v1/employability/series?tipo=IDELR&pais=ury&anio_desde=2023&anio_hasta=2023"
    )

    assert response.status_code == 200
    cuerpo = response.json()
    assert cuerpo["filtros"]["pais"] == "URY"
    assert cuerpo["total"] == 1
    assert cuerpo["puntos"][0]["pais"] == "URY"
    assert cuerpo["puntos"][0]["anio"] == 2023


def test_series_sin_datasets_devuelve_contrato_vacio(client, output_dirs):
    response = client.get("/api/v1/employability/series")

    assert response.status_code == 200
    cuerpo = response.json()
    assert cuerpo["fuente"] == "fallback"
    assert cuerpo["puntos"] == []
    assert cuerpo["total"] == 0
    assert "Sin datasets" in cuerpo["detalle"]


def test_series_rechaza_tipo_invalido(client):
    response = client.get("/api/v1/employability/series?tipo=XXX")

    assert response.status_code == 400
    assert "IDELR, ICOL" in response.json()["detail"]


def test_series_rechaza_ocupacion_con_idelr(client):
    response = client.get("/api/v1/employability/series?tipo=IDELR&ocupacion=OCUP_01")

    assert response.status_code == 400
    assert "solo aplica a tipo=ICOL" in response.json()["detail"]


def test_series_rechaza_pais_fuera_del_catalogo(client):
    response = client.get("/api/v1/employability/series?pais=BRA")

    assert response.status_code == 400
    assert "fuera del alcance regional" in response.json()["detail"]


def test_series_rechaza_rango_invertido(client):
    response = client.get("/api/v1/employability/series?anio_desde=2024&anio_hasta=2020")

    assert response.status_code == 400
    assert "anio_desde" in response.json()["detail"]


# ---------------------------------------------------------------------------
# ICOL
# ---------------------------------------------------------------------------
def test_series_icol_lee_snapshots(client_con_snapshots):
    response = client_con_snapshots.get("/api/v1/employability/series?tipo=ICOL&pais=URY")

    assert response.status_code == 200
    cuerpo = response.json()
    assert cuerpo["tipo"] == "ICOL"
    assert cuerpo["fuente"] == "database"
    assert cuerpo["total"] == 2
    assert cuerpo["puntos"][0]["periodo"] == "2026-11-04"
    assert cuerpo["puntos"][0]["fecha_calculo"] is not None
    assert cuerpo["puntos"][0]["metodologia_version"] == "test-v1"
    assert cuerpo["puntos"][0]["tendencia"] == "BASE"
    assert cuerpo["puntos"][1]["tendencia"] == "CRECIMIENTO"


def test_series_icol_sin_db_usa_calculo_en_vivo(client_sin_db):
    response = client_sin_db.get("/api/v1/employability/series?tipo=ICOL")

    assert response.status_code == 200
    cuerpo = response.json()
    assert cuerpo["fuente"] == "live"
    assert cuerpo["total"] == 60
    assert all(punto["tendencia"] == "BASE" for punto in cuerpo["puntos"])


def test_series_icol_filtra_ocupacion(client_sin_db):
    response = client_sin_db.get("/api/v1/employability/series?tipo=ICOL&ocupacion=OCUP_02")

    assert response.status_code == 200
    cuerpo = response.json()
    assert cuerpo["total"] == 3  # ARG, CHL y URY
    assert all(punto["ocupacion_id"] == "OCUP_02" for punto in cuerpo["puntos"])


def test_series_respeta_limite(client_sin_db):
    response = client_sin_db.get("/api/v1/employability/series?tipo=ICOL&limite=5")

    assert response.status_code == 200
    assert response.json()["total"] == 5
