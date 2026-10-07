# Estructura del Repositorio `app-backend`

Propuesta de arquitectura modular para el backend con FastAPI:

```text
app-backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   ├── alerts.py        # Endpoints para el sistema de alertas
│   │       │   ├── datasets.py      # Subida manual y validación de archivos
│   │       │   ├── employability.py # Índice de empleabilidad y dimensiones
│   │       │   ├── health.py       # Ping y estado de servicios/DB
│   │       │   └── indicators.py    # Filtros por país, sector y período
│   │       └── router.py            # Enrutador principal de la API v1
│   ├── core/
│   │   ├── config.py                # Variables de entorno y configuraciones
│   │   └── database.py              # Sesiones de SQLAlchemy / Supabase
│   ├── models/                      # Entidades de base de datos (tablas ORM)
│   │   ├── alert.py
│   │   ├── indicator.py
│   │   ├── lookup.py                # País, Sector, Ocupación
│   │   └── source.py
│   ├── schemas/                     # Validación de entrada/salida (Pydantic DTOs)
│   │   ├── alert.py
│   │   ├── dataset.py
│   │   ├── employability.py
│   │   └── indicator.py
│   ├── services/                    # Lógica de negocio y procesamiento pesado
│   │   ├── calculators/             # Algoritmo de Índice y proyecciones
│   │   ├── connectors/              # Clientes HTTPX para APIs externas (AR, UY, CL)
│   │   ├── ingestor.py              # Recepción: fetch → registro crudo
│   │   ├── parsers/                 # Lectura y validación de CSV/Excel con Pandas
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