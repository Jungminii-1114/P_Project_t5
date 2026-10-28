# 후속 작업

baseline-1은 v23(`64ac263`, tag `v23`)의 동작을 보존하는 참조점이다. baseline-2의 실험 완료와 실무 이관 상태를 아래에 기록한다.

| ID | 항목 | 설명 | 선행 조건 | 관련 문서 |
|---|---|---|---|---|
| B1 | 2차 베이스라인 — 실험 완료 | 파서 패키지·표 IR·렌더러 3종과 V0~V4 비교를 완료했다. 엄격 골든 실패와 남은 표 오류는 보존하며 표 문제가 해결됐다는 뜻은 아니다. | 파서 출력 계약 준수 | [결과](reference/baseline2/EVAL.md), [검증](reference/baseline2/VALIDATION.md), [인계](reference/baseline2/HANDOFF.md) |
| B2 | VLM 표 파싱 대조 — 실무 프로젝트로 이관 | baseline-1·baseline-2·VLM을 원문 골든, BM25 대리 지표, RAG 정답 수·시간으로 비교한다. 이번 저장소에서는 VLM을 실행하지 않는다. | B1 결과 및 IR 어댑터 계약 | [VLM 연결 지점](reference/baseline2/HANDOFF.md) |
| B3 | F2 짝 검사 오탐 수정 | 개체–숫자 연결 검사의 오탐과 미탐을 다룬다. B1에서 IR이 생기면 함께 처리할지 검토한다. | 오탐·미탐 근거 확인, B1 연계 검토 | [KNOWN_ISSUES](reference/baseline1/KNOWN_ISSUES.md) |
| B4 | 노트북 검증 | Jupyter 커널과 Colab에서 노트북 실행을 확인한다. 현재 보존된 확인은 exec 기반 실행이다. | 해당 실행 환경 준비 | [EVAL](reference/baseline1/EVAL.md) |
| B5 | 독립 테스트셋 | 기존 세트가 모두 개발에 사용되었으므로 별도의 독립 평가셋을 마련한다. | 독립 수집 및 채점 기준 정의 | [EVAL](reference/baseline1/EVAL.md) |
| B6 | 홈페이지 주소 원문 대조 | 저장된 홈페이지 smoke 결과와 원문·인용 위치를 직접 대조한다. 자동 검사 기록과 수동 확인을 구별한다. | 원문 확보 | [KNOWN_ISSUES](reference/baseline1/KNOWN_ISSUES.md) |
| B7 | 범용판 RAG 평가 | 중립 설정의 청크를 실제 파이프라인에 넣어 평가하고 다른 문서군에서도 시험한다. API 사용이 필요한 후속 작업이다. | 범용판 및 API 실행 승인, 평가 문서군 준비 | [프로필 비교](reference/baseline1/docparse_generic/PROFILE_DIFF.md), [EVAL](reference/baseline1/EVAL.md) |
| B8 | 파이프라인 특화 값 분리 | 검색·라우팅·프롬프트의 문서·도메인 특화 값을 설정으로 분리한다. | 현행 설정 목록 확인 | [CONFIG](reference/baseline1/CONFIG.md) |
| B9 | 실험·실습 노트북 | py 레퍼런스 모듈을 import해 단계별(원문·파싱·청킹·문맥 청크·프로필)로 실행하고 확인하는 노트북을 만든다. 로직은 py에만 두고, git에는 출력을 지운 상태로 커밋한다. | baseline-1 레퍼런스 | [PARSER](reference/baseline1/PARSER.md), [범용판 README](reference/baseline1/docparse_generic/README.md) |
