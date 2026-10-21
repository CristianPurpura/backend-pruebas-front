from pathlib import Path

from app.services.connectors.base import BaseConnector, ConnectorResponse
from app.services.storage.raw_store import append_raw


class IngestReport:
    def __init__(
        self,
        source_id: str,
        ok: bool,
        received: int,
        stored_path: str | None,
        error: str | None = None,
    ) -> None:
        self.source_id = source_id
        self.ok = ok
        self.received = received
        self.stored_path = stored_path
        self.error = error


async def ingest(
    connector: BaseConnector,
    raw_dir: str | Path | None = None,
    **params: object,
) -> IngestReport:
    """Flujo de recepción: fetch de la fuente → append del registro crudo."""
    response: ConnectorResponse = await connector.fetch(**params)
    if response.ok:
        path = append_raw(response.source_id, response.payload, status="ok", raw_dir=raw_dir)
        return IngestReport(
            source_id=response.source_id,
            ok=True,
            received=len(response.points),
            stored_path=str(path),
        )
    path = append_raw(
        response.source_id,
        None,
        status="error",
        error=response.error,
        raw_dir=raw_dir,
    )
    return IngestReport(
        source_id=response.source_id,
        ok=False,
        received=0,
        stored_path=str(path),
        error=response.error,
    )
