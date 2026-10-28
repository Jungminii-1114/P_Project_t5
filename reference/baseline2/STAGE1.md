# baseline-2 1단계 (API 없음)

기준은 baseline-1 / 3fbba3f이다. 패키지 동일성 커밋은 2e2375b이다.
원본 빌더·v23·노트북·동결 reference·legacy를 보존했다. `src/docparse`를 src 레이아웃으로 설치하고 표 IR·렌더러 3종·v24 빌더/평가 옵션을 추가했다.

## 동일성 및 구조

baseline-1 raw_docs 382개, chunks 513개, contextual_chunks 513개 JSONL의 SHA-256이 manifest와 같았다. 설치 패키지의 세 출력도 locator를 제외하고 바이트 단위로 같다.

표 209개: PDF cells 191개, HWP cells 18개, pdf_fallback 0개(추출된 PDF 표 중 0%). 미탐지 선 없는 표까지 복구했다는 뜻은 아니다.
헤더/라벨 불확실 118/209(56.5%), 다단 헤더 39개. 불확실한 표는 기존 출력으로 돌아간다.
crop와 기존 추출값 비교: 7481셀 중 372셀 차이, 7개 표에서 발생했다. 셀별 원문은 ignored IR diagnostics에 보존한다.

골든: 표 2/10, 셀 삼중항 11/54. 실패를 포함한 목록과 PNG 위치는 GOLDEN.md에 있다. 기대값은 사용자 검토 대기다. 엄격 골든 수용 검사는 실패하며, 구조 테스트의 성공과 구별한다.

## BM25 페이지 적중 대리 지표

하이브리드 검색 결과가 아니다. pipeline과 동일한 Kiwi 품사 태그만 사용하고 dense·라우팅·동의어·가중치를 적용하지 않는다. 상위 k 청크의 PDF 페이지 중 src 페이지가 하나 이상 나타난 문항 수다. 여러 출처를 모두 맞춘 지표는 metrics/bm25.json에 따로 있다.

| 세트 | PDF 채점 문항 | HWP만 있는 문항 제외 | baseline1 k=1/3/8 | header_records k=1/3/8 |
|---|---:|---:|---|---|
| drive20 | 17 | 3 | 11 / 14 / 17 | 11 / 14 / 16 |
| hard | 16 | 4 | 2 / 6 / 9 | 2 / 6 / 10 |
| holdout | 9 | 1 | 5 / 7 / 8 | 5 / 7 / 8 |

공식 sample3의 3문항에는 src가 없어 이 지표에서 제외했다. 나머지 50문항 중 HWP만 있는 8문항을 제외하고 42문항을 채점했다. 혼합 출처는 PDF 부분만 채점하고 HWP 참조는 제외한다. PDF src가 파일 페이지인지 3개 문항의 원문 PNG와 대조했으며 기록은 prepare_golden_tables.py의 page_number_validation.json에 있다.

## 길이 및 상한

| 렌더러 | min | p50 | p90 | p95 | max | 12000자 초과 표 |
|---|---:|---:|---:|---:|---:|---:|
| html_full | 110 | 409 | 2474 | 3866 | 7903 | 0 |
| header_records | 35 | 378 | 3145 | 6828 | 151741 | 7 |

상한 12,000자는 측정한 HTML 최대 7,903자를 수용하고 신규 대형 표의 전달을 제한하기 위해 정했다. 레코드 길이에는 사용하지 않는 uncertain 표의 진단값도 포함한다. confident 표만의 분포와 초과 표의 source/page/table_id 목록은 metrics/structure.json에 있다.

## 변경 범위와 검증

v23 대비 전체 diff는 PIPELINE_V23_V24.diff에 있다. 파서 §1~4, 설정, Chroma 스칼라 복사, 임베딩 캐시, _context만 연결했다. 검색·검증·프롬프트·모델·마감은 보존했다.
키 3종을 제거하고 소켓을 차단한 별도 프로세스에서 파싱·BM25가 성공했고 pytest 64개가 통과했다(76.73초). 결과는 metrics/api_free.json, 로그와 JUnit은 runs/baseline2/에 있다.
`git diff baseline-1 -- reference/ ...`의 문자 그대로의 빈 diff 요구는 새 baseline2 문서 추가 요구와 양립하지 않는다. 동결 대상 reference/baseline1/, legacy/, 원본 빌더·v23·노트북의 diff가 비었는지 별도로 확인한다.

## 승인된 2단계 실행 계획

사용자가 1단계 작업 중 API 평가를 명시적으로 승인했다. 1단계 완료 커밋과 v24 태그를 만든 뒤 실행한다.
변형: V0 baseline1/baseline1, V1 header_records/baseline1, V2 baseline1/html_full, V3 header_records/header_records, V4 header_records/html_full.
각 변형에 sample3+hard20+holdout10+drive20=53문항, 기본 5회 실행(265문항). 예상 답변·채점 호출은 265×(초안 1+교정 약 0.75+채점 1) ≈729회와 변형별 예열 1회다. 최소 535회, 교정 1회씩이면 800회 수준이며 추가검색 재초안은 별도다.
청크 색인 텍스트는 두 종류이므로 같은 텍스트를 캐시에서 재사용한다. 기존 페이지 색인은 LLM raw로 만들어 렌더러별로 추가 임베딩이 생길 수 있다. 이를 분리하는 1줄 변경은 사용자가 승인하지 않아 한계로 보존했다. 질의 캐시는 별도다. 임베딩 API 요청 수는 공급자 배치 크기에 따라 달라진다.
baseline-1 저장 실행의 53문항 답변 평균 6.35초를 기준으로 채점·색인까지 포함해 기본 비교 약 35~60분을 예상한다. 동률 재시험이면 상위 2변형별 sample3×3+drive20×1(58문항), 선정 후 sample3×3(9문항)이 추가될 수 있다.
V0는 세트별 정답 수가 baseline-1 대비 ±2 이내이고 모든 응답이 19초 미만이어야 한다. 실패하면 V1~V4를 실행하지 않고 멈춘다.
