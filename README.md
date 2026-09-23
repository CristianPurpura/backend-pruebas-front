# Observatorio Predictivo - Backend API

Servicio backend desarrollado en FastAPI para el **Observatorio Predictivo de Ocupaciones y Brechas de Habilidades** en el Cono Sur (Argentina, Uruguay y Chile).

Provee la ingesta y validación de datos (APIs externas y carga manual de archivos planos), cálculo de indicadores y exposición de endpoints REST para la plataforma.

---

## 1. Stack Tecnológico

* **Framework:** FastAPI
* **Servidor ASGI:** Uvicorn
* **Modelado y Validación:** Pydantic v2
* **Procesamiento de Datos:** Pandas + OpenPyXL
* **Base de Datos / ORM:** PostgreSQL / SQLAlchemy 2.0 (async)
* **Cliente HTTP:** HTTPX

---

## 2. Instalación y Ejecución Local

### Prerrequisitos
* Python 3.11+
* Git

### Pasos

1. Clonar el repositorio y acceder a la carpeta:
```bash
git clone [https://github.com/InnovaLab-2C-2026-Equipo-6/app-backend.git](https://github.com/InnovaLab-2C-2026-Equipo-6/app-backend.git)
cd app-backend
```

2. Crear y activar el entorno virtual:
```bash
# En Linux / macOS
python3 -m venv venv
source venv/bin/activate

# En Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1
```

3. Instalar dependencias:
```bash
pip install -r requirements.txt
```

4. Configurar variables de entorno:
```bash
cp .env.example .env
```

5. Iniciar el servidor en modo desarrollo:
```bash
python3 -m uvicorn app.main:app --reload
```

* **API Base:** `http://127.0.0.1:8000`
* **Swagger UI (Documentación interactiva):** `http://127.0.0.1:8000/docs`
* **ReDoc:** `http://127.0.0.1:8000/redoc`

---

## 3. Endpoints Disponibles

| Método | Ruta | Tag | Descripción |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/health` | `Health` | Comprobación de estado del servicio (`200 OK`) |
| `GET` | `/api/v1/occupations/{id}` | `Occupations` | Ficha técnica de ocupación según contrato regional |
| `POST` | `/api/v1/datasets/upload` | `Datasets` | Carga y validación estructural de archivos CSV o Excel |

---

## 4. Estructura del Proyecto

```text
app-backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   ├── datasets.py       # Endpoint POST /upload con validación
│   │       │   ├── health.py         # Chequeo de estado
│   │       │   └── occupations.py    # Fichas técnicas de ocupaciones
│   │       └── router.py             # Enrutador central v1
│   ├── core/                         # Configuración y conexión a DB
│   ├── models/                       # Modelos ORM SQLAlchemy
│   ├── schemas/                      # Schemas de validación Pydantic
│   │   ├── dataset.py
│   │   └── occupation.py
│   ├── services/                     # Lógica de negocio y procesamiento
│   │   └── parsers/
│   │       └── dataset_parser.py     # Parser Pandas para CSV / Excel
│   └── main.py                       # Instancia FastAPI y middleware CORS
├── docs/                             # Especificaciones técnicas y contratos
│   ├── DATA_CONTRACTS.md
│   ├── ROADMAP_BACKEND.md
│   ├── SPEC.md
│   └── STRUCTURE.md
├── requirements.txt
├── .gitignore
└── README.md
```

---

## 5. Formato para Carga Manual de Datasets

El endpoint `POST /api/v1/datasets/upload` valida que los archivos `.csv` o `.xlsx` contengan estrictamente las siguientes columnas:

```text
country_code,sector_id,occupation_id,metric_name,metric_value,period,source_name,data_type
```

Si alguna de estas columnas falta, el endpoint responde con código `400 Bad Request` indicando la lista de campos faltantes.

---

## 6. Documentación Adicional

Para más detalles sobre la arquitectura y contratos:
* [Especificación Técnica (`docs/SPEC.md`)](docs/SPEC.md)
* [Contratos de Datos (`docs/DATA_CONTRACTS.md`)](docs/DATA_CONTRACTS.md)
* [Roadmap y Sprints Kanban (`docs/ROADMAP_BACKEND.md`)](docs/ROADMAP_BACKEND.md)