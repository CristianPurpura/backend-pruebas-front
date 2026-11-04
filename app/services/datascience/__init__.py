"""Consumo del módulo de Data Science del equipo de Data (brechas y oferta formativa)."""

from app.services.datascience.client import (
    RUTA_BRECHAS,
    RUTA_COMPARATIVA,
    CacheData,
    RespuestaData,
    consultar_data,
    get_cache,
)
from app.services.datascience.mapper import (
    mapear_brechas,
    mapear_comparativa,
    respuesta_brechas,
    respuesta_comparativa,
)

__all__ = [
    "RUTA_BRECHAS",
    "RUTA_COMPARATIVA",
    "CacheData",
    "RespuestaData",
    "consultar_data",
    "get_cache",
    "mapear_brechas",
    "mapear_comparativa",
    "respuesta_brechas",
    "respuesta_comparativa",
]
