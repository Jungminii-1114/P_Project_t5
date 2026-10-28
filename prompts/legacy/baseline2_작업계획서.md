# 베이스라인 2 작업계획서 — 표 IR + 렌더러 비교 (워커 전달용)

> 이 문서만 보고 작업할 수 있도록 썼습니다. 이 프로젝트에서의 **마지막 작업**입니다. 결과물은 실무 프로젝트로 넘길 레퍼런스가 됩니다.

## 0. 목표와 범위

**목표**: baseline-1(tag `baseline-1`, commit `3fbba3f`)의 남은 표 문제를 다루는 **베이스라인 2**를 만든다.

1. **파서 패키지화**: 파서를 `src/docparse/` 패키지로 만들고, 파이프라인(v24)이 이 패키지를 import하게 한다.
2. **표 IR 도입**: 셀·병합 범위·헤더 경로를 담는 중간 표현(IR)을 도입한다.
3. **렌더러 3종**: 아래 두 방식을 설정만 바꿔 **둘 다 실험**할 수 있게 한다.
   - (a) 표를 통째로 LLM에 넘기기
   - (b) 헤더 경로 레코드로 넘기기
4. **2단계 진행**:
   - **1단계(API 없음)**: 구축, 골든 테스트, BM25 진단
   - **2단계(API 사용, 사용자 승인 후)**: 변형별 RAG 평가와 기본 변형 선정
5. **마무리**: 실무 인계 문서를 남기고 tag `baseline-2`를 단다.

**범위 밖 (하지 말 것)**
- 파서 외 모듈화: 검색·검증·답변 코드의 구조 변경, 전역 상태 제거, `Pipeline` 객체화. 허용되는 파이프라인 변경은 §2 단계 4의 목록뿐이다.
- 검색 가중치·라우팅·동의어·프롬프트·모델 변경. F2 오탐 수정(B3)도 하지 않는다.
- VLM. 실무 프로젝트에서 할 일이다. 인계 문서에 연결 지점만 적는다.
- 제출용 노트북 갱신. 노트북은 v23에서 동결하며, v24는 로컬 py 전용이다.
- `reference/baseline1/`, `legacy/`, tag가 붙은 커밋 수정.
- 1단계에서의 API 호출. 2단계는 §2 단계 7의 승인 절차를 거친 뒤에만 진행한다.

**원칙**
- **IR 경로와 기존 경로를 공존시킨다.** baseline-1 경로(`render_mode="baseline1"`)의 출력은 baseline-1 스냅샷과 바이트 단위로 같아야 한다. 새 경로는 이 기준과 비교된다.
- **새 규칙은 범용으로 만든다.** 특정 페이지·표·문서를 겨냥한 조건문은 쓰지 않는다. 도메인 값은 프로필로만 넣는다. baseline-1 범용판의 "특화 문자열 금지" 테스트를 그대로 적용한다.
- **골든 테스트의 기대값은 원문에서만 가져온다.** 평가셋의 질문·정답 문장을 코드나 테스트에 넣지 않는다(README 규칙).
- **골든 테스트를 통과시키려고 대상 표에 맞춘 예외를 넣지 않는다.** 실패하면 실패로 보고한다.
- **수치는 저장된 결과에서만 인용한다.** API 키 값은 출력·커밋·로그에 남기지 않는다.

## 1. 현재 상태 (반드시 먼저 읽을 것)

| 경로 | 내용 |
|---|---|
| `reference/baseline1/` | 동결 레퍼런스. `PARSER.md`, `INTERFACE.md`, `KNOWN_ISSUES.md`, `EVAL.md`, `CONFIG.md`를 먼저 읽는다. |
| `reference/baseline1/docparse_generic/` | 범용 파서. `ParserConfig`, `profiles/gachon_2027.py`, `run_all()`. **새 패키지의 출발점**이다. 복사해서 쓰고 원본은 수정하지 않는다. |
| `reference/baseline1/snapshots/` | baseline-1 스냅샷: `raw_docs`, `chunks`, `contextual_chunks`(513개), `manifest.json`. jsonl은 gitignore 대상이며 스크립트로 재생성한다. |
| `build_notebook.py` → `pipeline_v23.py` | 현재 파이프라인. 파서 코드가 빌더 안(§1~4)에 들어 있다. import하면 임베딩·색인까지 실행된다. |
| `scripts/run_eval.py`, `compare_eval.py` | 평가 러너와 비교. 현재 `--version`은 v22/v23만 받는다. |
| `eval/testset_*.json` | 평가셋. `src`에 출처가 있다. PDF는 `"03 p.104"` 형식(파일 페이지로 보임), HWP는 인쇄 쪽 번호 또는 `"01 (전형료 표)"` 같은 설명이다. |
| `BACKLOG.md` | B1(이 작업), B2(VLM, 실무로 이관), B3~B9. |

