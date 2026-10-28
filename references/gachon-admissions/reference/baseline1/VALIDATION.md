# baseline-1 작업 검증 기록

2026-10-28(Asia/Seoul)에 v23(`64ac263b19143fcbb9ea981f1c3b169dd0c056c1`)을 기준으로 수행했다. 시작 시 HEAD는 tag `v23`이었으며, 사용자가 전달한 작업계획서만 미추적 상태였다. `uv sync` 성공 후 기존 테스트는 32개 모두 통과했다.

## 검증 7항목

| 번호 | 항목 | 결과·증거 |
|---|---|---|
| 1 | 전체 테스트 | **통과: 41 passed, skip 0**, 62.03초. `GACHON_DATA_DIR`을 실제 원문 폴더로 설정하고 `uv run pytest -q` 실행. 기존 32개 + 동결판 2개 + 범용판 7개 |
| 2 | 키 없는 스냅샷·CLI 및 동일성 | **통과**. 섹션 0과 5 이후를 실행하지 않고 원본 §1~4만 실행. `OPENAI_API_KEY`, `VOYAGEAI_API_KEY` 제거 환경에서 스냅샷과 동결 CLI 실행. 두 번 만든 JSONL·manifest가 같고 동결 CLI도 모두 동일. 범용 CLI 테스트는 세 키(`VOYAGE_API_KEY` 포함)를 제거하고 socket 연결도 차단 |
| 3 | 키·비밀값 검사 | **통과: 0건**. `scripts/check_notebook.py`의 `SECRET_PATTERNS`를 재사용한 [감사 스크립트](../../scripts/check_reference.py)로 새 reference·백로그·스크립트·테스트 검사 |
| 4 | 평가셋 문장 유출 검사 | **통과: 0건**. hard/holdout/drive와 공식 sample3의 전체 q/question/gold를 공백 정규화해 검사. 기존 8자 부분문자열 검사를 적용한 결과와는 다른 범위이며, 문항 ID와 원문 표의 짧은 발췌는 허용 |
| 5 | 원본 동작 불변 | **통과**. `git diff v23 -- build_notebook.py pipeline_v23.py "202235052_박진성.ipynb"`가 비어 있음. 보존본과 원본 빌더의 SHA-256 일치. 동결판의 이식한 원본 함수 18개 AST도 모두 같음 |
| 6 | 범용판 | **통과**. 프로필의 513개 문맥 청크 전체가 locator 제외 시 동일. 특화 문자열·금지 의존성 검사, 중립 5개 문서, PyMuPDF 생성 임의 PDF, 별도 임시 위치에 폴더만 복사한 import·CLI 성공. 복사 테스트에는 원본 패키지 경로를 제공하지 않음 |
| 7 | 문서 링크·줄 번호 | **통과**. 로컬 링크 대상과 보존본의 함수·상수 위치를 열어 확인. 평가 run의 summary/env 복사본 8개는 원본과 바이트 동일. JSONL 9개의 실제 해시가 각 manifest와 일치 |

최종 정적 감사 상세는 [audit.json](audit.json)에 있다. 원문·상세 실행 로그는 Git에서 제외한다. Jupyter/Colab 실행과 새 RAG 평가는 이번 검증에 포함하지 않았으며 [B4/B7](../../BACKLOG.md)에 남겼다.

## 스냅샷 동일성

| 파일 | 레코드 수 | SHA-256 |
|---|---:|---|
| `raw_docs.jsonl` | 382 | `986ffdac46478303aea026864675faafdcbdf2458a352b58a918e9ba589540a2` |
| `chunks.jsonl` | 513 | `bc021007e619188cfe0b59c5e59629c6f8f0a582f6d2818c5bc1a9c4b18c8a60` |
| `contextual_chunks.jsonl` | 513 | `d267c399a38f009325930cf5d29080fc9547f33041057cb4196df1432b858922` |

출처는 [manifest](snapshots/manifest.json)다. 동결판은 이 세 파일을 바이트 단위로 재현한다. 범용판은 locator가 추가되므로 원본과 JSONL 해시가 다르며, locator를 제거하면 전체 요소·청크·문맥 청크의 텍스트와 기존 메타데이터가 일치한다.

## 변경과 조사 요약

