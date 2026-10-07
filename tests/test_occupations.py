"""Tests de GET /api/v1/occupations/{occupation_id}.

Mapeo con docs/Casos_Apis_CargaDatos - 22092026.csv:
  API-012 (parcial): trazabilidad - fuente y fecha de extraccion de los datos.
    Hoy el mock expone traceability.source / retrieved_at / last_updated en lugar
    de fuente_oficial / fecha_extraccion (campos todavia no implementados).
  API-013 (parcial): distincion dato fuente vs calculado via traceability.data_type.
Los tests 200/404 son extra (endpoint no figura en la matriz).
"""

OCCUPATION_URL = "/api/v1/occupations/OCUP_01"


def test_occupation_ocup_01_devuelve_200(client):
    response = client.get(OCCUPATION_URL)

    assert response.status_code == 200
    body = response.json()
    assert body["occupation"]["id"] == "OCUP_01"
    assert body["country"]["code"] == "ARG"
    assert body["sector"]["id"] == "TEC"


def test_occupation_desconocida_devuelve_404(client):
    response = client.get("/api/v1/occupations/OCUP_99")

    assert response.status_code == 404
    assert response.json()["detail"] == "Ocupación no encontrada"


def test_api_012_trazabilidad_fuente_y_fecha(client):
    """API-012: se puede saber de qué fuente viene cada dato y cuándo fue extraído."""
    traceability = client.get(OCCUPATION_URL).json()["traceability"]

    assert traceability["source"]
    assert traceability["source_url"]
    assert traceability["last_updated"]
    assert traceability["retrieved_at"]


def test_api_013_dato_fuente_identificado_por_data_type(client):
    """API-013: se diferencia un dato original de uno calculado (data_type)."""
    traceability = client.get(OCCUPATION_URL).json()["traceability"]

    assert traceability["data_type"] in {"observed", "projected"}
    assert traceability["data_type"] == "observed"
