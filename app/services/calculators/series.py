"""Construcción de series históricas y tendencias (#64).

Transforma los cálculos del IDELR y los snapshots del ICOL en puntos planos
(`SeriePunto`) listos para alimentar gráficos de líneas o barras, y resume la
evolución de cada entidad en una clasificación alza/estabilidad/caída.

La clasificación reutiliza `clasificar_tendencia` de la metodología, con la
misma banda muerta (`epsilon`) que expone `GET /employability`.
"""

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from app.services.calculators.employability import ICONOS_TENDENCIA, clasificar_tendencia

# Valor por defecto de la banda muerta, alineado con la metodología publicada.
EPSILON_DEFAULT = 1.0


def _punto(
    *,
    pais: str,
    valor: float,
    periodo: str,
    ocupacion_id: str | None = None,
    anio: int | None = None,
    fecha_calculo: datetime | None = None,
    categoria: str | None = None,
    tendencia: str | None = None,
    cobertura_pct: float | None = None,
    metodologia_version: str | None = None,
) -> dict[str, Any]:
    return {
        "pais": pais,
        "ocupacion_id": ocupacion_id,
        "periodo": periodo,
        "anio": anio,
        "fecha_calculo": fecha_calculo,
        "valor": round(float(valor), 2),
        "categoria": categoria,
        "tendencia": tendencia,
        "cobertura_pct": cobertura_pct,
        "metodologia_version": metodologia_version,
    }


def serie_desde_idelr(
    serie: Sequence[Mapping[str, Any]],
    *,
    pais: str | None = None,
    anio_desde: int | None = None,
    anio_hasta: int | None = None,
) -> list[dict[str, Any]]:
    """Convierte la serie IDELR calculada en puntos chart-ready."""
    puntos: list[dict[str, Any]] = []
    for fila in serie:
        codigo_pais = str(fila.get("pais_codigo_iso3") or "").upper()
        if pais and codigo_pais != pais.upper():
            continue
        anio = fila.get("anio")
        if anio is not None:
            if anio_desde is not None and int(anio) < anio_desde:
                continue
            if anio_hasta is not None and int(anio) > anio_hasta:
                continue
        puntos.append(
            _punto(
                pais=codigo_pais,
                anio=int(anio) if anio is not None else None,
                periodo=str(anio),
                valor=float(fila.get("indice_sintetico") or 0.0),
                categoria=str(fila.get("tendencia") or "") or None,
                tendencia=str(fila.get("tendencia") or "") or None,
                cobertura_pct=(
                    float(fila["cobertura_variables_pct"])
                    if fila.get("cobertura_variables_pct") is not None
                    else None
                ),
            )
        )
    puntos.sort(key=lambda punto: (punto["pais"], punto["anio"] or 0))
    return puntos


def serie_desde_snapshots(
    filas: Sequence[Any],
    *,
    epsilon: float = EPSILON_DEFAULT,
) -> list[dict[str, Any]]:
    """Convierte resultados persistidos (`IndicatorResult`) en puntos.

    La tendencia se calcula entre snapshots consecutivos de la misma
    combinación país × ocupación; el primer snapshot queda como `BASE`.
    """
    puntos: list[dict[str, Any]] = []
    for fila in filas:
        calculado_en = getattr(fila, "calculado_en", None)
        periodo = (
            calculado_en.strftime("%Y-%m-%d")
            if isinstance(calculado_en, datetime)
            else str(getattr(fila, "anio", "") or "")
        )
        puntos.append(
            _punto(
                pais=str(getattr(fila, "pais", "") or "").upper(),
                ocupacion_id=getattr(fila, "ocupacion_id", None),
                anio=getattr(fila, "anio", None),
                periodo=periodo,
                fecha_calculo=calculado_en,
                valor=float(getattr(fila, "valor", 0.0) or 0.0),
                categoria=getattr(fila, "categoria", None),
                cobertura_pct=(
                    float(fila.cobertura_pct)
                    if getattr(fila, "cobertura_pct", None) is not None
                    else None
                ),
                metodologia_version=getattr(fila, "metodologia_version", None),
            )
        )

    # Orden cronológico dentro de cada combinación para calcular la variación.
    agrupados: dict[tuple[str, str | None], list[dict[str, Any]]] = {}
    for punto in puntos:
        agrupados.setdefault((punto["pais"], punto["ocupacion_id"]), []).append(punto)

    for grupo in agrupados.values():
        grupo.sort(key=lambda punto: punto["periodo"])
        for posicion, punto in enumerate(grupo):
            if posicion == 0:
                punto["tendencia"] = "BASE"
                continue
            previo = grupo[posicion - 1]["valor"]
            variacion = (
                round((punto["valor"] - previo) / previo * 100.0, 2) if previo else None
            )
            punto["tendencia"] = clasificar_tendencia(variacion, epsilon=epsilon)

    puntos.sort(
        key=lambda punto: (
            punto["pais"],
            punto["ocupacion_id"] or "",
            punto["periodo"],
        )
    )
    return puntos


