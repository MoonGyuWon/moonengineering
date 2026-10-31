# H05-approve — 릴리스 승인 (사람)

W4 · 수용 시나리오가 통과한 뒤에만 선다. 실제 사용자에게 역질문한다.

계약: [specs/contracts/todo.md](../contracts/todo.md)

```harness
{
  "kind": "node",
  "id": "H05-approve",
  "type": "HUMAN",
  "impl": "VERIFIED",
  "layer": "interface",
  "boundary": "release",
  "reqs": [
    "REQ-F4"
  ],
  "requires": [
    "check.verdict == pass"
  ],
  "writes": [
    "release.action",
    "release.note"
  ],
  "human": {
    "actions": [
      "release",
      "stop"
    ],
    "approve": [
      "release"
    ],
    "field": "release.action",
    "note_field": "release.note"
  }
}
```
