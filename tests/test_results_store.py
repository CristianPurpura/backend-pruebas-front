"""Tests de persistencia histórica de los índices (issue #54).

Cubre el servicio `results_store` (guardado idempotente, consultas y
limpieza) y los endpoints `POST /employability/snapshot` y
`GET /employability/history`.

Los tests usan **SQLite en memoria** (`aiosqlite`), así que no tocan la base
de datos real: la variable `DATABASE_URL` se sobreescribe por fixture.
"""

import asyncio
from typing import Any, AsyncIterator, Iterator

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core import database
from app.core.config import get_settings
from app.models import Base
from app.services.persistence import results_store

# ---------------------------------------------------------------------------
# Cliente HTTP asíncrono
# ---------------------------------------------------------------------------
class ClienteAsync:
    """Cliente mínimo que llama a la app en el event loop actual.

    `TestClient` de Starlette levanta la app en su propio loop (por eso
    `anyio` portal), lo que no sirve cuando la sesión de base de datos está
    ligada a otro loop. Este cliente usa `httpx.AsyncClient` con el
    transporte ASGI, que sí corre en el loop donde se lo usa.
    """

    def __init__(self, app) -> None:
        self._app = app
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                transport=httpx.ASGITransport(app=self._app),
                base_url="http://testserver",
            )
        return self._client

    async def request(self, metodo: str, url: str, **kwargs) -> httpx.Response:
        cliente = await self._get_client()
        return await cliente.request(metodo, url, **kwargs)

    async def get(self, url: str, **kwargs) -> httpx.Response:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs) -> httpx.Response:
        return await self.request("POST", url, **kwargs)

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def run(self, metodo: str, url: str, **kwargs) -> httpx.Response:
        """Ejecuta la petición en el event loop actual (el del fixture)."""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.request(metodo, url, **kwargs))

    def get_sync(self, url: str, **kwargs) -> httpx.Response:
        return self.run("GET", url, **kwargs)

    def post_sync(self, url: str, **kwargs) -> httpx.Response:
        return self.run("POST", url, **kwargs)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def db_session(tmp_path, monkeypatch) -> AsyncIterator[AsyncSession]:
    """Sesión async contra un SQLite en memoria con las tablas del modelo.

    Se usa un único event loop para toda la vida del fixture: la sesión queda
    ligada a ese loop, así que las llamadas async deben correr en él.
    """
    url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    engine = create_async_engine(url, future=True)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def _preparar() -> AsyncSession:
        async with engine.begin() as conexion:
            await conexion.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        return factory()

    session = loop.run_until_complete(_preparar())
    try:
        yield session
    finally:
        loop.run_until_complete(session.close())
        loop.run_until_complete(engine.dispose())
        loop.close()
        asyncio.set_event_loop(None)


@pytest.fixture()
def event_loop(db_session) -> Iterator[asyncio.AbstractEventLoop]:
    """El loop del fixture de sesión, para correr corrutinas contra ella."""
    loop = asyncio.get_event_loop()
    yield loop


@pytest.fixture()
def client_con_db(db_session) -> Iterator["ClienteAsync"]:
    """Cliente HTTP asíncrono contra la app, con la DB del fixture.

    No se usa `TestClient` porque corre la app en su propio event loop y la
    sesión async del fixture está ligada a otro. Este cliente invoca la app
    con `httpx.AsyncClient` sobre el transporte ASGI, siempre en el loop del
    fixture.
    """
    from app.api.v1.endpoints import snapshots
    from app.main import app

    async def _get_db_requerida() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[snapshots.get_db_requerida] = _get_db_requerida
    cliente = ClienteAsync(app)
    try:
        yield cliente
    finally:
        app.dependency_overrides.pop(snapshots.get_db_requerida, None)


def _fila_idelr(pais: str = "ARG", anio: int = 2024, valor: float = 61.5) -> dict[str, Any]:
    return {
        "tipo": "IDELR",
        "pais": pais,
        "anio": anio,
        "ocupacion_id": None,
        "valor": valor,
        "categoria": "CRECIMIENTO",
        "cobertura_pct": 100.0,
        "payload": {"pais_codigo_iso3": pais, "anio": anio, "indice_sintetico": valor},
    }


def _fila_icol(
    pais: str = "URY",
    ocupacion: str = "OCUP_01",
    valor: float = 87.76,
) -> dict[str, Any]:
    return {
        "tipo": "ICOL",
        "pais": pais,
        "anio": 2024,
        "ocupacion_id": ocupacion,
        "valor": valor,
        "categoria": "Oportunidad Excepcional",
        "cobertura_pct": None,
        "payload": {"ocupacion_id": ocupacion, "indice_oportunidad_icol": valor},
    }


# ---------------------------------------------------------------------------
# Servicio: guardado
# ---------------------------------------------------------------------------
def _run(db_session: AsyncSession, coro):
    """Ejecuta una corrutina en el event loop del fixture."""
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


