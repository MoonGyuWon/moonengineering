"""질문 분류 — 수식이면 math, 아는 사실 키워드가 있으면 fact, 아니면 other (물음표가 없으면 확신이 낮다)."""
import json
import re
from pathlib import Path

FACTS = json.loads((Path(__file__).resolve().parents[1] / "data" / "facts.json").read_text(encoding="utf-8"))
MATH = re.compile(r"^[\d\s.+\-*/()]+$")


def run(state):
    q = state["q"].strip()
    if MATH.match(q) and re.search(r"[+\-*/]", q):
        return {"intent": "math", "confidence": 0.95}
    if any(k in q for k in FACTS):
        return {"intent": "fact", "confidence": 0.9}
    return {"intent": "other", "confidence": 0.6 if q.endswith("?") else 0.3}
