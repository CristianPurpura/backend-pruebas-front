import asyncio
import json
from pathlib import Path

from app.services.connectors.base import ConnectorResponse, SeriesPoint
from app.services.ingestor import ingest
from app.services.storage.raw_store import read_raw


class StubConnector:
    source_id = "stub"

    def __init__(self, response: ConnectorResponse) -> None:
        self._response = response

    async def fetch(self, **kwargs) -> ConnectorResponse:
        return self._response


def _ok_response() -> ConnectorResponse:
    return ConnectorResponse(
        source_id="stub",
        ok=True,
        payload={"data": [[1, 2]]},
        points=[SeriesPoint(periodo="2025-01", valor=1.0)],
    )


def _error_response() -> ConnectorResponse:
    return ConnectorResponse.failure("stub", "HTTP 500")


def test_ingest_ok_almacena_registro(tmp_path: Path):
    report = asyncio.run(ingest(StubConnector(_ok_response()), raw_dir=tmp_path))
    assert report.ok
    assert report.received == 1
    assert report.error is None
    path = Path(report.stored_path)
    assert path.exists()
    record = json.loads(path.read_text(encoding="utf-8").strip())
    assert record["status"] == "ok"
    assert record["raw_payload"] == {"data": [[1, 2]]}


def test_ingest_falla_almacena_error(tmp_path: Path):
    report = asyncio.run(ingest(StubConnector(_error_response()), raw_dir=tmp_path))
    assert not report.ok
    assert report.received == 0
    assert report.error == "HTTP 500"
    records = read_raw("stub", raw_dir=tmp_path)
    assert len(records) == 1
    assert records[0]["status"] == "error"
    assert records[0]["error"] == "HTTP 500"


def test_ingest_parametros_se_delegan_al_conector(tmp_path: Path):
    class ParamConnector(StubConnector):
        def __init__(self):
            super().__init__(_ok_response())
            self.received_params = None

        async def fetch(self, **kwargs):
            self.received_params = kwargs
            return self._response

    connector = ParamConnector()
    asyncio.run(ingest(connector, raw_dir=tmp_path, series_id="X", limit=5))
    assert connector.received_params == {"series_id": "X", "limit": 5}
