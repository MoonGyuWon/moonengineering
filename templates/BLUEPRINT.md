# BLUEPRINT — <프로젝트 이름> (만드는 법 카드)

> 양식: `templates/BLUEPRINT.md` · 요구사항(APPROVED) 다음, 플랜 전에 **반 쪽**으로 쓴다 · 정본은 ```harness 블록 · validate 9행.
> 묻는 것은 두 가지다: **완성품은 어떤 구조여야 하나** · **각 단위를 무엇으로 검증하나**. 개발 과정의 모양(체크리스트 / 그래프)과는 따로다.

## 1. 구조 판단 — 그래프로 만들 것인가

5개 중 **3개 이상이 참이면 그래프** (`graphrt.py` 런타임), 아니면 그 분야의 일반 구조. 판단은 요구사항에 근거한다.

| 칸 (`criteria`) | 질문 |
| --- | --- |
| `stages` | 단계가 3개 이상이고 단계마다 출력을 따로 평가할 수 있다 (노드별 골든셋이 가능하다) |
| `nondeterministic` | LLM · 외부 API 처럼 결과가 매번 달라질 수 있는 단계가 있다 |
| `repeated` | 반복해서 돈다 (입력이 많거나 매일 이상) — 실시간 로그 · 추적이 값을 한다 |
| `branching` | 중간 결과나 사람 승인에 따라 실행 도중 분기한다 |
| `resumable` | 오래 걸려 멈췄다 이어서 돌아야 한다 (사람 대기 포함) |

섞어도 된다: 웹앱(일반 구조) 안의 LLM 기능 하나만 그래프 — 그 폴더를 `program` 에 적는다.

## 2. 구조별 단위와 검증 — 단위 하나 = 계약 하나 = 검증 하나

| 구조 (`shape`) | 단위 | 계약 | 검증 (`verify`) |
| --- | --- | --- | --- |
| `graph` | 노드 (`nodes/<id>.py`) | 상태 필드 (`graph.json` 의 requires · writes) | `graphrt.py eval <노드>` 골든셋 + `eval` 전체 회귀 |
| `cli` | 명령 | 인자 · 출력 · 종료 코드 | 명령 실행 결과를 기대 출력과 비교 |
| `library` | 공개 함수 | 시그니처 · 예외 | 단위 + 속성 테스트 |
| `web` | API · 화면 | 스키마 (라우트 / 서비스 / 저장소 경계) | API 테스트 · e2e |
| `algorithm` | 함수 | 입력 · 출력 · 복잡도 목표 | 느리지만 확실한 오라클과 비교 · 속성 · 벤치마크 지표 |
| `pipeline` | 단계 스크립트 | 중간 파일 형식 | 지표(`harness/metric.py`) · 골든셋 · 기준선 회귀 |

수치로 판정하는 검증은 지표 JSON 을 만들고 `python harness/metric.py <metrics.json> "<경로> >= <값>" [--baseline <base.json>]` 로 게이트한다.
기준선 · 골든셋 · 임계값을 바꾸는 것은 사람이 결정한 뒤에만 (`--save-baseline --note` → DECISIONS) — 게이트를 약하게 만들지 않는다.

## 3. 카드

| 칸 | 값 |
| --- | --- |
| 구조 | |
| 판단 규칙 (참인 것) | |
| 이유 (규칙과 다르게 골랐다면 특히) | |
| 단위 목록 → 검증 | |
| 그래프면 프로그램 폴더 | |

```harness
{
  "kind": "blueprint",
  "shape": "graph",
  "criteria": {"stages": true, "nondeterministic": true, "repeated": true, "branching": false, "resumable": false},
  "reason": "",
  "program": "app/",
  "units": [{"id": "route", "verify": "golden/route.jsonl · accuracy >= 0.95"}],
  "verify": ["golden", "e2e"]
}
```
