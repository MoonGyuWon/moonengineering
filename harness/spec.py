"""스펙 읽기 창구 — md 안의 ```harness 블록(JSON)이 정본이다.

프로젝트 폴더 구조 (하네스를 쓰는 쪽)
    specs/REQUIREMENTS.md     {"kind": "requirements", ...}
    specs/GRAPH.md            {"kind": "graph", ...}   상태 스키마 · 완료 조건 · 예산
    specs/nodes/*.md          {"kind": "node", ...}    노드 하나 = 파일 하나 (GRAPH.md 의 "nodes" 에 넣어도 된다)
    specs/CHECKLIST.md        S 규모(체크리스트 모드)에서만

조건식은 `field op value` 한 줄뿐이다. 코드는 스펙에 넣지 않는다.
    op: == != >= <= > < in   ·   단항: `field exists` · `field missing`
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

BLOCK_RE = re.compile(r"```harness\s*\n(.*?)\n```", re.S)

NODE_TYPES = ("CODE", "AGENT", "HUMAN", "JUDGE")
FIELD_TYPES = ("str", "int", "float", "bool", "list", "dict", "enum")
BINARY_OPS = ("==", "!=", ">=", "<=", ">", "<", " in ")
UNARY_OPS = ("exists", "missing")
INPUT_OWNER = "input"


class SpecError(Exception):
    pass


def project_dir(arg: str | None = None) -> Path:
    return Path(arg or os.environ.get("HARNESS_PROJECT") or ".").resolve()


def read_blocks(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    out = []
    for i, raw in enumerate(BLOCK_RE.findall(text), 1):
        try:
            out.append(json.loads(raw))
        except json.JSONDecodeError as e:
            raise SpecError(f"{path.name}: harness 블록 {i} 의 JSON 이 깨졌습니다 — {e}") from e
    return out


def load(root: Path) -> dict:
    """프로젝트 스펙 전체를 dict 하나로 읽는다. 없는 파일은 None."""
    specs = root / "specs"
    spec = {"root": root, "requirements": None, "graph": None, "nodes": [], "checklist": None, "sources": {}}
    for name, key in (("REQUIREMENTS.md", "requirements"), ("GRAPH.md", "graph"), ("CHECKLIST.md", "checklist")):
        p = specs / name
        if not p.exists():
            continue
        for b in read_blocks(p):
            if b.get("kind") == key:
                spec[key] = b
            elif b.get("kind") == "node":
                spec["nodes"].append(b)
                spec["sources"][b.get("id")] = p.relative_to(root).as_posix()
    if spec["graph"]:
        for n in spec["graph"].get("nodes", []):
            spec["nodes"].append(n)
            spec["sources"][n.get("id")] = "specs/GRAPH.md"
    nodes_dir = specs / "nodes"
    if nodes_dir.is_dir():
        for p in sorted(nodes_dir.glob("*.md")):
            for b in read_blocks(p):
                if b.get("kind") == "node":
                    spec["nodes"].append(b)
                    spec["sources"][b.get("id")] = p.relative_to(root).as_posix()
    return spec


def fields(spec: dict) -> dict:
    return (spec.get("graph") or {}).get("fields", {})


def owners(fdef: dict) -> list[str]:
    if "owners" in fdef:
        return list(fdef["owners"])
    return [fdef["owner"]] if "owner" in fdef else []


# ── 조건식 ──────────────────────────────────────────────────────────────

def parse_cond(cond: str) -> tuple[str, str, object]:
    s = cond.strip()
    for u in UNARY_OPS:
        if s.endswith(" " + u):
            return s[: -len(u) - 1].strip(), u, None
    for op in BINARY_OPS:
        if op in s:
            left, right = s.split(op, 1)
            return left.strip(), op.strip(), _literal(right.strip(), op.strip())
    raise SpecError(f"조건식을 읽지 못했습니다: '{cond}' (형식: field op value · field exists)")


def _literal(raw: str, op: str):
    if op == "in":
        try:
            v = json.loads(raw)
        except json.JSONDecodeError:
            v = [x.strip() for x in raw.strip("[]").split(",") if x.strip()]
        if not isinstance(v, list):
            raise SpecError(f"in 뒤에는 목록이 와야 합니다: {raw}")
        return v
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw  # 따옴표 없는 글자 — enum 값을 그대로 적는 경우


def eval_cond(cond: str, values: dict) -> bool:
    """values: {field: value} — 값이 없는 필드는 키가 없다."""
    field, op, lit = parse_cond(cond)
    if op == "exists":
        return field in values
    if op == "missing":
        return field not in values
    if field not in values:
        return False
    v = values[field]
    try:
        if op == "==":
            return v == lit
        if op == "!=":
            return v != lit
        if op == "in":
            return v in lit
        if op == ">=":
            return v >= lit
        if op == "<=":
            return v <= lit
        if op == ">":
            return v > lit
        if op == "<":
            return v < lit
    except TypeError:
        return False
    raise SpecError(f"모르는 연산자: {op}")


# ── 경로 (files · 영역 root) ─────────────────────────────────────────────
#   "web/"        폴더 하나 전체 (끝의 / 가 폴더라는 표시)
#   "web/src/**"  와일드카드 앞까지를 폴더로 본다
#   "a/b.py"      파일 하나

def norm_path(p: str) -> str:
    s = str(p).replace("\\", "/").strip()
    while s.startswith("./"):
        s = s[2:]
    cut = min([i for i in (s.find("*"), s.find("?"), s.find("[")) if i >= 0], default=-1)
    if cut >= 0:  # 와일드카드 → 그 앞 폴더
        s = s[:cut]
        s = s[: s.rfind("/") + 1] if "/" in s else ""
    return s


def _is_dir(s: str) -> bool:
    return s == "" or s.endswith("/")


def paths_overlap(a: str, b: str) -> bool:
    a, b = norm_path(a), norm_path(b)
    if a == b:
        return True
    if _is_dir(a) and b.startswith(a):
        return True
    return _is_dir(b) and a.startswith(b)


def under(path: str, root: str) -> bool:
    """path 가 root(폴더) 안인가."""
    p, r = norm_path(path), norm_path(root)
    if not r.endswith("/"):
        r += "/"
    return p.startswith(r)


def has_dotdot(p: str) -> bool:
    return ".." in str(p).replace("\\", "/").split("/")


def contained(path: str, files: list[str]) -> bool:
    """바뀐 파일 path 가 files(파일 · 폴더) 안인가. 폴더 · 빈 경로 · `..` 를 바뀐 파일로 보고하면 거부한다."""
    if has_dotdot(path):
        return False
    n = norm_path(path)
    if _is_dir(n):
        return False
    for f in files:
        if has_dotdot(f):
            continue
        nf = norm_path(f)
        if nf == n or (_is_dir(nf) and n.startswith(nf)):
            return True
    return False


def node_reads(node: dict) -> list[str]:
    return [parse_cond(c)[0] for c in node.get("requires", [])]


def derived_edges(spec: dict) -> list[dict]:
    """간선은 손으로 적지 않는다. requires/rerun_on 이 가리키는 필드의 주인 → 그 노드."""
    fdefs = fields(spec)
    edges = []
    for n in spec["nodes"]:
        for c in n.get("requires", []):
            try:
                f = parse_cond(c)[0]
            except SpecError:
                continue  # 깨진 조건식은 validate 3행이 보고한다
            for o in owners(fdefs.get(f, {})):
                edges.append({"source": o, "target": n["id"], "label": c, "kind": "requires"})
        for f in n.get("rerun_on", []):
            for o in owners(fdefs.get(f, {})):
                edges.append({"source": o, "target": n["id"], "label": f"{f} 바뀌면 다시", "kind": "rerun"})
    return edges
