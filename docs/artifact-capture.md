# H-02 단계별 아티팩트 저장 — MVP 구현 범위

> **결정 (2026-11-01): H-02 노드별 아티팩트 저장만 MVP 구현 대상 확정.**
>
> **H-03 Checkpointer/실행 중단 후 재개: 미정. 구현하지 않을 수 있음. MVP 필수 기능 아님.**
>
> 상태: 구현 범위와 기능 경계 확정 / **실제 저장 기능 코드는 미구현**. 현재 JS 브랜치에서는 설계 문서로만 기록한다.
>
> 관련 문서: [하네스 백로그](idea-backlog.md) · [Query Agent](query-agent-mvp.md) · [Small Node 반환 계약](small-nodes/common-result-contract.md)

## 1. 구현할 기능 (H-02)

- Small Node(N-01~N-11)가 반환한 `NodeResult[T]`를 **노드 호출별 아티팩트**로 남긴다. 이는 하네스 공통 저장 기능이며 별도 Small Node/Tiny Node가 아니다.
- 유효한 `data`와 `status`, `outcome`, 필요한 `diagnostics`를 기록한다. 부분 실패라면 가용 결과와 실패 원인을 모두 보존한다.
- `run_id`, `node_id`, `invocation_id`(반복 실행별 식별자), `attempt`, 입력 참조/해시, 문서·색인·설정·모델·모듈·스키마 버전 등 추적 메타데이터를 기록한다. 구체 필드·스키마는 구현 시 정한다.
- **로컬 JSON 파일**을 기본 구현 방향으로 삼고, `capture_artifacts` 같은 **독립 ON/OFF 설정**을 제공한다. 기본 활성 환경·보존 기간·저장 경로는 구현 시 결정한다.
- 아티팩트 저장을 꺼도 기존 Small Node의 반환 계약과 Big Node의 실행 순서는 바뀌지 않아야 한다.

## 2. 실행 흐름 시각화

아래 캡처 단계는 **그래프의 새로운 Small Node/엣지가 아니라 하네스 관측 기능**이다.

~~~mermaid
flowchart TD
  N["Small Node 실행"] --> R["NodeResult[T] 반환"]
  R --> S["LangGraph State에 반환 결과 적용"]
  R --> C{"Artifact Capture ON?"}
  C -->|ON| V["민감 정보 제거·참조 검사"]
  V --> A["로컬 JSON 아티팩트 기록"]
  A --> M["run Manifest에 기록"]
  C -->|OFF| X["저장 생략"]
  S --> NEXT["다음 Small Node 실행"]
  M -. "테스트·사후 분석 기록" .-> NEXT
~~~

## 3. 로컬 아티팩트 예시

~~~text
artifacts/
└── run_001/
    ├── manifest.json
    ├── N-01__001.json
    ├── N-01__002.json
    └── N-02__001.json
~~~

반복·재시도 때 이전 결과를 덮어쓰지 않도록 호출 인스턴스를 구분한다.

~~~json
{
  "run_id": "run_001",
  "node_id": "N-01",
  "invocation_id": "N-01__001",
  "attempt": 1,
  "input_refs": ["request_001", "index_v3"],
  "input_hash": "sha256:example",
  "schema_version": "1",
  "result": {
    "status": "partial",
    "data": {"candidates": [{"chunk_id": "chunk_042"}]},
    "diagnostics": {
      "dense_search": {"status": "failed", "error_code": "TIMEOUT"}
    },
    "outcome": null
  }
}
~~~

예시 식별자·경로·스키마는 미확정이며, 실제 테스트 실행 결과가 아니다.

## 4. 저장 정책과 한계

- 원문 전체, 표·이미지·임베딩·색인 본체 등 큰 데이터를 중복 보존하지 않는다. 가능하면 변경되지 않는 원문/아티팩트 **ID·버전·위치 참조**를 사용한다.
- 민감 문서·권한·API 키·전체 스택 트레이스가 JSON에 노출되지 않도록 저장 전 검증한다. 파일 접근 권한, 삭제/보존, 원자적 쓰기·오류 처리는 구현 단계에서 정한다.
- 저장 실패는 **업무 노드의 `NodeResult.status`와 별개의 하네스 기록 오류**로 구분한다. 테스트/서비스에서 저장 실패를 어떻게 취급할지는 후속 정책으로 결정한다.
- 저장된 결과는 **노드별 테스트·회귀 비교·실험의 입력**으로 활용한다. 자동 캐시 무효화(H-04)와 자동 실행 분기·리플레이(H-05)가 함께 구현되는 것은 아니다.

## 5. 체크포인트(H-03): 별도 미결 사항

**MVP는 Checkpointer 설치, 그래프 상태 영속화, 중단 후 자동 재개, 체크포인트 토글 구현을 요구하지 않는다.** 필요성이 입증되지 않으면 구현하지 않아도 된다. H-02 아티팩트 캡처가 이를 대신한다고 해석하지 않는다.

## 6. 구현 완료 판단 기준

- [ ] 설정이 켜진 실행에서 Small Node별 `NodeResult[T]`를 JSON으로 저장
- [ ] 같은 Small Node의 반복·재시도 실행을 독립 파일·ID로 구분
- [ ] `success` / `partial` / `error`, `data`, `diagnostics`, `outcome` 보존
- [ ] 저장 비활성화 시 원래 업무 실행에 영향 없음
- [ ] 저장한 중간 결과를 단위/회귀 테스트에서 읽을 수 있음
- [ ] 민감 정보·권한 위반·불필요한 원문 중복 기록 방지

**현재는 위 체크리스트의 구현·테스트를 수행하지 않았다.**
