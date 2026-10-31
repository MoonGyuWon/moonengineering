"""스킬 동기화 — 정본은 `.agents/skills/`(Agent Skills 표준 · Codex · Gemini CLI 가 읽는 곳)이다.
`.agents/skills/` 를 읽지 않는 도구를 위해 복사본을 만든다. 복사본은 손으로 고치지 않는다.

    python harness/sync_skills.py [--root DIR] [--to .claude/skills ...]      복사
    python harness/sync_skills.py --check                                     표준 frontmatter 검사 + 복사본이 정본과 같은지

기본 복사 대상: .claude/skills (Claude Code 는 .claude/skills 만 읽는다)
종료 코드 0 OK · 1 표준 위반 또는 복사본이 다름
"""
from __future__ import annotations

import argparse
import filecmp
import re
import shutil
import sys
from pathlib import Path

SOURCE = ".agents/skills"
DEFAULT_TARGETS = [".claude/skills"]
# https://agentskills.io/specification — 이 밖의 키는 도구 전용이라 쓰지 않는다
ALLOWED = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def frontmatter(p: Path) -> dict[str, str]:
    t = p.read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---\n", t, re.S)
    if not m:
        raise ValueError("frontmatter(--- … ---)가 없습니다")
    out = {}
    for line in m.group(1).splitlines():
        km = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)  # 들여쓴 줄은 metadata 의 하위 키
        if km:
            out[km.group(1)] = km.group(2).strip().strip('"')
    return out


def check_standard(src: Path) -> list[str]:
    errs = []
    dirs = sorted(d for d in src.iterdir() if d.is_dir())
    if not dirs:
        errs.append(f"{src} 에 스킬이 없습니다")
    for d in dirs:
        f = d / "SKILL.md"
        if not f.exists():
            errs.append(f"{d.name}: SKILL.md 가 없습니다")
            continue
        try:
            fm = frontmatter(f)
        except ValueError as e:
            errs.append(f"{d.name}: {e}")
            continue
        extra = set(fm) - ALLOWED
        if extra:
            errs.append(f"{d.name}: 표준 밖의 키 {sorted(extra)} — 도구 전용 필드는 쓰지 않는다")
        name, desc = fm.get("name", ""), fm.get("description", "")
        if not NAME_RE.match(name) or len(name) > 64:
            errs.append(f"{d.name}: name {name!r} — 소문자 · 숫자 · 하이픈, 64자 이하")
        if name != d.name:
            errs.append(f"{d.name}: name({name}) 이 폴더 이름과 다릅니다")
        if not 1 <= len(desc) <= 1024:
            errs.append(f"{d.name}: description 은 1~1024자 (지금 {len(desc)})")
        if "compatibility" in fm and not 1 <= len(fm["compatibility"]) <= 500:
            errs.append(f"{d.name}: compatibility 는 1~500자")
        lines = len(f.read_text(encoding="utf-8").splitlines())
        if lines > 500:
            errs.append(f"{d.name}: SKILL.md 가 {lines}줄 — 500줄 이하 권장 (나머지는 references/ 로)")
    return errs


def same_tree(a: Path, b: Path) -> list[str]:
    diffs = []
    if not b.exists():
        return [f"{b} 가 없습니다"]
    cmp = filecmp.dircmp(a, b)

    def walk(c, rel=""):
        for x in c.left_only:
            diffs.append(f"복사본에 없음: {rel}{x}")
        for x in c.right_only:
            diffs.append(f"복사본에만 있음: {rel}{x}")
        for x in c.common_files:
            if not filecmp.cmp(Path(c.left) / x, Path(c.right) / x, shallow=False):
                diffs.append(f"내용이 다름: {rel}{x}")
        for name, sub in c.subdirs.items():
            walk(sub, f"{rel}{name}/")

    walk(cmp)
    return diffs


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".")
    ap.add_argument("--to", action="append", help="복사 대상 (여러 번 가능)")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve()
    src = root / SOURCE
    targets = [root / t for t in (a.to or DEFAULT_TARGETS)]
    if not src.is_dir():
        print(f"ERROR: 정본 {SOURCE} 가 없습니다")
        return 1
    errs = check_standard(src)
    for e in errs:
        print("표준 위반:", e)
    if a.check:
        for t in targets:
            for d in sorted(x for x in src.iterdir() if x.is_dir()):
                for diff in same_tree(d, t / d.name):
                    errs.append(diff)
                    print(f"동기화 필요 ({t.relative_to(root).as_posix()}/{d.name}):", diff)
        print("OK" if not errs else f"\n{len(errs)}건 — `python harness/sync_skills.py` 로 복사본을 다시 만든다")
        return 1 if errs else 0
    if errs:
        print("표준 위반이 있어 복사하지 않습니다")
        return 1
    for t in targets:
        t.mkdir(parents=True, exist_ok=True)
        for d in sorted(x for x in src.iterdir() if x.is_dir()):
            dst = t / d.name
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(d, dst, ignore=shutil.ignore_patterns("__pycache__"))
            print(f"복사: {SOURCE}/{d.name} → {t.relative_to(root).as_posix()}/{d.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
