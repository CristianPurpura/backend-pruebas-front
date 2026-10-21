"""Schemas del Índice de Empleabilidad (IDELR + ICOL).

Los nombres de campo siguen la convención publicada por el equipo de Data
(`DataAnalyst/INFORME_INTEGRACION_VISUAL_FRONTEND.md`) para que el Frontend
pueda consumir ambas APIs con los mismos tipos.
"""

from typing import Any

from pydantic import BaseModel, Field


class DimensionBreakdown(BaseModel):
    """Desglose de una dimensión (indicador) evaluada en el índice macro."""

    valor_original: float
    unidad: str = ""
    valor_normalizado_100: float
    peso_asignado: float
    contribucion_al_indice: float


class MacroIndexEntry(BaseModel):
    """IDELR de un país en un año."""

    pais_codigo_iso3: str
    pais_nombre: str
    anio: int
    indice_sintetico: float
    cobertura_variables_pct: float
    indice_previo: float | None = None
    delta_absoluto: float | None = None
    variacion_interanual_pct: float | None = None
    tendencia: str
    tendencia_icono: str = ""
    desglose_variables: dict[str, DimensionBreakdown] = Field(default_factory=dict)


class OccupationScore(BaseModel):
    """ICOL de una combinación país × ocupación."""

    pais_codigo_iso3: str
    pais_nombre: str
    sector: str
    ocupacion_id: str
    ocupacion_nombre: str
    codigo_ciuo08_oit: str = ""
    nivel_demanda: str
    score_demanda_100: float
    crecimiento_anual_pct: float
    score_crecimiento_100: float
    score_entorno_macro_100: float
    factor_madurez_pais: float
    indice_oportunidad_icol: float
    categoria_oportunidad: str
    icono: str = ""
    prioridad_formacion: str = ""
    habilidades_clave: str = ""
    contexto_pais: str = ""
    ranking_regional: int
    ranking_pais: int
    ranking_sector: int


class MethodologyInfo(BaseModel):
    """Parámetros metodológicos aplicados (trazabilidad del cálculo)."""

    indice_macro: str = "IDELR"
    indice_ocupacional: str = "ICOL"
    fuente_metodologia: str = "DataAnalyst/INFORME_METODOLOGICO_INDICES.md"
    epsilon_pct: float = 1.0
    variables_idelr: dict[str, Any] = Field(default_factory=dict)
    ponderaciones_icol: dict[str, float] = Field(default_factory=dict)
    metodo_normalizacion: str = "Min-Max acotado [0, 100] + agregación lineal ponderada"


class DataSourceInfo(BaseModel):
    """Origen de los datos usados en el cálculo."""

    tipo: str
    datasets: list[str] = Field(default_factory=list)
    detalle: str = ""


class EmployabilityFilters(BaseModel):
    """Filtros aplicados a la consulta."""

    pais: str | None = None
    sector: str | None = None
    ocupacion: str | None = None
    anio_inicio: int | None = None
    anio_fin: int | None = None


class EmployabilitySummary(BaseModel):
    """Resumen de la respuesta."""

    paises_evaluados: int
    ocupaciones_evaluadas: int
    indicadores_evaluados: int
    cobertura_variables_pct: float | None = None
    mejor_ocupacion: str | None = None
    mejor_indice_ocupacional: float | None = None


class EmployabilityResponse(BaseModel):
    """Respuesta de `GET /api/v1/employability`."""

    generated_at: str
    metodologia: MethodologyInfo
    fuente_datos: DataSourceInfo
    filtros: EmployabilityFilters
    serie_macro: list[MacroIndexEntry] = Field(default_factory=list)
    ranking_ocupaciones: list[OccupationScore] = Field(default_factory=list)
    resumen: EmployabilitySummary


__all__ = [
    "DataSourceInfo",
    "DimensionBreakdown",
    "EmployabilityFilters",
    "EmployabilityResponse",
    "EmployabilitySummary",
    "MacroIndexEntry",
    "MethodologyInfo",
    "OccupationScore",
]
