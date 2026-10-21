import io
from collections.abc import Sequence

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app

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

COMMON_COLUMNS = (
    "pais_codigo_iso3",
    "pais_nombre",
    "dimension",
    "indicador_nombre",
    "anio",
    "periodo",
    "valor",
    "unidad_medida",
    "fuente_oficial",
    "fecha_extraccion",
)

VALID_ROW = {
    "country_code": "ARG",
    "sector_id": "TEC",
    "occupation_id": "OCUP_01",
    "metric_name": "demanda_laboral",
    "metric_value": "1500.0",
    "period": "2025",
    "source_name": "INDEC-EPH",
    "data_type": "count",
}


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def build_rows(**overrides: str) -> list[dict[str, str]]:
    row = {**VALID_ROW, **overrides}
    return [row]


def make_csv(
    rows: Sequence[dict[str, str]],
    columns: Sequence[str] = REQUIRED_COLUMNS,
) -> bytes:
    df = pd.DataFrame(list(rows), columns=list(columns))
    return df.to_csv(index=False).encode("utf-8")


def make_xlsx(
    rows: Sequence[dict[str, str]],
    columns: Sequence[str] = REQUIRED_COLUMNS,
) -> bytes:
    df = pd.DataFrame(list(rows), columns=list(columns))
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False)
    return buffer.getvalue()


def upload(client: TestClient, filename: str, content: bytes):
    return client.post(
        "/api/v1/datasets/upload",
        files={"file": (filename, content, "application/octet-stream")},
    )


def make_common_csv(rows: Sequence[dict[str, object]]) -> bytes:
    """CSV en el esquema común de Data (10 columnas)."""
    df = pd.DataFrame(list(rows), columns=list(COMMON_COLUMNS))
    return df.to_csv(index=False).encode("utf-8")


@pytest.fixture()
def output_dirs(tmp_path, monkeypatch):
    """Redirige la persistencia (dataset normalizado y cuarentena) a tmp_path."""
    processed = tmp_path / "processed"
    quarantine = tmp_path / "quarantine"
    monkeypatch.setenv("PROCESSED_DIR", str(processed))
    monkeypatch.setenv("QUARANTINE_DIR", str(quarantine))
    get_settings.cache_clear()
    try:
        yield processed, quarantine
    finally:
        get_settings.cache_clear()
