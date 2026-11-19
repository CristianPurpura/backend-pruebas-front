"""Schemas de las series históricas y tendencias de los índices (#64).

La respuesta está pensada para que el Frontend dibuje gráficos sin tener que
desanidar el `payload` de cada snapshot: cada punto trae su `periodo` (el
valor que va en el eje X), el valor y la clasificación de tendencia.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class SerieFiltros(BaseModel):
    """Filtros aplicados a la consulta de series."""

    tipo: str
    pais: str | None = None
    ocupacion: str | None = None
    anio_desde: int | None = None
    anio_hasta: int | None = None


class SeriePunto(BaseModel):
    """Un punto chart-ready de la serie.

    `periodo` es el eje X: el año para datos macro (`"2023"`) o la fecha del
    snapshot para el ICOL (`"2026-11-18"`).
    """

    pais: str
    ocupacion_id: str | None = None
    periodo: str
    anio: int | None = None
    fecha_calculo: datetime | None = None
    valor: float
    categoria: str | None = None
    tendencia: str | None = None
    cobertura_pct: float | None = None
    metodologia_version: str | None = None


class SeriesResponse(BaseModel):
    """Respuesta de `GET /api/v1/employability/series`."""

    generated_at: str
    tipo: str
    fuente: str  # processed | database | live | fallback
    detalle: str = ""
    filtros: SerieFiltros
    total: int
    puntos: list[SeriePunto] = Field(default_factory=list)


class TendenciaEntrada(BaseModel):
    """Evolución de una entidad entre sus dos últimos puntos."""

    tipo: str
    pais: str
    ocupacion_id: str | None = None
    periodo_actual: str
    periodo_previo: str | None = None
    valor_actual: float
    valor_previo: float | None = None
    variacion_pct: float | None = None
    tendencia: str
    icono: str = ""


class TrendsResponse(BaseModel):
    """Respuesta de `GET /api/v1/employability/trends`."""

    generated_at: str
    tipo: str
    epsilon_pct: float
    fuente: str
    detalle: str = ""
    total: int
    tendencias: list[TendenciaEntrada] = Field(default_factory=list)


__all__ = [
    "SerieFiltros",
    "SeriePunto",
    "SeriesResponse",
    "TendenciaEntrada",
    "TrendsResponse",
]
