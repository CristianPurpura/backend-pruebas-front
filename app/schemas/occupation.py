"""Ficha consolidada de una ocupación (`GET /api/v1/occupations/{id}`).

El perfil mezcla tres cosas: la ficha técnica del catálogo canónico
(`app/core/catalogs.py`), el índice de oportunidad ICOL calculado con la
metodología del equipo de Data y la comparación entre los tres países del
alcance regional.

> Contrato v2: el bloque `trazabilidad` ya no expone `data_type` (que en el
> contrato de carga pasó a ser la unidad de medida). La semántica de dato
> observado vs. proyectado vive en `is_projection`.
"""

from pydantic import BaseModel, Field


class PaisPerfil(BaseModel):
    """País del perfil."""

    codigo: str = Field(description="Código ISO-3: ARG, CHL o URY.")
    nombre: str


class SectorPerfil(BaseModel):
    """Sector productivo de la ocupación."""

    id: str = Field(description="Código canónico del sector: TEC, SAL, ENE, TUR o ECO.")
    slug: str
    nombre: str


class OcupacionPerfil(BaseModel):
    """Identificación de la ocupación."""

    id: str = Field(description="Identificador del catálogo: OCUP_01..OCUP_20.")
    nombre: str
    ciuo08: str = Field(description="Clasificación CIUO-08 / ISCO-08.")


class ScoresICOL(BaseModel):
    """Dimensiones normalizadas a 0-100 que componen el ICOL."""

    demanda: float = Field(description="Score del nivel de demanda del mercado.")
    crecimiento: float = Field(description="Score del crecimiento anual estimado.")
    entorno_macro: float = Field(description="IDELR del país (entorno macroeconómico).")


class RankingsICOL(BaseModel):
    """Posición de la ocupación dentro de cada recorte."""

    regional: int
    pais: int
    sector: int


class IndicadoresPerfil(BaseModel):
    """Indicadores y clasificación de oportunidad de la ocupación."""

    nivel_demanda: str
    crecimiento_anual_pct: float
    icol: float = Field(ge=0, le=100, description="Índice Compuesto de Oportunidad Laboral.")
    categoria_oportunidad: str
    icono: str = ""
    prioridad_formacion: str = ""
    scores: ScoresICOL
    rankings: RankingsICOL


class ComparacionPais(BaseModel):
    """ICOL de la misma ocupación en otro país, para comparar."""

    codigo: str
    nombre: str
    icol: float
    ranking_pais: int
    categoria_oportunidad: str


class TrazabilidadPerfil(BaseModel):
    """Origen del perfil y del índice que expone."""

    fuente: str
    fuente_url: str
    actualizado: str = Field(description="Fecha de la última versión del catálogo (AAAA-MM-DD).")
    is_projection: bool = Field(
        description=(
            "True si los valores del perfil son estimaciones: el nivel de demanda y el "
            "crecimiento anual del catálogo son proyecciones, no observaciones."
        )
    )
    origen_indice: str = Field(description="`processed` si hay datasets cargados, `fallback` si no.")
    datasets: list[str] = Field(default_factory=list, description="Datasets normalizados usados en el cálculo.")


class OccupationResponse(BaseModel):
    """Respuesta de `GET /api/v1/occupations/{occupation_id}`."""

    pais: PaisPerfil
    sector: SectorPerfil
    ocupacion: OcupacionPerfil
    indicadores: IndicadoresPerfil
    habilidades: list[str] = Field(default_factory=list)
    comparacion_paises: list[ComparacionPais] = Field(default_factory=list)
    trazabilidad: TrazabilidadPerfil


__all__ = [
    "ComparacionPais",
    "IndicadoresPerfil",
    "OcupacionPerfil",
    "OccupationResponse",
    "PaisPerfil",
    "RankingsICOL",
    "ScoresICOL",
    "SectorPerfil",
    "TrazabilidadPerfil",
]
