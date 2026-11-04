"""Persistencia de resultados (snapshots históricos de los índices)."""

from app.services.persistence.results_store import (
    METODOLOGIA_VERSION,
    history,
    latest,
    purge,
)

__all__ = [
    "METODOLOGIA_VERSION",
    "history",
    "latest",
    "purge",
]
