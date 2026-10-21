"""Mapeo del contrato de carga manual al esquema común del equipo Data.

El esquema común (`ESQUEMA_COLUMNAS` de `etl/cleaner.py` en DataAnalyst) tiene
10 columnas. El Backend agrega dos columnas propias para no perder
información que el contrato de carga manual sí trae: `occupation_id` e
`is_projection`.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from app.core import catalogs

# Esquema común aprobado por el equipo de Data (etl/cleaner.py).
COMMON_COLUMNS: list[str] = [
    "pais_codigo_iso3",
    "pais_nombre",
    "dimension",
    "indicador_nombre",
    "anio",
    "periodo",
    "valor",
    "unidad_medida",
    "fuente_oficial",
    "fecha_extraccion",
]

# Columnas propias del Backend (extensión sobre el esquema común).
EXTRA_COLUMNS: list[str] = ["occupation_id", "is_projection"]

NORMALIZED_COLUMNS: list[str] = COMMON_COLUMNS + EXTRA_COLUMNS

# Flags de cuarentena (LOAD-012).
QUARANTINE_UNMAPPED_CATALOG = "UNMAPPED_CATALOG"
QUARANTINE_OUTLIER_RANGE = "OUTLIER_RANGE"

# Indicadores que no admiten valores negativos. El golden dataset regional
# incluye variaciones negativas legítimas del PIB, por eso el corte no puede
# ser un "valor < 0" genérico (ver Data_Contracts.md, Desviaciones).
NON_NEGATIVE_INDICATORS: frozenset[str] = frozenset(
    catalogs.slug(nombre)
    for nombre in (
        "Tasa de Desocupación Total",
        "Tasa de Ocupación",
        "Tasa de Finalización de Educación Secundaria",
        "Gasto Público en Educación (% del PIB)",
        "Población Total",
        "Índice de Salario Real",
    )
)

_TRUE_VALUES = {"true", "1", "yes", "si", "sí", "x"}
_FALSE_VALUES = {"false", "0", "no", ""}


@dataclass(frozen=True)
class MappedRow:
    """Resultado del mapeo de una fila: dato normalizado o causa de cuarentena."""

    position: int
    data: dict[str, Any]
    flag: str | None = None
    cause: str | None = None
    warnings: tuple[str, ...] = ()

    @property
    def quarantined(self) -> bool:
        return self.flag is not None


def extracted_timestamp() -> str:
    """Marca de extracción en UTC (ISO-8601), usada como `fecha_extraccion`."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_bool(value: Any, default: bool = False) -> bool:
    """Interpreta un booleano de carga manual (`true/false`, `1/0`, `sí/no`)."""
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    clave = catalogs.slug(value).lower()
    if clave in _TRUE_VALUES:
        return True
    if clave in _FALSE_VALUES:
        return False
    return default


