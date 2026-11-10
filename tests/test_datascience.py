"""Tests de los endpoints de brechas y oferta formativa (issue #74).

Cubren el contrato normalizado del módulo de Data Science del equipo de Data
y la cadena de degradación: `live` → `cache` → `reference` → 503.

Los tests no usan la red: el cliente se monkeypatchea con
`httpx.MockTransport`.
"""

import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.datascience import DataSourceMeta, GapItem
from app.services.datascience import client as data_client
from app.services.datascience import mapper
from app.services.datascience.summary import construir_resumen

# ---------------------------------------------------------------------------
# Payloads de ejemplo (misma forma que produce `DataAnalyst`)
# ---------------------------------------------------------------------------
PAYLOAD_BRECHAS = {
    "status": "success",
    "total_ocupaciones_analizadas": 2,
    "brechas_y_habilidades": [
        {
            "pais_codigo_iso3": "URY",
            "pais_nombre": "Uruguay",
            "sector": "Tecnología",
            "ocupacion_id": "OCUP_02",
            "ocupacion_nombre": "Ingeniero de Datos y Machine Learning",
            "codigo_ciuo08_oit": "2511",
            "indice_oportunidad_icol": 88.19,
            "score_demanda_mercado": 100.0,
            "score_crecimiento_estimado": 80.0,
            "coeficiente_cobertura_educativa_cce": 0.571,
            "score_brecha_talento_100": 87.76,
            "diagnostico_brecha": "Déficit Crítico de Talento",
            "icono_brecha": "🔴",
            "urgencia_intervencion": "Prioridad 1: Formación Acelerada Inmediata",
            "habilidades_tradicionales": ["ETL Batch", "Pandas"],
            "habilidades_emergentes_2026": ["Arquitecturas RAG", "Edge AI"],
            "nivel_adopcion_habilidades": "Muy Alta",
            "impacto_ia_automatizacion": "Acelerador Fundamental",
            "velocidad_obsolescencia": "Ultra Rápida (< 12 meses)",
        },
        {
            "pais_codigo_iso3": "ARG",
            "pais_nombre": "Argentina",
            "sector": "Salud",
            "ocupacion_id": "OCUP_05",
            "ocupacion_nombre": "Médico General y Especialista",
            "codigo_ciuo08_oit": "2512",
            "indice_oportunidad_icol": 61.0,
            "score_demanda_mercado": 80.0,
            "score_crecimiento_estimado": 40.0,
            "coeficiente_cobertura_educativa_cce": 0.779,
            "score_brecha_talento_100": 63.2,
            "diagnostico_brecha": "Equilibrio Oferta-Demanda",
            "icono_brecha": "🟢",
            "urgencia_intervencion": "Prioridad 3: Monitoreo Regular",
            "habilidades_tradicionales": ["Diagnóstico Clínico"],
            "habilidades_emergentes_2026": ["Genómica clínica"],
            "nivel_adopcion_habilidades": "Media",
            "impacto_ia_automatizacion": "Moderado",
            "velocidad_obsolescencia": "Moderada",
        },
    ],
}

