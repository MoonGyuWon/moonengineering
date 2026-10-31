# REQUIREMENTS — csv-summary (리허설 S)

> ⚠ 하네스 리허설용이다. 인터뷰 답은 **가상의 사용자 답**으로 채웠다 (2026-10-31, Claude 가 사용자 역할).

## 0. 문제 이해

- 원문 요약: "CSV 파일을 주면 열별 요약(행 수 · 숫자 열 평균/최소/최대 · 범주 열 빈도)을 md 로 뽑아 줘"
- 유형 · 규모: 데이터 처리 스크립트 · **S** (단계 2개 · 분기 없음 · 사람 승인 분기 없음)
- 고른 질문: Q1.1 · Q1.2 · Q2.1 · Q3.2 · Q4.1 (A 등급만). C 등급 Q5.1 은 가정표로.

## 1. 스테이크홀더

| id | 역할 | 쓰는가 · 결정하는가 · 영향받는가 | 성공이란 | 충돌 지점 |
| --- | --- | --- | --- | --- |
| SH1 | 요청자(분석가) | 쓴다 · 결정한다 | 명령 한 줄로 요약 md 가 나온다 | 없음 |

## 2. GOAL · 최종 산출물

- GOAL: CSV 하나를 넣으면 요약 md 하나가 나온다
- 산출물: `out/summary.md`

## 3. 요구사항

| id | 내용 | 수용 기준 | 확인 |
| --- | --- | --- | --- |
| REQ-F1 | 숫자 열은 평균 · 최소 · 최대 | `tests/test_summary.py` 의 숫자 열 테스트 통과 | code |
| REQ-F2 | 범주 열은 값별 빈도 | 같은 테스트 파일의 범주 열 테스트 통과 | code |
| REQ-F3 | `python src/summarize.py <csv> <md>` 한 줄로 md 생성 | 명령 exit 0 · `out/summary.md` 에 `행 수: 4` 포함 | code |

## 4. 하지 않는 것

- 그래프 · 차트 · 여러 파일 합치기

## 7. 가정표

| 질문 | 채운 값 | 이유 |
| --- | --- | --- |
| Q5.1 실행 환경 | Python 3 표준 라이브러리 · UTF-8 CSV | 이 PC 에 Python 3.12 |

```harness
{
  "kind": "requirements",
  "status": "APPROVED",
  "scale": "S",
  "goal": "CSV 하나를 넣으면 요약 md 하나가 나온다",
  "stakeholders": [{"id": "SH1", "role": "요청자(분석가)", "uses": true, "decides": true, "affected": false, "success": "명령 한 줄로 요약 md"}],
  "reqs": [
    {"id": "REQ-F1", "text": "숫자 열 평균·최소·최대", "stakeholders": ["SH1"], "acceptance": "tests/test_summary.py 숫자 열 테스트 통과", "verify": "code"},
    {"id": "REQ-F2", "text": "범주 열 빈도", "stakeholders": ["SH1"], "acceptance": "tests/test_summary.py 범주 열 테스트 통과", "verify": "code"},
    {"id": "REQ-F3", "text": "명령 한 줄로 md 생성", "stakeholders": ["SH1"], "acceptance": "exit 0 · out/summary.md 에 '행 수: 4'", "verify": "code"}
  ],
  "out_of_scope": ["차트", "여러 파일 합치기"],
  "invariants": ["data/sample.csv 는 고치지 않는다"],
  "assumptions": [{"q": "Q5.1", "value": "Python 3 표준 라이브러리 · UTF-8"}],
  "open_questions": []
}
```
