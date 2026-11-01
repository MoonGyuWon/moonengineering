"""그림 생성 — 스펙과 이벤트에서 diagrams/*.md (Mermaid) 를 만든다. 손으로 고치지 않는다.

    python harness/render.py [--project DIR]

  diagrams/graph.md          실행 그래프: 노드 종류별 모양 · 상태별 색 · 간선 = requires
  diagrams/timeline.md       현재 Run 의 노드 시도 gantt · 실패 · 대기 · 사람의 답

GitHub · VS Code("Markdown Preview Mermaid Support" 확장) 미리보기에서 그림으로 보인다.
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run as R  # noqa: E402
import spec as S  # noqa: E402

SHAPE = {"CODE": ('["', '"]'), "AGENT": ('("', '")'), "HUMAN": ('{{"', '"}}')}
COLORS = {
    "pending": "fill:#f4f4f5,stroke:#a1a1aa,color:#3f3f46",
    "ready": "fill:#dbeafe,stroke:#2563eb,stroke-width:3px,color:#1e3a8a",
    "running": "fill:#fef9c3,stroke:#ca8a04,color:#713f12",
    "waiting_human": "fill:#ffedd5,stroke:#ea580c,stroke-width:3px,color:#7c2d12",
    "executed": "fill:#dcfce7,stroke:#16a34a,color:#14532d",
    "failed_retryable": "fill:#fce7f3,stroke:#db2777,color:#831843",
    "failed": "fill:#fee2e2,stroke:#dc2626,stroke-width:3px,color:#7f1d1d",
    "skipped": "fill:#fafafa,stroke:#d4d4d8,stroke-dasharray:4 3,color:#a1a1aa",
    "draft": "fill:#ffffff,stroke:#a1a1aa,stroke-dasharray:4 3,color:#52525b",
}
HEADER = "<!-- harness/render.py 가 만든 파일 — 손으로 고치지 않는다 -->\n"


def mid(nid: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", nid)


def esc(s: str) -> str:
    """Mermaid 라벨용 — 엔티티는 Mermaid 표기(#quot; #lt; #gt;)를 쓴다."""
    return str(s).replace('"', "#quot;").replace("<", "#lt;").replace(">", "#gt;")


def cell(s) -> str:
    """마크다운 표 칸용."""
    return str(s).replace("|", "\\|").replace("\n", " ")


def node_status(spec, st, n) -> str:
    if st is None:
        return "draft"
    if n["id"] in R.ready_nodes(spec, st):
        return "ready"
    return R.node_state(st, n["id"])["status"]


def graph_md(spec, st) -> str:
    fdefs = S.fields(spec)
    stop = spec["graph"].get("stop_when")
    lines = ["flowchart LR", '  IN(["입력"])', '  DONE((("완료")))'] + (['  STOP((("중단")))'] if stop else [])
    for n in spec["nodes"]:
        a, b = SHAPE.get(n.get("type"), ('["', '"]'))
        ns = R.node_state(st, n["id"]) if st else {"runs": 0}
        extra = f"<br/>실행 {ns['runs']} · 시도 {ns['attempts']}" if ns["runs"] else ""
        lines.append(f"  {mid(n['id'])}{a}{esc(n['id'])}<br/>{n.get('type')}{extra}{b}")
        lines.append(f"  class {mid(n['id'])} {node_status(spec, st, n)}")
    merged: dict[tuple, list[str]] = {}
    for e in S.derived_edges(spec):
        src = "IN" if e["source"] == S.INPUT_OWNER else mid(e["source"])
        merged.setdefault((src, mid(e["target"])), []).append(e["label"])
    for key, conds in (("DONE", spec["graph"].get("done_when", [])), ("STOP", stop or [])):
        for c in conds:
            try:
                f = S.parse_cond(c)[0]
            except S.SpecError:
                continue
            for o in S.owners(fdefs.get(f, {})):
                merged.setdefault(("IN" if o == S.INPUT_OWNER else mid(o), key), []).append(c)
    for (src, dst), labels in merged.items():
        lines.append(f'  {src} -->|"{"<br/>".join(esc(x) for x in labels)}"| {dst}')
    lines += [f"  classDef {k} {v}" for k, v in COLORS.items()]
    lines.append("  class IN,DONE" + (",STOP" if stop else "") + " pending")
    legend = ("| 모양 | 종류 |  | 색 | 상태 |\n| --- | --- | --- | --- | --- |\n"
              "| 사각형 | CODE |  | 파랑 굵은 테 | ready (지금 실행 가능 · 같이 있으면 병렬 웨이브) |\n"
              "| 둥근 사각형 | AGENT |  | 초록 | executed |\n"
              "| 육각형 | HUMAN |  | 주황 굵은 테 | waiting_human (역질문 중) |\n"
              "| 화살표 | requires (그 조건이 참이면 준비) |  | 빨강 / 분홍 | failed / failed_retryable |\n"
              "|  |  |  | 회색 점선 테 | 아직 Run 없음 (draft) · skipped |\n")
    return "```mermaid\n" + "\n".join(lines) + "\n```\n\n" + legend


def node_table(spec, st) -> str:
    rows = ["| 노드 | 종류 | 상태 | REQ | 스펙 |", "| --- | --- | --- | --- | --- |"]
    for n in spec["nodes"]:
        src = spec["sources"].get(n["id"], "")
        rows.append(f"| {n['id']} | {n.get('type')} | {node_status(spec, st, n)} | {', '.join(n.get('reqs', []))} | [{src}](../{src}) |")
    return "\n".join(rows) + "\n"


EVENT_TEXT = {
    "wait": ("역질문 대기", lambda e: e.get("reason")),
    "answer": ("사람의 답", lambda e: f"{e.get('action')} — {e.get('note') or ''}"),
    "decision": ("사람의 결정", lambda e: f"{e.get('topic')} → {e.get('choice')} — {e.get('note') or ''}"),
    "reset": ("재실행", lambda e: e.get("note")),
    "budget": ("예산 추가", lambda e: e.get("note")),
    "run_end": ("Run 종료", lambda e: e.get("result")),
}


def timeline_md(spec, st, evs, rid) -> str:
    if not st:
        return "아직 Run 이 없습니다 — `python harness/run.py start`\n"
    mine = [e for e in evs if e.get("run_id") == rid]
    starts: dict[str, dict] = {}
    g = ["gantt", f"  title {rid}", "  dateFormat YYYY-MM-DDTHH:mm:ss", "  axisFormat %H:%M:%S"]
    rows = ["| seq | 시각 | 사건 | 노드 | 내용 |", "| --- | --- | --- | --- | --- |"]
    for e in mine:
        t = e["type"]
        if t == "node_start":
            starts[e["node"]] = e
        elif t in ("node_end", "wait") and e.get("node") in starts and e.get("status") != "skipped":
            s = starts.pop(e["node"]) if t == "node_end" else starts[e["node"]]
            t0 = datetime.fromisoformat(s["ts"])
            t1 = max(datetime.fromisoformat(e["ts"]), t0 + timedelta(seconds=1))
            status = e.get("status", "waiting_human")
            tag = {"failed": "crit, ", "failed_retryable": "crit, ", "waiting_human": "active, "}.get(status, "done, ")
            g += [f"  section {esc(s['node'])}",
                  f"  {esc(s['node'] + ' · ' + status)} :{tag}{t0.isoformat(timespec='seconds')}, {t1.isoformat(timespec='seconds')}"]
        if t == "node_end" and e["status"] in ("failed", "failed_retryable"):
            what, detail = "실패", f"[{e.get('cause')}] {e.get('symptom')}"
        elif t in EVENT_TEXT:
            what, detail = EVENT_TEXT[t][0], EVENT_TEXT[t][1](e)
        else:
            continue
        rows.append(f"| {e['seq']} | {e['ts'][11:]} | {what} | {e.get('node', '-')} | {cell(detail or '')} |")
    s = R.summary(spec, st)
    head = f"**{s['phase']}** · ready: {', '.join(s['ready']) or '-'} · 대기: {', '.join(s['waiting_human']) or '-'} · 시도 {s['attempts_total']}\n\n"
    return (head + "```mermaid\n" + "\n".join(g) + "\n```\n\n## 사건 (실패 · 역질문 · 사람의 답)\n\n" + "\n".join(rows) +
            "\n\n자세히: [DECISIONS](../memory/DECISIONS.md) · [TROUBLESHOOTING](../memory/TROUBLESHOOTING.md) · `trace/events.jsonl` 의 seq\n")


def render(root: Path) -> list[Path]:
    spec = S.load(root)
    if not spec["graph"]:
        raise S.SpecError("specs/GRAPH.md 의 graph 블록이 없습니다 (체크리스트 모드는 그림을 만들지 않습니다)")
    evs = R.Store(root).events()
    rid = R.current_run(evs)
    st = R.fold(evs, rid) if rid else None
    out = root / "diagrams"
    out.mkdir(exist_ok=True)
    stamp = f"> 생성 {datetime.now().isoformat(timespec='seconds')} · " + (f"Run {rid}" if rid else "Run 없음") + "\n\n"
    files = {"graph.md": "# 실행 그래프\n\n" + stamp + graph_md(spec, st) + "\n## 노드\n\n" + node_table(spec, st),
             "timeline.md": "# 타임라인\n\n" + stamp + timeline_md(spec, st, evs, rid)}
    for name, body in files.items():
        (out / name).write_text(HEADER + body, encoding="utf-8")
    return [out / n for n in files]


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project")
    a = ap.parse_args(argv)
    root = S.project_dir(a.project)
    try:
        for p in render(root):
            print("생성:", p.relative_to(root))
    except S.SpecError as e:
        print("ERROR:", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
