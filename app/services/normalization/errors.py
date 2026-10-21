"""Errores de la ingesta de datasets y detalle del rechazo por fila."""

from typing import Any


class RowError:
    """Detalle de un rechazo sincrónico (Nivel 1) sobre una fila del archivo."""

    def __init__(self, position: int, field: str, value: Any, cause: str) -> None:
        self.position = position
        self.field = field
        self.value = value
        self.cause = cause

    def as_dict(self) -> dict[str, Any]:
        return {
            "row": self.position,
            "field": self.field,
            "value": None if self.value is None else str(self.value),
            "cause": self.cause,
        }


class DatasetValidationError(Exception):
    """Error estructural del archivo (extensión, vacío, columnas faltantes).

    Se traduce a HTTP 400: el archivo no tiene la forma mínima exigida.
    """

    status_code = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class DatasetRowRejectionError(DatasetValidationError):
    """Rechazo sincrónico de filas (Nivel 1) según LOAD-010 / LOAD-012.

    Se traduce a HTTP 422: las filas inválidas no entran al pipeline y el
    archivo completo se rechaza de forma atómica.
    """

    status_code = 422

    def __init__(self, message: str, rows: list[RowError]) -> None:
        super().__init__(message)
        self.rows = rows

    def as_dict(self) -> dict[str, Any]:
        return {
            "error": self.message,
            "rows": [row.as_dict() for row in self.rows],
        }


__all__ = ["DatasetRowRejectionError", "DatasetValidationError", "RowError"]
