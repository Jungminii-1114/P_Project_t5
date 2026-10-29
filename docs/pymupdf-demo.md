# PyMuPDF PDF 추출 데모

실제 파싱·VLM 담당자의 출력이 연결되기 전, RAG 개발에 사용할 텍스트 입력을 만드는 임시 추출기입니다. 특정 기관·연도·문서 제목을 코드의 분기 조건으로 사용하지 않습니다. 팀의 최종 데이터 계약을 확정한 구현은 아닙니다.

## 실행

현재 프로젝트의 Python 3.13.9 / PyMuPDF 1.28.2 환경을 사용합니다.

```bash
cd "/Users/ijeongmin/ai_study/Personal_project/Report Agent"

# data/raw 안의 PDF를 처리합니다.
./.venv/bin/python 01_extract_pdf.py

# PDF 한 개와 선택적 출처·키워드를 지정합니다.
./.venv/bin/python 01_extract_pdf.py \
  --pdf data/raw/kistep_2025_plan.pdf \
  --source-url "https://www.kistep.re.kr/boardDownload.es?bid=0017&list_no=16371&seq=2" \
  --keyword "국가연구개발성과평가"
```

- PDF를 여러 개 처리할 때는 `--file-dir data/raw`를 사용합니다. `.PDF` 확장자도 지원합니다.
- `--pdf`와 `--file-dir`는 함께 지정하지 않습니다.
- CLI의 상대 입력·출력 경로는 터미널 위치와 관계없이 이 프로젝트 폴더를 기준으로 해석합니다.
- 기본 결과 루트는 `data/processed/pymupdf_demo`이며 `--out`으로 변경할 수 있습니다.
- `--source-url`을 생략하면 출처 URL은 `null`입니다. 배치에서 지정한 URL은 모든 입력에 공통으로 기록됩니다.
- `--keyword`는 공백을 무시하는 문자열 일치로 후보 페이지를 모읍니다. 의미 검색·RAG·정확성 검증은 수행하지 않습니다.
- `--split-pages`를 추가하면 검토용 페이지별 PDF도 저장합니다. 기본 실행에서는 생성하지 않습니다.
- 실패한 문서가 있으면 종료 코드 1과 오류 목록을 반환하며, 배치의 다른 PDF는 계속 처리합니다.

## 저장 위치와 파일

```text
data/processed/pymupdf_demo/
└── kistep_2025_plan_0530d100e085/
    ├── manifest.json
    ├── pages.jsonl
    ├── blocks.jsonl
    ├── output.txt
    ├── candidate_pages.txt
    ├── summary.json
    └── pages/                 # --split-pages 사용 시
```

문서 폴더명은 파일명과 원본 SHA-256 일부로 구성합니다. 같은 이름의 다른 PDF는 별도 폴더를 사용합니다. 같은 PDF를 같은 결과 루트에 재실행하면 해당 결과 파일을 갱신합니다. 기존 `data/processed/kistep_2025`와 원본 PDF는 수정하지 않습니다.

| 파일 | 용도 |
|---|---|
| manifest.json | 문서 ID, 원본 SHA-256, 파일·출처 정보, 페이지 수, 파서 버전 |
| pages.jsonl | 페이지당 한 줄. 페이지 텍스트, 문자 수, 상태, 문서·페이지 참조 |
| blocks.jsonl | 텍스트 블록당 한 줄. 블록 ID, 텍스트, 원문 페이지·좌표. RAG 청킹의 입력으로 사용 |
| output.txt | 사람이 확인하기 쉬운 전체 텍스트. 파일 페이지 구분 포함 |
| candidate_pages.txt | 키워드에 일치한 페이지. 키워드가 없거나 일치하지 않으면 빈 파일 |
| summary.json | 페이지·블록·문자 수, 텍스트 없는 페이지, 키워드 후보, 결과 경로 |

## RAG 코드에서 재사용

기존 실행 파일명은 유지하고, 실제 추출 로직은 일반 Python 모듈로 분리했습니다.

```python
from pathlib import Path
from pdf_extract import extract_pdf

result = extract_pdf(Path("data/raw/kistep_2025_plan.pdf"))

document = result.document       # DocumentManifest
pages = result.pages             # list[PageManifest]
blocks = result.blocks           # list[TextBlock]

for block in blocks:
    print(block.block_id, block.text, block.source_locator)
```

또는 저장된 `blocks.jsonl`을 읽어서 청킹·임베딩·검색 모듈에 전달할 수 있습니다. 텍스트 블록은 PyMuPDF의 추출 단위이며, RAG용 의미 청크와 동일하지 않습니다.

## 출처와 상태 해석

- `pdf_page`는 파일의 물리적 페이지이며 1부터 시작합니다.
- `printed_page_label`은 인쇄된 쪽번호를 확인하기 전까지 `null`입니다. PDF 내부 페이지 라벨은 별도 `metadata.pdf_page_label`에 기록합니다.
- 블록의 `source_locator.bbox`는 PyMuPDF의 회전 전 페이지 좌표이며 단위는 pt입니다.
- 문서·페이지·블록은 원본 SHA-256으로 연결합니다. 같은 원본과 파서 조건에서 블록 ID를 추적할 수 있습니다. 파서 버전이 달라지면 블록 분할이 달라질 수 있으므로 버전 정보도 함께 사용해야 합니다.
- 모든 페이지·블록의 `verification_status`는 `unverified`입니다. 추출 성공을 사실 검증 완료로 취급하지 않습니다.
- 텍스트가 없으면 `no_native_text`, 기준보다 적으면 `low_text`로 기록하고 검토 대상으로 남깁니다. 텍스트가 없다는 사실만으로 스캔 문서라고 확정하지 않습니다.
- OCR·VLM 해석, 이미지·차트 내용 인식, 표의 행·열·다중 헤더·단위 의미 검증은 수행하지 않습니다.
- 읽기 순서 정렬을 사용하지만 복잡한 다단 문서와 표의 의미 연결까지 보장하지 않습니다.

## 테스트와 기존 코드

```bash
./.venv/bin/python -m unittest discover -s tests -v
```

테스트는 페이지·좌표 출처, ID 일관성, 같은 이름의 다른 파일 분리, 빈 페이지·이미지 전용 페이지, 암호 PDF, 잘못된 다운로드, 배치 처리, 선택적 페이지 PDF 저장을 확인합니다.


구현 참고: [PyMuPDF 텍스트 추출](https://pymupdf.readthedocs.io/en/latest/recipes-text.html), [Page.get_text](https://pymupdf.readthedocs.io/en/latest/page.html#Page.get_text).
