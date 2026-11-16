"""Brechas de talento de una ocupación (issue #75).

Extrae a un servicio la consulta que antes vivía dentro del endpoint
`GET /api/v1/skills/{ocupacion_id}`, para que el perfil de ocupación
(`GET /api/v1/occupations/{id}`) y el detalle de brechas consuman **la misma**
fuente, el mismo filtrado y la misma degradación `live → cache → reference`.

No lanza HTTPException: devuelve `None` cuando no hay ninguna fuente
disponible, y deja que cada endpoint decida (503 en `/skills`, bloque con
`brecha_disponible: false` en el perfil).
"""

from __future__ import annotations

from app.schemas.datascience import DataSourceMeta, SkillItem
from app.services.datascience import client as data_client
from app.services.datascience import mapper


async def brechas_de_ocupacion(
    ocupacion_id: str,
    pais: str | None = None,
) -> tuple[DataSourceMeta, list[SkillItem]] | None:
    """Filas de brechas de `ocupacion_id`, opcionalmente acotadas a `pais`.

    Devuelve `(meta, items)`; `items` puede quedar vacío si la ocupación no
    está en el payload de Data. Devuelve `None` si no hay live, cache ni
    referencia.
    """
    respuesta = await data_client.consultar_data(
        data_client.RUTA_BRECHAS,
        {"pais": pais},
    )
    if respuesta is None:
        return None

    cuerpo = mapper.respuesta_brechas(
        respuesta.datos,
        respuesta.fuente,
        respuesta.actualizado,
        {"pais": pais, "ocupacion": ocupacion_id},
    )
    items = [item for item in cuerpo.items if item.ocupacion_id == ocupacion_id]
    return cuerpo.meta, items


__all__ = ["brechas_de_ocupacion"]
