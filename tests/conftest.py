import io
from collections.abc import Sequence

import pandas as pd
import pytest
from fastapi.testclient import TestClient

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

VALID_ROW = {
    "country_code": "ARG",
    "sector_id": "TEC",
    "occupation_id": "OCUP_01",
    "metric_name": "demanda_laboral",
    "metric_value": "1500.0",
    "period": "2025",
    "source_name": "INDEC-EPH",
    "data_type": "observed",
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
