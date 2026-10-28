# baseline-1 파싱 레퍼런스

실무 이식에는 [docparse_generic](docparse_generic/README.md) 폴더를 사용한다. [docparse_b1](docparse_b1/)은 v23(`64ac263`)의 출력 비교 기준이다. 둘은 같은 파싱·청킹·행 요약 알고리즘을 사용하며, 범용판의 도메인 프로필은 동결판과 같은 텍스트·기존 메타데이터를 재현한다. 범용판에는 위치 의미를 나타내는 `locator`만 추가된다. 설정 분리 목록은 [HARDCODED](docparse_generic/HARDCODED.md), 실제 출력 차이는 [PROFILE_DIFF](docparse_generic/PROFILE_DIFF.md)에 있다.

| 단계 | 입력 → 출력 | 함수 | 주요 값 |
|---|---|---|---|
| 입력 | 로컬 경로 → 순서 있는 원본 목록 | 동결판 `load_sources`; 범용판 `parse_files`의 입력 확장 | 동결판은 고정 5개, 범용판은 파일·폴더·glob 및 선택적 필수 목록 |
| 요소 추출 | 원본 → `raw_docs` | `parse_hwp`, `parse_pdf` | HWP 병합셀 반복 기준 40자, PDF 표는 markdown 길이 60자 초과 |
| 청킹 | 요소 → `chunks` | `chunk_documents`, `split_table_markdown`, `_hard_split` | 본문 800자/겹침 100자; 표 본문 1,400자 기준, 첫 두 줄 반복 |
| 문맥 구성 | 청크 → `contextual_chunks` | `build_contextual_chunks`, `doc_title`, `parse_table`, `row_summary` | wide 기준 7열, 표제 30자, 행 요약 최대 30행/2,600자, 한 행 최대 6쌍 |

원본 함수 위치는 [v23 보존본](../../legacy/build_notebook_v23.py)의 §1(150~190), §2(328~420), §3(447~489), §4(518~675)다. 고정 상수는 동결판 `constants.py`, 범용판 `config.py`와 `profiles/`에서 확인한다. 이 설명의 수치는 위 소스에서 가져왔다.

HWP는 `HwpHwpxLoader(mode="elements", distribution_backend="pyhwp")`를 쓴다. 본문 요소는 공백을 벗긴 텍스트로 보존하고, 표의 cells JSON을 자체 렌더러에 넣는다. 렌더러는 `rowspan`/`colspan`을 격자에 전개하고 구조 마커를 제거한다. 40자 이하 셀은 병합 범위에 반복하고 그보다 긴 셀은 좌상단만 채운다. 중복 행·빈 행을 건너뛰고 markdown 표로 직렬화한다. 실제 HWP 쪽 번호는 얻지 못한다.

PDF는 두 경로를 순서대로 실행한다. PyMuPDF `get_text("text")`로 페이지 본문을 얻어 공백과 숫자 사이 날짜 점을 정규화한 뒤, pdfplumber `extract_tables()`로 표를 별도 추출한다. 표는 빈 행·열을 지우고 markdown으로 바꾼다. 따라서 본문에 포함된 표 텍스트와 별도 표가 중복될 수 있다. PDF `page`는 1부터 시작하는 파일 페이지이고 인쇄 쪽 번호와 다를 수 있다.

본문은 `RecursiveCharacterTextSplitter`를 사용한다. 표는 처음 두 줄(첫 헤더와 markdown 구분선)을 반복하면서 데이터 행을 모은다. 길이가 넘는 단일 행은 `_hard_split`이 공백으로 나눈다. 1,400자는 헤더·접두사·개행을 포함한 최종 길이의 강제 상한이 아니며, 공백 없는 긴 단어도 더 길 수 있다. `part`는 요소 내부 순번, `chunk_id`는 전체 순번이다.

표 처리는 `dedup_cells` → `parse_table` → `row_summary`로 이어진다. `dedup_cells`는 값이 나오기 전의 반복 라벨만 줄이고 숫자·기호·빈 셀은 보존한다. `parse_table`은 헤더 경계·일정 패턴·열 수에 따라 wide 또는 roster 모드를 정하고, wide에서는 `expand_header`가 빈 헤더를 왼쪽 값으로 채워 위→아래로 합친다. `row_summary`는 wide의 키워드 라벨 또는 roster의 첫 값 왼쪽 라벨로 `- 라벨: 열=값`을 만든다. 임계값에 도달하면 이후 행은 생략된다.

