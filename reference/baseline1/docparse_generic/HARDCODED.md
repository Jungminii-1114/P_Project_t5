# 동결판 하드코딩 목록

이 목록은 `reference/baseline1/docparse_b1/`의 파서와 CLI를 대상으로 한다. 값 하나씩을 무조건 설정으로 옮기라는 뜻은 아니다. 동결판의 구성 값 중 범용판에서 바꾸어 쓸 항목은 `ParserConfig`와 프로필로 옮기고, 파서 형식의 구조와 알려진 한계는 알고리즘을 바꾸지 않고 문서화한다.

## 유형별 항목 수

아래 수는 이 문서의 인벤토리 표에서 각 규칙을 한 행으로 묶어 센 값이다. 파일명이나 표 셀 값처럼 같은 역할의 여러 문자열은 한 항목으로 센다.

| 유형 | 항목 수 | 범용판 처리 |
|---|---:|---|
| 문서 특화 | 2 | 고정 파일명과 제목 매핑을 설정으로 이동한다. 기본값은 빈 목록·빈 매핑이다. |
| 도메인(입시) 특화 | 5 | 헤더·행 라벨·제외 열·일정·일반 열 규칙을 `gachon_2027` 프로필로 이동한다. 중립 기본값은 비워 둔다. |
| 언어(한국어) | 2 | 설정 가능하게 두고 동결판과 같은 한국어 기본 구분·날짜 정규화를 유지한다. |
| 튜닝값 | 8 | `ParserConfig` 기본값을 동결판 값으로 둔다. 필요한 값은 프로필에서 조정할 수 있다. |
| 환경 | 5 | 파서 구현 선택과 실행 환경 정보로 남기고, CLI에서 입력 경로를 받는다. API·Colab 탐색은 포함하지 않는다. |
| 형식 한계·구조 | 18 | 표·문서 포맷과 메타데이터 계약으로 문서화한다. 알고리즘 변경은 하지 않는다. |
| **합계** | **40** |  |

## 문서 특화

| ID | 위치 | 동결판 값·규칙 | 유형 | 범용판 처리 |
|---|---|---|---|---|
| D1 | `constants.py:REQUIRED`, `sources.py:required_files` | `01_2027학년도_재외국민_모집요강.hwp`, `02_2027학년도_지역의사선발전형_안내.pdf`, `03_2027학년도_수시_모집요강.pdf`, `04_2027학년도_정시_모집요강.pdf`, `05_2027학년도_수시_면접고사_일정.pdf`를 이 순서로 요구한다. | 문서 특화 | 선택 입력 `required_files`로 이동한다. 기본값은 빈 목록이며, 설정하면 누락 파일을 오류로 알린다. Gachon 프로필이 다섯 파일명을 제공한다. |
| D2 | `constants.py:DOC_TITLES`, `context.py:doc_title` | basename의 앞 두 글자(`01`~`05`)로 제목을 찾고, 없으면 원본 basename을 사용한다. 제목 매핑은 `2027학년도 재외국민 모집요강`, `2027학년도 지역의사선발전형 안내`, `2027학년도 수시 모집요강`, `2027학년도 정시 모집요강`, `2027학년도 수시 면접고사 일정`이다. | 문서 특화 | 제목 매핑과 prefix 길이를 설정으로 이동한다. 기본 매핑은 비우고 파일명 stem에서 앞 번호와 `_`를 정리한 제목을 결정적으로 만든다. Gachon 프로필은 제목과 prefix 길이 2를 제공한다. |

## 도메인(입시) 특화

