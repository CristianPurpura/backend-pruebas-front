"""Catálogos canónicos del Backend.

Fuente de verdad local para la normalización de la carga manual. Los valores
provenen de los contratos aprobados por el equipo de Data
(`DataAnalyst/DEFINICIONES_CASOS_CARGA_QA.md`), del catálogo de ocupaciones
publicado por ese equipo (`DataAnalyst/README.md`) y del esquema común de su
ETL (`etl/cleaner.py`), de modo que lo que produce el Backend sea compatible
con el golden dataset regional.

Los catálogos son datos puros: no dependen de FastAPI, Pandas ni de la base.
"""

import re
import unicodedata
from typing import Any

# ---------------------------------------------------------------------------
# Países (SPEC §6: countries)
# ---------------------------------------------------------------------------
PAISES_INFO: dict[str, dict[str, str]] = {
    "ARG": {"nombre": "Argentina", "iso3": "ARG"},
    "CHL": {"nombre": "Chile", "iso3": "CHL"},
    "URY": {"nombre": "Uruguay", "iso3": "URY"},
}

# ---------------------------------------------------------------------------
# Sectores (5 sectores productivos del MVP, SPEC §2)
# ---------------------------------------------------------------------------
SECTORES: dict[str, str] = {
    "TEC": "Tecnología",
    "SAL": "Salud",
    "ENE": "Energía",
    "TUR": "Turismo",
    "ECO": "Economía del Conocimiento",
}

# Alias aceptados en la carga manual para cada sector (normalizados con _slug).
SECTOR_ALIASES: dict[str, str] = {
    "TECNOLOGIA": "TEC",
    "TECNOLOGIAS": "TEC",
    "TECH": "TEC",
    "TIC": "TEC",
    "SALUD": "SAL",
    "SANIDAD": "SAL",
    "HEALTH": "SAL",
    "ENERGIA": "ENE",
    "ENERGIAS": "ENE",
    "ENERGY": "ENE",
    "TURISMO": "TUR",
    "TRAVEL": "TUR",
    "ECONOMIA_DEL_CONOCIMIENTO": "ECO",
    "ECONOMIAS_DEL_CONOCIMIENTO": "ECO",
    "KNOWLEDGE_ECONOMY": "ECO",
    "CONOCIMIENTO": "ECO",
}

