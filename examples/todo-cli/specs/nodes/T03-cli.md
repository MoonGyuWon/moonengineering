# T03-cli — CLI — add · list · done

W2 · store · format 을 계약 API 로만 부른다. stdout 은 UTF-8.

계약: [specs/contracts/todo.md](../contracts/todo.md)

```harness
{
  "kind": "node",
  "id": "T03-cli",
  "type": "AGENT",
  "boundary": "cli",
  "reqs": [
    "REQ-F1",
    "REQ-F3"
  ],
  "requires": [
    "store.ok == true",
    "format.ok == true"
  ],
  "writes": [
    "cli.ok"
  ],
  "files": [
    "todo/cli.py",
    "todo/__main__.py",
    "todo/__init__.py"
  ],
  "gate": {
    "cmd": "{python} -m unittest tests.test_cli",
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
