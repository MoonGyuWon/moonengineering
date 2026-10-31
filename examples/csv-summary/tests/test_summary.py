import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from summarize import summarize, to_md  # noqa: E402

ROWS = [{"city": "서울", "score": "82"}, {"city": "부산", "score": "91"}, {"city": "서울", "score": "77"}]


class T(unittest.TestCase):
    def test_numeric(self):
        s = summarize(ROWS)["numeric"]["score"]
        self.assertEqual((s["min"], s["max"]), (77, 91))
        self.assertAlmostEqual(s["mean"], 250 / 3)

    def test_categorical(self):
        self.assertEqual(summarize(ROWS)["categorical"]["city"], {"서울": 2, "부산": 1})

    def test_md(self):
        self.assertIn("행 수: 3", to_md(summarize(ROWS)))


if __name__ == "__main__":
    unittest.main()