def serie_icol_live(
    ranking: Sequence[Mapping[str, Any]],
    anio_referencia: int | None,
    *,
    fecha: datetime | None = None,
) -> list[dict[str, Any]]:
    """Devuelve el cálculo ICOL actual como un único punto por ocupación."""
    momento = fecha or datetime.now(timezone.utc)
    periodo = momento.strftime("%Y-%m-%d")
    puntos = [
        _punto(
            pais=str(fila.get("pais_codigo_iso3") or "").upper(),
            ocupacion_id=str(fila.get("ocupacion_id") or "").upper() or None,
            anio=anio_referencia,
            periodo=periodo,
            fecha_calculo=momento,
            valor=float(fila.get("indice_oportunidad_icol") or 0.0),
            categoria=str(fila.get("categoria_oportunidad") or "") or None,
            tendencia="BASE",
        )
        for fila in ranking
    ]
    puntos.sort(key=lambda punto: (punto["pais"], punto["ocupacion_id"] or ""))
    return puntos


def calcular_tendencias(
    puntos: Sequence[Mapping[str, Any]],
    epsilon: float = EPSILON_DEFAULT,
) -> list[dict[str, Any]]:
    """Resume la evolución de cada entidad con sus dos últimos puntos."""
    agrupados: dict[tuple[str, str | None], list[Mapping[str, Any]]] = {}
    for punto in puntos:
        clave = (str(punto["pais"]), punto.get("ocupacion_id"))
        agrupados.setdefault(clave, []).append(punto)

    tendencias: list[dict[str, Any]] = []
    for (pais, ocupacion_id), grupo in agrupados.items():
        ordenado = sorted(grupo, key=lambda punto: str(punto["periodo"]))
        actual = ordenado[-1]
        previo = ordenado[-2] if len(ordenado) > 1 else None

        valor_previo = float(previo["valor"]) if previo is not None else None
        valor_actual = float(actual["valor"])
        variacion = (
            round((valor_actual - valor_previo) / valor_previo * 100.0, 2)
            if valor_previo
            else None
        )
        tendencia = clasificar_tendencia(variacion, epsilon=epsilon)

        tendencias.append(
            {
                "tipo": actual.get("tipo"),
                "pais": pais,
                "ocupacion_id": ocupacion_id,
                "periodo_actual": str(actual["periodo"]),
                "periodo_previo": str(previo["periodo"]) if previo is not None else None,
                "valor_actual": valor_actual,
                "valor_previo": valor_previo,
                "variacion_pct": variacion,
                "tendencia": tendencia,
                "icono": ICONOS_TENDENCIA.get(tendencia, ""),
            }
        )

    tendencias.sort(key=lambda fila: (fila["pais"], fila["ocupacion_id"] or ""))
    return tendencias


__all__ = [
    "EPSILON_DEFAULT",
    "calcular_tendencias",
    "serie_desde_idelr",
    "serie_desde_snapshots",
    "serie_icol_live",
]
