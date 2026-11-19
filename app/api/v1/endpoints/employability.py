"""Endpoint del Índice de Empleabilidad (IDELR + ICOL)."""

from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import catalogs
from app.core.database import get_db_opcional
from app.core.validation import validar_ocupacion, validar_pais, validar_tipo
from app.schemas.employability import (
    DataSourceInfo,
    EmployabilityFilters,
    EmployabilityResponse,
    EmployabilitySummary,
    MethodologyInfo,
)
from app.schemas.indicator_series import SerieFiltros, SeriesResponse, TrendsResponse
from app.services.calculators import (
    DEFAULT_ICOL_WEIGHTS,
    VARIABLES_IDELR,
    calcular_icol,
    calcular_idelr,
    expandir_ocupaciones,
    leer_datasets_normalizados,
    macro_scores,
)
from app.services.calculators import series as series_service
from app.services.persistence import results_store

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
    codigo_pais = validar_pais(pais)
    id_ocupacion = validar_ocupacion(ocupacion)

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


def _validar_rango(anio_desde: int | None, anio_hasta: int | None) -> None:
    if anio_desde is not None and anio_hasta is not None and anio_desde > anio_hasta:
        raise HTTPException(
            status_code=400,
            detail="anio_desde no puede ser mayor que anio_hasta.",
        )


async def _construir_serie(
    session: AsyncSession | None,
    *,
    tipo: str,
    pais: str | None,
    ocupacion: str | None,
    anio_desde: int | None,
    anio_hasta: int | None,
) -> tuple[list[dict[str, Any]], str, str]:
    """Arma los puntos de la serie y devuelve también su procedencia."""
    if tipo == "ICOL":
        if session is not None:
            try:
                filas = await results_store.history(
                    session,
                    tipo="ICOL",
                    pais=pais,
                    ocupacion_id=ocupacion,
                    anio_desde=anio_desde,
                    anio_hasta=anio_hasta,
                    limite=5000,
                )
            except SQLAlchemyError:
                filas = []
            if filas:
                return (
                    series_service.serie_desde_snapshots(filas),
                    "database",
                    f"{len(filas)} snapshot(s) ICOL leídos de la base de datos.",
                )

        filas_datos, _ = leer_datasets_normalizados()
        serie_macro = calcular_idelr(filas_datos)
        ranking = calcular_icol(
            expandir_ocupaciones(),
            macro=macro_scores(serie_macro) or None,
            pais_filtro=pais,
        )
        if ocupacion:
            ranking = [fila for fila in ranking if fila["ocupacion_id"] == ocupacion]

        anio_referencia = max((fila["anio"] for fila in serie_macro), default=None)
        if anio_referencia is not None:
            if anio_desde is not None and anio_referencia < anio_desde:
                ranking = []
            if anio_hasta is not None and anio_referencia > anio_hasta:
                ranking = []

        return (
            series_service.serie_icol_live(ranking, anio_referencia),
            "live",
            "Sin snapshots ICOL guardados: se devuelve el cálculo actual "
            "como un único punto.",
        )

    filas, archivos = leer_datasets_normalizados()
    serie = calcular_idelr(
        filas,
        pais_filtro=pais,
        anio_inicio=anio_desde,
        anio_fin=anio_hasta,
    )
    puntos = series_service.serie_desde_idelr(
        serie,
        pais=pais,
        anio_desde=anio_desde,
        anio_hasta=anio_hasta,
    )
    if archivos:
        return (
            puntos,
            "processed",
            f"{len(archivos)} archivo(s) normalizado(s) leídos de data/processed/.",
        )
    return (
        puntos,
        "fallback",
        "Sin datasets normalizados: no hay serie macro para devolver.",
    )


