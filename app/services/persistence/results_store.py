"""Persistencia de resultados históricos de los índices (IDELR / ICOL).

Guarda los cálculos que produce `app/services/calculators/employability.py`
para que se pueda mirar el pasado: qué valía el índice, cuándo se calculó y
con qué metodología.

Dos garantías:

* **Idempotencia**: dos snapshots del mismo día para la misma combinación
  se actualizan en lugar de duplicarse (clave `dedupe_key`).
* **Degradación limpia**: sin `DATABASE_URL` configurada el servicio no
  rompe; devuelve `None` y el endpoint de escritura responde 503.
"""

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.indicator_result import TIPO_ICOL, TIPO_IDELR, IndicatorResult

# Versión de la metodología usada en los snapshots. Se cambia cuando cambia
# la fórmula o los pesos, para poder distinguir snapshots comparables.
METODOLOGIA_VERSION = "idelr-icol-2026-11"


def _momento() -> datetime:
    """Momento actual con zona horaria, para ordenar snapshots."""
    return datetime.now(timezone.utc)


def _dedupe_key(
    tipo: str,
    pais: str,
    anio: int | None,
    ocupacion_id: str | None,
    fecha: str,
) -> str:
    """Clave de idempotencia: `tipo|pais|anio|ocupacion|fecha`."""
    return f"{tipo}|{pais}|{anio or '-'}|{ocupacion_id or '-'}|{fecha}"