def test_guarda_un_snapshot_nuevo(db_session):
    """Un snapshot nuevo inserta las filas."""
    conteo = _run(
        db_session, results_store.save_snapshot(db_session, [_fila_idelr(), _fila_icol()])
    )

    assert conteo == {"insertados": 2, "actualizados": 0, "total": 2}
    guardados = _run(db_session, results_store.history(db_session))
    assert len(guardados) == 2


def test_guardar_dos_veces_el_mismo_dia_no_duplica(db_session):
    """El snapshot es idempotente: el segundo guardado actualiza."""
    _run(db_session, results_store.save_snapshot(db_session, [_fila_idelr()], fecha="2026-11-04"))
    conteo = _run(
        db_session,
        results_store.save_snapshot(
            db_session,
            [_fila_idelr(valor=72.0)],
            fecha="2026-11-04",
        ),
    )

    assert conteo == {"insertados": 0, "actualizados": 1, "total": 1}
    guardados = _run(db_session, results_store.history(db_session))
    assert len(guardados) == 1
    assert float(guardados[0].valor) == 72.0


def test_guardar_en_otro_dia_crea_una_fila_nueva(db_session):
    """Un día distinto es un snapshot distinto: se conserva el histórico."""
    _run(db_session, results_store.save_snapshot(db_session, [_fila_idelr()], fecha="2026-11-04"))
    _run(
        db_session,
        results_store.save_snapshot(
            db_session,
            [_fila_idelr(valor=70.0)],
            fecha="2026-11-05",
        ),
    )

    guardados = _run(db_session, results_store.history(db_session))
    assert len(guardados) == 2


def test_el_snapshot_calculado_tiene_las_filas_correctas():
    """La conversión de la serie IDELR respeta los campos del modelo."""
    serie = [
        {
            "pais_codigo_iso3": "ARG",
            "anio": 2023,
            "indice_sintetico": 58.25,
            "cobertura_variables_pct": 100.0,
            "tendencia": "CRECIMIENTO",
        }
    ]

    filas = results_store.snapshot_idelr(serie)

    assert len(filas) == 1
    assert filas[0]["tipo"] == "IDELR"
    assert filas[0]["pais"] == "ARG"
    assert filas[0]["anio"] == 2023
    assert filas[0]["ocupacion_id"] is None
    assert filas[0]["valor"] == 58.25
    assert filas[0]["categoria"] == "CRECIMIENTO"
    assert filas[0]["cobertura_pct"] == 100.0


def test_el_snapshot_icol_usa_el_anio_de_referencia():
    """El ICOL se registra con el año macro de referencia."""
    ranking = [
        {
            "pais_codigo_iso3": "URY",
            "ocupacion_id": "OCUP_01",
            "indice_oportunidad_icol": 87.76,
            "categoria_oportunidad": "Oportunidad Excepcional",
        }
    ]

    filas = results_store.snapshot_icol(ranking, 2024)

    assert filas[0]["tipo"] == "ICOL"
    assert filas[0]["anio"] == 2024
    assert filas[0]["ocupacion_id"] == "OCUP_01"
    assert filas[0]["valor"] == 87.76


# ---------------------------------------------------------------------------
# Servicio: consultas
# ---------------------------------------------------------------------------
def test_history_filtra_por_tipo(db_session):
    _run(
        db_session,
        results_store.save_snapshot(
            db_session, [_fila_idelr(), _fila_icol()], fecha="2026-11-04"
        ),
    )

    solo_idelr = _run(db_session, results_store.history(db_session, tipo="IDELR"))
    solo_icol = _run(db_session, results_store.history(db_session, tipo="ICOL"))

    assert len(solo_idelr) == 1
    assert solo_idelr[0].tipo == "IDELR"
    assert len(solo_icol) == 1
    assert solo_icol[0].tipo == "ICOL"


def test_history_filtra_por_pais_y_ocupacion(db_session):
    _run(
        db_session,
        results_store.save_snapshot(
            db_session,
            [_fila_idelr(pais="ARG"), _fila_icol(pais="URY", ocupacion="OCUP_03")],
            fecha="2026-11-04",
        ),
    )

    por_pais = _run(db_session, results_store.history(db_session, pais="URY"))
    por_ocupacion = _run(db_session, results_store.history(db_session, ocupacion_id="OCUP_03"))

    assert len(por_pais) == 1
    assert por_pais[0].pais == "URY"
    assert len(por_ocupacion) == 1
    assert por_ocupacion[0].ocupacion_id == "OCUP_03"


def test_history_filtra_por_rango_de_anios(db_session):
    _run(
        db_session,
        results_store.save_snapshot(
            db_session,
            [_fila_idelr(anio=2022), _fila_idelr(anio=2024)],
            fecha="2026-11-04",
        ),
    )

    desde_2023 = _run(db_session, results_store.history(db_session, anio_desde=2023))

    assert len(desde_2023) == 1
    assert desde_2023[0].anio == 2024