**v23/baseline-1에서 남은 표 관련 문제** (`reference/baseline1/KNOWN_ISSUES.md` 참조)
- **표 오독**: holdout #6(04 p.35, 다단 헤더 `학교폭력조치사항 / 1호…9호`), drive #17(등급 구간표), drive #19(면접일 열).
- **표 페이지 검색 누락**: drive #12, #20.
- **분할 시 다단 헤더 소실**: `split_table_markdown`이 헤더를 첫 2줄로 고정한다.
- **PDF 병합 셀 정보 소실**: `extract_tables()`는 병합 셀을 `None`으로 돌려주고 범위 정보를 버린다.
- **HWP**: 셀 JSON에 `row/col/rowspan/colspan`이 있어서 IR로 바로 옮길 수 있다. `page`는 실제 쪽 번호가 아니다(`locator` 참조).

## 2. 단계별 작업

### 단계 1. 기준 확인
1. HEAD가 tag `baseline-1`인지 확인한다. 미커밋 변경은 아래 두 가지만 허용한다. 둘 다 단계 2 커밋에 포함한다. 그 밖의 변경이 있으면 멈춘다.
   - `BACKLOG.md`의 B9 행 추가
   - 이 계획서 파일 `uv sync` 후 `uv run pytest -q`가 모두 통과해야 한다.
2. baseline-1 스냅샷이 없으면 baseline-1의 스냅샷 스크립트로 다시 만든다. `manifest.json`의 sha256과 같은지 확인한다.

### 단계 2. 파서 패키지 `src/docparse/`
1. `reference/baseline1/docparse_generic/`를 `src/docparse/`로 복사한다. 패키지 이름만 바꾸고 동작은 그대로 둔다.
2. `pyproject.toml`에 패키지를 등록해 `uv run python -c "import docparse"`가 동작하게 한다. 방식은 src 레이아웃 빌드 설정이다.
3. 동일성 테스트를 옮긴다. `profile=gachon_2027`, `render_mode="baseline1"`일 때 513 청크가 baseline-1 스냅샷과 같아야 한다. `locator`는 비교에서 제외한다.
4. 여기까지 커밋한다(메시지 예: `refactor: package parser as docparse (baseline-1 parity)`).

### 단계 3. 표 IR과 렌더러
1. **IR 스키마** `docparse/ir.py`:
   - `Table`: `table_id`, `source`, `locator`, `page`, `n_rows`, `n_cols`, `cells`, `header_rows`, `stub_cols`, `origin`
     - `table_id`: 문서·위치 기반의 결정적 ID
     - `header_rows`: 헤더 행 수
     - `stub_cols`: 행 라벨 열 수
     - `origin`: `"hwp_cells"` / `"pdf_cells"` / `"pdf_fallback"`
   - `Cell`: `row`, `col`, `rowspan`, `colspan`, `text`, `is_header`
   - `header_path(col) -> list[str]`, `row_label(row) -> list[str]`
   - JSON 직렬화와 역직렬화를 지원한다. VLM 결과를 IR로 바꾸는 어댑터의 기준이 된다.
2. **추출기**:
   - **HWP**: 기존 셀 JSON을 그대로 IR로 옮긴다. `_MARKER` 제거와 `[IMAGE]` 처리는 기존 규칙을 따른다.
   - **PDF**: pdfplumber `page.find_tables()`의 셀 좌표로 행·열 경계를 만들고, 각 셀이 덮는 범위로 rowspan/colspan을 계산한다.
     - 셀 좌표는 `Table(page, cells)` 인스턴스의 `cells` 속성(bbox 목록)과 `table.rows`·`table.columns`에서 얻는다(0.11.10에서 확인).
     - 셀 텍스트는 `page.crop(bbox).extract_text()`로 얻는다. 기존 `extract_tables()` 결과와 셀 값이 일치하는지 표 단위로 대조해 기록한다.
     - 선이 없어서 셀 좌표를 못 얻는 표는 `origin="pdf_fallback"`으로 표시하고 `extract_tables()` 결과를 병합 없이 IR로 옮긴다.
     - fallback 비율을 기록한다.
