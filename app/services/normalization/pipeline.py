"""Pipeline de normalización de la carga manual.

Implementa los tres niveles definidos por el equipo de Data en
`DEFINICIONES_CASOS_CARGA_QA.md`:

1. **Rechazo sincrónico (Nivel 1)** → HTTP 422. El archivo completo se
   rechaza de forma atómica y no entra al pipeline.
2. **Cuarentena (Nivel 2)** → la fila se aísla con un flag
   (`UNMAPPED_CATALOG` u `OUTLIER_RANGE`) para revisión del equipo de Data.
3. **Deduplicación (Nivel 3)** → la clave natural de 7 campos más
   `occupation_id`; dentro del mismo lote gana el último registro.
"""

import math
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from app.core import catalogs
from app.services.normalization.errors import DatasetRowRejectionError, RowError
from app.services.normalization.mapper import (
    MappedRow,
    extracted_timestamp,
    map_common_row,
    map_manual_row,
)

# Clave natural de unicidad (LOAD-006 / LOAD-011).
# Los 7 campos canónicos aprobados por Data más `occupation_id`: sin este
# último, dos ocupaciones del mismo sector con la misma métrica, año y fuente
# se colapsarían en una sola fila (pérdida de datos). Ver Data_Contracts.md,
# sección "Desviaciones".
DEDUPE_KEY: tuple[str, ...] = (
    "pais_codigo_iso3",
    "dimension",
    "indicador_nombre",
    "anio",
    "periodo",
    "unidad_medida",
    "fuente_oficial",
    "occupation_id",
)

_SORT_KEY = ("pais_nombre", "dimension", "indicador_nombre", "anio", "periodo", "occupation_id")


@dataclass
class QuarantineRecord:
    """Fila aislada por no cumplir las reglas de producción."""

    position: int
    flag: str
    cause: str
    payload: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "row": self.position,
            "flag": self.flag,
            "cause": self.cause,
            "payload": self.payload,
        }


@dataclass
class NormalizationResult:
    """Resultado de normalizar un archivo: filas válidas, cuarentena y avisos."""

    valid: list[dict[str, Any]] = field(default_factory=list)
    quarantine: list[QuarantineRecord] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    duplicates_removed: int = 0
    rows_read: int = 0
    rejected: list[RowError] = field(default_factory=list)

    @property
    def rows_valid(self) -> int:
        return len(self.valid)

    @property
    def rows_quarantined(self) -> int:
        return len(self.quarantine)


def _is_missing(value: Any) -> bool:
    """True si el valor está vacío (None, cadena vacía o NaN)."""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, float) and math.isnan(value):
        return True
    return False


def _validate_manual_row(row: Mapping[str, Any], position: int) -> list[RowError]:
    """Nivel 1: validación de formato y presencia (HTTP 422 si falla)."""
    errors: list[RowError] = []

    country = row.get("country_code")
    if _is_missing(country):
        errors.append(RowError(position, "country_code", country, "campo obligatorio"))
    elif str(country).strip().upper() not in catalogs.PAISES_INFO:
        errors.append(
            RowError(
                position,
                "country_code",
                country,
                f"código de país fuera del alcance regional ({', '.join(catalogs.PAISES_INFO)})",
            )
        )

    if _is_missing(row.get("sector_id")):
        errors.append(RowError(position, "sector_id", row.get("sector_id"), "campo obligatorio"))
    if _is_missing(row.get("occupation_id")):
        errors.append(
            RowError(position, "occupation_id", row.get("occupation_id"), "campo obligatorio")
        )
    elif not catalogs.is_occupation_format(row.get("occupation_id")):
        errors.append(
            RowError(
                position,
                "occupation_id",
                row.get("occupation_id"),
                "formato inválido (se espera OCUP_XX, por ejemplo OCUP_01)",
            )
        )

    if _is_missing(row.get("metric_name")):
        errors.append(RowError(position, "metric_name", row.get("metric_name"), "campo obligatorio"))

    if _is_missing(row.get("source_name")):
        errors.append(RowError(position, "source_name", row.get("source_name"), "campo obligatorio"))

    raw_value = row.get("metric_value")
    if _is_missing(raw_value):
        errors.append(RowError(position, "metric_value", raw_value, "campo obligatorio"))
    else:
        try:
            float(raw_value)
        except (TypeError, ValueError):
            errors.append(
                RowError(
                    position,
                    "metric_value",
                    raw_value,
                    "valor no numérico (no se admiten 'sin dato', 's/d' ni texto)",
                )
            )

    if _is_missing(row.get("period")):
        errors.append(RowError(position, "period", row.get("period"), "campo obligatorio"))
    elif catalogs.parse_period(row.get("period")) is None:
        errors.append(
            RowError(
                position,
                "period",
                row.get("period"),
                "formato de período inválido (se admiten 2023, 2023-Q2 y 2023-06)",
            )
        )

    if _is_missing(row.get("data_type")):
        errors.append(RowError(position, "data_type", row.get("data_type"), "campo obligatorio"))
    elif catalogs.resolve_unit(row.get("data_type")) is None:
        errors.append(
            RowError(
                position,
                "data_type",
                row.get("data_type"),
                f"valor no permitido ({', '.join(catalogs.DATA_TYPES)})",
            )
        )

    return errors


