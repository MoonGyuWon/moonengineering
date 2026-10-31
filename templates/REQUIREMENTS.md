# REQUIREMENTS — <프로젝트 이름>

> 양식: `templates/REQUIREMENTS.md` · 작성: `req-intake` · 정본은 맨 아래 ```harness 블록이다 (표는 읽기용).
> `status` 가 `APPROVED` 이고 `open_questions` 가 비어야 `validate.py` 7행이 통과한다.

## 0. 문제 이해

- 원문 요약: (사용자가 준 문제를 한두 줄로)
- 유형 · 규모: (예: CLI 도구 · M)
- 이번에 고른 질문: (Q1.1, Q2.2, … — `templates/QUESTION_BANK.md`)

## 1. 스테이크홀더

| id | 역할 | 쓰는가 · 결정하는가 · 영향받는가 | 성공이란 | 충돌 지점 |
| --- | --- | --- | --- | --- |
| SH1 | | | | |

## 2. GOAL · 최종 산출물

- GOAL:
- 산출물:
- 완료 판정: (`done_when` 으로 옮겨질 것)

## 3. 요구사항

| id | 내용 | 스테이크홀더 | 수용 기준 (값으로 판정) | 확인 방법 |
| --- | --- | --- | --- | --- |
| REQ-F1 | | SH1 | | code |
| REQ-N1 | | SH1 | | code |

## 4. 하지 않는 것

-

## 5. 불변 · 수정 권한

- 불변:
- 고쳐도 되는 것:

## 6. 종료 · 이관

- 멈추고 사람에게 넘기는 경우:
- 예산:

## 6-b. 도구 선정 (req-intake 3-b)

| 능력 | 고른 것 | 후보 | 이유 | 출처 (웹 확인 날짜 · URL / 알고 있는 정보 (확인 안 함)) |
| --- | --- | --- | --- | --- |

## 7. 가정표 (묻지 않고 기본값으로 채운 것)

| 질문 | 채운 값 | 이유 |
| --- | --- | --- |

## 8. 미결 질문

-

---

```harness
{
  "kind": "requirements",
  "status": "DRAFT",
  "scale": "M",
  "goal": "",
  "stakeholders": [
    {"id": "SH1", "role": "", "uses": true, "decides": true, "affected": false, "success": ""}
  ],
  "reqs": [
    {"id": "REQ-F1", "text": "", "stakeholders": ["SH1"], "acceptance": "", "verify": "code"}
  ],
  "out_of_scope": [],
  "invariants": [],
  "tools": [
    {"need": "", "reqs": ["REQ-F1"], "choice": "", "candidates": [], "reason": "", "source": "", "status": "undecided"}
  ],
  "assumptions": [],
  "open_questions": ["(질문이 남아 있으면 여기에 — 비어야 APPROVED 가능)"]
}
```
