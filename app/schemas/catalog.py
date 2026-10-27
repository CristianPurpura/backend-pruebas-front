"""Schemas de los catálogos del Observatorio.

Son los catálogos canónicos de `app/core/catalogs.py` expuestos al Frontend.
El objetivo es reemplazar los mocks del frontend (`src/mocks/*.json`) con datos
reales sin cambiar la forma de los objetos.

Contratos:
    * `GET /api/v1/countries`   -> listado de países del alcance regional.
    * `GET /api/v1/sectors`     -> sectores productivos del MVP.
    * `GET /api/v1/occupations` -> ocupaciones del catálogo (filtro por sector).
"""

from pydantic import BaseModel, Field


class CountryOut(BaseModel):
    """País del alcance regional (Argentina, Chile, Uruguay)."""

    id: str = Field(description="Código ISO-3 del país: ARG, CHL o URY.")
    nombre: str
    iso2: str = Field(description="Código ISO-2 corto: AR, CL o UY.")
    iso3: str


class SectorOut(BaseModel):
    """Sector productivo del MVP."""

    id: str = Field(description="Código canónico del sector: TEC, SAL, ENE, TUR o ECO.")
    slug: str = Field(description="Slug estable usado por el frontend (p. ej. `economia-conocimiento`).")
    nombre: str


class OccupationOut(BaseModel):
    """Ficha resumida de una ocupación del catálogo."""

    id: str = Field(description="Identificador de la ocupación: OCUP_01..OCUP_20.")
    nombre: str
    sector: SectorOut
    ciuo08: str = Field(description="Clasificación CIUO-08 / ISCO-08.")
    demanda: str = Field(description="Demanda estimada: Muy Alta, Alta o Media-Alta.")
    crecimiento_anual_pct: float = Field(description="Crecimiento anual estimado, en puntos porcentuales.")
    habilidades: list[str] = Field(default_factory=list, description="Habilidades clave del perfil.")
