"""Calculadoras de índices (IDELR / ICOL)."""

from app.services.calculators.employability import (
    DEFAULT_ICOL_WEIGHTS,
    VARIABLES_IDELR,
    calcular_icol,
    calcular_idelr,
    expandir_ocupaciones,
    macro_scores,
)
from app.services.calculators.datasets import leer_datasets_normalizados

__all__ = [
    "DEFAULT_ICOL_WEIGHTS",
    "VARIABLES_IDELR",
    "calcular_icol",
    "calcular_idelr",
    "expandir_ocupaciones",
    "leer_datasets_normalizados",
    "macro_scores",
]
