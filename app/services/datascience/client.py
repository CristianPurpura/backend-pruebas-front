"""Cliente de la API del equipo de Data (repo `DataAnalyst`).

El módulo de Data Science (brechas de talento, habilidades emergentes y
comparativa educativo-laboral) vive en `DataAnalyst` y se consume por HTTP
desde el Backend, en lugar de reimplementar sus fórmulas.

Robustez en tres niveles, para que el frontend nunca se quede sin datos:

1. **live**: la API de Data responde.
2. **cache**: la API falló, pero hay una respuesta reciente en memoria (TTL).
3. **reference**: la API falló y no hay cache; se usa el snapshot de
   referencia commiteado en `data/reference/`.

Si no hay ninguna de las tres, el cliente devuelve `None` y el endpoint
responde 503.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from app.core.config import get_settings

# Rutas del módulo de Data Science que consume el Backend.
RUTA_BRECHAS = "/api/v1/ds/brechas-habilidades"
RUTA_COMPARATIVA = "/api/v1/ds/comparativa-educativo-laboral"

# Snapshot de referencia commiteado (último recurso).
ARCHIVO_REFERENCIA = {
    RUTA_BRECHAS: "brechas.json",
    RUTA_COMPARATIVA: "comparativa.json",
}


@dataclass
class RespuestaData:
    """Respuesta de la API de Data con su procedencia."""

    datos: dict[str, Any]
    fuente: str  # "live" | "cache" | "reference"
    actualizado: str | None = None


class CacheData:
    """Cache en memoria con TTL, por ruta + parámetros."""

    def __init__(self) -> None:
        self._entradas: dict[str, tuple[float, dict[str, Any]]] = {}

    @staticmethod
    def _clave(ruta: str, params: dict[str, Any]) -> str:
        return ruta + "?" + "&".join(f"{k}={v}" for k, v in sorted(params.items()))

    def get(self, ruta: str, params: dict[str, Any], ttl: int) -> dict[str, Any] | None:
        entrada = self._entradas.get(self._clave(ruta, params))
        if entrada is None:
            return None
        guardado_en, datos = entrada
        if time.monotonic() - guardado_en > ttl:
            return None
        return datos

    def set(self, ruta: str, params: dict[str, Any], datos: dict[str, Any]) -> None:
        self._entradas[self._clave(ruta, params)] = (time.monotonic(), datos)

    def clear(self) -> None:
        self._entradas.clear()


_cache = CacheData()


def get_cache() -> CacheData:
    """Cache compartida (singleton) del módulo."""
    return _cache


def _leer_referencia(ruta: str, reference_dir: str | None = None) -> tuple[dict[str, Any], str] | None:
    """Lee el snapshot de referencia commiteado para una ruta."""
    nombre = ARCHIVO_REFERENCIA.get(ruta)
    if not nombre:
        return None
    base = Path(reference_dir or get_settings().reference_dir)
    archivo = base / nombre
    if not archivo.exists():
        return None
    try:
        datos = json.loads(archivo.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    actualizado = str(datos.get("_actualizado") or "")
    return datos, actualizado


async def consultar_data(
    ruta: str,
    params: dict[str, Any] | None = None,
    client: httpx.AsyncClient | None = None,
) -> RespuestaData | None:
    """Consulta la API de Data con cache y fallback a la referencia.

    Devuelve `None` si no hay ninguna fuente disponible (ni live, ni cache,
    ni referencia): en ese caso el endpoint debe responder 503.
    """
    settings = get_settings()
    parametros = {k: v for k, v in (params or {}).items() if v is not None}
    url = settings.data_api_url.rstrip("/") + ruta

    # 1) live
    try:
        if client is not None:
            respuesta = await client.get(ruta, params=parametros)
        else:
            async with httpx.AsyncClient(
                timeout=settings.data_api_timeout, base_url=settings.data_api_url.rstrip("/")
            ) as cliente:
                respuesta = await cliente.get(ruta, params=parametros)
        respuesta.raise_for_status()
        datos = respuesta.json()
        _cache.set(ruta, parametros, datos)
        return RespuestaData(datos=datos, fuente="live")
    except (httpx.HTTPError, ValueError):
        pass

    # 2) cache
    cacheado = _cache.get(ruta, parametros, settings.data_cache_ttl)
    if cacheado is not None:
        return RespuestaData(datos=cacheado, fuente="cache")

    # 3) referencia
    referencia = _leer_referencia(ruta)
    if referencia is not None:
        datos, actualizado = referencia
        return RespuestaData(datos=datos, fuente="reference", actualizado=actualizado)

    return None


__all__ = [
    "ARCHIVO_REFERENCIA",
    "RUTA_BRECHAS",
    "RUTA_COMPARATIVA",
    "CacheData",
    "RespuestaData",
    "consultar_data",
    "get_cache",
]
