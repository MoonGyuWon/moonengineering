"""구조 검사 — 스펙이 상태값만으로 돌 수 있는 모양인지 본다.

    python harness/validate.py [--project DIR]

종료 코드  0 PASS · 1 ERROR(스펙이 깨짐 — 사람에게) · 2 SHORT(아직 덜 됨 — 요구사항 미확정 등)

검사행
  1 스펙 필수 칸            5 순환 (requires 만으로 도는 순환 = 교착 · rerun_on 은 max_runs 필수)
  2 참조 · 도달 가능성       6 추적성 (REQ → 노드 + 게이트)
  3 조건식                  7 요구사항 확정 (미결 질문 0 · 수용 기준 · APPROVED)
  4 필드 주인 · reducer      8 확장 (JUDGE · HUMAN · 부작용 승인 · 병렬 파일 충돌 · 계층 이름)
                            9 영역 (areas · 노드 files 가 영역 폴더 안)   ※ gate.cwd · files 의 `..` 는 1행
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import spec as S  # noqa: E402

REDUCERS = ("append", "replace")  # + "merge_by_key:<키>"
CAUSES = ("transient", "input", "contract_violation", "structural")
NUMERIC = ("int", "float")


class Report:
    def __init__(self):
        self.rows: dict[str, list[tuple[str, str]]] = {}

    def add(self, row: str, level: str, msg: str):
        self.rows.setdefault(row, []).append((level, msg))

    def ok(self, row: str):
        self.rows.setdefault(row, [])

    def code(self) -> int:
        levels = [lv for items in self.rows.values() for lv, _ in items]
        if "ERROR" in levels:
            return 1
        if "SHORT" in levels:
            return 2
        return 0

    def print(self):
        for row in sorted(self.rows):
            items = self.rows[row]
            errs = [i for i in items if i[0] in ("ERROR", "SHORT")]
            head = "OK" if not errs else max((i[0] for i in errs), key=lambda x: x == "ERROR")
            print(f"[{row}] {head}")
            for lv, msg in items:
                print(f"     {lv:5} {msg}")
        print("최종:", {0: "PASS", 1: "ERROR", 2: "SHORT"}[self.code()], f"(exit {self.code()})")


def check_requirements(spec: dict, r: Report):
    row = "7 요구사항 확정"
    req = spec["requirements"]
    r.ok(row)
    if not req:
        r.add(row, "SHORT", "specs/REQUIREMENTS.md 에 requirements 블록이 없습니다 — req-intake 부터")
        return
    if req.get("status") != "APPROVED":
        r.add(row, "SHORT", f"status 가 {req.get('status')!r} 입니다 — 사람이 승인하면 APPROVED")
    oq = req.get("open_questions") or []
    if oq:
        r.add(row, "SHORT", f"미결 질문 {len(oq)}개: " + " / ".join(map(str, oq[:3])))
    if not req.get("stakeholders"):
        r.add(row, "SHORT", "stakeholders 가 비어 있습니다")
    if not req.get("reqs"):
        r.add(row, "SHORT", "reqs 가 비어 있습니다")
    for q in req.get("reqs", []):
        if not str(q.get("acceptance", "")).strip():
            r.add(row, "SHORT", f"{q.get('id')}: 수용 기준(acceptance)이 없습니다")
    if req.get("scale") in ("M", "L") and "tools" not in req:
        r.add(row, "SHORT", "M/L 인데 tools(도구 선정 · req-intake 3-b)가 없습니다 — 고를 것이 없으면 표준 라이브러리로 정했다고 적는다")
    for t in req.get("tools", []):
        if t.get("status") != "decided" or not str(t.get("choice", "")).strip():
            r.add(row, "SHORT", f"도구 '{t.get('need')}': 아직 정하지 않았습니다 (status decided · choice 필요)")
        elif not str(t.get("source", "")).strip():
            r.add(row, "SHORT", f"도구 '{t.get('need')}': 근거(source — 웹 확인 날짜·URL 또는 '알고 있는 정보 (확인 안 함)')가 없습니다")
    if req.get("scale") not in ("S", "M", "L"):
        r.add(row, "ERROR", f"scale 은 S · M · L 중 하나여야 합니다 (지금 {req.get('scale')!r})")


def check_checklist(spec: dict, r: Report):
    row = "1 스펙 필수 칸"
    r.ok(row)
    cl = spec["checklist"]
    if not cl:
        r.add(row, "SHORT", "S 규모인데 specs/CHECKLIST.md 의 checklist 블록이 없습니다")
        return
    ids = {q["id"] for q in (spec["requirements"] or {}).get("reqs", [])}
    covered = set()
    for i, step in enumerate(cl.get("steps", []), 1):
        for k in ("id", "do", "check", "reqs"):
            if k not in step:
                r.add(row, "ERROR", f"단계 {i}: '{k}' 칸이 없습니다")
        covered |= set(step.get("reqs", []))
    for q in sorted(ids - covered):
        r.add("6 추적성", "ERROR", f"{q} 를 맡은 단계가 없습니다")
    r.ok("6 추적성")


def check_graph(spec: dict, r: Report):
    g = spec["graph"]
    nodes = spec["nodes"]
    for row in ("1 스펙 필수 칸", "2 참조 · 도달", "3 조건식", "4 필드 주인", "5 순환", "6 추적성", "8 확장", "9 영역"):
        r.ok(row)
    if not g:
        r.add("1 스펙 필수 칸", "SHORT", "specs/GRAPH.md 에 graph 블록이 없습니다 — graph-plan 부터")
        return
    fdefs = S.fields(spec)
    ids = [n.get("id") for n in nodes]
    by_id = {n.get("id"): n for n in nodes}

    # 1 필수 칸
    row = "1 스펙 필수 칸"
    if not nodes:
        r.add(row, "SHORT", "노드가 없습니다")
    for k in ("graph_version", "fields", "done_when"):
        if k not in g:
            r.add(row, "ERROR", f"graph 블록에 '{k}' 가 없습니다")
    dup = {i for i in ids if ids.count(i) > 1}
    for i in dup:
        r.add(row, "ERROR", f"노드 id 가 겹칩니다: {i}")
    for n in nodes:
        nid = n.get("id", "?")
        for k in ("id", "type", "requires", "writes", "reqs"):
            if k not in n:
                r.add(row, "ERROR", f"{nid}: '{k}' 칸이 없습니다")
        t = n.get("type")
        if t not in S.NODE_TYPES:
            r.add(row, "ERROR", f"{nid}: type 은 {S.NODE_TYPES} 중 하나 (지금 {t!r})")
        if t == "CODE" and not n.get("cmd"):
            r.add(row, "ERROR", f"{nid}: CODE 노드는 cmd 가 필요합니다")
        if t in ("CODE", "AGENT") and not (n.get("gate") or {}).get("cmd"):
            r.add(row, "ERROR", f"{nid}: {t} 노드는 값으로 판정하는 gate.cmd 가 필요합니다")
        if t == "HUMAN" and not ((n.get("human") or {}).get("actions") and (n.get("human") or {}).get("field")):
            r.add(row, "ERROR", f"{nid}: HUMAN 노드는 human.actions · human.field 가 필요합니다")
        if t == "JUDGE" and not (n.get("judge") or {}).get("questions"):
            r.add(row, "ERROR", f"{nid}: JUDGE 노드는 judge.questions 가 필요합니다")
        for k, c in (("cmd", n.get("cmd")), ("gate.cmd", (n.get("gate") or {}).get("cmd"))):
            if isinstance(c, str) and re.match(r"^\s*python3?\s", c):
                r.add(row, "WARN", f"{nid}: {k} 가 'python' 으로 시작합니다 — OS 마다 python/python3 이 다르니 {{python}} 을 권장")
        rt = n.get("retry") or {}
        bad = [c for c in rt.get("on", []) if c not in CAUSES]
        if bad or not isinstance(rt.get("max", 0), int) or not 0 <= rt.get("max", 0) <= 3:
            r.add(row, "ERROR", f"{nid}: retry 는 max 0~3 · on ⊆ {CAUSES} (지금 {rt})")
        te = n.get("transient_exit", [])
        if not isinstance(te, list) or not all(isinstance(x, int) and not isinstance(x, bool) for x in te):
            r.add(row, "ERROR", f"{nid}: transient_exit 는 정수 목록입니다 (지금 {te!r})")
        dd = [f for f in n.get("files", []) if S.has_dotdot(f)]
        if dd:
            r.add(row, "ERROR", f"{nid}: files 에 `..` 를 쓰지 않습니다 {dd} — 프로젝트 안 경로만")
        cwd = (n.get("gate") or {}).get("cwd")
        if cwd is not None and (not isinstance(cwd, str) or Path(cwd).is_absolute() or ".." in Path(cwd).parts):
            r.add(row, "ERROR", f"{nid}: gate.cwd 는 프로젝트 안의 상대 경로입니다 (지금 {cwd!r})")
        gp = (n.get("gate") or {}).get("pass", "exit==0")
        if n.get("gate") and not re.fullmatch(r"exit==\d+", str(gp)):
            r.add(row, "ERROR", f"{nid}: gate.pass 는 'exit==<숫자>' 형식입니다 (지금 {gp!r})")
    for f, d in fdefs.items():
        if d.get("type") not in S.FIELD_TYPES:
            r.add(row, "ERROR", f"필드 {f}: type 은 {S.FIELD_TYPES} 중 하나")
        if d.get("type") == "enum" and not d.get("values"):
            r.add(row, "ERROR", f"필드 {f}: enum 은 values 가 필요합니다")

    # 4 필드 주인 · reducer
    row = "4 필드 주인"
    for f, d in fdefs.items():
        os_ = S.owners(d)
        if not os_:
            r.add(row, "ERROR", f"필드 {f}: owner 가 없습니다 (입력이면 \"owner\": \"input\")")
        for o in os_:
            if o != S.INPUT_OWNER and o not in by_id:
                r.add(row, "ERROR", f"필드 {f}: owner {o} 라는 노드가 없습니다")
        red = d.get("reducer")
        if len(os_) > 1 and not red:
            r.add(row, "ERROR", f"필드 {f}: 쓰는 노드가 {len(os_)}개({', '.join(os_)}) — reducer 를 선언해야 합니다")
        if red and not (red in REDUCERS or red.startswith("merge_by_key:")):
            r.add(row, "ERROR", f"필드 {f}: 모르는 reducer {red!r} (append · replace · merge_by_key:<키>)")
    for n in nodes:
        for f in n.get("writes", []):
            if f not in fdefs:
                r.add(row, "ERROR", f"{n.get('id')}: 선언되지 않은 필드 {f} 를 씁니다")
            elif n.get("id") not in S.owners(fdefs[f]):
                r.add(row, "ERROR", f"{n.get('id')}: 필드 {f} 의 주인이 아닙니다 (주인: {S.owners(fdefs[f])})")
    for f, d in fdefs.items():
        for o in S.owners(d):
            if o in by_id and f not in by_id[o].get("writes", []):
                r.add(row, "ERROR", f"필드 {f}: 주인 {o} 의 writes 에 없습니다")

    # 3 조건식
    row = "3 조건식"
    conds = [(n.get("id"), c) for n in nodes for c in n.get("requires", [])]
    conds += [("done_when", c) for c in g.get("done_when", [])]
    conds += [("stop_when", c) for c in g.get("stop_when", [])]
    for where, c in conds:
        try:
            f, op, lit = S.parse_cond(c)
        except S.SpecError as e:
            r.add(row, "ERROR", f"{where}: {e}")
            continue
        d = fdefs.get(f)
        if d is None:
            r.add(row, "ERROR", f"{where}: '{c}' — 선언되지 않은 필드 {f}")
            continue
        if d.get("free_text"):
            r.add(row, "ERROR", f"{where}: '{c}' — 자유 문장 필드 {f} 로는 분기하지 않습니다")
        t = d.get("type")
        if t == "enum" and op in ("==", "!=", "in"):
            vals = lit if op == "in" else [lit]
            bad = [v for v in vals if v not in d.get("values", [])]
            if bad:
                r.add(row, "ERROR", f"{where}: '{c}' — {bad} 는 {f} 의 값이 아닙니다 {d.get('values')}")
        if op in (">=", "<=", ">", "<") and t not in NUMERIC:
            r.add(row, "ERROR", f"{where}: '{c}' — 크기 비교는 수 필드에만 ({f} 는 {t})")
    for n in nodes:
        for f in n.get("rerun_on", []):
            if f not in fdefs:
                r.add(row, "ERROR", f"{n.get('id')}: rerun_on 의 {f} 가 선언되지 않았습니다")

    # 2 참조 · 도달 — 값은 무시하고 "그 필드를 쓸 수 있는 노드가 돌 수 있나"만 본다
    row = "2 참조 · 도달"
    avail = {f for f, d in fdefs.items() if S.INPUT_OWNER in S.owners(d)}
    runnable: set[str] = set()
    changed = True
    while changed:
        changed = False
        for n in nodes:
            nid = n.get("id")
            if nid in runnable:
                continue
            try:
                reads = S.node_reads(n)
            except S.SpecError:
                continue
            if all(f in avail for f in reads):
                runnable.add(nid)
                avail |= set(n.get("writes", []))
                changed = True
    for n in nodes:
        if n.get("id") not in runnable:
            try:
                missing = [f for f in S.node_reads(n) if f not in avail]
            except S.SpecError:
                missing = ["(조건식 오류)"]
            r.add(row, "ERROR", f"{n.get('id')}: 영영 준비되지 못합니다 — 아무도 쓰지 않는 필드 {missing}")
    for c in g.get("done_when", []):
        try:
            f = S.parse_cond(c)[0]
        except S.SpecError:
            continue
        if f not in avail:
            r.add(row, "ERROR", f"done_when '{c}' — {f} 를 쓸 수 있는 노드가 없습니다 (끝나지 않는 그래프)")

    # 5 순환
    row = "5 순환"
    req_edges = [e for e in S.derived_edges(spec) if e["kind"] == "requires" and e["source"] in by_id]
    adj: dict[str, set[str]] = {}
    for e in req_edges:
        adj.setdefault(e["source"], set()).add(e["target"])
    cyc = _find_cycle(adj)
    if cyc:
        r.add(row, "ERROR", "requires 만으로 도는 순환은 교착입니다 (서로를 기다림): " + " → ".join(cyc))
    for n in nodes:
        if n.get("rerun_on"):
            mr = n.get("max_runs")
            if not isinstance(mr, int) or not 1 <= mr <= 5:
                r.add(row, "ERROR", f"{n.get('id')}: rerun_on 이 있으면 max_runs(1~5) 가 필요합니다 — 상한 없는 순환 금지")

    # 6 추적성
    row = "6 추적성"
    req_ids = {q["id"] for q in (spec["requirements"] or {}).get("reqs", [])}
    covered = {}
    for n in nodes:
        for q in n.get("reqs", []):
            if req_ids and q not in req_ids:
                r.add(row, "ERROR", f"{n.get('id')}: 없는 요구사항 {q} 를 가리킵니다")
            verified = bool((n.get("gate") or {}).get("cmd")) or n.get("type") in ("HUMAN", "JUDGE")
            covered[q] = covered.get(q, False) or verified
    for q in sorted(req_ids):
        if q not in covered:
            r.add(row, "ERROR", f"{q} 를 맡은 노드가 없습니다")
        elif not covered[q]:
            r.add(row, "ERROR", f"{q} 를 판정하는 게이트가 없습니다")

    # 8 확장
    row = "8 확장"
    for n in nodes:
        nid = n.get("id")
        if n.get("type") == "HUMAN":
            h = n.get("human") or {}
            d = fdefs.get(h.get("field"), {})
            if d.get("type") != "enum" or sorted(d.get("values", [])) != sorted(h.get("actions", [])):
                r.add(row, "ERROR", f"{nid}: human.field 는 values == actions 인 enum 이어야 합니다")
            if not set(h.get("approve", [])) <= set(h.get("actions", [])):
                r.add(row, "ERROR", f"{nid}: human.approve {h.get('approve')} 는 actions 의 일부여야 합니다")
        if n.get("type") == "JUDGE":
            j = n.get("judge") or {}
            auto = j.get("auto")
            if not isinstance(auto, (int, float)) or not 0 < auto <= 1:
                r.add(row, "ERROR", f"{nid}: judge.auto(자동 진행 신뢰도 임계값)는 0 < x ≤ 1")
            for q in j.get("questions", []):
                qt, qf = q.get("type"), q.get("field")
                d = fdefs.get(qf, {})
                if qf not in n.get("writes", []):
                    r.add(row, "ERROR", f"{nid}: 질문 {q.get('name')} 의 field {qf} 가 writes 에 없습니다")
                if qt == "choice":
                    opts = q.get("options") or []
                    if len(opts) < 2 or d.get("type") != "enum" or sorted(opts) != sorted(d.get("values", [])):
                        r.add(row, "ERROR", f"{nid}: choice {q.get('name')} — options 2개 이상, field 는 같은 values 의 enum")
                elif qt == "score":
                    sc = q.get("scale") or []
                    if len(sc) != 2 or not 2 <= sc[1] - sc[0] + 1 <= 10 or d.get("type") not in NUMERIC:
                        r.add(row, "ERROR", f"{nid}: score {q.get('name')} — scale [최소, 최대] 2~10단계, field 는 수")
                elif qt == "noul":
                    if d.get("type") != "float":
                        r.add(row, "ERROR", f"{nid}: noul {q.get('name')} — field 는 float(예일 확률)")
                else:
                    r.add(row, "ERROR", f"{nid}: 질문 타입은 choice · score · noul (지금 {qt!r})")
        if n.get("side_effect"):
            # 승인은 "사람이 그 값을 골랐다" 여야 한다 — `exists` · `!=` · `in` 이면 거절해도 지나간다
            approve_of = {(m.get("human") or {}).get("field"): set((m.get("human") or {}).get("approve", []))
                          for m in nodes if m.get("type") == "HUMAN"}
            approved, loose = False, []
            for c in n.get("requires", []):
                try:
                    f, op, lit = S.parse_cond(c)
                except S.SpecError:
                    continue
                if f in approve_of:
                    if op == "==" and lit in approve_of[f]:
                        approved = True
                    else:
                        loose.append(c)
            if loose:
                r.add(row, "ERROR", f"{nid}: 부작용 노드의 승인 조건 {loose} — 승인 필드는 `== <human.approve 의 값>` 으로만 건다 (거절해도 지나간다)")
            if not approved:
                r.add(row, "ERROR", f"{nid}: 부작용({n['side_effect'].get('class')}) 노드는 requires 에 `<HUMAN 필드> == <승인 값>` 이 필요합니다 (승인 값은 HUMAN 노드의 human.approve)")
            if not n["side_effect"].get("idempotency_key"):
                r.add(row, "ERROR", f"{nid}: 부작용 노드는 idempotency_key 가 필요합니다")
    # 병렬 파일 충돌: 순서가 보장되지 않는(= 같은 웨이브에 설 수 있는) 두 노드가 겹치는 경로를 쓰면 안 된다.
    # 순서를 보장하는 간선만 센다 — `missing` 조건과 주인이 여럿인 필드(아무 주인 하나만 써도 참)는 순서가 아니다
    order: dict[str, set[str]] = {}
    for e in req_edges:
        try:
            f, op, _ = S.parse_cond(e["label"])
        except S.SpecError:
            continue
        if op == "missing" or len(S.owners(fdefs.get(f, {}))) > 1:
            continue
        order.setdefault(e["source"], set()).add(e["target"])
    reach = {nid: _reachable(order, nid) for nid in by_id}
    nl = [n for n in nodes if n.get("files")]
    for i, a in enumerate(nl):
        for b in nl[i + 1:]:
            if b["id"] in reach[a["id"]] or a["id"] in reach[b["id"]]:
                continue
            both = sorted({f"{x} ↔ {y}" for x in a["files"] for y in b["files"] if S.paths_overlap(x, y)})
            if both:
                r.add(row, "ERROR", f"{a['id']} · {b['id']}: 같은 웨이브에 설 수 있는데 겹치는 경로를 씁니다 {both}")
    # 계층 이름
    layers = g.get("layers") or []
    for n in nodes:
        if layers and n.get("layer") and n["layer"] not in layers:
            r.add(row, "ERROR", f"{n.get('id')}: layer {n['layer']!r} 가 graph.layers {layers} 에 없습니다 (그림에서 빠진다)")

    # 9 영역 — 폴더로 나눈 작업 영역 (frontend/ · backend/ · packages/<x>/ …)
    row = "9 영역"
    areas = g.get("areas") or {}
    roots = {}
    for name, a in areas.items():
        root = S.norm_path((a or {}).get("root", ""))
        if S.has_dotdot((a or {}).get("root", "")):
            r.add(row, "ERROR", f"영역 {name}: root 에 `..` 를 쓰지 않습니다 (지금 {(a or {}).get('root')!r})")
            continue
        if not root or not root.endswith("/"):
            r.add(row, "ERROR", f"영역 {name}: root 는 폴더('web/' 처럼 / 로 끝남)여야 합니다 (지금 {(a or {}).get('root')!r})")
            continue
        for other, oroot in roots.items():
            if S.paths_overlap(root, oroot):
                r.add(row, "ERROR", f"영역 {name}({root}) · {other}({oroot}): 영역 폴더가 겹칩니다")
        roots[name] = root
    for n in nodes:
        ar = n.get("area")
        if ar is None:
            continue  # 영역 없는 노드 = 계약 · 통합 노드 — 영역을 가로질러 고칠 수 있다
        if ar not in areas:
            r.add(row, "ERROR", f"{n.get('id')}: area {ar!r} 가 graph.areas 에 없습니다 ({sorted(areas)})")
            continue
        if ar not in roots:
            continue
        if not n.get("files"):
            r.add(row, "ERROR", f"{n.get('id')}: 영역 노드는 files 가 필요합니다 (영역 폴더 안의 경로)")
        outside = [f for f in n.get("files", []) if not S.under(f, roots[ar])]
        if outside:
            r.add(row, "ERROR", f"{n.get('id')}: 영역 {ar}({roots[ar]}) 밖을 고칩니다 {outside} — 영역을 가로지르는 일은 계약 · 통합 노드(area 없음)가 한다")


def _find_cycle(adj: dict[str, set[str]]) -> list[str] | None:
    color: dict[str, int] = {}
    stack: list[str] = []

    def dfs(u):
        color[u] = 1
        stack.append(u)
        for v in sorted(adj.get(u, ())):
            if color.get(v) == 1:
                return stack[stack.index(v):] + [v]
            if not color.get(v):
                got = dfs(v)
                if got:
                    return got
        stack.pop()
        color[u] = 2
        return None

    for u in sorted(adj):
        if not color.get(u):
            got = dfs(u)
            if got:
                return got
    return None


def _reachable(adj, start) -> set[str]:
    seen, todo = set(), [start]
    while todo:
        for v in adj.get(todo.pop(), ()):
            if v not in seen:
                seen.add(v)
                todo.append(v)
    return seen


def validate(root: Path) -> Report:
    r = Report()
    try:
        spec = S.load(root)
    except S.SpecError as e:
        r.add("1 스펙 필수 칸", "ERROR", str(e))
        return r
    check_requirements(spec, r)
    scale = (spec["requirements"] or {}).get("scale")
    if scale == "S":
        check_checklist(spec, r)
    else:
        check_graph(spec, r)
    return r


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", help="하네스를 쓰는 프로젝트 폴더 (기본: 현재 폴더 · HARNESS_PROJECT)")
    a = ap.parse_args(argv)
    r = validate(S.project_dir(a.project))
    r.print()
    return r.code()


if __name__ == "__main__":
    sys.exit(main())
