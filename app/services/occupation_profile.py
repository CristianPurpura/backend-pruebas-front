"""Perfil consolidado de una ocupación: catálogo + índice de oportunidad.

Reutiliza las mismas calculadoras que `GET /api/v1/employability`
(`calcular_idelr` + `calcular_icol`), de modo que el ICOL que se ve en el
perfil de una ocupación es **idéntico** al del ranking del endpoint de
empleabilidad: no hay dos fórmulas.
"""

from typing import Any

from app.core import catalogs
from app.services.calculators import (
    calcular_icol,
    calcular_idelr,
    expandir_ocupaciones,
    leer_datasets_normalizados,
    macro_scores,
)

# Origen del catálogo de ocupaciones (CIUO-08, demanda, crecimiento, habilidades).
CATALOGO_FUENTE = "Catálogo regional de ocupaciones (DataAnalyst)"
CATALOGO_FUENTE_URL = "https://github.com/InnovaLab-2C-2026-Equipo-6/DataAnalyst"
CATALOGO_ACTUALIZADO = "2026-10-15"


def construir_perfil(ocupacion_id: str, pais: str) -> dict[str, Any]:
    """Arma el perfil de `ocupacion_id` para `pais`, con comparación regional."""
    ficha = catalogs.resolve_occupation(ocupacion_id) or {}
    filas, archivos = leer_datasets_normalizados()

    # El entorno macro se calcula sobre el panel completo (igual que en el
    # endpoint de empleabilidad y en la implementación de Data).
    macro = macro_scores(calcular_idelr(filas))
    ranking = calcular_icol(expandir_ocupaciones(), macro=macro or None)

    combinaciones = [fila for fila in ranking if fila["ocupacion_id"] == ocupacion_id]
    perfil = next(
        (fila for fila in combinaciones if fila["pais_codigo_iso3"] == pais),
        None,
    )
    if perfil is None:  # pragma: no cover - los 60 pares siempre se calculan
        raise ValueError(f"Sin filas de ICOL para {ocupacion_id} / {pais}.")

    comparacion = _comparacion_paises(combinaciones, pais)

    return {
        "pais": {"codigo": pais, "nombre": catalogs.resolve_country(pais) or pais},
        "sector": catalogs.sector_info(ficha.get("sector")),
        "ocupacion": {
            "id": ocupacion_id,
            "nombre": ficha.get("nombre", ""),
            "ciuo08": ficha.get("ciuo08", ""),
        },
        "indicadores": {
            "nivel_demanda": perfil["nivel_demanda"],
            "crecimiento_anual_pct": perfil["crecimiento_anual_pct"],
            "icol": perfil["indice_oportunidad_icol"],
            "categoria_oportunidad": perfil["categoria_oportunidad"],
            "icono": perfil["icono"],
            "prioridad_formacion": perfil["prioridad_formacion"],
            "scores": {
                "demanda": perfil["score_demanda_100"],
                "crecimiento": perfil["score_crecimiento_100"],
                "entorno_macro": perfil["score_entorno_macro_100"],
            },
            "rankings": {
                "regional": perfil["ranking_regional"],
                "pais": perfil["ranking_pais"],
                "sector": perfil["ranking_sector"],
            },
        },
        "habilidades": catalogs.ocupacion_habilidades(ocupacion_id),
        "comparacion_paises": comparacion,
        "trazabilidad": {
            "fuente": CATALOGO_FUENTE,
            "fuente_url": CATALOGO_FUENTE_URL,
            "actualizado": CATALOGO_ACTUALIZADO,
            # Demanda y crecimiento del catálogo son estimaciones, no mediciones.
            "is_projection": True,
            "origen_indice": "processed" if archivos else "fallback",
            "datasets": list(archivos),
        },
    }


def _comparacion_paises(combinaciones: list[dict[str, Any]], pais_seleccionado: str) -> list[dict[str, Any]]:
    """Filas de los 3 países: el seleccionado primero y luego el orden del catálogo."""
    orden = [pais_seleccionado] + [codigo for codigo in catalogs.PAISES_INFO if codigo != pais_seleccionado]
    filas = {fila["pais_codigo_iso3"]: fila for fila in combinaciones}
    return [
        {
            "codigo": codigo,
            "nombre": filas[codigo]["pais_nombre"],
            "icol": filas[codigo]["indice_oportunidad_icol"],
            "ranking_pais": filas[codigo]["ranking_pais"],
            "categoria_oportunidad": filas[codigo]["categoria_oportunidad"],
        }
        for codigo in orden
        if codigo in filas
    ]


__all__ = ["construir_perfil"]