3. **헤더·라벨 판별** `docparse/table_ir.py`. 범용 규칙이며, 프로필 키워드는 보조로만 쓴다.
   - 헤더 행: 위에서부터 값 셀(`is_value` 기준)이 처음 나오는 행 직전까지. 가로로 병합된 셀이 있는 위쪽 행은 헤더 후보로 본다.
   - 행 라벨 열: 왼쪽부터 첫 값 열 직전까지.
   - 세로 병합된 라벨은 아래로 채워 각 행이 완전한 라벨을 갖게 한다.
   - 판별 결과가 불확실하면(예: 헤더 행 0개) 표에 `confidence` 플래그를 남긴다. 렌더러는 이 경우 baseline1 출력으로 되돌아간다.
4. **렌더러** `docparse/render.py`. 색인용과 LLM용을 **따로** 고른다.
   - `baseline1`: 기존 markdown과 행 요약. 동일성 기준이다.
   - `html_full` — 방식 (a):
     - `rowspan`/`colspan`을 살린 `<table>` HTML로 **표 전체**를 렌더링한다.
     - 청크에는 `metadata.table_id`를 넣고, 표 전체 텍스트는 별도 저장소(`tables.jsonl` 또는 메모리 dict)에 둔다.
     - 길이 상한(`table_full_max_chars`, 기본값은 측정 후 정해 근거와 함께 보고)을 넘으면 헤더를 반복한 분할로 대체한다.
   - `header_records` — 방식 (b):
     - 행마다 `[행 라벨] 헤더경로1/헤더경로2 = 값` 형태로 렌더링한다.
     - 분할할 때도 모든 조각이 완전한 헤더 경로를 유지한다. 다단 헤더 소실 문제를 이렇게 해결한다.
   - 색인 텍스트 조합: `index_render ∈ {baseline1, header_records}`. 문맥 헤더 형식은 유지한다.
   - LLM 텍스트 조합: `llm_render ∈ {baseline1, html_full, header_records}`. 결과는 `metadata.raw`에 들어간다. `html_full`이면 `raw`에는 조각을, 표 전체는 `table_id`로 찾게 한다.
5. **설정**: `ParserConfig`에 `index_render`, `llm_render`, `table_full_max_chars`, IR 관련 임계값을 추가한다. 기본값은 `baseline1`/`baseline1`로 둔다(동작 불변).
6. **Chroma 호환**: Chroma 메타데이터에는 스칼라만 넣는다. 중첩 객체(`locator`, IR)는 색인 메타데이터에서 빼고 `table_id` 같은 문자열 키로만 연결한다.

### 단계 4. 파이프라인 v24 연결 (허용되는 변경은 이것뿐)
1. `build_notebook.py`를 복사해 `build_pipeline_v24.py`를 만든다. 원본 빌더와 v23 노트북은 그대로 둔다. 새 빌더는 `pipeline_v24.py`만 생성한다.
2. §1~4의 파서 코드를 `docparse.run_all(...)` 호출로 바꾼다. 결과 변수 이름(`raw_docs`, `chunks`, `chunks_ctx`)은 유지한다.
3. 설정은 환경변수로 받는다. 값은 `env.json`과 평가 로그에 기록한다.
   - `DOCPARSE_PROFILE` (기본 `gachon_2027`)
   - `DOCPARSE_INDEX_RENDER` (기본 `baseline1`)
   - `DOCPARSE_LLM_RENDER` (기본 `baseline1`)
4. `_context()`: `llm_render="html_full"`이면 같은 `table_id`의 조각을 한 번만, 표 전체로 넣는다. 나머지 경우는 기존과 같다.
5. **임베딩 캐시**: `langchain_classic.embeddings.CacheBackedEmbeddings`(현재 환경에 설치됨, `langchain.embeddings`에는 없음)와 로컬 파일 저장소를 쓴다. 쓸 수 없으면 같은 키 규칙의 간단한 디스크 캐시를 직접 만든다. 키는 모델 이름과 텍스트 해시이고, 위치는 `runs/cache/`(gitignore)다. 색인 텍스트가 같은 변형끼리는 임베딩을 다시 만들지 않는다.
6. 그 밖의 코드(검색, 검증, 프롬프트, 마감시간)는 한 글자도 바꾸지 않는다. `git diff`로 확인할 수 있게 v23 대비 diff를 보고서에 첨부한다.
7. `scripts/run_eval.py`가 `--version v24`와 위 환경변수 조합을 받도록 확장한다. 변형 이름(`--variant`)도 run 폴더 이름과 `env.json`에 남긴다.

