"""그림 생성 — 스펙과 이벤트에서 diagrams/*.md (Mermaid) 를 만든다. 손으로 고치지 않는다.

    python harness/render.py [--project DIR]

  diagrams/graph.md          실행 그래프: 노드 종류별 모양 · 상태별 색 · 간선 = requires(실선) / rerun_on(점선)
  diagrams/architecture.md   계층 · 경계(컴포넌트) · 경계를 넘는 필드(계약) — 노드에 layer 가 있을 때
  diagrams/timeline.md       현재 Run 의 노드 시도 gantt · 실패 · 대기 · 사람의 답
  diagrams/index.html        위 셋을 한 장으로 — Mermaid 를 못 그리는 편집기 · 터미널이면 브라우저로 연다

VS Code 에서 보려면 "Markdown Preview Mermaid Support" 확장을 설치하고 미리보기(Ctrl+Shift+V)를 연다.
"""
from __future__ import annotations

import argparse
import html
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run as R  # noqa: E402
import spec as S  # noqa: E402

SHAPE = {"CODE": ('["', '"]'), "AGENT": ('("', '")'), "HUMAN": ('{{"', '"}}'), "JUDGE": ('{"', '"}')}
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


def load_state(root: Path, fdefs: dict):
    store = R.Store(root)
    evs = store.events()
    rid = R.current_run(evs)
    return (R.fold(evs, rid, fdefs) if rid else None), evs, rid


def node_status(spec, st, n) -> str:
    if st is None:
        return "draft" if n.get("impl", "DRAFT") == "DRAFT" else "pending"
    s = R.node_state(st, n["id"])["status"]
    if n["id"] in R.ready_nodes(spec, st):
        return "ready"
    return s


def graph_md(spec, st) -> str:
    fdefs = S.fields(spec)
    lines = ["flowchart LR", '  IN(["입력"])', '  DONE((("완료")))']
    if spec["graph"].get("stop_when"):
        lines.append('  STOP((("중단")))')
    areas = spec["graph"].get("areas") or {}

    def node_line(n, ind):
        a, b = SHAPE.get(n.get("type"), ('["', '"]'))
        extra = ""
        if st:
            ns = R.node_state(st, n["id"])
            if ns["runs"]:
                extra = f"<br/>실행 {ns['runs']} · 시도 {ns['attempts']}"
        lines.append(f"{ind}{mid(n['id'])}{a}{esc(n['id'])}<br/>{n.get('type')} · {n.get('impl', 'DRAFT')}{extra}{b}")

    for name, ad in areas.items():  # 영역 = 병렬로 나뉜 작업 폴더
        lines.append(f'  subgraph AREA_{mid(name)}["영역 {esc(name)} · {esc(ad.get("root", ""))}"]')
        for n in spec["nodes"]:
            if n.get("area") == name:
                node_line(n, "    ")
        lines.append("  end")
    for n in spec["nodes"]:
        if n.get("area") not in areas:
            node_line(n, "  ")
    for n in spec["nodes"]:
        lines.append(f"  class {mid(n['id'])} {node_status(spec, st, n)}")
    merged: dict[tuple, list[str]] = {}
    for e in S.derived_edges(spec):
        src = "IN" if e["source"] == S.INPUT_OWNER else mid(e["source"])
        merged.setdefault((src, mid(e["target"]), e["kind"]), []).append(e["label"])
    for key, conds in (("DONE", spec["graph"].get("done_when", [])), ("STOP", spec["graph"].get("stop_when", []))):
        for c in conds:
            try:
                f = S.parse_cond(c)[0]
            except S.SpecError:
                continue
            for o in S.owners(fdefs.get(f, {})):
                merged.setdefault(("IN" if o == S.INPUT_OWNER else mid(o), key, "requires"), []).append(c)
    for (src, dst, kind), labels in merged.items():
        arrow = "-.->" if kind == "rerun" else "-->"
        lines.append(f'  {src} {arrow}|"{"<br/>".join(esc(x) for x in labels)}"| {dst}')
    for k, v in COLORS.items():
        lines.append(f"  classDef {k} {v}")
    lines.append("  class IN,DONE" + (",STOP" if spec["graph"].get("stop_when") else "") + " pending")
    legend = ("| 모양 | 종류 |  | 색 | 상태 |\n| --- | --- | --- | --- | --- |\n"
              "| 사각형 | CODE |  | 파랑 굵은 테 | ready (지금 실행 가능 · 같이 있으면 병렬 웨이브) |\n"
              "| 둥근 사각형 | AGENT |  | 초록 | executed |\n"
              "| 육각형 | HUMAN |  | 주황 굵은 테 | waiting_human (역질문 중) |\n"
              "| 마름모 | JUDGE (JEV) |  | 빨강 / 분홍 | failed / failed_retryable |\n"
              "| 실선 | requires (그 조건이 참이면 준비) |  | 회색 점선 테 | 아직 Run 없음 (DRAFT) · skipped |\n"
              "| 점선 | rerun_on (그 필드가 바뀌면 다시) |  |  |  |\n")
    return "```mermaid\n" + "\n".join(lines) + "\n```\n\n" + legend


