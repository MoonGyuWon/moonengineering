"""C04 수용 시나리오 — 계약 문서의 CLI 표를 처음부터 끝까지 한 번 돈다. 결과는 HARNESS_WRITES 로."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
f = Path(tempfile.mkdtemp()) / "todo.json"


def run(*a):
    p = subprocess.run([sys.executable, "-m", "todo", "--file", str(f), *a], cwd=ROOT, capture_output=True)
    return p.returncode, p.stdout.decode("utf-8", "replace")


steps = [
    (run("list"), (0, "(할 일 없음)\n")),
    (run("add", "한글 제목 ✓"), (0, "추가: 1 한글 제목 ✓\n")),
    (run("done", "1"), (0, "완료: 1\n")),
    (run("list"), (0, "[x] 1 한글 제목 ✓\n")),
]
bad = [i for i, (got, want) in enumerate(steps, 1) if got != want]
for i in bad:
    print(f"단계 {i}: 받은 것 {steps[i - 1][0]!r} · 기대 {steps[i - 1][1]!r}")
w = {"check.verdict": "fail" if bad else "pass", "check.failure_kind": "unknown" if bad else "none"}
print("HARNESS_WRITES " + json.dumps(w))
