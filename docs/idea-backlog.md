# 하네스 엔지니어링 아이디어 백로그

> 상태: 설계 아이디어 / 미확정  
> 대상: ReportAnchor (로컬 문서 검토·근거 추적 에이전트)  
> 범위: 하네스 구조, 모듈 경계, 상태·결과 보존, 재현성 및 검증 체계  
> 본 문서는 구현 확정안이나 소규모 실험 실행 계획이 아니다.

## 1. 목표와 설계 관점

문서 파싱, VLM 보완, 청킹·색인, 검색, 근거 조회, 수치 계산, 검토, 인용 검증을 독립 모듈로 분리한다. 각 모듈 종료 시 **입력·출력·실행 상태와 버전 정보**를 보존해, 특정 단계만 교체하거나 동일한 중간 결과에서 후속 단계를 재실행할 수 있도록 한다.

컴퓨터 구조의 파이프라인 단계·중간 상태 보존과 유사한 설계 발상이다. 실제 구현 모델은 순차 파이프라인만이 아니라 의존성 있는 작업을 실행하는 **데이터플로 그래프(DAG), 체크포인트, 증분 재실행**의 조합에 가깝다.

핵심 목표:
- 모듈별 책임·입출력 계약의 명확화 및 팀원 작업의 독립성 확보
- 실패 위치와 원인 추적, 중단 시 복구, 실행 제약의 일관된 적용
- 공통 입력에서 검색·검토·검증 전략을 교체하는 비교 가능 환경 구성
- 불필요한 파싱·임베딩·모델 호출을 피할 수 있는 단계별 결과 재사용
- 모든 판단을 문서 버전과 원문 근거에 연결하여 재현성 보존

## 2. 기술 구성 후보

| 구성 요소 | 제안 역할 | 참고 및 유의점 |
|---|---|---|
| LangGraph | 상태 그래프, 분기·합류, 실행 제어, 체크포인트, 중단·재개 | 하네스의 실행 중심축으로 검토 |
| LangChain | LLM·임베딩·Retriever·도구 어댑터 | LangGraph 노드 내부 또는 Agent 구현에서 선택적으로 사용. 중복 실행 계층을 만들지 않음 |
| DSH (DeepSeek Harness) | 플러그인 경계, 실행 이벤트, 세션/도구 추적, 정책 분리 | Cordis·전체 플러그인 런타임 복제는 범위에서 제외 |
| Open Notebook | LangGraph 활용, FastAPI와 비동기 워커 분리, 로컬 데이터 관리 | 서비스 통합 구조를 참고하되 저장소·워커 선택은 독립적으로 결정 |
| 로컬 영속 저장소 | 그래프 체크포인트, 실행 메타데이터, 아티팩트 저장 | 체크포인트와 아티팩트를 논리적으로 분리하고 실제 저장 기술은 추후 결정 |

LangChain과 LangGraph를 병용하되, 검색 전략·답변 로직은 RAG/Agent 담당 모듈의 책임으로 유지한다. 하네스는 해당 모듈을 실행·관찰·평가하는 공통 인터페이스를 제공한다.

## 3. 모듈 경계와 저장 지점

### 3.1 문서 준비 흐름

**문서 등록/버전 식별 → 파싱 → (필요 영역 VLM 보완) → 문서·표 구조화 → 청킹 → 색인**

| 경계 | 저장할 대표 아티팩트 | 재사용·검증 관점 |
|---|---|---|
| 원문 등록 | DocumentVersion, 원문 해시·형식·위치 | 동일 원문 식별, 버전 변경 추적 |
| 파싱 완료 | ParsedDocument, 표·문단의 원문 위치 | 파서 변경 전후 출력 비교 |
| 구조화/VLM 보완 완료 | TableIR, 추출기 출처·검증 상태 | 헤더·행 라벨·단위·연도 보존 |
| 청킹 완료 | ChunkSet, 청크 ID·원문/구조 참조 | 청킹 전략 비교 |
| 색인 완료 | IndexManifest, 임베딩 모델·설정·청크 집합 버전 | 불필요한 재색인 방지 |

### 3.2 질의·문서 검토 흐름

**질문 및 검토 기준 → 검색/리랭킹 → 근거 보강 및 도구 실행 → 검토 초안 → 주장·인용 검증 → 결과/판단 보류**

| 경계 | 저장할 대표 아티팩트 | 재사용·검증 관점 |
|---|---|---|
| 요청 분석 | ReviewRequest, 검토 기준·문서 범위 | 동일 조건으로 전략 변경 |
| 검색 완료 | EvidenceBundle, 문서·표·청크·근거 위치 | 검색/리랭킹 비교, 원문 조회 |
| 도구 실행 완료 | ToolResult, 수치 계산 입력·단위·출처 | 결정적 계산 재검증 |
| 초안 생성 완료 | ReviewDraft, 모델·프롬프트·참조 근거 | 재생성 없이 검증 로직 비교 |
| 인용 검증 완료 | VerificationReport, 불일치·미확인·판단 근거 | 검증 규칙 변경에 따른 결과 비교 |
| 최종 처리 | FinalReview, 성공/보완/판단 보류 상태 | 사용자에게 결과와 근거 제공 |