def area_table(spec, st) -> str:
    areas = spec["graph"].get("areas") or {}
    if not areas:
        return ""
    rows = ["| 영역 | 폴더 | 노드 | 끝남 | ready | 진행 · 대기 | 실패 |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for name, ad in list(areas.items()) + [("(영역 없음 · 계약 · 통합)", {"root": "-"})]:
        ns = [n for n in spec["nodes"] if (n.get("area") == name if name in areas else n.get("area") not in areas)]
        stt = [node_status(spec, st, n) for n in ns]
        rows.append(f"| {name} | {ad.get('root')} | {len(ns)} | {stt.count('executed')} | {stt.count('ready')} | "
                    f"{stt.count('running') + stt.count('waiting_human')} | {stt.count('failed') + stt.count('failed_retryable')} |")
    return "\n## 영역별 진행\n\n" + "\n".join(rows) + "\n"


def node_table(spec, st) -> str:
    rows = ["| 노드 | 종류 | 영역 | 계층 | 구현 | 상태 | REQ | 스펙 |", "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for n in spec["nodes"]:
        src = spec["sources"].get(n["id"], "")
        rows.append(f"| {n['id']} | {n.get('type')} | {n.get('area', '-')} | {n.get('layer', '-')} | {n.get('impl', 'DRAFT')} | "
                    f"{node_status(spec, st, n)} | {', '.join(n.get('reqs', []))} | [{src}](../{src}) |")
    return "\n".join(rows) + "\n"


def architecture_md(spec) -> str | None:
    nodes = spec["nodes"]
    if not any(n.get("layer") for n in nodes):
        return None
    order = list(spec["graph"].get("layers") or [])
    order += sorted({n.get("layer", "-") for n in nodes} - set(order))  # 선언 밖 계층도 빠뜨리지 않는다
    layer_of = {n["id"]: n.get("layer", "-") for n in nodes}
    lines = ["flowchart TB"]
    for layer in order:
        lines.append(f'  subgraph L_{mid(layer)}["계층: {esc(layer)}"]')
        members = [n for n in nodes if n.get("layer", "-") == layer]
        bounds = sorted({n.get("boundary") for n in members if n.get("boundary")})
        for bnd in bounds:
            lines.append(f'    subgraph B_{mid(layer)}_{mid(bnd)}["경계: {esc(bnd)}"]')
            for n in members:
                if n.get("boundary") == bnd:
                    lines.append(f'      {mid(n["id"])}["{esc(n["id"])}"]')
            lines.append("    end")
        for n in members:
            if not n.get("boundary"):
                lines.append(f'    {mid(n["id"])}["{esc(n["id"])}"]')
        lines.append("  end")
    cross: dict[tuple, set] = {}
    for e in S.derived_edges(spec):
        if e["source"] == S.INPUT_OWNER or e["kind"] != "requires":
            continue
        f = S.parse_cond(e["label"])[0]
        lines.append(f'  {mid(e["source"])} -->|"{esc(f)}"| {mid(e["target"])}')
        a, b = layer_of.get(e["source"]), layer_of.get(e["target"])
        if a != b:
            cross.setdefault((a, b), set()).add(f)
    table = ["| 보내는 계층 | 받는 계층 | 경계를 넘는 필드 (계약) |", "| --- | --- | --- |"]
    for (a, b), fs in sorted(cross.items()):
        table.append(f"| {a} | {b} | {', '.join(sorted(fs))} |")
    return "```mermaid\n" + "\n".join(lines) + "\n```\n\n## 경계를 넘는 계약\n\n" + "\n".join(table) + "\n"


def timeline_md(spec, st, evs, rid) -> str:
    if not st:
        return "아직 Run 이 없습니다 — `python harness/run.py start`\n"
    mine = [e for e in evs if e.get("run_id") == rid]
    starts: dict[str, dict] = {}
    tasks = []
    for e in mine:
        if e["type"] == "node_start":
            starts[e["node"]] = e
        elif e["type"] in ("node_end", "wait") and e.get("node") in starts:
            s = starts.pop(e["node"]) if e["type"] == "node_end" else starts[e["node"]]
            t0 = datetime.fromisoformat(s["ts"])
            t1 = max(datetime.fromisoformat(e["ts"]), t0 + timedelta(seconds=1))
            status = e.get("status", "waiting_human")
            tag = {"failed": "crit, ", "failed_retryable": "crit, ", "waiting_human": "active, "}.get(status, "done, ")
            if e["type"] == "node_end" and status == "skipped":
                continue
            tasks.append((s["node"], f"{s['node']} · {status}", tag, t0, t1))
    g = ["gantt", f"  title {rid} (graph v{st['graph_version']})", "  dateFormat YYYY-MM-DDTHH:mm:ss", "  axisFormat %H:%M:%S"]
    for nid, label, tag, t0, t1 in tasks:
        g.append(f"  section {esc(nid)}")
        g.append(f"  {esc(label)} :{tag}{t0.isoformat(timespec='seconds')}, {t1.isoformat(timespec='seconds')}")
    rows = ["| seq | 시각 | 사건 | 노드 | 내용 |", "| --- | --- | --- | --- | --- |"]
    for e in mine:
        t = e["type"]
        if t == "node_end" and e["status"] in ("failed", "failed_retryable"):
            what, detail = "실패", f"[{e.get('cause')}] {e.get('symptom')}"
        elif t == "wait":
            what, detail = "역질문 대기", e.get("reason")
        elif t == "answer":
            what, detail = "사람의 답", f"{e.get('action')} — {e.get('note') or ''}"
        elif t == "decision":
            what, detail = "사람의 결정", f"{e.get('topic')} → {e.get('choice')} — {e.get('note') or ''}"
        elif t in ("reset", "budget", "migrate"):
            what, detail = {"reset": "재실행", "budget": "예산 추가", "migrate": "스펙 변경 수용"}[t], e.get("note")
        elif t == "judge":
            what, detail = "JEV 판단", "; ".join(f"{k}: {v}" for k, v in e.get("answers", {}).items())
        elif t == "run_end":
            what, detail = "Run 종료", e.get("result")
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
        raise S.SpecError("specs/GRAPH.md 의 graph 블록이 없습니다 (S 규모 체크리스트 모드는 그림을 만들지 않습니다)")
    st, evs, rid = load_state(root, S.fields(spec))
    out = root / "diagrams"
    out.mkdir(exist_ok=True)
    stamp = f"> 생성 {datetime.now().isoformat(timespec='seconds')} · graph v{spec['graph'].get('graph_version')}" + \
            (f" · Run {rid}" if rid else " · Run 없음") + "\n\n"
    files = {"graph.md": "# 실행 그래프\n\n" + stamp + graph_md(spec, st) + area_table(spec, st) + "\n## 노드\n\n" + node_table(spec, st),
             "timeline.md": "# 타임라인\n\n" + stamp + timeline_md(spec, st, evs, rid)}
    arch = architecture_md(spec)
    if arch:
        files["architecture.md"] = "# 계층 · 경계\n\n" + stamp + arch
    written = []
    for name, body in files.items():
        p = out / name
        p.write_text(HEADER + body, encoding="utf-8")
        written.append(p)
    # Mermaid 를 못 그리는 편집기 · 터미널을 위해 같은 내용을 브라우저용 HTML 한 장으로도 낸다
    order = [n for n in ("graph.md", "architecture.md", "timeline.md") if n in files]
    p = out / "index.html"
    p.write_text(to_html([files[n] for n in order], spec["graph"].get("graph_version"), rid), encoding="utf-8")
    written.append(p)
    return written


MERMAID_JS = "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js"


def _inline(s: str) -> str:
    s = html.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    return re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', s)


def md_to_html(md: str) -> str:
    """이 파일이 만드는 md 만 다룬다 — 제목 · 인용 · 표 · mermaid 블록 · 문단."""
    out, lines, i = [], md.splitlines(), 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("```mermaid"):
            j = lines.index("```", i + 1)
            out.append('<pre class="mermaid">' + html.escape("\n".join(lines[i + 1:j])) + "</pre>")
            i = j + 1
            continue
        if ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in re.split(r"(?<!\\)\|", lines[i].strip())[1:-1]]
                if not all(re.fullmatch(r"-+", c) for c in cells):
                    rows.append(cells)
                i += 1
            head, body = rows[0], rows[1:]
            out.append("<table><thead><tr>" + "".join(f"<th>{_inline(c)}</th>" for c in head) + "</tr></thead><tbody>" +
                       "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>" for r in body) + "</tbody></table>")
            continue
        m = re.match(r"^(#{1,3}) (.*)", ln)
        if m:
            out.append(f"<h{len(m.group(1))}>{_inline(m.group(2))}</h{len(m.group(1))}>")
        elif ln.startswith("> "):
            out.append(f"<p class=note>{_inline(ln[2:])}</p>")
        elif ln.strip() and not ln.startswith("<!--"):
            out.append(f"<p>{_inline(ln)}</p>")
        i += 1
    return "\n".join(out)


