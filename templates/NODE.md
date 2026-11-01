# <노드 id> — <한 줄 이름>

> 양식: `templates/NODE.md` · 노드 하나 = 파일 하나 (`specs/nodes/<id>.md`) · 정본은 ```harness 블록.
> id 규칙: 종류 접두어 + 번호 + 이름 — `T`(task: CODE/AGENT) · `C`(검사기) · `H`(HUMAN).

| 칸 | 값 |
| --- | --- |
| 종류 | CODE · AGENT · HUMAN |
| 맡은 REQ | |
| 준비 조건 (`requires`) | 이 조건들이 모두 참이면 ready — 계약 필드에만 건다 |
| 쓰는 필드 (`writes`) | 이 노드가 주인인 필드만 |
| 고치는 파일 (`files`) | 이 밖은 고치지 않는다. 파일(`a/b.py`) · 폴더(`web/` — 끝의 `/`) · `web/src/**`. 같은 웨이브의 다른 노드와 겹치지 않는다 |
| 게이트 | 명령 · 통과 기준 (값으로) |
| 실패 처리 | retry(일시적 오류 · 노드 안의 수정 반복) · 그 밖은 역질문 |
| 하지 않는 것 | |

## 하는 일

(에이전트가 이 노드에서 할 일 — 입력을 어디서 읽고, 무엇을 만들고, 무엇을 쓰는가)

## 종류별 칸

- **게이트 폴더**: `"gate": {"cmd": "npm test", "cwd": "web"}` — 하위 폴더에서 테스트할 때. 프로젝트 안 상대 경로만.
- **바뀐 파일 확인**: 병렬로 돌린 노드는 `run.py finish <id> --changed <파일…>` 로 바뀐 파일 ⊆ `files` 를 하네스가 본다 (하위 에이전트의 보고). 폴더 · `./` · `..` 는 바뀐 파일로 받지 않는다.
- **명령 공통**: `cmd` · `gate.cmd` 의 파이썬은 `{python}` 으로 쓴다 — 하네스가 자기 실행 파일로 바꾼다 (Windows `python` · macOS/Linux `python3` 차이 없음).
  셸은 OS 기본(Windows cmd · 그 밖은 sh)이라 셸마다 다른 따옴표 · 파이프 · `&&` 는 피하고, 복잡하면 `tools/*.py` 스크립트로 뺀다.
- **실패 원인**: cmd 가 0 이 아닌 값으로 끝나면 기본은 `contract_violation`(사람에게). 네트워크처럼 다시 하면 될 수 있는 실패의 exit 코드만
  `"transient_exit": [<코드>]` 에 적는다 — 그 코드만 `transient` 로 분류돼 `retry` 를 탄다. 원인은 에이전트가 고르지 않고 스펙이 정한다.
- **CODE**: `cmd` — 하네스가 직접 실행한다. 상태는 환경변수 `HARNESS_STATE`(state.json 경로)로 읽고, 쓰기는 stdout 에 `HARNESS_WRITES {"필드": 값}` 한 줄.
- **AGENT**: 에이전트가 `run.py begin` → 작업 → `run.py finish --set 필드=값`. 게이트는 finish 때 하네스가 돌린다.
  테스트를 고쳐 가며 다시 해야 하는 일이면 `"retry": {"max": 2, "on": ["contract_violation"]}` — 루프는 노드 안에, 한도와 함께.
  LLM 의 판단이 필요한 일도 AGENT 노드다 — 판단 결과는 enum 필드로 쓰고, 맞는지는 게이트 · 검사기가 잰다.
- **HUMAN**: `human.actions` = `human.field`(enum)의 값. `note_field` 는 자유 문장(분기에 안 씀 · 비어도 된다).
  부작용을 여는 승인 값은 `human.approve` 에 적는다 (예: `["publish"]`) — 부작용 노드는 이 값으로만 열린다.
- **부작용**: `side_effect.class` · `idempotency_key` · requires 에 `<HUMAN 필드> == <human.approve 의 값>` (`exists` · `!=` · 거절 값은 ERROR).

```harness
{
  "kind": "node",
  "id": "T01-example",
  "type": "AGENT",
  "reqs": ["REQ-F1"],
  "requires": ["input_path exists"],
  "writes": ["report.status"],
  "files": ["src/example.py"],
  "gate": {"cmd": "{python} -m unittest tests.test_example", "pass": "exit==0", "timeout": 600},
  "retry": {"max": 2, "on": ["contract_violation"]}
}
```