### 단계 5. 골든 테스트 (API 없음)
1. 5개 문서 전체에서 **표 유형별로** 8~12개 표를 고른다.
   - 유형 예: 다단 헤더 / 세로 병합 행 라벨 / 오전·오후가 있는 일정표 / 등급·구간표 / 기호(★·○) 표 / 각주가 붙은 표 / 선 없는 표 / HWP 표
   - 위 "남은 표 문제"의 표 3개(04 p.35 등)는 포함하되, 나머지는 그와 무관한 표로 채운다.
2. 표마다 원문 페이지를 PNG로 렌더링(pymupdf)해 직접 보고 기대값을 만든다. HWP는 셀 JSON과 대조한다.
   - 기대값: 헤더 행 수, 행 라벨 열 수, 그리고 **표본 셀 5~10개의 (행 라벨, 헤더 경로, 값)**.
3. 저장 위치는 `tests/golden/tables.yaml`이다. 표마다 `source`, `page`(또는 `locator`), 선택 이유(유형), 기대값을 적는다. 원문 문장을 길게 옮기지 말고 셀 값만 적는다.
4. 기대값은 워커가 만든 것이므로 **사용자 검토 대상**이다. 보고서에 표 목록과 렌더링 PNG 경로(scratch 위치, 커밋하지 않음)를 남긴다.
5. `tests/test_table_ir.py`: 골든 대조, IR JSON 왕복, 렌더러별 출력 형식, 분할 후 헤더 경로 유지, baseline1 동일성.

### 단계 6. 1단계 진단 (API 없음)
1. **구조 지표**: 표 수, `origin`별 비율(`pdf_fallback` 포함), 헤더 판별 불확실 비율, 다단 헤더 표 수, 골든 통과율(셀 단위·표 단위).
2. **BM25 진단** `scripts/diagnose_bm25.py`:
   - 각 평가셋 질문에 대해, `src`의 **PDF 페이지**가 BM25 상위 k(1·3·8)에 드는지 센다. 비교 대상은 `index_render` 두 종류다.
   - HWP `src`(인쇄 쪽 번호·설명)는 제외하고, 제외한 수를 보고한다.
   - 토크나이저는 파이프라인과 같은 kiwi 설정(`reference/baseline1/CONFIG.md`의 품사 태그)을 쓴다.
   - 이것은 하이브리드 검색이 아닌 **대리 지표**라고 보고서에 명시한다.
   - 먼저 PDF `src` 페이지가 파일 페이지 기준인지 3건 이상 확인한다. 아니면 멈춘다.
3. **크기 지표**: `html_full`과 `header_records`의 표당 길이 분포. 상한을 넘는 표의 수와 목록.
4. 결과를 `reference/baseline2/STAGE1.md`에 정리하고 커밋한 뒤, tag `v24`를 단다.
5. **여기서 멈추고 보고한다.** 2단계 시작 여부를 사용자에게 묻는다(단계 7).

### 단계 7. 2단계 RAG 평가 (사용자 승인 후에만)
1. 승인을 요청할 때 함께 제시할 것:
   - 변형 목록
   - 실행 횟수
   - 예상 호출 수: 문항 수 × (초안 + 교정 비율 + 채점), 임베딩 재생성 횟수
   - 예상 소요 시간
2. 변형 (세트: sample3, hard20, holdout10, drive20):

   | 이름 | index_render | llm_render | 목적 |
   |---|---|---|---|
   | V0 | baseline1 | baseline1 | 패키지 연결 후 baseline-1 재현 확인 |
   | V1 | header_records | baseline1 | 색인만 바꿨을 때 검색 효과 |
   | V2 | baseline1 | html_full | 방식 (a) |
   | V3 | header_records | header_records | 방식 (b) |
   | V4 | header_records | html_full | (a)+(b) 조합 |

3. **V0 판정**: 세트별 정답 수가 baseline-1 대비 ±2 이내이고 모든 응답이 19초 미만이어야 한다. 실패하면 다른 변형을 돌리지 말고 멈춘다.
4. **기본 변형 선정**:
   - 1순위 총 정답 수, 2순위 시간 점수.
   - 차이가 세트당 2문항 이내면 LLM 출력 변동 범위 안으로 본다. 이때는 상위 두 변형을 sample3 ×3과 drive20 ×1로 한 번 더 돌린다. 그래도 차이가 없으면 단순한 쪽(구현·토큰이 적은 쪽)을 고르고 그 이유를 적는다.
