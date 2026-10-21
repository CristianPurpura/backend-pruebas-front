"""Lectura de los datasets normalizados para el cálculo de índices.

Los datasets son los que produce `POST /api/v1/datasets/upload` (o los que se
reingieren en el esquema común de Data). Mientras la base de datos no esté
configurada, se leen desde `data/processed/`.
"""

from pathlib import Path
from typing import Any

import pandas as pd

from app.core.config import get_settings
from app.services.normalization.mapper import COMMON_COLUMNS

# Mínimo de columnas comunes para considerar que un CSV es un dataset normalizado.
_MIN_COLUMNAS_COMUNES = 4


def leer_datasets_normalizados(
    base_dir: str | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Lee los CSV normalizados de `data/processed/`.

    Devuelve las filas concatenadas y la lista de archivos leídos.
    """
    raiz = Path(base_dir or get_settings().processed_dir)
    if not raiz.exists():
        return [], []

    filas: list[dict[str, Any]] = []
    archivos: list[str] = []

    for archivo in sorted(raiz.rglob("*.csv")):
        try:
            dataframe = pd.read_csv(archivo, encoding="utf-8-sig")
        except Exception:
            continue

        comunes = [columna for columna in COMMON_COLUMNS if columna in dataframe.columns]
        if len(comunes) < _MIN_COLUMNAS_COMUNES:
            continue

        filas.extend(dataframe[comunes].to_dict(orient="records"))
        archivos.append(str(archivo))

    return filas, archivos


__all__ = ["leer_datasets_normalizados"]
