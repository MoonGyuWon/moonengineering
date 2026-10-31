# GRAPH — <프로젝트 이름>

> 양식: `templates/GRAPH.md` · 작성: `graph-plan` · 정본은 ```harness 블록이다.
> **간선은 적지 않는다.** 노드의 `requires`(조건) · `rerun_on` 이 가리키는 필드의 주인에서 간선이 계산된다 (`diagrams/graph.md`).
> 스펙을 바꾸면 `graph_version` 을 올린다. 진행 중 Run 은 사람이 `run.py migrate` 를 결정한다.

## 상태 스키마 (계약 — 비 task 스펙)

| 필드 | 형 | 주인 | 값 · 설명 |
| --- | --- | --- | --- |
| input_path | str | input | 실행할 때 넣는 입력 |

규칙: 필드 하나에 주인 하나. 여럿이면 `owners` + `reducer`(append · replace · merge_by_key:<키>). 횟수 같은 카운터는 int 필드 · reducer 없음(덮어쓰기).
자유 문장 필드는 `"free_text": true` — 분기 조건에 쓸 수 없다. 분기에 쓰는 필드는 `enum` 이나 수로 만든다.

## 완료 · 중단 · 예산

- `done_when` (모두 참이면 SUCCESS):
- `stop_when` (하나라도 참이면 STOPPED — 사람이 멈춤):
- `budget`: 총 시도 · 시간(분)

## 영역 (폴더 단위 병렬 · 선택)

`"areas": {"web": {"root": "web/"}, "api": {"root": "api/"}}` — 영역 노드는 `area` 와 그 폴더 안의 `files` 를 가진다.
계약 · 공유 루트 파일(package.json · 락파일 · CI)은 영역 없는 W0 계약 노드가, 통합(e2e)은 영역 없는 노드가 맡는다.

## 계층 (L 규모)

`layers` 는 위에서 아래 순서. 노드마다 `layer` · `boundary` 를 적으면 `diagrams/architecture.md` 가 생긴다.

## 웨이브 계획 (사람 승인용 · 읽기용)

| 웨이브 | 영역 | task | 쓰는 필드 · 파일 | 기대는 계약 |
| --- | --- | --- | --- | --- |
| W0 | - | (계약 · fixture · 수용 테스트 · 공유 루트 파일) | | |
| W1 | | | | |

병렬 모드: 같은 폴더(A) / worktree(B · lanes.py) — 승인: (날짜)

---

```harness
{
  "kind": "graph",
  "graph_version": 1,
  "areas": {},
  "layers": [],
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
