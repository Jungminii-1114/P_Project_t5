# 독립 문서 파싱 단계 (JS 브랜치)

> 상태: 초기 코드와 계약 작성. 실제 PDF/HWP 실행 검증 전.  
> 범위: **문서 원본 → 텍스트/표 요소 + 원문 위치 + 구조 아티팩트**.  
> 비범위: 청킹, 임베딩, RAG 검색, LLM/VLM 호출, 최종 표 의미 검증, LangGraph 오케스트레이션.

## 1. 설계 경계

- 구현: `src/reportanchor_harness/parsing.py` — 모델 비의존 `ParserBackend` 프로토콜, `ParsingStage`, `load_parsing_artifact`.
- 어댑터: `src/reportanchor_harness/adapters/gachon_docparse.py` — 기존 `references/gachon-admissions/src/docparse`의 **parse_files만 사용**. `run_all`에 포함된 청킹/문맥 청크 생성은 호출하지 않음.
- 테스트: `tests/test_parsing_stage.py` — 외부 API 없는 더미 백엔드로 저장, 읽기, 실패 및 체크섬 검증을 정의.
- 기존 레퍼런스 RAG: 수정하지 않음. 추후 입력 계약을 합의해 검색·검증에 연결.
- 현재 어댑터는 docparse에서 제공하는 텍스트·표 및 선택적 Table IR을 전달함. 이는 **추출된 잠정 구조**이며 헤더·셀 의미가 올바르다고 검증된 자료는 아님.

## 2. 저장 계약 v1

출력은 실행별 새 디렉터리 `output_root/parse_<uuid>/`에 저장됨.

| 파일 | 용도 |
|---|---|
| `blocks.jsonl` | 각 텍스트/표 블록의 순서, 내용, 내용 해시, 문서 ID, locator, 연결된 table_id, 검증 상태 |
| `tables.jsonl` | 가능한 경우 Table IR. 모든 레코드의 검증 상태는 초기 `unverified` |
| `manifest.json` | 스키마 버전, 문서 해시/크기, 어댑터 버전, 설정 해시, 출력 해시/건수 |
| `state.json` | `running / completed / failed`, run_id와 오류 타입 |

`locator`는 `{"type":"page","value":1}` 또는 `{"type":"element_index","value":0}`처럼 의미를 분리. HWP `element_index`는 출력 페이지 번호가 아니며, PDF일 때만 `pdf_page`에 실제 PDF 파일 페이지 번호가 들어감(인쇄 쪽 번호와 별개).

## 3. 실행 예시

레퍼런스 파서를 설치하고(레퍼런스의 `pyproject.toml` 참조), 새 프로젝트 패키지를 import 가능한 환경에서 실행:

```python
from reportanchor_harness.parsing import ParsingStage, load_parsing_artifact
from reportanchor_harness.adapters.gachon_docparse import LegacyDocparseAdapter

stage = ParsingStage(LegacyDocparseAdapter())
result = stage.run("data/raw/example.pdf", "outputs/parsing")
manifest, blocks, tables = load_parsing_artifact(result.directory)
print(manifest["status"], len(blocks), len(tables))
```

로컬 개발에선 저장소 루트의 `src`와 `references/gachon-admissions/src`를 Python import 경로에 두거나 두 패키지를 개발용 editable install해야 함. 의존성·패키징은 아직 통합하지 않았음.

## 4. 다음 모듈과의 인터페이스

- **입력**: 단일 로컬 PDF/HWP 파일 및 파서 설정.
- **출력**: `manifest`와 파일 참조, `blocks`(텍스트, 표, locator), 선택적 `tables`(Table IR).
- **후속 VLM/구조 보완**: `block_id`, `table_id`, locator를 유지하면서 기존 IR과 새로운 해석을 비교·버전화.
- **후속 청킹**: 저장된 파싱 아티팩트를 읽어 chunk 집합을 생성하고, 각각에 원본 `block_id` 및 원문 위치를 연결. 파서를 다시 실행할 필요가 없어야 함.

현재 단계는 **독립 결과 저장**까지 구현하며, 입력 기반 캐시 적중·증분 재실행, 구조 검증, 병렬 실행 및 체크포인트 복구는 후속 하네스 모듈 책임.

## 5. 확인 및 제한 사항

- 코드 작성과 브랜치 커밋은 완료되었지만 이 대화에서는 실제 Python 테스트/파서 실행을 수행하지 않았음.
- 레퍼런스 파서는 기존 로직을 재사용하므로 PDF의 선 없는 표, HWP 실제 쪽 번호, 병합 헤더 등 기존 알려진 한계가 남아 있음.
- 표 파싱은 청킹과 분리하더라도 표 구조 정확도까지 보장하지 않음. v24 골든 평가에서 표 2/11 통과 기록을 유지함.
- 원본 파일 내용 자체는 출력에 복사하지 않으나 텍스트/표 추출 결과는 민감 내용을 포함할 수 있음. 출력 경로의 접근권한과 Git 제외 처리가 필요.
- 아티팩트 출력 SHA-256은 손상 검출용. 원본 해시 및 백엔드/설정 해시와 함께 보관하지만 암호학적 서명이나 접근통제는 아님.

## 레퍼런스

- [기존 docparse](../references/gachon-admissions/src/docparse/)
- [기존 파서 데이터 계약](../references/gachon-admissions/reference/baseline1/INTERFACE.md)
- [기존 Table IR](../references/gachon-admissions/reference/baseline2/IR.md)
- [기존 파서 이식 지침](../references/gachon-admissions/reference/baseline2/HANDOFF.md)
