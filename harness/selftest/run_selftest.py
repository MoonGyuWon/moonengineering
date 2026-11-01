"""검사기를 검사한다 — 정상 프로젝트는 통과하고, 망가뜨린 프로젝트는 그 검사행에서 빨간불이 켜져야 한다.
그리고 실행기가 상태값만으로 맞게 도는지 시나리오로 본다.

    python harness/selftest/run_selftest.py      exit 0 = 전부 통과
"""
from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
HARNESS = HERE.parent
sys.path.insert(0, str(HARNESS))
sys.path.insert(0, str(HERE))
import fixture as F  # noqa: E402
import validate as V  # noqa: E402

RESULTS: list[tuple[bool, str]] = []


def check(ok: bool, name: str, detail: str = ""):
    RESULTS.append((ok, name))
    print(("  PASS " if ok else "  FAIL ") + name + ("" if ok else f"\n       {detail}"))


def tmp() -> Path:
    return Path(tempfile.mkdtemp(prefix="harness-selftest-"))


def node(graph, nid):
    return next(n for n in graph["nodes"] if n["id"] == nid)


def run_validate(req=None, graph=None) -> tuple[int, dict]:
    d = tmp()
    try:
        F.write(d, req, graph)
        r = V.validate(d)
        return r.code(), r.rows
    finally:
        shutil.rmtree(d, ignore_errors=True)


def bad_rows(rows) -> list[str]:
    return [k for k, items in rows.items() if any(lv in ("ERROR", "SHORT") for lv, _ in items)]


# ── 1. validate ─────────────────────────────────────────────────────────

def m(fn):
    g, r = copy.deepcopy(F.GRAPH), copy.deepcopy(F.REQUIREMENTS)
    fn(g, r)
    return r, g


MUTATIONS = [
    ("게이트 없는 AGENT/CODE 노드", "1", lambda g, r: node(g, "T02a-stats").pop("gate")),
    ("cmd 없는 CODE 노드", "1", lambda g, r: node(g, "T01-load").pop("cmd")),
    ("retry.on 에 모르는 원인", "1", lambda g, r: node(g, "X09-flaky").update(retry={"max": 1, "on": ["oops"]})),
    ("선언 안 된 필드 쓰기", "4", lambda g, r: node(g, "T01-load")["writes"].append("ghost")),
    ("필드 하나에 주인 둘", "4", lambda g, r: (g["fields"]["stats_a"].update(owners=["T02a-stats", "T02b-stats"]),
                                              g["fields"]["stats_a"].pop("owner"), node(g, "T02b-stats")["writes"].append("stats_a"))),
    ("자유 문장 필드로 분기", "3", lambda g, r: node(g, "T07-publish")["requires"].append("approval.note == ok")),
    ("enum 에 없는 값", "3", lambda g, r: node(g, "H06-approve").update(requires=["check.verdict == ok"])),
    ("조건식 문법 오류", "3", lambda g, r: node(g, "T01-load").update(requires=["input_path ~ x"])),
    ("영영 준비되지 못하는 노드", "2", lambda g, r: node(g, "T01-load").update(requires=["rows exists"])),
    ("requires 순환 = 교착", "5", lambda g, r: node(g, "C03-check")["requires"].append("approval.action exists")),
    ("맡은 노드 없는 REQ", "6", lambda g, r: r["reqs"].append({"id": "REQ-F9", "text": "x", "acceptance": "y"})),
    ("사람 승인 없는 부작용", "8", lambda g, r: node(g, "T07-publish").update(requires=["check.verdict == pass"])),
    ("승인 필드를 exists 로 건 부작용 (거절해도 지나감)", "8", lambda g, r: node(g, "T07-publish").update(requires=["approval.action exists"])),
    ("gate.pass 형식 오류", "1", lambda g, r: node(g, "T01-load")["gate"].update({"pass": "exit 0"})),
    ("같은 웨이브 파일 충돌", "8", lambda g, r: node(g, "T02b-stats").update(files=["out/a.json"])),
    ("폴더와 그 안 파일 충돌 (out/ ↔ out/a.json)", "8", lambda g, r: node(g, "T02b-stats").update(files=["out/"])),
    ("경로 표기만 다른 충돌 (./out/a.json)", "8", lambda g, r: node(g, "T02b-stats").update(files=["./out/a.json"])),
    ("missing 조건은 순서가 아니다", "8", lambda g, r: (node(g, "T02b-stats").update(requires=["rows exists", "stats_a missing"]),
                                                     node(g, "T02b-stats").update(files=["out/a.json"]))),
    ("거절 값(== stop)으로 건 부작용", "8", lambda g, r: node(g, "T07-publish").update(requires=["approval.action == stop"])),
    ("gate.cwd 가 프로젝트 밖", "1", lambda g, r: node(g, "T01-load")["gate"].update(cwd="../x")),
    ("HUMAN actions 와 enum 불일치", "8", lambda g, r: node(g, "H06-approve")["human"].update(actions=["publish", "later"])),
]


