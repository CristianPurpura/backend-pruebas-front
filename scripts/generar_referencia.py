"""Genera los snapshots de referencia del módulo de Data Science.

Los archivos resultantes (`data/reference/*.json`) son el último recurso del
cliente: si la API de Data no está disponible y no hay caché, el Backend
sigue respondiendo con estos datos.

Se generan desde la API del repo `DataAnalyst` para garantizar que el
formato sea exactamente el que produce Data.

Uso:
    python -m scripts.generar_referencia [--url http://127.0.0.1:8001]
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import httpx

RUTAS = {
    "brechas.json": "/api/v1/ds/brechas-habilidades",
    "comparativa.json": "/api/v1/ds/comparativa-educativo-laboral",
}

COMMIT_ESPERADO = "45abdfc"


def commit_actual() -> str:
    """Commit del repo DataAnalyst clonado (o "desconocido")."""
    try:
        salida = subprocess.run(
            ["git", "-C", "/tmp/opencode/DataAnalyst", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return salida.stdout.strip() or "desconocido"
    except (OSError, subprocess.SubprocessError):
        return "desconocido"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8001", help="Base de la API de Data")
    parser.add_argument("--destino", default="data/reference", help="Carpeta de salida")
    args = parser.parse_args()

    base = args.url.rstrip("/")
    destino = Path(args.destino)
    destino.mkdir(parents=True, exist_ok=True)

    generado = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    commit = commit_actual()

    for nombre, ruta in RUTAS.items():
        respuesta = httpx.get(base + ruta, timeout=60.0)
        respuesta.raise_for_status()
        datos = respuesta.json()
        datos["_actualizado"] = generado
        datos["_fuente"] = f"DataAnalyst@{commit}:{ruta}"
        archivo = destino / nombre
        archivo.write_text(
            json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"escrito {archivo} ({archivo.stat().st_size} bytes)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
