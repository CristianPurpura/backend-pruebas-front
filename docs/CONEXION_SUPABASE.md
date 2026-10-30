# Conexión a Supabase — runbook y anotaciones

> **Registro de la tarea de conexión inicial (29/10/2026)**: qué se hizo, qué se
> descubrió, cómo replicarlo y qué quedó pendiente.
>
> ⚠️ **Este archivo no debe contener credenciales.** La contraseña vive solo en
> cada `.env` local (gitignored) y en el gestor de contraseñas del equipo.

---

## 1. Estado actual

| Componente | Estado |
| :--- | :--- |
| Conexión app → Supabase | ✅ `GET /api/v1/health` → `{"status":"ok","db":"ok"}` |
| Migraciones Alembic (async) | ✅ head = `15e7e704a237` (`raw_data_logs`) |
| Modelos ORM | ✅ `app/models/` → `Base`, `RawDataLog` |
| Suite de tests | ✅ 81 passed / 19 skipped |
| MCP Supabase (HTTPS) | ⏸ `enabled: false` — la cuenta no tiene privilegios sobre el proyecto |
| Commits | `ab60f6c` (deps) · `667d8f2` (db + alembic) |

---

## 2. Cómo conectar (réplica en 3 pasos)

1. Copiar `.env.example` → `.env` y completar:

   ```dotenv
   DATABASE_URL=postgresql+asyncpg://postgres.[PROJECT-REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:5432/postgres?ssl=require
   ```

2. Instalar dependencias y verificar:

   ```bash
   pip install -r requirements.txt
   python -c "import asyncio; from app.core.database import async_check_db; print(asyncio.run(async_check_db()))"
   # → ok
   ```

3. Levantar y comprobar:

   ```bash
   python -m uvicorn app.main:app --reload
   curl http://127.0.0.1:8000/api/v1/health   # → {"status":"ok","db":"ok"}
   ```

### Significado de cada valor del `DATABASE_URL`

| Trozo | Por qué |
| :--- | :--- |
| `postgresql+asyncpg://` | Forma correcta en SQLAlchemy 2.x. **`postgresql+asyncio+asyncpg` NO existe** y truena con `ValueError: too many values to unpack (expected 2)` |
| `postgres.[PROJECT-REF]` | Usuario del **pooler** (lleva el project ref). El usuario del host directo es solo `postgres` |
| `aws-0-[REGION].pooler.supabase.com:5432` | Pooler en **modo Session** |
| `?ssl=require` | Cifra la conexión **sin validar el certificado** (ver §4) |

---

## 3. Pooler: Session (5432) vs Transaction (6543)

* **Usar siempre Session / 5432.**
* Transaction (6543) **no sirve** con `asyncpg` ni con Alembic: rompe los
  *prepared statements* (que SQLAlchemy usa por defecto) y las operaciones de
  sesión (`SET`, transacciones explícitas).
* El modo se cambia en Supabase → *Settings → Database → Connection pooling*.
* Síntoma si se usa Transaction: errores de `prepared statement` / `protocol
  violation` de pgbouncer al ejecutar la app o `alembic upgrade`.

---

## 4. SSL: por qué `?ssl=require` y no `verify-full`

Descubierto por prueba y error:

* El pooler **sí soporta TLS** (responde `S` al `SSLRequest` estándar de Postgres).
* El certificado es legítimo: `CN=*.pooler.supabase.com` emitido por
  **`Supabase Intermediate 2021 CA`** — una **CA privada de Supabase**.
* Su raíz self-signed **no está en los trust stores públicos**, por lo que
  `sslmode=verify-full` (y `ssl=true` con contexto por defecto) falla con:
  `CERTIFICATE_VERIFY_FAILED: self-signed certificate in certificate chain`.
* `?ssl=require` = cifra sin verificar → funciona y es lo equivalente a
  `sslmode=require` de libpq. **No hay interceptación/MITM**: es la
  arquitectura de certs de Supabase.
* Variantes probadas con SQLAlchemy: `?ssl=true` ❌ · `?sslmode=require` ❌
  (asyncpg no acepta `sslmode`) · **`?ssl=require` ✅** · `connect_args={"ssl": ctx}` ✅.

---

## 5. Red: el puerto 5432 estaba bloqueado (el hallazgo más importante)

**Síntoma:** todo andaba de golpe y después `TimeoutError` al conectar,
o `async_check_db → error`.

