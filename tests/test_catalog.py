"""Tests de los endpoints de catálogos (GET /countries, /sectors, /occupations).

Cubren la integración con el Frontend (issue #74): los catálogos del Backend
reemplazan a los mocks del repositorio `frontend` (`src/mocks/*.json`).
"""

COUNTRIES_URL = "/api/v1/countries"
SECTORS_URL = "/api/v1/sectors"
OCCUPATIONS_URL = "/api/v1/occupations"


def test_countries_devuelve_los_tres_paises_del_alcance(client):
    body = client.get(COUNTRIES_URL).json()

    assert sorted(pais["id"] for pais in body) == ["ARG", "CHL", "URY"]
    for pais in body:
        assert set(pais) == {"id", "nombre", "iso2", "iso3"}
        assert len(pais["iso2"]) == 2
        assert pais["id"] == pais["iso3"]


def test_countries_coincide_con_la_forma_del_mock_del_frontend(client):
    """El frontend usa {id, nombre, iso2}: no debe tener que mapear nada."""
    body = {pais["id"]: pais for pais in client.get(COUNTRIES_URL).json()}

    assert body["ARG"] == {"id": "ARG", "nombre": "Argentina", "iso2": "AR", "iso3": "ARG"}
    assert body["CHL"]["iso2"] == "CL"
    assert body["URY"]["iso2"] == "UY"


def test_sectors_devuelve_los_cinco_sectores_con_su_slug(client):
    body = client.get(SECTORS_URL).json()

    assert len(body) == 5
    for sector in body:
        assert set(sector) == {"id", "slug", "nombre"}
    assert [sector["slug"] for sector in body] == [
        "tecnologia",
        "salud",
        "energia",
        "turismo",
        "economia-conocimiento",
    ]
    assert body[-1]["id"] == "ECO"
    assert body[-1]["nombre"] == "Economía del Conocimiento"


def test_occupations_devuelve_las_veinte_ocupaciones(client):
    body = client.get(OCCUPATIONS_URL).json()

    assert len(body) == 20
    assert body[0]["id"] == "OCUP_01"
    assert body[0]["nombre"] == "Desarrollador de Software y Aplicaciones"
    assert body[0]["sector"] == {"id": "TEC", "slug": "tecnologia", "nombre": "Tecnología"}
    assert body[0]["ciuo08"] == "2512"
    assert body[0]["crecimiento_anual_pct"] == 18.5
    assert "Python" in body[0]["habilidades"]


def test_occupations_todas_tienen_sector_ciuo_demanda_y_habilidades(client):
    body = client.get(OCCUPATIONS_URL).json()

    for ocupacion in body:
        assert ocupacion["sector"]["id"] in {"TEC", "SAL", "ENE", "TUR", "ECO"}
        assert ocupacion["ciuo08"].isdigit() and len(ocupacion["ciuo08"]) == 4
        assert ocupacion["demanda"] in {"Muy Alta", "Alta", "Media-Alta"}
        assert isinstance(ocupacion["crecimiento_anual_pct"], float)
        assert ocupacion["habilidades"] and all(ocupacion["habilidades"])


def test_occupations_filtro_por_sector_canonico(client):
    body = client.get(OCCUPATIONS_URL, params={"sector": "TEC"}).json()

    assert len(body) == 4
    assert {ocupacion["id"] for ocupacion in body} == {"OCUP_01", "OCUP_02", "OCUP_03", "OCUP_04"}


def test_occupations_filtro_por_slug_o_nombre_del_sector(client):
    """El frontend filtra por slug (`economia-conocimiento`) y la carga por nombre."""
    por_slug = client.get(OCCUPATIONS_URL, params={"sector": "economia-conocimiento"}).json()
    por_nombre = client.get(OCCUPATIONS_URL, params={"sector": "Economía del Conocimiento"}).json()

    assert len(por_slug) == 4
    assert {ocupacion["id"] for ocupacion in por_slug} == {"OCUP_17", "OCUP_18", "OCUP_19", "OCUP_20"}
    assert por_nombre == por_slug


def test_occupations_sector_desconocido_devuelve_422(client):
    response = client.get(OCCUPATIONS_URL, params={"sector": "mineria"})

    assert response.status_code == 422
    assert "mineria" in response.json()["detail"]


def test_occupations_cada_sector_tiene_cuatro_perfiles(client):
    for slug_sector in ("tecnologia", "salud", "energia", "turismo", "economia-conocimiento"):
        body = client.get(OCCUPATIONS_URL, params={"sector": slug_sector}).json()
        assert len(body) == 4, slug_sector
