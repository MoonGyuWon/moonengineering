import json
from pathlib import Path

FACTS = json.loads((Path(__file__).resolve().parents[1] / "data" / "facts.json").read_text(encoding="utf-8"))


def run(state):
    key = next(k for k in FACTS if k in state["q"])
    return {"result": FACTS[key]}
