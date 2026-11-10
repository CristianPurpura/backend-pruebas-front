"""Métricas de brecha educativo-laboral y Talent Gap Score (TGS).

Reúne las constantes y fórmulas publicadas por el equipo de Data en
`DataAnalyst/etl/data_science.py`, para que los endpoints del Backend
calculen y clasifiquen con una única fuente de verdad.

Fórmula oficial del TGS:

    TGS = min(100, (0.55 * demanda + 0.25 * crecimiento
                    + 0.20 * max(0, 1 - CCE) * 100) * factor_pais)

donde `CCE = egresados_anuales / demanda_anual` del sector.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# 1. Constantes oficiales (espejo de DataAnalyst)
# ---------------------------------------------------------------------------
TGS_PESOS: dict[str, float] = {
    "demanda": 0.55,
    "crecimiento": 0.25,
    "cobertura": 0.20,
}

FACTOR_MADUREZ_PAIS: dict[str, float] = {
    "URY": 1.05,
    "CHL": 1.00,
    "ARG": 0.95,
}

CCE_UMBRALES: dict[str, float] = {
    "critico": 0.60,
    "alerta": 0.85,
    "equilibrio": 1.20,
}

TGS_UMBRALES: dict[str, float] = {
    "critico": 82.0,
    "moderado": 68.0,
    "equilibrio": 50.0,
}

R3_UMBRALES: dict[str, float] = {
    "deficit": 0.60,
    "superavit": 1.40,
}

DIAGNOSTICOS_CCE: dict[str, dict[str, str]] = {
    "CRITICA": {
        "estado": "CRITICA",
        "semaforo": "🔴",
        "diagnostico": "Déficit Formativo Severo (Alerta Roja)",
    },
    "ALERTA": {
        "estado": "ALERTA",
        "semaforo": "🟡",
        "diagnostico": "Déficit Formativo Moderado",
    },
    "ESTABLE": {
        "estado": "ESTABLE",
        "semaforo": "🟢",
        "diagnostico": "Equilibrio Formativo-Laboral",
    },
    "ATENCION": {
        "estado": "ATENCION",
        "semaforo": "🔵",
        "diagnostico": "Superávit Formativo / Riesgo de Desempleo Técnico",
    },
    "SIN_DATOS": {
        "estado": "SIN_DATOS",
        "semaforo": "⚪",
        "diagnostico": "Sin datos de cobertura educativa",
    },
}

DIAGNOSTICOS_TGS: dict[str, dict[str, str]] = {
    "CRITICO": {
        "diagnostico": "Déficit Crítico de Talento",
        "icono": "🔴",
        "prioridad": "Prioridad 1: Formación Acelerada Inmediata",
    },
    "MODERADO": {
        "diagnostico": "Déficit Moderado de Especialistas",
        "icono": "🟡",
        "prioridad": "Prioridad 2: Actualización de Currículas",
    },
    "EQUILIBRIO": {
        "diagnostico": "Equilibrio Oferta-Demanda",
        "icono": "🟢",
        "prioridad": "Prioridad 3: Monitoreo Regular",
    },
    "SUPERAVIT": {
        "diagnostico": "Superávit Relativo / Saturación",
        "icono": "🔵",
        "prioridad": "Prioridad 4: Reconversión Hacia Nichos",
    },
    "SIN_DATOS": {
        "diagnostico": "Sin datos de brecha",
        "icono": "⚪",
        "prioridad": "Sin prioridad asignada",
    },
}


# ---------------------------------------------------------------------------
# 2. Utilidades internas
# ---------------------------------------------------------------------------
def _score(valor: float | None) -> float:
    """Convierte un score opcional a float (0.0 si falta)."""
    return float(valor) if valor is not None else 0.0


def _factor_pais(pais: str | None) -> float:
    """Factor de madurez del país; 1.0 si no está en el catálogo."""
    return FACTOR_MADUREZ_PAIS.get(str(pais or "").strip().upper(), 1.0)


def _componente_cobertura(cce: float | None) -> float:
    """Componente de déficit de cobertura: `max(0, 1 - CCE) * 100`."""
    if cce is None:
        return 0.0
    return max(0.0, 1.0 - float(cce)) * 100.0


# ---------------------------------------------------------------------------
# 3. Funciones públicas
# ---------------------------------------------------------------------------
def clasificar_cce(cce: float | None) -> dict[str, str]:
    """Clasifica el Coeficiente de Cobertura Educativa con los umbrales de Data.

    Devuelve `{estado, semaforo, diagnostico}`. `None` se reporta como
    `SIN_DATOS` en lugar de asumir un valor.
    """
    if cce is None:
        return dict(DIAGNOSTICOS_CCE["SIN_DATOS"])
    valor = float(cce)
    if valor < CCE_UMBRALES["critico"]:
        return dict(DIAGNOSTICOS_CCE["CRITICA"])
    if valor < CCE_UMBRALES["alerta"]:
        return dict(DIAGNOSTICOS_CCE["ALERTA"])
    if valor <= CCE_UMBRALES["equilibrio"]:
        return dict(DIAGNOSTICOS_CCE["ESTABLE"])
    return dict(DIAGNOSTICOS_CCE["ATENCION"])


def clasificar_tgs(tgs: float | None) -> dict[str, str]:
    """Clasifica el Talent Gap Score en la escala cualitativa de Data."""
    if tgs is None:
        return dict(DIAGNOSTICOS_TGS["SIN_DATOS"])
    valor = float(tgs)
    if valor >= TGS_UMBRALES["critico"]:
        return dict(DIAGNOSTICOS_TGS["CRITICO"])
    if valor >= TGS_UMBRALES["moderado"]:
        return dict(DIAGNOSTICOS_TGS["MODERADO"])
    if valor >= TGS_UMBRALES["equilibrio"]:
        return dict(DIAGNOSTICOS_TGS["EQUILIBRIO"])
    return dict(DIAGNOSTICOS_TGS["SUPERAVIT"])


def brecha_cobertura_pct(cce: float | None) -> float | None:
    """Brecha de cobertura en porcentaje: `max(0, 1 - CCE) * 100`.

    Es el complemento de la cobertura: 0 % indica que los egresados cubren
    toda la demanda; 100 % indica que no hay egresados para esa demanda.
    Devuelve `None` cuando no hay CCE.
    """
    if cce is None:
        return None
    return round(_componente_cobertura(cce), 2)


def calcular_tgs(
    score_demanda: float | None,
    score_crecimiento: float | None,
    cce: float | None,
    pais: str | None,
) -> float:
    """Calcula el Talent Gap Score (0-100) con la fórmula oficial de Data."""
    base = (
        TGS_PESOS["demanda"] * _score(score_demanda)
        + TGS_PESOS["crecimiento"] * _score(score_crecimiento)
        + TGS_PESOS["cobertura"] * _componente_cobertura(cce)
    )
    return round(min(max(base * _factor_pais(pais), 0.0), 100.0), 2)


def desglosar_tgs(
    score_demanda: float | None,
    score_crecimiento: float | None,
    cce: float | None,
    pais: str | None,
) -> dict[str, Any]:
    """Desglosa el TGS en sus tres componentes y el factor país.

    Es el bloque que consume el Frontend para explicar el score en un tooltip:
    cada componente informa su score/brecha, su peso y su aporte.
    """
    demanda = _score(score_demanda)
    crecimiento = _score(score_crecimiento)
    brecha = _componente_cobertura(cce)
    factor = _factor_pais(pais)

    return {
        "demanda": {
            "score": round(demanda, 2),
            "peso": TGS_PESOS["demanda"],
            "aporte": round(TGS_PESOS["demanda"] * demanda, 2),
        },
        "crecimiento": {
            "score": round(crecimiento, 2),
            "peso": TGS_PESOS["crecimiento"],
            "aporte": round(TGS_PESOS["crecimiento"] * crecimiento, 2),
        },
        "cobertura": {
            "brecha_pct": round(brecha, 2),
            "peso": TGS_PESOS["cobertura"],
            "aporte": round(TGS_PESOS["cobertura"] * brecha, 2),
        },
        "factor_pais": factor,
        "tgs_calculado": calcular_tgs(demanda, crecimiento, cce, pais),
    }


__all__ = [
    "CCE_UMBRALES",
    "DIAGNOSTICOS_CCE",
    "DIAGNOSTICOS_TGS",
    "FACTOR_MADUREZ_PAIS",
    "R3_UMBRALES",
    "TGS_PESOS",
    "TGS_UMBRALES",
    "brecha_cobertura_pct",
    "calcular_tgs",
    "clasificar_cce",
    "clasificar_tgs",
    "desglosar_tgs",
]
