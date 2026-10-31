# CHECKLIST — csv-summary (S 규모 · 체크리스트 모드)

| 단계 | 할 일 | 확인 (값으로) | REQ | 결과 |
| --- | --- | --- | --- | --- |
| S1 | `src/summarize.py` 의 `summarize(rows)` 구현 + `tests/test_summary.py` | `python -m unittest tests.test_summary` exit 0 | REQ-F1 · REQ-F2 | 1회째 exit 1 (`tests/__init__.py` 없음 → 모듈 못 찾음) → 추가 후 exit 0 · 3 tests OK (15:22) |
| S2 | CLI 로 md 생성 | 아래 check 명령 exit 0 (`행 수: 4` 포함) | REQ-F3 | 1회째 확인 명령이 틀림(findstr 경로 · 한글) → python 확인으로 바꿔 exit 0 (15:22) |

```harness
{
  "kind": "checklist",
  "steps": [
    {"id": "S1", "do": "summarize(rows) 구현 + 단위 테스트", "check": "python -m unittest tests.test_summary", "reqs": ["REQ-F1", "REQ-F2"],
     "result": "exit 0 · 3 tests OK (1회째 tests/__init__.py 누락으로 exit 1)"},
    {"id": "S2", "do": "CLI 로 md 생성",
     "check": "python src/summarize.py data/sample.csv out/summary.md && python -c \"import sys;sys.exit(0 if '행 수: 4' in open('out/summary.md',encoding='utf-8').read() else 1)\"",
     "reqs": ["REQ-F3"], "result": "exit 0 (1회째 findstr 확인 명령이 틀려 python 확인으로 교체)"}
  ]
}
```
