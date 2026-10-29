# 기술 레퍼런스 조사 목록

> 문서 목적: ReportAnchor의 기술 후보와 공식 근거, 한계, 라이선스 검토 상태를 한곳에 축적하는 공통 레퍼런스 문서
>
> 마지막 조사: 2026-10-29 · 현재 단계: **기술 후보 조사 / 최종 채택 및 법률 검토 전**
>
> **프로젝트 요구:** 로컬·오프라인 구동이 가능하고, 기업의 상업적 사용·내부 배포·오픈소스 재배포를 지원할 수 있어야 함. 문서 종류나 특정 데이터셋에 종속된 구성은 지양함.

추후 다른 기술 분야의 레퍼런스도 이 문서에 별도 항목으로 추가한다. 조사 내용은 **공식 소스에서 확인한 사실**, **설계상 추정**, **추가 검증 필요 항목**을 구분하여 관리한다. 여기의 후보 제안은 구현 결정이 아니다.

---

## 1. 문서 파서 및 시각 요소 인식

### 1.1 검토 범위와 현재 설계

입력 문서에서 **본문, 표, 이미지, 도형·흐름도, 차트, 수식, 출처 위치**를 독립적으로 추출·표현하는 범용 파싱 계층을 검토한다. 파서는 최종 답변을 생성하지 않고, 파싱 출력은 공통 중간 표현(IR)을 거쳐 하네스의 아티팩트 저장소에 보존한다.

- **원시 추출**: PDF 텍스트 레이어, 문자·선·사각형·벡터, 이미지, 파일 형식별 구조를 우선 확보
- **레이아웃·표 구조 인식**: 표 영역·셀·병합·헤더 후보, 읽기 순서, 시각적 요소 영역을 구분
- **선택적 OCR/VLM 보완**: 스캔·구조 불명확 영역에 한해 호출하는 방향 검토. 무조건 VLM에 모든 페이지를 전달하지 않음
- **출력 검증**: 원시 추출과 보완 결과를 덮어쓰지 않고 각각 보존하여 누락·불일치·근거 위치를 확인
- **하네스 경계**: 추출 로직은 파서에, 결과 버전·체크포인트·실행 이벤트·재사용 정책은 공통 하네스에 배치

**미결정:** PDF 전용 기본 추출기, HWP/HWPX 경로, 시각 모델과 구조 모델의 조합, 로컬 하드웨어별 실행 정책.

### 1.2 기술 후보 비교 (프로젝트에 채택한 것은 아님)

