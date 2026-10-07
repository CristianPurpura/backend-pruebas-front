import asyncio

import httpx
import pytest

from app.services.connectors import (
    BancoMundialConnector,
    DatosArgentinaConnector,
    SimelChileConnector,
)

DATOS_AR_SAMPLE = {
    "data": [["2024-01-01", 100.5], ["2024-02-01", 101.2], [None, None]],
    "count": 2,
    "meta": [{"id": "148.3_INIVELNAL_DICI_M_26", "titulo": "IPC"}],
}

BM_SAMPLE = [
    {"page": 1, "pages": 1, "total": 2},
    [
        {"countryiso3code": "ARG", "date": "2023", "value": 6.139},
        {"countryiso3code": "ARG", "date": "2022", "value": None},
        {"countryiso3code": "ARG", "date": "2021", "value": 7.441},
    ],
]

SIMEL_CSV = (
    "DATAFLOW,FREQ,INDICADOR,AREA_REF,SEXO,TIME_PERIOD,OBS_VALUE,OBS_STATUS,NOTAS_INDICADOR,FUENTE,UNIDAD\n"
    "CL01:DF_DES_SEXO(1.0),M,DES,16,T,2025-01-01/P3M,10225.02,,,ENE,PS\n"
    "CL01:DF_DES_SEXO(1.0),M,DES,16,T,2025-04-01/P3M,11596.66,,,ENE,PS\n"
)


def _async_get_ok(payload=None, text=None):
    async def get(self, url, params=None, **kwargs):
        request = httpx.Request("GET", url)
        if text is not None:
            return httpx.Response(200, text=text, request=request)
        return httpx.Response(200, json=payload, request=request)

    return get


def _async_get_status(status):
    async def get(self, url, params=None, **kwargs):
        request = httpx.Request("GET", url)
        return httpx.Response(status, request=request)

    return get


def _async_get_network_error():
    async def get(self, url, params=None, **kwargs):
        request = httpx.Request("GET", url)
        raise httpx.ConnectError("sin conexión", request=request)

    return get


class TestDatosArgentina:
    def test_fetch_parsea_series(self, monkeypatch):
        monkeypatch.setattr(httpx.AsyncClient, "get", _async_get_ok(payload=DATOS_AR_SAMPLE))
        response = asyncio.run(DatosArgentinaConnector().fetch())
        assert response.ok and response.error is None
        assert response.payload["count"] == 2
        assert [p.periodo for p in response.points] == ["2024-01-01", "2024-02-01"]
        assert response.points[0].valor == 100.5

    def test_fetch_http_500(self, monkeypatch):
        monkeypatch.setattr(httpx.AsyncClient, "get", _async_get_status(500))
        response = asyncio.run(DatosArgentinaConnector().fetch())
        assert not response.ok
        assert "HTTP 500" in response.error

    def test_fetch_error_de_red(self, monkeypatch):
        monkeypatch.setattr(httpx.AsyncClient, "get", _async_get_network_error())
        response = asyncio.run(DatosArgentinaConnector().fetch())
        assert not response.ok
        assert "error de red" in response.error


class TestBancoMundial:
    def test_fetch_parsea_tres_paises(self, monkeypatch):
        monkeypatch.setattr(httpx.AsyncClient, "get", _async_get_ok(payload=BM_SAMPLE))
        response = asyncio.run(BancoMundialConnector().fetch())
        assert response.ok
        assert set(response.payload) == {"ARG", "CHL", "URY"}
        assert len(response.points) == 6
        assert response.points[0].periodo == "2023"
        assert response.points[0].valor == 6.139

    def test_fetch_http_404(self, monkeypatch):
        monkeypatch.setattr(httpx.AsyncClient, "get", _async_get_status(404))
        response = asyncio.run(BancoMundialConnector().fetch(countries=("ARG",)))
        assert not response.ok
        assert "HTTP 404" in response.error

    def test_parse_payload_malformado(self):
        assert BancoMundialConnector.parse_points({"unexpected": True}) == []


class TestSimelChile:
    def test_fetch_parsea_csv(self, monkeypatch):
        monkeypatch.setattr(httpx.AsyncClient, "get", _async_get_ok(text=SIMEL_CSV))
        response = asyncio.run(SimelChileConnector().fetch())
        assert response.ok
        assert len(response.payload["records"]) == 2
        assert len(response.points) == 2
        assert response.points[0].periodo == "2025-01-01/P3M"
        assert response.points[0].valor == 10225.02

    def test_fetch_http_500(self, monkeypatch):
        monkeypatch.setattr(httpx.AsyncClient, "get", _async_get_status(500))
        response = asyncio.run(SimelChileConnector().fetch())
        assert not response.ok
        assert "HTTP 500" in response.error


def _fetch_or_skip(connector, **params):
    response = asyncio.run(connector.fetch(**params))
    if not response.ok and response.error and "error de red" in response.error:
        pytest.skip(f"sin salida a internet: {response.error}")
    return response


class TestConexionesEnVivo:
    def test_datos_argentina_en_vivo(self):
        response = _fetch_or_skip(DatosArgentinaConnector(), limit=12)
        assert response.ok, response.error
        assert response.points, "serie sin puntos"
        assert isinstance(response.points[0].valor, float)

    def test_banco_mundial_en_vivo(self):
        response = _fetch_or_skip(BancoMundialConnector(), date_range="2022:2024")
        assert response.ok, response.error
        assert len(response.points) >= 3
        assert {p.periodo for p in response.points} >= {"2022", "2023"}

    def test_simel_chile_en_vivo(self):
        response = _fetch_or_skip(SimelChileConnector())
        assert response.ok, response.error
        assert response.points, "serie sin puntos"
        assert all(isinstance(p.valor, float) for p in response.points)
