# T01-store — 저장소 — load · add · mark_done

W1 · 계약의 데이터 모양과 store API 만 본다. format · cli 는 보지 않는다.

계약: [specs/contracts/todo.md](../contracts/todo.md)

```harness
{
  "kind": "node",
  "id": "T01-store",
  "type": "AGENT",
  "impl": "VERIFIED",
  "layer": "infra",
  "boundary": "storage",
  "reqs": [
    "REQ-N1"
  ],
  "requires": [
    "todo_file exists"
  ],
  "writes": [
    "store.ok"
  ],
  "files": [
    "todo/store.py"
  ],
  "gate": {
    "cmd": "{python} -m unittest tests.test_store",
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
