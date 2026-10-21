"""Normalización de la carga manual hacia el esquema común del equipo Data."""

from app.services.normalization.errors import (
    DatasetRowRejectionError,
    DatasetValidationError,
    RowError,
)
from app.services.normalization.mapper import (
    COMMON_COLUMNS,
    EXTRA_COLUMNS,
    NORMALIZED_COLUMNS,
    QUARANTINE_OUTLIER_RANGE,
    QUARANTINE_UNMAPPED_CATALOG,
    map_common_row,
    map_manual_row,
)
from app.services.normalization.pipeline import (
    DEDUPE_KEY,
    NormalizationResult,
    QuarantineRecord,
    normalize_common_rows,
    normalize_manual_rows,
)
from app.services.normalization.store import write_normalized, write_quarantine

__all__ = [
    "COMMON_COLUMNS",
    "DEDUPE_KEY",
    "DatasetRowRejectionError",
    "DatasetValidationError",
    "EXTRA_COLUMNS",
    "NORMALIZED_COLUMNS",
    "NormalizationResult",
    "QUARANTINE_OUTLIER_RANGE",
    "QUARANTINE_UNMAPPED_CATALOG",
    "QuarantineRecord",
    "RowError",
    "map_common_row",
    "map_manual_row",
    "normalize_common_rows",
    "normalize_manual_rows",
    "write_normalized",
    "write_quarantine",
]
