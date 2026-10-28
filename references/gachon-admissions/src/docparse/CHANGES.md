# CHANGES — 범용판

기준은 독립 패키지 docparse_b1의 v23(64ac263) §1–§4 동작이다. 범용판은 docparse_b1을 import하지 않는다. 일반 입력과 설정을 받기 위해 전역 설정·파일 목록을 객체 인자로 바꾸고, 동결판의 파싱·청킹·표 요약 알고리즘은 유지한다.

| 영역·함수 | 변경 | 이유 |
|---|---|---|
| ParserConfig | 문서 목록·제목 규칙·표 키워드·일정 패턴·문자열 템플릿·형식 처리값·튜닝값을 dataclass로 모았다. 기본값은 문서 제목·헤더·행 라벨·일정 규칙을 비워 둔다. | 문서군마다 소스를 편집하지 않고 설정·프로필로 규칙을 바꾸도록 한다. |
| load_profile | 기본 neutral, 패키지 안의 Python 프로필, JSON 설정 파일을 지원한다. 프로필 이름은 module identifier만 받는다. | 중립 실행과 새 도메인 프로필을 CLI와 API에서 선택할 수 있게 한다. |
| load_sources | 단일 파일, 폴더, glob을 읽고 결정적으로 정렬한다. 선택적 required_files가 있으면 그 순서를 지키며 누락 시 오류를 낸다. | 동결판의 고정 5개 파일 목록을 임의의 로컬 문서 입력으로 확장한다. 네트워크·Drive·zip 탐색은 없다. |
| build_document_manifest | 받은 파일별 SHA-256·크기·파서 구현 버전을 반환한다. | 임의 입력 목록의 출처를 기록한다. |
| normalize | 공백·날짜 정규식과 날짜 정규화 여부를 설정에서 받는다. | 문장·날짜 서식을 문서 언어에 맞춰 조정할 수 있게 한다. |
| render_hwp_table, parse_hwp | 병합 셀 반복 한계·marker·image marker와 loader 모드·백엔드를 설정에서 받는다. page는 동결판 값으로 유지하고 locator={"type":"element_index","value":...}를 추가한다. | 형식값을 설정화하고 HWP page가 실제 쪽 번호가 아님을 보충 메타데이터로 드러낸다. |
| parse_pdf | PDF 표 최소 길이를 설정에서 받고 locator={"type":"page","value":...}를 추가한다. | 형식 튜닝과 실제 PDF 페이지 위치를 드러낸다. 기존 page 값은 유지한다. |
| chunk_documents | 본문 크기·겹침·구분자·접두사 템플릿과 표 최대 길이를 설정에서 받는다. | 문서군 설정에 맞춰 청크 파라미터를 바꿀 수 있게 한다. _hard_split과 분할 루프는 동결판과 같다. |
| parse_table | 헤더 키워드, wide 열 기준, note marker, 일정 패턴/표제, 일반 열 이름, 캡션 길이를 설정에서 받는다. 헤더 키워드가 비면 기존 fallback start=1을 쓴다. | 도메인 단어를 프로필로 옮기고 기존 표 파싱 경로를 유지한다. |
| row_summary | 행 라벨 키워드·제외 열·값 판정·행/문자/쌍 상한을 설정에서 받는다. wide 표에서 행 라벨 키워드가 비면 기존 roster 요약 경로를 사용한다. | 도메인 규칙을 제거한 중립 기본값을 제공한다. 새로운 라벨 휴리스틱은 추가하지 않았다. |
| doc_title, build_contextual_chunks | 제목 매핑·fallback·청크 접두사·문맥 header·표제·kind 라벨·요약/원문 marker를 설정에서 받는다. | 문맥 문자열 형식과 제목 규칙을 바꿔 쓸 수 있게 한다. |
| run_all, CLI | 입력 경로와 ParserConfig를 전달해 파싱, 청킹, 문맥 생성을 실행한다. JSONL과 manifest는 패키지 내부 serializer로 저장한다. | 범용판을 별도 복사해도 CLI와 API가 동작하도록 한다. |
| JSONL metadata | 기존 metadata를 보존하고 locator를 추가한다. | HWP element index와 PDF page의 위치 의미를 명시한다. |

## 프로필

profiles/gachon_2027.py는 필수 파일명·문서 제목·prefix 길이와 가천대 표 규칙을 제공한다. 설정된 튜닝값은 동결판과 같아야 하며, 스냅샷 parity 테스트가 이 구성을 확인한다. 중립 기본값은 문서 제목·도메인 header/row 키워드·일정 키워드·고정 입력 목록을 사용하지 않는다.

## 변경하지 않은 알고리즘

normalize의 변환 순서, HWP 병합 셀 전개, PDF 표 행 markdown 변환, 본문 recursive splitter, 표의 첫 두 줄 반복 분할, parse_table의 wide/roster 분기, expand_header, dedup_cells, row_summary 정렬 규칙과 문맥 청크의 원문/색인 텍스트 분리는 동결판 흐름을 유지한다. 알려진 표·헤더 한계는 HARDCODED.md에 기록했다.