def test_validate():
    print("[validate]")
    code, rows = run_validate()
    check(code == 0, "정상 프로젝트 → PASS", f"exit {code} · {bad_rows(rows)} · {rows}")
    for name, row, fn in MUTATIONS:
        req, g = m(fn)
        code, rows = run_validate(req, g)
        hit = [k for k in bad_rows(rows) if k.startswith(row)]
        check(code == 1 and hit, f"{name} → {row}행 ERROR", f"exit {code} · 빨간불 행 {bad_rows(rows)}")
    for name, fn in [("미결 질문", lambda g, r: r["open_questions"].append("배포 대상은?")),
                     ("M 인데 도구 선정(tools) 없음", lambda g, r: r.pop("tools")),
                     ("승인 전(DRAFT)", lambda g, r: r.update(status="DRAFT"))]:
        req, g = m(fn)
        code, rows = run_validate(req, g)
        check(code == 2 and "7 요구사항 확정" in bad_rows(rows), f"{name} → 7행 SHORT", f"exit {code} · {bad_rows(rows)}")
    # S 규모 = 체크리스트 모드
    d = tmp()
    try:
        req = dict(copy.deepcopy(F.REQUIREMENTS), scale="S")
        F.write(d, req)
        check(V.validate(d).code() == 2, "S 규모인데 체크리스트 없음 → SHORT")
        steps = [{"id": f"S{i}", "do": "x", "check": "y", "reqs": [q["id"]]} for i, q in enumerate(req["reqs"][:-1])]
        (d / "specs" / "CHECKLIST.md").write_text(F.block({"kind": "checklist", "steps": steps}), encoding="utf-8")
        r = V.validate(d)
        check(r.code() == 1 and "6 추적성" in bad_rows(r.rows), "체크리스트가 REQ 하나를 빠뜨림 → 6행 ERROR")
        steps.append({"id": "S9", "do": "x", "check": "y", "reqs": [req["reqs"][-1]["id"]]})
        (d / "specs" / "CHECKLIST.md").write_text(F.block({"kind": "checklist", "steps": steps}), encoding="utf-8")
        check(V.validate(d).code() == 0, "체크리스트 모드 정상 → PASS")
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ── 2. run (상태값만으로 도는가) ───────────────────────────────────────────

class Proj:
    def __init__(self, graph=None, env=None):
        self.d = tmp()
        F.write(self.d, graph=graph)
        self.env = {**os.environ, "PYTHONIOENCODING": "utf-8", **(env or {})}

    def run(self, *args) -> tuple[int, str]:
        p = subprocess.run([sys.executable, str(HARNESS / "run.py"), "--project", str(self.d), *args],
                           capture_output=True, env=self.env)
        return p.returncode, p.stdout.decode("utf-8", "replace") + p.stderr.decode("utf-8", "replace")

    def ready(self) -> list[str]:
        code, out = self.run("next", "--json")
        return json.loads(out.splitlines()[0])["ready"] if out.startswith("{") else []

    def status(self) -> dict:
        return json.loads(self.run("status", "--json")[1])

    def events(self) -> list[dict]:
        return [json.loads(x) for x in (self.d / "trace" / "events.jsonl").read_text(encoding="utf-8").splitlines() if x]

    def close(self):
        shutil.rmtree(self.d, ignore_errors=True)


def to_review(p: Proj):
    p.run("start", "--set", "input_path=data.csv")
    for nid in ("T01-load", "T02a-stats", "T02b-stats", "C03-check"):
        p.run("exec", nid)


def test_happy_path():
    print("[run · 정상 경로 + 병렬 웨이브 + 사람 게이트]")
    p = Proj()
    try:
        code, out = p.run("start", "--set", "input_path=data.csv")
        check(code == 0 and p.ready() == ["T01-load"], "start → ready = T01 만", out)
        p.run("exec", "T01-load")
        check(sorted(p.ready()) == ["T02a-stats", "T02b-stats"], "T01 뒤 ready 웨이브 = T02a · T02b (병렬)", str(p.ready()))
        p.run("exec", "T02a-stats")
        check(p.ready() == ["T02b-stats"], "T02a 끝 → 다시 돌지 않고 T02b 만 남음 (재개 시 성공 노드 재실행 없음)", str(p.ready()))
        p.run("exec", "T02b-stats")
        p.run("exec", "C03-check")
        check(p.ready() == ["H06-approve"], "검사 통과 → H06 ready", str(p.ready()))
        code, out = p.run("wait", "H06-approve", "--reason", "발행 승인")
        check(code == 2 and "waiting_human" in json.dumps(p.status()), "HUMAN 노드 → 대기 (exit 2)", out)
        code, out = p.run("answer", "H06-approve", "--action", "maybe")
        check(code == 1, "허용값 밖의 답 → 거부", out)
        p.run("answer", "H06-approve", "--action", "publish", "--note", "좋습니다")
        code, out = p.run("exec", "T07-publish")
        check(code == 0 and "DONE" in out, "발행 → DONE", out)
        evs = p.events()
        check(evs[-1]["type"] == "run_end" and evs[-1]["result"] == "SUCCESS", "run_end SUCCESS 이벤트")
        skipped = [e["node"] for e in evs if e["type"] == "node_end" and e["status"] == "skipped"]
        check(skipped == ["X09-flaky"], "준비되지 않은 노드는 skipped 로 닫힘", str(skipped))
        dec = (p.d / "memory" / "DECISIONS.md").read_text(encoding="utf-8")
        check(dec.count("\n## ") == 1 and "publish" in dec, "사람의 답이 DECISIONS.md 에 남음", dec)
        before = json.loads((p.d / "state" / "state.json").read_text(encoding="utf-8"))["digest"]
        (p.d / "state" / "state.json").unlink()
        p.run("rebuild")
        after = json.loads((p.d / "state" / "state.json").read_text(encoding="utf-8"))["digest"]
        check(before == after, "state.json 을 지우고 이벤트로 다시 만들면 digest 가 같다", f"{before} != {after}")
    finally:
        p.close()


