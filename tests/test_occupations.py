"""Tests de GET /api/v1/occupations/{occupation_id}.

El endpoint reemplaza al mock de `OCUP_01` (issue #75): expone el perfil
consolidado de las 20 ocupaciones del catálogo con su ICOL.

Validaciones:
    * Formato inválido (`OCC-1`)            -> 422
    * Formato válido fuera de catálogo      -> 404
    * País fuera del alcance regional       -> 400

El ICOL del perfil es el mismo que devuelve `GET /api/v1/employability`
(misma calculadora), lo que se verifica en
`test_icol_del_perfil_coincide_con_el_de_employability`.
"""

import pytest

from app.core import catalogs
from tests.conftest import COMMON_COLUMNS, make_common_csv

OCCUPATIONS_URL = "/api/v1/occupations"

# Panel macro sembrado en los tests que necesitan datasets cargados (2024).
FILAS_SEMBRADAS = [
    ("ARG", "Argentina", "Variación Anual del PIB Real", 4.6, "Porcentaje (%)"),
    ("ARG", "Argentina", "Índice de Salario Real", 92.0, "Índice (Base 2018=100)"),
    ("ARG", "Argentina", "Tasa de Ocupación", 58.0, "Porcentaje (%)"),
    ("ARG", "Argentina", "Tasa de Finalización de Educación Secundaria", 68.0, "Porcentaje (%)"),
    ("ARG", "Argentina", "Tasa de Desocupación Total", 7.6, "Porcentaje (%)"),
    ("CHL", "Chile", "Variación Anual del PIB Real", 2.5, "Porcentaje (%)"),
    ("CHL", "Chile", "Índice de Salario Real", 101.0, "Índice (Base 2018=100)"),
    ("CHL", "Chile", "Tasa de Ocupación", 60.5, "Porcentaje (%)"),
    ("CHL", "Chile", "Tasa de Finalización de Educación Secundaria", 78.0, "Porcentaje (%)"),
    ("CHL", "Chile", "Tasa de Desocupación Total", 8.8, "Porcentaje (%)"),
    ("URY", "Uruguay", "Variación Anual del PIB Real", 3.1, "Porcentaje (%)"),
    ("URY", "Uruguay", "Índice de Salario Real", 97.0, "Índice (Base 2018=100)"),
    ("URY", "Uruguay", "Tasa de Ocupación", 59.4, "Porcentaje (%)"),
    ("URY", "Uruguay", "Tasa de Finalización de Educación Secundaria", 74.0, "Porcentaje (%)"),
    ("URY", "Uruguay", "Tasa de Desocupación Total", 8.5, "Porcentaje (%)"),
]


def sembrar_dataset(output_dirs) -> None:
    """Escribe un dataset normalizado (esquema común) en el tmp procesado."""
    procesado, _quarantine = output_dirs
    destino = procesado / "sembrado"
    destino.mkdir(parents=True, exist_ok=True)
    filas = [
        dict(
            zip(
                COMMON_COLUMNS,
                (
                    codigo,
                    nombre,
                    catalogs.homologate_indicator(indicador),
                    indicador,
                    "2024",
                    "Anual",
                    valor,
                    unidad,
                    "INDEC / INE / Banco Central",
                    "2026-10-15",
                ),
            )
        )
        for codigo, nombre, indicador, valor, unidad in FILAS_SEMBRADAS
    ]
    (destino / "panel_macro.csv").write_bytes(make_common_csv(filas))


# ---------------------------------------------------------------------------
# Perfil completo de las 20 ocupaciones
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("ocupacion_id", catalogs.OCUPACION_IDS)
def test_las_veinte_ocupaciones_devuelven_su_perfil(client, ocupacion_id):
    body = client.get(f"{OCCUPATIONS_URL}/{ocupacion_id}").json()

    assert body["ocupacion"]["id"] == ocupacion_id
    assert body["ocupacion"]["nombre"]
    assert body["ocupacion"]["ciuo08"].isdigit()
    assert body["sector"]["id"] in {"TEC", "SAL", "ENE", "TUR", "ECO"}
    assert body["habilidades"]


def test_perfil_trae_sector_completo_y_rankings(client):
    body = client.get(f"{OCCUPATIONS_URL}/OCUP_01").json()

    assert body["sector"] == {"id": "TEC", "slug": "tecnologia", "nombre": "Tecnología"}
    assert body["pais"] == {"codigo": "ARG", "nombre": "Argentina"}
    assert body["indicadores"]["nivel_demanda"] == "Muy Alta"
    assert body["indicadores"]["crecimiento_anual_pct"] == 18.5


def test_icol_y_categorias_estan_en_rango(client):
    body = client.get(f"{OCCUPATIONS_URL}/OCUP_01").json()

    indicadores = body["indicadores"]
    assert 0 <= indicadores["icol"] <= 100
    assert indicadores["categoria_oportunidad"]
    assert indicadores["prioridad_formacion"]
    for score in indicadores["scores"].values():
        assert 0 <= score <= 100
    rankings = indicadores["rankings"]
    assert 1 <= rankings["regional"] <= 60  # 3 países x 20 ocupaciones
    assert 1 <= rankings["pais"] <= 20
    assert 1 <= rankings["sector"] <= 20


