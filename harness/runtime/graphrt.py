#!/usr/bin/env python3
"""graphrt — 그래프로 도는 프로그램의 런타임. 파일 하나 · 표준 라이브러리만 · 하네스 없이 혼자 돈다.

하네스가 "구조 = 그래프"로 판단한 프로그램 폴더에 이 파일을 복사해 넣는다 (`graphrt.py init DIR`).

  program/
    graph.json          노드 · 분기 조건 · 완료 조건 (조건식은 하네스와 같다: `field op value` · `field exists`)
    nodes/<id>.py       노드 하나 = 파일 하나 · def run(state) 또는 run(state, ctx) -> {쓸 필드: 값}
    golden/<id>.jsonl   노드 골든셋  {"input": {...}, "expect": {...}}
    golden/e2e.jsonl    전체 골든셋  {"input": {...}, "expect": {...}, "answers": {"<HUMAN 노드>": {...}}}
    llm.py              (선택) def complete(prompt, **kw) -> str — LLM 노드의 ctx.llm 이 부른다
    mocks/llm.json      (선택) [{"match": "<프롬프트에 든 글자>", "reply": "..."}] — llm.py 가 없거나 GRAPHRT_LLM=mock
    runs/<run>.jsonl    실행 기록. 이벤트가 정본이고 상태는 이벤트를 접은 결과다

  python graphrt.py init DIR                     새 프로그램 뼈대
  python graphrt.py check                        graph.json · 노드 파일 검사
  python graphrt.py run [--input JSON|@파일]      한 번 실행 → 출력 필드 JSON
  python graphrt.py resume RUN NODE --set f=v    사람 대기 노드에 답하고 이어서
  python graphrt.py eval [NODE ...] [--out metrics.json] [--repeat N]   골든셋 (인자 없으면 전부 + e2e)
  python graphrt.py serve [--port 8765]          실시간 로그 화면

종료 코드  0 성공 · 1 실패(스펙 오류 · 노드 실패 · 막힘 · 골든셋 불일치) · 2 사람 대기
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
import inspect
import json
import os
import shutil
import sys
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path

__version__ = "0.1"
TYPES = ("CODE", "LLM", "HUMAN")
BINARY_OPS = ("==", "!=", ">=", "<=", ">", "<", " in ")
UNARY_OPS = ("exists", "missing")
LOCK = threading.Lock()


class GraphError(Exception):
    pass


# ── 조건식 (하네스 harness/spec.py 와 같은 문법 · selftest 가 둘이 같은지 본다) ─────────────

def parse_cond(cond: str):
    s = cond.strip()
    for u in UNARY_OPS:
        if s.endswith(" " + u):
            return s[: -len(u) - 1].strip(), u, None
    for op in BINARY_OPS:
        if op in s:
            left, right = s.split(op, 1)
            op = op.strip()
            raw = right.strip()
            if op == "in":
                try:
                    lit = json.loads(raw)
                except json.JSONDecodeError:
                    lit = [x.strip() for x in raw.strip("[]").split(",") if x.strip()]
                if not isinstance(lit, list):
                    raise GraphError(f"in 뒤에는 목록이 와야 합니다: {raw}")
            else:
                try:
                    lit = json.loads(raw)
                except json.JSONDecodeError:
                    lit = raw  # 따옴표 없는 글자 (enum 값)
            return left.strip(), op, lit
    raise GraphError(f"조건식을 읽지 못했습니다: '{cond}' (형식: field op value · field exists)")


def eval_cond(cond: str, values: dict) -> bool:
    field, op, lit = parse_cond(cond)
    if op == "exists":
        return field in values
    if op == "missing":
        return field not in values
    if field not in values:
        return False
    v = values[field]
    try:
        return {"==": lambda: v == lit, "!=": lambda: v != lit, "in": lambda: v in lit, ">=": lambda: v >= lit,
                "<=": lambda: v <= lit, ">": lambda: v > lit, "<": lambda: v < lit}[op]()
    except TypeError:
        return False


# ── 그래프 ─────────────────────────────────────────────────────────────

def load_graph(root: Path) -> dict:
    p = root / "graph.json"
    if not p.exists():
        raise GraphError(f"{p} 가 없습니다")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise GraphError(f"graph.json 이 깨졌습니다 — {e}") from e


def reads(n: dict) -> list[str]:
    return [parse_cond(c)[0] for c in n.get("requires", [])]


def writers(g: dict) -> dict:
    out: dict[str, list[str]] = {f: ["input"] for f in g.get("inputs", [])}
    for n in g.get("nodes", []):
        for f in n.get("writes", []):
            out.setdefault(f, []).append(n["id"])
    return out


def deps(g: dict) -> dict:
    """노드 → 그 노드가 읽는 필드를 쓰는 노드들 (간선은 손으로 적지 않는다)."""
    w = writers(g)
    return {n["id"]: sorted({o for f in reads(n) for o in w.get(f, []) if o not in ("input", n["id"])})
            for n in g.get("nodes", [])}


def check(root: Path, g: dict) -> list[str]:
    errs, ids = [], [n.get("id") for n in g.get("nodes", [])]
    if not ids:
        errs.append("nodes 가 비어 있습니다")
    if len(ids) != len(set(ids)):
        errs.append(f"노드 id 가 겹칩니다: {sorted({i for i in ids if ids.count(i) > 1})}")
    w = writers(g)
    for n in g.get("nodes", []):
        nid, t = n.get("id"), n.get("type")
        if t not in TYPES:
            errs.append(f"{nid}: type 은 {TYPES} 중 하나 (지금 {t!r})")
        if not n.get("writes"):
            errs.append(f"{nid}: writes 가 비어 있습니다 — 노드는 쓰는 필드로 다음 노드를 연다")
        for f in n.get("writes", []):
            if f in g.get("inputs", []):
                errs.append(f"{nid}: 입력 필드 {f} 를 쓰지 않습니다")
        if t in ("CODE", "LLM") and not (root / "nodes" / f"{nid}.py").exists():
            errs.append(f"{nid}: nodes/{nid}.py 가 없습니다")
        for c in n.get("requires", []):
            try:
                f = parse_cond(c)[0]
            except GraphError as e:
                errs.append(f"{nid}: {e}")
                continue
            if f not in w:
                errs.append(f"{nid}: requires 의 {f} 를 쓰는 노드 · 입력이 없습니다")
    for c in g.get("done_when", []):
        try:
            if parse_cond(c)[0] not in w:
                errs.append(f"done_when 의 {parse_cond(c)[0]} 를 쓰는 노드 · 입력이 없습니다")
        except GraphError as e:
            errs.append(f"done_when: {e}")
    left = deps(g)  # 노드는 Run 마다 한 번만 돈다 — 순환이면 영원히 ready 가 안 된다
    while left:
        free = [x for x, ds in left.items() if not set(ds) & set(left)]
        if not free:
            errs.append(f"순환이 있습니다: {sorted(left)}")
            break
        for x in free:
            del left[x]
    return errs


# ── 기록 (이벤트가 정본) ─────────────────────────────────────────────────

class Store:
    """path 가 None 이면 메모리에만 (eval 이 runs/ 를 더럽히지 않게)."""

    def __init__(self, path: Path | None):
        self.path, self.mem = path, []

    def events(self) -> list[dict]:
        if self.path is None:
            return list(self.mem)
        if not self.path.exists():
            return []
        return [json.loads(x) for x in self.path.read_text(encoding="utf-8").splitlines() if x.strip()]

    def emit(self, **ev) -> dict:
        with LOCK:
            evs = self.events()
            ev = {"seq": len(evs) + 1, "ts": datetime.now().isoformat(timespec="milliseconds"), **ev}
            if self.path is None:
                self.mem.append(ev)
            else:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        return ev


def fold(g: dict, events: list[dict]) -> dict:
    st = {"run": None, "status": "new", "values": {}, "nodes": {n["id"]: "pending" for n in g["nodes"]}, "written_by": {}}
    for e in events:
        t = e["type"]
        if t == "run_start":
            st.update(run=e["run"], status="running")
            st["values"].update(e.get("input", {}))
        elif t == "node_start":
            st["nodes"][e["node"]] = "running"
        elif t in ("node_end", "answer"):
            st["nodes"][e["node"]] = "done"
            for f, v in e.get("writes", {}).items():
                st["values"][f] = v
                st["written_by"][f] = e["node"]
        elif t == "node_fail":
            st["nodes"][e["node"]] = "failed"
        elif t == "wait":
            st["nodes"][e["node"]] = "waiting"
            st["status"] = "waiting"
        elif t == "resume":
            st["status"] = "running"
        elif t == "run_end":
            st["status"] = e["status"]
            st["error"] = e.get("error")
            for i, s in st["nodes"].items():  # 끝난 Run 에 남은 사람 대기는 취소로 닫는다
                if s in ("waiting", "running"):
                    st["nodes"][i] = "cancelled"
    if st["status"] in ("running", "waiting"):  # 대기 노드가 하나라도 남아 있으면 대기
        st["status"] = "waiting" if "waiting" in st["nodes"].values() else "running"
    return st


# ── 노드 실행 ───────────────────────────────────────────────────────────

class Ctx:
    def __init__(self, root: Path, store: Store, run: str, node: str):
        self.root, self.store, self.run_id, self.node = root, store, run, node

    def log(self, msg: str):
        self.store.emit(type="log", run=self.run_id, node=self.node, msg=str(msg))

    def llm(self, prompt: str, **kw) -> str:
        self.log(f"llm ← {prompt[:120]}")
        reply = llm_complete(self.root, prompt, **kw)
        self.log(f"llm → {str(reply)[:120]}")
        return reply


def llm_complete(root: Path, prompt: str, **kw) -> str:
    """제공자는 프로그램이 정한다: llm.py 의 complete() · 없거나 GRAPHRT_LLM=mock 이면 mocks/llm.json."""
    if os.environ.get("GRAPHRT_LLM") != "mock" and (root / "llm.py").exists():
        return load_module(root, root / "llm.py", "graphrt_llm").complete(prompt, **kw)
    mp = root / "mocks" / "llm.json"
    if not mp.exists():
        raise GraphError("LLM 제공자가 없습니다 — llm.py 의 complete(prompt) 를 만들거나 mocks/llm.json 을 둔다")
    for m in json.loads(mp.read_text(encoding="utf-8")):
        if m["match"] in prompt:
            return m["reply"]
    raise GraphError(f"mocks/llm.json 에 맞는 항목이 없습니다: {prompt[:80]!r}")


def load_module(root: Path, path: Path, name: str):
    """매번 새로 읽는다 — serve 중에 노드 파일을 고치면 다음 실행부터 바로 반영된다."""
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def own_writes(n: dict, out: dict) -> dict:
    extra = sorted(set(out) - set(n.get("writes", [])))
    if extra:
        raise GraphError(f"{n['id']}: 쓰기로 하지 않은 필드를 썼습니다 {extra} (writes: {n.get('writes')})")
    return out


def call_node(root: Path, n: dict, values: dict, ctx: Ctx) -> dict:
    fn = load_module(root, root / "nodes" / f"{n['id']}.py", f"graphrt_node_{n['id']}").run
    args = (copy.deepcopy(values), ctx) if len(inspect.signature(fn).parameters) >= 2 else (copy.deepcopy(values),)
    out = fn(*args)
    if not isinstance(out, dict):
        raise GraphError(f"{n['id']}: run() 은 dict 를 돌려줘야 합니다 (지금 {type(out).__name__})")
    return own_writes(n, out)


def new_run_id(root: Path | None) -> str:
    base = datetime.now().strftime("%Y%m%d-%H%M%S")
    rid, i = base, 1
    while root is not None and (root / "runs" / f"{rid}.jsonl").exists():
        i += 1
        rid = f"{base}-{i}"
    return rid


def start(root: Path, g: dict, inp: dict, store: Store | None = None, answers: dict | None = None,
          rid: str | None = None) -> tuple[str, Store]:
    rid = rid or new_run_id(None if store else root)
    store = store or Store(root / "runs" / f"{rid}.jsonl")
    missing = [f for f in g.get("inputs", []) if f not in inp]
    store.emit(type="run_start", run=rid, input=inp, graph=g.get("name"), version=g.get("version"))
    if missing:
        store.emit(type="run_end", run=rid, status="failed", error=f"입력 필드가 없습니다: {missing}")
        return rid, store
    advance(root, g, store, answers)
    return rid, store


def advance(root: Path, g: dict, store: Store, answers: dict | None = None) -> dict:
    """ready(대기 중 · requires 가 모두 참)를 웨이브로 돌린다. 끝 · 막힘 · 실패 · 사람 대기에서 멈춘다."""
    nodes = {n["id"]: n for n in g["nodes"]}
    while True:
        st = fold(g, store.events())
        rid, vals = st["run"], st["values"]
        if st["status"] not in ("running", "waiting"):
            return st
        if g.get("done_when") and all(eval_cond(c, vals) for c in g["done_when"]):
            store.emit(type="run_end", run=rid, status="done")
            continue
        ready = [i for i, s in st["nodes"].items() if s == "pending" and all(eval_cond(c, vals) for c in nodes[i].get("requires", []))]
        if not ready:
            if any(s == "waiting" for s in st["nodes"].values()):
                return st
            ok = not g.get("done_when")
            store.emit(type="run_end", run=rid, status="done" if ok else "stuck",
                       **({} if ok else {"error": "실행할 노드가 없는데 done_when 이 거짓입니다"}))
            continue
        for nid in ready:
            n = nodes[nid]
            if n["type"] == "HUMAN":
                if answers and nid in answers:
                    store.emit(type="answer", run=rid, node=nid, writes=answers[nid], by="golden")
                else:
                    store.emit(type="wait", run=rid, node=nid, writes=n.get("writes", []), prompt=n.get("prompt", ""))
                continue
            store.emit(type="node_start", run=rid, node=nid)
            t0, tries = time.time(), int(n.get("retry", 0)) + 1
            for k in range(tries):
                try:
                    out = call_node(root, n, fold(g, store.events())["values"], Ctx(root, store, rid, nid))
                    clash = sorted(f for f in out if f in fold(g, store.events())["written_by"])
                    if clash:
                        raise GraphError(f"{nid}: 다른 노드가 이미 쓴 필드입니다 {clash}")
                    store.emit(type="node_end", run=rid, node=nid, writes=out, ms=int((time.time() - t0) * 1000))
                    break
                except Exception as e:  # noqa: BLE001 — 노드의 어떤 예외도 기록으로 남긴다
                    last = traceback.format_exc().strip().splitlines()[-1]
                    if k + 1 < tries:
                        store.emit(type="log", run=rid, node=nid, msg=f"재시도 {k + 1}/{tries - 1}: {last}")
                        continue
                    store.emit(type="node_fail", run=rid, node=nid, error=str(e) or last, trace=last)
                    store.emit(type="run_end", run=rid, status="failed", error=f"{nid}: {e}")
            if fold(g, store.events())["status"] == "failed":
                break


def resume(root: Path, g: dict, rid: str, nid: str, writes: dict) -> dict:
    store = Store(root / "runs" / f"{rid}.jsonl")
    st = fold(g, store.events())
    if st["nodes"].get(nid) != "waiting":
        raise GraphError(f"{nid} 는 사람 대기가 아닙니다 (지금 {st['nodes'].get(nid)})")
    own_writes(next(x for x in g["nodes"] if x["id"] == nid), writes)
    store.emit(type="answer", run=rid, node=nid, writes=writes, by="human")
    store.emit(type="resume", run=rid)
    return advance(root, g, store)


# ── 골든셋 평가 ─────────────────────────────────────────────────────────

def read_jsonl(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def diff(expect: dict, got: dict) -> dict:
    return {k: {"기대": v, "실제": got.get(k, "<없음>")} for k, v in expect.items() if got.get(k, object()) != v}


def evaluate(root: Path, g: dict, which: list[str], repeat: int | None) -> dict:
    nodes = {n["id"]: n for n in g["nodes"]}
    targets = which or [p.stem for p in sorted((root / "golden").glob("*.jsonl"))]
    report = {}
    for t in targets:
        p = root / "golden" / f"{t}.jsonl"
        if not p.exists():
            raise GraphError(f"golden/{t}.jsonl 이 없습니다")
        if t != "e2e" and (t not in nodes or nodes[t]["type"] == "HUMAN"):
            raise GraphError(f"{t}: CODE · LLM 노드의 골든셋만 평가합니다")
        cases = read_jsonl(p)
        reps = repeat or (int(nodes[t].get("repeat", 1)) if t in nodes else 1)
        passed, total, fails = 0, 0, []
        for i, c in enumerate(cases, 1):
            for _ in range(reps):
                total += 1
                try:
                    if t == "e2e":
                        _, store = start(root, g, c["input"], Store(None), c.get("answers"))
                        st = fold(g, store.events())
                        got = {**st["values"], "status": st["status"]}
                    else:
                        got = call_node(root, nodes[t], c["input"], Ctx(root, Store(None), "eval", t))
                    d = diff(c.get("expect", {}), got)
                except Exception as e:  # noqa: BLE001
                    d = {"오류": str(e)}
                if d:
                    fails.append({"case": i, "input": c["input"], "diff": d})
                else:
                    passed += 1
        report[t] = {"n": len(cases), "repeat": reps, "passed": passed, "total": total,
                     "accuracy": round(passed / total, 4) if total else 0.0, "fails": fails[:5]}
    return report


# ── 실시간 로그 화면 ─────────────────────────────────────────────────────

PAGE = r"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>graphrt</title><style>
:root{--bg:#fafaf9;--fg:#1c1917;--mut:#78716c;--line:#d6d3d1;--card:#fff;--pending:#e7e5e4;--running:#3b82f6;--done:#16a34a;--failed:#dc2626;--waiting:#f59e0b}
@media (prefers-color-scheme:dark){:root{--bg:#1c1917;--fg:#f5f5f4;--mut:#a8a29e;--line:#44403c;--card:#292524;--pending:#44403c}}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 system-ui,sans-serif}
header{display:flex;gap:12px;align-items:center;padding:10px 16px;border-bottom:1px solid var(--line);flex-wrap:wrap}
main{display:grid;grid-template-columns:minmax(0,3fr) minmax(0,2fr);gap:12px;padding:12px 16px}
@media (max-width:800px){main{grid-template-columns:1fr}}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px;overflow:auto}
#log{font:12px/1.6 ui-monospace,monospace;max-height:70vh;white-space:pre-wrap}
textarea,select,input,button{font:inherit;background:var(--card);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px 8px}
button{cursor:pointer}.mut{color:var(--mut)}svg text{fill:var(--fg);font-size:12px}
</style></head><body>
<header><b id="title">graphrt</b><select id="runs"></select><span id="status" class="mut"></span>
<textarea id="inp" rows="1" cols="40">{}</textarea><button id="go">실행</button></header>
<main><div><div class="card"><svg id="g" width="100%"></svg></div><div class="card" id="human" hidden></div></div>
<div class="card"><div id="log"></div></div></main>
<script>
const $=s=>document.querySelector(s);let G,es,st={};
const color=s=>`var(--${s||'pending'})`;
async function boot(){G=await (await fetch('api/graph')).json();$('#title').textContent=G.name||'graphrt';
 $('#inp').value=JSON.stringify(Object.fromEntries((G.inputs||[]).map(k=>[k,''])));draw();await runs();}
function draw(){const L={},lv=id=>L[id]??(L[id]=1+Math.max(0,...G.deps[id].map(lv))),by={};G.nodes.forEach(n=>(by[lv(n.id)]=by[L[n.id]]||[]).push(n));
 const W=150,H=44,gx=60,gy=24,pos={input:[10,10]},cols=Math.max(...Object.keys(by).map(Number))+1;
 Object.entries(by).forEach(([l,ns])=>ns.forEach((n,i)=>pos[n.id]=[10+l*(W+gx),10+i*(H+gy)]));
 const rows=Math.max(...Object.values(by).map(a=>a.length));let s='';
 G.nodes.forEach(n=>(G.deps[n.id].length?G.deps[n.id]:['input']).forEach(d=>{const[a,b]=pos[d],[c,e]=pos[n.id];
  s+=`<path d="M${a+W} ${b+H/2} C${a+W+gx/2} ${b+H/2},${c-gx/2} ${e+H/2},${c} ${e+H/2}" fill="none" stroke="var(--line)" stroke-width="1.5"/>`;}));
 const box=(id,t,stt)=>{const[x,y]=pos[id];return `<g><rect x="${x}" y="${y}" width="${W}" height="${H}" rx="8" fill="var(--card)" stroke="${color(stt)}" stroke-width="${stt&&stt!='pending'?3:1.5}"/>
  <text x="${x+10}" y="${y+18}" font-weight="600">${id}</text><text x="${x+10}" y="${y+34}" class="mut" style="fill:var(--mut)">${t}${stt?' · '+stt:''}</text></g>`};
 s+=box('input','입력','');G.nodes.forEach(n=>s+=box(n.id,n.type,st[n.id]));
 $('#g').setAttribute('height',20+rows*(H+gy));$('#g').setAttribute('viewBox',`0 0 ${20+cols*(W+gx)} ${20+rows*(H+gy)}`);$('#g').innerHTML=s;}
async function runs(sel){const r=await (await fetch('api/runs')).json();
 $('#runs').innerHTML=r.map(x=>`<option value="${x.run}">${x.run} · ${x.status}</option>`).join('');
 if(sel)$('#runs').value=sel;if($('#runs').value)watch($('#runs').value);}
function watch(run){if(es)es.close();st={};$('#log').textContent='';$('#human').hidden=true;draw();
 es=new EventSource('api/events?run='+encodeURIComponent(run));es.onmessage=m=>{const e=JSON.parse(m.data);
  const t={node_start:'running',node_end:'done',answer:'done',node_fail:'failed',wait:'waiting'}[e.type];if(t)st[e.node]=t;
  if(e.type=='run_end'||e.type=='run_start'||e.type=='resume'||e.type=='wait')$('#status').textContent=e.status||(e.type=='wait'?'waiting':'running');
  if(e.type=='wait')ask(run,e);if(e.type=='answer')$('#human').hidden=true;
  const extra=e.writes&&e.type!='wait'?' '+JSON.stringify(e.writes):e.error?' ✖ '+e.error:e.msg?' '+e.msg:e.ms!=null?'':'';
  $('#log').textContent+=`${e.ts.slice(11)}  ${(e.node||'').padEnd(10)} ${e.type}${e.ms!=null?' '+e.ms+'ms':''}${extra}\n`;draw();};}
function ask(run,e){const h=$('#human');h.hidden=false;h.innerHTML=`<b>${e.node}</b> 사람 판단 대기 <span class="mut">${e.prompt||''}</span><br>`+
 e.writes.map(f=>`<label>${f} <input data-f="${f}" placeholder="JSON 값 (예: true · &quot;글자&quot;)"></label> `).join('')+'<button id="ans">답하기</button>';
 $('#ans').onclick=async()=>{const set={};h.querySelectorAll('input').forEach(i=>{try{set[i.dataset.f]=JSON.parse(i.value)}catch{set[i.dataset.f]=i.value}});
  await fetch('api/answer',{method:'POST',body:JSON.stringify({run,node:e.node,set})});};}
$('#go').onclick=async()=>{let inp;try{inp=JSON.parse($('#inp').value)}catch{return alert('입력이 JSON 이 아닙니다')}
 const r=await (await fetch('api/run',{method:'POST',body:JSON.stringify(inp)})).json();setTimeout(()=>runs(r.run),150);};
$('#runs').onchange=()=>watch($('#runs').value);boot();
</script></body></html>"""


