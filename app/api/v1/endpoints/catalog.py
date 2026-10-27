"""Endpoints de catálogos: países, sectores y ocupaciones.

Reemplazan los mocks que hoy usa el frontend (`src/mocks/*.json`), exponiendo
los catálogos canónicos de `app/core/catalogs.py` con la misma forma de objeto.
"""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.core import catalogs
from app.schemas.catalog import CountryOut, OccupationOut, SectorOut

router = APIRouter()


@router.get("/countries", response_model=list[CountryOut])
def get_countries() -> list[CountryOut]:
    """Países del alcance regional del Observatorio."""
    return [
        CountryOut(id=codigo, nombre=pais["nombre"], iso2=pais["iso2"], iso3=pais["iso3"])
        for codigo, pais in catalogs.PAISES_INFO.items()
    ]


@router.get("/sectors", response_model=list[SectorOut])
def get_sectors() -> list[SectorOut]:
    """Sectores productivos del MVP (con el slug que usa el frontend)."""
    return [
        SectorOut(id=codigo, slug=catalogs.SECTOR_SLUGS[codigo], nombre=nombre)
        for codigo, nombre in catalogs.SECTORES.items()
    ]


@router.get("/occupations", response_model=list[OccupationOut])
def get_occupations(
    sector: Annotated[
        str | None,
        Query(description="Filtra por sector: acepta el código (`TEC`) o el slug (`economia-conocimiento`)."),
    ] = None,
) -> list[OccupationOut]:
    """Ocupaciones del catálogo regional, opcionalmente filtradas por sector."""
    codigo_sector = None
    if sector is not None:
        codigo_sector = catalogs.resolve_sector_code(sector)
        if codigo_sector is None:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Sector desconocido: «{sector}». "
                    f"Usá uno de: {', '.join(catalogs.SECTOR_SLUGS.values())}."
                ),
            )

    fichas: list[OccupationOut] = []
    for ocupacion_id in catalogs.OCUPACION_IDS:
        ficha = catalogs.resolve_occupation(ocupacion_id)
        if ficha is None:
            continue
        sector_out = catalogs.sector_info(ficha["sector"])
        if sector_out is None:
            continue
        if codigo_sector and sector_out["id"] != codigo_sector:
            continue
        fichas.append(
            OccupationOut(
                id=ocupacion_id,
                nombre=ficha["nombre"],
                sector=SectorOut(**sector_out),
                ciuo08=ficha["ciuo08"],
                demanda=ficha["demanda"],
                crecimiento_anual_pct=catalogs.ocupacion_crecimiento_pct(ocupacion_id) or 0.0,
                habilidades=catalogs.ocupacion_habilidades(ocupacion_id),
            )
        )
    return fichas
