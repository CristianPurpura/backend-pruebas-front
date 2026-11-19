# Estructura del Repositorio `app-backend`

Propuesta de arquitectura modular para el backend con FastAPI:

```text
app-backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   ├── alerts.py        # Endpoints para el sistema de alertas
│   │       │   ├── catalog.py       # Catálogos del frontend (países, sectores, ocupaciones)
│   │       │   ├── datasets.py      # Subida manual y validación de archivos
│   │       │   ├── employability.py # Índice de empleabilidad y dimensiones
│   │       │   ├── health.py       # Ping y estado de servicios/DB
│   │       │   ├── indicators.py    # Filtros por país, sector y período
│   │       │   └── occupations.py   # Ficha técnica de una ocupación
│   │       └── router.py            # Enrutador principal de la API v1
│   ├── core/
│   │   ├── config.py                # Variables de entorno y configuraciones
│   │   ├── catalogs.py              # Catálogos canónicos (países, sectores, ocupaciones, unidades)
│   │   ├── validation.py            # Validadores compartidos de filtros (país, ocupación, tipo)
│   │   └── database.py              # Sesiones de SQLAlchemy / Supabase
│   ├── models/                      # Entidades de base de datos (tablas ORM)
│   │   ├── alert.py
│   │   ├── indicator.py
│   │   ├── indicator_result.py      # Snapshot histórico de IDELR/ICOL (#54)
│   │   ├── lookup.py                # País, Sector, Ocupación
│   │   ├── raw_data_log.py          # Registro crudo de ingesta
│   │   └── source.py
│   ├── schemas/                     # Validación de entrada/salida (Pydantic DTOs)
│   │   ├── alert.py
│   │   ├── catalog.py
│   │   ├── dataset.py
│   │   ├── employability.py
│   │   ├── indicator.py
│   │   ├── indicator_result.py      # Snapshot, historial y latest (#54/#65)
│   │   ├── indicator_series.py      # Series chart-ready y tendencias (#64)
│   │   ├── datascience.py           # Brechas y oferta formativa (#74)
│   │   └── occupation.py
│   ├── services/                    # Lógica de negocio y procesamiento pesado
│   │   ├── calculators/             # Algoritmo de Índice, series y proyecciones
│   │   │   └── series.py            # Puntos chart-ready y tendencias (#64)
│   │   ├── connectors/              # Clientes HTTPX para APIs externas (AR, UY, CL)
│   │   ├── datascience/             # Brechas y oferta formativa (#74)
│   │   │   ├── client.py            # Cliente HTTPX a DataAnalyst + cache + fallback
│   │   │   └── mapper.py            # Normalización del payload de Data
│   │   ├── ingestor.py              # Recepción: fetch → registro crudo
│   │   ├── normalization/           # ETL de carga manual: esquema común, cuarentena y dedupe
│   │   │   ├── mapper.py            # Mapeo al ESQUEMA_COLUMNAS de Data
│   │   │   ├── pipeline.py          # Clasificación en 3 niveles
│   │   │   ├── store.py             # Dataset normalizado (CSV) y cuarentena (JSONL)
│   │   │   └── errors.py            # Rechazo por fila (HTTP 422)
│   │   ├── occupation_profile.py    # Perfil de ocupación: catálogo + ICOL
│   │   ├── parsers/                 # Lectura y validación de CSV/Excel con Pandas
│   │   ├── persistence/             # Snapshots históricos de los índices (#54/#65)
│   │   │   ├── results_store.py     # Guardado idempotente y consulta del histórico
│   │   │   └── snapshot_service.py  # Cálculo reutilizable + snapshot post-carga
│   │   ├── scheduler/               # Tareas cron / ejecución periódica
│   │   └── storage/                 # Almacenamiento crudo (JSONL por fuente)
│   └── main.py                      # Punto de entrada de la aplicación FastAPI
├── migrations/                      # Versiones de base de datos con Alembic
├── tests/                           # Tests unitarios y de integración (Pytest)
├── .env.example
├── .gitignore
├── Dockerfile
├── requirements.txt
└── README.md