def test_retry_and_reset():
    print("[run · 일시적 오류 재시도 → 실패 → 사람이 reset]")
    p = Proj()
    try:
        p.run("start", "--set", "input_path=flaky")
        check("X09-flaky" in p.ready(), "input_path=flaky → X09 ready")
        code, out = p.run("exec", "X09-flaky")
        check(code == 3 and "failed_retryable" in out and "X09-flaky" in p.ready(), "1회째 실패(transient) → 자동 재시도 가능 (exit 3)", out)
        code, out = p.run("exec", "X09-flaky")
        check(code == 2 and "X09-flaky" in p.status()["failed"], "2회째 실패 → failed · 사람 판단 (exit 2)", out)
        tr = (p.d / "memory" / "TROUBLESHOOTING.md").read_text(encoding="utf-8")
        check(tr.count("\n## ") == 2, "실패 2건이 TROUBLESHOOTING.md 에 남음")
        p.run("reset", "X09-flaky", "--note", "환경 고친 뒤 다시")
        check("X09-flaky" in p.ready(), "reset → 다시 ready")
    finally:
        p.close()


def test_budget():
    print("[run · 예산]")
    g = copy.deepcopy(F.GRAPH)
    g["budget"] = {"max_attempts_total": 2}
    p = Proj(graph=g)
    try:
        p.run("start", "--set", "input_path=data.csv")
        p.run("exec", "T01-load")
        p.run("exec", "T02a-stats")
        code, out = p.run("exec", "T02b-stats")
        check(code == 2 and "예산" in out, "시도 예산 소진 → 시작 거부 (exit 2)", out)
        p.run("extend-budget", "1", "--note", "한 번만 더")
        code, out = p.run("exec", "T02b-stats")
        check("T02b-stats: PASS" in out and code == 2 and "3/3" in out,
              "사람이 예산 추가 → 한 노드 진행 → 바로 다음에 다시 예산 소진을 알림", out)
    finally:
        p.close()


def test_stop():
    print("[run · 사람이 stop]")
    p = Proj()
    try:
        to_review(p)
        p.run("wait", "H06-approve", "--reason", "발행?")
        code, out = p.run("answer", "H06-approve", "--action", "stop")
        check(code == 0 and "STOPPED" in out, "stop → STOPPED (stop_when)", out)
    finally:
        p.close()


def test_render():
    print("[render]")
    p = Proj()
    try:
        code = subprocess.run([sys.executable, str(HARNESS / "render.py"), "--project", str(p.d)], capture_output=True).returncode
        g = (p.d / "diagrams" / "graph.md").read_text(encoding="utf-8")
        check(code == 0 and "flowchart LR" in g and "class T01_load draft" in g, "Run 전: 그래프 그림 · 노드는 draft 표시")
        to_review(p)
        subprocess.run([sys.executable, str(HARNESS / "render.py"), "--project", str(p.d)], capture_output=True)
        g = (p.d / "diagrams" / "graph.md").read_text(encoding="utf-8")
        check("class T01_load executed" in g and "class H06_approve ready" in g, "Run 후: executed · ready 색", g[:1500])
        t = (p.d / "diagrams" / "timeline.md").read_text(encoding="utf-8")
        check("gantt" in t and "T02a-stats" in t, "타임라인 gantt")
    finally:
        p.close()


