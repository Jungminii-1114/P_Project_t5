# AutoRAG — ReportAnchor 설계 레퍼런스

> 조사일: **2026-11-01** · 공식 검토 기준: [AutoRAG v2.13.4](https://github.com/Marker-Inc-Korea/AutoRAG/releases/tag/v2.13.4) (2026-10-31 공개)
>
> **판정: 관련성 높음 / 설계·평가 참고용.** 아직 도입, 연동, 벤치마크, 성능 우위 검증을 수행하지 않았다. 공식 README·문서·일부 공개 소스를 확인한 정적 조사이며, 코드는 복제·반입하지 않는다.
>
> ReportAnchor의 **Small → Big → Small** 구조 및 [Big Node T-01~T-03](../../docs/query-agent-mvp.md), [Small Node N-01~N-11](../../docs/query-agent-node-list.md)의 MVP 결정은 유지한다.

## 1. 대상 프로젝트 구분

| 구분 | 공식 경로 | 기능 | 상태 및 관련성 |
|---|---|---|---|
| **AutoRAG 2.0 / Agent** | [저장소 루트](https://github.com/Marker-Inc-Korea/AutoRAG/tree/v2.13.4) · TypeScript/Node.js, Pi 기반 | 로컬 파일·연결 데이터소스 검색, 근거 기반 답변, 파일 정리 Agent | 현재 신규 기능 개발 중심. **T-01, N-01/N-02/N-03/N-10** 참고 |
| **Original AutoRAG / Legacy** | [`legacy/`](https://github.com/Marker-Inc-Korea/AutoRAG/tree/v2.13.4/legacy) · Python | RAG 전처리·검색·생성 모듈 조합의 자동 평가·최적화(AutoML) | 버그 수정·의존성·PyPI 유지보수 중심. **검색 전략 비교 실험** 참고 |

**중요:** 2.0은 문서 검색 *사용자용 에이전트*, Legacy는 RAG 파이프라인 *실험·최적화 도구*다. 같은 이름이어도 목적이 다르므로 하나의 시스템으로 오해하지 않는다. [공식 Agent README](https://github.com/Marker-Inc-Korea/AutoRAG/blob/v2.13.4/README.md) · [Legacy README](https://github.com/Marker-Inc-Korea/AutoRAG/blob/v2.13.4/legacy/README.md).

## 2. AutoRAG 2.0에서 확인한 설계

| 관찰 내용 | 확인한 역할 및 구현 경계 | ReportAnchor에 적용해 볼 개념 |
|---|---|---|
| **문서 준비와 검색 실행 분리** | 사전 색인·갱신(`refresh`) 후 질의 실행; 로컬 BM25/MinSync 의미 검색과 외부 데이터소스 검색을 지원 | N-01은 **검색 실행만** 담당하고 파싱·색인 준비 책임과 분리 |
| **등록된 검색 방법 조합** | [RetrievalEngine](https://github.com/Marker-Inc-Korea/AutoRAG/blob/v2.13.4/src/retrieval/engine.ts)이 검색 방법 호출·범위 필터링·결과 통합·진단을 담당 | N-01에 검색 모듈 교체 가능성과 오류 상태·검색 범위 메타데이터 반영 |
| **원문 근거의 안전한 인용** | [EvidenceLedger](https://github.com/Marker-Inc-Korea/AutoRAG/blob/v2.13.4/src/agent/evidence-ledger.ts)는 검색 시 발급한 근거 ID를 실제 출처·청크에 연결하고 [Answer Citations](https://github.com/Marker-Inc-Korea/AutoRAG/blob/v2.13.4/src/agent/answer-citations.ts)가 인용을 해소 | N-02는 근거 참조 보존, N-03은 **실제 존재하는 인용인지**와 **주장이 근거로 지지되는지**를 별도로 검증 |
| **라우팅의 독립 경계** | [Query Routing](https://github.com/Marker-Inc-Korea/AutoRAG/blob/v2.13.4/src/agent/query-routing.ts)이 로컬 검색/정리 등 요청 분류를 다룸 | N-10 역할 분리 참고. ReportAnchor에서는 **T-01~T-03 중 하나**만 선택 |
| **후보 재정렬** | [Rerank](https://github.com/Marker-Inc-Korea/AutoRAG/blob/v2.13.4/docs/rerank.md)는 후보 통합 후 선택적 재정렬과 실패 진단을 다룸 | N-01 내부의 선택형 Reranker 실험과 장애 처리 비교 |
| **근거 판정 이력** | [Retrieval Memory](https://github.com/Marker-Inc-Korea/AutoRAG/blob/v2.13.4/docs/retrieval-memory.md)가 사용된 근거·검색 방법·판정 정보를 추적 | 근거 계보 기록 참고. 장기 메모리 도입은 **MVP 범위 밖** |
| **한국어 로컬 문서 처리** | PDF 및 HWP/HWPX를 포함한 문서 처리·미리보기 생태계를 소개 | 문서 형식 대응 참고. 원문 표/각주 추출 정확도는 **독립 검증 필요** |

### 반드시 구분할 검색 통합 방식

[AutoRAG 2.0 ResultMerger](https://github.com/Marker-Inc-Korea/AutoRAG/blob/v2.13.4/src/retrieval/merger.ts)는 **검색 방식별 min-max 점수 정규화, 중복 청크 제거, 제한된 교차 근거 보너스**를 사용한다. ReportAnchor의 **Dense + BM25 → RRF(순위 기반 통합)**와 목적은 비슷하지만 **같은 알고리즘이 아니다**. AutoRAG Legacy에는 별도의 `hybrid_rrf` 모듈이 있다.

인용 ID가 유효하다는 사실도 해당 인용이 답변의 주장을 **의미적으로 입증했다는 뜻은 아니다**. N-03에서 두 종류의 검증을 구분하는 참고 사례다.

## 3. AutoRAG Legacy — 실험 평가 참고

[Legacy README](https://github.com/Marker-Inc-Korea/AutoRAG/blob/v2.13.4/legacy/README.md)는 `qa.parquet`(질문·평가 데이터)와 `corpus.parquet`(문서 청크 모음), YAML 실험 설정을 사용해 모듈 구성을 비교하는 방식을 설명한다. 어휘·의미·하이브리드 검색, 재정렬, 프롬프트·생성 등 모듈 후보와 Recall/nDCG/MRR 등의 검색 평가 지표가 포함된다.

| 참고할 개념 | ReportAnchor에서의 활용 방향 |
|---|---|
| **동일 평가셋으로 구성 비교** | RRF 단독 대 선택형 로컬 Reranker, 청킹·검색 전략 등을 **동일 질문/문서/정답 근거**로 비교 |
| **단계별 결과·설정 저장** | 버전·중간 산출물·평가 지표를 독립 저장해 실험 재현성과 오류 위치 추적 |
| **평가용 QA/정답 근거 준비** | 합성 QA를 사용하더라도 정답 근거·원문 위치·표 수치의 **사람 또는 독립 검증** 필요 |

공식 코드 참고: [Evaluator](https://github.com/Marker-Inc-Korea/AutoRAG/blob/v2.13.4/legacy/autorag/evaluator.py) · [Node Line](https://github.com/Marker-Inc-Korea/AutoRAG/blob/v2.13.4/legacy/autorag/node_line.py) · [Hybrid Retrieval](https://github.com/Marker-Inc-Korea/AutoRAG/tree/v2.13.4/legacy/autorag/nodes/hybridretrieval).

**Legacy의 `Node`는 ReportAnchor의 Big Node / Small Node와 다른 용어 체계**다. 코드·설정 파일을 가져오거나 명칭을 혼합하지 않고, 평가 설계만 참고한다.

## 4. MVP 기능 겹침과 차별화 검토

| ReportAnchor 단위 | 관련성 | 검토 의견 |
|---|---|---|
| **T-01 Document QA** | **직접 겹침** | 로컬 문서 질문·근거 기반 답변만으로는 새로움을 주장하기 어려움 |
| **N-01 `retrieve_evidence`** | **높음** | 검색기 등록, 범위, 결과 통합, 오류 진단 인터페이스 비교 |
| **N-02 `get_source_context`** | **높음** | 원문 ID·청크·출처·문맥 유지 및 출처 해소 방식 참고 |
| **N-03 `verify_grounding`** | **높음** | 실존하는 인용과 실제 주장 지지 여부를 구분하는 검증 |
| **N-10 `route_query`** | 중간 | 라우팅 분리 참고. 자율적 추가 도구 호출은 MVP에서 불허 |
| **T-02 Criteria Review** | 부분 | **사용자 기준별 충족/미충족/확인 불가**, 단순 검색 누락과 부재 입증의 구별을 핵심 기여 후보로 검토 |
| **T-03 Comparative Analysis** | 부분 | **기간·단위·집계 기준 비교 가능성 검증**, 결정적 수치 계산 및 인용을 기여 후보로 검토 |

**판단 한계:** AutoRAG 2.0에 T-02/T-03과 동등한 기능이 *존재하지 않음*을 증명한 것은 아니다. 전용 워크플로 수준에서 기능·품질을 비교하는 후속 검증이 필요하다.

## 5. 로컬 실행·라이선스·설계 충돌

1. **로컬 색인과 전체 오프라인 동작은 별개.** AutoRAG의 의미 임베딩은 로컬 MinSync가 기본이지만, LLM, Jev 판단 모델, Reranker 등에는 원격 공급자 설정이 있다. [Rerank 공식 문서](https://github.com/Marker-Inc-Korea/AutoRAG/blob/v2.13.4/docs/rerank.md)에서도 원격 재정렬을 설명한다. **기업·개인 문서의 질문/근거가 외부로 나갈 수 있는지** 별도 점검이 필요하다.
2. **릴리스와 개발 브랜치 차이 주의.** [v2.13.4 Jev 문서](https://github.com/Marker-Inc-Korea/AutoRAG/blob/v2.13.4/docs/jev-decisions.md)에는 Jev 비활성화·로컬 검색 대체 경로가 기록되어 있다. 반면 2026-11-01 확인한 [main Jev 문서](https://github.com/Marker-Inc-Korea/AutoRAG/blob/main/docs/jev-decisions.md)는 Jev를 필수라고 서술한다. **참조 태그를 고정**하고 도입 시점의 실제 동작을 재검증한다.
3. **라이선스 구별.** AutoRAG 2.0 엔진과 Legacy는 각각 [Apache-2.0](https://github.com/Marker-Inc-Korea/AutoRAG/blob/v2.13.4/LICENSE), [Apache-2.0](https://github.com/Marker-Inc-Korea/AutoRAG/blob/v2.13.4/legacy/LICENSE). 데스크톱 앱은 **[별도 저장소](https://github.com/NomaDamas/AutoRAG-app)에서 FSL-1.1-MIT**로 공개되므로 동일한 오픈소스 조건으로 보면 안 된다. [NOTICE](https://github.com/Marker-Inc-Korea/AutoRAG/blob/v2.13.4/NOTICE)의 번들 바이너리·서드파티 라이선스도 재검토 대상이다.
4. **실행 구조 차이.** AutoRAG 2.0은 Pi 기반 Agent와 자율 도구·라우팅 기능을 사용한다. ReportAnchor는 LangChain/LangGraph의 **Small → Big → Small 고정 워크플로**를 채택했으므로 실행 구조를 복제하지 않는다.
5. **검증 상태.** 한국어/PDF/HWP/HWPX 정확도, 최신 릴리스 동작, 성능/비용/보안·라이선스 적합성에 대해 직접 실행한 검증 결과는 없다.

## 6. 후속 검토 제안 (백로그성·미확정)

| 우선순위 | 후속 검증 |
|---|---|
| 높음 | N-02/N-03의 **근거 ID → 원문 위치 → 주장 검증** 데이터 계약 |
| 높음 | N-01의 **검색 결과/부분 실패 진단** 및 AutoRAG 검색기 구성 비교 |
| 중간 | Legacy 방식의 평가 데이터·동일 코퍼스 검색 구성 비교 도입 가능성 |
| 중간 | 한국어 표·각주·연도/단위가 원문까지 추적 가능한지 |
| 후순위 | Jev, 메모리, 질의 분해 등 MVP 밖의 기능 타당성 |

**현재 결정 유지:** Big Node **T-01/T-02/T-03**, Small Node **N-01~N-11**, 쿼리 증폭 H-12 보류, 로컬·오프라인 기본이라는 ReportAnchor 요구를 변경하지 않는다.

## 7. 공식 참조 색인

- [AutoRAG 공식 저장소](https://github.com/Marker-Inc-Korea/AutoRAG) · [v2.13.4 릴리스](https://github.com/Marker-Inc-Korea/AutoRAG/releases/tag/v2.13.4)
- [AutoRAG 2.0 README](https://github.com/Marker-Inc-Korea/AutoRAG/blob/v2.13.4/README.md) · [Legacy README](https://github.com/Marker-Inc-Korea/AutoRAG/blob/v2.13.4/legacy/README.md)
- [RetrievalEngine](https://github.com/Marker-Inc-Korea/AutoRAG/blob/v2.13.4/src/retrieval/engine.ts) · [ResultMerger](https://github.com/Marker-Inc-Korea/AutoRAG/blob/v2.13.4/src/retrieval/merger.ts) · [EvidenceLedger](https://github.com/Marker-Inc-Korea/AutoRAG/blob/v2.13.4/src/agent/evidence-ledger.ts)
- [Rerank](https://github.com/Marker-Inc-Korea/AutoRAG/blob/v2.13.4/docs/rerank.md) · [Jev Decisions](https://github.com/Marker-Inc-Korea/AutoRAG/blob/v2.13.4/docs/jev-decisions.md) · [Retrieval Memory](https://github.com/Marker-Inc-Korea/AutoRAG/blob/v2.13.4/docs/retrieval-memory.md)
- [공통 레퍼런스](../../docs/reference-catalog.md) · [MVP 설계](../../docs/query-agent-mvp.md)
