"""Tests del Índice de Empleabilidad (IDELR + ICOL).

Incluye un test de **paridad** contra la API del equipo Data: nuestra
reimplementación local debe devolver exactamente los mismos valores que
`/api/v1/analytics/indice-sintetico` y `/api/v1/analytics/ocupaciones/ranking`
del repo `DataAnalyst`.
"""

import io

import httpx
import pandas as pd
import pytest

from app.services.calculators.employability import (
    VARIABLES_IDELR,
    calcular_icol,
    calcular_idelr,
    expandir_ocupaciones,
    macro_scores,
    normalizar_valor,
    parse_tasa_crecimiento,
)

# Fixture de la API de Data (vive en el módulo de la matriz QA).
from tests.test_data_api_matrix import data_api  # noqa: F401

ANIO_INICIO = 2018
ANIO_FIN = 2024


def panel_sintetico() -> list[dict]:
    """Panel macro mínimo: 3 países × 2 años × 5 indicadores."""
    filas: list[dict] = []
    valores = {
        "Variación Anual del PIB Real": 2.0,
        "Índice de Salario Real": 95.0,
        "Tasa de Ocupación": 55.0,
        "Tasa de Finalización de Educación Secundaria": 70.0,
        "Tasa de Desocupación Total": 7.0,
    }
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
                        "fecha_extraccion": "2026-10-21",
                    }
                )
    return filas


def test_normalizacion_min_max_acotada():
    """La normalización respeta el rango [0, 100] y la polaridad."""
    assert normalizar_valor(10.0, 0.0, 20.0) == 50.0
    assert normalizar_valor(-5.0, 0.0, 20.0) == 0.0
    assert normalizar_valor(50.0, 0.0, 20.0) == 100.0
    assert normalizar_valor(10.0, 0.0, 20.0, polaridad="negativa") == 50.0
    assert normalizar_valor(5.0, 5.0, 5.0) == 50.0


def test_parse_tasa_crecimiento():
    """Se extrae la tasa numérica de textos como '+18.5% anual'."""
    assert parse_tasa_crecimiento("+18.5% anual") == 18.5
    assert parse_tasa_crecimiento("-6.4% anual") == -6.4
    assert parse_tasa_crecimiento(12) == 12.0
    assert parse_tasa_crecimiento("sin dato") == 0.0


def test_idelr_calcula_por_pais_y_anio():
    """El IDELR se calcula por país y año, con cobertura y desglose."""
    serie = calcular_idelr(panel_sintetico())

    assert len(serie) == 6  # 3 países × 2 años
    primera = serie[0]
    assert 0.0 <= primera["indice_sintetico"] <= 100.0
    assert primera["cobertura_variables_pct"] == 100.0
    assert primera["tendencia"] == "BASE"
    assert len(primera["desglose_variables"]) == 5


def test_idelr_respeta_filtros():
    """Los filtros de país y año recortan la serie."""
    serie = calcular_idelr(panel_sintetico(), pais_filtro="URY", anio_inicio=2023)

    assert len(serie) == 1
    assert serie[0]["pais_codigo_iso3"] == "URY"
    assert serie[0]["anio"] == 2023


def test_icol_cubre_las_60_combinaciones():
    """El ICOL evalúa 3 países × 20 ocupaciones y respeta el rango [0, 100]."""
    ranking = calcular_icol(expandir_ocupaciones())

    assert len(ranking) == 60
    assert all(0.0 <= fila["indice_oportunidad_icol"] <= 100.0 for fila in ranking)
    rangos = {fila["ranking_regional"] for fila in ranking}
    assert min(rangos) == 1
    assert rangos.issubset(set(range(1, 61)))
    # Los empates comparten posición (método 'min', igual que en Data).
    por_score: dict[float, set[int]] = {}
    for fila in ranking:
        por_score.setdefault(fila["indice_oportunidad_icol"], set()).add(fila["ranking_regional"])
    assert all(len(positions) == 1 for positions in por_score.values())
    assert ranking[0]["ranking_regional"] == 1
    assert ranking[0]["indice_oportunidad_icol"] >= ranking[-1]["indice_oportunidad_icol"]


def test_icol_usa_el_entorno_macro():
    """Un IDELR más alto para un país eleva su ICOL."""
    sin_macro = calcular_icol(expandir_ocupaciones())
    con_macro = calcular_icol(
        expandir_ocupaciones(), macro={"ARG": 90.0, "CHL": 90.0, "URY": 90.0}
    )

    indice_arg_sin = [f for f in sin_macro if f["pais_codigo_iso3"] == "ARG"][0]
    indice_arg_con = [f for f in con_macro if f["pais_codigo_iso3"] == "ARG"][0]
    assert indice_arg_con["indice_oportunidad_icol"] > indice_arg_sin["indice_oportunidad_icol"]


