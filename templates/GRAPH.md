# GRAPH — <프로젝트 이름>

> 양식: `templates/GRAPH.md` · 작성: `graph-plan` · 정본은 ```harness 블록이다.
> **간선은 적지 않는다.** 노드의 `requires`(조건)가 가리키는 필드의 주인에서 간선이 계산된다 (`diagrams/graph.md`).

## 상태 스키마 (계약 — 비 task 스펙)

| 필드 | 형 | 주인 | 값 · 설명 |
| --- | --- | --- | --- |
| input_path | str | input | 실행할 때 넣는 입력 |

규칙: 필드 하나에 주인 하나. 두 노드가 같은 것을 쓰고 싶으면 필드를 나눈다 (`stats_a` · `stats_b`).
자유 문장 필드는 `"free_text": true` — 분기 조건에 쓸 수 없다. 분기에 쓰는 필드는 `enum` 이나 수로 만든다.

## 완료 · 중단 · 예산

- `done_when` (모두 참이면 SUCCESS):
- `stop_when` (하나라도 참이면 STOPPED — 사람이 멈춤):
- `budget`: 총 시도 · 시간(분)

## 웨이브 계획 (사람 승인용 · 읽기용)

| 웨이브 | task | 쓰는 필드 · 파일 | 기대는 계약 |
| --- | --- | --- | --- |
| W0 | (계약 · fixture · 수용 테스트 · 공유 루트 파일) | | |
| W1 | | | |

병렬 실행 승인: (날짜 · 없으면 순차)

---

```harness
{
  "kind": "graph",
  "budget": {"max_attempts_total": 30},
  "done_when": ["report.status == written"],
  "stop_when": [],
  "fields": {
    "input_path": {"type": "str", "owner": "input"},
    "report.status": {"type": "enum", "values": ["written"], "owner": "T01-example"}
  },
  "nodes": []
}
```
