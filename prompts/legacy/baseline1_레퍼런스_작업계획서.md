# 1차 베이스라인 레퍼런스 작업계획서 — 가천대 입학 안내 Agentic RAG (워커 전달용)

> 이 문서만 보고 작업할 수 있도록 썼습니다. 모르는 점이 생기면 §4의 멈춤 조건을 먼저 확인하세요.

## 0. 목표와 범위

**목표**: v23(tag `v23`, commit `64ac263`)을 **1차 베이스라인(baseline-1)**으로 동결하고, 다른 프로젝트(실무)에서 참고·재사용할 수 있는 두 가지 레퍼런스를 만든다.

- **R1 파싱 레퍼런스 (동결판)**: 원문 5개 → 파싱 → 청킹 → 색인용 문맥 청크까지를 LLM·벡터DB 없이 단독 실행되는 패키지로 분리한다. 동작은 v23과 **바이트 단위로 동일**해야 한다.
- **R1-G 파싱 레퍼런스 (범용판)**: 동결판에서 **현 문서·도메인에 특화된 하드코딩을 덜어낸** 별도 패키지다. 실무 프로젝트에 가져갈 것은 이쪽이다.
  - 특화 값은 모두 설정 객체(`ParserConfig`)와 프로필로 옮긴다.
  - **가천대 프로필**로 실행하면 동결판과 출력이 같아야 한다.
  - **중립 기본값**으로 실행하면 임의의 HWP/PDF에 그대로 쓸 수 있어야 한다.
- **R2 프로젝트 레퍼런스**: 전체 파이프라인의 구조·설정·평가 방법·실험 이력·알려진 문제를 문서로 정리하고, v23 코드를 레거시로 보존한다.
- **부가 산출물**: 이후 파서(2차 베이스라인, VLM)가 같은 파이프라인에 끼워질 수 있도록 **파서 출력 계약(INTERFACE)**을 문서화하고, 후속 작업을 `BACKLOG.md`에 등록한다.

**범위 밖 (하지 말 것)**
- 동작 변경 전부: F2 오탐 수정, 표 파싱 개선, IR 도입, 검색·프롬프트·모델 변경.
  - 유일한 예외는 범용판의 **중립 기본값**이다. 이때는 특화 규칙이 빠지므로 출력이 달라지는 것이 정상이다.
  - 그 경우에도 알고리즘 자체(병합 셀 전개, 헤더 반복 분할, 행 요약 방식)는 바꾸지 않는다. 바꾸는 것은 하드코딩된 값과 규칙의 출처뿐이다.
- 2차 베이스라인 구현, VLM 파싱, 파서 간 대조 실험. 모두 백로그 항목이다.
- API 호출(OpenAI, Voyage). **이 작업 전체는 API 없이 끝나야 한다.** 필요해 보이면 멈추고 물어볼 것.
- 파이프라인(`build_notebook.py`, `pipeline_v23.py`)의 구조 변경. 레퍼런스는 **복사본**으로 만든다.

**원칙**
- 레퍼런스 코드는 v23 코드를 그대로 옮긴다. 허용되는 변경은 import 정리, 전역 실행 코드를 함수로 감싸기, 전역변수를 인자로 바꾸기, `print` 제거뿐이다. 모든 변경을 `CHANGES.md`에 기록한다.
- 문서의 수치·결과는 저장된 파일(run 로그, `eval/*.json`, 보고서)에서만 가져오고 출처를 적는다. 추정하거나 지어내지 않는다.
- 평가셋의 질문·정답 문장을 코드에 넣지 않는다(README 금지 규칙). 문서에서 실패 사례를 설명할 때는 세트 이름과 문항 ID로 가리킨다.
- API 키 값을 출력·커밋·로그에 남기지 않는다.

## 1. 현재 상태 (반드시 먼저 읽을 것)