대용량 원문·이미지·표는 그래프 상태에 복사하지 않고, 안정적인 아티팩트 참조(ID/버전)를 전달하는 방식을 우선 고려한다. 문서 처리와 질의 처리는 서로 다른 그래프 또는 하위 그래프가 될 수 있다.

## 4. 하네스 아이디어 후보

| ID | 아이디어 | 핵심 내용 | 검토 우선도 |
|---|---|---|---|
| H-01 | 타입 기반 모듈 계약 | Pydantic 기반 입력/출력·스키마 버전·근거 위치·오류 형식을 합의하여 파서/RAG/검증 모듈 교체 가능하게 구성 | 높음 |
| H-02 | 단계별 아티팩트 저장소 | 불변 결과와 입력 참조, 생성 모듈/설정/시각을 저장. 단계 결과를 다른 실행에서 재사용 | 높음 |
| H-03 | 그래프 체크포인트와 복구 | LangGraph 실행 상태 저장, 중단·재개, 분기별 완료 상태 관리. 병렬 실행의 super-step 경계 고려 | 높음 |
| H-04 | 의존성 기반 캐시 무효화 | 원문·입력 아티팩트·모듈 코드/설정·프롬프트·모델 버전으로 캐시 키 계산. 변경 지점의 후속 단계만 재실행 | 높음 |
| H-05 | 실행 분기·비교(Fork/Replay) | 동일한 중간 결과에서 검색·검토·검증 전략을 분기하고 실행 계보와 비교 지표 기록 | 높음 |
| H-06 | 구조화된 실행 이벤트 | run/node/tool/모델 호출의 시작·종료·오류·재시도·근거 참조를 추적. 원문 전체는 로그에 중복 저장하지 않음 | 높음 |
| H-07 | 경량 플러그인/어댑터 | 파서·Retriever·VLM·Verifier를 교체 가능한 레지스트리로 등록하고 계약 호환성 검사 | 중간 |
| H-08 | 실행 정책 및 실패 처리 | 모듈별 timeout, 호출 횟수·토큰 예산, 오류 유형별 재시도, 판단 보류 및 취소·복구 정책 | 높음 |
| H-09 | 비동기 작업 분리 | 문서 등록·파싱·색인과 대화형 검토 요청의 실행 수명·큐 분리. 로컬 우선 운영 | 중간 |
| H-10 | 사람 승인·문서 버전 이력 | 첨삭안의 원문 대비 변경점, 사용자 승인, 승인 전 원본 보호. 문서 직접 편집이 확정되면 도입 | 후순위 |

이 항목들은 모두 **제안**이며, 구현 범위·우선도는 팀 데이터 계약과 사용 사례를 합의한 후 확정한다.

## 5. 저장 계층의 책임 구분

1. **Checkpoint**: 현재 그래프 실행 상태와 재개 지점. 실패 복구와 실행 제어를 위한 정보.
2. **Artifact**: 각 모듈의 입력·출력 및 근거를 버전과 함께 보존한 재사용 가능한 결과.
3. **Execution Trace**: 실제 호출 순서, 오류, 소요 시간, 비용 등 관찰·평가 가능한 실행 기록.

세 계층은 목적이 다르므로 동일 데이터로 취급하지 않는다. 체크포인트 복구가 곧 과거 모델 응답의 결정적 재현을 의미하지 않으며, 재실행 과정에서 외부 도구의 부작용이 중복되지 않도록 멱등성도 고려해야 한다.

권장 메타데이터 후보:
- 실행 계보: run_id, parent_run_id, node_id, attempt, input_artifact_ids, output_artifact_ids
- 자료 버전: document_id, document_hash, schema_version, source_locator, source_version
- 실행 조건: module_version, config_hash, model_id/parameters, prompt_hash, index_version
- 상태 및 지표: status, started_at, elapsed_ms, token_usage, retry_count, error_type
- 검증: evidence_refs, verification_status, evaluator_version, evaluation_set_version

캐시 적중 여부와 아티팩트 재사용 여부는 별도 지표로 기록한다. LLM 출력 캐싱은 동일 입력·모델 조건일 때만 허용하며, 비결정적 호출의 재사용 결과를 새로운 독립 모델 실행으로 간주하지 않는다.

## 6. 검증 및 비교 관점

하네스 자체의 품질은 최종 답변 점수와 별도로 측정한다.

