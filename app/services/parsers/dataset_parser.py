import io
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import UploadFile

from app.schemas.dataset import DatasetUploadResponse

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

ALLOWED_EXTENSIONS = (".csv", ".xlsx")


class DatasetValidationError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def parse_dataset(file: UploadFile) -> DatasetUploadResponse:
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
        if extension == ".csv":
            df: Any = pd.read_csv(io.BytesIO(content))
        else:
            df = pd.read_excel(io.BytesIO(content))
    except Exception as exc:
        raise DatasetValidationError(f"No se pudo leer el archivo: {exc}") from exc

    columns: list[str] = [str(column) for column in df.columns]
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in columns]

    if missing_columns:
        raise DatasetValidationError(
            "Faltan columnas obligatorias: " + ", ".join(missing_columns)
        )

    return DatasetUploadResponse(
        filename=filename,
        status="ok",
        rows_count=int(len(df)),
        columns_detected=columns,
        message="Archivo válido",
    )