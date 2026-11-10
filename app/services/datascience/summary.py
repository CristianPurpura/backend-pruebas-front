"""Agregados de oferta, demanda y brecha para el dashboard.

El Frontend no debe replicar fórmulas: este módulo calcula los totales y los
campos derivados de `GET /api/v1/gaps/summary` a partir del mismo payload de
Data que usa `GET /api/v1/gaps`.

Reglas:

* `deficit_bruto = Σ max(0, D − O)`
* `brecha_neta  = Σ (D − O)`
* `superavit_total = Σ max(0, O − D)`
* `CCE ponderado = Σ O / Σ D` (nunca promedio simple)
* las filas sin demanda u oferta no entran en los agregados
"""

from __future__ import annotations

from typing import Iterable

from app.schemas.datascience import (
    DataSourceMeta,
    GapItem,
    GapPaisResumen,
    GapSectorResumen,
    GapsSummaryResponse,
    GapTotales,
)
from app.services.datascience.metrics import brecha_cobertura_pct, clasificar_cce


def _totales(items: Iterable[GapItem]) -> GapTotales:
    """Calcula los agregados de un recorte (país, sector o región)."""
    validos = [
        item
        for item in items
        if item.demanda_anual is not None and item.egresados_anuales is not None
    ]

    demanda = sum(float(item.demanda_anual) for item in validos)
    egresados = sum(float(item.egresados_anuales) for item in validos)
    deficit_bruto = sum(
        max(0.0, float(item.demanda_anual) - float(item.egresados_anuales))
        for item in validos
    )
    brecha_neta = sum(
        float(item.demanda_anual) - float(item.egresados_anuales) for item in validos
    )
    superavit_total = sum(
        max(0.0, float(item.egresados_anuales) - float(item.demanda_anual))
        for item in validos
    )

    cce = round(egresados / demanda, 3) if demanda > 0 else None
    brecha = round(max(0.0, 1.0 - cce) * 100.0, 2) if cce is not None else None

    return GapTotales(
        demanda_anual=round(demanda, 2),
        egresados_anuales=round(egresados, 2),
        deficit_bruto=round(deficit_bruto, 2),
        brecha_neta=round(brecha_neta, 2),
        superavit_total=round(superavit_total, 2),
        cce_ponderado=cce,
        brecha_cobertura_pct=brecha,
    )


def _fila_sector(item: GapItem) -> GapSectorResumen:
    """Convierte una fila de `/gaps` en la fila enriquecida del resumen."""
    clasificacion = clasificar_cce(item.cce)

    deficit = item.deficit_anual
    if deficit is None and item.demanda_anual is not None and item.egresados_anuales is not None:
        deficit = round(max(0.0, float(item.demanda_anual) - float(item.egresados_anuales)), 2)

    return GapSectorResumen(
        pais=item.pais,
        pais_nombre=item.pais_nombre,
        sector=item.sector,
        demanda_anual=item.demanda_anual,
        egresados_anuales=item.egresados_anuales,
        deficit_anual=deficit,
        cce=item.cce,
        brecha_cobertura_pct=brecha_cobertura_pct(item.cce),
        crecimiento_matricula_pct=item.crecimiento_matricula_pct,
        estado_cce=clasificacion["estado"],
        semaforo=item.semaforo or clasificacion["semaforo"],
        diagnostico=item.diagnostico or clasificacion["diagnostico"],
        carreras_afines=list(item.carreras_afines),
        fuentes=list(item.fuentes),
        is_projection=item.is_projection,
    )


def construir_resumen(
    items: Iterable[GapItem],
    meta: DataSourceMeta,
    filtros: dict[str, object] | None = None,
) -> GapsSummaryResponse:
    """Arma la respuesta de `GET /api/v1/gaps/summary`."""
    filas = list(items)
    paises = sorted({item.pais for item in filas})

    por_pais: list[GapPaisResumen] = []
    for pais in paises:
        grupo = [item for item in filas if item.pais == pais]
        nombre = next((item.pais_nombre for item in grupo if item.pais_nombre), pais)
        por_pais.append(
            GapPaisResumen(
                pais=pais,
                pais_nombre=nombre,
                **_totales(grupo).model_dump(),
            )
        )

    return GapsSummaryResponse(
        meta=meta,
        filtros=dict(filtros or {}),
        total_sectores=len(filas),
        totales=_totales(filas),
        por_pais=por_pais,
        por_sector=[_fila_sector(item) for item in filas],
    )


__all__ = ["construir_resumen"]
