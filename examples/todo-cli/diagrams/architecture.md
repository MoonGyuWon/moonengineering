<!-- harness/render.py 가 만든 파일 — 손으로 고치지 않는다 -->
# 계층 · 경계

> 생성 2026-10-31T16:09:39 · graph v1 · Run run-20261031-152503

```mermaid
flowchart TB
  subgraph L_interface["계층: interface"]
    subgraph B_interface_cli["경계: cli"]
      T03_cli["T03-cli"]
    end
    subgraph B_interface_release["경계: release"]
      H05_approve["H05-approve"]
    end
  end
  subgraph L_verification["계층: verification"]
    C04_accept["C04-accept"]
  end
  subgraph L_domain["계층: domain"]
    subgraph B_domain_presentation["경계: presentation"]
      T02_format["T02-format"]
    end
  end
  subgraph L_infra["계층: infra"]
    subgraph B_infra_release["경계: release"]
      T06_release["T06-release"]
    end
    subgraph B_infra_storage["경계: storage"]
      T01_store["T01-store"]
    end
  end
  T03_cli -->|"cli.ok"| C04_accept
  C04_accept -->|"check.verdict"| H05_approve
  T01_store -->|"store.ok"| T03_cli
  T02_format -->|"format.ok"| T03_cli
  H05_approve -->|"release.action"| T06_release
```

## 경계를 넘는 계약

| 보내는 계층 | 받는 계층 | 경계를 넘는 필드 (계약) |
| --- | --- | --- |
| domain | interface | format.ok |
| infra | interface | store.ok |
| interface | infra | release.action |
| interface | verification | cli.ok |
| verification | interface | check.verdict |
