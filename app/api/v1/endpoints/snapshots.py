"""Endpoints de persistencia histórica de los índices (issue #54).

* `POST /api/v1/employability/snapshot` calcula los índices y **guarda** el
  resultado para poder mirar el pasado.
* `GET /api/v1/employability/history` consulta lo guardado.

El guardado es explícito (POST) a propósito: `GET /api/v1/employability` sigue
siendo de solo lectura y no escribe nada en la base.
"""

from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.catalogs import PAISES_INFO, OCUPACIONES
from app.core.database import get_db_requerida
from app.schemas.indicator_result import (
    HistoryEntry,
    HistoryResponse,
    SnapshotResponse,
    SnapshotSaved,
)
from app.services.calculators import (
    calcular_icol,
    calcular_idelr,
    expandir_ocupaciones,
    leer_datasets_normalizados,
    macro_scores,
)
from app.services.persistence import results_store
from app.services.persistence.results_store import METODOLOGIA_VERSION

router = APIRouter()


def _validar_pais(pais: str | None) -> str | None:
    if not pais:
        return None
    codigo = pais.strip().upper()
    if codigo not in PAISES_INFO:
        raise HTTPException(
            status_code=400,
            detail=f"País fuera del alcance regional: {pais}. Permitidos: "
            f"{', '.join(PAISES_INFO)}.",
        )
    return codigo


def _validar_ocupacion(ocupacion: str | None) -> str | None:
    if not ocupacion:
        return None
    clave = ocupacion.strip().upper()
    if clave not in OCUPACIONES:
        raise HTTPException(
            status_code=400,
            detail=f"Ocupación fuera del catálogo: {ocupacion}.",
        )
    return clave


@router.post("/snapshot", response_model=SnapshotResponse)
async def guardar_snapshot(
    session: Annotated[AsyncSession, Depends(get_db_requerida)],
) -> SnapshotResponse:
    """Calcula IDELR e ICOL y guarda el resultado en la base de datos.

    Es idempotente: volver a guardar el mismo día actualiza los registros
    existentes en lugar de duplicarlos.
    """
    ahora = datetime.now(timezone.utc)
    filas, archivos = leer_datasets_normalizados()

    macro = macro_scores(calcular_idelr(filas))
    serie = calcular_idelr(filas)
    ranking = calcular_icol(expandir_ocupaciones(), macro=macro or None)

    anio_referencia = max((fila["anio"] for fila in serie), default=None)

    filas_idelr = results_store.snapshot_idelr(serie)
    filas_icol = results_store.snapshot_icol(ranking, anio_referencia)

    conteo = await results_store.save_snapshot(
        session,
        filas_idelr + filas_icol,
        metodologia_version=METODOLOGIA_VERSION,
        fecha=ahora.strftime("%Y-%m-%d"),
    )

    return SnapshotResponse(
        generated_at=ahora.replace(microsecond=0).isoformat(),
        fecha_snapshot=ahora.strftime("%Y-%m-%d"),
        metodologia_version=METODOLOGIA_VERSION,
        fuente_datos="processed" if archivos else "fallback",
        anio_referencia=anio_referencia,
        guardado=SnapshotSaved(
            idelr=len(filas_idelr),
            icol=len(filas_icol),
            insertados=conteo["insertados"],
            actualizados=conteo["actualizados"],
        ),
    )


@router.get("/history", response_model=HistoryResponse)
async def consultar_historial(
    session: Annotated[AsyncSession, Depends(get_db_requerida)],
    tipo: Annotated[str | None, Query(description="IDELR o ICOL")] = None,
    pais: Annotated[str | None, Query(description="Código ISO-3 (ARG, CHL, URY)")] = None,
    ocupacion: Annotated[str | None, Query(description="Ocupación (OCUP_01..OCUP_20)")] = None,
    anio_desde: Annotated[int | None, Query(ge=1900, le=2100)] = None,
    anio_hasta: Annotated[int | None, Query(ge=1900, le=2100)] = None,
    limite: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> HistoryResponse:
    """Histórico de resultados guardados, del más reciente al más antiguo."""
    if tipo and tipo.strip().upper() not in {"IDELR", "ICOL"}:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de índice desconocido: {tipo}. Permitidos: IDELR, ICOL.",
        )

    codigo_pais = _validar_pais(pais)
    id_ocupacion = _validar_ocupacion(ocupacion)

    resultados = await results_store.history(
        session,
        tipo=tipo,
        pais=codigo_pais,
        ocupacion_id=id_ocupacion,
        anio_desde=anio_desde,
        anio_hasta=anio_hasta,
        limite=limite,
    )

    return HistoryResponse(
        generated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        total=len(resultados),
        resultados=[
            HistoryEntry(
                tipo=fila.tipo,
                pais=fila.pais,
                anio=fila.anio,
                ocupacion_id=fila.ocupacion_id,
                valor=float(fila.valor),
                categoria=fila.categoria,
                cobertura_pct=(
                    float(fila.cobertura_pct) if fila.cobertura_pct is not None else None
                ),
                metodologia_version=fila.metodologia_version,
                calculado_en=fila.calculado_en,
                payload=fila.payload or {},
            )
            for fila in resultados
        ],
    )


__all__ = ["router"]