def test_robust():
    print("[run · 고착 방지 (페이블 리뷰)]")
    g = copy.deepcopy(F.GRAPH)
    node(g, "T01-load")["cmd"] = "{python} tools/emit.py BAD"
    p = Proj(graph=g)
    try:
        em = p.d / "tools" / "emit.py"
        em.write_text(em.read_text(encoding="utf-8") + "if sys.argv[1] == 'BAD': print('HARNESS_WRITES {bad')\n", encoding="utf-8")
        p.run("start", "--set", "input_path=data.csv")
        code, out = p.run("exec", "T01-load")
        st = p.status()
        check(code == 2 and "T01-load" in st["failed"], "깨진 HARNESS_WRITES → running 에 고착되지 않고 failed · 역질문", out)
        p.run("reset", "T01-load", "--note", "고친 뒤 다시")
        check(p.ready() == ["T01-load"], "reset → 다시 ready")
        p.run("begin", "T01-load")
        code, out = p.run("next")
        check(code == 2 and "running" in out, "ready 없이 running 만 남음 → 헛돌지 않고 역질문 (exit 2)", out)
        code, out = p.run("reset", "T01-load", "--note", "멈춘 노드 정리")
        check(p.ready() == ["T01-load"], "고아가 된 running 노드도 reset 가능", out)
    finally:
        p.close()


def test_tools_field():
    print("[req · 도구 선정]")
    r = copy.deepcopy(F.REQUIREMENTS)
    r["tools"] = [{"need": "CSV 읽기", "choice": "", "status": "undecided"}]
    code, rows = run_validate(req=r)
    check(code == 2 and "7 요구사항 확정" in bad_rows(rows), "도구 미정 → 7행 SHORT", str(rows.get("7 요구사항 확정")))
    r["tools"] = [{"need": "CSV 읽기", "choice": "csv (표준 라이브러리)", "status": "decided", "source": "알고 있는 정보 (확인 안 함)"}]
    code, rows = run_validate(req=r)
    check(code == 0, "도구를 정하고 근거를 적으면 → PASS", str(rows.get("7 요구사항 확정")))


PAR_GRAPH = {
    "kind": "graph", "done_when": ["e2e.verdict == pass"],
    "fields": {
        "input_path": {"type": "str", "owner": "input"},
        "contract.status": {"type": "enum", "values": ["frozen"], "owner": "C00-contract"},
        "api.done": {"type": "bool", "owner": "T11-api"},
        "web.done": {"type": "bool", "owner": "T12-web"},
        "e2e.verdict": {"type": "enum", "values": ["pass", "fail"], "owner": "C20-e2e"},
    },
    "nodes": [
        {"kind": "node", "id": "C00-contract", "type": "AGENT", "reqs": ["REQ-F1"], "requires": ["input_path exists"],
         "writes": ["contract.status"], "files": ["contracts/"], "gate": {"cmd": "{python} -c exit(0)"}},
        {"kind": "node", "id": "T11-api", "type": "AGENT", "reqs": ["REQ-F2"], "requires": ["contract.status == frozen"],
         "writes": ["api.done"], "files": ["api/"], "gate": {"cmd": "{python} check.py", "cwd": "api"}},
        {"kind": "node", "id": "T12-web", "type": "AGENT", "reqs": ["REQ-N1"], "requires": ["contract.status == frozen"],
         "writes": ["web.done"], "files": ["web/"], "gate": {"cmd": "{python} check.py", "cwd": "web"}},
        {"kind": "node", "id": "C20-e2e", "type": "CODE", "reqs": ["REQ-F3"], "requires": ["api.done == true", "web.done == true"],
         "writes": ["e2e.verdict"], "files": ["e2e/"], "cmd": "{python} tools/emit.py E2E", "gate": {"cmd": "{python} -c exit(0)"}},
    ],
}


def par_project() -> Proj:
    q = Proj(graph=copy.deepcopy(PAR_GRAPH))
    em = q.d / "tools" / "emit.py"
    em.write_text(em.read_text(encoding="utf-8").replace('"T07":', '"E2E": {"e2e.verdict": "pass"}, "T07":'), encoding="utf-8")
    for ar in ("web", "api"):
        (q.d / ar).mkdir()
        (q.d / ar / "check.py").write_text("import pathlib,sys\nsys.exit(0 if pathlib.Path('done.txt').exists() else 1)\n", encoding="utf-8")
    return q


def test_parallel_files():
    print("[병렬 노드 — 계약 → web · api → 통합 (files · gate.cwd)]")
    code, rows = run_validate(graph=copy.deepcopy(PAR_GRAPH))
    check(code == 0, "frontend/backend 형 그래프 → PASS", str({k: v for k, v in rows.items() if v}))
    q = par_project()
    try:
        q.run("start", "--set", "input_path=x")
        q.run("begin", "C00-contract")
        q.run("finish", "C00-contract", "--set", "contract.status=frozen")
        check(sorted(q.ready()) == ["T11-api", "T12-web"], "계약 뒤 web · api 가 한 웨이브", str(q.ready()))
        q.run("begin", "T11-api"); q.run("begin", "T12-web")
        (q.d / "api" / "done.txt").write_text("ok", encoding="utf-8")
        code, out = q.run("finish", "T11-api", "--set", "api.done=true", "--changed", "api/done.txt", "web/oops.js")
        check(code == 3 or code == 2, "노드 files 밖 파일을 바꿨다고 보고 → 실패", out)
        check("files 밖" in out, "  └ 증상에 files 밖 파일이 남는다", out)
        q.run("reset", "T11-api", "--note", "다시")
        q.run("begin", "T11-api")
        code, out = q.run("finish", "T11-api", "--set", "api.done=true", "--changed", "api/done.txt")
        check("T11-api: PASS" in out, "gate.cwd=api 에서 게이트 · 바뀐 파일 ⊆ files → PASS", out)
        (q.d / "web" / "done.txt").write_text("ok", encoding="utf-8")
        q.run("finish", "T12-web", "--set", "web.done=true")
        code, out = q.run("exec", "C20-e2e")
        check(code == 0 and "DONE" in out, "통합(e2e) → DONE", out)
    finally:
        q.close()


