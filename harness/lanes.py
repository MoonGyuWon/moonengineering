"""영역별 git worktree (병렬 모드 B · 사람이 고를 때만) — 영역(frontend/ · backend/ …)마다 자기 작업 폴더 · 브랜치에서 일하고, 메인이 병합한다.
대부분은 모드 A(같은 폴더)로 충분하다. 모드 B 는 루트 캐시 · node_modules · 무거운 빌드가 영역끼리 부딪힐 때만 쓴다.

    python harness/lanes.py [--project DIR] checkpoint --dry-run         커밋할 파일 목록만 본다 (역질문 ② 에 보여 준다)
    python harness/lanes.py [--project DIR] checkpoint --note "…"        W0(계약) 결과를 커밋 — 사람 승인 뒤
    python harness/lanes.py [--project DIR] open   <영역>                 지금 메인 HEAD 에서 영역 worktree → 하위 에이전트 폴더 경로 출력
    python harness/lanes.py [--project DIR] merge  <영역> --note "…"      영역 root 만 커밋해 메인에 병합 → finish 에 줄 --changed 목록 출력
    python harness/lanes.py [--project DIR] close  <영역> [--force]       병합 안 된 작업이 있으면 거부 (--force 는 사람이 정했을 때만)
    python harness/lanes.py [--project DIR] list

규칙
- 영역은 GRAPH.md 의 `areas`. merge 는 **그 영역 root 만** 커밋한다 — 밖에서 바뀐 것은 따라오지 않고 exit 2.
- 체크포인트는 하네스 기록(trace · state · evidence · memory · diagrams)을 커밋하지 않는다 — 정본(이벤트)을 git 이 되돌리지 못하게.
  비밀로 보이는 파일(.env · *.pem · *.key · id_rsa …)이 들어가면 멈춘다.
- 하네스 상태는 메인만 쓴다. 영역 worktree 에서는 run.py 를 쓰지 않는다.
- 병합을 못 하면(충돌 · 메인의 커밋 안 된 변경) 되돌리고 exit 2 — 역질문.

종료 코드 0 성공 · 1 오류 · 2 사람 판단 필요
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import spec as S  # noqa: E402

STATE = "state/lanes.json"
HOME = Path(__file__).resolve().parents[1].as_posix()
RECORDS = ("trace/", "state/", "evidence/", "memory/", "diagrams/")  # 하네스 기록 — 체크포인트에 넣지 않는다
SECRETS = (".env", ".env.*", "*.pem", "*.key", "*.p12", "*.pfx", "id_rsa*", "id_ed25519*", "*credentials*", "*secret*")


class LaneError(Exception):
    pass


def git(cwd: Path, *args, check=True) -> str:
    p = subprocess.run(["git", "-c", "core.quotepath=false", "-C", str(cwd), *args], capture_output=True)
    out = p.stdout.decode("utf-8", "replace").strip()
    if check and p.returncode != 0:
        raise LaneError(f"git {' '.join(args)} 실패 — {p.stderr.decode('utf-8', 'replace').strip()}")
    return out


def status_paths(cwd: Path) -> list[str]:
    """`status --porcelain -z` — 공백 · 따옴표가 든 경로도 그대로 받는다."""
    p = subprocess.run(["git", "-C", str(cwd), "status", "--porcelain", "-z", "-uall"], capture_output=True)
    toks = p.stdout.decode("utf-8", "replace").split("\0")
    out, i = [], 0
    while i < len(toks):
        t = toks[i]
        if len(t) > 3:
            out.append(t[3:])
            if t[0] in "RC":  # 이름 바꾸기 — 다음 토큰은 옛 이름
                i += 1
        i += 1
    return out


def load(root: Path) -> dict:
    p = root / STATE
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"base": None, "lanes": {}}


def save(root: Path, data: dict):
    p = root / STATE
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def repo_info(root: Path) -> tuple[Path, str]:
    top = Path(git(root, "rev-parse", "--show-toplevel"))
    prefix = git(root, "rev-parse", "--show-prefix")  # 저장소 안에서 프로젝트 폴더 (예: "examples/todo-cli/")
    return top, prefix


def area_root(root: Path, area: str) -> str:
    spec = S.load(root)
    areas = (spec["graph"] or {}).get("areas") or {}
    if area not in areas:
        raise LaneError(f"영역 {area!r} 가 GRAPH.md 의 areas 에 없습니다 ({sorted(areas)})")
    return S.norm_path(areas[area]["root"])


def checkpoint_files(top: Path, prefix: str) -> list[str]:
    files = []
    for f in status_paths(top):
        if not f.startswith(prefix):
            continue
        rel = f[len(prefix):]
        if any(rel.startswith(r) for r in RECORDS):
            continue
        files.append(f)
    return files


def cmd_checkpoint(root: Path, a) -> int:
    top, prefix = repo_info(root)
    files = checkpoint_files(top, prefix)
    secret = [f for f in files if any(fnmatch.fnmatch(Path(f).name.lower(), pat) for pat in SECRETS)]
    if a.dry_run:
        print(f"커밋할 파일 {len(files)}개 (하네스 기록 {', '.join(RECORDS)} 는 뺀다):")
        for f in files:
            print("  ", f)
        if secret:
            print("⚠ 비밀로 보이는 파일:", secret)
        return 0
    if not a.note:
        raise LaneError("--note 가 필요합니다 (사람의 승인 내용)")
    if secret:
        print(f"⚠ 사람 판단 필요 — 비밀로 보이는 파일이 커밋에 들어갑니다: {secret}. .gitignore 에 넣거나 사람이 확인한 뒤 다시")
        return 2
    if files:
        git(top, "add", "-A", "--", *files)
        git(top, "commit", "-m", f"harness checkpoint: {a.note}")
    base = git(top, "rev-parse", "HEAD")
    data = load(root)
    data["base"] = base
    save(root, data)
    print(f"체크포인트 {base[:10]} — 커밋한 파일 {len(files)}개" + ("" if files else " (바뀐 것이 없어 HEAD 를 그대로 출발점으로)"))
    return 0


def cmd_open(root: Path, a) -> int:
    data = load(root)
    if not data["base"]:
        raise LaneError("체크포인트가 없습니다 — W0 를 끝내고 사람 승인 뒤 `lanes.py checkpoint`")
    ar = area_root(root, a.area)
    top, prefix = repo_info(root)
    if a.area in data["lanes"]:
        print(f"이미 열림:\n  {data['lanes'][a.area]['project_dir']}")
        return 0
    head = git(top, "rev-parse", "HEAD")  # 지금 메인 — 이미 병합된 영역 코드가 들어 있다
    wt = top / ".worktrees" / a.area
    branch = f"harness/{a.area}"
    git(top, "branch", "-D", branch, check=False)  # 전에 닫은 같은 이름 (병합된 것만 닫히므로 안전)
    git(top, "worktree", "add", "-b", branch, str(wt), head)
    excl = Path(git(top, "rev-parse", "--git-common-dir"))
    excl = (excl if excl.is_absolute() else top / excl) / "info" / "exclude"
    excl.parent.mkdir(parents=True, exist_ok=True)
    if ".worktrees/" not in (excl.read_text(encoding="utf-8") if excl.exists() else ""):
        with excl.open("a", encoding="utf-8") as f:
            f.write("\n.worktrees/\n")
    pdir = wt / prefix
    data["lanes"][a.area] = {"branch": branch, "worktree": str(wt), "project_dir": str(pdir), "root": ar, "from": head, "merged": []}
    save(root, data)
    print(f"영역 {a.area} 열림 (메인 {head[:10]} 에서) — 하위 에이전트는 이 폴더에서 {ar} 만 고친다:\n  {pdir}")
    return 0


def cmd_merge(root: Path, a) -> int:
    data = load(root)
    lane = data["lanes"].get(a.area)
    if not lane:
        raise LaneError(f"영역 {a.area} 가 열려 있지 않습니다")
    top, prefix = repo_info(root)
    wt = Path(lane["worktree"])
    scope = prefix + lane["root"]
    outside = [f for f in status_paths(wt) if not f.startswith(scope)]
    git(wt, "add", "-A", "--", scope)
    if git(wt, "diff", "--cached", "--name-only"):
        git(wt, "commit", "-m", f"lane {a.area}: {a.note}")
    before = git(top, "rev-parse", "HEAD")
    p = subprocess.run(["git", "-C", str(top), "merge", "--no-ff", "--no-edit", lane["branch"]], capture_output=True)
    if p.returncode != 0:
        subprocess.run(["git", "-C", str(top), "merge", "--abort"], capture_output=True)
        print("⚠ 사람 판단 필요 — 병합하지 못해 되돌렸습니다 (충돌 또는 메인의 커밋 안 된 변경):\n"
              + p.stdout.decode("utf-8", "replace") + p.stderr.decode("utf-8", "replace"))
        print(f"  → 역질문 ({HOME}/templates/ASK.md \"영역 병렬\"): 계약 수정 / 한쪽 다시 / 손으로 병합 / 순차로")
        return 2
    names = git(top, "diff", "--name-only", before, "HEAD").splitlines()
    changed = [n[len(prefix):] for n in names if n.startswith(prefix)]
    lane["merged"].append({"from": before, "to": git(top, "rev-parse", "HEAD"), "changed": changed, "note": a.note})
    save(root, data)
    code = 0
    if not changed:
        print(f"⚠ 사람 판단 필요 — 영역 {a.area} 에서 병합할 변경이 없습니다 (하위 에이전트가 아무것도 안 했거나 영역 밖만 고침)")
        code = 2
    else:
        print(f"영역 {a.area} 병합 — 바뀐 파일 {len(changed)}개. 이 목록으로 노드를 끝낸다:")
        print(f"  python {HOME}/harness/run.py finish <노드> --changed " + " ".join(f'"{c}"' if " " in c else c for c in changed))
    if outside:
        print(f"⚠ 영역 밖에서 바뀐 파일은 병합하지 않았습니다 (worktree 에 남음): {outside}")
        code = 2
    return code


def cmd_close(root: Path, a) -> int:
    data = load(root)
    lane = data["lanes"].get(a.area)
    if not lane:
        raise LaneError(f"영역 {a.area} 가 열려 있지 않습니다")
    top, _ = repo_info(root)
    wt = Path(lane["worktree"])
    dirty = status_paths(wt) if wt.exists() else []
    unmerged = subprocess.run(["git", "-C", str(top), "merge-base", "--is-ancestor", lane["branch"], "HEAD"],
                              capture_output=True).returncode != 0
    if (dirty or unmerged) and not a.force:
        print(f"⚠ 사람 판단 필요 — 영역 {a.area} 에 병합하지 않은 작업이 있습니다"
              + (f" (커밋 안 된 파일 {dirty})" if dirty else "") + (" (메인에 없는 커밋)" if unmerged else "")
              + " — merge 하거나, 버려도 된다고 사람이 정하면 close --force")
        return 2
    git(top, "worktree", "remove", "--force", lane["worktree"])
    git(top, "branch", "-D", lane["branch"], check=False)
    del data["lanes"][a.area]
    save(root, data)
    print(f"영역 {a.area} 정리")
    return 0


def cmd_list(root: Path, a) -> int:
    data = load(root)
    print("체크포인트:", data["base"] or "(없음)")
    for k, v in data["lanes"].items():
        print(f"  {k:12} {v['root']:16} 병합 {len(v['merged'])}회 · {v['project_dir']}")
    return 0


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("checkpoint"); sp.add_argument("--note"); sp.add_argument("--dry-run", action="store_true")
    sub.add_parser("open").add_argument("area")
    sp = sub.add_parser("merge"); sp.add_argument("area"); sp.add_argument("--note", required=True)
    sp = sub.add_parser("close"); sp.add_argument("area"); sp.add_argument("--force", action="store_true")
    sub.add_parser("list")
    a = ap.parse_args(argv)
    root = S.project_dir(a.project)
    try:
        return {"checkpoint": cmd_checkpoint, "open": cmd_open, "merge": cmd_merge, "close": cmd_close,
                "list": cmd_list}[a.cmd](root, a)
    except (LaneError, S.SpecError) as e:
        print("ERROR:", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
