
```markdown
# Contratos de Datos y Schemas (Mocks Oficiales)

Este documento define la estructura de intercambio y normalización entre Frontend, Data y Backend.

## 1. Ocupación Individual y Ficha Técnica
* **Ruta:** `GET /api/v1/occupations/{occupation_id}?country={code}`
* **Payload de respuesta:**

```json
{
  "country": {
    "code": "ARG",
    "name": "Argentina"
  },
  "sector": {
    "id": "TEC",
    "name": "Tecnología"
  },
  "occupation": {
    "id": "OCUP_01",
    "name": "Desarrollador de Software y Aplicaciones",
    "isco_code": "2512"
  },
  "indicators": {
    "demand_level": "Muy Alta",
    "annual_growth": 18.5
  },
  "skills": [
    "Python",
    "FastAPI",
    "React",
    "SQL",
    "Git"
  ],
  "traceability": {
    "source": "INDEC-EPH",
    "source_url": "https://www.indec.gob.ar",
    "last_updated": "2025-Q3",
    "retrieved_at": "2026-09-18",
    "data_type": "observed"
  }
}
```

## 2. Catálogos Base (Normalización)

### Países (`countries`)
* `ARG`: Argentina
* `URY`: Uruguay
* `CHL`: Chile

### Sectores (`sectors`)
* `TEC`: Tecnología
* `SAL`: Salud
* `ENE`: Energía
* `TUR`: Turismo
* `ECO`: Economía del Conocimiento

## 3. Formato para Ingesta Manual (CSV / Excel)
Para el parser de carga manual (`POST /api/v1/datasets/upload`), las columnas obligatorias esperadas en la plantilla son:

| Columna | Tipo | Ejemplo | Descripción |
| :--- | :--- | :--- | :--- |
| `country_code` | String(3) | `ARG` | Código ISO del país |
| `sector_id` | String(10) | `TEC` | ID de sector oficial |
| `occupation_id` | String(20) | `OCUP_01` | Identificador de ocupación |
| `metric_name` | String(50) | `annual_growth` | Nombre normalizado de la métrica |
| `metric_value` | Float | `18.5` | Valor numérico |
| `period` | String(10) | `2025-Q3` | Período de referencia |
| `source_name` | String(100)| `INDEC-EPH` | Organismo oficial |
| `data_type` | String(20) | `observed` | `observed` o `projected` |

```
