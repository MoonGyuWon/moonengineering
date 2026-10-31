# 계약 — todo (W0 · 비 task 스펙 · 잠김)

task 노드들은 **이 문서에만** 기댄다. 서로의 구현을 보지 않는다. 바꾸려면 graph-plan change (graph_version +1, 이 계약을 읽는 task 는 전부 다시).

## 데이터 (저장 파일)

UTF-8 JSON, `ensure_ascii=False`. 파일이 없으면 빈 목록으로 본다.

```json
[{"id": 1, "title": "우유 사기", "done": false}]
```

- `id`: 1부터, 지금 최대 id + 1
- `title`: 그대로 저장 (앞뒤 공백만 제거)

## `todo/store.py` (T01)

| 함수 | 동작 |
| --- | --- |
| `load(path) -> list[dict]` | 파일 없으면 `[]` |
| `add(path, title) -> dict` | 새 항목을 저장하고 돌려준다 |
| `mark_done(path, id) -> dict` | 없는 id 면 `KeyError` |

## `todo/format.py` (T02)

| 함수 | 동작 |
| --- | --- |
| `render(items) -> str` | 줄마다 `[ ] <id> <title>` 또는 `[x] <id> <title>`, 빈 목록이면 `(할 일 없음)` |

## CLI `python -m todo --file <경로> <명령>` (T03)

| 명령 | 출력 | exit |
| --- | --- | --- |
| `add <제목>` | `추가: <id> <제목>` | 0 |
| `list` | `render()` 결과 | 0 |
| `done <id>` | `완료: <id>` | 0 · 없는 id 는 stderr `없는 id: <id>` + exit 2 |

stdout 은 UTF-8 로 쓴다 (Windows 콘솔 cp949 에서도 한글이 깨지지 않게 `sys.stdout.reconfigure(encoding="utf-8")`).

## 수용 테스트 (W0 에서 먼저 씀 — 구현 전에는 빨간불)

`tests/test_store.py` (T01 게이트) · `tests/test_format.py` (T02 게이트) · `tests/test_cli.py` (T03 게이트) · `tools/accept.py` (C04 · 전체 시나리오)
