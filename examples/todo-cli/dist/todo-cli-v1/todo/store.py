"""todo 저장소 — 계약 specs/contracts/todo.md "todo/store.py" 구현."""
import json
from pathlib import Path


def load(path):
    p = Path(path)
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8"))


def _save(path, items):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def add(path, title):
    items = load(path)
    new_id = max((it["id"] for it in items), default=0) + 1
    item = {"id": new_id, "title": title.strip(), "done": False}
    items.append(item)
    _save(path, items)
    return item


def mark_done(path, id):
    items = load(path)
    for it in items:
        if it["id"] == id:
            it["done"] = True
            _save(path, items)
            return it
    raise KeyError(id)