def test_runtime_guards():
    print("[run · 실행 중 안전망]")
    g = copy.deepcopy(F.GRAPH)
    g["fields"]["flaky.done"] = {"type": "bool", "owner": "X09-flaky"}
    node(g, "X09-flaky").update(requires=["input_path exists"], files=["out/a.json"], cmd="{python} tools/emit.py BADTYPE")
    node(g, "T02a-stats").update(files=["out/a.json"])
    p = Proj(graph=g)
    try:
        em = p.d / "tools" / "emit.py"
        em.write_text(em.read_text(encoding="utf-8").replace('"T07":', '"BADTYPE": {"flaky.done": "yes"}, "T07":'), encoding="utf-8")
        p.run("start", "--set", "input_path=data.csv")
        code, out = p.run("exec", "X09-flaky")
        check("X09-flaky" in p.status()["failed"], "형이 틀린 HARNESS_WRITES → running 에 남지 않고 failed", out)
        p.run("exec", "T01-load")
        p.run("reset", "X09-flaky", "--note", "x")
        p.run("begin", "X09-flaky")
        code, out = p.run("begin", "T02a-stats")
        check(code == 1 and "겹칩니다" in out, "진행 중인 노드와 같은 파일 → begin 거부", out)
    finally:
        p.close()
    g = copy.deepcopy(F.GRAPH)
    g["fields"]["side.note"] = {"type": "enum", "values": ["ok"], "owner": "H08-side"}
    g["nodes"].append({"kind": "node", "id": "H08-side", "type": "HUMAN", "reqs": ["REQ-F1"], "requires": ["rows exists"],
                       "writes": ["side.note"], "human": {"actions": ["ok"], "field": "side.note"}})
    p = Proj(graph=g)
    try:
        p.run("start", "--set", "input_path=data.csv")
        p.run("exec", "T01-load")
        p.run("wait", "H08-side", "--reason", "확인")
        code, out = p.run("next")
        check(code == 2 and "T02a-stats" in out and "진행해도 된다" in out, "사람 대기 중에도 관계없는 가지의 ready 를 보여 준다", out)
    finally:
        p.close()


def test_install_global():
    print("[설치 — 전역 (~/.claude/skills)]")
    u = tmp()
    env = {**os.environ, "USERPROFILE": str(u), "HOME": str(u), "PYTHONIOENCODING": "utf-8"}
    G = lambda *a: subprocess.run([sys.executable, str(HARNESS / "install.py"), "--global", *a], capture_output=True, env=env)  # noqa: E731
    try:
        r = G()
        home = HARNESS.parent.as_posix()
        sk = u / ".claude" / "skills" / "graph-run" / "SKILL.md"
        txt = sk.read_text(encoding="utf-8") if sk.exists() else ""
        check(r.returncode == 0 and f"python {home}/harness/run.py" in txt, "전역 스킬 — 스크립트를 설치 폴더 경로로", r.stdout.decode("utf-8", "replace"))
        check(f"{home}/AGENTS.md" in txt, "전역 스킬 — 규칙은 하네스 폴더의 AGENTS.md 를 읽는다")
        check(not (u / ".agents").exists() and not (u / ".claude" / "CLAUDE.md").exists(), "기본은 ~/.claude/skills 만 — 전역 CLAUDE.md 는 건드리지 않는다")
        check(G("--check").returncode == 0, "--global --check → 같다")
        other = u / ".claude" / "skills" / "req-intake"
        (other / ".harness.json").unlink()
        check(G().returncode == 1, "같은 이름의 다른 스킬이 있으면 덮어쓰지 않는다")
    finally:
        shutil.rmtree(u, ignore_errors=True)


