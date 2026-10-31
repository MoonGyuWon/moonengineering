"""프로젝트 연결 — 하네스는 이 폴더 한 곳에 두고, 프로젝트에는 AI 도구가 읽을 스킬 · 규칙만 놓는다.

    python <하네스>/harness/install.py <프로젝트 폴더>            연결 (다시 돌리면 갱신 — git pull 뒤에)
    python <하네스>/harness/install.py <프로젝트 폴더> --check    프로젝트의 사본이 지금 하네스와 같은가

프로젝트에 생기는 것
  .agents/skills/<스킬>/SKILL.md   Codex · Gemini CLI 등이 읽는 곳   } 하네스 경로(harness/ · templates/)를
  .claude/skills/<스킬>/SKILL.md   Claude Code 가 읽는 곳            }  이 설치 폴더의 절대 경로로 바꾼 사본
  AGENTS.md    하네스 규칙을 <!-- moonengineering:begin --> … <!-- moonengineering:end --> 블록으로 (원래 내용은 그대로)
  CLAUDE.md    `@AGENTS.md` 줄이 없을 때만 덧붙인다
  .harness.json  설치 폴더 · 그때의 git 커밋 (어느 하네스로 작업했는지 추적)

AI 도구는 스킬을 정해진 위치에서만 읽는다 — 그래서 스킬 사본은 프로젝트에 두고, 스크립트 · 양식은 설치 폴더에서 부른다.
종료 코드 0 OK · 1 오류 또는 사본이 다름(--check)
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

HOME = Path(__file__).resolve().parents[1]
SKILLS = HOME / ".agents" / "skills"
BEGIN, END = "<!-- moonengineering:begin -->", "<!-- moonengineering:end -->"
TARGETS = (".agents/skills", ".claude/skills")


def home_str() -> str:
    return HOME.as_posix()


def rewrite(text: str) -> str:
    """상대 경로 harness/ · templates/ 를 설치 폴더의 절대 경로로 (specs/ 같은 프로젝트 경로는 그대로)."""
    h = home_str()
    text = re.sub(r"(?<![\w./\\-])harness/", h + "/harness/", text)
    return re.sub(r"(?<![\w./\\-])templates/", h + "/templates/", text)


def agents_block() -> str:
    body = (HOME / "AGENTS.md").read_text(encoding="utf-8")
    return (f"{BEGIN}\n<!-- {home_str()}/AGENTS.md 에서 install.py 가 넣은 블록 — 여기는 고치지 말고 하네스를 고친 뒤 다시 install -->\n"
            + rewrite(body).rstrip() + f"\n{END}\n")


def merged_agents(old: str | None) -> str:
    blk = agents_block()
    if not old:
        return blk
    nb, ne = old.count(BEGIN), old.count(END)
    if (nb, ne) not in ((0, 0), (1, 1)) or (nb == 1 and old.index(END) < old.index(BEGIN)):
        raise SystemExit(f"ERROR: AGENTS.md 의 하네스 표시({BEGIN} {nb}개 · {END} {ne}개)가 짝이 맞지 않습니다 — "
                         "사용자 내용을 지울 수 있어 멈춥니다. 표시를 정리한 뒤 다시 install")
    if nb == 1:
        pre, rest = old.split(BEGIN, 1)
        post = rest.split(END, 1)[1].lstrip("\n")
        return pre + blk + (("\n" + post) if post else "")
    return old.rstrip() + "\n\n" + blk


def plan(project: Path) -> dict[Path, str]:
    """프로젝트에 있어야 할 파일 → 내용."""
    out: dict[Path, str] = {}
    for d in sorted(x for x in SKILLS.iterdir() if x.is_dir()):
        txt = rewrite((d / "SKILL.md").read_text(encoding="utf-8"))
        for t in TARGETS:
            out[project / t / d.name / "SKILL.md"] = txt
    ag = project / "AGENTS.md"
    out[ag] = merged_agents(ag.read_text(encoding="utf-8") if ag.exists() else None)
    cl = project / "CLAUDE.md"
    old = cl.read_text(encoding="utf-8") if cl.exists() else ""
    out[cl] = old if re.search(r"^@AGENTS\.md\s*$", old, re.M) else (old.rstrip() + "\n\n" if old.strip() else "") + "@AGENTS.md\n"
    return out


def head_commit() -> str | None:
    p = subprocess.run(["git", "-C", str(HOME), "rev-parse", "HEAD"], capture_output=True)
    return p.stdout.decode().strip() if p.returncode == 0 else None


def home_dirty() -> bool:
    """하네스에 커밋 안 된 변경이 있으면 commit 만으로는 어느 버전인지 알 수 없다."""
    p = subprocess.run(["git", "-C", str(HOME), "status", "--porcelain"], capture_output=True)
    return p.returncode == 0 and bool(p.stdout.strip())


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    project = Path(a.project).resolve()
    if not project.is_dir():
        print(f"ERROR: 프로젝트 폴더가 없습니다: {project}")
        return 1
    if project == HOME:
        print("ERROR: 하네스 폴더 자체에는 연결하지 않습니다 (이미 들어 있다)")
        return 1
    if " " in home_str():
        print(f"⚠ 하네스 경로에 공백이 있습니다 ({home_str()}) — 스킬의 명령을 따옴표로 감싸야 할 수 있다. 공백 없는 곳을 권장")
    want = plan(project)
    if a.check:
        bad = [p for p, txt in want.items() if not p.exists() or p.read_text(encoding="utf-8") != txt]
        for p in bad:
            print("다름:", p.relative_to(project).as_posix())
        print("OK — 프로젝트의 사본이 지금 하네스와 같다" if not bad else
              f"{len(bad)}개가 다릅니다 — `python {home_str()}/harness/install.py {project.as_posix()}` 로 갱신")
        return 1 if bad else 0
    for p, txt in want.items():
        p.parent.mkdir(parents=True, exist_ok=True)
        changed = not p.exists() or p.read_text(encoding="utf-8") != txt
        p.write_text(txt, encoding="utf-8")
        print(("갱신 " if changed else "같음 ") + p.relative_to(project).as_posix())
    dirty = home_dirty()
    (project / ".harness.json").write_text(json.dumps({"home": home_str(), "commit": head_commit(), "dirty": dirty}, indent=2), encoding="utf-8")
    if dirty:
        print("⚠ 하네스에 커밋 안 된 변경이 있습니다 — .harness.json 의 commit 이 실제 버전과 다를 수 있다 (dirty: true)")
    print(f"\n연결 완료 — 하네스 {home_str()} (commit {(head_commit() or '-')[:10]})")
    print(f"이제 AI 도구를 {project.as_posix()} 에서 열고 req-intake 스킬로 시작한다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