PAYLOAD_COMPARATIVA = {
    "status": "success",
    "total_sectores_evaluados": 2,
    "comparativa_educativo_laboral": [
        {
            "pais_codigo_iso3": "ARG",
            "pais_nombre": "Argentina",
            "sector": "Energía",
            "carreras_universitarias_afines": "Ing. Eléctrica, Ing. Química/Petróleo",
            "egresados_anuales_estimados": 4800,
            "crecimiento_matricula_anual": "+9.1% anual",
            "demanda_anual_puestos_nuevos": 8900,
            "brecha_anual_puestos_deficit": 4100,
            "coeficiente_cobertura_educativa_cce": 0.539,
            "diagnostico_descalce": "Déficit Formativo Severo (Alerta Roja)",
            "estado_alerta": "CRITICA",
            "semaforo": "🔴",
            "fuentes_oficiales_cruzadas": "Secretaría de Energía / CONEAU / SPU",
        },
        {
            "pais_codigo_iso3": "URY",
            "pais_nombre": "Uruguay",
            "sector": "Turismo",
            "carreras_universitarias_afines": "Licenciatura en Turismo",
            "egresados_anuales_estimados": 500,
            "crecimiento_matricula_anual": "+3.0% anual",
            "demanda_anual_puestos_nuevos": 1200,
            "brecha_anual_puestos_deficit": 700,
            "coeficiente_cobertura_educativa_cce": 0.417,
            "diagnostico_descalce": "Déficit Formativo Severo (Alerta Roja)",
            "estado_alerta": "CRITICA",
            "semaforo": "🔴",
            "fuentes_oficiales_cruzadas": "Monitor MEC / UdelaR (URY)",
        },
    ],
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def cache_limpia():
    """Cada test arranca sin caché (evita contaminación entre casos)."""
    data_client.get_cache().clear()
    yield
    data_client.get_cache().clear()


@pytest.fixture()
def mock_data(monkeypatch):
    """Simula la API de Data con `httpx.MockTransport`.

    Devuelve una función que permite (re)configurar la respuesta: el mock
    se reemplaza en cada llamada, así que un test puede pasar de "Data viva"
    a "Data caída" dentro del mismo caso.
    """
    estado: dict[str, object] = {"respuestas": None, "excepcion": None, "llamadas": []}

    def handler(peticion: httpx.Request) -> httpx.Response:
        estado["llamadas"].append(peticion.url.path)  # type: ignore[union-attr]
        excepcion = estado["excepcion"]
        if isinstance(excepcion, Exception):
            raise excepcion
        respuestas = estado["respuestas"]
        if isinstance(respuestas, dict) and peticion.url.path in respuestas:
            codigo, cuerpo = respuestas[peticion.url.path]
            return httpx.Response(codigo, json=cuerpo)
        if peticion.url.path == data_client.RUTA_BRECHAS:
            return httpx.Response(200, json=PAYLOAD_BRECHAS)
        if peticion.url.path == data_client.RUTA_COMPARATIVA:
            return httpx.Response(200, json=PAYLOAD_COMPARATIVA)
        return httpx.Response(404, json={"detail": "no encontrado"})

    transporte = httpx.MockTransport(handler)
    monkeypatch.setattr(
        data_client.httpx,
        "AsyncClient",
        _cliente_que_usa(transporte),
    )

    def _parchear(
        respuestas: dict[str, tuple[int, object]] | None = None,
        excepcion: Exception | None = None,
    ) -> list[str]:
        estado["respuestas"] = respuestas
        estado["excepcion"] = excepcion
        estado["llamadas"] = []
        return estado["llamadas"]  # type: ignore[return-value]

    return _parchear


def _cliente_que_usa(transporte: httpx.MockTransport):
    """Construye un `AsyncClient` que siempre usa el transporte dado."""
    original = httpx.AsyncClient

    def _factory(*args, **kwargs):
        kwargs.pop("transport", None)
        kwargs.pop("base_url", None)
        kwargs.pop("timeout", None)
        return original(transport=transporte, base_url="http://data.test", timeout=5.0)

    return _factory


@pytest.fixture()
def sin_referencia(monkeypatch, tmp_path):
    """Apunta la carpeta de referencia a un directorio vacío."""
    monkeypatch.setenv("REFERENCE_DIR", str(tmp_path / "vacio"))
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# /skills
# ---------------------------------------------------------------------------
def test_skills_normaliza_el_payload_de_data(mock_data):
    mock_data()

    response = TestClient(app).get("/api/v1/skills")

    assert response.status_code == 200
    cuerpo = response.json()
    assert cuerpo["meta"]["fuente"] == "live"
    assert cuerpo["total"] == 2

    primero = cuerpo["items"][0]
    assert primero["ocupacion_id"] == "OCUP_02"
    assert primero["pais"] == "URY"
    assert primero["score_brecha"] == 87.76
    assert primero["cce"] == 0.571
    assert primero["icol"] == 88.19
    assert primero["score_demanda_100"] == 100.0
    assert primero["score_crecimiento_100"] == 80.0
    assert primero["factor_madurez_pais"] == 1.05
    assert primero["brecha_cobertura_pct"] == 42.9
    assert primero["tgs_desglose"]["demanda"]["aporte"] == 55.0
    assert primero["tgs_desglose"]["crecimiento"]["aporte"] == 20.0
    assert primero["tgs_desglose"]["cobertura"]["aporte"] == 8.58
    assert primero["tgs_desglose"]["tgs_calculado"] == 87.76
    assert primero["diagnostico"] == "Déficit Crítico de Talento"
    assert primero["icono"] == "🔴"
    assert primero["habilidades_emergentes"] == ["Arquitecturas RAG", "Edge AI"]
    assert primero["habilidades_tradicionales"] == ["ETL Batch", "Pandas"]
    assert primero["is_projection"] is True


def test_mapear_brechas_sin_componentes_del_tgs():
    """Si Data no envía los scores, el desglose viaja en None (no en cero)."""
    item = mapper.mapear_brechas(
        {
            "pais_codigo_iso3": "ARG",
            "ocupacion_id": "OCUP_01",
            "score_brecha_talento_100": 50.0,
        }
    )

    assert item.score_demanda_100 is None
    assert item.score_crecimiento_100 is None
    assert item.brecha_cobertura_pct is None
    assert item.tgs_desglose is None


def test_skills_filtra_por_pais(mock_data):
    mock_data()

    response = TestClient(app).get("/api/v1/skills?pais=URY")

    assert response.status_code == 200
    cuerpo = response.json()
    assert cuerpo["filtros"]["pais"] == "URY"
    # El mock devuelve las dos filas; el filtro real lo aplica Data.
    assert cuerpo["total"] == 2


def test_skills_normaliza_el_sector_a_su_nombre_canonico(mock_data):
    """Data espera el nombre del sector; el backend acepta código o slug."""
    mock_data()

    for valor in ("TEC", "tecnologia", "Tecnología"):
        response = TestClient(app).get(f"/api/v1/skills?sector={valor}")
        assert response.status_code == 200
        assert response.json()["filtros"]["sector"] == "Tecnología"


def test_skills_rechaza_pais_invalido(mock_data):
    mock_data()

    response = TestClient(app).get("/api/v1/skills?pais=BRA")

    assert response.status_code == 400
    assert "BR A" not in response.json()["detail"]


def test_skills_rechaza_sector_invalido(mock_data):
    mock_data()

    response = TestClient(app).get("/api/v1/skills?sector=Automotriz")

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# /skills/{ocupacion_id}
# ---------------------------------------------------------------------------
def test_detalle_de_ocupacion(mock_data):
    mock_data()

    response = TestClient(app).get("/api/v1/skills/OCUP_02")

    assert response.status_code == 200
    cuerpo = response.json()
    assert cuerpo["ocupacion"]["id"] == "OCUP_02"
    assert cuerpo["ocupacion"]["nombre"] == "Ingeniero de Datos y Machine Learning"
    assert cuerpo["total"] == 1
    assert cuerpo["items"][0]["ocupacion_id"] == "OCUP_02"


def test_detalle_rechaza_formato_invalido(mock_data):
    mock_data()

    response = TestClient(app).get("/api/v1/skills/OCC-1")

    assert response.status_code == 422


def test_detalle_responde_404_si_no_existe_en_catalogo(mock_data):
    mock_data()

    response = TestClient(app).get("/api/v1/skills/OCUP_99")

    assert response.status_code == 404


def test_detalle_responde_404_si_no_hay_brechas_de_esa_ocupacion(mock_data):
    mock_data()

    response = TestClient(app).get("/api/v1/skills/OCUP_13")

    assert response.status_code == 404
    assert "brechas" in response.json()["detail"]


# ---------------------------------------------------------------------------
# /gaps
# ---------------------------------------------------------------------------
def test_gaps_normaliza_el_payload_de_data(mock_data):
    mock_data()

    response = TestClient(app).get("/api/v1/gaps?pais=ARG")

    assert response.status_code == 200
    cuerpo = response.json()
    assert cuerpo["meta"]["fuente"] == "live"
    assert cuerpo["total"] == 2

    primero = cuerpo["items"][0]
    assert primero["pais"] == "ARG"
    assert primero["sector"] == "Energía"
    assert primero["egresados_anuales"] == 4800
    assert primero["demanda_anual"] == 8900
    assert primero["deficit_anual"] == 4100
    assert primero["cce"] == 0.539
    assert primero["crecimiento_matricula_pct"] == 9.1
    assert primero["estado"] == "CRITICA"
    assert primero["semaforo"] == "🔴"
    # Las carreras vienen como texto separado por comas en Data.
    assert primero["carreras_afines"] == ["Ing. Eléctrica", "Ing. Química/Petróleo"]
    assert primero["fuentes"] == ["Secretaría de Energía / CONEAU / SPU"]


def test_gaps_rechaza_pais_invalido(mock_data):
    mock_data()

    response = TestClient(app).get("/api/v1/gaps?pais=BRA")

    assert response.status_code == 400


def test_porcentaje_parsea_texto_de_data():
    """`crecimiento_matricula_anual` llega como texto ("+9.1% anual")."""
    assert mapper._porcentaje("+9.1% anual") == 9.1
    assert mapper._porcentaje("+3.0% anual") == 3.0
    assert mapper._porcentaje(4.2) == 4.2
    assert mapper._porcentaje("sin numero") is None
    assert mapper._porcentaje(None) is None


# ---------------------------------------------------------------------------
# /gaps/summary
# ---------------------------------------------------------------------------
def test_gaps_summary_calcula_agregados(mock_data):
    """Los totales y el CCE ponderado se calculan en el Backend."""
    mock_data()

    response = TestClient(app).get("/api/v1/gaps/summary")

    assert response.status_code == 200
    cuerpo = response.json()
    assert cuerpo["total_sectores"] == 2

    totales = cuerpo["totales"]
    assert totales["demanda_anual"] == 10100
    assert totales["egresados_anuales"] == 5300
    assert totales["deficit_bruto"] == 4800
    assert totales["brecha_neta"] == 4800
    assert totales["superavit_total"] == 0
    assert totales["cce_ponderado"] == 0.525
    assert totales["brecha_cobertura_pct"] == 47.5


def test_gaps_summary_desglosa_por_pais_y_sector(mock_data):
    """El resumen expone los agregados por país y las filas enriquecidas."""
    mock_data()

    response = TestClient(app).get("/api/v1/gaps/summary")

    assert response.status_code == 200
    cuerpo = response.json()

    por_pais = {fila["pais"]: fila for fila in cuerpo["por_pais"]}
    assert por_pais["ARG"]["demanda_anual"] == 8900
    assert por_pais["ARG"]["deficit_bruto"] == 4100
    assert por_pais["ARG"]["cce_ponderado"] == 0.539
    assert por_pais["ARG"]["brecha_cobertura_pct"] == 46.1
    assert por_pais["URY"]["cce_ponderado"] == 0.417

    primero = cuerpo["por_sector"][0]
    assert primero["pais"] == "ARG"
    assert primero["sector"] == "Energía"
    assert primero["deficit_anual"] == 4100
    assert primero["cce"] == 0.539
    assert primero["brecha_cobertura_pct"] == 46.1
    assert primero["crecimiento_matricula_pct"] == 9.1
    assert primero["estado_cce"] == "CRITICA"
    assert primero["semaforo"] == "🔴"


def test_gaps_summary_filtra_por_sector(mock_data):
    """El filtro de sector se aplica localmente sobre el payload de Data."""
    mock_data()

    response = TestClient(app).get("/api/v1/gaps/summary", params={"sector": "Energía"})

    assert response.status_code == 200
    cuerpo = response.json()
    assert cuerpo["total_sectores"] == 1
    assert cuerpo["filtros"]["sector"] == "Energía"
    assert [fila["sector"] for fila in cuerpo["por_sector"]] == ["Energía"]


def test_gaps_summary_rechaza_pais_invalido(mock_data):
    mock_data()

    response = TestClient(app).get("/api/v1/gaps/summary?pais=BRA")

    assert response.status_code == 400


def test_gaps_summary_rechaza_sector_invalido(mock_data):
    mock_data()

    response = TestClient(app).get("/api/v1/gaps/summary?sector=Automotriz")

    assert response.status_code == 422


def test_gaps_summary_sin_data_usa_la_referencia(mock_data):
    """Sin API de Data el resumen sale del snapshot commiteado."""
    destino = Path("data/reference")
    if not (destino / "comparativa.json").exists():
        pytest.skip("Falta el snapshot de referencia (data/reference/comparativa.json).")

    mock_data(excepcion=httpx.ConnectError("sin conexión"))

    response = TestClient(app).get("/api/v1/gaps/summary")

    assert response.status_code == 200
    cuerpo = response.json()
    assert cuerpo["meta"]["fuente"] == "reference"
    assert cuerpo["total_sectores"] == 15
    assert cuerpo["totales"]["demanda_anual"] == 165250
    assert cuerpo["totales"]["egresados_anuales"] == 113450
    assert cuerpo["totales"]["deficit_bruto"] == 51800
    assert cuerpo["totales"]["cce_ponderado"] == 0.687
    assert cuerpo["totales"]["brecha_cobertura_pct"] == 31.3


def test_summary_pondera_el_cce_por_demanda():
    """El CCE agregado no es el promedio simple de los sectores."""
    items = [
        GapItem(pais="ARG", sector="A", demanda_anual=1000, egresados_anuales=100, cce=0.1),
        GapItem(pais="ARG", sector="B", demanda_anual=100, egresados_anuales=100, cce=1.0),
    ]

    resumen = construir_resumen(items, DataSourceMeta(fuente="reference"))

    assert resumen.totales.cce_ponderado == 0.182
    assert resumen.totales.cce_ponderado != 0.55  # promedio simple


def test_summary_con_demanda_cero_no_divide_por_cero():
    items = [
        GapItem(pais="ARG", sector="A", demanda_anual=0, egresados_anuales=100, cce=None),
    ]

    resumen = construir_resumen(items, DataSourceMeta(fuente="reference"))

    assert resumen.totales.cce_ponderado is None
    assert resumen.totales.brecha_cobertura_pct is None
    assert resumen.totales.superavit_total == 100


def test_summary_excluye_filas_sin_oferta_de_los_agregados():
    items = [
        GapItem(pais="ARG", sector="A", demanda_anual=100, egresados_anuales=50, cce=0.5),
        GapItem(pais="ARG", sector="B", demanda_anual=100, egresados_anuales=None, cce=None),
    ]

    resumen = construir_resumen(items, DataSourceMeta(fuente="reference"))

    assert resumen.total_sectores == 2
    assert resumen.totales.demanda_anual == 100
    assert resumen.totales.egresados_anuales == 50
    assert len(resumen.por_sector) == 2


# ---------------------------------------------------------------------------
# Degradación: live → cache → reference → 503
# ---------------------------------------------------------------------------
def test_sin_data_usa_el_snapshot_de_referencia(mock_data):
    """Sin API de Data se responde con el snapshot de referencia commiteado."""
    destino = Path("data/reference")
    if not (destino / "brechas.json").exists():
        pytest.skip("Falta el snapshot de referencia (data/reference/brechas.json).")

    mock_data(excepcion=httpx.ConnectError("sin conexión"))

    response = TestClient(app).get("/api/v1/skills")

    assert response.status_code == 200
    cuerpo = response.json()
    assert cuerpo["meta"]["fuente"] == "reference"
    assert cuerpo["total"] == 60
    assert cuerpo["meta"]["actualizado"]


def test_sin_data_usa_la_cache_si_hubo_una_consulta_exitosa(mock_data):
    """La segunda consulta sin Data se resuelve con la caché en memoria."""
    mock_data()
    cliente = TestClient(app)

    primero = cliente.get("/api/v1/skills")
    assert primero.json()["meta"]["fuente"] == "live"

    mock_data(excepcion=httpx.ConnectError("sin conexión"))
    segundo = cliente.get("/api/v1/skills")

    assert segundo.status_code == 200
    assert segundo.json()["meta"]["fuente"] == "cache"


def test_sin_data_sin_cache_sin_referencia_responde_503(mock_data, sin_referencia):
    """Sin ninguna fuente disponible el endpoint responde 503."""
    mock_data(excepcion=httpx.ConnectError("sin conexión"))

    response = TestClient(app).get("/api/v1/skills")

    assert response.status_code == 503
    assert "Data" in response.json()["detail"]


def test_data_que_devuelve_500_responde_503(mock_data, sin_referencia):
    """Un error del upstream no se traduce a un 500 del Backend."""
    mock_data(respuestas={data_client.RUTA_BRECHAS: (500, {"detail": "boom"})})

    response = TestClient(app).get("/api/v1/skills")

    assert response.status_code == 503


def test_data_que_devuelve_500_sin_referencia_tambien_responde_503(mock_data, sin_referencia):
    mock_data(respuestas={data_client.RUTA_COMPARATIVA: (500, {"detail": "boom"})})

    response = TestClient(app).get("/api/v1/gaps")

    assert response.status_code == 503


# ---------------------------------------------------------------------------
# Cliente
# ---------------------------------------------------------------------------
def test_el_clave_de_cache_incluye_los_parametros():
    cache = data_client.CacheData()
    cache.set("/ruta", {"pais": "URY"}, {"a": 1})
    cache.set("/ruta", {"pais": "ARG"}, {"a": 2})

    assert cache.get("/ruta", {"pais": "URY"}, 300) == {"a": 1}
    assert cache.get("/ruta", {"pais": "ARG"}, 300) == {"a": 2}


def test_la_cache_expira():
    cache = data_client.CacheData()
    cache.set("/ruta", {}, {"a": 1})

    assert cache.get("/ruta", {}, 0) is None


def test_el_snapshot_de_referencia_se_lee_con_su_fecha(monkeypatch, tmp_path):
    archivo = tmp_path / "brechas.json"
    archivo.write_text(
        json.dumps({"brechas_y_habilidades": [], "_actualizado": "2026-11-04T00:00:00+00:00"}),
        encoding="utf-8",
    )

    datos, actualizado = data_client._leer_referencia(
        data_client.RUTA_BRECHAS, reference_dir=str(tmp_path)
    )

    assert datos["brechas_y_habilidades"] == []
    assert actualizado == "2026-11-04T00:00:00+00:00"
