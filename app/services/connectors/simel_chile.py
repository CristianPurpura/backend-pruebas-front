import io
import json
from typing import Any

import pandas as pd

from app.core.config import get_settings
from app.services.connectors.base import (
    BaseConnector,
    ConnectorError,
    ConnectorResponse,
    SeriesPoint,
)

DEFAULT_DATAFLOW = "CL01,DF_DES_SEXO,1.0"
PERIOD_COLUMN = "TIME_PERIOD"
VALUE_COLUMN = "OBS_VALUE"


class SimelChileConnector(BaseConnector):
    """Series laborales de Chile (SIMEL/ENE) vía SDMX del INE.

    www.simel.gob.cl responde 418 a clientes automatizados; las mismas series
    ENE se consultan por el servicio SDMX oficial de INE (sdmx.ine.gob.cl).
    """

    source_id = "simel_chile"

    def __init__(
        self,
        base_url: str | None = None,
        dataflow: str = DEFAULT_DATAFLOW,
        timeout: float = 25.0,
    ) -> None:
        super().__init__(timeout=timeout)
        settings = get_settings()
        self.base_url = (base_url or settings.simel_base_url).rstrip("/")
        self.dataflow = dataflow

    async def fetch(
        self,
        start_period: str = "2025",
        end_period: str = "2025",
    ) -> ConnectorResponse:
        try:
            response = await self.get(
                f"/data/{self.dataflow}",
                params={
                    "format": "csv",
                    "startPeriod": start_period,
                    "endPeriod": end_period,
                },
            )
            dataframe = pd.read_csv(io.StringIO(response.text))
        except ConnectorError as exc:
            return ConnectorResponse.failure(self.source_id, exc.message)
        except (ValueError, pd.errors.ParserError) as exc:
            return ConnectorResponse.failure(self.source_id, f"CSV inválido: {exc}")
        records = json.loads(dataframe.to_json(orient="records", date_format="iso"))
        return ConnectorResponse(
            source_id=self.source_id,
            ok=True,
            payload={"dataflow": self.dataflow, "records": records},
            points=self.parse_points(dataframe),
        )

    @staticmethod
    def parse_points(dataframe: pd.DataFrame) -> list[SeriesPoint]:
        if PERIOD_COLUMN not in dataframe.columns or VALUE_COLUMN not in dataframe.columns:
            return []
        points: list[SeriesPoint] = []
        for period, value in dataframe[[PERIOD_COLUMN, VALUE_COLUMN]].itertuples(index=False):
            if pd.isna(period) or pd.isna(value):
                continue
            points.append(SeriesPoint(periodo=str(period), valor=float(value)))
        return points
