# Query Agent MVP — Small Node 설계 LIST

> 상태: **Small → Big → Small 최상위 구조 확정(2026-10-31), Small Node 11종 등록 / 구현 미착수**. 이 문서는 Small Node의 이름·책임·최소 입출력을 나열하는 **LIST**다. 실행 순서·분기는 [Big Node 워크플로](query-agent-mvp.md), 용어는 [명칭 통일 문서](naming-conventions.md)를 기준으로 한다.
>
> 범위: 최상위 공통 Small Node N-10·N-11, Big Node 내부 Small Node N-01~N-09. MVP Big Node 3종(T-01~T-03)에 우선 적용하며 T-04·T-05는 후속 계획으로 유지한다.

## 1. 최상위 공통 Small Node (입구·출구)

| ID | Small Node | 역할 | 최소 입력 → 출력 | 적용 위치 |
|---|---|---|---|---|
| **N-10** | `route_query` | 질문·대상 문서/권한/조건 확인, 요청 유형 분류, 실행할 Big Node 선택. 기준별 판정·검색은 수행하지 않음 | 원본 요청·허용 범위 → `RoutedTask` 또는 실행 전 종료 상태·사유 | **Small → Big**, 모든 요청의 입구 |
| **N-11** | `deliver_result` | Big Node 결과 또는 실행 전 종료 사유를 사용자에게 전달할 형태로 정리. 새로운 업무 판단·근거 생성 금지 | `WorkflowResult` 또는 라우팅 종료 상태·사유 → 사용자 결과(근거·검증 상태 포함) | **Big → Small**, 모든 요청의 출구 |

**공통 실행:** 정상 요청은 **N-10 → 선택된 Big Node(T-01/T-02/T-03 중 하나) → N-11**. 명확화·권한 부족·미지원 등으로 실행 전 종료되는 요청은 **N-10 → N-11**을 거친다. 두 Small Node는 Big Node 바깥의 고정 단계다.

## 2. Big Node 내부 공통 Small Node

| ID | Small Node | 역할 | 최소 입력 → 출력 | 사용 Tool |
|---|---|---|---|---|
| **[N-01](small-nodes/N-01.md)** | `retrieve_evidence` | 허용된 문서·색인 범위에서 질문 또는 명시적 항목에 관련된 검색 후보를 찾음 | 질문/검색 조건·문서 범위 → `RetrievalCandidates` | T-01 · T-02 · T-03 |
| **N-02** | `get_source_context` | 후보를 원문 문단·표·헤더·각주·위치 및 추출 상태와 연결 | 후보 참조·문서 버전 → 원문 근거 묶음(`EvidenceBundle`) | T-01 · T-02 · T-03 |
| **N-03** | `verify_grounding` | 답변·판정·비교 결과의 주장과 인용이 실제 원문 근거로 뒷받침되는지 검사 | 업무별 결과 초안·원문 근거 → `VerificationReport` | T-01 · T-02 · T-03 |

## 3. Big Node 내부 전용 Small Node

| ID | Small Node | 역할 | 최소 입력 → 출력 | 사용 Tool |
|---|---|---|---|---|
| **N-04** | `draft_answer` | 확인된 근거만 이용해 문서 질문의 답변 초안 작성 | 질문·`EvidenceBundle` → `ReviewDraft` | T-01 Document QA |
| **N-05** | `structure_criteria` | 사용자가 제공한 평가 기준을 판정 가능한 항목으로 구조화하고 원문 조건 보존 | 명시적 평가 기준 → `CriteriaSet` | T-02 Criteria Review |
| **N-06** | `evaluate_criterion` | 각 기준을 근거와 대조해 충족·미충족·확인 불가로 분류 | `CriteriaSet` 항목·근거 → `CriterionFinding` | T-02 Criteria Review |
| **N-07** | `define_comparison` | 비교할 문서·대상·기간·지표 및 범위 정리 | 명시적 비교 요청 → `ComparisonSpec` | T-03 Comparative Analysis |
| **N-08** | `check_comparability` | 값·단위·기간·집계 기준 또는 정성적 비교 범위가 일치하는지 확인 | `ComparisonSpec`·대상별 근거 → 비교 가능성 및 사유 | T-03 Comparative Analysis |
| **N-09** | `build_comparison` | 비교 가능한 대상의 차이 계산 또는 정성적 대조 결과 구성 | 비교 가능성·대상별 확인값/내용 → `ComparisonFinding` | T-03 Comparative Analysis |

## 4. Big Node별 Small Node 조합 색인

다음 표는 **Big Node 내부**에서 사용하는 Small Node만 보여 준다. 모든 Big Node 앞뒤에 공통으로 붙는 N-10·N-11은 중복 표기하지 않는다. 실제 실행 순서·예외 분기는 [Big Node 워크플로 문서](query-agent-mvp.md)를 따른다.

| Big Node | 사용하는 Small Node |
|---|---|
| **T-01 Document QA** | N-01 · N-02 · N-04 · N-03 |
| **T-02 Criteria Review** | N-05 · N-01 · N-02 · N-06 · N-03 |
| **T-03 Comparative Analysis** | N-07 · N-01 · N-02 · N-08 · N-09 · N-03 |

## 5. Small Node로 분리하지 않는 내부 기능

| 기능 | 위치·이유 |
|---|---|
| Dense 검색·BM25·RRF·선택형 Reranker | **N-01 내부 검색 파이프라인**. 세부 구성은 [문서 처리 파이프라인](document-pipeline.md)에서 관리 |
| 표의 헤더·각주·주변 문맥 확장 | **N-02 내부 원문 조회 기능** |
| 결정적 산술·단위 환산 | **N-06 또는 N-09에서 이용하는 공통 계산 기능**. 독립 그래프 노드 여부는 구현 시 판단 |
| 요청 분류·Big Node 선택 | **N-10 `route_query`** 책임. Big Node 내부에서 다시 수행하지 않음 |
| 사용자용 결과 서식화 | **N-11 `deliver_result`** 책임. Big Node 내부에서 별도 공통 노드로 중복 정의하지 않음 |
| 체크포인트·Trace·오류·예산 제어 | **하네스 공통 실행 기능**. 업무 목적 노드와 구별 |

**설계 원칙:** 목록의 Small Node가 반드시 별도 LLM 호출이나 별도 LangGraph 노드 하나를 의미하는 것은 아니다. 구현 시 독립 실행·테스트·재사용이 필요한 경계만 노드로 유지하고 단순 연산은 내부 함수로 둘 수 있다. **새 쿼리를 만드는 증폭 기법은 H-12 백로그 유지**이며, N-05의 명시된 기준 구조화는 그와 다르다.

**관련 문서:** [Big Node / Small Node 명칭 통일](naming-conventions.md) · [Big Node MVP 워크플로](query-agent-mvp.md) · [문서 처리·하이브리드 검색 파이프라인](document-pipeline.md) · [하네스 아이디어 백로그](idea-backlog.md)
