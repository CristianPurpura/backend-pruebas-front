"""Schemas de persistencia histórica de los índices (IDELR / ICOL)."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SnapshotSaved(BaseModel):
    """Conteo de filas guardadas en un snapshot."""

    idelr: int = 0
    icol: int = 0
    insertados: int = 0
    actualizados: int = 0


class SnapshotResponse(BaseModel):
    """Respuesta de `POST /api/v1/employability/snapshot`."""

    generated_at: str
    fecha_snapshot: str
    metodologia_version: str
    fuente_datos: str
    anio_referencia: int | None = None
    guardado: SnapshotSaved


class HistoryEntry(BaseModel):
    """Un resultado histórico dentro de la respuesta del historial."""

    tipo: str
    pais: str
    anio: int | None = None
    ocupacion_id: str | None = None
    valor: float
    categoria: str | None = None
    cobertura_pct: float | None = None
    metodologia_version: str
    calculado_en: datetime
    payload: dict[str, Any] = Field(default_factory=dict)


class HistoryResponse(BaseModel):
    """Respuesta de `GET /api/v1/employability/history`."""

    generated_at: str
    total: int
    resultados: list[HistoryEntry] = Field(default_factory=list)


__all__ = [
    "HistoryEntry",
    "HistoryResponse",
    "SnapshotResponse",
    "SnapshotSaved",
]
