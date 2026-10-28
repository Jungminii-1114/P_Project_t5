# 골든 원문 대조

기대값은 원문 PDF PNG와 HWP cells JSON에서만 작성했다. 사용자 검토 상태는 **대기**다. JSON 문법은 YAML의 부분집합이므로 추가 YAML 의존성 없이 읽는다.

| ID | 출처·위치 | 유형 | 통과 셀 | 표 통과 | PNG / 셀 JSON (scratch, Git 제외) |
|---|---|---|---:|---|---|
| hwp-roster-multi-stub | 01 / 2 | HWP merged headers and numeric roster | 0/5 | 실패 | runs/baseline2/golden/hwp_cells_reference.json |
| hwp-schedule-notes | 01 / 3 | HWP schedule with vertically merged category and note columns | 0/5 | 실패 | runs/baseline2/golden/hwp_cells_reference.json |
| 02-region-eligibility-symbols | 02 / 4 | eligibility matrix with check and cross symbols | 0/5 | 실패 | runs/baseline2/golden/source_pngs/02_p004.png |
| 02-regional-allocation-panels | 02 / 6 | large regional allocation matrix with repeated panel headers | 0/5 | 실패 | runs/baseline2/golden/source_pngs/02_p006.png |
| 03-admission-unit-count-matrix | 03 / 33 | unrelated multilevel admission-by-unit matrix | 0/5 | 실패 | runs/baseline2/golden/source_pngs/03_p033.png |
| 03-grade-conversion-inset | 03 / 85 | grade-interval lookup embedded inside a larger table cell | 0/6 | 실패 | runs/baseline2/golden/source_pngs/03_p085.png |
| 03-regional-balance-career-grid | 03 / 85 | nested career-choice grade-interval lookup | 0/6 | 실패 | runs/baseline2/golden/source_pngs/03_p085.png |
| 04-school-violence-multilevel | 04 / 35 | multilevel headers with stage-specific merged assessment cells | 0/6 | 실패 | runs/baseline2/golden/source_pngs/04_p035.png |
| 04-scholarship-merged-rows | 04 / 40 | unrelated scholarship table with hierarchical header and vertical row merges | 0/6 | 실패 | runs/baseline2/golden/source_pngs/04_p040.png |
| 05-interview-date-session | 05 / 2 | interview schedule with dates split into morning and afternoon | 6/6 | 통과 | runs/baseline2/golden/source_pngs/05_p002.png |
| 05-interview-category-date-session | 05 / 3 | nested interview category, date, and session headers | 5/5 | 통과 | runs/baseline2/golden/source_pngs/05_p003.png |

엄격 결과: 표 2/11, 셀 삼중항 11/60, 값만 비교 37/60.
공백만 정규화하며 라벨 별칭·특정 페이지 보정·정답 맞춤 예외는 없다. 실패별 실제 추출값은 metrics/golden.json에 보존했다.

초기 10개에 원문 감사로 확인한 하단 지역균형 구간표를 11번째로 추가했다. 표본은 원문 셀에서 작성했고 기존 기대값은 유지했다. 이 중첩 구간표는 별도 추출되지 않아 table_ordinal=null, extraction_status=not_separately_detected로 기록하고 누락 실패로 센다. 파서에 예외를 추가하지 않았다.

제목·공백 뒤의 논리 헤더와 top-contiguous header_rows는 다를 수 있다. 추출기별 격자 좌표 차이, 지역별 반복 소헤더, 텍스트형 값과 누락 문자도 엄격 비교에서 실패한다. 선 없는 표는 시각 확인하지 못했다.

pytest는 IR·렌더러·분할·비교기의 동작을 검증한다. 원문 골든 수용 검사는 `uv run python -m scripts.check_table_golden --strict`이며 현재 종료 코드 1이다. pytest 통과가 골든 전체 통과를 뜻하지 않는다.

재생성: `uv run python scripts/prepare_golden_tables.py`. PNG, source_table_inventory.json, page_number_validation.json, HWP 셀 JSON을 scratch에 저장한다.