| ID | 위치 | 동결판 값·규칙 | 유형 | 범용판 처리 |
|---|---|---|---|---|
| A1 | `table.py:parse_table` | 헤더 시작 행을 찾을 때 `학과`, `학부`, `전공`, `의예과`, `지역`이 들어간 셀을 검사한다. | 도메인(입시) 특화 | `header_keywords`로 이동한다. 중립 기본값은 빈 목록이며, 비어 있으면 기존 대체 경로인 `start=1`을 쓴다. Gachon 프로필에 원래 키워드를 둔다. |
| A2 | `table.py:row_summary` wide 모드 | 행 라벨은 `학과`, `학부`, `전공`, `지역` 중 하나가 들어간 첫 셀이다. | 도메인(입시) 특화 | `row_label_keywords`로 이동한다. 중립 기본값이 비면 새 키워드 휴리스틱을 만들지 않고 기존 roster 방식(첫 값 앞의 비값 셀)을 쓴다. Gachon 프로필에 원래 키워드를 둔다. |
| A3 | `table.py:row_summary` wide 모드 | 열 이름이 `모집단위`인 쌍은 요약에서 제외한다. | 도메인(입시) 특화 | `excluded_columns`로 이동한다. 중립 기본값은 빈 목록, Gachon 프로필에는 `모집단위`를 둔다. |
| A4 | `table.py:parse_table` | 헤더에서 월·일·시간·일시·오전·오후 표식을 정규식으로 찾으면 일정 표로 간주하고 표제 `면접/전형 일정`을 붙인다. 월·일 표식은 숫자 뒤에 `월` 또는 `일`이 오는 형식이다. | 도메인(입시) 특화 | `schedule_pattern`과 `schedule_caption`으로 이동한다. 중립 기본값은 패턴·표제 모두 비워 일정 분류를 끈다. Gachon 프로필이 기존 패턴과 표제를 제공한다. |
| A5 | `constants.py:GENERIC_COLS`, `table.py` | `비고`, `계열`, `연번`, `번호`, `구분`은 일반 열로 보고 캡션·행 요약의 후보에서 제외한다. | 도메인(입시) 특화 | `ParserConfig.generic_columns`로 이동한다. 중립 기본값은 빈 목록, Gachon 프로필은 원래 다섯 값을 제공한다. |

## 언어(한국어)

| ID | 위치 | 동결판 값·규칙 | 유형 | 범용판 처리 |
|---|---|---|---|---|
| L1 | `text.py:normalize` | `[ \t]+`를 공백 하나로 바꾸고, `(?<=\d)\s*\.\s*(?=\d)`를 `.`로 바꾼다. 빈 줄은 결과에서 뺀다. 날짜의 `YYYY . MM . DD .` 표기를 정리한다. | 언어(한국어) | `whitespace_pattern`, `date_dot_pattern`, `normalize_date_dots`로 설정한다. 한국어 기본값은 동결판과 같은 동작을 유지한다. |
| L2 | `chunk.py:splitter` | 문장 분리자 목록 `\n\n`, `\n`, `. `, `다. `, 공백, 빈 문자열을 이 순서로 사용한다. | 언어(한국어) | `ParserConfig.separators`로 이동한다. 기본값은 한국어 문서에 적합하도록 동결판 목록을 유지하고 프로필에서 덮어쓸 수 있다. |

## 튜닝값

