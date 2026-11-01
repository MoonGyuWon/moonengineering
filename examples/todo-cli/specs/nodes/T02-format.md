# T02-format — 목록 출력 형식 — render

W1 · 계약의 format API 만 본다. store · cli 는 보지 않는다.

계약: [specs/contracts/todo.md](../contracts/todo.md)

```harness
{
  "kind": "node",
  "id": "T02-format",
  "type": "AGENT",
  "boundary": "presentation",
  "reqs": [
    "REQ-F2"
  ],
  "requires": [
    "todo_file exists"
  ],
  "writes": [
    "format.ok"
  ],
  "files": [
    "todo/format.py"
  ],
  "gate": {
    "cmd": "{python} -m unittest tests.test_format",
    "pass": "exit==0"
  },
  "retry": {
    "max": 2,
    "on": [
      "contract_violation"
    ]
  }
}
```
