"""Cálculo del Índice de Empleabilidad (IDELR + ICOL).

Reimplementa localmente la metodología publicada por el equipo de Data
(`DataAnalyst/INFORME_METODOLOGICO_INDICES.md`), de modo que el Backend no
dependa de la disponibilidad de su API. La equivalencia numérica con la
implementación de Data se verifica en `tests/test_employability.py`.

* **IDELR** (Índice de Desarrollo Económico-Laboral Regional): normalización
  Min-Max acotada en `[0, 100]` y agregación lineal ponderada sobre cinco
  indicadores macroeconómicos, con clasificación de tendencia por banda
  muerta (epsilon = 1 %).
* **ICOL** (Índice Compuesto de Oportunidad Laboral): combina el IDELR más
  reciente del país, el nivel de demanda de la ocupación y su tasa de
  crecimiento estimada, ajustado por el factor de madurez contextual del país.
"""

import re
from typing import Any, Iterable, Mapping, Sequence

from app.core import catalogs

# ---------------------------------------------------------------------------
# 1. Configuración metodológica (IDELR)
# ---------------------------------------------------------------------------
VARIABLES_IDELR: dict[str, dict[str, Any]] = {
    "Variación Anual del PIB Real": {
        "dimension": "Economía",
        "peso": 0.25,
        "polaridad": "positiva",
        "min_teorico": -12.0,
        "max_teorico": 15.0,
        "descripcion": "Crecimiento del Producto Interno Bruto a precios constantes",
    },
    "Índice de Salario Real": {
        "dimension": "Salarios",
        "peso": 0.25,
        "polaridad": "positiva",
        "min_teorico": 60.0,
        "max_teorico": 120.0,
        "descripcion": "Poder adquisitivo de los salarios deflactado por IPC",
    },
    "Tasa de Ocupación": {
        "dimension": "Empleo",
        "peso": 0.20,
        "polaridad": "positiva",
        "min_teorico": 30.0,
        "max_teorico": 65.0,
        "descripcion": "Proporción de la población ocupada sobre la población total",
    },
    "Tasa de Finalización de Educación Secundaria": {
        "dimension": "Educación",
        "peso": 0.15,
        "polaridad": "positiva",
        "min_teorico": 40.0,
        "max_teorico": 90.0,
        "descripcion": "Tasa de graduación de nivel secundario/medio superior",
    },
    "Tasa de Desocupación Total": {
        "dimension": "Empleo",
        "peso": 0.15,
        "polaridad": "negativa",
        "min_teorico": 3.0,
        "max_teorico": 15.0,
        "descripcion": "Población desocupada en relación a la fuerza de trabajo activa",
    },
}

# ---------------------------------------------------------------------------
# 2. Configuración metodológica (ICOL)
# ---------------------------------------------------------------------------
DEMANDA_SCORE_MAP: dict[str, float] = {
    "Muy Alta": 100.0,
    "Alta": 80.0,
    "Media-Alta": 65.0,
    "Media": 50.0,
    "Baja": 30.0,
}

PAIS_FACTOR_MADUREZ_MAP: dict[str, float] = {
    "URY": 1.05,
    "CHL": 1.00,
    "ARG": 0.95,
}

DEFAULT_ICOL_WEIGHTS: dict[str, float] = {
    "peso_macro_idelr": 0.35,
    "peso_demanda_mercado": 0.40,
    "peso_crecimiento_estimado": 0.25,
}

# Valores de referencia del entorno macro cuando no hay serie cargada.
MACRO_FALLBACK: dict[str, float] = {"URY": 72.5, "CHL": 68.4, "ARG": 54.2}

MIN_CRECIMIENTO = 0.0
MAX_CRECIMIENTO = 30.0

CONTEXTO_PAIS: dict[str, str] = {
    "URY": "Alta Especialización en Servicios Globales",
    "CHL": "Liderazgo en Minería Verde, Energías y Fintech",
    "ARG": "Gran Volumen de Talento y AgTech/Biotecnología",
}

ICONOS_TENDENCIA = {
    "BASE": "⚪",
    "CRECIMIENTO": "🟢",
    "ESTABILIDAD": "🟡",
    "DISMINUCION": "🔴",
}

_RE_NUMERO = re.compile(r"([+-]?\d+(?:\.\d+)?)")