| ID | 위치 | 동결판 값·규칙 | 유형 | 범용판 처리 |
|---|---|---|---|---|
| T1 | `chunk.py:splitter` | 본문 `chunk_size=800`, `chunk_overlap=100`. | 튜닝값 | `ParserConfig`의 본문 크기·겹침 기본값으로 유지한다. |
| T2 | `chunk.py:split_table_markdown` | 표 조각 최대 길이 `max_chars=1400`. | 튜닝값 | `ParserConfig.table_max_chars` 기본값으로 유지한다. 조각 경계 비교와 행 단위 분할 알고리즘은 그대로 둔다. |
| T3 | `hwp.py:render_hwp_table` | 병합 셀 영역이 40자 이하이면 텍스트를 각 병합 칸에 반복한다. 40자 초과이면 좌상단 칸에만 둔다. | 튜닝값 | `ParserConfig.merged_repeat_max_chars=40`으로 이동한다. |
| T4 | `pdf.py:parse_pdf` | 정규화된 PDF 표 markdown 길이가 `60`보다 클 때만 요소로 추가한다. | 튜닝값 | `ParserConfig.pdf_table_min_chars=60`으로 이동한다. 비교 조건은 원래와 같은 `>`다. |
| T5 | `table.py:parse_table` | `width >= 7`이면 wide 모드다(일정표 감지 또한 wide 모드로 분류). | 튜닝값 | `ParserConfig.wide_min_columns=7`로 이동한다. |
| T6 | `table.py:row_summary` | 행 요약은 최대 `30`행·`2600`자다. 상한을 넘는 첫 행에서 중단한다. | 튜닝값 | `ParserConfig.summary_max_rows`, `summary_max_chars` 기본값으로 둔다. |
| T7 | `table.py:row_summary` | 한 행에 표시하는 열=값 쌍은 `pairs[:6]`으로 제한한다. | 튜닝값 | `ParserConfig.summary_max_pairs=6`으로 이동한다. 초기 목록에는 없던 값이다. |
| T8 | `table.py:parse_table` | 표제 후보는 첫 헤더 셀의 첫 30자다. | 튜닝값 | `ParserConfig.caption_max_chars=30`으로 이동한다. 초기 목록에는 없던 값이다. |

## 환경

| ID | 위치 | 동결판 값·규칙 | 유형 | 범용판 처리 |
|---|---|---|---|---|
| E1 | `hwp.py:parse_hwp` | `HwpHwpxLoader(..., mode="elements", distribution_backend="pyhwp")`로 HWP를 읽는다. | 환경 | `ParserConfig.hwp_mode`, `hwp_distribution_backend`로 노출한다. 동결판 재현 프로필은 `elements`/`pyhwp`를 지정한다. |
| E2 | `pdf.py:parse_pdf` | PyMuPDF로 페이지 텍스트를 읽고, pdfplumber `extract_tables()`로 표를 읽는다. | 환경 | 문서화만: 이 두 라이브러리의 추출 순서와 구현은 고정 알고리즘으로 유지한다. PDF 파서 교체 설정은 추가하지 않았다. |
| E3 | constants.py:PARSER_VERSIONS, sources.py:build_document_manifest | .suffix.lower() 결과 .hwp는 hwp-elements-pyhwp-v1, .pdf는 pymupdf-text-pdfplumber-v1로 manifest에 기록한다. 미지원 suffix는 오류다. | 환경 | manifest 구현 식별자로 문서화한다. 확장자 dispatch는 파서가 지원하는 형식 계약으로 유지한다. |
| E4 | `__main__.py` | lock에서 `langchain-core`, `langchain-text-splitters`, `langchain-hwp-hwpx-loader`, `pdfplumber`, `pymupdf` 버전을 기록한다. CLI는 데이터 폴더와 필수 `--out` 경로를 받는다. | 환경 | 패키지 버전 기록은 실행 환경 정보다. 범용판 CLI는 파일·폴더·glob 경로와 프로필을 받으며 현재 작업 폴더에 의존하지 않는다. |
| E5 | `sources.py:_sha256_file` | 파일 해시를 읽을 때 1 MiB 블록(`1024 * 1024`) 단위로 처리한다. 원본 manifest에는 SHA-256, `size_bytes`, `parser_version`을 기록한다. | 환경 | 로컬 파일 I/O 및 manifest 형식으로 유지한다. 경로 검색·zip·Drive·업로드는 동결판 패키지에서 제외되어 있다. |

## 형식 한계·구조