def _deduplicate(
    rows: Sequence[tuple[int, dict[str, Any]]],
) -> tuple[list[dict[str, Any]], int, list[str]]:
    """Nivel 3: aplica la clave natural y conserva el último registro del lote."""
    por_clave: dict[tuple[Any, ...], tuple[int, dict[str, Any]]] = {}
    warnings: list[str] = []
    duplicados = 0

    for position, row in rows:
        clave = tuple(row.get(column) for column in DEDUPE_KEY)
        previa = por_clave.get(clave)
        if previa is None:
            por_clave[clave] = (position, row)
            continue

        duplicados += 1
        posicion_previa, fila_previa = previa
        if fila_previa.get("valor") != row.get("valor"):
            warnings.append(
                "Registro sobreescrito por actualización en la misma carga "
                f"(fila {position} reemplaza a la fila {posicion_previa})"
            )
        por_clave[clave] = (position, row)

    ordenadas = [fila for _, fila in por_clave.values()]
    ordenadas.sort(key=lambda fila: tuple(str(fila.get(column)) for column in _SORT_KEY))
    return ordenadas, duplicados, warnings


def _finalize(
    mapped: Sequence[MappedRow],
    rows_read: int,
) -> NormalizationResult:
    """Separa cuarentena, deduplica y ordena las filas mapeadas."""
    valid: list[tuple[int, dict[str, Any]]] = []
    quarantine: list[QuarantineRecord] = []
    warnings: list[str] = []

    for item in mapped:
        warnings.extend(item.warnings)
        if item.quarantined:
            quarantine.append(
                QuarantineRecord(
                    position=item.position,
                    flag=item.flag or "",
                    cause=item.cause or "",
                    payload=item.data,
                )
            )
        else:
            valid.append((item.position, item.data))

    rows, duplicates_removed, dedupe_warnings = _deduplicate(valid)
    return NormalizationResult(
        valid=rows,
        quarantine=quarantine,
        warnings=warnings + dedupe_warnings,
        duplicates_removed=duplicates_removed,
        rows_read=rows_read,
    )


def normalize_manual_rows(
    rows: Sequence[Mapping[str, Any]],
    positions: Sequence[int] | None = None,
) -> NormalizationResult:
    """Normaliza un archivo en el contrato de carga manual (8 columnas).

    Lanza `DatasetRowRejectionError` (HTTP 422) si alguna fila falla el Nivel 1.
    """
    indices = list(positions) if positions is not None else list(range(2, len(rows) + 2))
    errores: list[RowError] = []

    for indice, row in zip(indices, rows):
        errores.extend(_validate_manual_row(row, indice))

    if errores:
        raise DatasetRowRejectionError(
            f"Se rechazaron {len(errores)} dato(s) por validación de entrada "
            "(HTTP 422); el archivo no entró al pipeline.",
            errores,
        )

    extracted_at = extracted_timestamp()
    mapped = [
        map_manual_row(row, indice, extracted_at) for indice, row in zip(indices, rows)
    ]
    return _finalize(mapped, rows_read=len(rows))


def normalize_common_rows(
    rows: Sequence[Mapping[str, Any]],
    positions: Sequence[int] | None = None,
) -> NormalizationResult:
    """Normaliza un archivo que ya viene en el esquema común del equipo Data."""
    indices = list(positions) if positions is not None else list(range(2, len(rows) + 2))
    extracted_at = extracted_timestamp()
    mapped: list[MappedRow] = []

    for indice, row in zip(indices, rows):
        item = map_common_row(row, indice, extracted_at)
        country = str(row.get("pais_codigo_iso3") or "").strip().upper()
        if country and country not in catalogs.PAISES_INFO:
            item = MappedRow(
                position=indice,
                data=item.data,
                flag="UNMAPPED_CATALOG",
                cause=(
                    f"pais_codigo_iso3 '{country}' fuera del alcance regional "
                    f"({', '.join(catalogs.PAISES_INFO)})"
                ),
            )
        mapped.append(item)

    return _finalize(mapped, rows_read=len(rows))


__all__ = [
    "DEDUPE_KEY",
    "NormalizationResult",
    "QuarantineRecord",
    "normalize_common_rows",
    "normalize_manual_rows",
]
