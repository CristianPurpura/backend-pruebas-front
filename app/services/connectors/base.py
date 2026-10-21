import abc
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ConnectorError(Exception):
    def __init__(self, source_id: str, message: str) -> None:
        super().__init__(f"[{source_id}] {message}")
        self.source_id = source_id
        self.message = message


@dataclass(frozen=True)
class SeriesPoint:
    periodo: str
    valor: float


@dataclass
class ConnectorResponse:
    source_id: str
    ok: bool
    fetched_at: str = field(default_factory=utc_now)
    payload: Any = None
    points: list[SeriesPoint] = field(default_factory=list)
    error: str | None = None

    @classmethod
    def failure(cls, source_id: str, message: str) -> "ConnectorResponse":
        return cls(source_id=source_id, ok=False, error=message)


class BaseConnector(abc.ABC):
    """Cliente base hacia una fuente externa. fetch() nunca lanza ConnectorError."""

    source_id: str = ""
    base_url: str = ""

    def __init__(self, timeout: float = 15.0) -> None:
        self.timeout = timeout

    async def get(self, path: str, params: dict[str, Any] | None = None) -> httpx.Response:
        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
        except httpx.HTTPError as exc:
            raise ConnectorError(self.source_id, f"error de red hacia {url}: {exc}") from exc
        if response.status_code != 200:
            raise ConnectorError(self.source_id, f"HTTP {response.status_code} en {url}")
        return response

    @abc.abstractmethod
    async def fetch(self, **kwargs: Any) -> ConnectorResponse:
        """Obtiene y parsea datos de la fuente."""
