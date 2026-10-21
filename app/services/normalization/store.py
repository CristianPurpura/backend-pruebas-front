"""Persistencia del dataset normalizado y de las filas en cuarentena.

Mientras no haya base de datos configurada (la DB se difiere a Sprint 1), el
Backend escribe el resultado en disco con el mismo criterio que usa el
equipo de Data: CSV con codificación `utf-8-sig` en `data/processed/` y un
JSONL de cuarentena en `data/quarantine/`.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

from app.core.config import get_settings
from app.services.normalization.mapper import NORMALIZED_COLUMNS
from app.services.normalization.pipeline import QuarantineRecord

_RE_NO_ALNUM = re.compile(r"[^A-Za-z0-9]+")


def _safe_slug(filename: str) -> str:
    """Nombre de archivo seguro a partir del nombre original."""
    base = Path(filename or "dataset").stem
    slug = _RE_NO_ALNUM.sub("_", base).strip("_").lower()
    return slug[:60] or "dataset"


def _target_path(base_dir: str, filename: str, suffix: str) -> Path:
    """Ruta `data/{base_dir}/{YYYY-MM-DD}/{HHMMSS}_{slug}{suffix}`."""
    ahora = datetime.now(timezone.utc)
    directorio = Path(base_dir) / ahora.strftime("%Y-%m-%d")
    directorio.mkdir(parents=True, exist_ok=True)
    return directorio / f"{ahora.strftime('%H%M%S')}_{_safe_slug(filename)}{suffix}"


def write_normalized(
    rows: Sequence[dict[str, Any]],
    filename: str,
    base_dir: str | None = None,
) -> Path:
    """Escribe el dataset normalizado y devuelve la ruta del archivo generado."""
    destino = _target_path(base_dir or get_settings().processed_dir, filename, ".csv")
    registros = [{columna: fila.get(columna) for columna in NORMALIZED_COLUMNS} for fila in rows]
    dataframe = pd.DataFrame(registros, columns=NORMALIZED_COLUMNS)
    dataframe.to_csv(destino, index=False, encoding="utf-8-sig")
    return destino


def write_quarantine(
    records: Sequence[QuarantineRecord],
    filename: str,
    base_dir: str | None = None,
) -> Path | None:
    """Escribe las filas en cuarentena (JSONL) y devuelve la ruta del archivo."""
    if not records:
        return None

    destino = _target_path(base_dir or get_settings().quarantine_dir, filename, ".jsonl")
    with destino.open("w", encoding="utf-8") as archivo:
        for record in records:
            archivo.write(
                json.dumps(
                    {
                        "row": record.position,
                        "flag": record.flag,
                        "cause": record.cause,
                        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                        "payload": record.payload,
                    },
                    ensure_ascii=False,
                )
            )
            archivo.write("\n")
    return destino


__all__ = ["write_normalized", "write_quarantine"]