def map_manual_row(
    row: Mapping[str, Any],
    position: int,
    extracted_at: str,
) -> MappedRow:
    """Mapea una fila del contrato de carga manual (8 campos) al esquema común.

    Devuelve la fila normalizada o, si no puede mapearse con fidelidad, el
    flag y la causa de cuarentena.
    """
    occupation_id = str(row.get("occupation_id") or "").strip().upper()
    sector_nombre = catalogs.resolve_sector(row.get("sector_id"))
    ficha = catalogs.resolve_occupation(occupation_id) if occupation_id else None
    indicador = catalogs.homologate_indicator(row.get("metric_name"))
    valor = round(float(row["metric_value"]), 2)
    unidad = catalogs.resolve_unit(row.get("data_type")) or ""
    country_code = str(row.get("country_code") or "").strip().upper()
    pais_nombre = catalogs.resolve_country(country_code) or country_code
    periodo_info = catalogs.parse_period(row.get("period")) or (0, "")

    data: dict[str, Any] = {
        "pais_codigo_iso3": country_code,
        "pais_nombre": pais_nombre,
        "dimension": sector_nombre or str(row.get("sector_id") or "").strip(),
        "indicador_nombre": indicador,
        "anio": periodo_info[0],
        "periodo": periodo_info[1],
        "valor": valor,
        "unidad_medida": unidad,
        "fuente_oficial": str(row.get("source_name") or "").strip(),
        "fecha_extraccion": extracted_at,
        "occupation_id": occupation_id,
        "is_projection": parse_bool(row.get("is_projection")),
    }

    # --- Nivel 2: cuarentena por catálogo (UNMAPPED_CATALOG) ----------------
    if sector_nombre is None:
        return MappedRow(
            position=position,
            data=data,
            flag=QUARANTINE_UNMAPPED_CATALOG,
            cause=(
                f"sector_id '{row.get('sector_id')!r} no existe en el catálogo de sectores "
                f"({', '.join(catalogs.SECTORES)})"
            ),
        )

    if occupation_id and ficha is None:
        return MappedRow(
            position=position,
            data=data,
            flag=QUARANTINE_UNMAPPED_CATALOG,
            cause=(
                f"occupation_id '{occupation_id}' no existe en el catálogo de ocupaciones "
                f"({catalogs.OCUPACION_IDS[0]}..{catalogs.OCUPACION_IDS[-1]})"
            ),
        )

    if ficha and ficha["sector"] != sector_nombre:
        return MappedRow(
            position=position,
            data=data,
            warnings=(
                f"sector_id '{row.get('sector_id')!r}' no coincide con el sector del catálogo "
                f"para {occupation_id} ('{ficha['sector']}'); se conserva el sector informado",
            ),
        )

    # --- Nivel 2: cuarentena por rango (OUTLIER_RANGE) ----------------------
    if valor > 100 and catalogs.slug(row.get("data_type")).lower() == "percentage":
        return MappedRow(
            position=position,
            data=data,
            flag=QUARANTINE_OUTLIER_RANGE,
            cause=f"valor {valor} fuera del rango lógico de un porcentaje (0..100)",
        )

    if valor < 0 and catalogs.slug(indicador) in NON_NEGATIVE_INDICATORS:
        return MappedRow(
            position=position,
            data=data,
            flag=QUARANTINE_OUTLIER_RANGE,
            cause=f"valor {valor} negativo para un indicador que no lo admite ('{indicador}')",
        )

    return MappedRow(position=position, data=data)


def map_common_row(
    row: Mapping[str, Any],
    position: int,
    extracted_at: str,
) -> MappedRow:
    """Normaliza una fila que ya viene en el esquema común del equipo Data.

    Permite reingerir el golden dataset regional (`dataset_consolidado_regional.csv`)
    sin perder trazabilidad ni aplicar la homologación de indicadores.
    """
    country_code = str(row.get("pais_codigo_iso3") or "").strip().upper()
    indicador = catalogs.homologate_indicator(row.get("indicador_nombre"))
    occupation_id = str(row.get("occupation_id") or row.get("ocupacion_id") or "").strip().upper()

    data: dict[str, Any] = {
        "pais_codigo_iso3": country_code,
        "pais_nombre": catalogs.resolve_country(country_code)
        or str(row.get("pais_nombre") or "").strip(),
        "dimension": str(row.get("dimension") or "").strip(),
        "indicador_nombre": indicador,
        "anio": int(row.get("anio") or 0),
        "periodo": str(row.get("periodo") or "").strip(),
        "valor": round(float(row.get("valor") or 0.0), 2),
        "unidad_medida": str(row.get("unidad_medida") or "").strip(),
        "fuente_oficial": str(row.get("fuente_oficial") or "").strip(),
        "fecha_extraccion": str(row.get("fecha_extraccion") or "").strip() or extracted_at,
        "occupation_id": occupation_id,
        "is_projection": parse_bool(row.get("is_projection")),
    }

    if data["anio"] <= 0:
        return MappedRow(
            position=position,
            data=data,
            flag=QUARANTINE_UNMAPPED_CATALOG,
            cause="'anio' ausente o inválido en el esquema común",
        )

    return MappedRow(position=position, data=data)


__all__ = [
    "COMMON_COLUMNS",
    "EXTRA_COLUMNS",
    "NORMALIZED_COLUMNS",
    "NON_NEGATIVE_INDICATORS",
    "QUARANTINE_OUTLIER_RANGE",
    "QUARANTINE_UNMAPPED_CATALOG",
    "MappedRow",
    "extracted_timestamp",
    "map_common_row",
    "map_manual_row",
    "parse_bool",
]
