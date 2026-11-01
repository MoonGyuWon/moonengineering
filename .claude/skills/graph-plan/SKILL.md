---
name: graph-plan
description: APPROVED 된 specs/REQUIREMENTS.md 를 받아 먼저 만드는 법 카드(BLUEPRINT — 완성품을 그래프 프로그램으로 만들지 일반 구조로 만들지 · 단위마다 검증 방법)를 정하고, 플랜과 스펙을 만든다 — 규모 S · M 이면 CHECKLIST.md (M 은 계약 단계가 먼저), L 이면 계약(상태 스키마 · 인터페이스 · fixture · 수용 테스트)을 먼저 쓰고 그 계약에만 기대는 task 노드 스펙(requires · writes · files · gate)을 잘게 쪼개 GRAPH.md 와 specs/nodes/*.md 로 쓴 뒤 validate · render 를 통과시키고 웨이브 계획을 사람에게 승인받는다. 이미 승인된 스펙의 변경(영향 범위 계산)도 맡는다. "플랜 세워줘", "스펙 써줘", "노드 나눠줘", "스펙 바꾸고 싶어" 에서 사용한다. 노드를 실행하지 않는다 (다음은 graph-run).
compatibility: Python 3 (표준 라이브러리). 하네스(harness/ · templates/)는 같은 폴더에 있거나 install.py 로 연결한다. Agent Skills 표준 — Claude Code · Codex · Gemini CLI 등.
---

# graph-plan — 플랜 · 스펙 (4단계) · 변경

> 상태값만으로 도는 그래프를 **스펙으로** 만든다. 간선은 적지 않는다 — 노드의 `requires` 가 가리키는 필드의 주인에서 계산된다.
> 끝나면 `python harness/validate.py` 가 **exit 0** 이고 `diagrams/` 가 최신이며, 사람이 웨이브 계획을 승인했다.

> **시작할 때 `AGENTS.md` 를 읽는다** (역질문 · 그래프 규칙 · 종료 코드). 산출물(specs/ · trace/ …)은 지금 연 프로젝트 폴더에 만든다.

## 들어가기 전 확인

```bash
python harness/validate.py --project <프로젝트>      # 7행(요구사항 확정)이 OK 가 아니면 멈추고 req-intake 로
```

## 0. 만드는 법 카드 — 모든 규모 · 맨 먼저

`templates/BLUEPRINT.md` → `specs/BLUEPRINT.md` (반 쪽). 요구사항에서 5개 판단 규칙을 true/false 로 채우고, 구조(`shape`)와 단위별 검증을 고른다. 사람에게 승인받는다 (validate 9행).

- **3개 이상 참 → `graph`**: `python harness/runtime/graphrt.py init <program>` — 런타임이 복사돼 완성품은 하네스 없이 돈다.
  노드 하나 = `nodes/<id>.py` 하나 = `golden/<id>.jsonl` 하나. 플랜도 노드 단위로 나누고, 단계마다 check 는 `python <program>/graphrt.py eval <id>`,
  마지막 단계는 `eval` 전체 회귀(+ 임계값이 있으면 `metric.py`). HUMAN 노드는 사람 판단이 필요할 때만. LLM 노드는 `ctx.llm` — 제공자는 프로그램의 `llm.py`, 테스트는 `mocks/llm.json`.
- **아니면 그 분야의 일반 구조** (cli · library · web · algorithm · pipeline). 카드의 단위표대로 단위마다 검증을 정한다.
- 수치 검증(정확도 · 지연 · 비용)은 지표 JSON + `python harness/metric.py <metrics.json> "<경로> >= <값>" [--baseline …]`. 임계값 · 기준선은 수용 기준에서 온다.

## 모드 판별

| 모드 | 조건 | 하는 일 |
| --- | --- | --- |
| **new** | GRAPH.md / CHECKLIST.md 가 없다 | 0 다음에 A(S · M) 또는 B(L) |
| **change** | 스펙이 있고 바꾸자는 요청 · graph-run 의 역질문에서 "스펙 수정"을 골랐다 | C |

## A. 체크리스트 — S · M

`templates/CHECKLIST.md` → `specs/CHECKLIST.md`. 단계마다 `do` · `check`(값으로 판정하는 명령) · `reqs`.
M 은 첫 단계가 계약이다 (`specs/contracts/*.md` · fixture · 수용 테스트) — 이후 단계는 계약에만 기대고, 단계마다 자기 check 로 판정된다.
모든 REQ 가 어느 단계에 있어야 한다 (validate 6행). 그래프 · 이벤트 · 그림은 만들지 않는다. 승인받고 graph-run 으로.

## B. 개발 그래프 — L (여러 모듈 · 부작용 승인 · 승인된 병렬)

**B1. 비 task 스펙 = 계약** (W0 · 순차 · 사람 승인)

- `specs/GRAPH.md`(`templates/GRAPH.md`)의 상태 스키마: 필드마다 형 · 주인 · enum 값.
  - 입력은 `"owner": "input"`. 분기에 쓸 필드는 `enum` 이나 수. 자유 문장은 `"free_text": true`.
- 경계를 넘는 데이터의 모양(파일 형식 · 함수 시그니처 · JSON 스키마)은 `specs/contracts/*.md` 에 쓴다.
- **폴더로 나눠 병렬** (`web/` · `api/` 처럼): 공유 루트 파일(package.json · 락파일 · CI)과 계약은 W0 노드가 독점하고, 폴더 노드는 계약 필드에만 기대며
  `files` 는 자기 폴더 · `gate.cwd` 로 그 폴더에서 테스트. 합치는 e2e 노드가 각 완료 필드를 requires 로 받는다. 폴더마다 task 가 2개 미만이면 나누지 않는다.
- 각 task 의 **수용 테스트**(게이트가 돌릴 테스트)를 계약 fixture 로 먼저 정한다 — 구현 전에 빨간불이 나는 테스트.
- `done_when` · `stop_when` · `budget` 을 REQUIREMENTS 의 종료 · 이관 절에서 옮긴다.
- REQUIREMENTS 의 `tools`(req-intake 3-b 에서 고른 도구)마다 **환경 확인**을 W0 에 둔다 — `{python} -c "import x"` · `x --version` 같은 CODE 노드 게이트.
  없으면 그 노드가 실패해 역질문이 된다. **설치는 사람이 승인한 뒤에만** 한다 (설치 명령도 스펙에 적어 둔다).

**B2. task 스펙** (`templates/NODE.md` → `specs/nodes/<id>.md`)

쪼개는 규칙 — 행 번호가 있는 것은 validate 가 검사하고, 없는 것은 **사람이 웨이브 계획을 보고** 확인한다.

```text
1 task 의 requires 는 계약 필드에만 건다. 다른 task 의 구현(코드)에 기대지 않는다
2 같은 웨이브에 설 수 있는 task 끼리는 writes(필드) · files(파일)가 겹치지 않는다     (8행)
3 task 마다 혼자 판정되는 gate 가 있다 (CODE/AGENT)                                     (1행)
4 크기 = 에이전트 하나가 한 번에 끝내고 테스트 하나로 판정할 수 있는 만큼. 더 잘게 쪼개면 계약만 는다
5 REQ 마다 그것을 맡는 노드 + 게이트가 있다                                            (6행)
6 사람 확인이 필요한 REQ(verify: human)는 HUMAN 노드. LLM 판단은 AGENT 노드가 enum 으로 쓰고 게이트가 잰다
7 외부로 나가는 일은 side_effect 노드 + HUMAN 승인 필드를 requires 에                    (8행)
8 반복이 필요한 일은 노드 안에 둔다 — AGENT 의 retry {max, on: [contract_violation]}. 노드 사이 순환은 없다
```

**B3. 검사 · 그림 · 승인**

```bash
python harness/validate.py --project <프로젝트>     # ERROR 면 스펙을 고친다 — 최대 3회. 그래도 ERROR 면 역질문 (검사기를 고치지 않는다)
python harness/render.py   --project <프로젝트>     # diagrams/graph.md · timeline.md
```

GRAPH.md 의 **웨이브 계획 표**(웨이브 · task · 쓰는 필드/파일 · 기대는 계약)를 채워 보여 주고, 사람에게 물어 승인받는다.

- 병렬 실행 여부(W1 을 병렬 에이전트로 돌릴지)는 여기서 사람이 고른다. 권장: task 가 5개 이하면 순차 — 병렬은 토큰이 많이 들고 조율 비용이 있다.
- 승인한 결정은 `run.py decide` 를 아직 쓸 수 없으므로(Run 이 없다) GRAPH.md 웨이브 표 아래 "승인" 줄에 날짜와 함께 적는다.

## C. 변경 — 영향 범위부터

1. 무엇을 바꾸는지 받는다. **영향 범위를 계산해 먼저 보여 준다**:
   바꾸는 필드 → 그 필드를 requires 에 건 노드 → 그 노드들이 맡은 REQ → 이미 executed 인 노드(다시 돌아야 함).
2. 사람이 승인하면 스펙을 고친다.
3. validate · render. 진행 중 Run 이 있으면 다시 돌아야 하는 노드를 graph-run 에게 넘긴다 (사람이 reset 또는 새 Run 을 고른다).
4. 계약(B1)을 바꾸는 변경이면 그 계약을 읽는 task 가 **전부** 다시 돌아야 한다는 것을 분명히 알린다.

## 하지 않는 것

- 노드를 실행하거나 구현 코드를 쓰는 것 (graph-run)
- validate 를 통과시키려고 validate.py · 수용 기준을 고치는 것
- 간선을 손으로 적는 것 — requires 를 고친다
- 사람 승인 없이 병렬 · 범위 확장