색인에는 문서 헤더와 표 행 요약을 붙이고, LLM에는 `metadata.raw`에 보존한 원문 청크를 전달한다. 요약은 검색을 돕는 파생 텍스트이며 원문을 교체하지 않는다. 전체 메타데이터 키는 `source`, `page`, `kind`, `part`, `chunk_id`, `raw`, `title`이며 범용판은 `locator`를 추가한다. 타입·필수 시점과 페이지 의미는 [INTERFACE](INTERFACE.md)에 명시했다.

## 새 문서군으로 이식

1. 범용판 폴더와 최소 파싱 의존성을 가져온 뒤 중립 `ParserConfig()`로 실행한다.
2. 입력 순서를 고정하고 필요하면 필수 파일 목록과 제목 규칙을 설정한다.
3. 원문 표를 보면서 헤더 경계·행 라벨·제외 열·일정 패턴·일반 열 이름을 문서군 프로필에 넣는다.
4. 길이 임계값과 구분자를 프로필에서 조정하고 단계별 jsonl·manifest로 결과를 보존한다.
5. 색인·검색에 연결할 때 `raw`와 위치 의미를 유지한다. RAG 정확도 검증은 [B7](../../BACKLOG.md)에서 별도로 수행한다.

동결판은 비교 기준으로 보존한다. 새 휴리스틱이나 표 개선은 [B1](../../BACKLOG.md)의 새 버전에서 다룬다.

## 알려진 한계

- 병합 셀을 단순 반복하고 다단 헤더를 추정하므로 잘못된 열–값 연결이 생길 수 있다. ★ 같은 기호를 값으로 인식해도 그 의미까지 해석하지 않는다.
- 선 없는 PDF 표는 기본 `extract_tables()`에서 누락될 수 있다. 이미지·스캔 OCR과 VLM은 없다.
- 본문의 제목 계층·섹션 경로를 추출하지 않는다.
- HWP `page`는 실제 쪽 번호가 아니다. 범용판의 `locator`를 함께 확인한다.
- 표 분할은 첫 두 줄만 반복한다. 다단 헤더의 둘째 헤더 줄 이후는 첫 조각의 데이터에 섞이고 후속 조각에서 빠진다.
- 표 폭이나 행 길이가 깨진 경우 요약이 비거나 잘못 연결될 수 있다. 원문 표도 loader 추출 결과이므로 원본 배치와 동일하다고 보장하지 않는다.

실제 스냅샷 예시는 아래에 기록한다. 출처는 [스냅샷 manifest](snapshots/manifest.json)의 해시로 고정된다.

`contextual_chunks.jsonl`, `chunk_id=0`(HWP 본문)의 앞부분이다. 문서 문맥과 원문 접두사가 별도로 붙으며 여기의 `p.1`은 실제 HWP 쪽 번호가 아니다.

```text
[문서] 2027학년도 재외국민 모집요강 | p.1 | 본문
[원문]
[01_2027학년도_재외국민_모집요강.hwp p.1]
Gachon University
```

같은 파일의 `chunk_id=340`, 03 p.74 표의 짧은 발췌다. 빈 가장자리 셀을 처리한 roster 요약이 색인 텍스트에 붙고 표는 raw에 남는다.

```text
[표 행 요약]
- Bassoon: 모집인원=1
- Horn: 모집인원=1
```

`chunk_id=499`, 04 p.35 표는 다단 헤더가 깨진 사례다. 다음은 raw에서 연속한 세 줄이며 첫 줄은 생략했다.

```text
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| | | | 1호 | 2호 | 3호 | 4호 | 5호 | 6호 | 7호 | 8호 | 9호 | |
| | | | - | - | - | –10 | | –20 | | –100 | | 1,000점 만점 기준 감점 |
```

병합 셀 때문에 호수와 수치 사이의 빈 칸이 남고 이 청크에는 행 요약이 생성되지 않았다. 해당 헤더는 첫 두 줄 뒤에 있으므로 표가 여러 조각으로 나뉘면 후속 조각의 반복 헤더에도 포함되지 않는다. holdout10 #6의 표 오독과 관련된 위치이며, 원문 정답을 재구성하거나 표를 수정하지 않았다.