@router.get("/series", response_model=SeriesResponse)
async def get_series(
    session: Annotated[AsyncSession | None, Depends(get_db_opcional)],
    tipo: Annotated[str | None, Query(description="IDELR o ICOL")] = None,
    pais: Annotated[str | None, Query(description="Código ISO-3 (ARG, CHL, URY)")] = None,
    ocupacion: Annotated[str | None, Query(description="Ocupación (OCUP_01..OCUP_20)")] = None,
    anio_desde: Annotated[int | None, Query(ge=1900, le=2100)] = None,
    anio_hasta: Annotated[int | None, Query(ge=1900, le=2100)] = None,
    limite: Annotated[int, Query(ge=1, le=5000)] = 1000,
) -> SeriesResponse:
    """Serie histórica plana, lista para graficar (#64).

    * `IDELR`: un punto por país y año, calculado desde los datasets
      normalizados.
    * `ICOL`: un punto por snapshot guardado (país × ocupación × fecha); si no
      hay snapshots, devuelve el cálculo actual como un único punto.
    """
    _validar_rango(anio_desde, anio_hasta)
    tipo_normalizado = str(validar_tipo(tipo))
    codigo_pais = validar_pais(pais)
    id_ocupacion = validar_ocupacion(ocupacion)
    if tipo_normalizado == "IDELR" and id_ocupacion:
        raise HTTPException(
            status_code=400,
            detail="ocupacion solo aplica a tipo=ICOL.",
        )

    puntos, fuente, detalle = await _construir_serie(
        session,
        tipo=tipo_normalizado,
        pais=codigo_pais,
        ocupacion=id_ocupacion,
        anio_desde=anio_desde,
        anio_hasta=anio_hasta,
    )
    puntos = puntos[:limite]

    return SeriesResponse(
        generated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        tipo=tipo_normalizado,
        fuente=fuente,
        detalle=detalle,
        filtros=SerieFiltros(
            tipo=tipo_normalizado,
            pais=codigo_pais,
            ocupacion=id_ocupacion,
            anio_desde=anio_desde,
            anio_hasta=anio_hasta,
        ),
        total=len(puntos),
        puntos=puntos,
    )


@router.get("/trends", response_model=TrendsResponse)
async def get_trends(
    session: Annotated[AsyncSession | None, Depends(get_db_opcional)],
    tipo: Annotated[str | None, Query(description="IDELR o ICOL")] = None,
    pais: Annotated[str | None, Query(description="Código ISO-3 (ARG, CHL, URY)")] = None,
    ocupacion: Annotated[str | None, Query(description="Ocupación (OCUP_01..OCUP_20)")] = None,
    anio_desde: Annotated[int | None, Query(ge=1900, le=2100)] = None,
    anio_hasta: Annotated[int | None, Query(ge=1900, le=2100)] = None,
    epsilon: Annotated[float, Query(ge=0, le=100)] = 1.0,
    limite: Annotated[int, Query(ge=1, le=5000)] = 1000,
) -> TrendsResponse:
    """Clasifica la evolución de cada país/ocupación (#64).

    Usa la misma banda muerta (`epsilon`) que `GET /employability` y devuelve
    `CRECIMIENTO`, `ESTABILIDAD`, `DISMINUCION` o `BASE` (sin punto previo).
    """
    _validar_rango(anio_desde, anio_hasta)
    tipo_normalizado = str(validar_tipo(tipo))
    codigo_pais = validar_pais(pais)
    id_ocupacion = validar_ocupacion(ocupacion)
    if tipo_normalizado == "IDELR" and id_ocupacion:
        raise HTTPException(
            status_code=400,
            detail="ocupacion solo aplica a tipo=ICOL.",
        )

    puntos, fuente, detalle = await _construir_serie(
        session,
        tipo=tipo_normalizado,
        pais=codigo_pais,
        ocupacion=id_ocupacion,
        anio_desde=anio_desde,
        anio_hasta=anio_hasta,
    )
    tendencias = series_service.calcular_tendencias(
        [{**punto, "tipo": tipo_normalizado} for punto in puntos],
        epsilon=epsilon,
    )[:limite]

    return TrendsResponse(
        generated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        tipo=tipo_normalizado,
        epsilon_pct=epsilon,
        fuente=fuente,
        detalle=detalle,
        total=len(tendencias),
        tendencias=tendencias,
    )


__all__ = ["router"]