# ---------------------------------------------------------------------------
# Validaciones
# ---------------------------------------------------------------------------
def test_ocupacion_desconocida_devuelve_404(client):
    response = client.get(f"{OCCUPATIONS_URL}/OCUP_99")

    assert response.status_code == 404
    assert response.json()["detail"].startswith("Ocupación no encontrada")


def test_formato_invalido_devuelve_422(client):
    response = client.get(f"{OCCUPATIONS_URL}/OCC-1")

    assert response.status_code == 422
    assert "inválido" in response.json()["detail"]


def test_id_en_minusculas_se_normaliza(client):
    body = client.get(f"{OCCUPATIONS_URL}/ocup_01").json()

    assert body["ocupacion"]["id"] == "OCUP_01"


# ---------------------------------------------------------------------------
# País
# ---------------------------------------------------------------------------
def test_pais_default_es_argentina(client):
    body = client.get(f"{OCCUPATIONS_URL}/OCUP_01").json()

    assert body["pais"]["codigo"] == "ARG"


def test_filtro_por_pais(client):
    body = client.get(f"{OCCUPATIONS_URL}/OCUP_09", params={"pais": "CHL"}).json()

    assert body["pais"] == {"codigo": "CHL", "nombre": "Chile"}
    # El entorno macro es distinto por país, así que el ICOL también.
    assert body["indicadores"]["scores"]["entorno_macro"] > 0


def test_pais_invalido_devuelve_400(client):
    response = client.get(f"{OCCUPATIONS_URL}/OCUP_01", params={"pais": "XXX"})

    assert response.status_code == 400
    assert "alcance regional" in response.json()["detail"]


def test_comparacion_incluye_los_tres_paises_con_el_pedido_primero(client):
    body = client.get(f"{OCCUPATIONS_URL}/OCUP_01", params={"pais": "CHL"}).json()

    comparacion = body["comparacion_paises"]
    assert [fila["codigo"] for fila in comparacion] == ["CHL", "ARG", "URY"]
    assert all(fila["ranking_pais"] >= 1 for fila in comparacion)
    assert comparacion[0]["icol"] == body["indicadores"]["icol"]


# ---------------------------------------------------------------------------
# Coherencia con el resto de la API y origen de los datos
# ---------------------------------------------------------------------------
def test_icol_del_perfil_coincide_con_el_de_employability(client):
    perfil = client.get(f"{OCCUPATIONS_URL}/OCUP_01", params={"pais": "CHL"}).json()
    ranking = client.get(
        "/api/v1/employability", params={"pais": "CHL", "ocupacion": "OCUP_01"}
    ).json()["ranking_ocupaciones"]

    assert len(ranking) == 1
    assert perfil["indicadores"]["icol"] == ranking[0]["indice_oportunidad_icol"]
    assert perfil["indicadores"]["rankings"]["pais"] == ranking[0]["ranking_pais"]
    assert perfil["indicadores"]["categoria_oportunidad"] == ranking[0]["categoria_oportunidad"]


def test_fallback_sin_datasets_deja_explicito_el_origen(client):
    body = client.get(f"{OCCUPATIONS_URL}/OCUP_01").json()

    assert body["trazabilidad"]["origen_indice"] == "fallback"
    assert body["trazabilidad"]["datasets"] == []
    assert body["indicadores"]["icol"] > 0


def test_con_dataset_cargado_el_indice_usa_los_datos_reales(client, output_dirs):
    sembrar_dataset(output_dirs)

    body = client.get(f"{OCCUPATIONS_URL}/OCUP_01").json()

    assert body["trazabilidad"]["origen_indice"] == "processed"
    assert any("panel_macro.csv" in ruta for ruta in body["trazabilidad"]["datasets"])
    # El entorno macro sale del panel sembrado, no del valor de referencia.
    assert body["indicadores"]["scores"]["entorno_macro"] != 54.2


def test_trazabilidad_sigue_el_contrato_v2(client):
    body = client.get(f"{OCCUPATIONS_URL}/OCUP_01").json()

    trazabilidad = body["trazabilidad"]
    assert "data_type" not in trazabilidad
    assert trazabilidad["is_projection"] is True
    assert trazabilidad["fuente"] and trazabilidad["fuente_url"]
    assert trazabilidad["actualizado"] == "2026-10-15"
    assert trazabilidad["origen_indice"] in {"processed", "fallback"}


