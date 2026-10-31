"""T06 배포 — 승인된 Run 에서만 dist/todo-cli-v1/ 로 복사한다. 같은 키로 다시 불리면 아무것도 하지 않는다 (멱등)."""
import json
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
dst = ROOT / "dist" / "todo-cli-v1"
key = f"{os.environ.get('HARNESS_RUN')}+T06-release"
marker = dst / "RELEASE_KEY"
if marker.exists() and marker.read_text(encoding="utf-8") == key:
    print("이미 배포됨 (같은 idempotency key) — 건너뜀")
else:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(ROOT / "todo", dst / "todo", ignore=shutil.ignore_patterns("__pycache__"))
    marker.write_text(key, encoding="utf-8")
    print(f"배포: {dst.relative_to(ROOT)}")
print("HARNESS_WRITES " + json.dumps({"release.status": "done"}))
