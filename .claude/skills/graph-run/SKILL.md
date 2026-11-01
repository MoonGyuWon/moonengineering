---
name: graph-run
description: validate 가 PASS 인 스펙을 상태값만으로 실행한다 — run.py next 로 ready 웨이브를 계산하고, 노드마다 스펙대로 구현 · 실행한 뒤 게이트(값으로 판정)를 돌려 이벤트 · 증거를 남기고 그림을 갱신한다. 실패 · STUCK · 예산 소진 · HUMAN 노드에서는 멈추고 5칸 역질문으로 사람에게 묻고, 답을 run.py answer/decide/reset 으로 남긴다. 승인된 경우에만 같은 웨이브를 병렬 에이전트로 돌린다(도구가 지원할 때). 끝나면 증거 기반 검토(문제 최대 3개)와 실패 집계를 보고한다. 체크리스트 모드(S · M)는 CHECKLIST 를 단계별로 실행한다. "실행해줘", "다음 노드", "이어서 해줘", "결과 검토" 에서 사용한다.
compatibility: Python 3 (표준 라이브러리). 하네스(harness/ · templates/)는 같은 폴더에 있거나 install.py 로 연결한다. Agent Skills 표준 — Claude Code · Codex · Gemini CLI 등.
---

# graph-run — 실행 (5단계) · 역질문 · 검토

> "다음에 무엇을 할까"는 언제나 **상태에서 다시 계산한다** (`run.py next`). 기억이나 대화 흐름으로 정하지 않는다.
> 문제가 생기면 멈추고 묻는다. 묻지 않고 넘어가는 것은 스펙에 선언된 자동 경로뿐이다.

> **시작할 때 `AGENTS.md` 를 읽는다** (역질문 · 그래프 규칙 · 종료 코드). 산출물(specs/ · trace/ …)은 지금 연 프로젝트 폴더에 만든다.

## 들어가기 전 확인

```bash
python harness/validate.py --project <프로젝트>      # exit 0 이 아니면 실행하지 않는다 → graph-plan
```

체크리스트 모드(`specs/CHECKLIST.md`)면 맨 아래 **체크리스트 실행** 으로.

## 시작 · 이어 하기

```bash
python harness/run.py start --set input_path=…     # 새 Run (입력 필드는 owner: input 인 것만)
python harness/run.py next                         # 이어서 할 때는 이것만 — 이벤트에서 상태를 다시 만든다
python harness/run.py status                       # 상태 · 실패 · 대기 · 필드 값
```

끝나지 않은 Run 이 있는데 `start` 하려 하면 하네스가 막는다 — 이어 할지 새로 할지 역질문.

## 한 노드를 실행하는 절차 (웨이브 안의 노드마다)

`run.py next` 가 준 ready 목록에서 하나씩 (병렬은 아래 절).

1. 노드 스펙(`specs/nodes/<id>.md` 또는 GRAPH.md)을 **다시 읽는다.** requires · writes · files · gate · 하지 않는 것.
2. 종류별로:

   | 종류 | 하는 일 |
   | --- | --- |
   | CODE | `python harness/run.py exec <id>` — 하네스가 cmd · 게이트를 돌리고 쓰기를 반영한다 |
   | AGENT | `run.py begin <id>` → 스펙의 files 안에서만 구현 → `run.py finish <id> --set 필드=값 [--evidence 경로]` (게이트는 하네스가 돌린다) |
   | HUMAN | `run.py wait <id> --reason "…"` → **역질문** → `run.py answer <id> --action <값> --note "…"` |

   - 상태 값이 필요하면 `state/state.json` 을 읽는다 (CODE 노드는 환경변수 `HARNESS_STATE`).
   - 스펙 밖의 파일을 고쳐야 한다고 판단되면 **고치지 말고** 역질문 → "스펙 수정(graph-plan)"을 선택지로.
   - 에이전트가 스스로 막혔으면 `run.py fail <id> --cause <분류> --symptom "…"` 로 남긴다 (분류: transient · input · contract_violation · structural).
3. 그림을 갱신한다: `python harness/render.py --project <프로젝트>`.
4. `run.py next` 로 다음 웨이브.

## 하네스 종료 코드 → 할 일

| 출력 / exit | 뜻 | 할 일 |
| --- | --- | --- |
| exit 0 · `DONE` | done_when 이 모두 참 | **검토** 절로 |
| exit 0 · `STOPPED` | 사람이 멈추기로 함 (stop_when) | 검토 절로 (멈춘 이유를 적는다) |
| exit 0 · ready 목록 | 계속 | 다음 노드 |
| exit 3 · `failed_retryable` | 선언된 retry 한도 안 | **묻지 않고** 같은 노드를 다시 (AGENT 면 게이트 로그를 읽고 고친 뒤) — 한도는 하네스가 센다 |
| exit 1 · `ERROR:` | 명령을 잘못 불렀다 (예: ready 가 아닌 노드) | `run.py next` 를 보고 바로잡는다. 스펙 문제면 graph-plan |
| exit 2 · `⚠ 사람 판단 필요` | FAIL · STUCK · BLOCKED · waiting_human · running 만 남음 · 하네스 오류 | **역질문** |

