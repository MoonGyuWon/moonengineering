# ASK — 역질문 화면 (5칸)

문제가 생기면 이 모양으로 묻는다 (AGENTS.md 3절). 선택지 질문 도구가 있으면(예: Claude Code 의 AskUserQuestion) 질문 본문에 ①②를, 선택지에 ③④를 넣는다. 없으면 채팅에 5칸을 그대로 쓰고 답을 기다린다.

```text
① 지금    <노드 id> · <상태: FAIL / STUCK / waiting_human / BLOCKED> · <실행 N · 시도 M>
② 왜      <원인 요약 1~3줄 — 분류(transient · input · contract_violation · structural)>
          근거: evidence/<노드>/<rNNaMM>/gate.log · trace seq <N>
③ 권장    <첫 선택지> — <이유 한 줄, 지금 상황에서 계산한 것>
④ 고르기  <선택지 A>  → 고르면 일어나는 일 (어느 명령 · 어느 노드가 ready 가 되는지)
          <선택지 B>  → …
          <선택지 C>  → …
⑤ 답      action: <허용값 중 하나>   note: <자유 문장 — 기록만 된다>
```

## 답을 남기는 명령

| 상황 | 명령 |
| --- | --- |
| HUMAN 노드의 답 | `run.py answer <노드> --action <값> --note "…"` |
| JUDGE 저신뢰 확인 | `run.py answer <노드> --action accept` · `--action override --set 필드=값` |
| 실패한 노드를 다시 | `run.py reset <노드> --note "…"` |
| 예산 추가 | `run.py extend-budget <N> --note "…"` |
| 스펙 변경을 Run 에 반영 | `run.py migrate --note "…"` (먼저 graph-plan 으로 스펙 수정) |
| 그 밖의 결정 (범위 · 방향) | `run.py decide --topic "…" --choice "…" --options "a,b,c" --note "…"` |
| 영역 worktree 체크포인트 (승인 뒤) | `lanes.py checkpoint --dry-run`(목록을 ② 에) → 승인 → `run.py decide --topic "W0 체크포인트" --choice commit` → `lanes.py checkpoint --note "…"` |

## 자주 쓰는 선택지 묶음

- **노드 실패 (contract_violation)**: 고쳐서 다시(reset) · 스펙 수정(graph-plan → migrate) · 이 REQ 를 범위에서 뺌(decide) · 멈춤
- **STUCK (갈 곳 없음)**: 막힌 노드 reset · 처방 가지 추가(graph-plan) · 완료 조건 재검토(decide) · 멈춤
- **JUDGE 저신뢰**: 제안값 수락(accept) · 값을 바꿈(override) · 근거를 더 모아 다시 판단(reset)
- **예산 소진**: 예산 추가 · 범위 축소 · 멈춤
- **영역 병렬** — 병합 충돌 · 영역 밖 변경: 계약 수정(graph-plan → 양쪽 다시) · 한쪽만 다시(reset) · 사람이 손으로 병합 · 순차로 바꿈
- **영역 병렬** — 체크포인트 커밋(lanes.py checkpoint) 승인: 커밋하고 worktree 로 · 커밋하지 않고 같은 폴더(모드 A)로 · 멈춤
- **영역 병렬** — 병합 안 된 작업이 있는 close: 먼저 merge · 버린다(close --force) · 그대로 둔다
