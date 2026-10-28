# 파서 출력 계약

baseline-1의 소비자는 `langchain_core.documents.Document` 목록을 받는다. 다음 파서도 아래 문맥 청크를 반환하면 현재 색인·검색 코드에 연결할 수 있다. 기준 구현은 [동결판 context.py](docparse_b1/context.py), 소비 코드는 [v23 보존본](../../legacy/build_notebook_v23.py)의 §5~9이다.

| 필드 | 타입 | 필수 시점 | 의미 |
|---|---|---|---|
| `page_content` | `str` | 항상 | 요소 단계에서는 추출 본문/markdown 표, 청킹 단계에서는 출처 접두사와 조각, 문맥 단계에서는 색인 텍스트 |
| `metadata` | JSON 직렬화 가능한 `dict` | 항상 | 아래 메타데이터를 포함 |
| `metadata.source` | `str` | 항상 | 확장자를 포함한 원본 파일명. 검색·인용에서 문서 식별자로 사용 |
| `metadata.page` | `int` | 항상 | PDF는 1부터 시작하는 실제 파일 페이지. HWP는 아래의 호환 위치 값 |
| `metadata.kind` | `"text"` 또는 `"table"` | 항상 | 본문과 표. 다른 값은 현재 소비자와 합의되지 않음 |
| `metadata.part` | `int` | 청킹 이후 | 해당 요소 내부 조각 번호, 0부터 시작 |
| `metadata.chunk_id` | `int` | 청킹 이후 | 목록 전체의 0부터 시작하는 순번. 입력·정렬·청킹 변경 시 바뀜 |
| `metadata.raw` | `str` | 문맥 단계 | 청킹 단계 `page_content` 전체. 출처 접두사를 포함하며 LLM 근거로 사용 |
| `metadata.title` | `str` | 문맥 단계 | 설정된 문서 제목 또는 결정적 파일명 기반 제목 |
| `metadata.locator` | `dict` | 범용판 | 아래 위치 유형·값. 동결판에는 없고 향후 파서에는 사용 권장 |

`page_content`는 문맥 헤더 + 선택적 `[표 행 요약]` + `[원문]` + `raw`다. 임베딩과 BM25는 행 요약을 포함한 이 텍스트를 사용한다. v23의 `_context()`는 `metadata.raw`를 우선 사용한다. 행 요약을 원문 근거처럼 LLM에 보내지 않는 분리다. 현재 소비자와의 호환을 위해 기존 키와 값은 유지하고 새 정보는 추가 키에 둔다.

PDF `page=3`은 PDF 파일의 세 번째 페이지이며 인쇄된 지면 번호와 다를 수 있다. HWP 본문 `page=1`은 관례적 값이다. HWP 표 `page=element_index+1`은 loader 요소 위치이며 실제 쪽 번호가 아니다. 범용판은 PDF에 `{"type":"page","value":3}`, HWP에 `{"type":"element_index","value":12}`처럼 원래 loader의 0부터 시작하는 요소 위치를 추가한다. HWP 본문도 loader의 `element_index`를 쓰며, 키가 없는 경우 0을 사용한다. `page`를 실제 쪽 번호로 재해석하지 않는다.

현재 Chroma 단계에 직접 연결할 때는 중첩 객체인 `locator`를 별도 저장하거나 색인 전용 메타데이터에서 제외해야 한다. v23 자체는 이 키를 처리하도록 수정하지 않았다. 범용판을 실제 RAG에 연결하는 검증은 [B7](../../BACKLOG.md)의 범위다.

새 파서는 [ParserConfig](docparse_generic/config.py)와 프로필 구조를 따르는 것을 권장한다. 설정과 도메인별 값을 분리하되 현재 계약의 `raw`, 문서·위치 식별, 종류를 보존한다. 표 IR·VLM 결과의 추가 필드는 이 계약의 확장으로 다루며 이번 작업에서 구현하지 않는다.

파서 단위 비교 산출물은 `raw_docs.jsonl`(요소), `chunks.jsonl`(청킹), `contextual_chunks.jsonl`(색인 텍스트와 raw), `manifest.json`(입력 해시·패키지·개수·출력 해시)이다. jsonl은 각 행에 `page_content`와 `metadata`만 저장한다. 비교 지점은 입력 해시, 단계별 순서·개수, 문맥 청크 전체 텍스트·메타데이터이며 범용판의 프로필 동일성에서는 `locator`만 제외한다. 문서·데이터가 없을 때의 테스트 skip은 성공적 비교를 뜻하지 않는다. 지표나 파서 간 실험 설계는 [B2](../../BACKLOG.md)에 남긴다.
