# T06-release — 배포 (부작용)

W4 · 승인 필드를 requires 에 건 부작용 노드. 같은 키로 다시 불리면 건너뛴다.

계약: [specs/contracts/todo.md](../contracts/todo.md)

```harness
{
  "kind": "node",
  "id": "T06-release",
  "type": "CODE",
  "boundary": "release",
  "reqs": [
    "REQ-F4"
  ],
  "requires": [
    "release.action == release"
  ],
  "writes": [
    "release.status"
  ],
  "files": [
    "dist/todo-cli-v1"
  ],
  "side_effect": {
    "class": "local_release",
    "idempotency_key": "HARNESS_RUN+T06-release"
  },
  "cmd": "{python} tools/release.py",
  "gate": {
    "cmd": "{python} -c \"import pathlib,sys;sys.exit(0 if pathlib.Path('dist/todo-cli-v1/todo/cli.py').exists() else 1)\"",
    "pass": "exit==0"
  }
}
```
