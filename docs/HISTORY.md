# HISTORY — 어디서 왔고, 어떻게 검증했나

## 어디서 왔나

| 출처 | 가져온 것 |
| --- | --- |
| `loop_practice` | 8문항(→ 질문 은행) · "질문할 것 / 기본값으로 채울 것" · 가정표 · 완료 정의 · 값으로 판정하는 게이트 · 증거 4원칙 · 불변 · 문제 최대 3개 검토 |
| `graph_starter_kit` | 진단 → 처방 가지(fix → 검사기 복귀 · 한도) · 게이트 5칸 화면 · `action` 만 분기 · "한 번은 일화, 세 번은 패턴" · 검사기를 검사한다 · 종료 코드 0/1/2 · 그래프 규칙 |
| Graph Engineering (Simmons 정의 · [zenn 요약](https://zenn.dev/suwash/articles/graph-engineering_20260727?locale=en)) | 엣지 = 경계 계약 · 루프는 노드 안으로 · 노드 생명주기 10상태 · 실패 사다리 · 이벤트가 감사 기준 · Run 의 버전 고정 · 1~3단계는 그래프가 손해 |
| [LangGraph Graph API](https://docs.langchain.com/oss/javascript/langgraph/graph-api) | superstep(준비된 노드 = 같은 걸음 병렬) · 필드별 reducer |
| [Stately Agent](https://stately.ai/docs/packages/agent/xstate-as-agent-workflow) | 상태 기계가 결정하고 호스트가 실행 · 조건은 코드가 아닌 데이터 |
| JEV ([1](https://daleseo.com/jev/) · [2](https://www.eigent.ai/ko/blog/typesafe-ai-jev-system-one-models)) | 판단은 타입이 정해진 답(choice · score · noul) + 신뢰도, 분기는 코드 — API 는 쓰지 않고 패턴만 |

버린 것: LangGraph · Studio · LangSmith · 여행 도메인 · 결정 13개 교육 흐름 · 세션/회차 루프 · p4 · 메타 스킬 · 정성 3회 고정.

## 리허설 기록 (2026-10-31)

인터뷰(0~3단계)는 가상의 사용자 답으로 채웠다. 실행은 실제로 돌렸다.

| | csv-summary (S · 체크리스트) | todo-cli (M · 그래프) |
| --- | --- | --- |
| 문서 | 2장 (REQUIREMENTS · CHECKLIST) | REQUIREMENTS · GRAPH · 계약 1 · 노드 6 |
| 실행 시간 | 약 1분 (15:22:06 → 15:22:57) | 약 5분 (Run 시작 15:25:03 → DONE 15:28:24) |
| 웨이브 | — | W1 병렬(T01 · T02, 서브에이전트 2) → T03 → C04 → H05(사람) → T06 |
| 실패 | 2건 — `tests/__init__.py` 누락 · 확인 명령(findstr) 오류 | T03 2건 — cp949 출력(일부러 넣음) · `\r\n` 줄끝(실제 실패 · 계약 문서의 구멍) → retry 안에서 자동 처리 |
| 역질문 | — | H05 배포 승인 1회 (실제 사용자에게) → `memory/DECISIONS.md` seq 22 |
| 검증 | validate PASS | validate PASS · DONE · state.json 삭제 후 rebuild · T06 재실행 거부(멱등) |

추적: `examples/todo-cli/diagrams/timeline.md` → seq → `trace/events.jsonl` · `evidence/T03-cli/r01a0N/gate.log` · `memory/*.md`.

## 독립 검증 (2026-10-31 · Fable)

읽기 전용으로 검토했다. selftest · validate · sync_skills 는 통과했고, 결함 11건과 덜어낼 후보 · 루프 점검을 받았다. 반영한 것은 다음과 같다.

| 지적 | 반영 |
| --- | --- |
| 부작용 승인을 `exists` 로 걸면 거절해도 배포된다 (높음) | validate 8행 — 승인 필드는 `== <승인 값>` 만. `exists` · `!=` · `in` 은 ERROR |
| `gate.pass` 형식 오류 · 깨진 `HARNESS_WRITES` · 하네스 예외 → 노드가 running 에 고착 | validate 1행 형식 검사 · 깨진 쓰기는 실패로 기록 · 모든 예외에서 running 노드를 failed(structural) 로 남기고 역질문 |
| ready 없이 running 만 있으면 `next` 가 exit 0 으로 헛돈다 | exit 2 + 역질문 · reset 이 running · waiting_human 도 받는다 |
| exit 1 이 "ERROR" 와 "자동 재시도" 두 뜻 | 자동 재시도는 exit 3 으로 분리 |
| cmd 실패를 무조건 transient 로 분류 | 기본 contract_violation · 스펙의 `transient_exit` 에 적힌 코드만 transient |
| 상한 없는 루프: graph-plan 의 스펙 수정 · req-intake 라운드 · "검증될 때까지 반복" | 스펙 수정 3회 · 질문 라운드 3회 뒤 역질문 · AGENTS.md 2절에 한도 문구 추가 |
| reset · extend-budget 를 에이전트가 불러도 막히지 않는다 | 코드로는 못 막는 신뢰 경계로 명시 (AGENTS.md 3절 · run.py 머리말) — 모두 DECISIONS 에 남는다 |
| 증거 경로가 Windows 역슬래시 · run_id 겹침 가능 | `as_posix()` 통일 · 같은 초 run_id 에 번호를 붙인다 |
| 덜어내기 | `fork` · `counter` 삭제 · `writes_optional` → note_field 자동 예외 · 명령은 ASK.md / `run.py -h`, 처방 가지는 NODE.md 한 곳으로 |

## 2차 검증 · 폴더 단위 병렬 (2026-10-31 · Fable)

1차 수정 10건 가운데 9건 확인, 1건(깨진 쓰기)은 경로가 남아 있었다. 남은 결함과 반영:

| 지적 | 반영 |
| --- | --- |
| 형이 틀린 `HARNESS_WRITES` → running 고착 | 쓰기 검사 실패도 노드 실패(contract_violation) |
| `missing` 조건 · 주인이 여럿인 필드를 순서로 봐서 병렬 충돌을 놓침 (상) | 8행이 순서를 보장하는 간선만 센다 |
| `./a` ↔ `a`, `out/` ↔ `out/a.json` 겹침을 못 잡음 | `spec.norm_path` · `paths_overlap` (폴더 · `**` 접두어) |
| 입력 실수까지 structural 실패로 기록 | 깨진 `--answers` · `--set-json` 은 입력 오류(exit 1) — 노드는 그대로 |
| 사람 대기가 다른 가지의 ready 를 가림 | 대기와 함께 ready 를 보여 준다 — 묻고 나서 진행 (사람이 정함) |
| 거절 값(`== stop`)도 승인으로 통과 | HUMAN `human.approve` — 부작용은 그 값으로만 |
| M/L 인데 `tools` 가 없어도 통과 | 7행 SHORT |
| DONE 때 running 노드를 그대로 둠 · `--evidence` 경로 · layers 밖 계층 | cancelled 로 닫음 · posix · 8행 ERROR + 그림에서 빠뜨리지 않음 |

폴더 단위 병렬(설계 제안 → 사람이 "전부" 선택): `areas` · 노드 `area` · validate 9행 · `gate.cwd` · `begin` 실행 중 겹침 거부 ·
`finish --changed / --lane` · `harness/lanes.py`(체크포인트 · 영역 worktree · 영역 root 만 병합) · 그림의 영역 묶음과 진행표.
selftest 103개 (frontend/backend 형 그래프를 같은 폴더 · worktree 두 모드로 끝까지).

## 설치 방식 (2026-10-31)

사람이 "한 곳 설치 + 연결"을 골랐다. `harness/install.py` 가 프로젝트에 스킬 사본(경로를 설치 폴더로 바꾼 것) · AGENTS.md 블록 · CLAUDE.md 줄 · .harness.json 을 놓는다. 프로젝트에 하네스 전체를 복사하지 않는다.

## 3차 검증 (2026-10-31 · Fable)

2차 반영분은 대부분 확인. 새 기능(바뀐 파일 검사 · worktree · install)에서 결함 11건 — 사람이 "전부 고침 + 덜어내기"를 골랐다.

| 지적 | 반영 |
| --- | --- |
| `--changed ./` · `web/` · `web/../api` 가 통과 (상) | `spec.contained` — 바뀐 파일은 파일만 · `..` 거부. files · 영역 root 의 `..` 는 validate ERROR |
| `--lane` 이 시점 · 영역과 무관한 "마지막 병합"을 읽음 (상) | `--lane` 삭제 (덜어내기). `lanes.py merge` 가 `--changed` 목록을 출력 · 변경 0개 병합은 exit 2 |
| close 가 병합 안 된 작업을 지움 (상) | 거부 · `--force` 는 사람이 정했을 때만 |
| reopen 이 옛 체크포인트에서 출발 | 지금 메인 HEAD 에서 연다 |
| 체크포인트가 trace · state 까지 커밋 (git 이 정본을 되돌릴 수 있음) · 비밀 파일 | 하네스 기록 제외 · 비밀로 보이는 파일이면 멈춤 · `--dry-run` 목록을 역질문에 먼저 |
| 공백 경로를 영역 밖으로 오판 | `status --porcelain -z` |
| 웨이브 첫 노드 finish 마다 불필요한 역질문 | finish 직후 next 는 형제가 진행 중이면 exit 0 |
| AGENTS.md 표시 짝이 안 맞으면 사용자 내용 소실 | install 이 멈춘다 |
| 연결된 프로젝트에서 상대 경로 안내 · `.harness.json` commit 이 실제 버전과 다름 | 안내는 설치 폴더 절대 경로 · `dirty: true` 기록 |

모드 B 는 "사람이 고를 때만"으로 낮췄다. selftest 127개.

## 전역 연결 (2026-10-31)

사람이 "이 PC 어디서나"를 원했다. `install.py --global` — `~/.claude/skills` 에 스킬 사본(스크립트 · 양식 · AGENTS.md 를 설치 폴더 경로로). 전역 CLAUDE.md 는 건드리지 않는다. `--with-agents` 는 `~/.agents/skills` 에도. selftest 132개.

## 방향 전환 · 덜어내기 (2026-11-01 · Fable 검증 뒤 사람이 확정)

사람의 목표: "어디서든 쓰이는 작고 가볍고 강력한 개발 하네스". 개발 과정은 그래프일 필요가 없고, 하네스는 **완성품**이 그래프 구조가 맞는지 다른 구조가 맞는지 판단해 그에 맞게 만든다.

| 더한 것 | 내용 |
| --- | --- |
| 만드는 법 카드 | `templates/BLUEPRINT.md` · validate 9행 — 5개 판단 규칙 중 3개 이상이면 그래프 프로그램 · 단위 하나 = 계약 하나 = 검증 하나 |
| 그래프 프로그램 런타임 | `harness/runtime/graphrt.py` — 파일 하나 · init · check · run · resume · eval(노드별 + e2e 골든셋) · serve(SSE 실시간 로그 HTML) · 예: `examples/graph-demo` |
| 메트릭 게이트 | `harness/metric.py` — 임계값 · 기준선 회귀 · 기준선 갱신은 note + DECISIONS |
| 규모 재정의 | S · M 은 체크리스트(M 은 계약 먼저) · 개발 그래프는 L 만 |

| 덜어낸 것 (개발 그래프 기계) | 대신 |
| --- | --- |
| 영역 병렬 `areas` · `lanes.py`(worktree) | 같은 웨이브의 files 분리(validate 8행 + begin) · `--changed` · `gate.cwd` 는 그대로 |
| JUDGE 노드(JEV · confidence) | AGENT 노드가 enum 으로 쓰고 게이트가 잰다 · 사람 확인은 HUMAN |
| reducer | 필드 하나에 주인 하나 — 필드를 나눈다 |
| 처방 가지(`rerun_on` · `max_runs`) · `report.py` | 노드 사이 순환 없음 · 실패하면 역질문 → reset 또는 graph-plan |
| `graph_version` · migrate · `impl` | 스펙이 바뀌면 사람이 reset 또는 새 Run |
| 계층 그림 · `diagrams/index.html` · `install --with-agents` | `graph.md` · `timeline.md` 만 |

selftest 111개 (지운 기능의 검사만 빠짐) · `PYTHONUTF8` 없이도 통과 (cp949 문제는 report.py 검사에 있었다).