| ID | 위치 | 동결판 값·규칙 | 유형 | 범용판 처리 |
|---|---|---|---|---|
| F1 | hwp.py:parse_hwp | loader metadata의 element_type 값이 body 또는 table일 때 처리한다. HWP 본문은 page_content.strip() 후 비어 있지 않은 경우만 추가하고, table은 cells JSON(기본 "[]")을 렌더링한 결과가 비어 있지 않을 때 추가한다. | 형식 한계 | loader 출력 스키마 계약으로 문서화한다. 인식하지 못하는 element type은 기존처럼 무시한다. |
| F2 | hwp.py:render_hwp_table | 셀 JSON에서 row, col, text, rowspan, colspan을 읽는다. span 누락·0 값은 1로 보정한다. 빈 기본 셀은 ""이며 표 폭·높이는 row + rowspan, col + colspan의 최댓값으로 계산한다. | 형식 한계 | HWP loader 출력 스키마로 문서화한다. 필드명과 기본 span 보정 알고리즘은 설정에 옮기지 않는다. |
| F3 | hwp.py:_MARKER, render_hwp_table | rowspan=N, colspan=M, 반대 순서 표기, merged:... 모양의 [ ... ] 구조 마커를 제거한다. [IMAGE] 셀은 빈 셀로 만든다. | 형식 한계 | ParserConfig.hwp_marker_pattern과 image_marker로 노출한다. 동결판과 프로필은 원래 값을 사용한다. |
| F4 | `hwp.py:render_hwp_table` | 셀 텍스트는 split()/공백 join으로 정리하고 파이프 문자를 slash로 바꾼다. 병합 span의 모든 칸을 순회한다. 이전 행과 완전히 같은 행 및 빈 행은 markdown에서 제외한다. 첫 행 아래 markdown divider를 만든다. | 형식 한계 | 표 markdown 직렬화 계약으로 유지한다. 알고리즘 변경은 하지 않는다. |
| F5 | `hwp.py:parse_hwp` | HWP 본문은 항상 `page=1`; 표는 `element_index + 1`을 `page`로 쓴다. `element_index`가 없으면 0을 쓴다. 이는 실제 페이지 번호가 아니다. | 형식 한계 | 기존 `page` 값은 유지한다. 범용판은 `locator`에 element index 의미를 추가한다. |
| F6 | `pdf.py:parse_pdf`, `rows_to_markdown` | PDF page 번호는 1부터 시작한다. 표의 첫 행을 열 제목으로 두고 두 줄 미만의 표는 버린다. 행의 개수가 짧으면 빈 셀을 덧붙이고, 빈 열·행은 제거하며, 셀 줄바꿈은 공백, 셀 내부 파이프 문자는 slash로 바꾼다. | 형식 한계 | PDF 행→markdown 규약으로 문서화한다. 표 구조 복구 알고리즘은 변경하지 않는다. |
| F7 | pdf.py:parse_pdf | 각 PDF page의 get_text("text") 결과를 먼저 본문 요소로 추가하고, pdfplumber extract_tables() 결과는 모든 페이지의 본문을 처리한 뒤 표 요소로 추가한다. metadata kind는 text 또는 table이다. | 형식 한계 | 원본·페이지 순서와 kind 값은 파서 출력 계약이다. 실제 페이지 번호를 유지한다. |
| F8 | `table.py:parse_table` | 줄 양끝 공백을 제거한 뒤 파이프로 시작하는 줄만 표 행으로 읽는다. 양끝 파이프를 제거하고 다시 파이프로 셀을 나눈다. 각 셀이 하이픈·콜론·공백으로만 구성된 행은 구분선으로 버린다. | 형식 한계 | Markdown 표 문법 지원 범위로 문서화한다. 다른 표 포맷 인식은 추가하지 않는다. |
| F9 | `table.py:parse_table` | 첫 셀이 `※`로 시작하는 행은 데이터에서 제외한다. 표 행이 없으면 `("", "roster", [], [])`를 돌려준다. | 형식 한계 | 빈 줄 표식은 `ParserConfig.note_prefix`로 설정한다. 빈 표의 반환 튜플은 형식 계약으로 유지한다. |
| F10 | table.py:parse_table | 모든 표 행을 순서대로 훑어 도메인 헤더 키워드가 들어간 첫 행을 start로 쓴다. 키워드가 없거나 첫 행에서 발견되면, 행이 둘 이상일 때 기존 대체 경로로 start=1, 하나면 start=0을 쓴다. | 형식 한계 | header_keywords가 빈 기본값이면 기존 대체 경로 start=1을 유지한다. 새 휴리스틱은 추가하지 않는다. |
| F11 | table.py:parse_table, row_summary | 표 폭은 모든 행의 최대 셀 수이며 최소 1이다. 처리 모드는 wide와 roster다. 넓이·일정 분류 후 wide는 헤더 열을 펼치고, roster는 마지막 헤더 행과 반복 셀 제거를 사용한다. | 형식 한계 | 두 알고리즘은 설정 입력에 따라 호출하되 그대로 유지한다. 빈 행 라벨 키워드는 roster 방식으로 처리한다. |
| F12 | `table.py:expand_header` | 각 header row의 마지막 비어 있지 않은 셀 전까지 빈 칸을 왼쪽 값으로 채운다. 같은 열에서 연속 중복되는 텍스트는 한 번만 두고 위→아래 값을 공백으로 결합한다. | 형식 한계 | 다단 헤더 처리 알고리즘과 한계를 문서화한다. 수정하지 않는다. |
| F13 | table.py:dedup_cells, row_summary roster 분기 | is_value가 참인 첫 셀 뒤는 반복 제거하지 않는다. roster 요약은 앞뒤 빈 칸을 먼저 제거하고, 너비 초과분은 첫 값 전에 라벨 셀이 둘 이상 남을 때 앞의 두 셀을 합친다. 남는 셀은 왼쪽 빈 칸으로 채운다. 값 포함 셀이 2개 미만이거나 열을 맞출 수 없으면 행을 건너뛴다. | 형식 한계 | 현 동결판 fallback으로 유지한다. 별도 일반 행 라벨 휴리스틱은 만들지 않는다. |
| F14 | `table.py:row_summary` wide 분기 | wide 행은 첫 라벨 키워드 셀을 라벨로 삼고, 빈 값·라벨 자체·일반 열·열 이름과 값이 같은 쌍을 제외한다. 각 요약 행 형식은 `- 라벨: 열=값, ...`이다. | 형식 한계 | 라벨·제외 열은 설정에서 온다. 형식과 기존 분기 로직은 유지한다. |
| F15 | `table.py:is_value` | 셀 값은 `^[\d,./~%()~\-–\s]+$` 숫자 패턴 일치 또는 기호 `O`, `■`, `□`, `△`, `○`, `●`, `X`, `▲`, `★`, `◉`일 때 값으로 취급한다. | 형식 한계 | `ParserConfig.numeric_pattern`, `value_symbols`로 설정한다. 이 숫자·기호 판정은 문서명이 아닌 표 형식 규칙이며 중립 기본값에도 보존한다. |
| F16 | `chunk.py:split_table_markdown`, `_hard_split` | 표의 처음 두 줄(첫 표 헤더와 markdown 구분선)을 고정 헤더로 반복하고 나머지 줄을 차례로 묶는다. 한 행이 길면 공백 기준 분할을 적용한다. 공백 없는 단일 token은 limit보다 길어도 더 나누지 않는다. 실제 두 번째 헤더 행은 body로 처리되므로 첫 조각에만 들어갈 수 있고 이후 조각에서는 반복되지 않는다. | 형식 한계 | `ParserConfig.table_max_chars`만 설정하고 기존 분할 구조와 한계를 문서화한다. 알고리즘은 바꾸지 않는다. |
| F17 | `chunk.py`, `context.py` | 원문 청크 접두사는 `[source p.page]`와 줄바꿈이다. 문맥 청크는 `[문서] title`, `p.page`, `표/본문` 라벨, 선택적 `표제: caption`, `[표 행 요약]`, `[원문]`을 사용한다. kind가 table인 경우만 표 라벨을 쓰고 그 외에는 본문 라벨이다. page_content에는 요약+원문을 두고 metadata.raw에는 원문, metadata.title에는 제목을 둔다. | 형식 한계 | `chunk_prefix_template`, `context_header_template`, `caption_template`, `kind_labels`, `summary_marker`, `raw_marker`로 설정한다. 원문과 색인 텍스트의 분리는 출력 계약으로 유지한다. |
| F18 | sources.py, chunk.py, __main__.py | metadata 필드 source, page, kind, part, chunk_id, 문맥 추가 필드 raw, title을 사용한다. part는 원문 요소별 0부터 시작하고 chunk_id는 전체 청크 순번이다. CLI JSONL은 page_content, metadata 키를 compact UTF-8 JSON으로 저장하고 객체 키를 정렬하며 각 행 끝에 newline을 둔다. 파일명은 raw_docs.jsonl, chunks.jsonl, contextual_chunks.jsonl, manifest.json이다. | 형식 한계 | 파서 출력 계약·CLI 직렬화 형식으로 문서화한다. 범용판도 기존 필드값은 보존하고 locator만 추가 metadata로 허용한다. |

