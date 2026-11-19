"""Tests de `GET /employability/latest` (issue #65)."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.v1.endpoints import snapshots
from app.main import app


def fila(
    *,
    pais: str = "URY",
    ocupacion: str | None = "OCUP_01",
    valor: float = 80.0,
    fecha: datetime | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        tipo="ICOL",
        pais=pais,
        anio=2024,
        ocupacion_id=ocupacion,
        valor=valor,
        categoria="Alta Oportunidad",
        cobertura_pct=None,
        metodologia_version="test-v1",
        calculado_en=fecha or datetime(2026, 11, 4, tzinfo=timezone.utc),
        payload={"detalle": "no debe exponerse"},
    )


class SesionFalsa:
    def __init__(self, filas):
        self._filas = filas

    async def scalars(self, consulta):  # noqa: ANN001
        return self._filas


@pytest.fixture()
def client_con_filas():
    filas = [
        fila(valor=80.0, fecha=datetime(2026, 11, 4, tzinfo=timezone.utc)),
        fila(
            valor=90.0,
            fecha=datetime(2026, 11, 4, tzinfo=timezone.utc) + timedelta(days=1),
        ),
        fila(pais="ARG", valor=70.0, fecha=datetime(2026, 11, 4, tzinfo=timezone.utc)),
    ]

    async def _db():
        yield SesionFalsa(filas)

    app.dependency_overrides[snapshots.get_db_requerida] = _db
    try:
        with TestClient(app) as cliente:
            yield cliente
    finally:
        app.dependency_overrides.pop(snapshots.get_db_requerida, None)


def test_latest_devuelve_el_mas_reciente_por_combinacion(client_con_filas):
    response = client_con_filas.get("/api/v1/employability/latest?tipo=ICOL")

    assert response.status_code == 200
    cuerpo = response.json()
    assert cuerpo["tipo"] == "ICOL"
    assert cuerpo["total"] == 2
    ury = next(fila for fila in cuerpo["resultados"] if fila["pais"] == "URY")
    assert ury["valor"] == 90.0
    assert cuerpo["fecha_snapshot"] is not None


def test_latest_no_expone_el_payload(client_con_filas):
    response = client_con_filas.get("/api/v1/employability/latest")

    assert response.status_code == 200
    for fila in response.json()["resultados"]:
        assert "payload" not in fila


def test_latest_rechaza_filtros_invalidos(client_con_filas):
    assert client_con_filas.get("/api/v1/employability/latest?tipo=XXX").status_code == 400
    assert client_con_filas.get("/api/v1/employability/latest?pais=BRA").status_code == 400
    assert (
        client_con_filas.get("/api/v1/employability/latest?ocupacion=OCUP_99").status_code
        == 400
    )


def test_latest_sin_base_de_datos_responde_503(monkeypatch):
    from app.core import database
    from app.core.config import Settings, get_settings

    monkeypatch.setattr(database, "get_settings", lambda: Settings(database_url=""))
    database.reset_engine()
    get_settings.cache_clear()

    with TestClient(app) as cliente:
        response = cliente.get("/api/v1/employability/latest")

    assert response.status_code == 503
    assert "DATABASE_URL" in response.json()["detail"]

    database.reset_engine()
    get_settings.cache_clear()
