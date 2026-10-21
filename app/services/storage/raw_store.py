import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import get_settings


def _base_dir(raw_dir: str | Path | None) -> Path:
    return Path(raw_dir) if raw_dir is not None else Path(get_settings().raw_dir)


def append_raw(
    source_id: str,
    payload: Any,
    status: str = "ok",
    error: str | None = None,
    raw_dir: str | Path | None = None,
) -> Path:
    """Append de un registro crudo (esquema raw_data_logs) a data/raw/{source}/YYYY-MM-DD.jsonl."""
    directory = _base_dir(raw_dir) / source_id
    directory.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    path = directory / f"{now.strftime('%Y-%m-%d')}.jsonl"
    record = {
        "source_id": source_id,
        "raw_payload": payload,
        "status": status,
        "error": error,
        "created_at": now.isoformat(timespec="seconds"),
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    return path


def read_raw(
    source_id: str,
    limit: int = 100,
    raw_dir: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Lee los últimos `limit` registros crudos de una fuente (orden cronológico)."""
    directory = _base_dir(raw_dir) / source_id
    if not directory.is_dir():
        return []
    records: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records[-limit:]