def test_endpoint_responde_con_el_indice(client, output_dirs):
    """GET /employability devuelve la serie macro y el ranking por ocupación."""
    response = client.get("/api/v1/employability")

    assert response.status_code == 200
    body = response.json()
    assert body["metodologia"]["indice_macro"] == "IDELR"
    assert body["metodologia"]["indice_ocupacional"] == "ICOL"
    assert body["fuente_datos"]["tipo"] == "fallback"
    assert body["resumen"]["ocupaciones_evaluadas"] == 60
    assert len(body["ranking_ocupaciones"]) == 60
    assert body["serie_macro"] == []


def test_endpoint_filtra_por_pais_sector_y_ocupacion(client, output_dirs):
    """Los filtros del endpoint acotan el ranking y validan los valores."""
    response = client.get("/api/v1/employability?pais=URY&sector=Tecnología")

    assert response.status_code == 200
    body = response.json()
    assert body["resumen"]["ocupaciones_evaluadas"] == 4
    assert all(fila["pais_codigo_iso3"] == "URY" for fila in body["ranking_ocupaciones"])

    response = client.get("/api/v1/employability?ocupacion=OCUP_02")
    assert response.status_code == 200
    body = response.json()
    assert body["resumen"]["ocupaciones_evaluadas"] == 3
    assert all(fila["ocupacion_id"] == "OCUP_02" for fila in body["ranking_ocupaciones"])


def test_endpoint_rechaza_filtros_invalidos(client, output_dirs):
    """Un país, sector u ocupación fuera de catálogo devuelven 400."""
    assert client.get("/api/v1/employability?pais=BRA").status_code == 400
    assert client.get("/api/v1/employability?sector=Automotriz").status_code == 400
    assert client.get("/api/v1/employability?ocupacion=OCUP_99").status_code == 400


def test_paridad_idelr_con_la_api_de_data(data_api):
    """Nuestro IDELR coincide con `/api/v1/analytics/indice-sintetico` de Data."""
    response = httpx.get(f"{data_api}/api/v1/consolidado/descargar", timeout=60.0)
    assert response.status_code == 200

    dataframe = pd.read_csv(io.BytesIO(response.content), encoding="utf-8-sig")
    filas = dataframe.to_dict(orient="records")

    nuestro = {
        (fila["pais_codigo_iso3"], fila["anio"]): fila
        for fila in calcular_idelr(filas, anio_inicio=ANIO_INICIO, anio_fin=ANIO_FIN)
    }

    theirs = httpx.get(
        f"{data_api}/api/v1/analytics/indice-sintetico",
        params={"anio_inicio": ANIO_INICIO, "anio_fin": ANIO_FIN},
        timeout=120.0,
    ).json()["serie_historica"]

    assert len(theirs) == len(nuestro)
    for fila in theirs:
        clave = (fila["pais_codigo_iso3"], fila["anio"])
        nuestro_fila = nuestro[clave]
        assert nuestro_fila["indice_sintetico"] == fila["indice_sintetico"], clave
        assert nuestro_fila["cobertura_variables_pct"] == fila["cobertura_variables_pct"], clave
        assert nuestro_fila["tendencia"] == fila["tendencia"], clave


def test_paridad_icol_con_la_api_de_data(data_api):
    """Nuestro ICOL coincide con `/api/v1/analytics/ocupaciones/ranking` de Data."""
    response = httpx.get(f"{data_api}/api/v1/consolidado/descargar", timeout=60.0)
    dataframe = pd.read_csv(io.BytesIO(response.content), encoding="utf-8-sig")
    filas = dataframe.to_dict(orient="records")

    macro = macro_scores(calcular_idelr(filas))
    nuestro = {
        (fila["pais_codigo_iso3"], fila["ocupacion_id"]): fila
        for fila in calcular_icol(expandir_ocupaciones(), macro=macro)
    }

    theirs = httpx.get(
        f"{data_api}/api/v1/analytics/ocupaciones/ranking", timeout=120.0
    ).json()["ranking_ocupaciones"]

    assert len(theirs) == len(nuestro) == 60
    for fila in theirs:
        clave = (fila["pais_codigo_iso3"], fila["ocupacion_id"])
        nuestro_fila = nuestro[clave]
        assert nuestro_fila["indice_oportunidad_icol"] == fila["indice_oportunidad_icol"], clave
        assert nuestro_fila["ranking_regional"] == fila["ranking_regional"], clave
        assert nuestro_fila["categoria_oportunidad"] == fila["categoria_oportunidad"], clave
