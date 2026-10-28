# 표 렌더러

색인은 `baseline1 | header_records`, LLM 근거는 `baseline1 | html_full | header_records`로 따로 고른다.
기본은 baseline1/baseline1이며 기존 JSONL 동일성을 유지한다. 문맥 헤더 형식도 유지한다.

- baseline1: 기존 markdown·표 행 요약과 metadata.raw를 사용한다.
- html_full: `<table><tr><th colspan="2">Window</th>…`처럼 병합 span을 보존한다.
- header_records: `[Alpha] Window/First = 10`처럼 각 사실에 행 라벨과 전체 헤더 경로를 넣는다.

새 경로는 `metadata.table_id` 문자열로 IR/전체 표 저장소에 연결된다. `run_all()`의 `table_ir`는
ID→Table, `tables`는 ID→전체 HTML이다. CLI는 각각 JSONL로 저장한다.
`metadata.raw`는 LLM용 조각이다. `_context()`는 html_full에서 전체 저장소에 있는 표만 중복을 제거하고
전체 HTML을 한 번 넣는다. 저장소에 없는 표는 조각을 모두 보존한다.

baseline 색인은 HTML 근거로 바꾸어도 page_content가 같아 임베딩을 재사용한다. 레코드 색인은
완전한 셀 사실 사이에서 분할한다. 한 사실이 길면 잘라 헤더를 잃게 하지 않고 상한을 초과하도록 둔다.
각 레코드 조각의 baseline/HTML 근거는 해당 행 범위를 렌더링하고 헤더를 반복한다.
한 행이 여러 레코드 조각에 걸리면 그 행의 markdown/HTML이 반복될 수 있다.

`table_full_max_chars=12000`: 측정한 전체 HTML 최대 7,903자를 모두 수용하면서 큰 신규 표의 전체 전달을
제한하는 보수적 상한이다. 현재 자료에서는 이 상한을 넘는 HTML 표가 0개다.
초과 표는 저장소에 넣지 않고, 헤더를 반복한 행 범위 HTML 조각으로 전달한다.
불확실한 표는 색인과 근거 모두 baseline1 출력을 사용한다.

Chroma에는 str/int/float/bool 메타데이터만 넣는다. locator, IR 등 중첩 값은 제외한 복사본을 사용한다.
원본 문서와 IR에는 위치 정보를 유지한다. 캐시는 모델 이름과 정확한 텍스트의 SHA-256을 키로 사용하고
runs/cache/ 아래에 저장한다. 문서와 질의 임베딩은 공급자의 서로 다른 입력 유형을 보존하기 위해 구별한다.
