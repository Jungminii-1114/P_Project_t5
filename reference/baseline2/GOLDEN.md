# 골든 원문 대조

기대값은 원문 PDF PNG와 HWP loader cells JSON에서 작성했다. 평가 질문·정답 문장은 사용하지 않았다.
사용자 검토 상태: **대기**. JSON 문법은 YAML의 부분집합이므로 추가 YAML 의존성 없이 읽을 수 있다.

| ID | 출처·위치 | 유형 | 통과 셀 | 표 통과 | PNG / 셀 JSON (scratch, Git 제외) |
|---|---|---|---:|---|---|
| hwp-roster-multi-stub | 01 / 2 | HWP merged headers and numeric roster | 0/5 | 실패 | runs/baseline2/golden/ (HWP cells JSON) |
| hwp-schedule-notes | 01 / 3 | HWP schedule with vertically merged category and note columns | 0/5 | 실패 | runs/baseline2/golden/ (HWP cells JSON) |
| 02-region-eligibility-symbols | 02 / 4 | eligibility matrix with check and cross symbols | 0/5 | 실패 | runs/baseline2/golden/source_pngs/02_p004.png |
| 02-regional-allocation-panels | 02 / 6 | large regional allocation matrix with repeated panel headers | 0/5 | 실패 | runs/baseline2/golden/source_pngs/02_p006.png |
| 03-admission-unit-count-matrix | 03 / 33 | unrelated multilevel admission-by-unit matrix | 0/5 | 실패 | runs/baseline2/golden/source_pngs/03_p033.png |
| 03-grade-conversion-inset | 03 / 85 | grade-interval lookup embedded inside a larger table cell | 0/6 | 실패 | runs/baseline2/golden/source_pngs/03_p085.png |
| 04-school-violence-multilevel | 04 / 35 | multilevel headers with stage-specific merged assessment cells | 0/6 | 실패 | runs/baseline2/golden/source_pngs/04_p035.png |
| 04-scholarship-merged-rows | 04 / 40 | unrelated scholarship table with hierarchical header and vertical row merges | 0/6 | 실패 | runs/baseline2/golden/source_pngs/04_p040.png |
| 05-interview-date-session | 05 / 2 | interview schedule with dates split into morning and afternoon | 6/6 | 통과 | runs/baseline2/golden/source_pngs/05_p002.png |
| 05-interview-category-date-session | 05 / 3 | nested interview category, date, and session headers | 5/5 | 통과 | runs/baseline2/golden/source_pngs/05_p003.png |

엄격 비교 결과는 표 2/10, 셀 삼중항 11/54, 값만 비교하면 37/54이다.
공백만 정규화하며 라벨 별칭, 특정 페이지 보정, 정답 맞춤 예외는 없다. 실패 상세와 실제 추출값은 metrics/golden.json에 저장했다.

원문과 IR의 구조 차이: 제목·공백 다음의 논리 헤더와 top-contiguous header_rows가 다르다. 일부 PDF 셀 좌표가 추출기별로 다르고, 03 p.85의 등급표는 외곽 셀 안의 중첩 표다. 02 p.6은 지역 패널마다 소헤더가 반복된다. 선 없는 PDF 표는 시각 확인하지 못했으므로 검증 완료로 세지 않았다.

pytest는 IR 계약·렌더러·분할·골든 비교기의 동작을 검증한다. 원문 골든 정확도는 별도 `uv run python -m scripts.check_table_golden --strict`로 검사하며 현재 종료 코드 1이다. pytest 통과가 골든 전체 통과를 뜻하지 않는다.

재생성: `uv run python scripts/prepare_golden_tables.py`. 이 도구는 PNG·source_table_inventory.json·page_number_validation.json·HWP cells를 scratch에 쓴다.
