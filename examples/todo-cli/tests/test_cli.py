import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def cli(f, *args):
    env = {k: v for k, v in os.environ.items() if k != "PYTHONIOENCODING"}  # 콘솔 기본 인코딩에서도 깨지지 않아야 한다
    p = subprocess.run([sys.executable, "-m", "todo", "--file", str(f), *args], cwd=ROOT, capture_output=True, env=env)
    return p.returncode, p.stdout.decode("utf-8"), p.stderr.decode("utf-8")


class T(unittest.TestCase):
    def setUp(self):
        self.f = Path(tempfile.mkdtemp()) / "todo.json"

    def test_add_list_done(self):
        self.assertEqual(cli(self.f, "add", "우유 사기"), (0, "추가: 1 우유 사기\n", ""))
        cli(self.f, "add", "책 반납")
        self.assertEqual(cli(self.f, "done", "2")[:2], (0, "완료: 2\n"))
        self.assertEqual(cli(self.f, "list")[1], "[ ] 1 우유 사기\n[x] 2 책 반납\n")

    def test_done_missing_id(self):
        code, out, err = cli(self.f, "done", "7")
        self.assertEqual(code, 2)
        self.assertIn("없는 id: 7", err)


if __name__ == "__main__":
    unittest.main()
