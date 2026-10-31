"""실패 집계 — 한 번은 일화, 세 번은 패턴.

    python harness/report.py [--project DIR] [--json] [다른 프로젝트 폴더 ...]

같은 (노드, 원인 분류, 증상) 실패를 서로 다른 Run 수로 센다.
  1 Run            [일화]   기록만 한다
  같은 Run 2번 ·
  2 Run            [후보]   지켜본다 — 고칠 법이 정해지면 처방 가지
  3 Run 이상       [패턴]   처방 가지 후보 → graph-plan 변경 모드에서 추가를 검토 (사람 승인)

종료 코드 0 (보고만 한다)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import spec as S  # noqa: E402


def normalize(symptom: str | None) -> str:
    s = re.sub(r"—\s*\S*evidence\S*", "", symptom or "")  # 회차마다 다른 증거 경로
    s = re.sub(r"r\d{2}a\d{2}", "", s)
    return re.sub(r"\s+", " ", s).strip()[:120]


def collect(roots: list[Path]) -> list[dict]:
    rows = []
    for root in roots:
        p = root / "trace" / "events.jsonl"
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            e = json.loads(line)
            if e.get("type") == "node_end" and e.get("status") in ("failed", "failed_retryable"):
                rows.append({"project": root.name, "run": f"{root.name}/{e['run_id']}", "node": e["node"],
                             "cause": e.get("cause"), "symptom": normalize(e.get("symptom")), "seq": e["seq"]})
    return rows


def aggregate(rows: list[dict]) -> list[dict]:
    groups: dict[tuple, dict] = {}
    for r in rows:
        k = (r["node"], r["cause"], r["symptom"])
        g = groups.setdefault(k, {"node": r["node"], "cause": r["cause"], "symptom": r["symptom"], "count": 0, "runs": set()})
        g["count"] += 1
        g["runs"].add(r["run"])
    out = []
    for g in groups.values():
        n_runs = len(g["runs"])
        label = "패턴" if n_runs >= 3 else "후보" if (n_runs >= 2 or g["count"] >= 2) else "일화"
        out.append({**g, "runs": sorted(g["runs"]), "n_runs": n_runs, "label": label})
    return sorted(out, key=lambda g: (-g["n_runs"], -g["count"]))


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("more", nargs="*", help="함께 셀 다른 프로젝트 폴더")
    a = ap.parse_args(argv)
    roots = [S.project_dir(a.project)] + [Path(x).resolve() for x in a.more]
    groups = aggregate(collect(roots))
    if a.json:
        print(json.dumps(groups, ensure_ascii=False, indent=2))
        return 0
    if not groups:
        print("실패 기록이 없습니다.")
        return 0
    print("| 분류 | 노드 | 원인 | 증상 | 횟수 | Run 수 |")
    print("| --- | --- | --- | --- | --- | --- |")
    for g in groups:
        print(f"| [{g['label']}] | {g['node']} | {g['cause']} | {g['symptom']} | {g['count']} | {g['n_runs']} |")
    pats = [g for g in groups if g["label"] == "패턴"]
    cands = [g for g in groups if g["label"] == "후보"]
    print()
    if pats:
        print(f"다음: 패턴 {len(pats)}건 — 처방 가지 후보입니다. graph-plan 변경 모드에서 추가를 검토하고 사람에게 승인받습니다 "
              "(고칠 법이 정해진 것만 처방 가지로 · 아니면 그대로 두고 역질문).")
    elif cands:
        print(f"후보 {len(cands)}건 — 아직 패턴은 아닙니다. TROUBLESHOOTING.md 의 원인 · 조치를 채우고 지켜봅니다.")
    else:
        print("한 번 나온 실패(일화)뿐입니다 — 처방 가지를 만들지 않습니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
