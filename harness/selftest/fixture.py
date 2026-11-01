"""셀프테스트용 정상 프로젝트 — 하네스의 모든 모양을 한 번씩 쓴다.

    T01-load ─▶ T02a-stats ─┐                     (병렬 웨이브: T02a · T02b)
             └▶ T02b-stats ─┴▶ C03-check ─▶ H06-approve(HUMAN) ─▶ T07-publish(부작용)
    X09-flaky (input_path == flaky 일 때만 · 일시적 오류 재시도)
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

PY = "{python}"

REQUIREMENTS = {
    "kind": "requirements", "status": "APPROVED", "scale": "M",
    "goal": "CSV 를 읽어 통계를 내고, 사람이 승인하면 보고서를 쓴다",
    "stakeholders": [{"id": "SH1", "role": "분석가", "success": "보고서가 승인된다"}],
    "reqs": [
        {"id": "REQ-F1", "text": "CSV 를 읽는다", "stakeholders": ["SH1"], "acceptance": "rows 길이 ≥ 1", "verify": "code"},
        {"id": "REQ-F2", "text": "통계 두 종류", "stakeholders": ["SH1"], "acceptance": "stats_a · stats_b 존재", "verify": "code"},
        {"id": "REQ-N1", "text": "인코딩이 깨지지 않는다", "stakeholders": ["SH1"], "acceptance": "check.verdict == pass", "verify": "code"},
        {"id": "REQ-F3", "text": "사람 승인 후 발행", "stakeholders": ["SH1"], "acceptance": "report.status == written", "verify": "human"},
    ],
    "open_questions": [], "assumptions": [],
    "tools": [{"need": "CSV 읽기", "choice": "csv (표준 라이브러리)", "status": "decided", "source": "알고 있는 정보 (확인 안 함)"}],
}


EMITS = {"T01": {"rows": [1, 2, 3]}, "T02a": {"stats_a": {"sum": 6}}, "T02b": {"stats_b": {"n": 3}},
         "C03": {"check.verdict": "pass"}, "T07": {"report.status": "written"}}
OK = f"{PY} -c exit(0)"


def _w(key: str) -> str:
    """HARNESS_WRITES 줄을 찍는 명령. Windows cmd 의 따옴표 문제를 피하려고 값은 tools/emit.py 안에 둔다."""
    return f"{PY} tools/emit.py {key}"


GRAPH = {
    "kind": "graph",
    "budget": {"max_attempts_total": 40},
    "done_when": ["report.status == written"],
    "stop_when": ["approval.action == stop"],
    "fields": {
        "input_path": {"type": "str", "owner": "input"},
        "rows": {"type": "list", "owner": "T01-load"},
        "stats_a": {"type": "dict", "owner": "T02a-stats"},
        "stats_b": {"type": "dict", "owner": "T02b-stats"},
        "check.verdict": {"type": "enum", "values": ["pass", "fail"], "owner": "C03-check"},
        "approval.action": {"type": "enum", "values": ["publish", "stop"], "owner": "H06-approve"},
        "approval.note": {"type": "str", "owner": "H06-approve", "free_text": True},
        "report.status": {"type": "enum", "values": ["written"], "owner": "T07-publish"},
        "flaky.done": {"type": "bool", "owner": "X09-flaky"},
    },
    "nodes": [
        {"kind": "node", "id": "T01-load", "type": "CODE", "reqs": ["REQ-F1"],
         "requires": ["input_path exists"], "writes": ["rows"],
         "cmd": _w("T01"), "gate": {"cmd": OK, "pass": "exit==0"}},
        {"kind": "node", "id": "T02a-stats", "type": "CODE", "reqs": ["REQ-F2"],
         "requires": ["rows exists"], "writes": ["stats_a"], "files": ["out/a.json"],
         "cmd": _w("T02a"), "gate": {"cmd": OK}},
        {"kind": "node", "id": "T02b-stats", "type": "CODE", "reqs": ["REQ-F2"],
         "requires": ["rows exists"], "writes": ["stats_b"], "files": ["out/b.json"],
         "cmd": _w("T02b"), "gate": {"cmd": OK}},
        {"kind": "node", "id": "C03-check", "type": "CODE", "reqs": ["REQ-N1"],
         "requires": ["stats_a exists", "stats_b exists"], "writes": ["check.verdict"],
         "cmd": _w("C03"), "gate": {"cmd": OK}},
        {"kind": "node", "id": "H06-approve", "type": "HUMAN", "reqs": ["REQ-F3"],
         "requires": ["check.verdict == pass"], "writes": ["approval.action", "approval.note"],
         "human": {"actions": ["publish", "stop"], "approve": ["publish"], "field": "approval.action", "note_field": "approval.note"}},
        {"kind": "node", "id": "T07-publish", "type": "CODE", "reqs": ["REQ-F3"],
         "requires": ["approval.action == publish"], "writes": ["report.status"],
         "side_effect": {"class": "external_publish", "idempotency_key": "run_id+T07-publish"},
         "cmd": _w("T07"), "gate": {"cmd": OK}},
        {"kind": "node", "id": "X09-flaky", "type": "CODE", "reqs": ["REQ-F1"],
         "requires": ["input_path == flaky"], "writes": ["flaky.done"], "retry": {"max": 1, "on": ["transient"]}, "transient_exit": [3],
         "cmd": f"{PY} -c exit(3)", "gate": {"cmd": OK}},
    ],
}


def block(obj) -> str:
    return "```harness\n" + json.dumps(obj, ensure_ascii=False, indent=2) + "\n```\n"


def write(root: Path, req=None, graph=None, split_nodes=True):
    req = copy.deepcopy(REQUIREMENTS if req is None else req)
    graph = copy.deepcopy(GRAPH if graph is None else graph)
    (root / "specs" / "nodes").mkdir(parents=True, exist_ok=True)
    (root / "tools").mkdir(exist_ok=True)
    (root / "tools" / "emit.py").write_text(
        "import json, sys\nE = " + json.dumps(EMITS) + "\nprint('HARNESS_WRITES ' + json.dumps(E[sys.argv[1]]))\n",
        encoding="utf-8")
    (root / "specs" / "REQUIREMENTS.md").write_text("# 요구사항\n\n" + block(req), encoding="utf-8")
    nodes = graph.pop("nodes")
    if split_nodes:  # 절반은 노드 파일로, 절반은 GRAPH.md 안에 — 두 경로 모두 읽히는지 본다
        graph["nodes"] = nodes[: len(nodes) // 2]
        for n in nodes[len(nodes) // 2:]:
            (root / "specs" / "nodes" / f"{n['id']}.md").write_text(f"# {n['id']}\n\n" + block(n), encoding="utf-8")
    else:
        graph["nodes"] = nodes
    (root / "specs" / "GRAPH.md").write_text("# 그래프\n\n" + block(graph), encoding="utf-8")
