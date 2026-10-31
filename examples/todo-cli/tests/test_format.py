import unittest

from todo import format as fmt


class T(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(fmt.render([]), "(할 일 없음)")

    def test_lines(self):
        items = [{"id": 1, "title": "우유", "done": False}, {"id": 2, "title": "책", "done": True}]
        self.assertEqual(fmt.render(items), "[ ] 1 우유\n[x] 2 책")


if __name__ == "__main__":
    unittest.main()