| 파일 | 내용 |
|---|---|
| `build_notebook.py` | 유일한 원본. 제출 노트북과 `pipeline_v23.py`를 생성한다. |
| `pipeline_v23.py` | 자동 생성물. **import하면 키 확인·임베딩·색인까지 전부 실행**되므로 파서만 따로 쓸 수 없다. |
| `202235052_박진성.ipynb` | v23 노트북(27셀, 코드 13셀). |
| `legacy/` | `build_notebook_v6.py`, `build_notebook_v22.py`, `experiments_v1_v7.py`, v6 노트북. |
| `scripts/run_eval.py` 외 | 평가 러너, 비교, 노트북 실행·점검 스크립트. |
| `eval/` | 테스트셋(hard, holdout, drive20), `results_v21/v22/v23.json`, F1·F2 검증 산출물. |
| `runs/` (gitignore) | 실행 로그. v23 기준 실행: `20261028_123828_709846_v23`, sample3 반복 3회: `20261028_1247*`, `1248*` 폴더. |
| `REPORT_중간평가_진행상황.md` | 세션 1~5 실험 이력 전체. |
| `README_LOCAL.md` | 로컬 실행 방법. |
| `data/dataset/` (gitignore) | 원문 5개. 환경변수 `GACHON_DATA_DIR`로 지정. |

**노트북 섹션과 `build_notebook.py` 위치 (v23 기준, 대략적 줄 번호)**

| 섹션 | 줄 | API 사용 | 주요 함수 |
|---|---|---|---|
| 0. 환경 설정 / 0-2 API 키 | 59~120 | 키 존재 확인만 | `load_api_key` |
| 1. 데이터 준비 | 122~298 | 없음 | `required_files`, `build_document_manifest`, `prepare_dataset` |
| 2. 문서 파싱 | 299~430 | 없음 | `normalize`, `render_hwp_table`, `rows_to_markdown`, `parse_hwp`, `parse_pdf` |
| 3. 청킹 | 431~493 | 없음 | `_hard_split`, `split_table_markdown` |
| 4. 색인용 문맥 청크 | 494~678 | 없음 | `doc_title`, `dedup_cells`, `is_value`, `expand_header`, `parse_table`, `row_summary`, `build_contextual_chunks` |
| 5. 벡터 DB + BM25 | 679~766 | **임베딩** | |
| 6~9. 라우팅·검색·검증·답변 | 767~1585 | **LLM** | |

섹션 0~4는 API 없이 실행된다(확인 완료). 다만 0-2 키 셀에는 키가 없으면 실패하는 `assert`가 있다.

**파싱 코드(섹션 1~4)의 하드코딩 — 초기 목록**

아래는 계획 작성자가 코드를 읽고 찾은 것이다. 완전한 목록이 아니므로 단계 3-G에서 워커가 전수 조사해 보완한다.

| 위치 | 하드코딩 내용 | 유형 |
|---|---|---|
| §1 `REQUIRED`, `parse_required_files` | 고정 파일명 5개만 파싱 | 문서 특화 |
| §1 `DATA_DIR`, `prepare_dataset`, `_extract`, `_bounded_find` | `/content/dataset`, zip·Drive 탐색 | 환경(Colab) |
| §4 `DOC_TITLES`, `doc_title` | 파일명 앞 2글자(`"01"`~`"05"`) → 문서 제목 | 문서 특화 |
| §4 `parse_table` | 헤더 끝 판별 키워드 `학과/학부/전공/의예과/지역` | 도메인(입시) 특화 |
| §4 `parse_table` | 일정표 판별 정규식(`월/일/시간/일시/오전/오후`), 표제 문자열 `"면접/전형 일정"` | 도메인 특화 |
| §4 `row_summary` (wide) | 행 라벨 키워드 `학과/학부/전공/지역`, 제외 열 `"모집단위"` | 도메인 특화 |
| §4 `GENERIC_COLS` | `비고/계열/연번/번호/구분` | 도메인·한국어 |
| §4 `SYMBOLS`, `NUMERIC` | 값으로 취급할 기호·숫자 패턴 | 언어·서식 |
| §2 `normalize` | `YYYY . MM . DD` 날짜 점 붙이기 | 언어(한국어 서식) |
| §3 `splitter` | 800/100, 구분자 `"다. "` 포함 | 튜닝값·언어 |
| §2·§3·§4 수치 | 병합 셀 반복 기준 40자, PDF 표 최소 60자, 표 분할 1400자, 행 요약 30행/2600자, wide 판별 열 7개 | 튜닝값 |
| §2 `parse_hwp` | HWP 본문은 모두 `page=1`, 표는 `page=element_index+1` (실제 쪽 번호 아님) | 형식 한계 |
| §3 청크 루프 | 출처 접두사 `[파일명 p.N]` 형식, `chunk_id`가 순번이라 입력이 바뀌면 달라짐 | 형식 |
| §3 `split_table_markdown` | 헤더를 첫 2줄로 고정 → 다단 헤더의 둘째 줄 이후는 분할 조각에서 빠짐 | 알고리즘 한계(수정 금지, 문서화) |

