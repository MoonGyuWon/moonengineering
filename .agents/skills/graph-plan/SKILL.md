---
name: graph-plan
description: APPROVED 된 specs/REQUIREMENTS.md 를 받아 전체 플랜과 스펙을 순서대로 만든다 — 규모 S 면 CHECKLIST.md 한 장, M/L 이면 계약(상태 스키마 · 인터페이스 · fixture · 수용 테스트)을 먼저 쓰고 그 계약에만 기대는 task 노드 스펙(requires · writes · files · gate)을 잘게 쪼개 GRAPH.md 와 specs/nodes/*.md 로 쓴 뒤 validate · render 를 통과시키고 웨이브 계획을 사람에게 승인받는다. 이미 승인된 스펙의 변경(영향 범위 계산 · graph_version 올리기)과, 실패 패턴에서 처방 가지를 추가하는 일도 맡는다. "플랜 세워줘", "스펙 써줘", "노드 나눠줘", "스펙 바꾸고 싶어", "처방 가지 추가" 에서 사용한다. 노드를 실행하지 않는다 (다음은 graph-run).
compatibility: Python 3 (표준 라이브러리). 하네스(harness/ · templates/)는 같은 폴더에 있거나 install.py 로 연결한다. Agent Skills 표준 — Claude Code · Codex · Gemini CLI 등.
---

# graph-plan — 플랜 · 스펙 (4단계) · 변경 · 처방 가지

> 상태값만으로 도는 그래프를 **스펙으로** 만든다. 간선은 적지 않는다 — 노드의 `requires` 가 가리키는 필드의 주인에서 계산된다.
> 끝나면 `python harness/validate.py` 가 **exit 0** 이고 `diagrams/` 가 최신이며, 사람이 웨이브 계획을 승인했다.

> **시작할 때 `AGENTS.md` 를 읽는다** (역질문 · 그래프 규칙 · 종료 코드). 산출물(specs/ · trace/ …)은 지금 연 프로젝트 폴더에 만든다.

## 들어가기 전 확인

```bash
python harness/validate.py --project <프로젝트>      # 7행(요구사항 확정)이 OK 가 아니면 멈추고 req-intake 로
```

## 모드 판별

| 모드 | 조건 | 하는 일 |
| --- | --- | --- |
| **new** | GRAPH.md / CHECKLIST.md 가 없다 | 아래 A(S) 또는 B(M/L) |
| **change** | 스펙이 있고 바꾸자는 요청 · graph-run 의 역질문에서 "스펙 수정"을 골랐다 | C |
| **detour** | `report.py` 가 [패턴]을 냈다 · 사람이 처방 가지를 승인했다 | D |

## A. 규모 S — 체크리스트 한 장

`templates/CHECKLIST.md` → `specs/CHECKLIST.md`. 단계마다 `do` · `check`(값으로 판정하는 명령) · `reqs`.
모든 REQ 가 어느 단계에 있어야 한다 (validate 6행). 그래프 · 이벤트 · 그림은 만들지 않는다. 승인받고 graph-run 으로.

## B. 규모 M/L — 계약 먼저, task 는 잘게

**B1. 비 task 스펙 = 계약** (W0 · 순차 · 사람 승인)

- `specs/GRAPH.md`(`templates/GRAPH.md`)의 상태 스키마: 필드마다 형 · 주인 · enum 값.
  - 입력은 `"owner": "input"`. 분기에 쓸 필드는 `enum` 이나 수. 자유 문장은 `"free_text": true`.
- 경계를 넘는 데이터의 모양(파일 형식 · 함수 시그니처 · JSON 스키마)은 `specs/contracts/*.md` 에 쓴다.
- **영역 분할 (폴더 단위 병렬 — 어떤 개발이든)**: 서로 다른 폴더에서 동시에 만들 수 있는 덩어리가 있으면 `areas` 로 나눈다.
  예: `web/ · api/` · `api/ · worker/ · infra/` · `packages/<x>/` · `ingest/ · model/ · report/` · `plugins/<x>/` · `docs/`.
  - GRAPH `"areas": {"web": {"root": "web/"}}`, 영역 노드는 `"area": "web"` + `files` 는 그 폴더 안 (validate 9행) · `gate.cwd` 로 그 폴더에서 테스트.
  - 영역 사이의 계약(API 스키마 · 공유 타입 · fixture)과 **공유 루트 파일(package.json · 락파일 · 루트 설정 · CI)은 W0 계약 노드가 독점**한다 (area 없음).
    의존성 설치도 W0 에서 끝낸다. 영역 노드는 계약 필드(예: `contract.status == frozen`)에만 기댄다 — 프론트는 fixture 목으로, 백엔드는 계약 테스트로 판정.
  - 영역을 합치는 통합(e2e) 노드는 area 없이 각 영역의 완료 필드를 requires 로 받고 `e2e/` 만 고친다.
  - 실행 모드(같은 폴더 A / worktree B — graph-run 병렬 절)를 웨이브 계획과 함께 승인받는다.
  - **나누지 않는다**: S 규모 · 영역마다 task 가 2개 미만 · UI 가 API 모양을 계속 바꾸는 프로토타입 · 한 폴더에 두 영역이 섞여 있음.
    계약이 자주 바뀌면 양쪽이 다 다시 돌고, 영역 수만큼 토큰이 든다.
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
6 사람 확인이 필요한 REQ(verify: human)는 HUMAN 노드, LLM 판단이 필요한 분기는 JUDGE 노드 (JEV: choice/score/noul + auto 임계값)
7 외부로 나가는 일은 side_effect 노드 + HUMAN 승인 필드를 requires 에                    (8행)
8 반복이 필요한 일은 노드 안에 둔다 — AGENT 의 retry {max, on: [contract_violation]}. 바깥 순환은 처방 가지만
```

**B3. 검사 · 그림 · 승인**

```bash
python harness/validate.py --project <프로젝트>     # ERROR 면 스펙을 고친다 — 최대 3회. 그래도 ERROR 면 역질문 (검사기를 고치지 않는다)
python harness/render.py   --project <프로젝트>     # diagrams/graph.md · architecture.md(L) · timeline.md
```

GRAPH.md 의 **웨이브 계획 표**(웨이브 · task · 쓰는 필드/파일 · 기대는 계약)를 채워 보여 주고, 사람에게 물어 승인받는다.

- 병렬 실행 여부(W1 을 병렬 에이전트로 돌릴지)는 여기서 사람이 고른다. 권장: task 가 5개 이하면 순차 — 병렬은 토큰이 많이 들고 조율 비용이 있다.
- 승인한 결정은 `run.py decide` 를 아직 쓸 수 없으므로(Run 이 없다) GRAPH.md 웨이브 표 아래 "승인" 줄에 날짜와 함께 적는다.

## C. 변경 — 영향 범위부터

1. 무엇을 바꾸는지 받는다. **영향 범위를 계산해 먼저 보여 준다**:
   바꾸는 필드 → 그 필드를 requires · rerun_on 에 건 노드 → 그 노드들이 맡은 REQ → 이미 executed 인 노드(다시 돌아야 함).
2. 사람이 승인하면 스펙을 고치고 **`graph_version` 을 1 올린다.**
3. validate · render. 진행 중 Run 이 있으면 graph-run 에게 넘긴다 — 그쪽이 `run.py migrate` 를 역질문으로 결정한다.
4. 계약(B1)을 바꾸는 변경이면 그 계약을 읽는 task 가 **전부** 다시 돌아야 한다는 것을 분명히 알린다.

## D. 처방 가지 추가 — 패턴일 때만

- 진입 조건: `python harness/report.py` 에 **[패턴]**(서로 다른 Run 3곳 이상)이 있고, **고칠 법이 정해져 있다.** 일화 · 후보면 만들지 않는다.
- 모양은 `templates/NODE.md` 의 "처방 가지" 한 곳에 있다. 처방 가지는 데이터 · 파일을 고치고 검사기가 다시 잰다. 검사기 · 수용 기준을 약하게 만들지 않는다.
- graph_version 을 올리고, TROUBLESHOOTING.md 의 그 증상 항목에 "처방 가지 F<n> 로 뺌"을 적는다.

## 하지 않는 것

- 노드를 실행하거나 구현 코드를 쓰는 것 (graph-run)
- validate 를 통과시키려고 validate.py · 수용 기준을 고치는 것
- 간선을 손으로 적는 것 — requires 를 고친다
- 사람 승인 없이 병렬 · 범위 확장