def test_latest_devuelve_el_snapshot_mas_reciente_por_combinacion(db_session):
    _run(
        db_session,
        results_store.save_snapshot(db_session, [_fila_idelr(valor=50.0)], fecha="2026-11-04"),
    )
    _run(
        db_session,
        results_store.save_snapshot(db_session, [_fila_idelr(valor=80.0)], fecha="2026-11-05"),
    )

    recientes = _run(db_session, results_store.latest(db_session))

    assert len(recientes) == 1
    assert float(recientes[0].valor) == 80.0


def test_purge_borra_los_snapshots(db_session):
    _run(
        db_session,
        results_store.save_snapshot(
            db_session, [_fila_idelr(), _fila_icol()], fecha="2026-11-04"
        ),
    )

    borrados = _run(db_session, results_store.purge(db_session, tipo="ICOL"))

    assert borrados == 1
    assert len(_run(db_session, results_store.history(db_session))) == 1


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
def test_snapshot_guarda_y_devuelve_el_conteo(client_con_db):
    """POST /employability/snapshot guarda y reporta qué se guardó."""
    response = client_con_db.post_sync("/api/v1/employability/snapshot")

    assert response.status_code == 200
    cuerpo = response.json()
    assert cuerpo["guardado"]["idelr"] >= 0
    assert cuerpo["guardado"]["icol"] == 60
    assert cuerpo["guardado"]["insertados"] == cuerpo["guardado"]["idelr"] + 60
    assert cuerpo["metodologia_version"] == results_store.METODOLOGIA_VERSION
    assert cuerpo["fecha_snapshot"]


def test_snapshot_es_idempotente(client_con_db):
    """Guardar dos veces el mismo día no duplica filas."""
    client_con_db.post_sync("/api/v1/employability/snapshot")
    segundo = client_con_db.post_sync("/api/v1/employability/snapshot")

    assert segundo.status_code == 200
    guardado = segundo.json()["guardado"]
    assert guardado["insertados"] == 0
    assert guardado["actualizados"] == guardado["idelr"] + 60


def test_history_devuelve_lo_guardado(client_con_db):
    """GET /employability/history lee lo que guardó el POST."""
    client_con_db.post_sync("/api/v1/employability/snapshot")
    response = client_con_db.get_sync("/api/v1/employability/history")

    assert response.status_code == 200
    cuerpo = response.json()
    assert cuerpo["total"] == 60
    assert cuerpo["resultados"][0]["tipo"] == "ICOL"
    assert cuerpo["resultados"][0]["metodologia_version"]


def test_history_filtra_por_pais(client_con_db):
    client_con_db.post_sync("/api/v1/employability/snapshot")
    response = client_con_db.get_sync("/api/v1/employability/history?pais=URY&tipo=ICOL")

    assert response.status_code == 200
    cuerpo = response.json()
    assert cuerpo["total"] == 20
    assert all(fila["pais"] == "URY" for fila in cuerpo["resultados"])


def test_latest_devuelve_el_ultimo_snapshot_de_cada_combinacion(client_con_db):
    client_con_db.post_sync("/api/v1/employability/snapshot")
    response = client_con_db.get_sync("/api/v1/employability/latest?tipo=ICOL&pais=URY")

    assert response.status_code == 200
    cuerpo = response.json()
    assert cuerpo["tipo"] == "ICOL"
    assert cuerpo["total"] == 20
    assert all(fila["pais"] == "URY" for fila in cuerpo["resultados"])
    assert all("payload" not in fila for fila in cuerpo["resultados"])
    assert cuerpo["fecha_snapshot"] is not None


def test_history_rechaza_filtros_invalidos(client_con_db):
    """Un tipo o país fuera de catálogo responde 400."""
    assert client_con_db.get_sync("/api/v1/employability/history?tipo=XXX").status_code == 400
    assert client_con_db.get_sync("/api/v1/employability/history?pais=BRA").status_code == 400
    assert (
        client_con_db.get_sync("/api/v1/employability/history?ocupacion=OCUP_99").status_code == 400
    )


def test_el_get_de_empleabilidad_no_guarda_nada(client_con_db):
    """Consultar el índice sigue siendo de solo lectura."""
    client_con_db.get_sync("/api/v1/employability")

    history = client_con_db.get_sync("/api/v1/employability/history")

    assert history.status_code == 200
    assert history.json()["total"] == 0


def test_snapshot_sin_base_de_datos_responde_503(monkeypatch):
    """Sin DATABASE_URL el POST responde 503 con un mensaje claro."""
    from app.api.v1.endpoints import snapshots
    from app.core import database
    from app.core.config import Settings
    from app.main import app

    monkeypatch.setattr(database, "get_settings", lambda: Settings(database_url=""))
    database.reset_engine()
    get_settings.cache_clear()

    with TestClient(app) as cliente:
        response = cliente.post("/api/v1/employability/snapshot")

    assert response.status_code == 503
    assert "DATABASE_URL" in response.json()["detail"]

    database.reset_engine()
    get_settings.cache_clear()
