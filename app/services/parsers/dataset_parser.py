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

ALLOWED_COUNTRIES = ("ARG", "CHL", "URY")
ALLOWED_DATA_TYPES = ("observed", "projected")
OCCUPATION_IDS = tuple(f"OCUP_{number:02d}" for number in range(1, 21))


class DatasetValidationError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _validate_row(position: int, row: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    country = row.get("country_code")
    if country not in ALLOWED_COUNTRIES:
        errors.append(
            f"country_code invalido en fila {position}: {country!r} "
            f"(permitidos: {', '.join(ALLOWED_COUNTRIES)})"
        )

    occupation = row.get("occupation_id")
    if occupation not in OCCUPATION_IDS:
        errors.append(
            f"occupation_id invalido en fila {position}: {occupation!r} "
            "(debe pertenecer al catalogo OCUP_01..OCUP_20)"
        )

    data_type = row.get("data_type")
    if data_type not in ALLOWED_DATA_TYPES:
        errors.append(
            f"data_type invalido en fila {position}: {data_type!r} "
            f"(permitidos: {', '.join(ALLOWED_DATA_TYPES)})"
        )

    metric_value = row.get("metric_value")
    try:
        numeric_value = float(metric_value)
    except (TypeError, ValueError):
        numeric_value = float("nan")
    if pd.isna(numeric_value):
        errors.append(
            f"metric_value invalido en fila {position}: {metric_value!r} (debe ser numerico)"
        )

    return errors


def _validate_values(df: Any) -> None:
    errors: list[str] = []
    for position, row in enumerate(df.to_dict(orient="records"), start=2):
        errors.extend(_validate_row(position, row))
    if errors:
        raise DatasetValidationError("; ".join(errors))


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

    _validate_values(df)

    return DatasetUploadResponse(
        filename=filename,
        status="ok",
        rows_count=int(len(df)),
        columns_detected=columns,
        message="Archivo válido",
    )
