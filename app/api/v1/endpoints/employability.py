"""Endpoint del Índice de Empleabilidad (IDELR + ICOL)."""

from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query

from app.core import catalogs
from app.schemas.employability import (
    DataSourceInfo,
    EmployabilityFilters,
    EmployabilityResponse,
    EmployabilitySummary,
    MethodologyInfo,
)
from app.services.calculators import (
    DEFAULT_ICOL_WEIGHTS,
    VARIABLES_IDELR,
    calcular_icol,
    calcular_idelr,
    expandir_ocupaciones,
    leer_datasets_normalizados,
    macro_scores,
)

router = APIRouter()


@router.get("", response_model=EmployabilityResponse)
def get_employability(
    pais: Annotated[str | None, Query(description="Código ISO-3 (ARG, CHL, URY)")] = None,
    sector: Annotated[str | None, Query(description="Sector productivo")] = None,
    ocupacion: Annotated[str | None, Query(description="Ocupación (OCUP_01..OCUP_20)")] = None,
    anio_inicio: Annotated[int | None, Query(ge=1900, le=2100)] = None,
    anio_fin: Annotated[int | None, Query(ge=1900, le=2100)] = None,
) -> EmployabilityResponse:
    """Índice de empleabilidad: serie macro (IDELR) y ranking por ocupación (ICOL).

    Los datos macro salen de los datasets normalizados (`data/processed/`); si
    todavía no hay ninguno, el ICOL usa los valores de referencia y la
    respuesta lo deja explícito en `fuente_datos`.
    """
    codigo_pais = pais.strip().upper() if pais else None
    if codigo_pais and codigo_pais not in catalogs.PAISES_INFO:
        raise HTTPException(
            status_code=400,
            detail=f"País fuera del alcance regional: {pais}. Permitidos: "
            f"{', '.join(catalogs.PAISES_INFO)}.",
        )

    id_ocupacion = ocupacion.strip().upper() if ocupacion else None
    if id_ocupacion and id_ocupacion not in catalogs.OCUPACIONES:
        raise HTTPException(
            status_code=400,
            detail=f"Ocupación fuera del catálogo: {ocupacion}. Permitidas: "
            f"{catalogs.OCUPACION_IDS[0]}..{catalogs.OCUPACION_IDS[-1]}.",
        )

    nombre_sector = sector.strip() if sector else None
    if nombre_sector and nombre_sector.lower() not in {
        nombre.lower() for nombre in catalogs.SECTORES.values()
    }:
        raise HTTPException(
            status_code=400,
            detail=f"Sector desconocido: {sector}. Permitidos: "
            f"{', '.join(catalogs.SECTORES.values())}.",
        )

    filas, archivos = leer_datasets_normalizados()
    # El entorno macro del ICOL se calcula sobre el panel completo (igual que
    # en la implementación de Data) y la serie mostrada sí respeta los filtros.
    macro = macro_scores(calcular_idelr(filas))
    serie = calcular_idelr(
        filas,
        pais_filtro=codigo_pais,
        anio_inicio=anio_inicio,
        anio_fin=anio_fin,
    )

    ocupaciones: list[dict[str, Any]] = expandir_ocupaciones()
    ranking = calcular_icol(
        ocupaciones,
        macro=macro or None,
        pais_filtro=codigo_pais,
        sector_filtro=nombre_sector,
    )
    if id_ocupacion:
        ranking = [fila for fila in ranking if fila["ocupacion_id"] == id_ocupacion]

    mejor = ranking[0] if ranking else None
    cobertura = serie[-1]["cobertura_variables_pct"] if serie else None

    return EmployabilityResponse(
        generated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        metodologia=MethodologyInfo(
            epsilon_pct=1.0,
            variables_idelr=VARIABLES_IDELR,
            ponderaciones_icol=DEFAULT_ICOL_WEIGHTS,
        ),
        fuente_datos=DataSourceInfo(
            tipo="processed" if archivos else "fallback",
            datasets=archivos,
            detalle=(
                "Datasets normalizados leídos de data/processed/"
                if archivos
                else "Sin datasets normalizados cargados: el ICOL usa los valores "
                "de referencia del entorno macro."
            ),
        ),
        filtros=EmployabilityFilters(
            pais=codigo_pais,
            sector=nombre_sector,
            ocupacion=id_ocupacion,
            anio_inicio=anio_inicio,
            anio_fin=anio_fin,
        ),
        serie_macro=serie,
        ranking_ocupaciones=ranking,
        resumen=EmployabilitySummary(
            paises_evaluados=len({fila["pais_codigo_iso3"] for fila in serie}),
            ocupaciones_evaluadas=len(ranking),
            indicadores_evaluados=len(VARIABLES_IDELR),
            cobertura_variables_pct=cobertura,
            mejor_ocupacion=(
                f"{mejor['ocupacion_id']} · {mejor['ocupacion_nombre']} ({mejor['pais_codigo_iso3']})"
                if mejor
                else None
            ),
            mejor_indice_ocupacional=mejor["indice_oportunidad_icol"] if mejor else None,
        ),
    )


__all__ = ["router"]