## 초기 목록에 없던 세부 항목

초기 작업계획서의 하드코딩 목록은 주요 도메인값과 조정값을 요약했다. 코드를 대조해 아래 구현 세부도 추가로 기록했다.

1. `summary_max_pairs=6`과 `caption_max_chars=30`의 상한.
2. HWP 셀 JSON 필드명·span 기본값, 구조 마커 정규식과 `[IMAGE]` 처리.
3. HWP 본문 `page=1`, 표 `element_index + 1` 및 없는 index의 0 대체.
4. PDF 표 첫 행 헤더 처리, 빈 행·열 제거, 셀 줄바꿈/파이프 치환, 2행 미만 제외.
5. 텍스트 정규화의 공백 regex 및 빈 줄 제거.
6. Markdown 표 행 시작·구분선 판정과 `※` 행 필터.
7. header keyword 미검출·첫 행 검출 시의 구체적 `start` fallback.
8. roster 요약의 반복 라벨 축약, 빈 셀 정렬, 과다 너비 합치기 및 행 생략 조건.
9. wide 요약의 열 이름과 값이 같은 쌍 제외, 한 행에서 최대 여섯 쌍 출력.
10. SHA-256 파일 읽기의 1 MiB 블록 단위와 manifest 필드 구성.
11. 메타데이터 키·값과 `part`/`chunk_id`의 순번 의미.
12. JSONL/manifest 이름·레코드 스키마 및 lock에 기록하는 실행 패키지 목록.
13. 동결판 패키지에는 `/content`, zip/Drive 탐색, 업로드 코드가 없으며 지정한 로컬 폴더만 검사한다.

