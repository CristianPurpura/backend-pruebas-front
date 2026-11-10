"""Tests del núcleo metodológico de brechas y Talent Gap Score (TGS).

Verifican que las constantes y fórmulas del Backend sean espejo de las
publicadas por Data (`DataAnalyst/etl/data_science.py`, commit `45abdfc`):

* los pesos del TGS suman 1.0;
* los umbrales de CCE y TGS se aplican en el borde exacto;
* `calcular_tgs` reproduce los 60 valores del snapshot de referencia;
* el desglose reconstruye el score que ve el Frontend.
"""

import json
from pathlib import Path

import pytest

from app.services.datascience.metrics import (
    CCE_UMBRALES,
    FACTOR_MADUREZ_PAIS,
    TGS_PESOS,
    TGS_UMBRALES,
    brecha_cobertura_pct,
    calcular_tgs,
    clasificar_cce,
    clasificar_tgs,
    desglosar_tgs,
)

REFERENCIA = Path(__file__).resolve().parents[1] / "data" / "reference" / "brechas.json"


# ---------------------------------------------------------------------------
# 1. Constantes
# ---------------------------------------------------------------------------
def test_los_pesos_del_tgs_suman_uno():
    """Las tres componentes del TGS reparten el 100 % del peso."""
    assert len(TGS_PESOS) == 3
    assert sum(TGS_PESOS.values()) == pytest.approx(1.0)


def test_los_factores_de_madurez_son_los_de_data():
    """El factor país coincide con `PAIS_FACTOR_MADUREZ_MAP` de Data."""
    assert FACTOR_MADUREZ_PAIS == {"URY": 1.05, "CHL": 1.00, "ARG": 0.95}


def test_los_umbrales_publicados_son_los_de_data():
    """Los cortes de CCE y TGS son los documentados por Data."""
    assert CCE_UMBRALES == {"critico": 0.60, "alerta": 0.85, "equilibrio": 1.20}
    assert TGS_UMBRALES == {"critico": 82.0, "moderado": 68.0, "equilibrio": 50.0}


# ---------------------------------------------------------------------------
# 2. Clasificación de CCE
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("cce", "estado", "semaforo"),
    [
        (0.0, "CRITICA", "🔴"),
        (0.599, "CRITICA", "🔴"),
        (0.60, "ALERTA", "🟡"),
        (0.849, "ALERTA", "🟡"),
        (0.85, "ESTABLE", "🟢"),
        (1.20, "ESTABLE", "🟢"),
        (1.201, "ATENCION", "🔵"),
        (1.50, "ATENCION", "🔵"),
    ],
)
def test_clasificar_cce_en_el_borde(cce, estado, semaforo):
    """Cada umbral corta en el estado correcto (borde incluido)."""
    resultado = clasificar_cce(cce)

    assert resultado["estado"] == estado
    assert resultado["semaforo"] == semaforo
    assert resultado["diagnostico"]


def test_clasificar_cce_sin_datos():
    """La ausencia de CCE no se interpreta como crítico ni como equilibrio."""
    resultado = clasificar_cce(None)

    assert resultado["estado"] == "SIN_DATOS"
    assert resultado["semaforo"] == "⚪"


# ---------------------------------------------------------------------------
# 3. Brecha de cobertura
# ---------------------------------------------------------------------------
def test_brecha_cobertura_pct():
    """La brecha es el complemento de la cobertura, acotado a [0, 100]."""
    assert brecha_cobertura_pct(0.571) == 42.9
    assert brecha_cobertura_pct(1.0) == 0.0
    assert brecha_cobertura_pct(1.5) == 0.0
    assert brecha_cobertura_pct(None) is None


# ---------------------------------------------------------------------------
# 4. TGS: paridad con el snapshot de Data
# ---------------------------------------------------------------------------
def test_calcular_tgs_reproduce_la_referencia():
    """Los 60 valores de `brechas.json` se recalculan con error <= 0.01."""
    filas = json.loads(REFERENCIA.read_text(encoding="utf-8"))["brechas_y_habilidades"]

    assert len(filas) == 60
    for fila in filas:
        calculado = calcular_tgs(
            fila["score_demanda_mercado"],
            fila["score_crecimiento_estimado"],
            fila["coeficiente_cobertura_educativa_cce"],
            fila["pais_codigo_iso3"],
        )
        assert calculado == pytest.approx(fila["score_brecha_talento_100"], abs=0.01)


def test_calcular_tgs_sin_scores_no_rompe():
    """Un payload incompleto devuelve un score acotado, no una excepción."""
    assert calcular_tgs(None, None, None, "ARG") == 0.0
    assert calcular_tgs(100.0, 100.0, 0.0, "ARG") <= 100.0


# ---------------------------------------------------------------------------
# 5. Desglose para el Frontend
# ---------------------------------------------------------------------------
def test_desglosar_tgs_reconstruye_el_score():
    """El desglose de URY / OCUP_02 coincide con el valor publicado."""
    desglose = desglosar_tgs(100.0, 80.0, 0.571, "URY")

    assert desglose["demanda"] == {"score": 100.0, "peso": 0.55, "aporte": 55.0}
    assert desglose["crecimiento"] == {"score": 80.0, "peso": 0.25, "aporte": 20.0}
    assert desglose["cobertura"] == {"brecha_pct": 42.9, "peso": 0.20, "aporte": 8.58}
    assert desglose["factor_pais"] == 1.05
    assert desglose["tgs_calculado"] == 87.76


def test_desglosar_tgs_incluye_el_factor_pais():
    """El mismo perfil rinde distinto según el factor de madurez del país."""
    ury = desglosar_tgs(100.0, 80.0, 0.571, "URY")
    arg = desglosar_tgs(100.0, 80.0, 0.571, "ARG")

    assert ury["factor_pais"] == 1.05
    assert arg["factor_pais"] == 0.95
    assert ury["tgs_calculado"] > arg["tgs_calculado"]


# ---------------------------------------------------------------------------
# 6. Clasificación de TGS
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("tgs", "diagnostico"),
    [
        (100.0, "Déficit Crítico de Talento"),
        (82.0, "Déficit Crítico de Talento"),
        (81.99, "Déficit Moderado de Especialistas"),
        (68.0, "Déficit Moderado de Especialistas"),
        (67.99, "Equilibrio Oferta-Demanda"),
        (50.0, "Equilibrio Oferta-Demanda"),
        (49.99, "Superávit Relativo / Saturación"),
        (0.0, "Superávit Relativo / Saturación"),
    ],
)
def test_clasificar_tgs_en_el_borde(tgs, diagnostico):
    """La escala cualitativa del TGS corta en los umbrales de Data."""
    assert clasificar_tgs(tgs)["diagnostico"] == diagnostico


def test_clasificar_tgs_sin_datos():
    """Un TGS ausente se reporta como sin datos."""
    assert clasificar_tgs(None)["diagnostico"] == "Sin datos de brecha"
