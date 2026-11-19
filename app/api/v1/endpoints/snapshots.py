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

from app.core.database import get_db_requerida
from app.core.validation import validar_ocupacion, validar_pais, validar_tipo
from app.schemas.indicator_result import (
    HistoryEntry,
    HistoryResponse,
    LatestEntry,
    LatestResponse,
    SnapshotResponse,
    SnapshotSaved,
)
from app.services.persistence import results_store, snapshot_service

router = APIRouter()


@router.post("/snapshot", response_model=SnapshotResponse)
async def guardar_snapshot(
    session: Annotated[AsyncSession, Depends(get_db_requerida)],
) -> SnapshotResponse:
    """Calcula IDELR e ICOL y guarda el resultado en la base de datos.

    Es idempotente: volver a guardar el mismo día actualiza los registros
    existentes en lugar de duplicarlos.
    """
    datos = await snapshot_service.generar_snapshot(session)

    return SnapshotResponse(
        generated_at=datos.generated_at,
        fecha_snapshot=datos.fecha_snapshot,
        metodologia_version=datos.metodologia_version,
        fuente_datos=datos.fuente_datos,
        anio_referencia=datos.anio_referencia,
        guardado=SnapshotSaved(
            idelr=datos.filas_idelr,
            icol=datos.filas_icol,
            insertados=datos.insertados,
            actualizados=datos.actualizados,
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
    tipo_normalizado = validar_tipo(tipo, default=None)
    codigo_pais = validar_pais(pais)
    id_ocupacion = validar_ocupacion(ocupacion)

    resultados = await results_store.history(
        session,
        tipo=tipo_normalizado,
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


@router.get("/latest", response_model=LatestResponse)
async def ultimo_snapshot(
    session: Annotated[AsyncSession, Depends(get_db_requerida)],
    tipo: Annotated[str | None, Query(description="IDELR o ICOL")] = None,
    pais: Annotated[str | None, Query(description="Código ISO-3 (ARG, CHL, URY)")] = None,
    ocupacion: Annotated[str | None, Query(description="Ocupación (OCUP_01..OCUP_20)")] = None,
) -> LatestResponse:
    """Último snapshot guardado de cada combinación (#65).

    No expone el `payload` completo: devuelve solo la fila resumida para que
    el Frontend muestre el estado actual sin descargar cálculos históricos.
    """
    tipo_normalizado = validar_tipo(tipo, default=None)
    codigo_pais = validar_pais(pais)
    id_ocupacion = validar_ocupacion(ocupacion)

    resultados = await results_store.latest(
        session,
        tipo=tipo_normalizado,
        pais=codigo_pais,
        ocupacion_id=id_ocupacion,
    )
    fecha_snapshot = max(
        (fila.calculado_en for fila in resultados),
        default=None,
    )

    return LatestResponse(
        generated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        tipo=tipo_normalizado,
        fecha_snapshot=fecha_snapshot,
        total=len(resultados),
        resultados=[
            LatestEntry(
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
            )
            for fila in resultados
        ],
    )


__all__ = ["router"]
