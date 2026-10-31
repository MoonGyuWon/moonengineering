"""CLI — 계약 specs/contracts/todo.md 의 CLI 표."""
import argparse
import sys

from todo import format as fmt
from todo import store


def main(argv=None) -> int:
    # 계약: stdout 은 UTF-8 (Windows 콘솔 · 파이프 기본값 cp949 에서도 한글이 깨지지 않게)
    # 수용 테스트(W0)는 줄 끝 \n 을 요구한다 — Windows 기본 \r\n 을 쓰지 않는다
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    sys.stderr.reconfigure(encoding="utf-8", newline="\n")
    ap = argparse.ArgumentParser(prog="todo")
    ap.add_argument("--file", default="todo.json")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("add").add_argument("title")
    sub.add_parser("list")
    sub.add_parser("done").add_argument("id", type=int)
    a = ap.parse_args(argv)
    if a.cmd == "add":
        item = store.add(a.file, a.title)
        print(f"추가: {item['id']} {item['title']}")
    elif a.cmd == "list":
        print(fmt.render(store.load(a.file)))
    else:
        try:
            store.mark_done(a.file, a.id)
        except KeyError:
            print(f"없는 id: {a.id}", file=sys.stderr)
            return 2
        print(f"완료: {a.id}")
    return 0