**Causa:** la red institucional/campus (`10.60.x.x`) **filtra los puertos de
Postgres de salida** (5432 y 6543). Desde el **hotspot móvil** (`10.192.x.x`)
conecta sin problemas.

Evidencia que permitió diagnosticarlo (todos los tests son de solo lectura):

```powershell
# 1. TCP directo al pooler — da False en la red bloqueada
$c = New-Object System.Net.Sockets.TcpClient
$t = $c.ConnectAsync("aws-0-us-east-1.pooler.supabase.com", 5432)
$t.Wait(8000) -and $c.Connected   # ← debe dar True

# 2. Control con 443 (anda siempre) → descarta que sea internet general
# 3. Si 443 anda y 5432/6543 no, en TODAS las regiones → firewall de salida
```

**Regla práctica para el equipo:** si `/health` devuelve `"db": "error"`
(no `"not_configured"`), lo primero es probar el TCP de arriba desde otra red
**antes** de investigar la app.

> ⚠️ La laptop se reconecta sola a la red institucional guardada. Si un
> `alembic` o la app falla con timeout, revisar a qué red está conectada.

---

## 6. Alembic (async) — estructura y comandos

```
alembic.ini                  # sqlalchemy.url lo inyecta migrations/env.py
migrations/
├── env.py                   # lee DATABASE_URL desde app.core.config (mismo .env que la app)
├── script.py.mako
└── versions/
    └── 15e7e704a237_raw_data_logs.py
app/models/
├── base.py                  # class Base(DeclarativeBase)
├── raw_data_log.py          # RawDataLog → tabla raw_data_logs (SPEC §6)
└── __init__.py              # exporta Base y RawDataLog
```

Comandos:

```bash
python -m alembic revision --autogenerate -m "descripcion"
python -m alembic upgrade head
python -m alembic current
python -m alembic history
```

**Anotación clave:** autogenerate **solo detecta los modelos importados**. Todo
modelo nuevo debe exportarse en `app/models/__init__.py`, o la migración sale
vacía sin avisar.

Esquema aplicado de `raw_data_logs` (SPEC §6 + `error` del JSONL de `raw_store`):

| columna | tipo | null |
| :--- | :--- | :--- |
| `id` | integer (PK) | NO |
| `source_id` | varchar(64) + índice | NO |
| `raw_payload` | json | NO |
| `status` | varchar(16) | NO |
| `error` | text | SÍ |
| `created_at` | timestamptz (server_default `now()`) | NO |

---

## 7. Errores que parecen del proyecto y no lo son

| Error | Causa real |
| :--- | :--- |
| `ImportError: greenlet` / fallo de `sqlalchemy.ext.asyncio` | Faltaba el extra → ya resuelto con `sqlalchemy[asyncio]>=2.0.0` |
| `ValueError: too many values to unpack (expected 2)` al crear el engine | URL con `postgresql+asyncio+asyncpg` (drivername inválido) |
| `DLL load failed ... Control de aplicaciones bloqueó este archivo` / `0x11C7` | **Smart App Control** de Windows 11 bloqueando `.pyd` de pandas sin reputación. Ver README §3 (workaround `pandas==2.2.3`) |
| `CERTIFICATE_VERIFY_FAILED: self-signed certificate in certificate chain` | CA privada de Supabase → usar `?ssl=require` (§4) |
| `TimeoutError` al conectar (andaba antes) | Red cambiando de red / puerto 5432 filtrado (§5) |
| `Your account does not have the necessary privileges` (MCP OAuth) | La cuenta local no tiene rol en el proyecto de Supabase |

---

## 8. Pendientes

1. **🔴 Rotar la contraseña de Supabase** (quedó expuesta en el chat y en
   `.env.example` durante la prueba): *Settings → Database → Reset DB password*,
   actualizar cada `.env` y distribuirla **por un canal seguro**.
2. **MCP Supabase**: conseguir rol en el proyecto (o que lo autorice el
   miembro que lo creó) → poner `enabled: true` en
   `~/.config/opencode/opencode.jsonc` + `opencode mcp auth supabase`.
3. **Red institucional**: pedir que habiliten la salida a 5432/6543, o
   desarrollar por hotspot mientras tanto.
4. **Sondeo a `/health`**: algo en local golpea `GET /health` (404) cada pocos
   segundos; la ruta real es `/api/v1/health`. Si alguna herramienta lo
   necesita, agregar un alias en `app/main.py`.
