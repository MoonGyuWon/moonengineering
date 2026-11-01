"""실행기 — 이벤트가 정본이고, 상태는 이벤트를 접은(fold) 결과다. "다음 노드" 포인터는 없다.

    python harness/run.py [--project DIR] <명령>

  start   [--set f=v ...]         새 Run 시작 (입력 필드를 쓴다)
  status  [--json]                지금 상태 · ready 웨이브 · 대기 · 실패 · 예산
  next    [--json]                지금 실행할 수 있는 노드 목록(= 웨이브). DONE 이면 exit 0, STUCK 이면 exit 2
  begin   NODE                    노드 시작 (ready 일 때만)
  finish  NODE [--set f=v ...] [--evidence 경로 ...] [--changed 파일 ...]
                                  게이트를 돌리고 통과하면 쓰기를 반영 · 실패면 원인 분류를 남긴다
                                  --changed: 바뀐 파일(폴더 아님)이 노드의 files 안인지 본다 (병렬 하위 에이전트가 보고)
  fail    NODE --cause C --symptom "..."   에이전트가 스스로 실패를 보고 (C: transient|input|contract_violation|structural)
  exec    NODE                    CODE 노드: begin → cmd → (HARNESS_WRITES {json} 줄) → 게이트 → finish
  wait    NODE --reason "..."     HUMAN 노드: 사람 대기로 둔다 (역질문 화면은 스킬이 띄운다)
  answer  NODE --action A [--note ...] [--set f=v ...]   사람의 답 → 상태 · DECISIONS.md
  decide  --topic T --choice C [--note ...]              노드 밖의 사람 결정 (STUCK · 범위 · 예산) → DECISIONS.md
  reset   NODE --note "..."       사람이 고른 재실행 (failed → pending)
  extend-budget N --note "..."    시도 예산 추가 (사람 결정)
  rebuild                         events 에서 state.json 을 다시 만든다 (digest 출력)

종료 코드  0 성공 · 1 ERROR(스펙 · 명령 오류 — 고치거나 사람에게) · 2 사람 판단 필요(역질문)
           3 실패했지만 선언된 retry 한도 안 (묻지 않고 같은 노드를 다시)

answer · decide · reset · extend-budget 은 **사람의 답을 받은 뒤에만** 쓴다.
하네스는 이것을 코드로 강제하지 못한다 (신뢰 경계) — 그래서 모두 memory/DECISIONS.md 에 남긴다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import spec as S  # noqa: E402

HOME = Path(__file__).resolve().parents[1].as_posix()  # 연결된 프로젝트에서도 맞는 안내 경로
TERMINAL = ("executed", "failed", "cancelled", "skipped")
CAUSES = ("transient", "input", "contract_violation", "structural")


# ── 저장소 ─────────────────────────────────────────────────────────────

class Store:
    def __init__(self, root: Path):
        self.root = root
        self.events_path = root / "trace" / "events.jsonl"
        self.state_path = root / "state" / "state.json"

    def events(self) -> list[dict]:
        if not self.events_path.exists():
            return []
        out = []
        for line in self.events_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append(json.loads(line))
        return out

    def append(self, ev: dict) -> dict:
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        evs = self.events()
        ev = {"seq": len(evs) + 1, "ts": now(), **ev}
        with self.events_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        return ev


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def digest(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


# ── fold ───────────────────────────────────────────────────────────────

def fold(events: list[dict], run_id: str) -> dict:
    st = None
    for ev in events:
        if ev.get("run_id") != run_id:
            continue
        t = ev["type"]
        if t == "run_start":
            st = {"run_id": run_id, "started": ev["ts"], "ended": None, "result": None, "fields": {}, "nodes": {},
                  "attempts_total": 0, "budget_extra": 0, "last_seq": ev["seq"]}
            continue
        if st is None:
            continue
        st["last_seq"] = ev["seq"]
        n = st["nodes"].setdefault(ev.get("node"), {"status": "pending", "attempts": 0, "runs": 0}) \
            if ev.get("node") else None
        if t == "state_write":
            f = ev["field"]
            st["fields"][f] = {"value": ev["value"], "by": ev["by"], "seq": ev["seq"]}
        elif t == "node_start":
            if n["status"] != "failed_retryable":
                n["runs"] += 1
            n["status"] = "running"
            n["attempts"] += 1
            st["attempts_total"] += 1
        elif t == "node_end":
            n["status"] = ev["status"]
            n["last_cause"] = ev.get("cause")
            n["last_symptom"] = ev.get("symptom")
        elif t == "wait":
            n["status"] = "waiting_human"
            n["wait_reason"] = ev.get("reason")
        elif t == "reset":
            n["status"] = "pending"
            n["attempts"] = 0
        elif t == "budget":
            st["budget_extra"] += ev["add"]
        elif t == "run_end":
            st["ended"] = ev["ts"]
            st["result"] = ev["result"]
    return st


def current_run(events: list[dict]) -> str | None:
    starts = [e for e in events if e["type"] == "run_start"]
    return starts[-1]["run_id"] if starts else None


def values_of(st: dict) -> dict:
    return {f: v["value"] for f, v in st["fields"].items()}


# ── 상태에서 계산하는 것들 ──────────────────────────────────────────────

def node_state(st: dict, nid: str) -> dict:
    return st["nodes"].get(nid, {"status": "pending", "attempts": 0, "runs": 0})


def ready_nodes(spec: dict, st: dict) -> list[str]:
    vals = values_of(st)
    out = []
    for n in spec["nodes"]:
        ns = node_state(st, n["id"])
        retry_max = (n.get("retry") or {}).get("max", 0)
        startable = ns["status"] == "pending" or (ns["status"] == "failed_retryable" and ns["attempts"] <= retry_max)
        if startable and all(S.eval_cond(c, vals) for c in n.get("requires", [])):
            out.append(n["id"])
    return out


def is_done(spec: dict, st: dict) -> bool:
    vals = values_of(st)
    return all(S.eval_cond(c, vals) for c in spec["graph"].get("done_when", []))


def is_stopped(spec: dict, st: dict) -> bool:
    """stop_when 은 OR — 하나라도 참이면 사람이 멈추기로 한 것이다."""
    vals = values_of(st)
    return any(S.eval_cond(c, vals) for c in spec["graph"].get("stop_when", []))


def budget_left(spec: dict, st: dict) -> tuple[bool, str]:
    b = spec["graph"].get("budget") or {}
    mx = b.get("max_attempts_total")
    if mx is not None and st["attempts_total"] >= mx + st["budget_extra"]:
        return False, f"시도 예산을 다 썼습니다 ({st['attempts_total']}/{mx + st['budget_extra']})"
    mm = b.get("max_minutes")
    if mm is not None:
        el = (datetime.now() - datetime.fromisoformat(st["started"])).total_seconds() / 60
        if el > mm:
            return False, f"시간 예산을 넘었습니다 ({el:.0f}/{mm}분)"
    return True, ""


def summary(spec: dict, st: dict) -> dict:
    ready = ready_nodes(spec, st)
    by = lambda s: [nid for nid, ns in st["nodes"].items() if ns["status"] == s]  # noqa: E731
    done = is_done(spec, st)
    ok, why = budget_left(spec, st)
    waiting, running = by("waiting_human"), by("running")
    phase = ("DONE" if done else "STOPPED" if is_stopped(spec, st) else "BLOCKED" if not ok
             else "WAITING_HUMAN" if waiting else "RUNNING" if running and not ready
             else "READY" if ready else "STUCK")
    return {"run_id": st["run_id"], "phase": phase, "budget_note": why,
            "ready": ready, "running": running, "waiting_human": waiting,
            "failed": by("failed"), "failed_retryable": by("failed_retryable"),
            "executed": by("executed"), "attempts_total": st["attempts_total"],
            "fields": {f: v["value"] for f, v in st["fields"].items()}, "digest": digest(st)}


# ── 입력 검사 ───────────────────────────────────────────────────────────

def parse_sets(pairs: list[str] | None, files: list[str] | None = None) -> dict:
    out = {}
    for p in pairs or []:
        if "=" not in p:
            raise S.SpecError(f"--set 은 field=value 형식입니다: {p}")
        k, v = p.split("=", 1)
        try:
            out[k.strip()] = json.loads(v)
        except json.JSONDecodeError:
            out[k.strip()] = v
    for fp in files or []:
        try:
            out.update(json.loads(Path(fp).read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, ValueError) as e:
            raise S.SpecError(f"--set-json {fp} 를 읽지 못했습니다 — {e}") from e
    return out


def check_value(f: str, fdef: dict, v):
    t = fdef.get("type")
    ok = {"str": isinstance(v, str), "int": isinstance(v, int) and not isinstance(v, bool),
          "float": isinstance(v, (int, float)) and not isinstance(v, bool), "bool": isinstance(v, bool),
          "list": isinstance(v, list), "dict": isinstance(v, dict),
          "enum": v in fdef.get("values", [])}.get(t, False)
    if not ok:
        raise S.SpecError(f"필드 {f}: {t} 형이 아닙니다 (받은 값 {v!r}" + (f", 허용 {fdef.get('values')}" if t == "enum" else "") + ")")


def check_writes(spec: dict, writer: str, writes: dict):
    fdefs = S.fields(spec)
    for f, v in writes.items():
        if f not in fdefs:
            raise S.SpecError(f"선언되지 않은 필드 {f}")
        if writer not in S.owners(fdefs[f]):
            raise S.SpecError(f"{writer} 는 필드 {f} 의 주인이 아닙니다 (주인: {S.owners(fdefs[f])})")
        check_value(f, fdefs[f], v)


# ── 메모리 (사람이 읽는 기록) ────────────────────────────────────────────

DECISIONS_HEAD = "# DECISIONS — 사람이 고른 것\n\n> 하네스가 자동으로 덧붙인다. `이벤트` 칸의 seq 로 `trace/events.jsonl` 과 이어진다.\n\n"
TROUBLE_HEAD = ("# TROUBLESHOOTING — 증상 → 원인 → 조치\n\n> 실패가 나면 하네스가 증상 줄을 덧붙인다. 원인 · 조치 칸은 해결한 뒤 채운다.\n"
                "> 같은 증상이 여러 Run 에서 반복되면 패턴이다 — graph-plan 에서 스펙 · 계약으로 반영한다.\n\n")


def memo(root: Path, name: str, head: str, body: str):
    p = root / "memory" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.write_text(head, encoding="utf-8")
    with p.open("a", encoding="utf-8") as f:
        f.write(body)


def record_decision(root, st, ev, where, choice, note, options=None):
    memo(root, "DECISIONS.md", DECISIONS_HEAD,
         f"## {ev['ts']} · {where}\n\n| 칸 | 값 |\n| --- | --- |\n| Run | {st['run_id']} |\n"
         f"| 선택지 | {', '.join(options) if options else '-'} |\n| 고른 것 | **{choice}** |\n| 이유(note) | {note or '-'} |\n"
         f"| 이벤트 | seq {ev['seq']} |\n\n")


def record_failure(root, st, ev):
    memo(root, "TROUBLESHOOTING.md", TROUBLE_HEAD,
         f"## {ev['ts']} · {ev['node']} · {ev['status']}\n\n| 칸 | 값 |\n| --- | --- |\n| Run | {st['run_id']} |\n"
         f"| 증상 | {ev.get('symptom') or '-'} |\n| 분류 | {ev.get('cause') or '-'} |\n| 증거 | {', '.join(ev.get('evidence') or []) or '-'} |\n"
         f"| 이벤트 | seq {ev['seq']} |\n| 원인 | (해결 후 채움) |\n| 조치 | (해결 후 채움) |\n\n")


# ── 명령 ───────────────────────────────────────────────────────────────

class Ctx:
    def __init__(self, root: Path):
        self.root = root
        self.spec = S.load(root)
        if not self.spec["graph"]:
            raise S.SpecError("specs/GRAPH.md 의 graph 블록이 없습니다 (S 규모 체크리스트 모드에서는 run.py 를 쓰지 않습니다)")
        self.store = Store(root)
        self.by_id = {n["id"]: n for n in self.spec["nodes"]}

    def state(self, need=True) -> dict | None:
        evs = self.store.events()
        rid = current_run(evs)
        st = fold(evs, rid) if rid else None
        if need and st is None:
            raise S.SpecError("Run 이 없습니다 — `run.py start` 부터")
        return st

    def save(self, st):
        self.store.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.store.state_path.write_text(json.dumps({**st, "digest": digest(st)}, ensure_ascii=False, indent=2), encoding="utf-8")

    def node(self, nid) -> dict:
        if nid not in self.by_id:
            raise S.SpecError(f"없는 노드: {nid}")
        return self.by_id[nid]

    def ev(self, st, **kw) -> dict:
        return self.store.append({"run_id": st["run_id"], **kw})


def human_exit(msg: str) -> int:
    print("⚠ 사람 판단 필요 — " + msg)
    print(f"  → 역질문: 사람에게 ① 지금 ② 왜 ③ 권장 ④ 고르기 ⑤ 답 을 보여 주고 ({HOME}/templates/ASK.md), 답을 `run.py answer` · `run.py decide` 로 남긴다")
    return 2


def cmd_start(c: Ctx, a) -> int:
    st = c.state(need=False)
    if st and not st["ended"] and not a.new:
        return human_exit(f"끝나지 않은 Run {st['run_id']} 이 있습니다. 이어서 하려면 `next`, 버리고 새로 하려면 `start --new`")
    rid = "run-" + datetime.now().strftime("%Y%m%d-%H%M%S")
    used = {e["run_id"] for e in c.store.events()}
    base, k = rid, 2
    while rid in used:
        rid, k = f"{base}-{k}", k + 1
    writes = parse_sets(a.set, a.set_json)
    check_writes(c.spec, S.INPUT_OWNER, writes)
    c.store.append({"run_id": rid, "type": "run_start"})
    st = c.state()
    for f, v in writes.items():
        c.ev(st, type="state_write", field=f, value=v, by=S.INPUT_OWNER)
    st = c.state()
    c.save(st)
    print(f"Run {rid} 시작 · 입력 {list(writes)}")
    return cmd_next(c, a)


def cmd_status(c: Ctx, a) -> int:
    st = c.state()
    s = summary(c.spec, st)
    if a.json:
        print(json.dumps(s, ensure_ascii=False, indent=2))
        return 0
    print(f"Run {s['run_id']} · {s['phase']} · 시도 {s['attempts_total']} · digest {s['digest']}")
    if s["budget_note"]:
        print("  예산:", s["budget_note"])
    for k in ("ready", "running", "waiting_human", "failed_retryable", "failed", "executed"):
        if s[k]:
            print(f"  {k:16} {', '.join(s[k])}")
    for nid in s["waiting_human"]:
        ns = st["nodes"][nid]
        print(f"    ↳ {nid} 대기 이유: {ns.get('wait_reason')}")
    for nid in s["failed"] + s["failed_retryable"]:
        ns = st["nodes"][nid]
        print(f"    ↳ {nid} [{ns.get('last_cause')}] {ns.get('last_symptom')}")
    print("  fields:", json.dumps(s["fields"], ensure_ascii=False)[:400])
    return 0


def cmd_next(c: Ctx, a) -> int:
    st = c.state()
    s = summary(c.spec, st)
    c.save(st)
    if getattr(a, "json", False):
        print(json.dumps({"phase": s["phase"], "ready": s["ready"], "waiting_human": s["waiting_human"]}, ensure_ascii=False))
    if s["phase"] == "DONE":
        if not st["ended"]:
            for n in c.spec["nodes"]:
                stt = node_state(st, n["id"])["status"]
                if stt in ("pending", "failed_retryable"):
                    c.ev(st, type="node_end", node=n["id"], status="skipped", cause=None, symptom="완료 조건이 먼저 참이 됨")
                elif stt in ("running", "waiting_human"):
                    c.ev(st, type="node_end", node=n["id"], status="cancelled", cause=None,
                         symptom="완료 조건이 먼저 참이 됨 — 하던 일이 반영되지 않았다")
            c.ev(st, type="run_end", result="SUCCESS")
            c.save(c.state())
        print("DONE — done_when 이 모두 참입니다")
        return 0
    if s["phase"] == "STOPPED":
        if not st["ended"]:
            c.ev(st, type="run_end", result="STOPPED")
            c.save(c.state())
        print("STOPPED — stop_when 이 참입니다 (사람이 멈추기로 함)")
        return 0
    if s["phase"] == "BLOCKED":
        return human_exit(s["budget_note"])
    if s["phase"] == "WAITING_HUMAN":
        if s["ready"] and not getattr(a, "json", False):
            print("ready 웨이브 (대기와 관계없는 가지):", ", ".join(s["ready"]))
        return human_exit("사람 대기 중인 노드: " + ", ".join(s["waiting_human"]) +
                          (" — 먼저 묻고, 답을 기다리는 동안 위 ready 는 진행해도 된다 (대기 노드의 하류는 상태값 때문에 돌지 않는다)"
                           if s["ready"] else ""))
    if s["phase"] == "STUCK":
        why = [f"{nid}[{st['nodes'][nid].get('last_cause')}] {st['nodes'][nid].get('last_symptom')}" for nid in s["failed"]]
        return human_exit("실행할 수 있는 노드가 없고 완료 조건도 거짓입니다 (STUCK). " + ("실패: " + " / ".join(why) if why else ""))
    if not s["ready"] and s["running"]:
        if getattr(a, "internal", False):  # finish 직후 — 형제 노드가 아직 하위 에이전트에서 도는 중. 소음으로 묻지 않는다
            print("ready 없음 · 진행 중:", ", ".join(s["running"]), "— 그 결과를 기다려 finish 한다")
            return 0
        return human_exit("실행할 노드가 없고 running 인 노드만 있습니다: " + ", ".join(s["running"]) +
                          " — 하위 에이전트가 하고 있으면 그 결과를 기다려 finish, 멈춘 것이면 `run.py fail <노드> --cause structural` 또는 사람이 reset")
    if not getattr(a, "json", False):
        print("ready 웨이브:", ", ".join(s["ready"]) or "(없음)")
        if s["running"]:
            print("running:", ", ".join(s["running"]))
        if len(s["ready"]) > 1:
            print("  (서로 쓰는 필드가 겹치지 않으므로 병렬로 돌릴 수 있습니다 — 병렬 여부는 사람이 승인)")
    return 0


def cmd_begin(c: Ctx, a, quiet=False) -> int:
    st = c.state()
    ok, why = budget_left(c.spec, st)
    if not ok:
        return human_exit(why)
    n = c.node(a.node)
    if a.node not in ready_nodes(c.spec, st):
        raise S.SpecError(f"{a.node} 는 지금 ready 가 아닙니다 (상태 {node_state(st, a.node)['status']}) — `run.py next` 를 보십시오")
    for other, ons in st["nodes"].items():
        if other != a.node and ons["status"] in ("running", "waiting_human") and other in c.by_id:
            both = [f"{x} ↔ {y}" for x in n.get("files", []) for y in c.by_id[other].get("files", []) if S.paths_overlap(x, y)]
            if both:
                raise S.SpecError(f"{a.node} 를 시작할 수 없습니다 — 진행 중인 {other} 와 고치는 경로가 겹칩니다 {both}")
    c.ev(st, type="node_start", node=a.node,
         inputs={f: digest(st["fields"][f]["value"]) for f in S.node_reads(n) if f in st["fields"]})
    if not quiet:
        ns = node_state(c.state(), a.node)
        print(f"{a.node} 시작 · {ns['runs']}번째 실행 · 시도 {ns['attempts']} · 스펙 {c.spec['sources'].get(a.node)}")
    return 0


def evidence_dir(c: Ctx, nid: str, st) -> Path:
    ns = node_state(st, nid)
    d = c.root / "evidence" / nid / f"r{ns['runs']:02d}a{ns['attempts']:02d}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def expand(cmd: str) -> str:
    """`{python}` → 하네스를 돌리는 그 파이썬. OS 마다 python / python3 이 달라도 스펙은 하나로 쓴다."""
    py = sys.executable if " " not in sys.executable else f'"{sys.executable}"'
    return cmd.replace("{python}", py)


def run_cmd(cmd: str, cwd: Path, log: Path, timeout: int, env: dict | None = None) -> int:
    t0 = time.time()
    cmd = expand(cmd)
    try:
        p = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, timeout=timeout,
                           env={**os.environ, **(env or {})})
        out = p.stdout.decode("utf-8", "replace") + p.stderr.decode("utf-8", "replace")
        code = p.returncode
    except subprocess.TimeoutExpired:
        out, code = f"(시간 초과 {timeout}초)", 124
    log.write_text(f"$ {cmd}\n(cwd {cwd} · exit {code} · {time.time() - t0:.1f}초)\n\n{out}", encoding="utf-8")
    return code


def cmd_env(c: Ctx, nid: str, st) -> dict:
    """CODE 노드 · 게이트가 지금 상태를 읽는 창구. 쓰기는 stdout 의 `HARNESS_WRITES {json}` 줄로만."""
    c.save(st)
    return {"HARNESS_STATE": str(c.store.state_path), "HARNESS_NODE": nid, "HARNESS_RUN": st["run_id"],
            "PYTHONIOENCODING": "utf-8"}


def end_node(c: Ctx, st, nid, ok: bool, writes: dict, evidence: list[str], cause=None, symptom=None) -> int:
    n = c.node(nid)
    if ok:
        try:
            check_writes(c.spec, nid, writes)
        except S.SpecError as e:
            ok, cause, symptom = False, "contract_violation", f"쓰기가 계약과 다릅니다 — {e}"
    if ok:
        optional = {(n.get("human") or {}).get("note_field")}  # 자유 문장 note 는 비어도 된다
        missing = [f for f in n.get("writes", []) if f not in writes and f not in st["fields"] and f not in optional]
        if missing:
            ok, cause, symptom = False, "contract_violation", f"선언한 writes 를 쓰지 않았습니다: {missing}"
    if ok:
        for f, v in writes.items():
            c.ev(st, type="state_write", node=nid, field=f, value=v, by=nid)
        c.ev(st, type="node_end", node=nid, status="executed", evidence=evidence)
        print(f"{nid}: PASS · 쓴 필드 {list(writes)}")
        return cmd_next(c, argparse.Namespace(json=False, internal=True))
    ns = node_state(c.state(), nid)
    retry = n.get("retry") or {}
    retry_max = retry.get("max", 0)
    status = "failed_retryable" if cause in retry.get("on", ["transient"]) and ns["attempts"] <= retry_max else "failed"
    ev = c.ev(st, type="node_end", node=nid, status=status, cause=cause, symptom=symptom, evidence=evidence)
    record_failure(c.root, st, ev)
    print(f"{nid}: FAIL [{cause}] {symptom} → {status}")
    if status == "failed_retryable":
        print(f"  자동 재시도 가능 (retry {ns['attempts']}/{retry_max + 1}) — 묻지 않고 같은 노드를 다시")
        return 3
    return human_exit(f"{nid} 실패 [{cause}] — 원인을 고쳐 reset 하거나 재계획(graph-plan)")


def gate(c: Ctx, nid, st, d: Path) -> tuple[bool, str | None, list[str]]:
    gt = c.node(nid).get("gate") or {}
    if not gt.get("cmd"):
        return True, None, []
    log = d / "gate.log"
    cwd = c.root / gt["cwd"] if gt.get("cwd") else c.root  # 하위 폴더에서 테스트 (예: "web")
    if not cwd.is_dir():
        log.write_text(f"gate.cwd {gt.get('cwd')} 폴더가 없습니다", encoding="utf-8")
        return False, f"gate.cwd {gt.get('cwd')!r} 폴더가 없습니다", [log.relative_to(c.root).as_posix()]
    code = run_cmd(gt["cmd"], cwd, log, gt.get("timeout", 600), cmd_env(c, nid, st))
    want = int(str(gt.get("pass", "exit==0")).split("==")[1])  # 형식은 validate 1행이 본다
    rel = log.relative_to(c.root).as_posix()
    if code == want:
        return True, None, [rel]
    return False, f"게이트 exit {code} (기대 {want}) — {rel}{first_error(log)}", [rel]


def first_error(log: Path) -> str:
    """증상을 구분하려고 로그의 첫 오류 줄을 붙인다 — 같은 'exit 1' 이라도 원인이 다르면 다른 증상이다."""
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if re.search(r"(Error|Exception|FAIL:|AssertionError|Traceback \(most)", s) and not s.startswith("$"):
            if s.startswith("Traceback"):
                continue
            return " · " + s[:140]
    return ""


def write_result(c, d, nid, st, ok, writes, extra=None):
    (d / "result.json").write_text(json.dumps({
        "node": nid, "run_id": st["run_id"], "ok": ok,
        "writes": writes, "inputs_digest": {f: digest(v["value"]) for f, v in st["fields"].items()},
        "gate": (c.node(nid).get("gate") or {}).get("cmd"), **(extra or {})}, ensure_ascii=False, indent=2), encoding="utf-8")


def cmd_finish(c: Ctx, a) -> int:
    st = c.state()
    if node_state(st, a.node)["status"] != "running":
        raise S.SpecError(f"{a.node} 는 running 이 아닙니다 — 먼저 `run.py begin {a.node}`")
    writes = parse_sets(a.set, a.set_json)
    changed = list(a.changed or [])
    outside = [x for x in changed if not S.contained(x, c.node(a.node).get("files", []))]
    d = evidence_dir(c, a.node, st)
    if outside:
        ok, symptom, ev_paths = False, f"노드의 files 밖을 고쳤습니다 {outside} (files: {c.node(a.node).get('files')})", []
    else:
        ok, symptom, ev_paths = gate(c, a.node, st, d)
    write_result(c, d, a.node, st, ok, writes, {"changed": changed} if changed else None)
    ev_paths = ([(d / "result.json").relative_to(c.root).as_posix()] + ev_paths +
                [str(x).replace("\\", "/") for x in (a.evidence or [])])
    return end_node(c, st, a.node, ok, writes, ev_paths, cause=None if ok else (a.cause or "contract_violation"), symptom=symptom)


def cmd_fail(c: Ctx, a) -> int:
    st = c.state()
    if node_state(st, a.node)["status"] != "running":
        raise S.SpecError(f"{a.node} 는 running 이 아닙니다")
    return end_node(c, st, a.node, False, {}, [str(x).replace("\\", "/") for x in (a.evidence or [])], cause=a.cause, symptom=a.symptom)


def cmd_exec(c: Ctx, a) -> int:
    n = c.node(a.node)
    if n.get("type") != "CODE":
        raise S.SpecError(f"{a.node} 는 CODE 노드가 아닙니다 — AGENT 는 begin → 작업 → finish")
    r = cmd_begin(c, a, quiet=True)
    if r:
        return r
    st = c.state()
    d = evidence_dir(c, a.node, st)
    log = d / "cmd.log"
    c.save(st)
    code = run_cmd(n["cmd"], c.root, log, n.get("timeout", 600), cmd_env(c, a.node, st))
    writes, bad = {}, None
    for line in log.read_text(encoding="utf-8").splitlines():
        if line.startswith("HARNESS_WRITES "):
            try:
                w = json.loads(line[len("HARNESS_WRITES "):])
                if not isinstance(w, dict):
                    raise ValueError("객체({...})가 아닙니다")
                writes.update(w)
            except (json.JSONDecodeError, ValueError) as e:
                bad = f"HARNESS_WRITES 줄의 JSON 이 깨졌습니다 ({e})"
    rel = log.relative_to(c.root).as_posix()
    if code != 0 or bad:
        # exit 만으로는 일시적인지 알 수 없다 — 스펙의 transient_exit 에 적힌 exit 만 transient, 나머지는 contract_violation
        write_result(c, d, a.node, st, False, writes, {"cmd": n["cmd"], "exit": code})
        cause = a.cause or ("transient" if code in n.get("transient_exit", []) else "contract_violation")
        return end_node(c, st, a.node, False, {}, [rel], cause=cause,
                        symptom=bad or f"cmd exit {code} — {rel}{first_error(log)}")
    ok, symptom, ev_paths = gate(c, a.node, st, d)
    write_result(c, d, a.node, st, ok, writes, {"cmd": n["cmd"], "exit": code})
    return end_node(c, st, a.node, ok, writes, [(d / "result.json").relative_to(c.root).as_posix(), rel] + ev_paths,
                    cause=None if ok else "contract_violation", symptom=symptom)


def cmd_wait(c: Ctx, a) -> int:
    n = c.node(a.node)
    if n.get("type") != "HUMAN":
        raise S.SpecError(f"{a.node} 는 HUMAN 노드가 아닙니다")
    st = c.state()
    if node_state(st, a.node)["status"] != "running":
        r = cmd_begin(c, a, quiet=True)
        if r:
            return r
        st = c.state()
    c.ev(st, type="wait", node=a.node, reason=a.reason)
    return human_exit(f"{a.node}: 고르기 {n['human']['actions']} — {a.reason}")


def cmd_answer(c: Ctx, a) -> int:
    n = c.node(a.node)
    st = c.state()
    ns = node_state(st, a.node)
    if ns["status"] != "waiting_human":
        raise S.SpecError(f"{a.node} 는 사람 대기가 아닙니다 (상태 {ns['status']})")
    extra = parse_sets(a.set, None)
    if n["type"] == "HUMAN":
        acts = n["human"]["actions"]
        if a.action not in acts:
            raise S.SpecError(f"{a.node} 의 답은 {acts} 중 하나입니다 (받은 것 {a.action!r}) — note 는 라우팅에 쓰지 않습니다")
        writes = {n["human"]["field"]: a.action, **extra}
        if n["human"].get("note_field") and a.note:
            writes[n["human"]["note_field"]] = a.note
        options = acts
    else:
        raise S.SpecError(f"{a.node} 는 HUMAN 노드가 아닙니다")
    ev = c.ev(st, type="answer", node=a.node, action=a.action, note=a.note, writes=writes)
    record_decision(c.root, st, ev, f"{a.node} ({n['type']})", a.action + (f" {extra}" if extra else ""), a.note, options)
    return end_node(c, c.state(), a.node, True, writes, [])


def cmd_decide(c: Ctx, a) -> int:
    st = c.state()
    ev = c.ev(st, type="decision", topic=a.topic, choice=a.choice, note=a.note)
    record_decision(c.root, st, ev, a.topic, a.choice, a.note, a.options.split(",") if a.options else None)
    print(f"결정 기록: {a.topic} → {a.choice} (seq {ev['seq']})")
    return 0


def cmd_reset(c: Ctx, a) -> int:
    st = c.state()
    c.node(a.node)
    ns = node_state(st, a.node)
    if ns["status"] not in ("failed", "failed_retryable", "executed", "cancelled", "running", "waiting_human"):
        raise S.SpecError(f"{a.node} 는 reset 할 수 없는 상태입니다 ({ns['status']})")
    ev = c.ev(st, type="reset", node=a.node, note=a.note)
    record_decision(c.root, st, ev, f"{a.node} 재실행", "reset", a.note)
    return cmd_next(c, argparse.Namespace(json=False))


def cmd_extend(c: Ctx, a) -> int:
    st = c.state()
    ev = c.ev(st, type="budget", add=a.n, note=a.note)
    record_decision(c.root, st, ev, "시도 예산 추가", f"+{a.n}", a.note)
    return cmd_next(c, argparse.Namespace(json=False))


def cmd_rebuild(c: Ctx, a) -> int:
    st = c.state()
    c.save(st)
    print(f"state.json 재생성 · Run {st['run_id']} · digest {digest(st)}")
    return 0


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def p(name, *node, **kw):
        sp = sub.add_parser(name)
        if node:
            sp.add_argument("node")
        return sp

    sp = p("start"); sp.add_argument("--set", action="append"); sp.add_argument("--set-json", action="append"); sp.add_argument("--new", action="store_true")
    sp = p("status"); sp.add_argument("--json", action="store_true")
    sp = p("next"); sp.add_argument("--json", action="store_true")
    p("begin", True)
    sp = p("finish", True); sp.add_argument("--set", action="append"); sp.add_argument("--set-json", action="append")
    sp.add_argument("--evidence", action="append"); sp.add_argument("--cause", choices=CAUSES)
    sp.add_argument("--changed", nargs="+")
    sp = p("fail", True); sp.add_argument("--cause", choices=CAUSES, required=True); sp.add_argument("--symptom", required=True)
    sp.add_argument("--evidence", action="append")
    sp = p("exec", True); sp.add_argument("--cause", choices=CAUSES)
    sp = p("wait", True); sp.add_argument("--reason", required=True)
    sp = p("answer", True); sp.add_argument("--action", required=True); sp.add_argument("--note"); sp.add_argument("--set", action="append")
    sp = p("decide"); sp.add_argument("--topic", required=True); sp.add_argument("--choice", required=True)
    sp.add_argument("--note"); sp.add_argument("--options")
    sp = p("reset", True); sp.add_argument("--note", required=True)
    sp = p("extend-budget"); sp.add_argument("n", type=int); sp.add_argument("--note", required=True)
    p("rebuild")
    a = ap.parse_args(argv)
    try:
        c = Ctx(S.project_dir(a.project))
        fn = {"start": cmd_start, "status": cmd_status, "next": cmd_next, "begin": cmd_begin, "finish": cmd_finish,
              "fail": cmd_fail, "exec": cmd_exec, "wait": cmd_wait, "answer": cmd_answer,
              "decide": cmd_decide, "reset": cmd_reset, "extend-budget": cmd_extend,
              "rebuild": cmd_rebuild}[a.cmd]
        return fn(c, a)
    except S.SpecError as e:
        print("ERROR:", e)
        return 1
    except Exception as e:  # 하네스가 터져도 노드를 running 에 버려두지 않는다 — 기록하고 사람에게
        nid = getattr(a, "node", None)
        try:
            st = c.state()
            if nid and node_state(st, nid)["status"] == "running":
                ev = c.ev(st, type="node_end", node=nid, status="failed", cause="structural",
                          symptom=f"하네스 오류 {type(e).__name__}: {e}"[:200])
                record_failure(c.root, st, ev)
        except Exception:
            pass
        return human_exit(f"하네스 오류 {type(e).__name__}: {e}" + (f" — {nid} 는 failed(structural) 로 기록" if nid else ""))


if __name__ == "__main__":
    sys.exit(main())
