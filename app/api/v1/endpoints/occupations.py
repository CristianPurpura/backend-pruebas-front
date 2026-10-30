"""Ficha técnica de una ocupación: catálogo canónico + índice de oportunidad."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query

from app.core import catalogs
from app.schemas.occupation import OccupationResponse
from app.services.occupation_profile import construir_perfil

router = APIRouter()


@router.get("/{occupation_id}", response_model=OccupationResponse)
def get_occupation(
    occupation_id: Annotated[str, Path(description="Ocupación: OCUP_01..OCUP_20.")],
    pais: Annotated[str, Query(description="Código ISO-3 del país (default: ARG).")] = "ARG",
) -> OccupationResponse:
    """Perfil consolidado de una ocupación.

    Combina la ficha técnica del catálogo (CIUO-08, demanda, crecimiento,
    habilidades) con el ICOL calculado por `GET /api/v1/employability`. Si
    todavía no hay datasets cargados, el índice usa el entorno macro de
    referencia y el perfil lo deja explícito en `trazabilidad.origen_indice`.
    """
    clave = occupation_id.strip().upper()
    if not catalogs.is_occupation_format(clave):
        raise HTTPException(
            status_code=422,
            detail=(
                f"Formato de ocupación inválido: «{occupation_id}». "
                f"Usá el formato {catalogs.OCUPACION_IDS[0]}..{catalogs.OCUPACION_IDS[-1]}."
            ),
        )
    if clave not in catalogs.OCUPACIONES:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Ocupación no encontrada: {clave}. "
                f"El catálogo incluye {catalogs.OCUPACION_IDS[0]}..{catalogs.OCUPACION_IDS[-1]}."
            ),
        )

    codigo_pais = pais.strip().upper()
    if codigo_pais not in catalogs.PAISES_INFO:
        raise HTTPException(
            status_code=400,
            detail=(
                f"País fuera del alcance regional: {pais}. "
                f"Permitidos: {', '.join(catalogs.PAISES_INFO)}."
            ),
        )

    return OccupationResponse(**construir_perfil(clave, codigo_pais))


__all__ = ["router"]
