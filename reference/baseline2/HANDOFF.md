# 실무 인계

가져갈 것은 `src/docparse/`, Table/Cell IR 계약, `tests/golden/tables.yaml` 형식,
`check_table_golden.py`, `diagnose_tables.py`, `diagnose_bm25.py`와 구조 테스트다.
파서 설치는 src 레이아웃 빌드 설정과 필요한 파싱 의존성을 새 프로젝트에 등록한다.
중립 ParserConfig로 시작하고 문서 순서·제목·용어는 새 프로필로 지정한다.

v24의 검색·검증·답변 파이프라인과 현 문서군 프로필은 실험용으로 두고 간다.
BM25 스크립트의 문서 접두사/src 해석과 수동 확인 기록 역시 이 자료군의 진단 어댑터다.
실무에서는 출처 식별 계약과 데이터 해시에 맞춰 교체한다.

## VLM 연결 지점 (설계만 제공)

```python
def table_from_vlm(payload: dict | str, *, source: str, locator: dict,
                   page: int, ordinal: int, config: ParserConfig) -> Table:
    ...
```

입력은 HTML table 또는 row/col/rowspan/colspan/text 셀 JSON이다.
어댑터는 원문에 없는 값을 보충하지 않고 0 기반 좌표와 span을 검사한 뒤 Cell 목록으로 옮긴다.
`table_id(source, locator, ordinal)`을 쓰고 source/locator/page를 보존한다.
현재 origin enum은 추출기 세 종류로 고정되어 있으므로 VLM을 실제 추가할 때 `vlm_cells` 같은
출처 값을 스키마 버전과 함께 확장해야 한다. 기존 추출기 출처로 위장하지 않는다.
결과를 infer_structure 또는 VLM이 명시한 검토 가능한 헤더 경계에 연결하고 동일 렌더러로 비교한다.
이번 작업에서 VLM 호출·어댑터는 구현하지 않았다.

비교 지표는 원문 골든 셀 삼중항 정확도, 표 전체 구조 정확도, BM25 페이지 적중 대리 지표,
동일 설정에서의 RAG 정답 수·시간 점수다. 골든 기대값은 사용자 검토 대기 상태이며 실패를 보존한다.

## 남은 문제

- F2 개체–숫자 오탐(B3): 이번 범위에서 수정하지 않았다.
- 선 없는 표 탐지, 중첩 표, 텍스트형 값, 추출기별 좌표·문자 차이.
- HWP 실제 쪽 번호와 제목/공백 행을 구별하는 헤더 모델.
- confidence는 확률이 아니므로 낮은 골든 성능을 가리지 말 것.
- 파서 외 모듈화·전역 상태·라우팅/프롬프트 특화 값 분리(B8).
- 새 독립 문서군과 평가셋에서 검증하기 전 일반화 성능을 주장하지 말 것.
