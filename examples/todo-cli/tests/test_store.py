import json
import tempfile
import unittest
from pathlib import Path

from todo import store


class T(unittest.TestCase):
    def setUp(self):
        self.p = Path(tempfile.mkdtemp()) / "todo.json"

    def test_missing_file_is_empty(self):
        self.assertEqual(store.load(self.p), [])

    def test_add_assigns_ids(self):
        a = store.add(self.p, "  우유 사기 ")
        b = store.add(self.p, "책 반납")
        self.assertEqual((a["id"], b["id"], a["title"], a["done"]), (1, 2, "우유 사기", False))

    def test_korean_roundtrip_utf8(self):
        store.add(self.p, "한글 제목 ✓")
        raw = self.p.read_bytes().decode("utf-8")
        self.assertIn("한글 제목 ✓", raw)  # ensure_ascii=False
        self.assertEqual(json.loads(raw)[0]["title"], "한글 제목 ✓")

    def test_mark_done(self):
        store.add(self.p, "a")
        self.assertTrue(store.mark_done(self.p, 1)["done"])
        self.assertTrue(store.load(self.p)[0]["done"])
        with self.assertRaises(KeyError):
            store.mark_done(self.p, 9)


if __name__ == "__main__":
    unittest.main()