## 범용 소스 문자열 금지 목록

`tests/test_reference_generic.py`는 아래 목록을 `profiles/` 밖의 범용판 소스에 검사한다. Gachon 전용 값은 `profiles/gachon_2027.py`에만 둔다. 목록은 금지 문자열을 만드는 출처이지 일반 소스에 값을 옮겨 적으라는 뜻이 아니다.

```text
가천
가천대
2027
입학
모집
모집요강
모집단위
학과
학부
전공
의예과
지역의사
지역
재외국민
수시
정시
면접
전형
면접/전형 일정
01_
02_
03_
04_
05_
/content
dataset.zip
MyDrive
```

### 제외하거나 중립적으로 남기는 포맷 문자열

다음 값은 Gachon 도메인 문자열이 아니라 파서 입출력·형식 syntax이므로 위 금지 목록에는 넣지 않는다: `.hwp`, `.pdf`, `rowspan`, `colspan`, `merged:`, `[IMAGE]`, Markdown `|`/`---`, metadata 필드명, `page_content`, `raw`, `title`, `locator`, `text`/`table`, `wide`/`roster`, `\n`, `p.`, JSONL 파일명. `GENERIC_COLS`의 값, 헤더·행 라벨 키워드와 일정 키워드는 프로필 밖 소스의 기본값에 두지 않는다. 기호 집합과 숫자 패턴은 일반 표 형식 규칙이므로 중립 설정 기본값에 유지한다.