def to_html(bodies: list[str], version, rid) -> str:
    sections = "\n<hr>\n".join(f"<section>{md_to_html(b)}</section>" for b in bodies)
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Harness Diagrams</title>
<!-- harness/render.py 가 만든 파일 — 손으로 고치지 않는다 -->
<style>
:root {{ --bg:#ffffff; --fg:#18181b; --muted:#71717a; --line:#e4e4e7; --code:#f4f4f5; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#18181b; --fg:#f4f4f5; --muted:#a1a1aa; --line:#3f3f46; --code:#27272a; }} }}
body {{ background:var(--bg); color:var(--fg); font:15px/1.6 system-ui,sans-serif; margin:0 auto; max-width:1200px; padding:16px; }}
table {{ border-collapse:collapse; display:block; overflow-x:auto; margin:8px 0 16px; }}
th,td {{ border:1px solid var(--line); padding:4px 8px; text-align:left; font-size:13px; }}
code {{ background:var(--code); padding:0 4px; border-radius:4px; }}
.note {{ color:var(--muted); }} hr {{ border:0; border-top:1px solid var(--line); margin:32px 0; }}
pre.mermaid {{ background:#ffffff; border:1px solid var(--line); border-radius:8px; padding:12px; overflow-x:auto; }}
</style></head><body>
<p class=note>graph v{version} · Run {rid or '없음'} · 그림이 비면 인터넷 연결(Mermaid CDN)을 확인 — 아래 표는 그대로 읽을 수 있다</p>
{sections}
<script src="{MERMAID_JS}"></script>
<script>if (window.mermaid) {{ mermaid.initialize({{ startOnLoad: true, securityLevel: "loose" }}); }}</script>
</body></html>
"""


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
