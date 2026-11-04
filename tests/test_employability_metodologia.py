"""Tests de metodología visible del Índice de Empleabilidad.

El entregable de la issue #58 exige que las **dimensiones y ponderaciones
sean visibles**: el endpoint `GET /api/v1/employability` tiene que exponer
exactamente la configuración que usan los calculadores, sin divergencia
entre lo que se anuncia y lo que se calcula.

Este módulo cubre ese contrato:

* la suma de ponderaciones del IDELR y del ICOL es 1.0;
* el endpoint expone las 5 dimensiones del IDELR con sus pesos;
* `metodologia` del endpoint es espejo de `VARIABLES_IDELR` y
  `DEFAULT_ICOL_WEIGHTS` (mismos valores, no una copia desactualizada);
* los umbrales de `clasificar_categoria_oportunidad` son consistentes con
  las categorías que devuelve el endpoint.
"""

import pytest

from app.services.calculators.employability import (
    DEFAULT_ICOL_WEIGHTS,
    VARIABLES_IDELR,
    clasificar_categoria_oportunidad,
)

# Categorías de ICOL, de mayor a menor score, con su umbral inferior.
CATEGORIAS_ESPERADAS = [
    (85.0, "Oportunidad Excepcional"),
    (70.0, "Alta Oportunidad"),
    (55.0, "Oportunidad Moderada"),
    (None, "En Desarrollo / Emergente"),
]

DIMENSIONES_ESPERADAS = {"Economía", "Salarios", "Empleo", "Educación"}


# ---------------------------------------------------------------------------
# 1. Ponderaciones
# ---------------------------------------------------------------------------
def test_los_pesos_del_idelr_suman_uno():
    """Las cinco variables del IDELR reparten el 100 % del peso."""
    suma = sum(float(cfg["peso"]) for cfg in VARIABLES_IDELR.values())

    assert len(VARIABLES_IDELR) == 5
    assert suma == pytest.approx(1.0)


def test_los_pesos_del_icol_suman_uno():
    """Las tres componentes del ICOL reparten el 100 % del peso."""
    suma = sum(float(peso) for peso in DEFAULT_ICOL_WEIGHTS.values())

    assert len(DEFAULT_ICOL_WEIGHTS) == 3
    assert suma == pytest.approx(1.0)


def test_las_dimensiones_del_idelr_son_las_publicadas():
    """Las dimensiones del índice macro son las cinco de la metodología."""
    dimensiones = {cfg["dimension"] for cfg in VARIABLES_IDELR.values()}

    assert dimensiones == DIMENSIONES_ESPERADAS


def test_cada_variable_declara_polaridad_y_rango():
    """Cada indicador expone polaridad y rango teórico: es lo que ve el Frontend."""
    for nombre, cfg in VARIABLES_IDELR.items():
        assert cfg["polaridad"] in {"positiva", "negativa"}, nombre
        assert cfg["min_teorico"] < cfg["max_teorico"], nombre
        assert cfg["descripcion"], nombre
        assert 0.0 < float(cfg["peso"]) <= 1.0, nombre


# ---------------------------------------------------------------------------
# 2. El endpoint es espejo de los calculadores
# ---------------------------------------------------------------------------
def test_el_endpoint_expone_las_mismas_variables_que_el_calculador(client, output_dirs):
    """`metodologia.variables_idelr` es idéntico a `VARIABLES_IDELR`."""
    response = client.get("/api/v1/employability")

    assert response.status_code == 200
    variables = response.json()["metodologia"]["variables_idelr"]

    assert variables == VARIABLES_IDELR


def test_el_endpoint_expone_las_mismas_ponderaciones_icol(client, output_dirs):
    """`metodologia.ponderaciones_icol` es idéntico a `DEFAULT_ICOL_WEIGHTS`."""
    response = client.get("/api/v1/employability")

    assert response.status_code == 200
    ponderaciones = response.json()["metodologia"]["ponderaciones_icol"]

    assert ponderaciones == DEFAULT_ICOL_WEIGHTS
    assert sum(ponderaciones.values()) == pytest.approx(1.0)


def test_el_endpoint_declara_el_epsilon_y_la_normalizacion(client, output_dirs):
    """La banda muerta y el método de normalización quedan publicados."""
    response = client.get("/api/v1/employability")

    assert response.status_code == 200
    metodologia = response.json()["metodologia"]

    assert metodologia["epsilon_pct"] == 1.0
    assert "Min-Max" in metodologia["metodo_normalizacion"]
    assert metodologia["indice_macro"] == "IDELR"
    assert metodologia["indice_ocupacional"] == "ICOL"
    assert "DataAnalyst" in metodologia["fuente_metodologia"]


# ---------------------------------------------------------------------------
# 3. Umbrales de categoría
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("score", "categoria"),
    [
        (100.0, "Oportunidad Excepcional"),
        (85.0, "Oportunidad Excepcional"),
        (84.99, "Alta Oportunidad"),
        (70.0, "Alta Oportunidad"),
        (69.99, "Oportunidad Moderada"),
        (55.0, "Oportunidad Moderada"),
        (54.99, "En Desarrollo / Emergente"),
        (0.0, "En Desarrollo / Emergente"),
    ],
)
def test_los_umbrales_de_categoria_son_consistentes(score, categoria):
    """Cada umbral corta en la categoría correcta (borde incluido)."""
    assert clasificar_categoria_oportunidad(score)["categoria"] == categoria


def test_los_umbrales_coinciden_con_las_categorias_publicadas():
    """Los umbrales del calculador son los mismos que se publican arriba."""
    for umbral, categoria in CATEGORIAS_ESPERADAS:
        if umbral is None:
            continue
        assert clasificar_categoria_oportunidad(umbral)["categoria"] == categoria
        assert clasificar_categoria_oportunidad(umbral - 0.01)["categoria"] != categoria


def test_la_categoria_del_endpoint_corresponde_al_score(client, output_dirs):
    """Cada fila del ranking expone la categoría que le corresponde a su score."""
    response = client.get("/api/v1/employability")

    assert response.status_code == 200
    for fila in response.json()["ranking_ocupaciones"]:
        esperada = clasificar_categoria_oportunidad(fila["indice_oportunidad_icol"])
        assert fila["categoria_oportunidad"] == esperada["categoria"]
        assert fila["icono"] == esperada["icono"]


def test_el_endpoint_recibe_la_metodologia_sin_datasets(client, output_dirs):
    """La metodología se publica aunque el cálculo use valores de referencia."""
    response = client.get("/api/v1/employability")

    assert response.status_code == 200
    cuerpo = response.json()
    assert cuerpo["fuente_datos"]["tipo"] == "fallback"
    assert cuerpo["resumen"]["indicadores_evaluados"] == 5
    assert len(cuerpo["metodologia"]["variables_idelr"]) == 5
