"""Schemas del módulo de brechas de talento y oferta formativa (issue #74).

Contrato normalizado del payload de Data (`DataAnalyst/etl/data_science.py`),
para que el Frontend no dependa de la forma interna del equipo de Data.
"""

from typing import Any

from pydantic import BaseModel, Field


class DataSourceMeta(BaseModel):
    """Procedencia de los datos de la respuesta."""

    fuente: str = Field(description="live | cache | reference")
    actualizado: str | None = Field(default=None, description="Fecha del dato en la fuente")
    detalle: str = ""


class TgsComponenteScore(BaseModel):
    """Aporte de un componente con score propio (demanda o crecimiento)."""

    score: float
    peso: float
    aporte: float


class TgsComponenteCobertura(BaseModel):
    """Aporte del déficit de cobertura educativa al TGS."""

    brecha_pct: float
    peso: float
    aporte: float


class TgsDesglose(BaseModel):
    """Desglose del Talent Gap Score para explicarlo en el Frontend."""

    demanda: TgsComponenteScore
    crecimiento: TgsComponenteScore
    cobertura: TgsComponenteCobertura
    factor_pais: float
    tgs_calculado: float


class SkillItem(BaseModel):
    """Brecha de talento de una ocupación en un país."""

    pais: str
    pais_nombre: str = ""
    sector: str = ""
    ocupacion_id: str
    ocupacion_nombre: str = ""
    ciuo08: str = ""
    icol: float | None = Field(default=None, description="Índice de oportunidad laboral (ICOL)")
    score_brecha: float = Field(description="Talent Gap Score (0-100)")
    cce: float | None = Field(default=None, description="Coeficiente de cobertura educativa")
    score_demanda_100: float | None = Field(
        default=None, description="Score de demanda del mercado (0-100)."
    )
    score_crecimiento_100: float | None = Field(
        default=None, description="Score de crecimiento estimado (0-100)."
    )
    factor_madurez_pais: float | None = Field(
        default=None, description="Factor de madurez del país aplicado al TGS."
    )
    brecha_cobertura_pct: float | None = Field(
        default=None, description="Brecha de cobertura: max(0, 1 - CCE) * 100."
    )
    tgs_desglose: TgsDesglose | None = Field(
        default=None, description="Desglose 55/25/20 del Talent Gap Score."
    )
    diagnostico: str = ""
    icono: str = ""
    urgencia: str = ""
    habilidades_tradicionales: list[str] = Field(default_factory=list)
    habilidades_emergentes: list[str] = Field(default_factory=list)
    nivel_adopcion: str = ""
    impacto_ia: str = ""
    obsolescencia: str = ""
    is_projection: bool = True


class SkillsResponse(BaseModel):
    """Respuesta de `GET /api/v1/skills`."""

    meta: DataSourceMeta
    filtros: dict[str, Any] = Field(default_factory=dict)
    total: int = 0
    items: list[SkillItem] = Field(default_factory=list)


class SkillDetailResponse(BaseModel):
    """Respuesta de `GET /api/v1/skills/{ocupacion_id}`."""

    meta: DataSourceMeta
    ocupacion: dict[str, Any] = Field(default_factory=dict)
    total: int = 0
    items: list[SkillItem] = Field(default_factory=list)


class GapItem(BaseModel):
    """Comparación entre demanda laboral y oferta formativa de un sector."""

    pais: str
    pais_nombre: str = ""
    sector: str = ""
    carreras_afines: list[str] = Field(default_factory=list)
    egresados_anuales: float | None = Field(default=None)
    demanda_anual: float | None = Field(default=None)
    deficit_anual: float | None = Field(default=None)
    crecimiento_matricula_pct: float | None = Field(default=None)
    cce: float | None = Field(default=None, description="Coeficiente de cobertura educativa")
    diagnostico: str = ""
    estado: str = ""
    semaforo: str = ""
    fuentes: list[str] = Field(default_factory=list)
    is_projection: bool = True


class GapsResponse(BaseModel):
    """Respuesta de `GET /api/v1/gaps`."""

    meta: DataSourceMeta
    filtros: dict[str, Any] = Field(default_factory=dict)
    total: int = 0
    items: list[GapItem] = Field(default_factory=list)


__all__ = [
    "DataSourceMeta",
    "GapItem",
    "GapsResponse",
    "SkillDetailResponse",
    "SkillItem",
    "SkillsResponse",
    "TgsComponenteCobertura",
    "TgsComponenteScore",
    "TgsDesglose",
]
