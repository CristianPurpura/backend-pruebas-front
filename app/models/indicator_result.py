"""Resultado histórico de un índice calculado (IDELR / ICOL).

Espejo en base de datos de los snapshots que el Backend guarda para poder
mirar el pasado: cada fila es *un cálculo* de un índice para una combinación
concreta (país × año para el IDELR, país × ocupación para el ICOL).

No guarda datos crudos (eso vive en `raw_data_logs`): guarda el **resultado**
del cálculo, con la fecha en que se hizo y la versión de la metodología
usada, para poder reproducirlo y compararlo con el de otros días.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Index, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

# Tipos de índice persistidos.
TIPO_IDELR = "IDELR"
TIPO_ICOL = "ICOL"
TIPOS_INDICE = (TIPO_IDELR, TIPO_ICOL)


class IndicatorResult(Base):
    """Snapshot de un índice de empleabilidad calculado por el Backend.

    La unicidad de `dedupe_key` garantiza que dos snapshots del mismo día
    para la misma combinación se actualicen en lugar de duplicarse.
    """

    __tablename__ = "indicator_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[str] = mapped_column(String(16), index=True)
    pais: Mapped[str] = mapped_column(String(3), index=True)
    # Año del dato: para IDELR es el año del índice; para ICOL, el año macro
    # de referencia con el que se calculó el entorno.
    anio: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    # `NULL` para el IDELR (que es macro, no ocupacional).
    ocupacion_id: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    valor: Mapped[float] = mapped_column(Numeric(6, 2))
    categoria: Mapped[str | None] = mapped_column(String(32), nullable=True)
    cobertura_pct: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    metodologia_version: Mapped[str] = mapped_column(String(32), default="")
    # Fila completa del cálculo (desglose de variables, scores, etc.).
    payload: Mapped[Any] = mapped_column(JSON, default=dict)
    # Clave de idempotencia: tipo|pais|anio|ocupacion|fecha.
    dedupe_key: Mapped[str] = mapped_column(String(96), unique=True, index=True)
    calculado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    __table_args__ = (
        Index("ix_indicator_results_tipo_pais_anio", "tipo", "pais", "anio"),
        Index("ix_indicator_results_ocupacion_calculado", "ocupacion_id", "calculado_en"),
    )


__all__ = ["TIPOS_INDICE", "TIPO_ICOL", "TIPO_IDELR", "IndicatorResult"]