5. 표 관련 문항(holdout #6, drive #12·#17·#19·#20)은 변형별 예측과 판정 이유를 표로 비교한다.
6. 선정된 변형을 `pipeline_v24`의 기본 설정으로 바꾸고, sample3 ×3이 모두 3/3인지 확인한다.

### 단계 8. 문서와 인계 (`reference/baseline2/`)
1. `IR.md`: 스키마, 추출기(HWP / PDF cells / fallback), 헤더·라벨 판별 규칙, 한계.
2. `RENDERERS.md`: 렌더러 3종의 출력 예(짧은 발췌), 색인용과 LLM용 분리, 길이 상한, Chroma 메타데이터 규칙.
3. `GOLDEN.md`: 골든 표 목록과 유형, 기대값 작성 방법, 사용자 검토 상태.
4. `EVAL.md`: 1단계 지표, 2단계 변형별 결과(run 폴더를 출처로), 선정 근거. 2단계를 하지 않았으면 그렇다고 적는다.
5. `HANDOFF.md` — 실무 프로젝트 인계서:
   - 가져갈 것: `src/docparse/`, IR 스키마, 골든 테스트 형식, 진단 스크립트
   - 두고 갈 것: v24 파이프라인, 가천대 프로필
   - **VLM 연결 지점**: VLM 출력(HTML/JSON 표)을 IR로 바꾸는 어댑터 인터페이스(함수 시그니처와 입출력). 비교 지표는 골든 셀 정확도, BM25 대리 지표, RAG 정답 수·시간.
   - 남은 문제: F2(B3), 선 없는 표, HWP 쪽 번호, 파서 외 모듈화(B8)
6. `BACKLOG.md` 갱신: B1을 완료로 표시하고 결과 문서로 연결한다. B2는 "실무 프로젝트로 이관"으로 표시한다.
7. `REPORT_중간평가_진행상황.md`에 Session 7 절을 짧게 추가한다.

### 단계 9. 검증과 정리
1. `uv run pytest -q`: 모두 통과해야 한다(기존 테스트 포함).
2. 키를 지운 환경에서 파싱·골든·BM25 진단이 성공해야 한다(1단계가 API 없이 돈다는 증명).
3. 변경 범위 확인:
   - `git diff baseline-1 -- reference/ legacy/ build_notebook.py "202235052_박진성.ipynb"`가 비어 있어야 한다.
   - `pipeline_v24.py`의 v23 대비 diff가 단계 4 목록 안에 있어야 한다.
4. 키·비밀값 패턴 검사(`scripts/check_notebook.py`의 패턴 재사용)와 평가셋 문장 유출 검사: 새 코드, 테스트, 문서가 대상이다.
5. 이 계획서를 `prompts/legacy/`로 옮기고 커밋한다. 2단계까지 마쳤으면 tag `baseline-2`를 단다. 1단계만 마쳤으면 tag는 `v24`까지만 둔다.

## 3. 보고 형식
- **1단계 종료 시(단계 6)**:
  - 만든 파일, 동일성 결과, 구조 지표, 골든 결과(실패 표 포함), BM25 진단 표, 길이 분포
  - 2단계 승인 요청: 변형, 예상 호출 수, 예상 시간
- **최종 보고**:
  - 변형별 결과표, 선정 변형과 근거, 표 관련 문항 비교
  - 검증 항목별 통과 여부, 커밋·tag
  - 생략했거나 실패한 것은 그대로 적는다.

## 4. 막혔을 때 멈추고 물어볼 것
- baseline1 렌더 모드가 스냅샷과 다른데 원인을 설명할 수 없을 때.
- 골든 테스트나 진단을 위해 특정 표·페이지 전용 규칙이 필요해 보일 때.
- 파이프라인에서 단계 4 목록 밖의 변경이 필요해 보일 때. 예: 프롬프트에 레코드 형식 설명을 추가해야 할 것 같은 경우.
- PDF `src`가 파일 페이지 기준이 아닐 때.
- `pdf_fallback` 비율이 절반을 넘을 때. IR 접근 자체를 다시 검토해야 한다.
- V0가 baseline-1을 재현하지 못할 때.
- 1단계를 마쳤을 때. 2단계는 승인 없이 시작하지 않는다.
