"""Endpoints de carga manual de datasets."""

from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.schemas.dataset import DatasetUploadResponse, QuarantineRow
from app.services.normalization import (
    NORMALIZED_COLUMNS,
    DatasetRowRejectionError,
    DatasetValidationError,
    normalize_common_rows,
    normalize_manual_rows,
    write_normalized,
    write_quarantine,
)
from app.services.parsers.dataset_parser import (
    SCHEMA_COMMON,
    parse_dataset,
)

router = APIRouter()


@router.post("/upload", response_model=DatasetUploadResponse)
def upload_dataset(
    file: Annotated[UploadFile, File(...)],
    persist: Annotated[bool, Query(description="Escribir el resultado en disco")] = True,
) -> DatasetUploadResponse:
    """Valida, normaliza y persiste un dataset en CSV o Excel.

    * `400`: el archivo no cumple la estructura mínima (extensión, vacío o
      columnas obligatorias faltantes).
    * `422`: alguna fila falla la validación de entrada; el archivo se rechaza
      de forma atómica y el detalle indica fila, campo y causa.
    """
    try:
        parsed = parse_dataset(file)
        if parsed.schema == SCHEMA_COMMON:
            result = normalize_common_rows(parsed.rows)
        else:
            result = normalize_manual_rows(parsed.rows)
    except DatasetRowRejectionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.as_dict()) from exc
    except DatasetValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    output_path = None
    quarantine_path = None
    if persist:
        if result.valid:
            output_path = write_normalized(result.valid, parsed.filename)
        quarantine_path = write_quarantine(result.quarantine, parsed.filename)

    status = "ok" if not result.warnings and not result.quarantine else "ok_with_warnings"
    message = (
        f"Archivo normalizado: {result.rows_valid} fila(s) válida(s), "
        f"{result.rows_quarantined} en cuarentena, "
        f"{result.duplicates_removed} duplicado(s) descartado(s)."
    )

    return DatasetUploadResponse(
        filename=parsed.filename,
        status=status,
        input_schema=parsed.schema,
        rows_count=parsed.rows_count,
        rows_valid=result.rows_valid,
        rows_rejected=len(result.rejected),
        rows_quarantined=result.rows_quarantined,
        duplicates_removed=result.duplicates_removed,
        columns_detected=parsed.columns,
        normalized_columns=list(NORMALIZED_COLUMNS),
        warnings=result.warnings,
        quarantine=[
            QuarantineRow(
                row=record.position,
                flag=record.flag,
                cause=record.cause,
                payload=record.payload,
            )
            for record in result.quarantine
        ],
        output_path=str(output_path) if output_path else None,
        quarantine_path=str(quarantine_path) if quarantine_path else None,
        message=message,
    )
