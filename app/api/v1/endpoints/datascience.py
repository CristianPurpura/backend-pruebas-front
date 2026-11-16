"""Endpoints de brechas de talento y oferta formativa (issue #74).

Consumen el módulo de Data Science del equipo de Data (`DataAnalyst`) a
través del cliente con cache y fallback:

* `GET /api/v1/skills` → ranking de brechas con habilidades emergentes.
* `GET /api/v1/skills/{ocupacion_id}` → detalle de una ocupación.
* `GET /api/v1/gaps` → comparativa entre demanda laboral y oferta formativa.
"""

from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query

from app.core import catalogs
from app.schemas.datascience import (
    GapsResponse,
    GapsSummaryResponse,
    SkillDetailResponse,
    SkillsResponse,
)
from app.services.datascience import client as data_client
from app.services.datascience import mapper, summary
from app.services.datascience.brechas import brechas_de_ocupacion

router = APIRouter(prefix="/skills", tags=["Data Science"])


def _validar_pais(pais: str | None) -> str | None:
    """Normaliza el país o responde 400 si está fuera del alcance."""
    if not pais:
        return None
    codigo = pais.strip().upper()
    if codigo not in catalogs.PAISES_INFO:
        raise HTTPException(
            status_code=400,
            detail=f"País fuera del alcance regional: {pais}. Permitidos: "
            f"{', '.join(catalogs.PAISES_INFO)}.",
        )
    return codigo


def _validar_sector(sector: str | None) -> str | None:
    """Normaliza el sector (código, slug o nombre) al nombre canónico."""
    if not sector:
        return None
    nombre = catalogs.resolve_sector(sector)
    if not nombre:
        raise HTTPException(
            status_code=422,
            detail=f"Sector desconocido: {sector}. Permitidos: "
            f"{', '.join(catalogs.SECTORES.values())}.",
        )
    return nombre


def _sin_datos() -> HTTPException:
    """503 cuando no hay ni API de Data, ni cache, ni snapshot de referencia."""
    return HTTPException(
        status_code=503,
        detail=(
            "No hay datos de brechas disponibles: la API de Data no respondió y "
            "no hay caché ni snapshot de referencia. Levantar el repo DataAnalyst "
            "o definir DATA_API_URL."
        ),
    )


@router.get("", response_model=SkillsResponse)
async def listar_brechas(
    pais: Annotated[str | None, Query(description="Código ISO-3 (ARG, CHL, URY)")] = None,
    sector: Annotated[str | None, Query(description="Sector (código, slug o nombre)")] = None,
) -> SkillsResponse:
    """Brechas de talento con habilidades emergentes, ordenadas por severity.

    Cada ítem combina el *Talent Gap Score* (0-100), el diagnóstico de la
    brecha y las habilidades tradicionales y emergentes que la-cover.
    """
    codigo_pais = _validar_pais(pais)
    nombre_sector = _validar_sector(sector)

    respuesta = await data_client.consultar_data(
        data_client.RUTA_BRECHAS,
        {"pais": codigo_pais, "sector": nombre_sector},
    )
    if respuesta is None:
        raise _sin_datos()

    return mapper.respuesta_brechas(
        respuesta.datos,
        respuesta.fuente,
        respuesta.actualizado,
        {"pais": codigo_pais, "sector": nombre_sector},
    )


@router.get("/{ocupacion_id}", response_model=SkillDetailResponse)
async def detalle_brechas(
    ocupacion_id: str,
    pais: Annotated[str | None, Query(description="Código ISO-3 (ARG, CHL, URY)")] = None,
) -> SkillDetailResponse:
    """Brecha de una ocupación concreta (en los 3 países o en el pedido)."""
    clave = ocupacion_id.strip().upper()
    if not catalogs.is_occupation_format(clave):
        raise HTTPException(
            status_code=422,
            detail=(
                f"Formato de ocupación inválido: «{ocupacion_id}». "
                f"Usá el formato {catalogs.OCUPACION_IDS[0]}..{catalogs.OCUPACION_IDS[-1]}."
            ),
        )
    if clave not in catalogs.OCUPACIONES:
        raise HTTPException(
            status_code=404,
            detail=f"Ocupación no encontrada: {clave}. El catálogo incluye "
            f"{catalogs.OCUPACION_IDS[0]}..{catalogs.OCUPACION_IDS[-1]}.",
        )

    codigo_pais = _validar_pais(pais)

    resultado = await brechas_de_ocupacion(clave, codigo_pais)
    if resultado is None:
        raise _sin_datos()

    meta, items = resultado
    if not items:
        raise HTTPException(
            status_code=404,
            detail=f"Sin datos de brechas para la ocupación {clave}.",
        )

    ficha = catalogs.resolve_occupation(clave) or {}
    ocupacion: dict[str, Any] = {
        "id": clave,
        "nombre": ficha.get("nombre", ""),
        "sector": catalogs.sector_info(ficha.get("sector")),
        "ciuo08": ficha.get("ciuo08", ""),
        "habilidades_catalogo": catalogs.ocupacion_habilidades(clave),
    }

    return SkillDetailResponse(
        meta=meta,
        ocupacion=ocupacion,
        total=len(items),
        items=items,
    )


gaps_router = APIRouter(prefix="/gaps", tags=["Data Science"])


@gaps_router.get("", response_model=GapsResponse)
async def listar_brechas_formativas(
    pais: Annotated[str | None, Query(description="Código ISO-3 (ARG, CHL, URY)")] = None,
) -> GapsResponse:
    """Oferta formativa: demanda laboral de nuevos puestos frente a egresados.

    Por sector y país: cuántos puestos nuevos se generan, cuántos profesionales
    egresa el sistema educativo, cuál es el déficit y el coeficiente de
    cobertura educativa (CCE) con su semáforo.
    """
    codigo_pais = _validar_pais(pais)

    respuesta = await data_client.consultar_data(
        data_client.RUTA_COMPARATIVA, {"pais": codigo_pais}
    )
    if respuesta is None:
        raise _sin_datos()

    return mapper.respuesta_comparativa(
        respuesta.datos,
        respuesta.fuente,
        respuesta.actualizado,
        {"pais": codigo_pais},
    )


@gaps_router.get("/summary", response_model=GapsSummaryResponse)
async def resumen_brechas_formativas(
    pais: Annotated[str | None, Query(description="Código ISO-3 (ARG, CHL, URY)")] = None,
    sector: Annotated[str | None, Query(description="Sector (código, slug o nombre)")] = None,
) -> GapsSummaryResponse:
    """Totales y campos derivados de oferta/demanda y brecha para el dashboard.

    Devuelve los agregados regionales, por país y por sector, con el CCE
    ponderado por demanda y la brecha de cobertura calculada en el Backend.
    """
    codigo_pais = _validar_pais(pais)
    nombre_sector = _validar_sector(sector)

    respuesta = await data_client.consultar_data(
        data_client.RUTA_COMPARATIVA, {"pais": codigo_pais}
    )
    if respuesta is None:
        raise _sin_datos()

    cuerpo = mapper.respuesta_comparativa(
        respuesta.datos,
        respuesta.fuente,
        respuesta.actualizado,
        {"pais": codigo_pais, "sector": nombre_sector},
    )

    items = cuerpo.items
    if nombre_sector:
        items = [
            item
            for item in items
            if item.sector.strip().lower() == nombre_sector.strip().lower()
        ]

    return summary.construir_resumen(
        items,
        cuerpo.meta,
        {"pais": codigo_pais, "sector": nombre_sector},
    )


__all__ = ["gaps_router", "router"]
