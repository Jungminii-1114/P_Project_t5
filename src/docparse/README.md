# docparse

로컬 HWP/PDF 파싱·청킹 패키지다. API 클라이언트, 임베딩, 벡터 DB를 사용하지 않는다.
`uv sync`로 src 레이아웃 패키지를 설치한다.

```python
from dataclasses import replace
import docparse

config = docparse.load_profile("neutral")
config = replace(config, index_render="header_records", llm_render="html_full")
result = docparse.run_all("local-documents", config)
```

기본 `baseline1/baseline1`은 동결 파서와 같은 세 목록 `raw_docs`, `chunks`,
`contextual_chunks`를 반환한다. `locator`를 제외한 JSONL은 baseline-1과 바이트 단위로 같다.
IR을 요청하면 `table_ir`(ID → Table)와 `tables`(ID → 길이 상한 이내 전체 HTML)도 반환한다.
`extract_table_ir=True`로 렌더러를 바꾸지 않고 구조만 수집할 수 있다.

```powershell
uv run python -m docparse data/dataset --profile gachon_2027 --extract-table-ir --out runs/parser
uv run python -m docparse data/dataset --profile gachon_2027 --index-render header_records --llm-render html_full --out runs/parser_html
```

HWP 쪽 위치는 실제 쪽 번호가 아닌 loader 요소 순번이다. 중첩 메타데이터는 Chroma 입력 전에
`docparse.render.chroma_metadata`로 제거한다. IR과 전체 표 저장소는 별도로 보관한다.
실무 이식 계약과 한계는 `reference/baseline2/` 문서를 참고한다.

함께 복사된 `CHANGES.md`, `HARDCODED.md`, `PROFILE_DIFF.md`는 출발점인 범용 파서의 이력이다.
새 문서군에서는 기본 중립 설정으로 시작하고 현 문서군 프로필은 가져가지 않는다.
