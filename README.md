# moonengineering — 상태값으로 도는 범용 노드 그래프 하네스

**요구사항을 끝까지 받아내고, 계약을 먼저 정해 잘게 쪼갠 노드를, 상태값만으로 실행하고, 사람이 처음부터 끝까지 추적할 수 있게 한다.**

프레임워크 없이 **md 스펙 + Python 표준 라이브러리 스크립트 + 스킬**로 돈다. 회차 루프는 없고 실행 단위는 노드다. 반복은 노드 안에 한도와 함께만 둔다.

## 흐름

```text
0 문제 읽기      규모 S / M / L                                                req-intake
1 질문 선정      질문 은행에서 이 문제에 필요한 질문만 골라 목록을 먼저 승인
2 스테이크홀더   누가 쓰고 · 결정하고 · 영향받는가 · 충돌 지점
3 요구사항       REQ 마다 값으로 판정되는 수용 기준 · 미결 질문 0 → APPROVED
3-b 도구 선정    필요한 능력마다 후보 비교(웹 확인 / 알고 있는 정보 구분) → 사람이 고름
4 플랜 · 스펙    계약(상태 스키마 · 인터페이스 · 수용 테스트) 먼저 → task 노드          graph-plan
5 실행           ready 웨이브 → 게이트 → 이벤트 → 그림 · 문제가 생기면 역질문           graph-run
```

- **상태값만으로 돈다** — 노드는 `requires`(조건)를 선언한다. `pending` 이고 조건이 모두 참이면 ready, ready 집합이 곧 병렬 웨이브다.
- **역질문이 기본이다** — 실패 · 막힘 · 저신뢰 판단 · 해석이 둘 이상이면 멈추고 5칸으로 묻는다. 답은 기록된다.
- **가볍다** — S 규모(1~3단계)는 그래프 없이 체크리스트 한 장으로 끝난다.
- **폴더 단위 병렬** — `web/` · `api/` 처럼 영역을 나누면 계약(W0) 뒤 영역마다 하위 에이전트가 동시에 만들고 통합 노드가 합친다. 기본은 같은 폴더, 빌드가 부딪히면 사람이 골라 영역별 git worktree.
- **도구 중립** — 규칙은 `AGENTS.md`, 스킬은 [Agent Skills 표준](https://agentskills.io/specification)의 `.agents/skills/`.

## 시작하는 법

하네스는 **한 폴더에만** 두고, 프로젝트에는 연결만 한다.

```bash
git clone <이 저장소> ~/moonengineering                      # 한 번
python ~/moonengineering/harness/install.py <내 프로젝트>    # 프로젝트마다 한 번 (git pull 뒤에는 다시 돌려 갱신)
python ~/moonengineering/harness/install.py <내 프로젝트> --check   # 프로젝트의 사본이 지금 하네스와 같은가
```

install 이 프로젝트에 놓는 것: `.agents/skills/` · `.claude/skills/`(스킬 사본 — 스크립트는 설치 폴더 경로로 부른다) ·
`AGENTS.md` 의 하네스 블록(원래 내용은 그대로) · `CLAUDE.md` 의 `@AGENTS.md` · `.harness.json`(설치 폴더 · 커밋).
**AI 도구는 스킬을 정해진 위치(프로젝트 · 사용자 전역)에서만 읽기 때문에** 스킬 사본은 프로젝트에 두고, 스크립트 · 양식은 설치 폴더에서 부른다.
그 뒤 AI 도구를 프로젝트에서 열고 `req-intake` 스킬로 시작한다. 각 스킬이 다음 스킬을 안내한다.

| 도구 | 규칙 파일 | 스킬을 읽는 곳 | 스킬 호출 |
| --- | --- | --- | --- |
| Codex | `AGENTS.md` | `.agents/skills/` | `$req-intake` · `/skills` |
| Gemini CLI | 기본은 `GEMINI.md` — `AGENTS.md` 는 설정이 필요할 수 있다 (미검증) | `.agents/skills/` (`.gemini/skills/` 의 별칭) | 스킬 목록에서 선택 |
| Claude Code | `CLAUDE.md` → `@AGENTS.md` | `.claude/skills/` (복사본) | `/req-intake` |
| 그 밖 | `AGENTS.md` 를 읽게 한다 | `.agents/skills/<이름>/SKILL.md` 를 직접 읽게 한다 | — |

- (하네스를 고칠 때) 스킬은 이 저장소의 `.agents/skills/` 만 고치고 `python harness/sync_skills.py` 로 `.claude/skills/` 를 다시 만든다. 연결된 프로젝트는 install 을 다시 돌린다.
- `python` 은 이 PC 의 Python 3 (macOS/Linux 는 보통 `python3`). 노드 스펙의 명령에는 `{python}` 을 쓴다.
- 그림: `diagrams/*.md` 의 Mermaid 는 GitHub · GitLab · Obsidian 에서 바로, VS Code 는 Markdown Preview Mermaid Support 확장으로 보인다. 못 그리는 곳이면 `diagrams/index.html` 을 브라우저로.

## 명령 · 문서가 있는 곳 (한 곳씩)

| 무엇 | 어디 |
| --- | --- |
| 규칙 (판단 먼저 · 목표 중심 · 역질문 · 그래프 규칙 · 종료 코드) | `AGENTS.md` |
| 실행 명령 전체 · 종료 코드 | `python harness/run.py -h` |
| 사람의 답을 남기는 명령 · 역질문 5칸 | `templates/ASK.md` |
| 노드 스펙의 모든 칸 · 처방 가지 모양 | `templates/NODE.md` |
| 구조 검사 8행 | `python harness/validate.py -h` |
| 그림 · 실패 집계 · 스킬 동기화 · 하네스 자체 검사 | `harness/render.py` · `report.py` · `sync_skills.py` · `selftest/run_selftest.py` |
| 폴더 단위 병렬 (frontend/backend 등) | 설계 `graph-plan` B1 "영역 분할" · 실행 `graph-run` "병렬 웨이브" · worktree `python harness/lanes.py -h` |
| 출처 · 리허설 · 독립 검증 기록 | `docs/HISTORY.md` |

## 파일 지도

```text
AGENTS.md  CLAUDE.md  README.md
.agents/skills/      req-intake · graph-plan · graph-run — 정본
.claude/skills/      복사본 (sync_skills.py 가 만든다)
templates/           QUESTION_BANK · REQUIREMENTS · CHECKLIST · GRAPH · NODE · ASK
harness/             spec · validate · run · render · report · sync_skills · lanes(영역 worktree) · install(프로젝트 연결) · selftest/
examples/            리허설 — csv-summary (S) · todo-cli (M)
docs/HISTORY.md

(하네스를 쓰는 프로젝트에 생기는 것)
specs/               REQUIREMENTS · GRAPH · nodes/ · contracts/ · CHECKLIST(S)
trace/events.jsonl   정본 — 모든 일이 한 줄씩 (seq)
state/state.json     이벤트를 접은 캐시 (`run.py rebuild`)
evidence/<노드>/     result.json · gate.log · cmd.log — 실행 · 시도마다
memory/              DECISIONS.md(사람이 고른 것) · TROUBLESHOOTING.md(증상 → 원인 → 조치)
diagrams/            graph · architecture · timeline (.md) · index.html — 자동 생성
```
