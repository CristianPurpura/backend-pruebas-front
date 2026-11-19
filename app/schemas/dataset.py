"""Schemas de la carga manual de datasets."""

from typing import Any

from pydantic import BaseModel, Field


class QuarantineRow(BaseModel):
    """Fila aislada durante la normalización, con su flag y causa."""

    row: int
    flag: str
    cause: str
    payload: dict[str, Any] = Field(default_factory=dict)


class DatasetUploadResponse(BaseModel):
    """Resumen de la ingesta: qué se normalizó, qué quedó en cuarentena y dónde."""

    filename: str
    status: str
    input_schema: str
    rows_count: int
    rows_valid: int
    rows_rejected: int
    rows_quarantined: int
    duplicates_removed: int
    columns_detected: list[str]
    normalized_columns: list[str]
    warnings: list[str] = Field(default_factory=list)
    quarantine: list[QuarantineRow] = Field(default_factory=list)
    output_path: str | None = None
    quarantine_path: str | None = None
    snapshot_programado: bool = False
    message: str


__all__ = ["DatasetUploadResponse", "QuarantineRow"]