# ---------------------------------------------------------------------------
# Ocupaciones (20 perfiles del MVP con su CIUO-08, sector, demanda y crecimiento)
# Catálogo publicado por el equipo de Data (DataAnalyst/README.md).
# ---------------------------------------------------------------------------
OCUPACIONES: dict[str, dict[str, str]] = {
    "OCUP_01": {"nombre": "Desarrollador de Software y Aplicaciones", "ciuo08": "2512", "sector": "Tecnología", "demanda": "Muy Alta", "crecimiento": "+18.5% anual", "habilidades": "Python, JavaScript, FastAPI, React, SQL, Git"},
    "OCUP_02": {"nombre": "Ingeniero de Datos y Machine Learning", "ciuo08": "2511", "sector": "Tecnología", "demanda": "Muy Alta", "crecimiento": "+24.0% anual", "habilidades": "Pipelines ETL, MLOps, PyTorch, Pandas, Power BI, SQL"},
    "OCUP_03": {"nombre": "Especialista en Ciberseguridad y Redes", "ciuo08": "2529", "sector": "Tecnología", "demanda": "Alta", "crecimiento": "+15.2% anual", "habilidades": "Seguridad de Infraestructura, ISO 27001, Ethical Hacking, Cloud Security"},
    "OCUP_04": {"nombre": "Arquitecto Cloud y DevOps", "ciuo08": "2522", "sector": "Tecnología", "demanda": "Muy Alta", "crecimiento": "+21.0% anual", "habilidades": "Docker, Kubernetes, AWS/Azure, CI/CD, Terraform"},
    "OCUP_05": {"nombre": "Médico General y Especialista", "ciuo08": "2211", "sector": "Salud", "demanda": "Alta", "crecimiento": "+6.5% anual", "habilidades": "Diagnóstico Clínico, Telemedicina, Gestión de Historias Clínicas Electrónicas"},
    "OCUP_06": {"nombre": "Profesional de Enfermería y Cuidados Críticos", "ciuo08": "2221", "sector": "Salud", "demanda": "Muy Alta", "crecimiento": "+9.8% anual", "habilidades": "Atención de Emergencias, Monitoreo Biomédico, Cuidados de Tercera Edad"},
    "OCUP_07": {"nombre": "Bioquímico y Farmacéutico Clínico", "ciuo08": "2262", "sector": "Salud", "demanda": "Media-Alta", "crecimiento": "+7.2% anual", "habilidades": "Análisis Clínicos, Ensayos Farmacológicos, Biología Molecular"},
    "OCUP_08": {"nombre": "Técnico en Diagnóstico por Imágenes y Bioinformática", "ciuo08": "3211", "sector": "Salud", "demanda": "Alta", "crecimiento": "+11.4% anual", "habilidades": "Operación de Resonancia/Tomografía, Procesamiento Digital de Imágenes Médicas"},
    "OCUP_09": {"nombre": "Ingeniero en Energías Renovables (Eólica / Solar)", "ciuo08": "2149", "sector": "Energía", "demanda": "Muy Alta", "crecimiento": "+16.8% anual", "habilidades": "Diseño de Parques Eólicos/Solares, Simulación Energética, SCADA"},
    "OCUP_10": {"nombre": "Ingeniero de Operaciones de Petróleo, Gas y Minería de Transición", "ciuo08": "2146", "sector": "Energía", "demanda": "Alta", "crecimiento": "+8.9% anual", "habilidades": "Extracción No Convencional, Minería de Litio/Cobre, Gestión Ambiental"},
    "OCUP_11": {"nombre": "Técnico en Redes Eléctricas Inteligentes (Smart Grids)", "ciuo08": "3113", "sector": "Energía", "demanda": "Alta", "crecimiento": "+12.0% anual", "habilidades": "Telemetría, Distribución Eléctrica de Alta/Media Tensión, Automatización"},
    "OCUP_12": {"nombre": "Auditor y Consultor en Eficiencia Energética", "ciuo08": "2149", "sector": "Energía", "demanda": "Media-Alta", "crecimiento": "+14.3% anual", "habilidades": "ISO 50001, Huella de Carbono, Optimización Térmica e Industrial"},
    "OCUP_13": {"nombre": "Administrador de Servicios Hoteleros y Experiencia de Huésped", "ciuo08": "1411", "sector": "Turismo", "demanda": "Media-Alta", "crecimiento": "+7.5% anual", "habilidades": "Revenue Management, PMS Hoteleros, Gestión de Hospitalidad, Inglés/Portugués"},
    "OCUP_14": {"nombre": "Guía Especializado en Ecoturismo y Aventura", "ciuo08": "5113", "sector": "Turismo", "demanda": "Alta", "crecimiento": "+13.1% anual", "habilidades": "Primeros Auxilios en Áreas Remotas, Interpretación Patrimonial, Idiomas"},
    "OCUP_15": {"nombre": "Coordinador de Operaciones Turísticas Digitales (TravelTech)", "ciuo08": "3339", "sector": "Turismo", "demanda": "Alta", "crecimiento": "+10.2% anual", "habilidades": "Canales OTA (Booking, Expedia), Marketing Turístico Digital, CRM"},
    "OCUP_16": {"nombre": "Chef Ejecutivo y Gestor Gastronómico Sostenible", "ciuo08": "3434", "sector": "Turismo", "demanda": "Media-Alta", "crecimiento": "+6.8% anual", "habilidades": "Cocina de Autor/Identidad Regional, Costos Gastronómicos, HACCP/BPM"},
    "OCUP_17": {"nombre": "Diseñador UX/UI y Experiencia de Producto Digital", "ciuo08": "2166", "sector": "Economía del Conocimiento", "demanda": "Muy Alta", "crecimiento": "+17.4% anual", "habilidades": "Figma, Design Systems, User Research, Prototipado, Accesibilidad Web"},
    "OCUP_18": {"nombre": "Consultor en Transformación Digital y Analítica de Negocio", "ciuo08": "2421", "sector": "Economía del Conocimiento", "demanda": "Muy Alta", "crecimiento": "+15.9% anual", "habilidades": "Gestión de Procesos (BPMN), Power BI, Scrum, Estrategia de Datos"},
    "OCUP_19": {"nombre": "Científico e Investigador en Biotecnología y AgTech", "ciuo08": "2131", "sector": "Economía del Conocimiento", "demanda": "Alta", "crecimiento": "+13.7% anual", "habilidades": "Genómica Aplicada, Fermentación de Precisión, Bioinformática"},
    "OCUP_20": {"nombre": "Analista Financiero Cuantitativo y FinTech", "ciuo08": "2413", "sector": "Economía del Conocimiento", "demanda": "Muy Alta", "crecimiento": "+19.2% anual", "habilidades": "Modelado Financiero, Python, Pagos Digitales, Cumplimiento Regulatorio / AML"},
}

OCUPACION_IDS: tuple[str, ...] = tuple(OCUPACIONES)

# ---------------------------------------------------------------------------
# Homologación de indicadores (misma tabla que etl/analytics.py del equipo Data)
# ---------------------------------------------------------------------------
INDICADORES_ALIAS: dict[str, str] = {
    "Tasa de Desocupación Total (% Fuerza de Trabajo)": "Tasa de Desocupación Total",
    "Tasa de Desocupación Total": "Tasa de Desocupación Total",
    "Tasa de Ocupación / Empleo": "Tasa de Ocupación",
    "Tasa de Ocupación": "Tasa de Ocupación",
    "Índice de Salario Medio Real (Base 2018=100)": "Índice de Salario Real",
    "Índice de Salario Real": "Índice de Salario Real",
    "Variación Anual del PIB Real": "Variación Anual del PIB Real",
    "Tasa de Finalización de Educación Secundaria": "Tasa de Finalización de Educación Secundaria",
    "Gasto Público en Educación (% del PIB)": "Gasto Público en Educación (% del PIB)",
    "Inflación Anual (IPC acumulado)": "Inflación Anual (IPC acumulado)",
    "Población Total": "Población Total",
}