def test_fable3():
    print("[3차 검증 반영]")
    import spec as SP
    files = ["web/"]
    check(not SP.contained("./", files) and not SP.contained("web/", files) and not SP.contained("web/../api/x.py", files)
          and SP.contained("web/a/b.js", files) and SP.contained("./web/x", files) and not SP.contained("api/x", files),
          "바뀐 파일 포함 판정 — 폴더 · `./` · `..` 보고는 거부, 안쪽 파일만 통과")
    g = copy.deepcopy(F.GRAPH)
    node(g, "T02a-stats").update(files=["out/a/../b.json"])
    code, rows = run_validate(graph=g)
    check(code == 1 and any(k.startswith("1") for k in bad_rows(rows)), "files 의 `..` → 1행 ERROR")
    d = tmp()
    try:
        (d / "AGENTS.md").write_text("내 규칙\n<!-- moonengineering:begin --> 를 설명하는 문장\n내 규칙 B\n", encoding="utf-8")
        r = subprocess.run([sys.executable, str(HARNESS / "install.py"), str(d)], capture_output=True)
        check(r.returncode != 0 and "내 규칙 B" in (d / "AGENTS.md").read_text(encoding="utf-8"),
              "AGENTS.md 의 표시 짝이 안 맞으면 install 이 멈춘다 (사용자 내용 보존)", r.stdout.decode("utf-8", "replace") + r.stderr.decode("utf-8", "replace"))
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_install():
    print("[설치 — 한 곳 설치 + 프로젝트 연결]")
    d = tmp()
    I = lambda *a: subprocess.run([sys.executable, str(HARNESS / "install.py"), str(d), *a], capture_output=True)  # noqa: E731
    try:
        (d / "AGENTS.md").write_text("# 우리 팀 규칙\n\n- 커밋 메시지는 한국어\n", encoding="utf-8")
        r = I()
        check(r.returncode == 0, "install → 연결 완료", r.stdout.decode("utf-8", "replace"))
        home = HARNESS.parent.as_posix()
        for t in (".agents/skills", ".claude/skills"):
            sk = (d / t / "graph-run" / "SKILL.md").read_text(encoding="utf-8")
            check(f"python {home}/harness/run.py" in sk and "python harness/" not in sk,
                  f"{t} 스킬 — 스크립트를 설치 폴더 절대 경로로 부른다")
        ag = (d / "AGENTS.md").read_text(encoding="utf-8")
        check("커밋 메시지는 한국어" in ag and "moonengineering:begin" in ag and f"{home}/templates/ASK.md" in ag,
              "AGENTS.md — 원래 내용은 그대로 · 하네스 규칙은 표시된 블록으로")
        check("@AGENTS.md" in (d / "CLAUDE.md").read_text(encoding="utf-8"), "CLAUDE.md 에 @AGENTS.md")
        check(json.loads((d / ".harness.json").read_text(encoding="utf-8"))["home"] == home, ".harness.json 에 설치 폴더 기록")
        check(I("--check").returncode == 0, "--check → 같다")
        I()
        check((d / "AGENTS.md").read_text(encoding="utf-8").count("moonengineering:begin") == 1
              and (d / "CLAUDE.md").read_text(encoding="utf-8").count("@AGENTS.md") == 1, "다시 install 해도 블록 · 줄이 늘지 않는다")
        (d / ".agents" / "skills" / "req-intake" / "SKILL.md").write_text("고쳐 버림", encoding="utf-8")
        check(I("--check").returncode == 1, "프로젝트 사본을 손대면 --check 가 잡는다")
        code = subprocess.run([sys.executable, str(HARNESS / "validate.py"), "--project", str(d)], capture_output=True).returncode
        check(code == 2, "연결된 빈 프로젝트에서 설치 폴더의 validate 가 돈다 (요구사항 없음 → SHORT)")
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_first_error():
    print("[run · 증상 구분]")
    import run as R
    d = tmp()
    try:
        a, b = d / "a.log", d / "b.log"
        a.write_text("$ x\nTraceback (most recent call last):\nUnicodeDecodeError: 'utf-8' codec\n", encoding="utf-8")
        b.write_text("$ x\nFAIL: test_add\nAssertionError: '\\r\\n' != '\\n'\n", encoding="utf-8")
        ea, eb = R.first_error(a), R.first_error(b)
        check("UnicodeDecodeError" in ea and "FAIL: test_add" in eb and ea != eb,
              "같은 exit 1 이라도 첫 오류 줄이 다르면 다른 증상", f"{ea!r} / {eb!r}")
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_portable():
    print("[범용 — 도구 · OS]")
    import run as R
    import sync_skills as SS
    repo = HARNESS.parent
    code = subprocess.run([sys.executable, str(HARNESS / "sync_skills.py"), "--root", str(repo), "--check"],
                          capture_output=True).returncode
    check(code == 0, ".agents/skills 정본이 표준 frontmatter 만 쓰고 .claude/skills 복사본과 같다 (sync_skills --check)")
    d = tmp()
    try:
        sk = d / ".agents" / "skills" / "bad-skill"
        sk.mkdir(parents=True)
        (sk / "SKILL.md").write_text("---\nname: bad-skill\ndescription: x\nuser-invocable: true\n---\n", encoding="utf-8")
        check(any("표준 밖의 키" in e for e in SS.check_standard(d / ".agents" / "skills")), "도구 전용 frontmatter 키 → 위반")
        (sk / "SKILL.md").write_text("---\nname: other\ndescription: x\n---\n", encoding="utf-8")
        check(any("폴더 이름" in e for e in SS.check_standard(d / ".agents" / "skills")), "name 과 폴더 이름이 다르면 → 위반")
    finally:
        shutil.rmtree(d, ignore_errors=True)
    e = R.expand("{python} -m x")
    check("{python}" not in e and Path(e.split(" -m")[0].strip('"')).name.lower().startswith("python"),
          "{python} → 하네스를 돌리는 파이썬 실행 파일", e)
    g = copy.deepcopy(F.GRAPH)
    node(g, "T01-load")["gate"]["cmd"] = "python -c exit(0)"
    code, rows = run_validate(graph=g)
    warns = [m for items in rows.values() for lv, m in items if lv == "WARN"]
    check(code == 0 and any("{python}" in m for m in warns), "cmd 가 'python' 으로 시작하면 WARN (실패는 아님)", str(warns))


