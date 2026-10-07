# Demo Issues #18 y #19 — Sprint 1 Backend

> **Cuándo:** demo de lo realizado en [Issue #18](https://github.com/InnovaLab-2C-2026-Equipo-6/observatorio-predictivo/issues/18) y [Issue #19](https://github.com/InnovaLab-2C-2026-Equipo-6/observatorio-predictivo/issues/19) · **Rama:** `feature/sprint0-cierre` · **Suite:** 53 tests passing

---

## 1. Resumen (para explicar en 2 minutos)

### Issue #18 — Probar conexión con las APIs seleccionadas ✅

Tres clientes HTTPX **asíncronos** en `app/services/connectors/`, cada uno expone
`await fetch(...) -> ConnectorResponse(source_id, ok, fetched_at, payload, points, error)`:

| `source_id` | Fuente | Serie probada |
|---|---|---|
| `datos_argentina` | Series de Tiempo (`apis.datos.gob.ar`) | IPC nacional (configurable por env `DATOS_AR_SERIES_IDS`) |
| `banco_mundial` | World Bank API v2 | `SL.UEM.TOTL.ZS` (desempleo) para ARG/CHL/URY |
| `simel_chile` | SIMEL/ENE vía SDMX del INE | `CL01,DF_DES_SEXO` (desocupación por sexo, fuente ENE) |

* ⚠️ **Dato interesante para la demo:** `www.simel.gob.cl` devuelve **418** (bloquea bots) →
  usamos el SDMX oficial del INE (`sdmx.ine.gob.cl`), que publica las mismas series ENE.
* **Prueba de conexión:** `tests/test_connectors.py` — tests *en vivo* (una llamada real por
  fuente; sin internet se omiten con *skip*) + tests unitarios de parseo y errores.

### Issue #19 — Flujo de recepción y almacenamiento de datos ✅

La DB quedó diferida, así que usamos la alternativa del propio issue: **guardado de datos crudos**.

* `app/services/storage/raw_store.py` → `append_raw()` escribe registros con el esquema
  `raw_data_logs` (SPEC §6) en **`data/raw/{fuente}/YYYY-MM-DD.jsonl`** (1 JSON por línea con
  `source_id, raw_payload, status, error, created_at`).
* `app/services/ingestor.py` → `await ingest(conector, **params)`: fetch → registro (ok o error)
  → `IngestReport`.
* `read_raw(fuente, limit)` para leer lo acumulado (base para la futura normalización con Data).

---

## 2. Paso a paso de la demo

> Todo se corre desde la raíz del repo (`app-backend/`). **No necesita servidor ni DB.**
> Sí necesita internet (los tests en vivo hacen llamadas reales).

### Paso 0 — Preparar el entorno (30 seg)

```bash
cd ~/Code/Innova-Lab/app-backend
git status --short          # debe estar limpio
rm -rf data/raw             # opcional: empezar de cero (data/raw/ está en .gitignore)
venv/bin/python -m pytest -q
```

✅ Esperado: **53 passed** en ~10 s (incluye los 3 tests en vivo contra las APIs reales).

### Paso 1 — Mostrar los conectores (1 min)

```bash
ls app/services/connectors/
venv/bin/python -m pytest tests/test_connectors.py::TestConexionesEnVivo -v
```

✅ Esperado: `test_datos_argentina_en_vivo` / `test_banco_mundial_en_vivo` /
`test_simel_chile_en_vivo` → **3 passed** (cada uno hace una llamada real, tarda ~5-10 s).

> **Si no hay internet:** los en vivo se marcan `skipped` (no fallan) y los unitarios siguen
> pasando. Decir: *"los tests en vivo se omiten sin red, justamente para no romper CI"*.

### Paso 2 — Ingesta end-to-end: API real → archivo crudo (2 min)

```bash
venv/bin/python - <<'EOF'
import asyncio
from app.services.connectors import DatosArgentinaConnector, BancoMundialConnector, SimelChileConnector
from app.services.ingestor import ingest

async def main():
    for c in (DatosArgentinaConnector(), BancoMundialConnector(), SimelChileConnector()):
        r = await ingest(c)
        print(f"[{'OK ' if r.ok else 'ERR'}] {r.source_id:16} puntos={r.received:3}  {r.stored_path}")

asyncio.run(main())
EOF
```

✅ Esperado (una corrida por fuente, ~5-10 s):

```text
[OK ] datos_argentina   puntos=100  data/raw/datos_argentina/2026-10-07.jsonl
[OK ] banco_mundial     puntos= 30  data/raw/banco_mundial/2026-10-07.jsonl
[OK ] simel_chile       puntos=510  data/raw/simel_chile/2026-10-07.jsonl
```

### Paso 3 — Mostrar el archivo crudo (1 min)

```bash
find data/raw -type f
head -c 400 data/raw/datos_argentina/$(date +%F).jsonl; echo
```

✅ Esperado: un JSON por línea con `source_id`, `raw_payload` (la respuesta cruda completa),
`status: "ok"`, `error: null` y `created_at`. Explicar: *"esquema `raw_data_logs` de la SPEC,
listo para migrar a PostgreSQL cuando tengamos `DATABASE_URL`"*.

### Paso 4 — Mostrar el camino de error (1 min)

```bash
venv/bin/python - <<'EOF'
import asyncio
from app.services.connectors import DatosArgentinaConnector
from app.services.ingestor import ingest
from app.services.storage.raw_store import read_raw

async def main():
    malo = DatosArgentinaConnector(base_url="https://no-existe.example")
    r = await ingest(malo)
    print("ok =", r.ok, "| error =", r.error)
    print("último registro:", read_raw("datos_argentina")[-1])

asyncio.run(main())
EOF
```

✅ Esperado: `ok = False`, error de red, y el registro guardado con
`status: "error"` → *"la falla también queda registrada, que es lo que pide el issue"*.

### Paso 5 — Leer lo acumulado (30 seg)

```bash
venv/bin/python -c "
from app.services.storage.raw_store import read_raw
for fuente in ('datos_argentina', 'banco_mundial', 'simel_chile'):
    print(fuente, '→', len(read_raw(fuente)), 'registros')"
```

✅ Esperado (empezando de limpio): `datos_argentina → 2` (ok + error del paso 4),
`banco_mundial → 1`, `simel_chile → 1`.

### Paso 6 — Cerrar con el estado del trabajo (1 min)

```bash
git log --oneline -3
```

* `eeb4be0` feat: conectores HTTPX (ref #18)
* `698e05f` feat: almacenamiento crudo JSONL + ingesta (ref #19)
* `bd42d78` docs: README §7, ROADMAP y STRUCTURE actualizados
* Ambos issues tienen comentario de cierre en GitHub.

---

## 3. Preguntas típicas y respuestas

| Pregunta | Respuesta |
|---|---|
| ¿Por qué no hay endpoint HTTP? | El issue pedía *probar conexión*; lo formalizamos con tests. Un `/sources/status` se puede agregar cuando Front/QA lo pida. |
| ¿Y la base de datos? | Diferida en Sprint 0 (falta `DATABASE_URL`); el esquema `raw_data_logs` ya está replicado en JSONL, la migración es directa. |
| ¿Por qué INE y no SIMEL directo? | `www.simel.gob.cl` responde 418 a clientes automatizados; el SDMX del INE publica las mismas series ENE de forma oficial. |
| ¿Y si falla la demo por red? | Los tests en vivo hacen *skip*; los unitarios (parseo + errores) siempre corren. La demo del paso 4 necesita fallar justamente por red. |
| ¿Cuál es el próximo paso? | Coordinar con Data la tabla de normalización (`normalized_metrics`) → convertir crudos en métricas. |

---

## 4. Limpieza posterior (opcional)

```bash
rm -rf data/raw   # los crudos de la demo (data/raw/ está en .gitignore, no afecta a git)
```