| 후보 | 검토 목적·강점 | 확인된 한계 또는 위험 | 확인한 라이선스 / 채택 상태 |
|---|---|---|---|
| [pdfplumber](https://github.com/jsvine/pdfplumber) | PDF 문자·선·사각형 좌표와 표 추출. lines/text 등 표 경계 전략과 디버깅 도구 제공 | OCR 미제공. 이미지 기반 표, 선 없는 표, 복잡한 병합·다단 헤더의 의미 연결에 취약할 수 있음. text 전략으로 선 없는 표 일부 처리 가능 | [MIT](https://github.com/jsvine/pdfplumber/blob/stable/LICENSE.txt) 확인 · **기본 경량 후보** |
| [pypdfium2](https://pypdfium2.readthedocs.io/en/stable/readme.html) | PDFium 기반 로컬 렌더링·PDF 페이지 처리. PyMuPDF와 별개의 라이선스 선택지 | 독립적인 고수준 표 의미 인식 엔진은 아님. 포함된 PDFium 바이너리·서드파티 고지 확인 필요 | [Apache-2.0 / BSD-3-Clause](https://pypdfium2.readthedocs.io/en/stable/readme.html) (래퍼) + PDFium/포함 의존성 별도 · **렌더링 후보** |
| [PyMuPDF](https://pymupdf.readthedocs.io/en/latest/) | 빠른 텍스트·좌표·이미지·벡터 추출과 PDF 렌더링 | 표·차트의 논리 의미 검증까지 자동 보장하지 않음. 기업 배포 시 라이선스 의무 검토가 중요 | [AGPL-3.0 또는 Artifex 상용](https://pymupdf.io/licensing) · **법률 검토 전 기본 채택 보류** |
| [Docling](https://github.com/docling-project/docling) | 통합 문서 IR, 레이아웃 분석, TableFormer, 선택적 OCR, 그림·차트 처리 기능. 로컬 실행 후보 | 모델별 사용 조건 상이. 복잡한 표/차트의 정확도, 로컬 메모리·속도, HWP/HWPX 경로 별도 검증 | [코드 MIT](https://github.com/docling-project/docling/blob/main/LICENSE). **모델 가중치별 라이선스 별도 확인 필요** · **우선 비교 후보** |
| [PaddleOCR / PP-StructureV3](https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/PP-StructureV3.html) | 문서 레이아웃, OCR, 표·수식·차트 인식이 모듈화된 파이프라인 | 별도 모델·런타임 다운로드와 하드웨어 지원, 한국어·병합 표 정확도 검증 필요 | [PaddleOCR 코드 Apache-2.0](https://github.com/PaddlePaddle/PaddleOCR/blob/main/LICENSE) 확인. 선택 모델/의존성은 별도 · **우선 비교 후보** |
| [PaddleOCR-VL 계열](https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/PaddleOCR-VL.html) | 레이아웃 탐지 후 영역별 VLM으로 표·수식·차트 등 인식. 어려운 영역에 선택적으로 활용 가능 | 전체 파이프라인과 VLM 단독 실행은 동일하지 않음. 구조·수치 환각, 한국어 성능, 실제 로컬 자원 검증 필요 | [PaddleOCR-VL-1.6 모델 카드 Apache-2.0](https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.6) 확인. **실제 선택한 가중치·레이아웃 모델·런타임 각각 확인 필요** · **선택 보완 후보** |
| [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) | 스캔 이미지의 텍스트 인식, 오프라인 실행, 언어별 학습 데이터 | 표 행·열 의미/차트 관계를 직접 복구하는 모델은 아님. 스캔 품질·언어 모델 영향 | [엔진 Apache-2.0](https://github.com/tesseract-ocr/tesseract/blob/main/LICENSE), [공식 tessdata Apache-2.0](https://github.com/tesseract-ocr/tessdata/blob/main/LICENSE) · **OCR 경량 후보** |
| [OCRmyPDF](https://github.com/ocrmypdf/OCRmyPDF) | 스캔 PDF에 OCR 텍스트 레이어 생성, 후속 파서 입력 전처리 | 그 자체가 표 구조 인식기는 아님. 실행 구성의 Ghostscript 등 별도 실행 파일 라이선스 점검 필요 | [본체 MPL-2.0](https://github.com/ocrmypdf/OCRmyPDF/blob/main/LICENSE), [Ghostscript AGPL 또는 상용](https://ghostscript.com/about/) · **의존성 확인 전 배포 채택 보류** |
| [hwp-hwpx-parser](https://pypi.org/project/hwp-hwpx-parser/) | HWP/HWPX 본문·표·이미지 등 로컬 추출을 위한 형식별 후보 | PyPI에 Apache-2.0 표기·출처 증명이 있지만, 연결된 원본 저장소의 라이선스 파일을 현재 직접 확인하지 못함. 실제 기능·유지보수·배포 출처 확인 필요 | **PyPI상 Apache-2.0 표시, 독립 검증 보류** · **HWP/HWPX 후보** |

별도로 [langchain-hwp-hwpx-loader](https://pypi.org/project/langchain-hwp-hwpx-loader/)는 PyPI에 **“Apache Software License (MIT License)”**처럼 일치하지 않는 메타데이터가 나타나고, 연결된 원본 저장소도 확인되지 않았다. 추후 사용한다면 원본 배포물의 LICENSE, 종속 패키지, 버전 출처를 다시 감사해야 한다. 기본 의존성으로 가정하지 않는다.

Docling 공식 지원 형식 목록에서 HWP/HWPX 직접 지원은 확인하지 못했다. 따라서 PDF·이미지 파서의 선택과 HWP/HWPX 어댑터 선택을 별도로 취급한다.

### 1.3 표·이미지·도형에서 확인해야 할 한계

| 요소 | 핵심 실패 유형 | 검증 관점 |
|---|---|---|
| 테두리 있는 PDF 표 | 셀 경계 오탐, 병합 셀 좌표 오류 | 행·열·병합 좌표와 원문 텍스트 일치 |
| 선 없는 표 / 다단 헤더 | 열 경계 및 상위 헤더 경로 누락 | 값만이 아니라 **행 라벨 + 헤더 경로 + 값**의 연결을 검증 |
| 여러 페이지의 표 | 헤더 반복·계속되는 행 연결 실패 | 페이지별 출처 보존 및 표의 연속성 |
| 스캔·이미지 기반 표 | 텍스트·선 객체 자체가 없음 | OCR/레이아웃 모델 경로 분리, 추정 결과에 출처 표시 |
| 사진·삽화 | 시각 내용이 본문 텍스트에 나타나지 않음 | 이미지 영역과 원본 파일·페이지 위치 보존 |
| 벡터 도형·흐름도 | 선·도형 객체를 얻어도 화살표 방향·연결 의미는 별개 | 객체 추출과 의미 해석을 분리하고 관계는 검증 전 상태로 관리 |
| 차트 | 축·범례·단위·색상·수치 계열의 오독 | 추정 수치와 원문 표시값 구분, 판단 보류 가능 |
| HWP/HWPX | 요소 인덱스와 실제 출력 페이지의 불일치, 이미지 마커만 보존될 위험 | 원문 요소 위치와 변환본 페이지 위치를 다른 참조로 관리 |

**pdfplumber의 정확한 위치:** PDF 내부 객체와 기하학적 패턴을 근거로 표를 찾는 도구이며 표의 의미를 이해하는 모델이 아니다. OCR과 OCR 기반 표의 강력한 지원은 공식 범위 밖이고, 텍스트 정렬 기반 'text' 전략은 기본 선 기반 탐지의 일부 대안이다. [공식 README: 표 탐지 알고리즘·제약](https://github.com/jsvine/pdfplumber/blob/stable/README.md#extracting-tables)

### 1.4 라이선스와 상업적 사용: 개념 정리

**목표 해석:** 기업이 ReportAnchor를 비용 없이 설치·수정·내부 활용하거나 적법하게 재배포할 수 있도록, 라이선스 의무와 특허·모델·배포 제한을 명확히 하는 것. **상업적 사용 가능**과 **라이선스 의무 없음**은 서로 다르다.

| 라이선스 | 상업적 이용 | 프로젝트 채택 시 핵심 검토 |
|---|---|---|
| **MIT / BSD 계열** | 일반적으로 허용 | 저작권·라이선스 고지 유지, 번들된 다른 의존성은 별도 확인 |
| **Apache-2.0** | 허용 | 저작권·LICENSE·NOTICE, 수정 표기 및 특허 조항 확인 |
| **MPL-2.0** | 허용 | 배포 시 MPL이 적용된 **파일 수준의 수정 소스 공개 의무** 등 준수. 라이브러리 바깥의 전체 프로젝트가 자동으로 MPL로 바뀌는 것은 아님 |
| **GPL-3.0 / AGPL-3.0** | 상업적 이용 자체는 금지하지 않음 | 결합·수정·재배포 시 공개/동일 라이선스 의무, **AGPL은 수정 버전의 네트워크 서비스 제공 상황**도 별도 검토. 기업용 배포 마찰이 클 수 있음 |
| **상용 이중 라이선스** | 조건에 따라 허용 | AGPL 대신 상용 라이선스를 구매할 수 있지만 **기업이 무료로 그대로 재사용할 수 있는 기본 구성**과는 충돌할 수 있음 |
| **모델 전용 라이선스** | 모델별로 다름 | 코드가 MIT/Apache여도 가중치·토크나이저·학습 데이터·런타임이 별개. 비상업적 사용 제한, 연구 전용, 별도 동의가 있다면 상업적 사용에 제약 |

오픈소스는 일반적으로 상업적 이용 자체를 허용한다. 따라서 **AGPL을 “상업적 사용 불가”로 표시하지 않는다.** 다만 기업이 이용·변경·배포·서비스 제공을 자유롭게 하려는 목적이라면, 가급적 permissive 라이선스(MIT/Apache/BSD) 위주의 기본 실행 경로를 구성하고 copyleft 의존성은 구체적 결합/배포 방식에 따라 검토한다. **서브프로세스로 분리했다는 사실만으로 AGPL/GPL 문제가 자동 해결되지는 않는다.**

관련 원문: [OSI Open Source Definition](https://opensource.org/osd), [OSI 상업적 이용 FAQ](https://opensource.org/faq), [Apache-2.0 전문](https://www.apache.org/licenses/LICENSE-2.0), [MPL-2.0 전문](https://www.mozilla.org/en-US/MPL/2.0/), [GNU AGPLv3 전문](https://www.gnu.org/licenses/agpl-3.0.html).

### 1.5 제품 배포 전 추가 확인 사항 — 필수

**라이선스 및 공급망**

- [ ] ReportAnchor **자체 라이선스**(MIT/Apache-2.0 등) 결정. 현재 미확정.
- [ ] 채택할 파서와 **정확한 패키지·버전·커밋의 LICENSE/NOTICE**를 확인하고 제3자 라이선스 목록 및 SBOM(SPDX/CycloneDX 등) 작성.
- [ ] **모든 실제 모델 가중치·토크나이저·레이아웃 탐지기·OCR 학습 데이터** 각각의 라이선스와 상업적 사용/재배포 가능 여부 확인. Docling 코드 MIT를 모델 전체의 MIT 허가로 간주하지 않음.
- [ ] PDF 렌더러/이미지 처리기, OCRmyPDF의 Ghostscript 등 **실행 파일·네이티브 라이브러리·전이 의존성**의 라이선스 확인.
- [ ] PyMuPDF / Ghostscript 같은 AGPL 이중 라이선스 구성품을 필수로 포함할 경우, 프로젝트 라이선스·기업 내 사용·제품 재배포·로컬 웹 UI/네트워크 사용 시나리오별 법률 검토.
- [ ] 로컬 오프라인 설치가 모델·바이너리 다운로드, 라이선스 서버, 텔레메트리, 클라우드 API를 **암묵적으로 요구하지 않는지** 확인.
- [ ] 의존성의 유지보수·보안 업데이트·원본 배포처 검증, 파일 포맷별 악성 입력 처리와 리소스 제한 정책 검토.

**기술적 검증**

- [ ] **독립 문서군**에서 표 구조(행·열·병합·헤더), 이미지·차트 탐지, 한글 OCR, 읽기 순서, 원문 위치 정합성을 별도 평가.
- [ ] 스캔·디지털 PDF, HWP/HWPX, 혼합 레이아웃을 구분하고 **원문/IR/모델 보완 출력**을 별도 기록.
- [ ] CPU만 있는 환경과 GPU가 있는 환경에서 속도·메모리·모델 다운로드 크기 및 설치 재현성 비교.
- [ ] 파서 신뢰도 점수를 곧바로 정확도 확률로 취급하지 않고, 미검증·불일치·부분 실패 상태를 명시.
- [ ] 원문에 없는 수치·헤더·도형 관계를 생성으로 보충하지 않도록 설계. 확정되지 않은 부분은 판단 보류.

### 1.6 잠정 방향 및 후속 조사 우선순위

1. **1차 로컬·경량 경로:** pdfplumber + 사용 가능한 permissive PDF 렌더링/텍스트 추출 대안(pypdfium2 등) + 필요한 OCR을 검토. 한 도구가 표 의미까지 보장한다고 가정하지 않음.
2. **2차 구조 인식:** Docling 및 PP-StructureV3를 **동등한 교체 후보**로 비교. 표·레이아웃 출력은 공통 IR 어댑터로 분리.
3. **선택적 시각 보완:** PaddleOCR-VL 등은 복잡한 표·차트·도형 영역에 선택 적용하는 후보. 출력은 원시 추출을 덮어쓰지 않고 출처·모델 정보를 별도 보존.
4. **HWP/HWPX:** 독립된 형식별 파서 후보를 확보하되, 기능 검증과 패키지/원본 라이선스 검증 전까지 특정 도구를 기본값으로 확정하지 않음.
5. **배포 정책:** 기업의 상업적 이용에 불필요한 장애가 없도록 기본 설치에서 미확인 또는 강한 copyleft 의존성이 생기지 않는 구성 우선. 사용자는 별도 조건을 수용한 선택형 구성요소를 추가할 수 있으나 그 경우에도 배포 적법성 검토가 필요.

**결론:** 기술 선택의 합격 기준은 단일 예시 문서의 추출 정확도만이 아니라 **범용 입력 대응, 원문 근거 보존, 로컬 실행 가능성, 교체 가능성, 기업 재배포를 포함한 라이선스 적합성**이다.

### 1.7 공식 출처 색인

- [pdfplumber README / table extraction](https://github.com/jsvine/pdfplumber/blob/stable/README.md#extracting-tables) · [LICENSE](https://github.com/jsvine/pdfplumber/blob/stable/LICENSE.txt)
- [pypdfium2 라이선스·PDFium 고지](https://pypdfium2.readthedocs.io/en/stable/readme.html)
- [PyMuPDF / Artifex 라이선스](https://pymupdf.io/licensing)
- [Docling 프로젝트·라이선스](https://github.com/docling-project/docling) · [Docling 모델 목록](https://github.com/docling-project/docling/blob/main/docs/usage/model_catalog.md)
- [PP-StructureV3 공식 사용 가이드](https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/PP-StructureV3.html) · [PaddleOCR LICENSE](https://github.com/PaddlePaddle/PaddleOCR/blob/main/LICENSE)
- [PaddleOCR-VL 공식 구조 설명](https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/PaddleOCR-VL.html) · [PaddleOCR-VL-1.6 모델 카드](https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.6)
- [Tesseract 엔진·라이선스](https://github.com/tesseract-ocr/tesseract) · [tessdata 라이선스](https://github.com/tesseract-ocr/tessdata)
- [OCRmyPDF 라이선스](https://github.com/ocrmypdf/OCRmyPDF/blob/main/README.md#license) · [Ghostscript 라이선스 안내](https://ghostscript.com/about/)
- [HWP/HWPX 파서 PyPI 정보](https://pypi.org/project/hwp-hwpx-parser/) · [HWP/HWPX 로더 PyPI 정보](https://pypi.org/project/langchain-hwp-hwpx-loader/)
- [OSI 오픈소스 정의](https://opensource.org/osd) · [OSI FAQ](https://opensource.org/faq)

> **라이선스 주의:** 이 문서는 공식 공개 자료에 기반한 기술 검토 메모이며 법률 자문이 아니다. 실제 배포 전에 **선택한 정확한 릴리스와 모델 가중치, 배포 방식**을 기준으로 제3자 라이선스를 다시 검토해야 한다.


---

## 2. 하이브리드 검색 및 리랭커

> 상태: 기술 비교 레퍼런스 및 **실험 아이디어**. 제품용 Reranker 모델 미선정. 상세 흐름은 [문서 처리 파이프라인](document-pipeline.md) 참고.

### 2.1 기본 구조와 용어

| 단계 | 기술/역할 | 도입 방향 |
|---|---|---|
| 1차 검색 | Dense 임베딩 기반 검색 + BM25 어휘 검색 | 공통 ChunkSet의 동일 원문 참조 사용 |
| 후보 통합 | **RRF (Reciprocal Rank Fusion)** | 각 검색기의 순위를 기계적으로 통합. **기본값** |
| 선택적 재정렬 | 규칙 기반 / 로컬 Cross-Encoder / 그 외 로컬 모델 | RRF 후보에만 적용하는 **교체형 모듈** |
| 결과 전달 | 공통 EvidenceBundle | 기본·확장 양쪽이 동일한 근거·원문 참조 계약 사용 |

**RRF와 PRF는 다른 방법**이다. RRF는 순위 결합이고, PRF(Pseudo-Relevance Feedback)는 초기 상위 문서를 이용해 질문을 확장·수정하고 재검색하는 방법이다. PRF는 기본 검색 경로에 넣지 않으며 추후 독립 연구 후보로만 고려한다.

**RRF는 원본 점수 자체를 가중합하는 모델이 아니다.** 각 결과 목록에서의 rank를 사용한다. 가중 RRF나 점수 정규화 기반 결합은 추후 대안 연구 대상이며 기본 구조에 포함한 것은 아니다.

### 2.2 선택형 Reranker의 기술 후보

| 후보 | 용도 | 주의 사항 / 상태 |
|---|---|---|
| 규칙 기반 | 명시적으로 지정된 문서 범위·필드·메타데이터 우선순위 등 적용 | 특정 기관·평가셋 문구에 맞춘 특화 규칙 금지. 선택형 후보 |
| 로컬 Cross-Encoder | 질문과 후보 청크의 관련성을 함께 추론 | 로컬 모델 가중치의 상업적 사용/재배포 라이선스, 한글 품질, CPU/GPU 자원 검토 필요. 선택형 후보 |
| 다른 로컬 리랭킹 방식 | 향후 경량 모델 또는 구조 인지형 방법 적용 | 공통 입출력 계약 유지. 구현 미정 |
| [Voyage Reranker API](https://docs.voyageai.com/docs/reranker) | **외부 API 비교 기준선**, 로컬 모델의 성능 지향점 탐색 | 제품 기본 설치에는 **포함하지 않음**. 외부 문서 전송·요금·약관 확인 필수 |

Reranker는 RRF에서 후보에 없던 문서를 스스로 찾아내지 않는다. 고품질 리랭커를 붙여도 **초기 검색 Recall 한계**를 넘을 수 없고, 관련성 점수는 원문 사실 검증을 대체하지 못한다.

### 2.3 Voyage 비교 기준선 — 실험 아이디어

- **목표:** 같은 RRF 후보를 기준으로 **리랭킹 없음 / Voyage API / 로컬 리랭커**를 비교하여 품질·지연·비용 간의 기준선을 만든다. Voyage의 점수를 정답 데이터로 사용하거나 모델을 모방 학습한다는 의미가 아니다.
- **모델 확인:** 공식 문서에 다양한 `rerank-2.5` 계열 및 후속 모델 정보가 표시되므로, 실제 실험 시점에 **사용 가능한 특정 모델 이름과 제공 버전**을 기록한다. 현재 고정 모델 없음.
- **동일 조건:** 질문·입력 후보의 텍스트 표현과 목록·개수·원문 버전·최종 Top-k를 통제하고, RRF 기준 후보를 공통 입력으로 재사용한다.
- **품질·운영 지표:** 독립적으로 원문 확인한 관련성 평가 기준이 있을 때 nDCG@k, MRR@k, Recall@k 등을 기록. 지연시간·토큰·API 요금·오류율·로컬 메모리도 별도 수집한다.
- **기록:** query_id, candidate_set_hash, RRF 원순위, reranker_id/version, 리랭커 점수·순위, 출력 Top-k, 호출 시간·비용·데이터셋 버전.
- **데이터 보안:** API에 질의·후보 문서 텍스트가 전송되므로 **공개·합성·허가된 데이터만** 활용한다. 기밀·민감·개인정보가 포함된 실제 기업 문서는 외부 전송하지 않는다.
- **약관:** [Voyage 서비스 약관](https://www.voyageai.com/tos)의 데이터 사용 및 **opt-out** 조항을 확인해야 한다. opt-out은 전송 이후 데이터에 적용되며, 별도 설정과 결제 수단이 필요할 수 있고 무료 토큰 조건에 영향을 줄 수 있다. 현재 계정 정책은 미확인.
- **배포 조건:** 외부 API 연동은 **비필수·실험 전용**이어야 한다. 기업이 로컬·오프라인 설치만으로 기본 검색 및 선택 가능한 로컬 Reranker를 이용하는 구조를 유지한다. API 서비스 계약과 코드/가중치의 오픈소스 라이선스는 구별한다.

### 2.4 참고 자료 및 검토 필요 항목

- [Elasticsearch RRF 설명 및 공식 계산식](https://www.elastic.co/docs/reference/elasticsearch/rest-apis/reciprocal-rank-fusion)
- [Qdrant Hybrid / Multi-stage query](https://qdrant.tech/documentation/search/hybrid-queries/)
- [Voyage Reranker 가이드](https://docs.voyageai.com/docs/reranker)
- [Voyage Reranker REST API](https://docs.voyageai.com/reference/reranker-api)
- [Voyage 사용량 기반 요금표](https://docs.voyageai.com/docs/pricing)
- [Voyage 서비스 약관](https://www.voyageai.com/tos)
- [Pseudo Relevance Feedback 관련 연구](https://doi.org/10.1145/3570724)

**추가 확인 필요:** 실제 채택할 로컬 모델의 정확한 라이선스·모델 가중치, Voyage API 계정의 데이터 정책/비용, 한국어 및 표 문맥 기반 검색 품질, 최종 Top-k와 후보 풀 크기에 따른 지연·정확도 절충. **어느 후보도 최종 채택 또는 성능 검증된 상태가 아니다.**
