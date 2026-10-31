# REQUIREMENTS — todo-cli (리허설 M)

> ⚠ 하네스 리허설용이다. 인터뷰 답은 **가상의 사용자 답**으로 채웠다 (2026-10-31, Claude 가 사용자 역할).
> 단, 릴리스 승인(H05)은 실제 사용자에게 역질문한다.

## 0. 문제 이해

- 원문 요약: "터미널에서 쓰는 할 일 관리 도구. 추가 · 목록 · 완료. 한글 제목이 깨지면 안 되고, 배포 전에 내가 확인하고 싶다"
- 유형 · 규모: CLI 도구 · **M** (노드 6 · 사람 승인 분기 · 독립 모듈 2개 → 병렬 웨이브 가능)
- 고른 질문: A — Q1.1 · Q1.2 · Q2.1 · Q2.2 · Q3.1 · Q3.2 · Q3.3 · Q4.1 / B — Q5.1 · Q5.4 · Q8.3. C(가정표) — Q7.2.

## 1. 스테이크홀더

| id | 역할 | 쓰는가 · 결정하는가 · 영향받는가 | 성공이란 | 충돌 지점 |
| --- | --- | --- | --- | --- |
| SH1 | 사용자 | 쓴다 | 명령 세 개로 할 일을 관리하고 한글이 안 깨진다 | 빨리 쓰고 싶다 ↔ SH2 의 확인 절차 |
| SH2 | 릴리스 승인자 (같은 사람, 다른 역할) | 결정한다 | 수용 시나리오가 통과한 것만 배포된다 | (충돌은 "배포 전 승인 1회"로 정리 — 사람이 고름) |

## 2. GOAL · 최종 산출물

- GOAL: `python -m todo` 로 add · list · done 이 되는 도구를 만들고, 승인 후 `dist/todo-cli-v1/` 로 배포한다
- 완료 판정: `release.status == done`

## 3. 요구사항

| id | 내용 | 수용 기준 (값으로) | 확인 |
| --- | --- | --- | --- |
| REQ-F1 | `add "<제목>"` → id 가 붙은 항목 추가 | `tests.test_cli` add 테스트 · `tools/accept.py` 시나리오 | code |
| REQ-F2 | `list` → `[ ] 1 제목` / `[x] 2 제목` | `tests.test_format` · accept 시나리오 | code |
| REQ-F3 | `done <id>` → 완료 표시 · 없는 id 는 exit 2 + 메시지 | `tests.test_cli` done 테스트 | code |
| REQ-N1 | 저장 파일 JSON · UTF-8 · 한글 제목 보존 | `tests.test_store` 한글 왕복 테스트 | code |
| REQ-F4 | 배포 전 사람 승인 · 승인 후에만 `dist/` 생성 | H05 승인 기록(DECISIONS) · `dist/todo-cli-v1/todo/cli.py` 존재 | human |

## 4. 하지 않는 것

- 마감일 · 우선순위 · 삭제 · 여러 사용자 · 외부 의존성

## 5. 불변 · 수정 권한

- 불변: `specs/contracts/todo.md` 의 데이터 모양과 API (바꾸려면 graph-plan change)
- 고쳐도 되는 것: 노드 스펙의 `files` 만

## 6. 종료 · 이관

- 사람이 배포를 멈추면(stop) STOPPED
- 예산: 시도 20

## 7. 가정표

| 질문 | 채운 값 | 이유 |
| --- | --- | --- |
| Q5.1 환경 | Python 3 표준 라이브러리 | 의존성 0 요구 |
| Q7.2 예산 | 시도 20 | 노드 6 × 여유 |
| Q8.3 병렬 | W1(store · format)만 병렬 | 서로 파일 · 필드가 겹치지 않음 |

```harness
{
  "kind": "requirements",
  "status": "APPROVED",
  "scale": "M",
  "goal": "python -m todo 로 add · list · done, 승인 후 dist/ 배포",
  "stakeholders": [
    {"id": "SH1", "role": "사용자", "uses": true, "decides": false, "affected": false, "success": "명령 세 개 · 한글 안 깨짐"},
    {"id": "SH2", "role": "릴리스 승인자", "uses": false, "decides": true, "affected": false, "success": "수용 시나리오 통과한 것만 배포"}
  ],
  "reqs": [
    {"id": "REQ-F1", "text": "add", "stakeholders": ["SH1"], "acceptance": "tests.test_cli add · tools/accept.py", "verify": "code"},
    {"id": "REQ-F2", "text": "list 형식", "stakeholders": ["SH1"], "acceptance": "tests.test_format · tools/accept.py", "verify": "code"},
    {"id": "REQ-F3", "text": "done · 없는 id exit 2", "stakeholders": ["SH1"], "acceptance": "tests.test_cli done", "verify": "code"},
    {"id": "REQ-N1", "text": "JSON UTF-8 한글 보존", "stakeholders": ["SH1"], "acceptance": "tests.test_store 한글 왕복", "verify": "code"},
    {"id": "REQ-F4", "text": "승인 후 배포", "stakeholders": ["SH2"], "acceptance": "DECISIONS 에 H05 승인 · dist/todo-cli-v1/todo/cli.py 존재", "verify": "human"}
  ],
  "out_of_scope": ["마감일", "우선순위", "삭제", "여러 사용자", "외부 의존성"],
  "invariants": ["specs/contracts/todo.md"],
  "assumptions": [{"q": "Q5.1", "value": "표준 라이브러리"}, {"q": "Q7.2", "value": "시도 20"}, {"q": "Q8.3", "value": "W1 병렬"}],
  "tools": [{"need": "CLI 인자 · JSON 저장 · 테스트", "reqs": ["REQ-F1", "REQ-N1"], "choice": "argparse · json · unittest (표준 라이브러리)", "candidates": ["표준 라이브러리", "click + pytest"], "reason": "의존성 0 요구 (Q5.1)", "source": "알고 있는 정보 (확인 안 함) — 리허설 가정", "status": "decided"}],
  "open_questions": []
}
```
