"""메트릭 게이트 — 지표 JSON 을 값으로 판정해 종료 코드로 답한다. 체크리스트 `check` · 노드 `gate.cmd` 어디서나 쓴다.

    python harness/metric.py METRICS.json "e2e.accuracy>=0.95" ["p95_ms<=200" ...] [--baseline BASE.json] [--tol 0.01]
    python harness/metric.py METRICS.json --save-baseline BASE.json --note "왜 기준선을 바꾸는가"

  조건      <점 경로> <op> <숫자>   op: >= <= > < ==   (예: route.accuracy>=0.9 · 경로는 JSON 안으로 점으로 들어간다)
  기준선    --baseline 이 있으면 조건에 쓴 지표마다 기준선보다 tol 넘게 나빠졌는지 본다 (>= > 는 클수록 좋음 · <= < 는 작을수록 좋음)
  기준선 갱신 --save-baseline 은 사람이 결정한 뒤에만 쓴다 — memory/DECISIONS.md 에 이유가 남는다 (게이트를 약하게 만들지 않는다)

종료 코드  0 통과 · 1 미달 · 회귀 · 입력 오류
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

COND = re.compile(r"^\s*([\w.\-]+)\s*(>=|<=|==|>|<)\s*(-?\d+(?:\.\d+)?)\s*$")
OPS = {">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b, ">": lambda a, b: a > b,
       "<": lambda a, b: a < b, "==": lambda a, b: a == b}


def get(d, path: str):
    cur = d
    for k in path.split("."):
        if not isinstance(cur, dict) or k not in cur:
            raise KeyError(path)
        cur = cur[k]
    if isinstance(cur, bool) or not isinstance(cur, (int, float)):
        raise TypeError(f"{path} 는 숫자가 아닙니다 ({cur!r})")
    return cur


def load(p: str) -> dict:
    try:
        d = json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise SystemExit(f"오류: {p} 를 읽지 못했습니다 — {e}")
    return d.get("metrics", d) if isinstance(d, dict) else {}  # 기준선 파일은 {"metrics": ..., "note": ...}


def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description="메트릭 게이트 (0 통과 · 1 실패)")
    ap.add_argument("metrics")
    ap.add_argument("conds", nargs="*")
    ap.add_argument("--baseline")
    ap.add_argument("--tol", type=float, default=0.0)
    ap.add_argument("--save-baseline")
    ap.add_argument("--note")
    ap.add_argument("--decisions", default="memory/DECISIONS.md")
    a = ap.parse_args(argv)
    try:
        m = load(a.metrics)
    except SystemExit as e:
        print(e, file=sys.stderr)
        return 1

    if a.save_baseline:
        if not a.note:
            print("오류: 기준선을 바꾸려면 --note 로 이유를 적는다 (사람이 결정한 뒤에만)", file=sys.stderr)
            return 1
        ts = datetime.now().isoformat(timespec="seconds")
        Path(a.save_baseline).write_text(json.dumps({"metrics": m, "note": a.note, "ts": ts}, ensure_ascii=False, indent=2), encoding="utf-8")
        dp = Path(a.decisions)
        dp.parent.mkdir(parents=True, exist_ok=True)
        with dp.open("a", encoding="utf-8") as f:
            f.write(f"\n- {ts} · 기준선 갱신 `{a.save_baseline}` ← `{a.metrics}` · {a.note}\n")
        print(f"기준선을 저장했습니다: {a.save_baseline} (기록: {dp})")
        return 0

    if not a.conds:
        print("오류: 조건이 없습니다 — 예: \"e2e.accuracy>=0.95\"", file=sys.stderr)
        return 1
    base = load(a.baseline) if a.baseline else None
    ok = True
    for c in a.conds:
        mt = COND.match(c)
        if not mt:
            print(f"ERROR {c}  — 형식: 경로 op 숫자 (op: >= <= > < ==)")
            ok = False
            continue
        path, op, want = mt.group(1), mt.group(2), float(mt.group(3))
        try:
            v = get(m, path)
        except (KeyError, TypeError) as e:
            print(f"ERROR {c}  — 지표를 찾지 못했습니다: {e}")
            ok = False
            continue
        line, good = f"{c}  (지금 {v})", OPS[op](v, want)
        if base is not None and op != "==":
            try:
                b = get(base, path)
                worse = (b - v) if op in (">=", ">") else (v - b)
                line += f" · 기준선 {b}"
                if worse > a.tol + 1e-12:
                    good = False
                    line += f" → 회귀 {worse:+.4g} (허용 {a.tol})"
            except (KeyError, TypeError):
                line += " · 기준선에 없음"
        print(("PASS  " if good else "FAIL  ") + line)
        ok = ok and good
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
