"""Parser de la carga manual de datasets (CSV / Excel).

Se ocupa de la **estructura** del archivo (extensión, contenido, columnas).
La validación de valores y la normalización al esquema común viven en
`app/services/normalization/`.
"""

import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import UploadFile

from app.services.normalization.errors import DatasetValidationError
from app.services.normalization.mapper import COMMON_COLUMNS

REQUIRED_COLUMNS = (
    "country_code",
    "sector_id",
    "occupation_id",
    "metric_name",
    "metric_value",
    "period",
    "source_name",
    "data_type",
)

OPTIONAL_COLUMNS = ("is_projection",)

ALLOWED_EXTENSIONS = (".csv", ".xlsx")

SCHEMA_MANUAL = "manual"
SCHEMA_COMMON = "common"


@dataclass
class ParsedDataset:
    """Archivo leído y validado estructuralmente."""

    filename: str
    columns: list[str]
    rows: list[dict[str, Any]] = field(default_factory=list)
    schema: str = SCHEMA_MANUAL

    @property
    def rows_count(self) -> int:
        return len(self.rows)


def _read_frame(content: bytes, extension: str) -> Any:
    if extension == ".csv":
        return pd.read_csv(io.BytesIO(content), dtype=str, keep_default_na=False)
    return pd.read_excel(io.BytesIO(content), dtype=str)


def parse_dataset(file: UploadFile) -> ParsedDataset:
    """Lee el archivo y devuelve sus filas ya tipadas como texto.

    Acepta dos contratos de entrada:

    * **manual**: las 8 columnas de la carga manual (`country_code` …
      `data_type`), con `is_projection` opcional.
    * **común**: las 10 columnas del esquema de Data (`pais_codigo_iso3` …
      `fecha_extraccion`), para reingerir el golden dataset regional.
    """
    filename = file.filename or ""
    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise DatasetValidationError(
            f"Extensión no permitida: '{extension or 'sin extensión'}'. "
            "Solo se admiten archivos .csv o .xlsx."
        )

    content: bytes = file.file.read()
    if not content:
        raise DatasetValidationError("El archivo está vacío.")

    try:
        df = _read_frame(content, extension)
    except Exception as exc:
        raise DatasetValidationError(f"No se pudo leer el archivo: {exc}") from exc

    columns: list[str] = [str(column) for column in df.columns]

    if set(COMMON_COLUMNS).issubset(set(columns)):
        schema = SCHEMA_COMMON
    else:
        missing_columns = [column for column in REQUIRED_COLUMNS if column not in columns]
        if missing_columns:
            raise DatasetValidationError(
                "Faltan columnas obligatorias: " + ", ".join(missing_columns)
            )
        schema = SCHEMA_MANUAL

    frame = df.where(pd.notna(df), None)
    rows: list[dict[str, Any]] = frame.to_dict(orient="records")

    return ParsedDataset(
        filename=filename,
        columns=columns,
        rows=rows,
        schema=schema,
    )


__all__ = [
    "ALLOWED_EXTENSIONS",
    "OPTIONAL_COLUMNS",
    "REQUIRED_COLUMNS",
    "SCHEMA_COMMON",
    "SCHEMA_MANUAL",
    "ParsedDataset",
    "parse_dataset",
]