**알려진 문제 (고치지 말고 문서화만 할 것)**
- **F2 개체–숫자 짝 검사 오탐**: v23 답변 53개 중 17개에서 `unsupported_pairs`가 발생했는데 대부분 오탐이다. 원인은 전화번호·날짜 분할, 연도, 표 헤더와 값이 다른 줄에 있음, `NUM_RE`가 끝의 쉼표까지 잡음(`'2,'`)이다. 반면 실제 오답(holdout #6)은 잡지 못한다. 그 결과 교정 호출이 27회에서 36회로 늘었다. 근거 run: `20261028_123828_709846_v23`, 비교 대상 `20261028_122601_013520_v22`.
- **표 병합 셀·다단 헤더 오독**: holdout #6(04 p.35), drive #17, #19.
- **검색 누락**: drive #12, #20.
- **조건 누락**: drive #4, #7, #14, #18.
- **노트북 검증 범위**: 노트북은 `exec()` 기반 실행으로만 확인했다. Jupyter 커널과 Colab에서는 검증하지 않았다.
- **홈페이지 주소**: 답변 `www.gachon.ac.kr`을 원문과 대조하지 않았다.
- **v22 로컬 측정**: 로컬 v22는 Colab 측정보다 느리고(타임아웃) 정답 수도 낮다. v23의 개선분 상당 부분은 F4(단일 마감시간) 효과다.

## 2. 단계별 작업

### 단계 1. 기준 확인
1. `git status`가 깨끗하고 HEAD가 tag `v23`인지 확인한다.
2. `uv sync` 후 `uv run pytest -q`를 실행한다. 32개 통과가 기준이다.
3. `cp build_notebook.py legacy/build_notebook_v23.py`. 기존 v22 백업과 같은 규칙이다.

### 단계 2. 파싱 기준 스냅샷 (API 없음)
1. `scripts/snapshot_parse.py`를 작성한다. 이 스크립트는 `build_notebook.py`의 `CELLS`에서 **섹션 1~4의 코드 셀만** 순서대로 실행하고 아래를 저장한다.
   - 실행 범위는 마크다운 헤더(`## 1.` ~ `## 5.` 직전)로 찾는다. 셀 번호를 하드코딩하지 않는다.
   - 섹션 0의 패키지 설치 셀과 키 셀은 실행하지 않는다. 필요한 import만 스크립트에서 직접 한다.
   - 저장 파일:
     - `raw_docs.jsonl`: 파싱 결과 요소별 `page_content`와 `metadata`
     - `chunks.jsonl`: 청킹 결과
     - `contextual_chunks.jsonl`: 색인용 문맥 청크. 색인 텍스트와 `metadata.raw`를 모두 포함한다.
     - `manifest.json`: 원문 sha256(기존 `build_document_manifest` 사용), 파서 버전, `uv.lock` 기준 주요 패키지 버전, 문서별·종류별(본문/표) 청크 수, 각 jsonl의 sha256
2. 출력 위치는 `reference/baseline1/snapshots/`로 한다. 원문 텍스트가 들어 있으므로 **jsonl은 gitignore**하고 `manifest.json`만 커밋한다. 스냅샷은 스크립트로 언제든 다시 만들 수 있다.
3. **OPENAI_API_KEY와 VOYAGEAI_API_KEY를 지운 환경**에서 실행해 성공해야 한다. 이것이 API를 쓰지 않는다는 증명이다.
4. 문맥 청크 수가 513개(`eval/f1_summary_diff.json`의 `total_chunks`)와 같은지 확인한다. 다르면 §4에 따라 멈춘다.
5. 같은 명령을 두 번 실행해 jsonl sha256이 같은지(결정적인지) 확인한다.

### 단계 3. R1 파싱 레퍼런스 패키지 (동결판)
1. `reference/baseline1/docparse_b1/` 패키지를 만든다.
   ```
   docparse_b1/
     __init__.py     # 공개 API: load_sources, parse_documents, chunk_documents, build_contextual_chunks, run_all
     __main__.py     # CLI: python -m reference.baseline1.docparse_b1 <data_dir> --out <dir>
     sources.py      # 섹션 1: 필수 파일, manifest (Colab 전용 prepare_dataset/zip/Drive 탐색은 제외)
     text.py         # normalize 등 공통 정규화
     hwp.py          # parse_hwp, render_hwp_table
     pdf.py          # parse_pdf, rows_to_markdown
     chunk.py        # 섹션 3
     table.py        # dedup_cells, is_value, expand_header, parse_table, row_summary
     context.py      # doc_title, DOC_TITLES, build_contextual_chunks
     constants.py    # 청크 크기, 정규식, 기호 집합 등 상수
   ```
2. 함수 본문은 `build_notebook.py`에서 그대로 옮긴다. 파일마다 맨 위에 다음 주석을 넣는다.
   `# baseline-1 동결 레퍼런스 — v23(64ac263) build_notebook.py §N에서 이식. 수정 금지. 개선은 새 버전에서.`
3. 금지 의존성: `langchain_openai`, `openai`, `voyageai`, `langchain_voyageai`, `chromadb`, `langchain_chroma`, `rank_bm25`, `kiwipiepy`. 테스트로 강제한다. `langchain_core`의 `Document`와 HWP 로더는 허용한다.
4. CLI 출력 형식은 단계 2의 스냅샷과 같아야 한다.
5. **동일성 테스트** `tests/test_reference_parity.py`를 추가한다.
   - 패키지 출력과 단계 2 스냅샷이 jsonl 기준으로 완전히 같아야 한다. 대상은 문맥 청크 513개 전부의 `page_content`와 `metadata`다.
   - `GACHON_DATA_DIR`이나 스냅샷이 없으면 `skip`한다.
   - 금지 의존성 import 검사도 같은 파일 또는 별도 테스트로 넣는다.
6. `reference/baseline1/docparse_b1/CHANGES.md`: 원본 대비 바꾼 점을 함수 단위로 기록한다. 바꾼 이유도 적는다.

### 단계 3-G. R1-G 범용 파싱 레퍼런스 (하드코딩 제거판)
단계 3의 동일성 테스트가 통과한 뒤에 시작한다.

1. **하드코딩 전수 조사**: `docparse_b1` 전체에서 문자열·정규식·숫자 상수·파일명 규칙을 모두 찾아 `reference/baseline1/docparse_generic/HARDCODED.md`에 표로 정리한다.
   - 열: 위치(파일·함수), 값, 유형, 범용판에서의 처리
   - 유형: 문서 특화 / 도메인(입시) 특화 / 언어(한국어) / 튜닝값 / 환경 / 형식 한계
   - 처리: 프로필로 이동 / 설정 기본값으로 유지 / 제거 / 문서화만
   - §1의 초기 목록에서 시작하되, 거기에 없는 항목도 찾는다.
2. **패키지 구성**: `reference/baseline1/docparse_generic/`. 동결판을 import하지 않는 **독립 패키지**여야 한다. 실무 프로젝트로 폴더째 복사해 쓸 수 있게 하기 위해서다.
   ```
   docparse_generic/
     __init__.py      # 공개 API: parse_files(paths, config), chunk_documents, build_contextual_chunks, run_all
     __main__.py      # CLI: <파일 또는 폴더...> --profile <이름|경로> --out <dir>
     config.py        # ParserConfig (dataclass, 기본값 = 중립)
     profiles/
       gachon_2027.py # 동결판 동작을 재현하는 값 전부
     text.py · hwp.py · pdf.py · chunk.py · table.py · context.py
     HARDCODED.md · CHANGES.md · README.md
   ```
3. **`ParserConfig`가 담을 것**: HARDCODED.md에서 "프로필로 이동"이나 "설정 기본값"으로 분류한 항목 전부. 최소한 아래를 포함한다.
   - **입력 파일**: 고정 목록 대신 경로·폴더·glob을 받는다. 필수 파일 목록은 선택 항목이며, 있으면 누락 시 오류를 낸다.
   - **문서 제목 규칙**: 파일명 → 제목 매핑(선택). 매핑이 없으면 파일명 stem에서 앞 번호와 `_`를 정리한 값을 쓴다. 결과는 결정적이어야 한다.
   - **표 처리 규칙**:
     - 헤더 끝 판별 키워드, 행 라벨 키워드, 제외 열 이름
     - 일정표 판별 패턴과 그때 붙일 표제
     - 일반 열 이름(`GENERIC_COLS`), 값으로 취급할 기호와 숫자 패턴
     - wide 판별 열 수
   - **언어 규칙**: 날짜 점 정규화 사용 여부, 문장 구분자 목록. 기본값은 한국어 문서 기준으로 둔다.
   - **튜닝값**: 청크 크기와 겹침, 표 분할 길이, 병합 셀 반복 기준, PDF 표 최소 길이, 행 요약 상한. 기본값은 동결판과 같은 값이다.
   - **청크 접두사 형식**: 문자열 템플릿.
4. **중립 기본값 원칙**:
   - 특정 문서나 도메인 단어(학과, 모집단위, 면접 등)가 기본값에 하나도 없어야 한다.
   - 키워드가 비어 있을 때의 동작은 동결판에 이미 있는 대체 경로를 쓴다. 예를 들어 헤더 판별 키워드가 없으면 `start=1`을 쓰고, 행 라벨은 roster 방식(첫 값 왼쪽의 비값 셀)을 쓴다. **새 휴리스틱을 발명하지 않는다.** 대체 경로가 없는 항목은 HARDCODED.md에 적고 멈춰서 물어본다.
5. **HWP 쪽 번호 의미를 드러내기**:
   - 동결판의 `page` 값은 그대로 둔다.
   - 범용판은 추가 메타데이터 키 `locator`(예: `{"type": "element_index", "value": 12}` / `{"type": "page", "value": 3}`)를 덧붙여 의미를 명시한다.
   - 추가 키만 허용하고, 기존 키의 값은 바꾸지 않는다.
6. **테스트** (`tests/test_reference_generic.py`, API 없음, 데이터 없으면 skip):
   - **가천대 프로필 동일성**: `gachon_2027` 프로필 출력이 동결판 스냅샷과 같아야 한다. 대상은 513 청크의 `page_content`와, `locator`를 뺀 `metadata` 전부다.
   - **특화 문자열 금지**: `profiles/` 밖의 범용판 소스에 `가천`, `2027`, `모집`, `학과`, `의예과`, `01_`, `/content` 같은 특화 문자열이 없어야 한다. 금지 목록은 HARDCODED.md에서 만든다.
   - **중립 기본값 실행**: 같은 5개 문서를 중립 기본값으로 돌려 오류 없이 끝나야 한다.
   - **임의 문서 실행**: 이 프로젝트와 무관한 작은 PDF(테스트 안에서 `pymupdf`로 생성)를 중립 기본값으로 파싱해 본문 청크가 나와야 한다.
   - 금지 의존성 검사는 동결판과 같은 기준을 적용한다.
7. **프로필 비교 보고** `reference/baseline1/docparse_generic/PROFILE_DIFF.md`: 같은 5개 문서를 두 프로필로 돌린 결과를 비교한다.
   - 비교 항목: 청크 수, 표 청크 중 행 요약이 생긴 수, 표제가 붙은 수, 문서 제목 차이
   - 차이가 큰 예시 2~3개를 짧게 발췌한다.
   - 정확도 주장은 하지 않는다. RAG 평가는 백로그(B7)다.
8. `CHANGES.md`(동결판 대비 바꾼 점)와 `README.md`(설치, CLI·API 사용법, 새 프로필 만드는 방법)를 작성한다.

### 단계 4. 문서 작성
모두 `reference/baseline1/` 아래에 둔다.

1. **`PARSER.md`** — 파싱 레퍼런스 설명서. 실무 이식용이다.
   - 단계별 흐름: 원문 → 요소 → 청크 → 문맥 청크. 단계마다 입력·출력·담당 함수·파라미터(본문 800자/겹침 100자, 표 1400자와 헤더 반복 등)를 적는다.
   - HWP 경로(loader `mode="elements"`, `distribution_backend="pyhwp"`, rowspan/colspan 렌더러)와 PDF 경로(PyMuPDF 본문 + pdfplumber 표)의 차이.
   - 메타데이터 키 전체 목록과 의미.
   - 표 처리 상세: `dedup_cells` → `parse_table` → `row_summary`. "색인에는 행 요약, LLM에는 원문 표"라는 분리 원칙도 설명한다.
   - 실제 예시 2~3개: 스냅샷에서 짧게 발췌한다. 04 p.35 표처럼 다단 헤더가 깨지는 예를 반드시 포함한다.
   - **이식 가이드**: 실무에는 범용판(`docparse_generic`)을 가져가라고 명시한다. 새 문서군에 맞춰 프로필을 만드는 순서와, 동결판은 비교 기준으로만 쓴다는 점을 적는다.
   - 동결판과 범용판의 관계: 같은 알고리즘이고, 가천대 프로필이면 출력이 같다. 차이는 HARDCODED.md와 PROFILE_DIFF.md로 연결한다.
   - 알려진 한계:
     - 다단 헤더와 병합 셀, ★ 등 기호, 선 없는 표
     - 본문의 제목 계층(섹션 경로) 미추출
     - HWP의 `page`가 실제 쪽 번호가 아님
     - 표 분할 시 다단 헤더의 둘째 줄 이후가 빠짐
2. **`INTERFACE.md`** — 파서 출력 계약.
   - 이후 파서(2차 베이스라인의 "표 통째로 LLM" 또는 IR, 그리고 VLM)가 현재 색인·검색 단계에 그대로 끼워지려면 무엇을 반환해야 하는지 정의한다.
   - 정의할 항목: 필드, 타입, 필수 여부, `page_content`(색인 텍스트)와 `metadata.raw`(LLM 텍스트)의 차이, `kind` 값.
   - 페이지 번호 규칙: HWP는 실제 쪽 번호가 아니라는 점과, 범용판의 `locator` 키.
   - 이후 파서는 범용판의 `ParserConfig`·프로필 구조를 따르는 것을 권장한다는 점.
   - 파서 단위 비교에 쓸 수 있는 산출물(스냅샷 jsonl, manifest)과 비교 지점도 적는다. 비교 방법 설계는 하지 않는다.
3. **`ARCHITECTURE.md`** — 전체 파이프라인.
   - mermaid 흐름도: 데이터 → 파싱 → 청킹 → 문맥 청크 → 색인(Chroma + BM25 + 페이지 인덱스) → 라우팅 → 검색(다중 질의 RRF, 보정, 이웃 확장, 분해 검색) → 초안 → 근거 검증 → 추가검색/교정 → 답변.
   - 단계별 담당 함수와 `legacy/build_notebook_v23.py` 기준 줄 번호.
   - 시간 예산: `HARD_LIMIT` 18s, `REPAIR_START_LIMIT` 9s, `MIN_STAGE_SECONDS` 1s. 단일 마감시간 동작 방식.
   - 로컬과 Colab 실행 구조: 빌더 → 노트북 / `pipeline_v23.py`, 키 로딩 순서, `GACHON_DATA_DIR`.
4. **`CONFIG.md`** — 조정 가능한 값 전부를 한 표에 모은다. 값, 위치, 역할, **문서 특화 여부**를 적는다. 검색·답변 쪽 특화 값(`DOC_TERMS`, 라우팅 정규식, 동의어 등)도 표시한다. 파이프라인 쪽 특화 값은 이번에 덜어내지 않고 표시만 한다.
   - 모델과 `reasoning_effort`, 임베딩 모델과 대체 모델
   - 청크 크기, RRF 가중치, 각종 boost 배율, 라우팅 정규식, 동의어 목록(개수와 대표 예), 형태소 태그
   - 타임아웃 값
5. **`EVAL.md`** — 평가 방법과 baseline-1 수치.
   - 러너 사용법, 세트 구성, 채점 프롬프트(그대로 인용), 시간 점수 공식(README 기준).
   - baseline-1 수치표: 위 v23 run과 sample3 반복 3회. run 폴더 이름을 출처로 단다.
   - 실패 문항을 유형별로 분류: 표 오독 / 검색 누락 / 조건 누락 / 기타. 세트와 ID로만 표기한다.
   - `runs/`는 gitignore이므로, 기준 run의 `summary.json`과 `env.json`을 `reference/baseline1/metrics/`에 복사해 커밋한다. `results.jsonl`은 복사하지 않고 경로와 sha256만 적는다.
6. **`HISTORY.md`** — v1→v23 실험 이력 요약.
   - 근거: `REPORT_중간평가_진행상황.md`, `eval/results_v2*.json`, `legacy/experiments_v1_v7.py`.
   - 버전마다 무엇을 바꿨는지, 결과, 유지/폐기 여부를 한 줄씩 정리한다. 효과가 컸던 결정(Voyage 전환, Dense 1위 보장, 분해 검색, 단일 마감시간 등)은 따로 강조한다.
   - 보고서의 정정 사항(errata)이 있으면 정정된 값을 쓴다.
7. **`KNOWN_ISSUES.md`** — §1의 알려진 문제를 근거(run 경로, 문항 ID, 예시 값)와 함께 정리한다.
8. **`reference/README.md`** — 레퍼런스 색인.
   - baseline-1 = v23(commit, tag). 문서 목록과 각 문서의 용도.
   - 재현 방법: `uv sync`, `GACHON_DATA_DIR` 설정, 스냅샷 생성 명령, 평가 명령.

### 단계 5. 백로그 등록
최상위에 `BACKLOG.md`를 만든다. 항목마다 한두 줄 설명, 선행 조건, 관련 문서 링크를 적는다. 구현 계획은 쓰지 않는다.
- **B1 2차 베이스라인**: 표 개선본. (a) 표를 통째로 LLM에 넘기는 방식, (b) IR(셀·병합·헤더 경로) 방식. 둘 중 선택하거나 둘 다 한다. 선행 조건은 INTERFACE 준수.
- **B2 VLM 표 파싱 대조** (실무 프로젝트): baseline-1, 2차 베이스라인, VLM 비교. 선행 조건은 B1과 비교 지표 정의.
- **B3 F2 짝 검사 오탐 수정**: B1의 IR이 생기면 같이 처리하는 것을 검토.
- **B4 노트북 검증**: Jupyter 커널과 Colab에서 실행 확인.
- **B5 독립 테스트셋**: 현재 세트는 모두 개발에 쓰였다.
- **B6 홈페이지 주소 원문 대조.**
- **B7 범용판 RAG 평가**: 범용판 중립 기본값으로 만든 청크를 실제 파이프라인에 넣어 평가한다. API가 필요하다. 다른 문서군에서도 시험한다.
- **B8 파이프라인 쪽 특화 값 분리**: 검색·라우팅·프롬프트의 문서 특화 값(`CONFIG.md`에 표시한 것)을 설정으로 분리한다.

### 단계 6. 검증
1. `uv run pytest -q`: 기존 32개와 신규 테스트가 모두 통과해야 한다.
2. 키를 지운 환경에서 스냅샷 스크립트와 CLI가 모두 성공하고, 두 출력이 같아야 한다.
3. 키·비밀값 패턴 검사: 기존 `scripts/check_notebook.py`의 패턴을 재사용해 `reference/`, `BACKLOG.md`, 새 스크립트를 검사한다. 0건이어야 한다.
4. 평가셋 문장 유출 검사: 새 코드와 문서에 testset의 `q`/`gold` 문장이 그대로 들어가지 않았는지 확인한다. 문서의 문항 ID 표기는 허용된다.
5. 동작 불변 확인: `git diff v23 -- build_notebook.py pipeline_v23.py "202235052_박진성.ipynb"`가 비어 있어야 한다.
6. 범용판 확인:
   - 가천대 프로필 동일성 통과
   - 특화 문자열 금지 테스트 통과
   - 중립 기본값과 임의 PDF 실행 통과
   - 범용판 폴더만 임시 폴더에 복사했을 때 import와 CLI가 동작해야 한다(독립성).
7. 문서 링크와 줄 번호가 실제 파일과 맞는지 직접 열어 확인한다.

### 단계 7. 정리
1. 이 계획서를 `prompts/legacy/`로 옮긴다.
2. `.gitignore`에 `reference/baseline1/snapshots/**/*.jsonl`을 추가한다. 범용판 프로필별 출력은 `snapshots/generic_<프로필>/`에 둔다.
3. 커밋(메시지 예: `docs: freeze v23 as baseline-1 reference`) 후 tag `baseline-1`을 단다. tag `v23`은 그대로 둔다.
4. `REPORT_중간평가_진행상황.md`에 Session 6 절을 짧게 추가한다. baseline-1 정의, 산출물 목록, 백로그 링크를 적는다.

## 3. 보고 형식 (작업 종료 시)
- 만든 파일 목록과 각 용도를 한 줄씩.
- 동일성 테스트 결과: 청크 수, 일치 여부, 스냅샷 sha256.
- API 미사용 증명 방법과 결과.
- `CHANGES.md` 요약: 동결판은 원본 대비, 범용판은 동결판 대비 바꾼 점.
- HARDCODED.md 요약: 유형별 항목 수와, 초기 목록에 없던 새 항목.
- PROFILE_DIFF.md 요약.
- 검증 7항목 각각의 통과 여부. 실패나 생략이 있으면 그대로 적는다.
- 커밋 해시와 tag.

## 4. 막혔을 때 멈추고 물어볼 것
- 문맥 청크 수가 513개가 아니거나, 패키지 출력이 스냅샷과 다른데 원인을 설명할 수 없을 때.
- 섹션 1~4 실행에 네트워크나 API 키가 필요해 보일 때.
- 레퍼런스로 옮기려면 함수 본문을 바꿔야 할 때.
- 범용판에서 가천대 프로필로 동결판 출력을 재현하려면 알고리즘 자체를 바꿔야 할 때.
- 중립 기본값에 쓸 대체 경로가 동결판에 없어서, 새 휴리스틱을 만들어야 할 것 같을 때.
- `build_notebook.py`, `pipeline_v23.py`, 노트북을 수정해야 할 것 같을 때.
- 보고서와 저장된 결과 파일의 수치가 서로 다를 때. 어느 쪽이 맞는지 임의로 정하지 않는다.
