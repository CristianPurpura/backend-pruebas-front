from app.services.connectors.base import (
    BaseConnector,
    ConnectorError,
    ConnectorResponse,
    SeriesPoint,
)
from app.services.connectors.banco_mundial import BancoMundialConnector
from app.services.connectors.datos_argentina import DatosArgentinaConnector
from app.services.connectors.simel_chile import SimelChileConnector

CONNECTORS: dict[str, type[BaseConnector]] = {
    DatosArgentinaConnector.source_id: DatosArgentinaConnector,
    BancoMundialConnector.source_id: BancoMundialConnector,
    SimelChileConnector.source_id: SimelChileConnector,
}

__all__ = [
    "BaseConnector",
    "BancoMundialConnector",
    "CONNECTORS",
    "ConnectorError",
    "ConnectorResponse",
    "DatosArgentinaConnector",
    "SeriesPoint",
    "SimelChileConnector",
]