## 역질문 (AGENTS.md 3절 · `templates/ASK.md`)

1. 근거를 모은다: `run.py status` · 그 노드의 `evidence/<id>/<rNNaMM>/gate.log` · `result.json` · `memory/TROUBLESHOOTING.md` 의 같은 증상.
2. 5칸으로 묻는다 (질문 도구가 있으면 그 도구, 없으면 채팅에 5칸을 쓰고 답을 기다린다): ① 지금 ② 왜(원인 + 근거 경로 · seq) ③ 권장(첫 선택지 + 이유) ④ 고르기(선택지마다 일어나는 일) ⑤ 답.
   `templates/ASK.md` 의 "자주 쓰는 선택지 묶음"에서 고른다.
3. 답을 **명령으로 남긴다** (`templates/ASK.md` 의 표). 말로만 진행하지 않는다. 사람이 답하기 전에 이 명령을 먼저 쓰지 않는다.
4. 실패가 해결되면 `memory/TROUBLESHOOTING.md` 의 그 항목의 **원인 · 조치** 칸을 채운다.

## 병렬 웨이브 (사람이 승인했을 때만)

- `run.py next` 가 둘 이상을 주면, graph-plan 에서 병렬을 승인했는지 확인한다. 아니면 순차로 하거나 지금 묻는다.
- **공통**: `run.py begin` · `finish` 는 **메인 세션만** 부른다 (이벤트 작성자는 하나). 하위 에이전트는 자기 노드의 `files` 만 고치고,
  끝나면 "바뀐 파일 목록 · 쓸 필드 값"을 보고한다. 하위 에이전트를 띄우는 법은 도구마다 다르고(Claude Code 의 서브에이전트 등),
  **지원하지 않으면 순차로 한다** — 결과는 같고 시간만 다르다. 같은 폴더의 다음 노드는 같은 하위 에이전트에 이어 맡기면 맥락 · 토큰을 아낀다.
- `begin` 은 진행 중인 노드와 고치는 경로가 겹치면 거부한다. validate 8행(정적) + begin(실행 중) 두 겹이다.

```text
run.py begin T11-api ; run.py begin T12-web          ← 메인
하위 에이전트 2개가 api/ · web/ 를 고친다            ← 병렬
run.py finish T11-api --set api.done=true --changed <보고받은 파일들>   ← 바뀐 파일 ⊆ files 를 하네스가 본다
```

**사람 대기 중**: `next` 가 대기(exit 2)와 함께 관계없는 ready 를 보여 주면 — **먼저 묻고**, 답을 기다리는 동안 그 ready 는 진행해도 된다
(하위 에이전트가 돌고 있으면 그대로 둔다). 대기 노드의 하류는 상태값 때문에 돌지 않는다.

## 검토 (DONE · STOPPED 뒤)

1. `python harness/render.py`.
2. REQ 마다 수용 기준을 실제 증거와 대조한다 (`evidence/…/result.json` · gate.log). 확인하지 않은 것을 확인했다고 쓰지 않는다.
3. 문제는 **최대 3개**, 각각 근거 파일 경로 + 해결책 + 확인 방법.
4. 보고 형식:

```text
상태        : SUCCESS | STOPPED | 진행 중(<phase>)
Run         : <run_id> · 시도 <n>
REQ         : REQ-F1 ✓ (근거 경로) · REQ-N1 ✓ · …   (확인 못 한 것은 ✗ 와 이유)
사람 결정   : N건 (memory/DECISIONS.md)
실패        : N건 (memory/TROUBLESHOOTING.md · 같은 증상 반복 여부)
그림        : diagrams/graph.md · timeline.md
문제 (≤3)   : 1) … — 근거 · 해결책 · 확인 방법
```

`SUCCESS` 가 아니면 성공했다고 쓰지 않는다. 같은 실패가 반복되면 "graph-plan 으로 스펙 · 계약 보강"을 다음 할 일로 제안한다.

## 체크리스트 실행 (S · M)

`specs/CHECKLIST.md` 의 단계를 차례로: 할 일 → `check` 명령을 실제로 돌림 → `result` 칸에 결과(exit · 값)를 적는다.
실패하면 역질문. 이벤트 · 그림은 없다. 병렬 · 부작용 승인 분기가 필요해지면 역질문으로 개발 그래프(L)로 올릴지 묻는다.

## 하지 않는 것

- 기억 · 대화 흐름으로 다음 노드를 고르는 것 (언제나 `run.py next`)
- `trace/events.jsonl` · `state/state.json` · `evidence/` · `memory/` 를 손으로 고치거나 지우는 것
- 게이트 · 수용 기준 · 검사기를 약하게 만들어 통과시키는 것
- 사람의 답을 명령으로 남기지 않고 진행하는 것
