from fastapi.testclient import TestClient
from app import app

client = TestClient(app)


def test_flujo_1_home_a_pais_dashboard_general():
    """
    Verifica: Home --> PAIS --> Dashboard con visualización general del país seleccionado.
    Comprueba que para ARG devuelve sus 20 ocupaciones del catálogo y 45 registros del consolidado.
    """
    resp = client.get("/api/v1/visualizacion/pais/ARG")
    assert resp.status_code == 200
    body = resp.json()
    assert body["pais_codigo_iso3"] == "ARG"
    assert body["kpis_generales"]["total_ocupaciones_catalogo"] == 20
    assert body["kpis_generales"]["total_registros_consolidado"] == 45
    assert len(body["ocupaciones_pais"]) == 20


def test_flujo_2_home_a_ficha_ocupacion_con_comparativas_y_fechas():
    """
    Verifica: Home --> PAIS + Sector + Area + Fechas --> Ficha completa de la ocupación
    (con comparativas) con datos obtenidos en las fechas.
    """
    resp = client.get(
        "/api/v1/visualizacion/ficha-ocupacion",
        params={
            "pais": "ARG",
            "sector": "Tecnología",
            "area": "Ingeniería de Software",
            "fecha_desde": "2024",
            "fecha_hasta": "2025",
        },
    )
    assert resp.status_code == 200
    body = resp.json()

    # Verificar identificación única pais_codigo_iso3 + ocupacion_id y código CIUO-08 (API-003)
    ficha = body["ficha_ocupacion"]
    assert ficha["ocupacion_uid"] == "ARG_OCUP_01"
    assert ficha["ciuo_08"] == "2512"
    assert ficha["trazabilidad"]["fuente_oficial"] == "ILOSTAT"

    # Verificar que los registros estén dentro del rango de fechas solicitado (2024 - 2025)
    for row in body["datos_en_fechas"]:
        assert "2024" <= str(row["period"]) <= "2025"

    # Verificar que existan las comparativas contra el sector (4 ocupaciones de Tecnología en ARG según API-009)
    # y contra los 3 países de la región (ARG, CHL, URY)
    comp = body["comparativas"]
    assert comp["vs_sector_nacional"]["ocupaciones_comparadas_en_sector"] == 4
    paises_comparados = {c["pais_codigo_iso3"] for c in comp["vs_otros_paises_region"]}
    assert paises_comparados == {"ARG", "CHL", "URY"}


def test_flujo_3_home_a_regional_macro_3_paises():
    """
    Verifica: Home --> Regional --> Macro con los 3 países (ARG, CHL, URY).
    Comprueba los 135 registros del consolidado (45 por país) y 60 del catálogo (LOAD-009).
    """
    resp = client.get("/api/v1/visualizacion/regional")
    assert resp.status_code == 200
    body = resp.json()
    assert body["paises_incluidos"] == ["ARG", "CHL", "URY"]
    assert body["cobertura_global"]["total_registros_consolidado"] == 135
    assert body["cobertura_global"]["total_registros_catalogo_ocupaciones"] == 60
    assert len(body["macro_por_pais"]) == 3
    for pais_summary in body["macro_por_pais"]:
        assert pais_summary["registros_consolidado"] == 45
        assert pais_summary["ocupaciones_catalogo"] == 20