# ---------------------------------------------------------------------------
# Unidades de medida (data_type del contrato de carga manual)
# ---------------------------------------------------------------------------
# Etiquetas canónicas propias, equivalentes a las que usa el golden dataset
# regional del equipo Data ("Porcentaje (%)", "% del PIB", "Índice (Base 100)").
UNIDADES: dict[str, str] = {
    "percentage": "Porcentaje (%)",
    "currency": "Moneda (USD)",
    "count": "Unidades (conteo)",
}

DATA_TYPES: tuple[str, ...] = tuple(UNIDADES)

# ---------------------------------------------------------------------------
# Períodos
# ---------------------------------------------------------------------------
PERIODO_ANUAL = "Anual"

MESES: dict[int, str] = {
    1: "Enero",
    2: "Febrero",
    3: "Marzo",
    4: "Abril",
    5: "Mayo",
    6: "Junio",
    7: "Julio",
    8: "Agosto",
    9: "Septiembre",
    10: "Octubre",
    11: "Noviembre",
    12: "Diciembre",
}

_RE_ANIO = re.compile(r"^(\d{4})$")
_RE_TRIMESTRE = re.compile(r"^(\d{4})[-_ ]?Q([1-4])$", re.IGNORECASE)
_RE_MES = re.compile(r"^(\d{4})[-_/](0[1-9]|1[0-2])$")

_RE_SLUG = re.compile(r"[^A-Z0-9]+")
_RE_OCUPACION = re.compile(r"^OCUP_\d{2}$")


def slug(value: Any) -> str:
    """Normaliza un texto a mayúsculas sin acentos y con `_` como separador."""
    if value is None:
        return ""
    texto = unicodedata.normalize("NFKD", str(value))
    texto = "".join(caracter for caracter in texto if not unicodedata.combining(caracter))
    return _RE_SLUG.sub("_", texto.upper()).strip("_")


def resolve_country(country_code: Any) -> str | None:
    """Nombre del país a partir del código ISO-3, o None si no está en catálogo."""
    codigo = str(country_code or "").strip().upper()
    pais = PAISES_INFO.get(codigo)
    return pais["nombre"] if pais else None


def resolve_sector(sector_id: Any) -> str | None:
    """Nombre canónico del sector a partir de su código o alias, o None."""
    clave = slug(sector_id)
    if not clave:
        return None
    if clave in SECTORES:
        return SECTORES[clave]
    codigo = SECTOR_ALIASES.get(clave)
    if codigo:
        return SECTORES[codigo]
    return None


def is_occupation_format(occupation_id: Any) -> bool:
    """True si el identificador tiene la forma `OCUP_XX` (aunque no exista)."""
    return bool(_RE_OCUPACION.match(str(occupation_id or "").strip().upper()))


def resolve_occupation(occupation_id: Any) -> dict[str, str] | None:
    """Ficha de la ocupación a partir de su identificador, o None si no existe."""
    clave = str(occupation_id or "").strip().upper()
    return OCUPACIONES.get(clave)


def resolve_unit(data_type: Any) -> str | None:
    """Etiqueta canónica de `unidad_medida` a partir del `data_type` de entrada."""
    clave = slug(data_type).lower()
    return UNIDADES.get(clave)


def homologate_indicator(metric_name: Any) -> str:
    """Homologa el nombre de la métrica contra el catálogo de indicadores."""
    nombre = str(metric_name or "").strip()
    if nombre in INDICADORES_ALIAS:
        return INDICADORES_ALIAS[nombre]
    clave = slug(nombre)
    for original, alias in INDICADORES_ALIAS.items():
        if slug(original) == clave:
            return alias
    return nombre


def parse_period(period: Any) -> tuple[int, str] | None:
    """Convierte el período de entrada en `(anio, periodo)` canónico.

    Formatos aceptados: `2023` (Anual), `2023-Q2` (Trimestre 2) y `2023-06`
    (Junio). Devuelve None si el formato no es válido.
    """
    valor = str(period or "").strip()
    if not valor:
        return None

    match = _RE_ANIO.match(valor)
    if match:
        return int(match.group(1)), PERIODO_ANUAL

    match = _RE_TRIMESTRE.match(valor)
    if match:
        return int(match.group(1)), f"Trimestre {match.group(2)}"

    match = _RE_MES.match(valor)
    if match:
        return int(match.group(1)), MESES[int(match.group(2))]

    return None


__all__ = [
    "DATA_TYPES",
    "INDICADORES_ALIAS",
    "MESES",
    "OCUPACIONES",
    "OCUPACION_IDS",
    "PAISES_INFO",
    "PERIODO_ANUAL",
    "SECTORES",
    "SECTOR_ALIASES",
    "UNIDADES",
    "homologate_indicator",
    "is_occupation_format",
    "parse_period",
    "resolve_country",
    "resolve_occupation",
    "resolve_sector",
    "resolve_unit",
    "slug",
]
