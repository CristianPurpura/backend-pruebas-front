"""Validaciones compartidas de los filtros de la API.

Centraliza los mensajes de error para que `/employability`, `/history`,
`/series` y `/trends` respondan exactamente igual ante un país, ocupación o
tipo de índice fuera de catálogo.
"""

from fastapi import HTTPException

from app.core import catalogs

TIPOS_INDICE = ("IDELR", "ICOL")


def validar_pais(pais: str | None) -> str | None:
    """Normaliza el país a ISO-3 o responde 400 si está fuera del alcance."""
    if not pais:
        return None
    codigo = pais.strip().upper()
    if codigo not in catalogs.PAISES_INFO:
        raise HTTPException(
            status_code=400,
            detail=(
                f"País fuera del alcance regional: {pais}. Permitidos: "
                f"{', '.join(catalogs.PAISES_INFO)}."
            ),
        )
    return codigo


def validar_ocupacion(ocupacion: str | None) -> str | None:
    """Normaliza la ocupación (`OCUP_XX`) o responde 400 si no existe."""
    if not ocupacion:
        return None
    clave = ocupacion.strip().upper()
    if clave not in catalogs.OCUPACIONES:
        raise HTTPException(
            status_code=400,
            detail=f"Ocupación fuera del catálogo: {ocupacion}.",
        )
    return clave


def validar_tipo(tipo: str | None, default: str | None = "IDELR") -> str | None:
    """Normaliza el tipo de índice o responde 400 si no es IDELR/ICOL.

    `default=None` permite usar la validación en endpoints donde el tipo es
    opcional (por ejemplo, el último snapshot de todos los índices).
    """
    if tipo is None or not tipo.strip():
        return default
    clave = tipo.strip().upper()
    if clave not in TIPOS_INDICE:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Tipo de índice desconocido: {tipo}. Permitidos: "
                f"{', '.join(TIPOS_INDICE)}."
            ),
        )
    return clave


__all__ = ["TIPOS_INDICE", "validar_ocupacion", "validar_pais", "validar_tipo"]
