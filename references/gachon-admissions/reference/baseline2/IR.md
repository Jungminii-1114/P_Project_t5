# Table IR

`src/docparse/ir.py`의 `Cell`은 0부터 시작하는 row/col, 양수 rowspan/colspan, text, is_header를 보존한다.
`Table`은 table_id, source, locator, page, n_rows/n_cols, cells, header_rows, stub_cols, origin,
confidence, diagnostics를 포함한다. `to_dict/to_json`, `from_dict/from_json`으로 왕복한다.
ID는 파일명·위치·표 순번의 SHA-256 앞 24자리다. 내용 변경 감지는 별도 입력 manifest 해시로 한다.

`header_path(col)`은 해당 열을 덮는 위쪽 헤더 셀을 순서대로 반환한다.
`row_label(row)`는 왼쪽 stub 영역을 덮는 셀을 반환하므로 세로 병합 라벨도 후속 행에서 유지된다.
연속한 같은 텍스트는 한 번만 반환한다. JSON은 VLM 어댑터의 공통 출력 계약이다.

## 추출

HWP는 loader cells JSON의 좌표·span을 옮긴다. 구조 마커 제거, 공백·파이프 처리와 `[IMAGE]` 제거는
기존 규칙을 따른다. locator는 element_index이며 page는 호환 값 element_index+1이다.

PDF는 pdfplumber `find_tables()`의 cells bbox, rows, columns를 읽는다. 좌표 경계를 0.5pt 허용오차로
묶고 각 bbox가 덮는 격자 구간에서 span을 계산한다. 텍스트는 `page.crop(bbox).extract_text()`로 읽는다.
`extract_tables()`의 대응 셀과 비교한 차이는 `diagnostics.cell_text_comparison`에 기록한다.
좌표가 없거나 유효하지 않으면 기존 2차원 셀을 span=1로 옮기고 `pdf_fallback`으로 표시한다.
기본 pdfplumber가 탐지하지 못한 선 없는 표를 이 fallback이 새로 발견하지는 않는다.

## 범용 판별과 한계

위쪽부터 `is_value` 숫자·기호 셀이 나오는 첫 데이터 행 직전까지를 헤더로 본다.
값 영역의 가로 병합 텍스트 밴드는 최대 8행까지 헤더 후보로 유지한다. 값 왼쪽의 가로 병합 라벨은
헤더 밴드로 간주하지 않는다. 데이터의 첫 값 열 중 가장 왼쪽 열 직전까지를 stub으로 삼는다.
헤더 0개, 값 경계 없음 등은 uncertain이며 새 렌더러 대신 baseline1로 돌아간다.

이 규칙은 제목·공백·각주가 앞에 있는 표, 텍스트형 값, 반복 지역별 패널 헤더, 중첩 표를 정확히
해석하지 못한다. confidence는 검증된 확률이 아니다. confident 표도 골든에서 실패할 수 있다.
실제 셀 정확도와 원문 대조 결과는 GOLDEN.md와 metrics/golden.json을 참고한다.
