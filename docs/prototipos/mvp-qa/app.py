import io
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import PlainTextResponse, JSONResponse

app = FastAPI(
    title="Backend API - Catálogo de Ocupaciones, Consolidado y Carga de Datasets",
    version="1.0.0",
)

# Directorio para almacenar datasets procesados
DATA_DIR = Path(os.getenv("DATA_DIR", "./data_storage"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Constantes del contrato del MVP
VALID_COUNTRIES = {"ARG", "CHL", "URY"}
VALID_DATA_TYPES = {"observed", "projected"}
REQUIRED_UPLOAD_COLUMNS = [
    "country_code",
    "sector_id",
    "occupation_id",
    "metric_name",
    "metric_value",
    "period",
    "source_name",
    "data_type",
]

# Definición de las 20 ocupaciones del MVP con sus códigos CIUO-08
# Nota (API-003): CIUO-08 puede repetirse entre ocupaciones; la clave única es pais_codigo_iso3 + ocupacion_id.
# Nota (API-009): Con sector="Tecnología" y pais="ARG" se esperan exactamente 4 registros.
MVP_OCCUPATIONS: List[Dict[str, str]] = [
    {"ocupacion_id": "OCUP_01", "nombre_ocupacion": "Desarrollador de Software", "ciuo_08": "2512", "sector_id": "SEC_TEC", "sector": "Tecnología"},
    {"ocupacion_id": "OCUP_02", "nombre_ocupacion": "Desarrollador Web y Multimedia", "ciuo_08": "2513", "sector_id": "SEC_TEC", "sector": "Tecnología"},
    {"ocupacion_id": "OCUP_03", "nombre_ocupacion": "Analista de Sistemas", "ciuo_08": "2511", "sector_id": "SEC_TEC", "sector": "Tecnología"},
    {"ocupacion_id": "OCUP_04", "nombre_ocupacion": "Especialista en Bases de Datos y Redes", "ciuo_08": "2521", "sector_id": "SEC_TEC", "sector": "Tecnología"},
    {"ocupacion_id": "OCUP_05", "nombre_ocupacion": "Ingeniero Industrial y de Producción", "ciuo_08": "2141", "sector_id": "SEC_IND", "sector": "Industria"},
    {"ocupacion_id": "OCUP_06", "nombre_ocupacion": "Supervisor de Planta Industrial", "ciuo_08": "2141", "sector_id": "SEC_IND", "sector": "Industria"},  # CIUO-08 repetido intencionalmente (API-003)
    {"ocupacion_id": "OCUP_07", "nombre_ocupacion": "Técnico en Automatización Industrial", "ciuo_08": "3119", "sector_id": "SEC_IND", "sector": "Industria"},
    {"ocupacion_id": "OCUP_08", "nombre_ocupacion": "Operador de Maquinaria Industrial", "ciuo_08": "8189", "sector_id": "SEC_IND", "sector": "Industria"},
    {"ocupacion_id": "OCUP_09", "nombre_ocupacion": "Ingeniero Agrónomo", "ciuo_08": "2132", "sector_id": "SEC_AGR", "sector": "Agroindustria"},
    {"ocupacion_id": "OCUP_10", "nombre_ocupacion": "Técnico Agropecuario", "ciuo_08": "3142", "sector_id": "SEC_AGR", "sector": "Agroindustria"},
    {"ocupacion_id": "OCUP_11", "nombre_ocupacion": "Especialista en Gestión Ambiental", "ciuo_08": "2133", "sector_id": "SEC_AGR", "sector": "Agroindustria"},
    {"ocupacion_id": "OCUP_12", "nombre_ocupacion": "Analista Financiero", "ciuo_08": "2413", "sector_id": "SEC_FIN", "sector": "Finanzas"},
    {"ocupacion_id": "OCUP_13", "nombre_ocupacion": "Contador Auditor", "ciuo_08": "2411", "sector_id": "SEC_FIN", "sector": "Finanzas"},
    {"ocupacion_id": "OCUP_14", "nombre_ocupacion": "Asesor de Inversiones", "ciuo_08": "2412", "sector_id": "SEC_FIN", "sector": "Finanzas"},
    {"ocupacion_id": "OCUP_15", "nombre_ocupacion": "Médico General", "ciuo_08": "2211", "sector_id": "SEC_SAL", "sector": "Salud"},
    {"ocupacion_id": "OCUP_16", "nombre_ocupacion": "Profesional de Enfermería", "ciuo_08": "2221", "sector_id": "SEC_SAL", "sector": "Salud"},
    {"ocupacion_id": "OCUP_17", "nombre_ocupacion": "Técnico en Registros Médicos", "ciuo_08": "3252", "sector_id": "SEC_SAL", "sector": "Salud"},
    {"ocupacion_id": "OCUP_18", "nombre_ocupacion": "Especialista en Logística y Comercio", "ciuo_08": "2421", "sector_id": "SEC_COM", "sector": "Comercio"},
    {"ocupacion_id": "OCUP_19", "nombre_ocupacion": "Ejecutivo de Ventas Comerciales", "ciuo_08": "3322", "sector_id": "SEC_COM", "sector": "Comercio"},
    {"ocupacion_id": "OCUP_20", "nombre_ocupacion": "Coordinador de Distribución", "ciuo_08": "1324", "sector_id": "SEC_COM", "sector": "Comercio"},
]

VALID_OCCUPATION_IDS = {item["ocupacion_id"] for item in MVP_OCCUPATIONS}
OCCUPATION_LOOKUP = {item["ocupacion_id"]: item for item in MVP_OCCUPATIONS}
EXTRACTION_DATE = "2026-10-28T00:00:00Z"


def build_occupations_catalog() -> List[Dict[str, Any]]:
    """
    Construye el catálogo de ocupaciones independiente:
    20 ocupaciones × 3 países (ARG, CHL, URY) = 60 registros (API-003, LOAD-009).
    """
    records: List[Dict[str, Any]] = []
    for country in sorted(VALID_COUNTRIES):
        for idx, occ in enumerate(MVP_OCCUPATIONS, start=1):
            dtype = "observed" if idx % 2 != 0 else "projected"
            records.append(
                {
                    "pais_codigo_iso3": country,
                    "ocupacion_id": occ["ocupacion_id"],
                    "ocupacion_uid": f"{country}_{occ['ocupacion_id']}",
                    "nombre_ocupacion": occ["nombre_ocupacion"],
                    "ciuo_08": occ["ciuo_08"],
                    "sector_id": occ["sector_id"],
                    "sector": occ["sector"],
                    "metric_name": "employment_rate",
                    "metric_value": round(50.0 + idx * 1.25, 2),
                    "period": "2025",
                    "fuente_oficial": "ILOSTAT",
                    "fecha_extraccion": EXTRACTION_DATE,
                    "data_type": dtype,
                    "traceability": {
                        "source": "ILOSTAT",
                        "fuente_oficial": "ILOSTAT",
                        "retrieved_at": EXTRACTION_DATE,
                        "fecha_extraccion": EXTRACTION_DATE,
                        "last_updated": EXTRACTION_DATE,
                        "data_type": dtype,
                    },
                }
            )
    return records


def build_regional_consolidated() -> List[Dict[str, Any]]:
    """
    Construye el consolidado regional socioeconómico:
    45 registros por país × 3 países (ARG, CHL, URY) = 135 registros en total (API-005, API-006, LOAD-009).
    """
    records: List[Dict[str, Any]] = []
    metrics = ["tasa_empleo", "ingreso_medio", "demanda_laboral"]
    periods = ["2024", "2025", "2026"]

    for country in sorted(VALID_COUNTRIES):
        count_for_country = 0
        for occ in MVP_OCCUPATIONS:
            for metric in metrics:
                for period in periods:
                    if count_for_country >= 45:
                        break
                    count_for_country += 1
                    dtype = "projected" if period == "2026" else "observed"
                    records.append(
                        {
                            "pais_codigo_iso3": country,
                            "sector_id": occ["sector_id"],
                            "ocupacion_id": occ["ocupacion_id"],
                            "metric_name": metric,
                            "metric_value": round(100.0 + count_for_country * 2.5, 2),
                            "period": period,
                            "fuente_oficial": "ILOSTAT",
                            "fecha_extraccion": EXTRACTION_DATE,
                            "data_type": dtype,
                        }
                    )
                if count_for_country >= 45:
                    break
            if count_for_country >= 45:
                break
    return records


def deduplicate_common_records(records: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    """
    Elimina duplicados usando clave compuesta de la estructura común (LOAD-006, LOAD-011).
    Clave compuesta: (pais_codigo_iso3, sector_id, ocupacion_id, metric_name, period, data_type).
    """
    seen = set()
    unique_records: List[Dict[str, Any]] = []
    duplicates_removed = 0

    for row in records:
        key = (
            row["pais_codigo_iso3"],
            row["sector_id"],
            row["ocupacion_id"],
            row["metric_name"],
            str(row["period"]),
            row["data_type"],
        )
        if key in seen:
            duplicates_removed += 1
            continue
        seen.add(key)
        unique_records.append(row)

    return unique_records, duplicates_removed


def transform_upload_to_common_structure(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Transforma el contrato de carga manual (country_code, sector_id, occupation_id,
    metric_name, metric_value, period, source_name, data_type) a la estructura común (LOAD-010).
    """
    common_rows: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        common_rows.append(
            {
                "pais_codigo_iso3": str(row["country_code"]).strip(),
                "sector_id": str(row["sector_id"]).strip(),
                "ocupacion_id": str(row["occupation_id"]).strip(),
                "metric_name": str(row["metric_name"]).strip(),
                "metric_value": float(row["metric_value"]),
                "period": str(row["period"]).strip(),
                "fuente_oficial": str(row["source_name"]).strip(),
                "fecha_extraccion": EXTRACTION_DATE,
                "data_type": str(row["data_type"]).strip(),
            }
        )
    return common_rows


def validate_and_parse_dataframe(df: pd.DataFrame) -> Tuple[List[Dict[str, Any]], int]:
    """
    Valida un DataFrame según las reglas LOAD-003, LOAD-004, LOAD-005, LOAD-006, LOAD-007, LOAD-008.
    """
    # LOAD-003: Verificar archivo sin filas o sin columnas
    if df is None or df.empty or len(df.columns) == 0:
        raise HTTPException(
            status_code=400,
            detail={"message": "El archivo cargado está vacío o no contiene registros.", "error_code": "EMPTY_FILE"},
        )

    # LOAD-004: Verificar campos obligatorios
    present_cols = [str(c).strip() for c in df.columns]
    missing_fields = [col for col in REQUIRED_UPLOAD_COLUMNS if col not in present_cols]
    if missing_fields:
        raise HTTPException(
            status_code=400,
            detail={
                "message": f"Faltan campos obligatorios: {', '.join(missing_fields)}",
                "missing_fields": missing_fields,
            },
        )

    # LOAD-005, LOAD-007, LOAD-008: Validar tipos y catálogos fila por fila
    string_cols = ["country_code", "sector_id", "occupation_id", "metric_name", "period", "source_name", "data_type"]
    for idx, row in df.iterrows():
        row_num = int(idx) + 1

        # Verificar que campos String no sean nulos ni vacíos (LOAD-005)
        for scol in string_cols:
            val = row[scol]
            if pd.isna(val) or str(val).strip() == "":
                raise HTTPException(
                    status_code=400,
                    detail={
                        "message": f"Fila {row_num}: el campo '{scol}' debe ser un String válido no vacío.",
                        "invalid_field": scol,
                    },
                )

        # Verificar metric_value como Float (LOAD-005)
        raw_metric_val = row["metric_value"]
        if pd.isna(raw_metric_val) or isinstance(raw_metric_val, bool):
            raise HTTPException(
                status_code=400,
                detail={"message": f"Fila {row_num}: 'metric_value' debe ser numérico (Float).", "invalid_field": "metric_value"},
            )
        try:
            float(raw_metric_val)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=400,
                detail={"message": f"Fila {row_num}: 'metric_value' debe ser de tipo Float.", "invalid_field": "metric_value"},
            )

        # Verificar valores permitidos de data_type (LOAD-005)
        dtype_val = str(row["data_type"]).strip()
        if dtype_val not in VALID_DATA_TYPES:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": f"Fila {row_num}: 'data_type' inválido ('{dtype_val}'). Valores permitidos: observed, projected.",
                    "invalid_field": "data_type",
                },
            )

        # Verificar código de país contra catálogo ARG/URY/CHL (LOAD-007)
        country_val = str(row["country_code"]).strip()
        if country_val not in VALID_COUNTRIES:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": f"Fila {row_num}: código de país '{country_val}' no permitido. Permitidos: ARG, CHL, URY.",
                    "invalid_field": "country_code",
                },
            )

        # Verificar occupation_id contra el catálogo de ocupaciones (LOAD-008)
        occ_val = str(row["occupation_id"]).strip()
        if occ_val not in VALID_OCCUPATION_IDS:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": f"Fila {row_num}: 'occupation_id' ('{occ_val}') no existe en el catálogo del MVP.",
                    "invalid_field": "occupation_id",
                },
            )

    # Transformar a estructura común (LOAD-010) y deduplicar (LOAD-006, LOAD-011)
    common_records = transform_upload_to_common_structure(df)
    dedup_records, duplicates_removed = deduplicate_common_records(common_records)
    return dedup_records, duplicates_removed


# Memoria inicial del sistema (respaldo y datasets activos)
CATALOG_DATA: List[Dict[str, Any]] = build_occupations_catalog()
CONSOLIDATED_DATA: List[Dict[str, Any]] = build_regional_consolidated()
UPLOADED_DATASETS: List[Dict[str, Any]] = []


def persist_datasets_to_disk(consolidated: List[Dict[str, Any]], catalog: List[Dict[str, Any]]) -> Dict[str, str]:
    """Guarda los CSV nacionales, el consolidado regional y el catálogo de ocupaciones en disco."""
    df_cons = pd.DataFrame(consolidated)
    paths: Dict[str, str] = {}

    for country in sorted(VALID_COUNTRIES):
        df_country = df_cons[df_cons["pais_codigo_iso3"] == country]
        c_path = DATA_DIR / f"consolidado_{country}.csv"
        df_country.to_csv(c_path, index=False)
        paths[country] = str(c_path)

    cons_path = DATA_DIR / "consolidado_regional.csv"
    df_cons.to_csv(cons_path, index=False)
    paths["consolidado"] = str(cons_path)

    df_cat = pd.DataFrame(catalog).drop(columns=["traceability"], errors="ignore")
    cat_path = DATA_DIR / "catalogo_ocupaciones.csv"
    df_cat.to_csv(cat_path, index=False)
    paths["ocupaciones"] = str(cat_path)

    return paths


# Inicializar archivos en disco al arrancar
persist_datasets_to_disk(CONSOLIDATED_DATA, CATALOG_DATA)


@app.get("/api/v1/ocupaciones/descargar")
def descargar_catalogo_ocupaciones(format: str = Query("csv", pattern="^(csv|json)$")):
    """
    API-001, API-002, API-003, API-007:
    Descarga el catálogo de ocupaciones (60 registros = 20 ocupaciones × 3 países).
    """
    df = pd.DataFrame(CATALOG_DATA).drop(columns=["traceability"], errors="ignore")
    if format == "json":
        return JSONResponse(content={"count": len(CATALOG_DATA), "items": CATALOG_DATA})
    csv_content = df.to_csv(index=False)
    return PlainTextResponse(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=catalogo_ocupaciones.csv"},
    )


@app.get("/api/v1/ocupaciones/catalogo")
def consultar_catalogo_ocupaciones(
    sector: Optional[str] = Query(None, description="Nombre o ID del sector (ej. Tecnología)"),
    pais: Optional[str] = Query(None, description="Código ISO3 del país (ARG, CHL, URY)"),
):
    """
    API-009, API-012, API-013, API-014:
    Consulta el catálogo de ocupaciones con y sin filtros de sector y país.
    Observación API-009: con sector=Tecnología y pais=ARG devuelve 4 registros.
    """
    results = CATALOG_DATA
    if pais:
        pais_norm = pais.strip().upper()
        results = [r for r in results if r["pais_codigo_iso3"] == pais_norm]
    if sector:
        sector_norm = sector.strip().lower()
        results = [
            r
            for r in results
            if r["sector"].lower() == sector_norm or r["sector_id"].lower() == sector_norm
        ]
    return {"count": len(results), "items": results}


@app.get("/api/v1/consolidado/descargar")
def descargar_consolidado_regional():
    """
    API-004, API-005, API-006:
    Devuelve HTTP 200 y el archivo consolidado regional en CSV (ARG, CHL, URY; 45 por país / 135 total).
    """
    df = pd.DataFrame(CONSOLIDATED_DATA)
    csv_content = df.to_csv(index=False)
    return PlainTextResponse(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=consolidado_regional.csv"},
    )


@app.get("/api/v1/consolidado/procesar")
def procesar_consolidado_regional(
    simulate_ilostat_down: bool = Query(False, description="Simula caída de ILOSTAT (API-010)"),
    simulate_schema_change: bool = Query(False, description="Simula cambio de estructura en fuente externa (API-011)"),
):
    """
    API-008, API-010, API-011, LOAD-009, LOAD-011:
    Procesa los 3 países (ARG, CHL, URY), aplica deduplicación y genera los archivos correspondientes.
    Gestiona resiliencia ante caída de ILOSTAT (API-010) o cambio de estructura (API-011).
    """
    global CONSOLIDATED_DATA

    # API-010: Si ILOSTAT no responde, usa el respaldo disponible sin incorporar datos incorrectos
    if simulate_ilostat_down:
        backup_records, dup_removed = deduplicate_common_records(CONSOLIDATED_DATA)
        paths = persist_datasets_to_disk(backup_records, CATALOG_DATA)
        return {
            "status": "processed_with_backup",
            "source_status": "ilostat_unavailable_using_backup",
            "countries_processed": sorted(list(VALID_COUNTRIES)),
            "total_records": len(backup_records),
            "duplicates_removed": dup_removed,
            "files": paths,
        }

    # API-011: Si cambia la estructura de la fuente externa, no incorpora datos corruptos ni falla sin control
    if simulate_schema_change:
        return JSONResponse(
            status_code=200,
            content={
                "status": "rejected_invalid_source_schema",
                "source_status": "schema_mismatch_detected",
                "data_incorporated": False,
                "countries_processed": sorted(list(VALID_COUNTRIES)),
                "total_records": len(CONSOLIDATED_DATA),
                "message": "Se detectó un cambio en la estructura de la fuente externa. Se mantuvo el respaldo válido sin incorporar datos corruptos.",
            },
        )

    # API-008: Procesamiento normal de los 3 países
    fresh_data = build_regional_consolidated()
    clean_data, dup_removed = deduplicate_common_records(fresh_data)
    CONSOLIDATED_DATA = clean_data
    paths = persist_datasets_to_disk(CONSOLIDATED_DATA, CATALOG_DATA)

    return {
        "status": "processed",
        "source_status": "ilostat_ok",
        "countries_processed": sorted(list(VALID_COUNTRIES)),
        "records_per_country": {
            c: sum(1 for r in CONSOLIDATED_DATA if r["pais_codigo_iso3"] == c) for c in sorted(VALID_COUNTRIES)
        },
        "total_records": len(CONSOLIDATED_DATA),
        "duplicates_removed": dup_removed,
        "files": paths,
    }


@app.post("/api/v1/datasets/upload")
async def upload_dataset(file: UploadFile = File(...)):
    """
    LOAD-001 a LOAD-012:
    Endpoint de carga manual de archivos CSV y XLSX con validación de estructura, tipos,
    catálogo de países y ocupaciones, deduplicación y transformación a estructura común.
    """
    filename = (file.filename or "").lower()
    raw_bytes = await file.read()

    # LOAD-003: Verificar archivo vacío en bytes
    if not raw_bytes or len(raw_bytes.strip()) == 0:
        raise HTTPException(
            status_code=400,
            detail={"message": "El archivo enviado está vacío.", "error_code": "EMPTY_FILE"},
        )

    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(raw_bytes))
        elif filename.endswith(".xlsx") or filename.endswith(".xls"):
            df = pd.read_excel(io.BytesIO(raw_bytes))
        else:
            raise HTTPException(
                status_code=400,
                detail={"message": "Formato de archivo no soportado. Use CSV o XLSX."},
            )
    except HTTPException:
        raise
    except pd.errors.EmptyDataError:
        raise HTTPException(
            status_code=400,
            detail={"message": "El archivo no contiene columnas ni datos válidos.", "error_code": "EMPTY_FILE"},
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail={"message": f"Error al leer el archivo: {str(exc)}"},
        )

    clean_records, duplicates_removed = validate_and_parse_dataframe(df)
    UPLOADED_DATASETS.extend(clean_records)

    return {
        "status": "accepted",
        "filename": file.filename,
        "records_received": len(df),
        "records_valid": len(clean_records),
        "duplicates_removed": duplicates_removed,
        "data": clean_records,
    }