def serve(root: Path, port: int):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from urllib.parse import parse_qs, urlparse

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def send(self, code, body, ctype="application/json; charset=utf-8"):
            data = body.encode("utf-8") if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            u = urlparse(self.path)
            g = load_graph(root)
            if u.path == "/":
                return self.send(200, PAGE, "text/html; charset=utf-8")
            if u.path == "/api/graph":
                return self.send(200, json.dumps({**g, "deps": deps(g)}, ensure_ascii=False))
            if u.path == "/api/runs":
                rs = sorted((root / "runs").glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)[:50]
                return self.send(200, json.dumps([{"run": p.stem, "status": fold(g, Store(p).events())["status"]} for p in rs]))
            if u.path == "/api/events":
                run = parse_qs(u.query).get("run", [""])[0]
                p = root / "runs" / f"{Path(run).name}.jsonl"
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                sent = 0
                try:
                    while True:  # 파일 꼬리를 따라간다 — 사람 대기 중이면 답이 올 때까지 계속
                        evs = Store(p).events()
                        for e in evs[sent:]:
                            self.wfile.write(f"data: {json.dumps(e, ensure_ascii=False)}\n\n".encode("utf-8"))
                        if len(evs) > sent:
                            self.wfile.flush()
                            sent = len(evs)
                        time.sleep(0.2)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    return
            self.send(404, '{"error": "없음"}')

        def do_POST(self):
            u = urlparse(self.path)
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)) or 0) or b"{}")
            except (ValueError, UnicodeDecodeError) as e:
                return self.send(400, json.dumps({"error": f"요청 본문이 UTF-8 JSON 이 아닙니다 — {e}"}, ensure_ascii=False))
            g = load_graph(root)
            if u.path == "/api/run":
                rid = new_run_id(root)
                store = Store(root / "runs" / f"{rid}.jsonl")
                threading.Thread(target=start, args=(root, g, body, store, None, rid), daemon=True).start()
                return self.send(200, json.dumps({"run": rid}))
            if u.path == "/api/answer":
                threading.Thread(target=resume, args=(root, g, body["run"], body["node"], body.get("set", {})), daemon=True).start()
                return self.send(200, '{"ok": true}')
            self.send(404, '{"error": "없음"}')

    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    print(f"graphrt {__version__} — http://127.0.0.1:{port}  (Ctrl+C 로 끝)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


# ── 명령 ────────────────────────────────────────────────────────────────

SKELETON = {
    "graph.json": json.dumps({"name": "my-program", "version": 1, "inputs": ["text"], "outputs": ["result"],
                              "nodes": [{"id": "work", "type": "CODE", "requires": ["text exists"], "writes": ["result"]}],
                              "done_when": ["result exists"]}, ensure_ascii=False, indent=2) + "\n",
    "nodes/work.py": 'def run(state):\n    return {"result": state["text"].upper()}\n',
    "golden/work.jsonl": '{"input": {"text": "hi"}, "expect": {"result": "HI"}}\n',
    "golden/e2e.jsonl": '{"input": {"text": "hi"}, "expect": {"result": "HI", "status": "done"}}\n',
    ".gitignore": "runs/\n__pycache__/\n",
}


def parse_input(s: str | None) -> dict:
    if not s:
        return {}
    raw = Path(s[1:]).read_text(encoding="utf-8") if s.startswith("@") else s
    try:
        v = json.loads(raw)
    except json.JSONDecodeError as e:
        raise GraphError(f"입력이 JSON 이 아닙니다 — {e}") from e
    if not isinstance(v, dict):
        raise GraphError("입력은 JSON 객체여야 합니다")
    return v


def parse_sets(items: list[str]) -> dict:
    out = {}
    for it in items or []:
        k, _, v = it.partition("=")
        try:
            out[k] = json.loads(v)
        except json.JSONDecodeError:
            out[k] = v
    return out


def report_run(g, st) -> int:
    out = {"run": st["run"], "status": st["status"],
           "outputs": {k: v for k, v in st["values"].items() if k in (g.get("outputs") or st["values"])}}
    if st.get("error"):
        out["error"] = st["error"]
    print(json.dumps(out, ensure_ascii=False, indent=2))
    if st["status"] == "waiting":
        w = [i for i, s in st["nodes"].items() if s == "waiting"]
        print(f"사람 대기: {w} — python graphrt.py resume {st['run']} {w[0]} --set 필드=값", file=sys.stderr)
        return 2
    return 0 if st["status"] == "done" else 1


def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):  # Windows 콘솔(cp949)에서도 한글이 깨지지 않게
        try:
            s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(prog="graphrt", description="그래프로 도는 프로그램의 런타임")
    ap.add_argument("--dir", default=None, help="프로그램 폴더 (기본: 이 파일이 있는 폴더)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init").add_argument("target")
    sub.add_parser("check")
    p = sub.add_parser("run")
    p.add_argument("--input")
    p = sub.add_parser("resume")
    p.add_argument("run")
    p.add_argument("node")
    p.add_argument("--set", action="append")
    p = sub.add_parser("eval")
    p.add_argument("targets", nargs="*")
    p.add_argument("--out")
    p.add_argument("--repeat", type=int)
    sub.add_parser("serve").add_argument("--port", type=int, default=8765)
    a = ap.parse_args(argv)
    root = Path(a.dir or Path(__file__).resolve().parent).resolve()
    try:
        if a.cmd == "init":
            t = Path(a.target)
            if (t / "graph.json").exists():
                raise GraphError(f"{t}/graph.json 이 이미 있습니다")
            for rel, text in SKELETON.items():
                (t / rel).parent.mkdir(parents=True, exist_ok=True)
                (t / rel).write_text(text, encoding="utf-8")
            shutil.copy2(Path(__file__).resolve(), t / "graphrt.py")
            print(f"만들었습니다: {t} — python {t / 'graphrt.py'} eval")
            return 0
        g = load_graph(root)
        errs = check(root, g)
        if errs:
            print("graph.json 검사 실패:\n  " + "\n  ".join(errs), file=sys.stderr)
            return 1
        if a.cmd == "check":
            print(f"OK — 노드 {len(g['nodes'])}개")
            return 0
        if a.cmd == "run":
            rid, store = start(root, g, parse_input(a.input))
            return report_run(g, fold(g, store.events()))
        if a.cmd == "resume":
            return report_run(g, resume(root, g, a.run, a.node, parse_sets(a.set)))
        if a.cmd == "eval":
            rep = evaluate(root, g, a.targets, a.repeat)
            for t, r in rep.items():
                print(f"{'PASS' if r['passed'] == r['total'] else 'FAIL'} {t:<12} {r['passed']}/{r['total']}  accuracy={r['accuracy']}")
                for f in r["fails"][:3]:
                    print(f"     case {f['case']}: {json.dumps(f['diff'], ensure_ascii=False)}")
            if a.out:
                Path(a.out).write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
            return 0 if all(r["passed"] == r["total"] for r in rep.values()) else 1
        if a.cmd == "serve":
            serve(root, a.port)
            return 0
    except GraphError as e:
        print(f"오류: {e}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    sys.exit(main())
