# CHANGES — 동결판

기준: `build_notebook.py` v23, commit `64ac263`, §1–§4.

| 함수·영역 | 변경 | 이유 |
|---|---|---|
| `required_files` | 본문 그대로 이식 | 필수 입력 파일명·순서·누락 오류를 v23과 유지한다. |
| `_sha256_file`, `build_document_manifest` | 본문 그대로 이식 | 원문 manifest 형식을 유지한다. |
| `parse_required_files` | 본문 그대로 이식 | 원문 5개에 HWP/PDF 파서를 적용하는 순서를 유지한다. |
| `prepare_dataset`, `_extract`, `_bounded_find`, `_all_present` | 이식하지 않음 | Colab의 ZIP·Drive·업로드 검색만 담당한다. `load_sources`는 지정한 로컬 디렉터리만 검사한다. |
| `normalize`, `render_hwp_table`, `parse_hwp`, `rows_to_markdown`, `parse_pdf` | 함수 본문 그대로 이식 | 형식별 파싱 및 메타데이터를 v23과 유지한다. import만 모듈별로 정리했다. |
| 섹션 3의 `splitter`, `_hard_split`, `split_table_markdown` | 설정값·분할 본문 그대로 이식 | 본문 800/100, 표 1,400자 분할과 헤더 반복을 유지한다. |
| 섹션 3의 청크 루프 | `chunk_documents(raw_docs)` 함수로 감쌌다. 출력 `print`만 제거했다. | 파이프라인 실행 없이 호출 가능한 API를 제공한다. 루프·접두사·메타데이터 본문은 유지한다. |
| `doc_title`, `dedup_cells`, `is_value`, `expand_header`, `parse_table`, `row_summary` | 본문 그대로 이식 | 표 처리와 문맥 구성 알고리즘을 변경하지 않았다. import를 정리했다. |
| `build_contextual_chunks` | 본문 그대로 이식 | `raw`, `title`, 색인 텍스트 생성을 유지한다. 요약 개수 출력은 원본처럼 유지한다. |
| 섹션 1의 전역 실행 | `parse_documents(directory)`와 `run_all(directory)`로 감쌌다. | import 시 원문 파싱이 실행되지 않도록 했다. |
| CLI | 결과 3종을 UTF-8 JSONL로 직렬화하고 같은 형식의 manifest를 기록한다. | 노트북 파이프라인 외부에서 단독 실행 및 스냅샷 대조를 지원한다. |
| `print` | 코드 셀 진행 출력은 CLI에서 간단한 완료 수치로 대체했다. `build_contextual_chunks`의 기존 요약 출력은 유지한다. | 라이브러리 호출 결과와 CLI 사용을 명확히 한다. |

`docparse_b1`은 API·임베딩·벡터 저장·검색 의존성을 직접 import하지 않는다. 원본의 HWP loader, `langchain_core.documents.Document`, PDF 파서 및 텍스트 splitter만 사용한다.