def snapshot_idelr(serie: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Convierte la serie IDELR en filas persistibles."""
    filas: list[dict[str, Any]] = []
    for fila in serie:
        filas.append(
            {
                "tipo": TIPO_IDELR,
                "pais": str(fila.get("pais_codigo_iso3") or "").upper(),
                "anio": int(fila["anio"]) if fila.get("anio") is not None else None,
                "ocupacion_id": None,
                "valor": float(fila.get("indice_sintetico") or 0.0),
                "categoria": str(fila.get("tendencia") or "") or None,
                "cobertura_pct": (
                    float(fila["cobertura_variables_pct"])
                    if fila.get("cobertura_variables_pct") is not None
                    else None
                ),
                "payload": dict(fila),
            }
        )
    return filas


def snapshot_icol(
    ranking: Sequence[Mapping[str, Any]],
    anio_referencia: int | None,
) -> list[dict[str, Any]]:
    """Convierte el ranking ICOL en filas persistibles.

    El ICOL no tiene un año propio (usa el entorno macro más reciente), así
    que se registra `anio_referencia` para saber con qué panel se calculó.
    """
    filas: list[dict[str, Any]] = []
    for fila in ranking:
        filas.append(
            {
                "tipo": TIPO_ICOL,
                "pais": str(fila.get("pais_codigo_iso3") or "").upper(),
                "anio": anio_referencia,
                "ocupacion_id": str(fila.get("ocupacion_id") or "").upper() or None,
                "valor": float(fila.get("indice_oportunidad_icol") or 0.0),
                "categoria": str(fila.get("categoria_oportunidad") or "") or None,
                "cobertura_pct": None,
                "payload": dict(fila),
            }
        )
    return filas


async def save_snapshot(
    session: AsyncSession,
    filas: Sequence[Mapping[str, Any]],
    metodologia_version: str = METODOLOGIA_VERSION,
    fecha: str | None = None,
) -> dict[str, int]:
    """Guarda un snapshot y devuelve el conteo de escrituras.

    Las filas con la misma `dedupe_key` (mismo tipo, país, año, ocupación y
    día) se **actualizan** en lugar de duplicarse.
    """
    dia = fecha or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    insertados = 0
    actualizados = 0

    for fila in filas:
        tipo = str(fila["tipo"])
        clave = _dedupe_key(
            tipo,
            str(fila.get("pais") or ""),
            fila.get("anio"),
            fila.get("ocupacion_id"),
            dia,
        )
        existente = await session.scalar(
            select(IndicatorResult).where(IndicatorResult.dedupe_key == clave)
        )
        valores = {
            "tipo": tipo,
            "pais": str(fila.get("pais") or ""),
            "anio": fila.get("anio"),
            "ocupacion_id": fila.get("ocupacion_id"),
            "valor": fila.get("valor"),
            "categoria": fila.get("categoria"),
            "cobertura_pct": fila.get("cobertura_pct"),
            "metodologia_version": metodologia_version,
            "payload": fila.get("payload") or {},
            "dedupe_key": clave,
            # Se fija explícitamente (y no con `server_default`) para que dos
            # snapshots del mismo día queden ordenables por fecha real.
            "calculado_en": _momento(),
        }
        if existente is None:
            session.add(IndicatorResult(**valores))
            insertados += 1
        else:
            for campo, valor in valores.items():
                setattr(existente, campo, valor)
            actualizados += 1

    await session.commit()
    return {"insertados": insertados, "actualizados": actualizados, "total": len(filas)}


async def history(
    session: AsyncSession,
    tipo: str | None = None,
    pais: str | None = None,
    ocupacion_id: str | None = None,
    anio_desde: int | None = None,
    anio_hasta: int | None = None,
    limite: int = 200,
) -> list[IndicatorResult]:
    """Devuelve el histórico, del snapshot más reciente al más antiguo."""
    consulta = select(IndicatorResult)
    if tipo:
        consulta = consulta.where(IndicatorResult.tipo == tipo.upper())
    if pais:
        consulta = consulta.where(IndicatorResult.pais == pais.upper())
    if ocupacion_id:
        consulta = consulta.where(IndicatorResult.ocupacion_id == ocupacion_id.upper())
    if anio_desde is not None:
        consulta = consulta.where(IndicatorResult.anio >= anio_desde)
    if anio_hasta is not None:
        consulta = consulta.where(IndicatorResult.anio <= anio_hasta)

    consulta = consulta.order_by(
        IndicatorResult.calculado_en.desc(),
        IndicatorResult.pais,
        IndicatorResult.ocupacion_id,
        IndicatorResult.anio,
    ).limit(max(1, min(limite, 1000)))
    resultado = await session.scalars(consulta)
    return list(resultado)


async def latest(
    session: AsyncSession,
    tipo: str | None = None,
    pais: str | None = None,
    ocupacion_id: str | None = None,
) -> list[IndicatorResult]:
    """Devuelve el snapshot más reciente de cada combinación."""
    consulta = select(IndicatorResult)
    if tipo:
        consulta = consulta.where(IndicatorResult.tipo == tipo.upper())
    if pais:
        consulta = consulta.where(IndicatorResult.pais == pais.upper())
    if ocupacion_id:
        consulta = consulta.where(IndicatorResult.ocupacion_id == ocupacion_id.upper())

    filas = list(await session.scalars(consulta))
    mas_recientes: dict[tuple[str, str, str | None, int | None], IndicatorResult] = {}
    for fila in filas:
        clave = (fila.tipo, fila.pais, fila.ocupacion_id, fila.anio)
        actual = mas_recientes.get(clave)
        if actual is None or fila.calculado_en > actual.calculado_en:
            mas_recientes[clave] = fila
    return sorted(
        mas_recientes.values(),
        key=lambda fila: (fila.tipo, fila.pais, fila.ocupacion_id or "", fila.anio or 0),
    )


async def purge(
    session: AsyncSession,
    tipo: str | None = None,
    antes_de: datetime | None = None,
) -> int:
    """Borra snapshots (por tipo y/o anteriores a una fecha)."""
    consulta = delete(IndicatorResult)
    if tipo:
        consulta = consulta.where(IndicatorResult.tipo == tipo.upper())
    if antes_de is not None:
        consulta = consulta.where(IndicatorResult.calculado_en < antes_de)
    resultado = await session.execute(consulta)
    await session.commit()
    return int(resultado.rowcount or 0)


__all__ = [
    "METODOLOGIA_VERSION",
    "history",
    "latest",
    "purge",
    "snapshot_idelr",
    "snapshot_icol",
]
