from typing import Any

from app.core.config import get_settings
from app.services.connectors.base import (
    BaseConnector,
    ConnectorError,
    ConnectorResponse,
    SeriesPoint,
)


class DatosArgentinaConnector(BaseConnector):
    source_id = "datos_argentina"

    def __init__(
        self,
        base_url: str | None = None,
        series_ids: list[str] | None = None,
        timeout: float = 15.0,
    ) -> None:
        super().__init__(timeout=timeout)
        settings = get_settings()
        self.base_url = (base_url or settings.datos_ar_base_url).rstrip("/")
        self.series_ids = series_ids or settings.datos_ar_series_ids_list

    async def fetch(
        self,
        series_id: str | None = None,
        limit: int | None = None,
    ) -> ConnectorResponse:
        serie = series_id or self.series_ids[0]
        params: dict[str, Any] = {"ids": serie, "format": "json"}
        if limit:
            params["limit"] = limit
        try:
            response = await self.get("/series/api/series/", params=params)
            payload = response.json()
        except ConnectorError as exc:
            return ConnectorResponse.failure(self.source_id, exc.message)
        except ValueError as exc:
            return ConnectorResponse.failure(self.source_id, f"respuesta no JSON: {exc}")
        if not isinstance(payload, dict):
            return ConnectorResponse.failure(
                self.source_id, f"payload inesperado: {type(payload).__name__}"
            )
        return ConnectorResponse(
            source_id=self.source_id,
            ok=True,
            payload=payload,
            points=self.parse_points(payload),
        )

    @staticmethod
    def parse_points(payload: dict[str, Any]) -> list[SeriesPoint]:
        points: list[SeriesPoint] = []
        for row in payload.get("data") or []:
            if not row or row[0] is None or len(row) < 2 or row[1] is None:
                continue
            points.append(SeriesPoint(periodo=str(row[0]), valor=float(row[1])))
        return points
