# GRAPH — todo-cli (리허설 M)

> 간선은 적지 않는다. 노드의 `requires` 가 가리키는 필드의 주인에서 계산된다 → `diagrams/graph.md`.

## 상태 스키마 (계약)

| 필드 | 형 | 주인 | 뜻 |
| --- | --- | --- | --- |
| todo_file | str | input | 수용 시나리오가 쓸 기본 저장 파일 이름 (Run 입력) |
| store.ok | bool | T01-store | `tests.test_store` 통과 |
| format.ok | bool | T02-format | `tests.test_format` 통과 |
| cli.ok | bool | T03-cli | `tests.test_cli` 통과 |
| check.verdict | enum pass · fail | C04-accept | 수용 시나리오 판정 |
| check.failure_kind | enum none · unknown | C04-accept | 처방 가지 자리 (지금은 없음 → unknown 이면 STUCK → 역질문) |
| release.action | enum release · stop | H05-approve | 사람의 답 |
| release.note | str (free_text) | H05-approve | 기록만 — 분기에 안 씀 |
| release.status | enum done | T06-release | 배포 끝 |

## 완료 · 중단 · 예산

- `done_when`: `release.status == done`
- `stop_when`: `release.action == stop`
- `budget`: 시도 20

## 웨이브 계획

| 웨이브 | task | 쓰는 필드 · 파일 | 기대는 계약 |
| --- | --- | --- | --- |
| W0 | 계약 · 수용 테스트 (이 문서 · `specs/contracts/todo.md` · `tests/*` · `tools/accept.py`) | — | — |
| W1 (병렬) | T01-store · T02-format | store.ok · `todo/store.py` / format.ok · `todo/format.py` | 데이터 모양 · store/format API |
| W2 | T03-cli | cli.ok · `todo/cli.py` · `todo/__main__.py` · `todo/__init__.py` | CLI 표 · store · format API |
| W3 | C04-accept | check.* | CLI 표 |
| W4 | H05-approve (사람) → T06-release (부작용) | release.* · `dist/` | — |

승인: 2026-10-31 · W1 병렬 실행 (리허설 — 병렬 웨이브를 실제로 돌려 본다)

```harness
{
  "kind": "graph",
  "graph_version": 1,
  "layers": ["interface", "verification", "domain", "infra"],
  "budget": {"max_attempts_total": 20},
  "done_when": ["release.status == done"],
  "stop_when": ["release.action == stop"],
  "fields": {
    "todo_file": {"type": "str", "owner": "input"},
    "store.ok": {"type": "bool", "owner": "T01-store"},
    "format.ok": {"type": "bool", "owner": "T02-format"},
    "cli.ok": {"type": "bool", "owner": "T03-cli"},
    "check.verdict": {"type": "enum", "values": ["pass", "fail"], "owner": "C04-accept"},
    "check.failure_kind": {"type": "enum", "values": ["none", "unknown"], "owner": "C04-accept"},
    "release.action": {"type": "enum", "values": ["release", "stop"], "owner": "H05-approve"},
    "release.note": {"type": "str", "owner": "H05-approve", "free_text": true},
    "release.status": {"type": "enum", "values": ["done"], "owner": "T06-release"}
  },
  "nodes": []
}
```