# ---------------------------------------------------------------------------
# 3. Utilidades matemáticas
# ---------------------------------------------------------------------------
def normalizar_valor(
    valor: float,
    min_val: float,
    max_val: float,
    polaridad: str = "positiva",
) -> float:
    """Normalización Min-Max acotada estrictamente en `[0, 100]`."""
    if max_val == min_val:
        return 50.0
    acotado = max(min(valor, max_val), min_val)
    if polaridad.lower() == "positiva":
        return ((acotado - min_val) / (max_val - min_val)) * 100.0
    return ((max_val - acotado) / (max_val - min_val)) * 100.0


def clasificar_tendencia(delta_pct: float | None, epsilon: float = 1.0) -> str:
    """Clasifica la dinámica interanual con banda muerta (`epsilon`)."""
    if delta_pct is None:
        return "BASE"
    if delta_pct > epsilon:
        return "CRECIMIENTO"
    if delta_pct < -epsilon:
        return "DISMINUCION"
    return "ESTABILIDAD"


def parse_tasa_crecimiento(valor: Any) -> float:
    """Extrae la tasa numérica de textos como `'+18.5% anual'`."""
    if isinstance(valor, (int, float)):
        return float(valor)
    if not isinstance(valor, str):
        return 0.0
    match = _RE_NUMERO.search(valor)
    if match:
        return float(match.group(1))
    return 0.0


def clasificar_categoria_oportunidad(score: float) -> dict[str, str]:
    """Traduce el score ICOL a una categoría cualitativa."""
    if score >= 85.0:
        return {
            "categoria": "Oportunidad Excepcional",
            "icono": "🌟",
            "prioridad_formacion": "Estratégica Inmediata",
        }
    if score >= 70.0:
        return {
            "categoria": "Alta Oportunidad",
            "icono": "🟢",
            "prioridad_formacion": "Alta Demanda",
        }
    if score >= 55.0:
        return {
            "categoria": "Oportunidad Moderada",
            "icono": "🟡",
            "prioridad_formacion": "Crecimiento Estable",
        }
    return {
        "categoria": "En Desarrollo / Emergente",
        "icono": "🔵",
        "prioridad_formacion": "Medio Plazo",
    }


# ---------------------------------------------------------------------------
# 4. IDELR: índice sintético macroeconómico
# ---------------------------------------------------------------------------
def calcular_idelr(
    filas: Iterable[Mapping[str, Any]],
    config: Mapping[str, Mapping[str, Any]] | None = None,
    epsilon: float = 1.0,
    pais_filtro: str | None = None,
    anio_inicio: int | None = None,
    anio_fin: int | None = None,
) -> list[dict[str, Any]]:
    """Calcula la serie IDELR por país y año.

    `filas` son registros en el esquema común (`pais_codigo_iso3`,
    `indicador_nombre`, `anio`, `valor`, ...).
    """
    configuracion = dict(config or VARIABLES_IDELR)
    suma_pesos = sum(float(cfg["peso"]) for cfg in configuracion.values())
    if suma_pesos <= 0:
        raise ValueError("La suma de ponderaciones debe ser mayor a 0.")

    seleccionadas: list[Mapping[str, Any]] = []
    for fila in filas:
        pais = str(fila.get("pais_codigo_iso3") or "").strip().upper()
        if pais_filtro and pais != pais_filtro.strip().upper():
            continue
        anio = int(fila.get("anio") or 0)
        if anio_inicio and anio < anio_inicio:
            continue
        if anio_fin and anio > anio_fin:
            continue
        seleccionadas.append(fila)

    # Rangos teóricos por defecto: los declarados en la configuración.
    for indicador, cfg in configuracion.items():
        if cfg.get("min_teorico") is not None and cfg.get("max_teorico") is not None:
            continue
        valores = [
            float(fila["valor"])
            for fila in seleccionadas
            if _indicador_de(fila) == indicador
        ]
        if not valores:
            continue
        cfg.setdefault("min_teorico", min(valores))
        cfg.setdefault("max_teorico", max(valores))

    grupos: dict[tuple[str, int], list[Mapping[str, Any]]] = {}
    for fila in seleccionadas:
        clave = (str(fila.get("pais_codigo_iso3") or "").strip().upper(), int(fila.get("anio") or 0))
        grupos.setdefault(clave, []).append(fila)

    resultados: list[dict[str, Any]] = []
    for (pais, anio), grupo in sorted(grupos.items()):
        indice_acumulado = 0.0
        peso_efectivo = 0.0
        desglose: dict[str, Any] = {}

        for fila in grupo:
            indicador = _indicador_de(fila)
            if indicador not in configuracion:
                continue
            cfg = configuracion[indicador]
            valor_real = float(fila["valor"])
            valor_normalizado = normalizar_valor(
                valor_real,
                float(cfg["min_teorico"]),
                float(cfg["max_teorico"]),
                str(cfg.get("polaridad", "positiva")),
            )
            peso_normalizado = float(cfg["peso"]) / suma_pesos
            contribucion = valor_normalizado * peso_normalizado

            indice_acumulado += contribucion
            peso_efectivo += peso_normalizado
            desglose[indicador] = {
                "valor_original": valor_real,
                "unidad": fila.get("unidad_medida", ""),
                "valor_normalizado_100": round(valor_normalizado, 2),
                "peso_asignado": round(peso_normalizado, 4),
                "contribucion_al_indice": round(contribucion, 2),
            }

        if peso_efectivo > 0:
            resultados.append(
                {
                    "pais_codigo_iso3": pais,
                    "pais_nombre": catalogs.resolve_country(pais) or pais,
                    "anio": anio,
                    "indice_sintetico": round(indice_acumulado / peso_efectivo, 2),
                    "cobertura_variables_pct": round(peso_efectivo * 100, 1),
                    "desglose_variables": desglose,
                }
            )

    resultados.sort(key=lambda fila: (fila["pais_codigo_iso3"], fila["anio"]))

    previos: dict[str, float | None] = {}
    for fila in resultados:
        pais = fila["pais_codigo_iso3"]
        indice_previo = previos.get(pais)
        fila["indice_previo"] = indice_previo
        if indice_previo:
            delta = round(fila["indice_sintetico"] - indice_previo, 2)
            variacion = round((delta / indice_previo) * 100.0, 2)
        else:
            delta = None
            variacion = None
        fila["delta_absoluto"] = delta
        fila["variacion_interanual_pct"] = variacion
        tendencia = clasificar_tendencia(variacion, epsilon=epsilon)
        fila["tendencia"] = tendencia
        fila["tendencia_icono"] = ICONOS_TENDENCIA[tendencia]
        previos[pais] = fila["indice_sintetico"]

    return resultados