def gr(prog: Path, *args) -> tuple[int, str]:
    r = subprocess.run([sys.executable, str(prog / "graphrt.py"), *args], capture_output=True)
    return r.returncode, (r.stdout + r.stderr).decode("utf-8", errors="replace")


def test_graphrt():
    print("[graphrt — 그래프로 도는 프로그램의 런타임]")
    import spec as S
    sys.path.insert(0, str(HARNESS / "runtime"))
    import graphrt as G
    vals = {"a": 1, "s": "x", "f": 0.4, "l": [1]}
    conds = ["a == 1", "a != 1", "a >= 1", "f < 0.5", "s == x", 's == "x"', "s in [x, y]", "a in [2, 3]",
             "a exists", "z exists", "z missing", "z == 1", "s > 1"]
    check(all(S.eval_cond(c, vals) == G.eval_cond(c, vals) for c in conds), "조건식이 하네스(spec.py)와 같다 — 개발 · 실행 문법 하나")
    demo = HARNESS.parent / "examples" / "graph-demo"
    check((demo / "graphrt.py").read_bytes() == (HARNESS / "runtime" / "graphrt.py").read_bytes(),
          "examples/graph-demo 의 graphrt.py 가 하네스 런타임과 같다 (복사본이 어긋나지 않음)")
    d = tmp()
    try:
        p = d / "demo"
        shutil.copytree(demo, p, ignore=shutil.ignore_patterns("runs", "__pycache__"))
        code, out = gr(p, "eval")
        check(code == 0 and "FAIL" not in out, "graph-demo 골든셋 전부 통과 (노드별 + e2e)", out)
        code, out = gr(p, "run", "--input", '{"q": "아무 말"}')
        rid = json.loads(out[out.index("{"):out.rindex("}") + 1])["run"] if "{" in out else ""
        check(code == 2 and '"waiting"' in out, "확신이 낮으면 HUMAN 노드에서 멈춘다 (exit 2)", out)
        code, out = gr(p, "resume", rid, "review", "--set", 'result="사람"')
        check(code == 0 and "사람" in out and '"done"' in out, "resume 으로 사람 답을 넣으면 이어서 끝난다", out)
        r = p / "nodes" / "route.py"
        r.write_text(r.read_text(encoding="utf-8").replace('"intent": "fact"', '"intent": "other"'), encoding="utf-8")
        code, out = gr(p, "eval", "route")
        check(code == 1 and "FAIL route" in out, "노드 하나를 망가뜨리면 그 노드의 골든셋이 잡는다", out)
        g = json.loads((p / "graph.json").read_text(encoding="utf-8"))
        bad = copy.deepcopy(g)
        bad["nodes"].append({"id": "ghost", "type": "CODE", "requires": ["nobody == 1"], "writes": ["q"]})
        bad["nodes"].append({"id": "x1", "type": "HUMAN", "requires": ["y2 exists"], "writes": ["x1v"]})
        bad["nodes"].append({"id": "y2", "type": "HUMAN", "requires": ["x1v exists"], "writes": ["y2"]})
        errs = G.check(p, bad)
        check(any("ghost.py" in e for e in errs) and any("nobody" in e for e in errs)
              and any("입력 필드" in e for e in errs) and any("순환" in e for e in errs),
              "check: 노드 파일 없음 · 아무도 안 쓰는 필드 · 입력 덮어쓰기 · 순환", str(errs))
        q = d / "clash"
        (q / "nodes").mkdir(parents=True)
        (q / "graph.json").write_text(json.dumps({"inputs": ["x"], "nodes": [
            {"id": "a", "type": "CODE", "requires": ["x exists"], "writes": ["y"]},
            {"id": "b", "type": "CODE", "requires": ["x exists"], "writes": ["y"]},
            {"id": "c", "type": "CODE", "requires": ["x exists"], "writes": ["w"]}]}), encoding="utf-8")
        for n, body in (("a", '{"y": 1}'), ("b", '{"y": 2}'), ("c", '{"zzz": 1}')):
            (q / "nodes" / f"{n}.py").write_text(f"def run(s):\n    return {body}\n", encoding="utf-8")
        st = G.fold(G.load_graph(q), G.start(q, G.load_graph(q), {"x": 1}, G.Store(None))[1].events())
        check(st["status"] == "failed" and "이미 쓴 필드" in (st.get("error") or ""), "한 Run 에서 두 노드가 같은 필드를 쓰면 실패", str(st))
        (q / "nodes" / "b.py").write_text("def run(s):\n    return {}\n", encoding="utf-8")
        st = G.fold(G.load_graph(q), G.start(q, G.load_graph(q), {"x": 1}, G.Store(None))[1].events())
        check(st["status"] == "failed" and "쓰기로 하지 않은 필드" in (st.get("error") or ""), "writes 밖의 필드를 쓰면 실패", str(st))
        code, out = gr(HARNESS / "runtime", "init", str(d / "new"))
        code2, out2 = gr(d / "new", "eval")
        check(code == 0 and code2 == 0, "init 뼈대가 바로 eval 을 통과한다", out + out2)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_blueprint():
    print("[만드는 법 카드 · 체크리스트 모드 (S · M)]")
    d = tmp()
    try:
        (d / "specs").mkdir()
        (d / "specs" / "REQUIREMENTS.md").write_text(F.block(F.REQUIREMENTS), encoding="utf-8")  # scale M
        steps = [{"id": "S1", "do": "계약", "check": "x", "reqs": [q["id"] for q in F.REQUIREMENTS["reqs"]]}]
        (d / "specs" / "CHECKLIST.md").write_text(F.block({"kind": "checklist", "steps": steps}), encoding="utf-8")
        r = V.validate(d)
        check(r.code() == 0 and "6 추적성" in r.rows, "M 규모도 GRAPH 없이 CHECKLIST 로 PASS (개발 그래프는 L 에서만)", str(r.rows))

        def bp(**kw):
            b = {"kind": "blueprint", "shape": "graph", "verify": ["golden"],
                 "criteria": {"stages": True, "nondeterministic": True, "repeated": True, "branching": False, "resumable": False}}
            b.update(kw)
            (d / "specs" / "BLUEPRINT.md").write_text(F.block(b), encoding="utf-8")
            r = V.validate(d)
            return r.code(), [lv for lv, _ in r.rows.get("9 만드는 법", [])]
        check(bp() == (0, []), "규칙 3/5 + graph + 검증 방법 → 9행 OK")
        two = {"stages": True, "nondeterministic": True, "repeated": False, "branching": False, "resumable": False}
        check(bp(criteria=two) == (0, ["WARN"]), "규칙 2/5 인데 graph → WARN (실패는 아님 · 이유를 적게)")
        check(bp(shape="cli") == (0, ["WARN"]), "규칙 3/5 인데 graph 아님 → WARN")
        check(bp(verify=[])[0] == 1 and bp(shape="spaceship")[0] == 1, "검증 방법 없음 · 모르는 구조 → ERROR")
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_metric():
    print("[metric — 메트릭 게이트]")
    d = tmp()
    try:
        (d / "m.json").write_text(json.dumps({"e2e": {"accuracy": 0.8}, "p95_ms": 120}), encoding="utf-8")

        def mt(*args):
            return subprocess.run([sys.executable, str(HARNESS / "metric.py"), str(d / "m.json"), *args], capture_output=True, cwd=d).returncode
        check(mt("e2e.accuracy>=0.75", "p95_ms<=200") == 0, "조건을 모두 넘으면 exit 0")
        check(mt("e2e.accuracy>=0.9") == 1 and mt("nope>=1") == 1 and mt("e2e.accuracy=>1") == 1, "미달 · 없는 지표 · 깨진 식 → exit 1")
        (d / "b.json").write_text(json.dumps({"metrics": {"e2e": {"accuracy": 0.95}, "p95_ms": 100}}), encoding="utf-8")
        check(mt("e2e.accuracy>=0.75", "--baseline", str(d / "b.json")) == 1, "임계값은 넘어도 기준선보다 나빠지면 회귀 → exit 1")
        check(mt("e2e.accuracy>=0.75", "--baseline", str(d / "b.json"), "--tol", "0.2") == 0, "허용치(tol) 안이면 통과")
        check(mt("p95_ms<=200", "--baseline", str(d / "b.json"), "--tol", "10") == 1, "작을수록 좋은 지표(<=)는 커지면 회귀")
        check(mt("--save-baseline", str(d / "b2.json")) == 1, "기준선 갱신은 --note(이유) 없이는 거부")
        check(mt("--save-baseline", str(d / "b2.json"), "--note", "x") == 0 and (d / "memory" / "DECISIONS.md").exists(),
              "기준선 갱신은 memory/DECISIONS.md 에 남는다")
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main() -> int:
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass
    test_validate()
    test_happy_path()
    test_retry_and_reset()
    test_budget()
    test_stop()
    test_render()
    test_first_error()
    test_portable()
    test_robust()
    test_tools_field()
    test_parallel_files()
    test_runtime_guards()
    test_install()
    test_fable3()
    test_install_global()
    test_graphrt()
    test_blueprint()
    test_metric()
    fails =[n for ok, n in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(fails)}/{len(RESULTS)} 통과")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
