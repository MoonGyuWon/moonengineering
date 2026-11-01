# C04-accept — 수용 시나리오 (검사기)

W3 · tools/accept.py 가 계약의 CLI 표를 처음부터 끝까지 돈다. 실패 분류는 failure_kind.

계약: [specs/contracts/todo.md](../contracts/todo.md)

```harness
{
  "kind": "node",
  "id": "C04-accept",
  "type": "CODE",
  "reqs": [
    "REQ-F1",
    "REQ-F2",
    "REQ-N1"
  ],
  "requires": [
    "cli.ok == true"
  ],
  "writes": [
    "check.verdict",
    "check.failure_kind"
  ],
  "cmd": "{python} tools/accept.py",
  "gate": {
    "cmd": "{python} -c exit(0)",
    "pass": "exit==0"
  }
}
```
