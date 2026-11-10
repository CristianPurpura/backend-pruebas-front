"""Normalización del payload de Data al contrato del Backend.

Aísla la forma interna del equipo de Data: si cambian los nombres de sus
campos, el ajuste queda acá y no en los endpoints.
"""

from __future__ import annotations

import re
from typing import Any

from app.schemas.datascience import (
    DataSourceMeta,
    GapItem,
    GapsResponse,
    SkillItem,
    SkillsResponse,
    TgsDesglose,
)
from app.services.datascience.metrics import (
    FACTOR_MADUREZ_PAIS,
    brecha_cobertura_pct,
    desglosar_tgs,
)

# Claves con las que Data envuelve cada lista.
CLAVE_BRECHAS = "brechas_y_habilidades"
CLAVE_COMPARATIVA = "comparativa_educativo_laboral"

_RE_PORCENTAJE = re.compile(r"([+-]?\d+(?:\.\d+)?)")


def _lista(payload: dict[str, Any], clave: str) -> list[dict[str, Any]]:
    """Extrae la lista de filas del payload de Data."""
    valor = payload.get(clave)
    if not isinstance(valor, list):
        return []
    return [fila for fila in valor if isinstance(fila, dict)]


def _texto(valor: Any, defecto: str = "") -> str:
    return str(valor) if valor not in (None, "") else defecto


def _numero(valor: Any) -> float | None:
    if valor is None or isinstance(valor, bool):
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def _porcentaje(valor: Any) -> float | None:
    """Extrae el número de textos como `"+9.1% anual"` que envía Data."""
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    if not isinstance(valor, str):
        return None
    match = _RE_PORCENTAJE.search(valor)
    return float(match.group(1)) if match else None


def _lista_texto(valor: Any) -> list[str]:
    if isinstance(valor, list):
        return [str(item) for item in valor if item not in (None, "")]
    if isinstance(valor, str) and valor.strip():
        return [parte.strip() for parte in valor.split(",") if parte.strip()]
    return []


def mapear_brechas(fila: dict[str, Any]) -> SkillItem:
    """Convierte una fila de `brechas_y_habilidades` en `SkillItem`."""
    pais = _texto(fila.get("pais_codigo_iso3")).upper()
    score_demanda = _numero(fila.get("score_demanda_mercado"))
    score_crecimiento = _numero(fila.get("score_crecimiento_estimado"))
    cce = _numero(fila.get("coeficiente_cobertura_educativa_cce"))

    desglose = None
    if score_demanda is not None or score_crecimiento is not None:
        desglose = TgsDesglose(
            **desglosar_tgs(score_demanda, score_crecimiento, cce, pais)
        )

    return SkillItem(
        pais=pais,
        pais_nombre=_texto(fila.get("pais_nombre")),
        sector=_texto(fila.get("sector")),
        ocupacion_id=_texto(fila.get("ocupacion_id")).upper(),
        ocupacion_nombre=_texto(fila.get("ocupacion_nombre")),
        ciuo08=_texto(fila.get("codigo_ciuo08_oit")),
        icol=_numero(fila.get("indice_oportunidad_icol")),
        score_brecha=_numero(fila.get("score_brecha_talento_100")) or 0.0,
        cce=cce,
        score_demanda_100=score_demanda,
        score_crecimiento_100=score_crecimiento,
        factor_madurez_pais=FACTOR_MADUREZ_PAIS.get(pais),
        brecha_cobertura_pct=brecha_cobertura_pct(cce),
        tgs_desglose=desglose,
        diagnostico=_texto(fila.get("diagnostico_brecha")),
        icono=_texto(fila.get("icono_brecha")),
        urgencia=_texto(fila.get("urgencia_intervencion")),
        habilidades_tradicionales=_lista_texto(fila.get("habilidades_tradicionales")),
        habilidades_emergentes=_lista_texto(fila.get("habilidades_emergentes_2026")),
        nivel_adopcion=_texto(fila.get("nivel_adopcion_habilidades")),
        impacto_ia=_texto(fila.get("impacto_ia_automatizacion")),
        obsolescencia=_texto(fila.get("velocidad_obsolescencia")),
    )


def mapear_comparativa(fila: dict[str, Any]) -> GapItem:
    """Convierte una fila de `comparativa_educativo_laboral` en `GapItem`."""
    return GapItem(
        pais=_texto(fila.get("pais_codigo_iso3")).upper(),
        pais_nombre=_texto(fila.get("pais_nombre")),
        sector=_texto(fila.get("sector")),
        carreras_afines=_lista_texto(fila.get("carreras_universitarias_afines")),
        egresados_anuales=_numero(fila.get("egresados_anuales_estimados")),
        demanda_anual=_numero(fila.get("demanda_anual_puestos_nuevos")),
        deficit_anual=_numero(fila.get("brecha_anual_puestos_deficit")),
        crecimiento_matricula_pct=_porcentaje(fila.get("crecimiento_matricula_anual")),
        cce=_numero(fila.get("coeficiente_cobertura_educativa_cce")),
        diagnostico=_texto(fila.get("diagnostico_descalce")),
        estado=_texto(fila.get("estado_alerta")),
        semaforo=_texto(fila.get("semaforo")),
        fuentes=_lista_texto(fila.get("fuentes_oficiales_cruzadas")),
    )


def respuesta_brechas(
    payload: dict[str, Any],
    fuente: str,
    actualizado: str | None,
    filtros: dict[str, Any],
) -> SkillsResponse:
    """Arma la respuesta de `/skills` a partir del payload de Data."""
    items = [mapear_brechas(fila) for fila in _lista(payload, CLAVE_BRECHAS)]
    return SkillsResponse(
        meta=DataSourceMeta(fuente=fuente, actualizado=actualizado),
        filtros=filtros,
        total=len(items),
        items=items,
    )


def respuesta_comparativa(
    payload: dict[str, Any],
    fuente: str,
    actualizado: str | None,
    filtros: dict[str, Any],
) -> GapsResponse:
    """Arma la respuesta de `/gaps` a partir del payload de Data."""
    items = [mapear_comparativa(fila) for fila in _lista(payload, CLAVE_COMPARATIVA)]
    return GapsResponse(
        meta=DataSourceMeta(fuente=fuente, actualizado=actualizado),
        filtros=filtros,
        total=len(items),
        items=items,
    )


__all__ = [
    "CLAVE_BRECHAS",
    "CLAVE_COMPARATIVA",
    "mapear_brechas",
    "mapear_comparativa",
    "respuesta_brechas",
    "respuesta_comparativa",
]
