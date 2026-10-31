# TROUBLESHOOTING — 증상 → 원인 → 조치

> 실패가 나면 하네스가 증상 줄을 덧붙인다. 원인 · 조치 칸은 해결한 뒤 채운다.
> 같은 증상이 서로 다른 Run 3곳 이상이면 패턴 — `python harness/report.py` 로 본다.

## 2026-10-31T15:26:18 · T03-cli · failed_retryable

| 칸 | 값 |
| --- | --- |
| Run | run-20261031-152503 |
| 증상 | 게이트 exit 1 (기대 0) — evidence\T03-cli\r01a01\gate.log |
| 분류 | contract_violation |
| 증거 | evidence\T03-cli\r01a01\result.json, evidence\T03-cli\r01a01\gate.log |
| 이벤트 | seq 10 |
| 원인 | Windows 에서 파이프로 나가는 stdout 기본 인코딩이 cp949 → 테스트가 UTF-8 로 읽다 `UnicodeDecodeError` (리허설: 1회째 구현에서 계약의 UTF-8 처리를 일부러 뺌) |
| 조치 | `todo/cli.py` 에서 `sys.stdout.reconfigure(encoding="utf-8")` — 노드 retry 안에서 자동 처리 |

## 2026-10-31T15:26:31 · T03-cli · failed_retryable

| 칸 | 값 |
| --- | --- |
| Run | run-20261031-152503 |
| 증상 | 게이트 exit 1 (기대 0) — evidence\T03-cli\r01a02\gate.log |
| 분류 | contract_violation |
| 증거 | evidence\T03-cli\r01a02\result.json, evidence\T03-cli\r01a02\gate.log |
| 이벤트 | seq 12 |
| 원인 | Windows 줄 끝 `\r\n` — 수용 테스트(W0)는 `\n` 을 요구. **계약 문서에 줄바꿈이 적혀 있지 않았다** (스펙 구멍 — 계획에 없던 실제 실패) |
| 조치 | `reconfigure(..., newline="\n")` 로 3회째 PASS. 다음 graph_version 에서 계약에 "줄 끝은 \n" 을 적을 것 |

