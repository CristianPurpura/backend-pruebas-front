from typing import Any

from app.core.config import get_settings
from app.services.connectors.base import (
    BaseConnector,
    ConnectorError,
    ConnectorResponse,
    SeriesPoint,
)

DEFAULT_INDICATOR = "SL.UEM.TOTL.ZS"
DEFAULT_COUNTRIES = ("ARG", "CHL", "URY")
DEFAULT_DATE_RANGE = "2015:2024"


class BancoMundialConnector(BaseConnector):
    source_id = "banco_mundial"

    def __init__(self, base_url: str | None = None, timeout: float = 20.0) -> None:
        super().__init__(timeout=timeout)
        settings = get_settings()
        self.base_url = (base_url or settings.banco_mundial_base_url).rstrip("/")

    async def fetch(
        self,
        indicator: str = DEFAULT_INDICATOR,
        countries: tuple[str, ...] | list[str] = DEFAULT_COUNTRIES,
        date_range: str = DEFAULT_DATE_RANGE,
    ) -> ConnectorResponse:
        payload: dict[str, Any] = {}
        points: list[SeriesPoint] = []
        try:
            for country in countries:
                response = await self.get(
                    f"/country/{country}/indicator/{indicator}",
                    params={"format": "json", "date": date_range, "per_page": 100},
                )
                data = response.json()
                payload[country] = data
                points.extend(self.parse_points(data))
        except ConnectorError as exc:
            return ConnectorResponse.failure(self.source_id, exc.message)
        except (ValueError, TypeError) as exc:
            return ConnectorResponse.failure(self.source_id, f"respuesta no JSON: {exc}")
        return ConnectorResponse(
            source_id=self.source_id,
            ok=True,
            payload=payload,
            points=points,
        )

    @staticmethod
    def parse_points(data: Any) -> list[SeriesPoint]:
        if not isinstance(data, list) or len(data) < 2 or not isinstance(data[1], list):
            return []
        points: list[SeriesPoint] = []
        for observation in data[1]:
            if not isinstance(observation, dict):
                continue
            value = observation.get("value")
            period = observation.get("date")
            if value is None or period is None:
                continue
            points.append(SeriesPoint(periodo=str(period), valor=float(value)))
        return points