def _indicador_de(fila: Mapping[str, Any]) -> str:
    """Nombre del indicador con la homologación del catálogo de Data."""
    nombre = fila.get("indicador_nombre") or fila.get("metric_name") or ""
    return catalogs.homologate_indicator(nombre)


def macro_scores(serie_idelr: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    """Último IDELR disponible por país (insumo del ICOL)."""
    ultimos: dict[str, float] = {}
    for fila in serie_idelr:
        ultimos[str(fila["pais_codigo_iso3"])] = float(fila["indice_sintetico"])
    return ultimos


# ---------------------------------------------------------------------------
# 5. ICOL: índice compuesto de oportunidad laboral
# ---------------------------------------------------------------------------
def expandir_ocupaciones() -> list[dict[str, Any]]:
    """Expande el catálogo de 20 ocupaciones a las 60 combinaciones con 3 países."""
    filas: list[dict[str, Any]] = []
    for pais in ("URY", "CHL", "ARG"):
        for ocupacion_id, ficha in catalogs.OCUPACIONES.items():
            filas.append(
                {
                    "pais_codigo_iso3": pais,
                    "pais_nombre": catalogs.resolve_country(pais) or pais,
                    "sector": ficha["sector"],
                    "ocupacion_id": ocupacion_id,
                    "ocupacion_nombre": ficha["nombre"],
                    "codigo_ciuo08_oit": ficha["ciuo08"],
                    "nivel_demanda": ficha["demanda"],
                    "tendencia_crecimiento_estimada": ficha["crecimiento"],
                    "habilidades_clave": ficha["habilidades"],
                    "contexto_pais": CONTEXTO_PAIS.get(pais, ""),
                }
            )
    return filas


def calcular_icol(
    ocupaciones: Sequence[Mapping[str, Any]] | None = None,
    macro: Mapping[str, float] | None = None,
    weights: Mapping[str, float] | None = None,
    pais_filtro: str | None = None,
    sector_filtro: str | None = None,
) -> list[dict[str, Any]]:
    """Calcula el ICOL para cada combinación país × ocupación."""
    datos = list(ocupaciones if ocupaciones is not None else expandir_ocupaciones())
    pesos = dict(weights or DEFAULT_ICOL_WEIGHTS)

    w_macro = float(pesos.get("peso_macro_idelr", 0.35))
    w_demanda = float(pesos.get("peso_demanda_mercado", 0.40))
    w_crecimiento = float(pesos.get("peso_crecimiento_estimado", 0.25))
    suma_w = w_macro + w_demanda + w_crecimiento
    if suma_w <= 0:
        raise ValueError("La suma de ponderaciones de ocupación debe ser mayor a 0.")
    w_macro /= suma_w
    w_demanda /= suma_w
    w_crecimiento /= suma_w

    scores_macro = dict(macro) if macro else dict(MACRO_FALLBACK)

    filas: list[dict[str, Any]] = []
    for fila in datos:
        pais = str(fila.get("pais_codigo_iso3") or "").strip().upper()
        if pais_filtro and pais != pais_filtro.strip().upper():
            continue
        sector = str(fila.get("sector") or "")
        if sector_filtro and sector.lower() != sector_filtro.strip().lower():
            continue

        nivel_demanda = str(fila.get("nivel_demanda") or "Media")
        score_demanda = DEMANDA_SCORE_MAP.get(nivel_demanda, 50.0)

        crecimiento = parse_tasa_crecimiento(
            fila.get("tendencia_crecimiento_estimada", fila.get("tendencia_crecimiento", "0%"))
        )
        score_crecimiento = normalizar_valor(
            crecimiento, MIN_CRECIMIENTO, MAX_CRECIMIENTO, polaridad="positiva"
        )

        score_macro = float(scores_macro.get(pais, 60.0))
        factor_madurez = PAIS_FACTOR_MADUREZ_MAP.get(pais, 1.0)

        score_base = (
            w_macro * score_macro
            + w_demanda * score_demanda
            + w_crecimiento * score_crecimiento
        )
        score_final = min(max(score_base * factor_madurez, 0.0), 100.0)
        diagnostico = clasificar_categoria_oportunidad(score_final)

        filas.append(
            {
                "pais_codigo_iso3": pais,
                "pais_nombre": fila.get("pais_nombre") or catalogs.resolve_country(pais) or pais,
                "sector": sector,
                "ocupacion_id": fila.get("ocupacion_id"),
                "ocupacion_nombre": fila.get("ocupacion_nombre"),
                "codigo_ciuo08_oit": fila.get("codigo_ciuo08_oit"),
                "nivel_demanda": nivel_demanda,
                "score_demanda_100": round(score_demanda, 2),
                "crecimiento_anual_pct": crecimiento,
                "score_crecimiento_100": round(score_crecimiento, 2),
                "score_entorno_macro_100": round(score_macro, 2),
                "factor_madurez_pais": factor_madurez,
                "indice_oportunidad_icol": round(score_final, 2),
                "categoria_oportunidad": diagnostico["categoria"],
                "icono": diagnostico["icono"],
                "prioridad_formacion": diagnostico["prioridad_formacion"],
                "habilidades_clave": fila.get("habilidades_clave", ""),
                "contexto_pais": fila.get("contexto_pais", ""),
            }
        )

    return _agregar_rankings(filas)


def _agregar_rankings(filas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Calcula los rankings regional, por país y por sector (method='min')."""
    if not filas:
        return filas

    ordenadas = sorted(
        filas,
        key=lambda fila: (-fila["indice_oportunidad_icol"], fila["pais_codigo_iso3"]),
    )

    def _rankear(subconjunto: list[dict[str, Any]]) -> None:
        for fila in subconjunto:
            posicion = 1 + sum(
                1
                for otra in subconjunto
                if otra["indice_oportunidad_icol"] > fila["indice_oportunidad_icol"]
            )
            fila["ranking"] = posicion

    _rankear(ordenadas)
    for fila in ordenadas:
        fila["ranking_regional"] = fila.pop("ranking")

    for _clave, grupo in _agrupar(ordenadas, "pais_codigo_iso3").items():
        _rankear(grupo)
        for fila in grupo:
            fila["ranking_pais"] = fila.pop("ranking")

    for _clave, grupo in _agrupar(ordenadas, "sector").items():
        _rankear(grupo)
        for fila in grupo:
            fila["ranking_sector"] = fila.pop("ranking")

    return ordenadas


def _agrupar(filas: list[dict[str, Any]], clave: str) -> dict[Any, list[dict[str, Any]]]:
    grupos: dict[Any, list[dict[str, Any]]] = {}
    for fila in filas:
        grupos.setdefault(fila.get(clave), []).append(fila)
    return grupos


__all__ = [
    "CONTEXTO_PAIS",
    "DEFAULT_ICOL_WEIGHTS",
    "DEMANDA_SCORE_MAP",
    "MACRO_FALLBACK",
    "PAIS_FACTOR_MADUREZ_MAP",
    "VARIABLES_IDELR",
    "calcular_icol",
    "calcular_idelr",
    "clasificar_categoria_oportunidad",
    "clasificar_tendencia",
    "expandir_ocupaciones",
    "macro_scores",
    "normalizar_valor",
    "parse_tasa_crecimiento",
]