- **운영·복구:** 완료율, 단계별 실패율, 재개 성공 여부, 중복 부작용 여부
- **성능:** 모듈별 시간, 전체 지연, 모델 호출 횟수·토큰, 캐시 적중·재사용률
- **재현성:** 원문/아티팩트/설정 해시 기록 충실도, 동일 조건 비교 가능 여부
- **문서 품질과 분리된 결과:** 검색 적중·원문 근거 정합성·표 구조 정확도·인용 검증 결과를 각 담당 평가 모듈에서 수신

비교 시 문서·검토 기준·평가셋·모델/프롬프트 버전 및 캐시 상태를 통제한다. 총정답 수가 같더라도 문항별 회귀·개선을 분리하고, 평가셋과 원문이 충돌하면 지표 해석에서 해당 사실을 표시한다.

## 7. 기존 레퍼런스 RAG 활용 방향

**대상:** [references/gachon-admissions/](../references/gachon-admissions/) — 기존 가천대 입학안내 RAG를 보존한 참조 구현

- **baseline-1 / v23:** HWP·PDF 파싱, 문맥 청킹, Chroma Dense + BM25, RRF 검색, 질의 라우팅, 초안·근거 검증을 하나의 파이프라인으로 구성한 동결 비교점. [구조 문서](../references/gachon-admissions/reference/baseline1/ARCHITECTURE.md) · [출력 계약](../references/gachon-admissions/reference/baseline1/INTERFACE.md)
- **baseline-2 / v24:** 설치 가능한 src/docparse 패키지, Table/Cell IR, 렌더러와 구조·원문 검증 실험. 실제 이식 후보는 파서와 IR 계약이며, 문서군 특화 검색/프롬프트/라우팅 로직은 그대로 일반화하지 않는다. [실무 인계](../references/gachon-admissions/reference/baseline2/HANDOFF.md) · [파서 코드](../references/gachon-admissions/src/docparse/)
- **평가 기반:** scripts/run_eval.py가 질문별 검색·초안·교정 시간, 근거, 실행 환경, 변형 정보와 결과를 JSONL/JSON으로 저장한다. 하네스 공통 Trace 및 평가 계약의 출발점으로 활용할 수 있다. [평가 러너](../references/gachon-admissions/scripts/run_eval.py)
- **참조 결과:** 저장된 v23 전체 40/53, v24 V0 40/53, V3 40/53. v24 엄격 표 구조 골든은 2/11 통과로 실패했고 렌더러 간 우열은 확정되지 않았다. 모든 질문 세트가 개발 과정에서 사용됐으며 원문–gold 충돌 사례가 있으므로 일반화 정확도나 인과적 개선을 뜻하지 않는다. [v23 평가](../references/gachon-admissions/reference/baseline1/EVAL.md) · [v24 평가](../references/gachon-admissions/reference/baseline2/EVAL.md) · [최종 검증](../references/gachon-admissions/reference/baseline2/VALIDATION.md)
- **현재 제약:** 참조 RAG는 OpenAI/Voyage API 의존성을 포함한다. ReportAnchor의 로컬 모델·데이터 경계에 곧바로 부합하는 완성 시스템은 아니므로 **파서·데이터 계약·평가 체계의 기준선**으로 취급한다.

기존 파이프라인의 색인용 텍스트, LLM용 근거, 검증용 원문이 일부 결합되어 있다는 인계 기록을 반영해, 신규 하네스에서는 **index_text / llm_context / verification_source**를 구분하고 동일한 원문·IR 참조에 연결하도록 설계한다. 문서 버전과 원문 위치를 유지하는 EvidenceBundle 계약을 우선 합의한다.

## 8. 팀 내 논의·결정 필요 사항

1. 파서/VLM → RAG → Agent/검증 간 필수 필드와 스키마 버전
2. 상태 체크포인트와 대용량 아티팩트의 저장 기술 및 보존 정책
3. 캐시 무효화 기준(원문 변경, 파서/청킹 변경, 모델·프롬프트 변경)
4. 분기 실행 시 원문·평가 조건 고정, LLM 출력 재사용과 실제 재호출의 구분
5. 실패 유형, 재시도·중단 조건, 멱등성 및 개인정보·민감 문서 로그 정책
6. 레퍼런스 RAG의 어떤 부분을 동결하고 어떤 부분을 교체 가능한 어댑터로 이식할지

## 9. 외부 설계 참고

- [LangGraph 문서](https://docs.langchain.com/oss/python/langgraph/overview) — 상태 기반 실행 및 체크포인트
- [LangChain 문서](https://docs.langchain.com/oss/python/langchain/overview) — 모델·Retriever·도구 통합
- [DeepSeek Harness 아키텍처](https://github.com/deepseek-ai/deepseek-harness/blob/main/docs/architecture.md) — 플러그인·이벤트·세션 실행 기록
- [Open Notebook 아키텍처](https://github.com/lfnovo/open-notebook/blob/main/docs/7-DEVELOPMENT/architecture.md) — LangGraph·FastAPI·백그라운드 워커 분리
