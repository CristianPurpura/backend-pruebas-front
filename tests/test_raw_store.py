import json
from pathlib import Path

from app.services.storage.raw_store import append_raw, read_raw


def test_append_y_read_roundtrip(tmp_path: Path):
    path = append_raw(
        "datos_argentina",
        {"data": [["2024-01-01", 100.5]]},
        raw_dir=tmp_path,
    )
    assert path.name.endswith(".jsonl")
    assert path.parent == tmp_path / "datos_argentina"
    records = read_raw("datos_argentina", raw_dir=tmp_path)
    assert len(records) == 1
    record = records[0]
    assert record["source_id"] == "datos_argentina"
    assert record["status"] == "ok"
    assert record["error"] is None
    assert record["raw_payload"]["data"] == [["2024-01-01", 100.5]]
    assert record["created_at"]


def test_multiples_appends_acumulan(tmp_path: Path):
    append_raw("fuente", {"n": 1}, raw_dir=tmp_path)
    append_raw("fuente", {"n": 2}, raw_dir=tmp_path)
    records = read_raw("fuente", raw_dir=tmp_path)
    assert [r["raw_payload"]["n"] for r in records] == [1, 2]


def test_append_con_error(tmp_path: Path):
    append_raw("fuente", None, status="error", error="HTTP 500", raw_dir=tmp_path)
    record = read_raw("fuente", raw_dir=tmp_path)[0]
    assert record["status"] == "error"
    assert record["error"] == "HTTP 500"
    assert record["raw_payload"] is None


def test_read_limit_y_fuente_inexistente(tmp_path: Path):
    for n in range(5):
        append_raw("fuente", {"n": n}, raw_dir=tmp_path)
    records = read_raw("fuente", limit=2, raw_dir=tmp_path)
    assert [r["raw_payload"]["n"] for r in records] == [3, 4]
    assert read_raw("inexistente", raw_dir=tmp_path) == []


def test_lineas_son_json_valido(tmp_path: Path):
    path = append_raw("fuente", {"texto": "ñandú"}, raw_dir=tmp_path)
    line = path.read_text(encoding="utf-8").strip()
    parsed = json.loads(line)
    assert parsed["raw_payload"]["texto"] == "ñandú"
