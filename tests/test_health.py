"""Tests de GET /api/v1/health (Sprint 0, SPEC.md: chequeo de DB y estado general).

No figura en la matriz QA; cubre los 3 estados del chequeo de base de datos.
"""

import asyncio


async def _db_ok() -> str:
    return "ok"


async def _db_not_configured() -> str:
    return "not_configured"


async def _db_error() -> str:
    return "error"


def test_health_devuelve_200_ok(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.health.async_check_db", _db_ok)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok"}


def test_health_sin_database_url_devuelve_not_configured(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.health.async_check_db", _db_not_configured)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "not_configured"}


def test_health_db_caida_devuelve_503(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.health.async_check_db", _db_error)

    response = client.get("/api/v1/health")

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "db": "error"}


def test_async_check_db_sin_url_devuelve_not_configured(monkeypatch):
    """Sin DATABASE_URL el chequeo no intenta conectar."""
    from app.core import database
    from app.core.config import Settings

    monkeypatch.setattr(database, "get_settings", lambda: Settings(database_url=""))
    database.reset_engine()

    assert asyncio.run(database.async_check_db()) == "not_configured"
