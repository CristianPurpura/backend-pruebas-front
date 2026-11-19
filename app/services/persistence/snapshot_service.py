"""Cálculo y guardado de snapshots de los índices (#65).

Extrae la lógica que antes vivía en el endpoint `POST /employability/snapshot`
para poder reutilizarla desde dos lugares:

* el endpoint manual (mismo contrato de siempre), y
* la tarea en segundo plano que se dispara al terminar una carga manual.

`generar_snapshot_seguro` es la variante para background: si no hay base de
datos o algo falla, no rompe la carga del archivo; solo deja un warning.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import database
from app.services.calculators import (
    calcular_icol,
    calcular_idelr,
    expandir_ocupaciones,
    leer_datasets_normalizados,
    macro_scores,
)
from app.services.persistence import results_store
from app.services.persistence.results_store import METODOLOGIA_VERSION

logger = logging.getLogger(__name__)


@dataclass
class SnapshotData:
    """Resultado de un snapshot, desacoplado del schema HTTP."""

    generated_at: str
    fecha_snapshot: str
    metodologia_version: str
    fuente_datos: str
    anio_referencia: int | None
    filas_idelr: int
    filas_icol: int
    insertados: int
    actualizados: int


async def generar_snapshot(
    session: AsyncSession,
    *,
    fecha: str | None = None,
) -> SnapshotData:
    """Calcula IDELR/ICOL y guarda el snapshot de forma idempotente."""
    ahora = datetime.now(timezone.utc)
    dia = fecha or ahora.strftime("%Y-%m-%d")

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
        fecha=dia,
    )

    return SnapshotData(
        generated_at=ahora.replace(microsecond=0).isoformat(),
        fecha_snapshot=dia,
        metodologia_version=METODOLOGIA_VERSION,
        fuente_datos="processed" if archivos else "fallback",
        anio_referencia=anio_referencia,
        filas_idelr=len(filas_idelr),
        filas_icol=len(filas_icol),
        insertados=conteo["insertados"],
        actualizados=conteo["actualizados"],
    )


async def generar_snapshot_seguro() -> SnapshotData | None:
    """Genera el snapshot sin propagar errores (para background tasks)."""
    if not database.is_db_configured():
        return None
    try:
        async with database.session_scope() as session:
            return await generar_snapshot(session)
    except Exception:  # noqa: BLE001 - la carga del archivo no debe fallar
        logger.warning("No se pudo generar el snapshot automático.", exc_info=True)
        return None


__all__ = ["SnapshotData", "generar_snapshot", "generar_snapshot_seguro"]