동결판은 import를 정리하고 전역 청크 루프를 `chunk_documents`로 감싸며 로컬 입력·실행·직렬화 진입점을 추가했다. Colab 탐색은 제외했고 기존 원본 함수 본문은 변경하지 않았다. [동결판 CHANGES](docparse_b1/CHANGES.md)에 함수별 이유가 있다.

범용판은 독립적으로 복사한 알고리즘에 `ParserConfig` 38개 필드를 주입했다. 고정 파일명·제목·도메인 표 규칙은 프로필로 옮겼고, 중립 설정은 기존 대체 분기를 사용한다. HWP/PDF 위치 의미를 locator로 추가하고 입력 파일·폴더·glob과 JSON 프로필을 지원한다. [범용판 CHANGES](docparse_generic/CHANGES.md)를 참조한다.

[HARDCODED](docparse_generic/HARDCODED.md)는 40개 규칙 묶음을 기록한다: 문서 특화 2, 입시 도메인 5, 한국어 2, 튜닝값 8, 환경 5, 형식·구조 18. 초기 목록에 없던 주요 세부는 행당 6쌍·표제 30자 제한, HWP 구조 마커와 IMAGE 처리, ※ 행 필터, JSONL 직렬화 계약과 1 MiB 해시 읽기 단위다.

[PROFILE_DIFF](docparse_generic/PROFILE_DIFF.md)의 두 설정은 모두 513개 청크·235개 표 청크를 만든다. 행 요약이 있는 표는 프로필 61개, 중립 63개이며 표제는 둘 다 235개다. 행 요약 46개와 표제 81개가 달랐고 문서 제목 5개는 같았다. 이 비교는 정확도 평가가 아니다.

## 새 파일과 용도

문서별 색인은 [reference/README](../README.md)에 있다. 코드 산출물은 다음과 같다.

| 파일 | 용도 |
|---|---|
| `legacy/build_notebook_v23.py` | v23 원본 빌더의 바이트 동일 보존본 |
| `scripts/snapshot_parse.py` | 마크다운 섹션 경계로 원본 §1~4를 선택하고 기준 스냅샷 생성 |
| `scripts/check_reference.py` | 기존 비밀값 패턴과 평가셋 전체 문장 유출 검사 |
| `tests/test_reference_parity.py` | 동결 CLI와 전체 스냅샷 동일성·금지 import 검사 |
| `tests/test_reference_generic.py` | 범용 프로필·중립·임의 PDF·독립 복사·입력·의존성·문자열 검사 |
| `docparse_b1/__init__.py`, `__main__.py` | 동결 API와 CLI |
| `docparse_b1/sources.py`, `constants.py` | 고정 입력·manifest와 문서군 상수 |
| `docparse_b1/text.py`, `hwp.py`, `pdf.py` | v23 정규화와 형식별 파싱 |
| `docparse_b1/chunk.py`, `table.py`, `context.py` | v23 청킹·표 요약·색인 문맥 구성 |
| `docparse_generic/__init__.py`, `__main__.py` | 범용 API와 CLI |
| `docparse_generic/config.py`, `profiles/__init__.py`, `profiles/gachon_2027.py` | 중립 설정·프로필 로딩과 문서군 재현 프로필 |
| `docparse_generic/sources.py`, `serialization.py` | 일반 로컬 입력·원문 manifest와 독립 JSONL/manifest 저장 |
| `docparse_generic/text.py`, `hwp.py`, `pdf.py` | 설정을 주입하는 형식별 파싱 및 locator 추가 |
| `docparse_generic/chunk.py`, `table.py`, `context.py` | 설정을 주입하는 청킹·기존 표 요약 분기·문맥 구성 |
| `snapshots/manifest.json`, `snapshots/generic_*/manifest.json` | 세 실행 구성의 입력·설정·개수·출력 해시 |
| `metrics/<run>/summary.json`, `env.json` | 기준 run 1개·반복 3개의 저장 수치·환경 보존 |
| `BACKLOG.md` | B1~B8 후속 작업 등록 |
| `prompts/legacy/baseline1_레퍼런스_작업계획서.md` | 완료한 작업계획서 보관 |

`.gitignore`에는 `reference/baseline1/snapshots/**/*.jsonl`을 추가했고, 진행 보고서에 Session 6을 추가했다. 이 변경을 담은 커밋에는 `baseline-1` 태그를 부여하며 기존 `v23` 태그는 유지한다. 커밋 해시는 작업 종료 메시지와 `git rev-parse baseline-1`로 확인한다.