# ---------------------------------------------------------------------------
# Bloque de brechas (issue #75)
# ---------------------------------------------------------------------------
def _fila_brecha(pais: str, nombre: str, score: float, emergentes: list[str]) -> dict:
    return {
        "pais_codigo_iso3": pais,
        "pais_nombre": nombre,
        "sector": "Tecnología",
        "ocupacion_id": "OCUP_01",
        "ocupacion_nombre": "Desarrollador de Software y Aplicaciones",
        "codigo_ciuo08_oit": "2512",
        "indice_oportunidad_icol": 80.0,
        "score_demanda_mercado": 100.0,
        "score_crecimiento_estimado": 90.0,
        "coeficiente_cobertura_educativa_cce": 0.55,
        "score_brecha_talento_100": score,
        "diagnostico_brecha": "Déficit Crítico de Talento",
        "icono_brecha": "🔴",
        "urgencia_intervencion": "Prioridad 1",
        "habilidades_tradicionales": ["Python", "SQL"],
        "habilidades_emergentes_2026": emergentes,
        "nivel_adopcion_habilidades": "Muy Alta",
        "impacto_ia_automatizacion": "Acelerador Fundamental",
        "velocidad_obsolescencia": "Alta",
    }


PAYLOAD_BRECHAS_PERFIL = {
    "brechas_y_habilidades": [
        _fila_brecha("ARG", "Argentina", 84.5, ["Arquitecturas RAG"]),
        _fila_brecha("CHL", "Chile", 79.1, ["Edge AI"]),
        _fila_brecha("URY", "Uruguay", 87.8, ["MLOps"]),
    ]
}


@pytest.fixture()
def mock_brechas(monkeypatch):
    """Reemplaza la consulta a Data para controlar live/reference/sin datos."""
    from app.services.datascience import client as data_client
    from app.services.datascience.client import RespuestaData

    def _configurar(
        payload: dict | None = PAYLOAD_BRECHAS_PERFIL,
        fuente: str = "live",
        actualizado: str | None = None,
    ) -> None:
        async def _consultar(ruta, params=None, client=None):
            if ruta != data_client.RUTA_BRECHAS or payload is None:
                return None
            return RespuestaData(datos=payload, fuente=fuente, actualizado=actualizado)

        monkeypatch.setattr(data_client, "consultar_data", _consultar)

    return _configurar


def test_perfil_incluye_bloque_de_brechas(client, mock_brechas):
    mock_brechas()

    body = client.get(f"{OCCUPATIONS_URL}/OCUP_01", params={"pais": "ARG"}).json()
    brechas = body["brechas"]

    assert brechas["brecha_disponible"] is True
    assert brechas["meta"]["fuente"] == "live"
    assert brechas["actual"]["pais"] == "ARG"
    assert brechas["actual"]["score_brecha"] == 84.5
    assert [fila["pais"] for fila in brechas["por_pais"]] == ["ARG", "CHL", "URY"]


def test_brechas_del_perfil_coinciden_con_skills(client, mock_brechas):
    mock_brechas()

    perfil = client.get(f"{OCCUPATIONS_URL}/OCUP_01", params={"pais": "CHL"}).json()
    detalle = client.get("/api/v1/skills/OCUP_01", params={"pais": "CHL"}).json()

    fila_chile = next(item for item in detalle["items"] if item["pais"] == "CHL")
    assert perfil["brechas"]["actual"] == fila_chile
    assert perfil["brechas"]["meta"] == detalle["meta"]


def test_perfil_sin_data_marca_brecha_no_disponible(client, mock_brechas):
    mock_brechas(payload=None)

    response = client.get(f"{OCCUPATIONS_URL}/OCUP_01")

    assert response.status_code == 200
    brechas = response.json()["brechas"]
    assert brechas["brecha_disponible"] is False
    assert brechas["meta"]["fuente"] == "unavailable"
    assert brechas["meta"]["detalle"]
    assert brechas["actual"] is None
    assert brechas["por_pais"] == []
    # El resto del perfil sigue intacto.
    assert response.json()["indicadores"]["icol"] > 0


def test_brechas_por_referencia_siguen_disponibles(client, mock_brechas):
    mock_brechas(fuente="reference", actualizado="2026-11-04T00:00:00+00:00")

    body = client.get(f"{OCCUPATIONS_URL}/OCUP_01").json()
    brechas = body["brechas"]

    assert brechas["brecha_disponible"] is True
    assert brechas["meta"]["fuente"] == "reference"
    assert brechas["meta"]["actualizado"] == "2026-11-04T00:00:00+00:00"


def test_ocupacion_sin_filas_de_brechas_no_rompe_el_perfil(client, mock_brechas):
    otra = _fila_brecha("ARG", "Argentina", 60.0, ["DataOps"])
    otra["ocupacion_id"] = "OCUP_02"
    mock_brechas(payload={"brechas_y_habilidades": [otra]})

    body = client.get(f"{OCCUPATIONS_URL}/OCUP_01").json()
    brechas = body["brechas"]

    assert brechas["brecha_disponible"] is False
    assert brechas["meta"]["fuente"] == "live"
    assert body["indicadores"]["icol"] > 0
