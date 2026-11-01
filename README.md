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
4 만드는 법 카드 완성품 구조(그래프 프로그램 / 일반 구조) · 단위마다 검증 방법             graph-plan
4-b 플랜        S · M 체크리스트 (M 은 계약 먼저) · L 개발 그래프 (계약 → task 노드)
5 실행           단계 · 웨이브 → 게이트(종료 코드 · 지표) → 기록 · 문제가 생기면 역질문     graph-run
```

- **상태값만으로 돈다** — 노드는 `requires`(조건)를 선언한다. `pending` 이고 조건이 모두 참이면 ready, ready 집합이 곧 병렬 웨이브다.
- **역질문이 기본이다** — 실패 · 막힘 · 사람 승인 · 해석이 둘 이상이면 멈추고 5칸으로 묻는다. 답은 기록된다.
- **개발 과정은 가볍게** — S · M 은 체크리스트로 끝난다. 개발 그래프는 L(여러 모듈 · 부작용 승인 · 승인된 병렬)에서만.
- **완성품은 맞는 구조로** — 만드는 법 카드(`templates/BLUEPRINT.md`)의 5개 규칙 중 3개 이상이면 그래프 프로그램:
  `harness/runtime/graphrt.py`(파일 하나 · 표준 라이브러리)가 프로그램에 복사돼 하네스 없이 돈다 — 노드 하나 = 파일 하나 = 골든셋 하나,
  `eval` 로 노드만 · 전체 회귀, `serve` 로 실시간 로그 화면. 예: `examples/graph-demo`.
- **수치로 판정한다** — 정확도 · 지연 같은 지표는 `harness/metric.py` 가 임계값 · 기준선 회귀로 게이트한다 (0 통과 · 1 실패).
- **승인된 병렬** — 같은 웨이브의 노드끼리 파일이 겹치지 않으면(validate 8행) 하위 에이전트가 동시에 만들고, 바뀐 파일 ⊆ `files` 를 하네스가 본다.
- **도구 중립** — 규칙은 `AGENTS.md`, 스킬은 [Agent Skills 표준](https://agentskills.io/specification)의 `.agents/skills/`.

## 시작하는 법

하네스는 **한 폴더에만** 두고, 프로젝트에는 연결만 한다.

```bash
git clone <이 저장소> ~/moonengineering                      # 한 번
python ~/moonengineering/harness/install.py <내 프로젝트>    # 프로젝트마다 한 번 (git pull 뒤에는 다시 돌려 갱신)
python ~/moonengineering/harness/install.py <내 프로젝트> --check   # 프로젝트의 사본이 지금 하네스와 같은가
```

**이 PC 어디서나 쓰려면 (Claude Code 전역)** — 프로젝트마다 연결하지 않고 `~/.claude/skills` 에 한 번:

```bash
python ~/moonengineering/harness/install.py --global          # 갱신도 같은 명령 (git pull 뒤) · --check 로 확인
```

전역은 프로젝트에 아무것도 놓지 않는다 — 스킬이 시작할 때 하네스 폴더의 `AGENTS.md` 를 읽고, 산출물은 그때 연 폴더에 생긴다. 사용자 전역 `CLAUDE.md` 는 건드리지 않는다.

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
- 그림: `diagrams/*.md` 의 Mermaid 는 GitHub · GitLab · Obsidian 에서 바로, VS Code 는 Markdown Preview Mermaid Support 확장으로 보인다.

## 명령 · 문서가 있는 곳 (한 곳씩)

| 무엇 | 어디 |
| --- | --- |
| 규칙 (판단 먼저 · 목표 중심 · 역질문 · 그래프 규칙 · 종료 코드) | `AGENTS.md` |
| 실행 명령 전체 · 종료 코드 | `python harness/run.py -h` |
| 사람의 답을 남기는 명령 · 역질문 5칸 | `templates/ASK.md` |
| 노드 스펙의 모든 칸 | `templates/NODE.md` |
| 구조 검사 9행 | `python harness/validate.py -h` |
| 만드는 법 카드 (구조 판단 5규칙 · 구조별 단위와 검증) | `templates/BLUEPRINT.md` |
| 그래프 프로그램 런타임 (init · check · run · resume · eval · serve) | `python harness/runtime/graphrt.py -h` |
| 메트릭 게이트 (임계값 · 기준선 회귀) | `python harness/metric.py -h` |
| 그림 · 스킬 동기화 · 하네스 자체 검사 | `harness/render.py` · `sync_skills.py` · `selftest/run_selftest.py` |
| 출처 · 리허설 · 독립 검증 기록 | `docs/HISTORY.md` |

## 파일 지도

```text
AGENTS.md  CLAUDE.md  README.md
.agents/skills/      req-intake · graph-plan · graph-run — 정본
.claude/skills/      복사본 (sync_skills.py 가 만든다)
templates/           QUESTION_BANK · REQUIREMENTS · BLUEPRINT · CHECKLIST · GRAPH · NODE · ASK
harness/             spec · validate · run · render · metric · sync_skills · install(프로젝트 연결) · selftest/
harness/runtime/     graphrt.py — 그래프 프로그램 런타임 (프로그램에 복사된다)
examples/            리허설 — csv-summary (체크리스트) · todo-cli (개발 그래프) · graph-demo (그래프 프로그램)
docs/HISTORY.md

(하네스를 쓰는 프로젝트에 생기는 것)
specs/               REQUIREMENTS · BLUEPRINT · CHECKLIST(S · M) · GRAPH · nodes/ · contracts/ (L)
trace/events.jsonl   정본 — 모든 일이 한 줄씩 (seq)
state/state.json     이벤트를 접은 캐시 (`run.py rebuild`)
evidence/<노드>/     result.json · gate.log · cmd.log — 실행 · 시도마다
memory/              DECISIONS.md(사람이 고른 것) · TROUBLESHOOTING.md(증상 → 원인 → 조치)
diagrams/            graph · timeline (.md) — 자동 생성
```
