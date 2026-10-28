# baseline-1 레퍼런스 색인

baseline-1은 v23(tag `v23`, commit `64ac263b19143fcbb9ea981f1c3b169dd0c056c1`)의 동작을 동결한 참조점이다. 원본 빌더·생성 파이프라인·제출 노트북을 유지하면서 복사본으로 파서와 문서를 분리했다. 실무 이식에는 **범용판 `docparse_generic`**을 사용한다.

| 산출물 | 용도 |
|---|---|
| [PARSER](baseline1/PARSER.md) | HWP/PDF 파싱·청킹·표 요약·이식 안내와 실제 스냅샷 예시 |
| [INTERFACE](baseline1/INTERFACE.md) | 색인·검색에 연결하는 파서 출력 필드와 위치 의미 |
| [ARCHITECTURE](baseline1/ARCHITECTURE.md) | 전체 RAG 흐름, 담당 함수, 시간 예산과 실행 구조 |
| [CONFIG](baseline1/CONFIG.md) | 파싱·검색·라우팅·답변 설정과 문서 특화 여부 |
| [EVAL](baseline1/EVAL.md) | 평가 러너·채점·시간 점수·저장된 baseline 수치 |
| [HISTORY](baseline1/HISTORY.md) | v1~v23 변경·실험·정정 사항 |
| [KNOWN_ISSUES](baseline1/KNOWN_ISSUES.md) | 표 오독·검색·조건 누락·검증 범위의 한계 |
| [VALIDATION](baseline1/VALIDATION.md) | 이번 작업의 검증 결과와 해시, 변경 요약 |
| [동결판](baseline1/docparse_b1/CHANGES.md) | v23과 바이트 단위 출력이 같은 파싱 패키지 및 원본 대비 변경 기록 |
| [범용판](baseline1/docparse_generic/README.md) | 폴더 단위 이식 가능한 설정·프로필 기반 패키지 |
| [HARDCODED](baseline1/docparse_generic/HARDCODED.md) | 동결판 하드코딩 전수 조사와 범용판 처리 방식 |
| [프로필 비교](baseline1/docparse_generic/PROFILE_DIFF.md) | 같은 원문의 문서군 프로필과 중립 설정 출력 차이 |
| [범용판 변경 기록](baseline1/docparse_generic/CHANGES.md) | 동결판 대비 설정 주입·위치 메타데이터·입력 처리 변경 |
| [스냅샷 manifest](baseline1/snapshots/manifest.json) | 원문·출력 SHA-256, lock 패키지 버전, 문서별·종류별 청크 수 |
| [metrics](baseline1/metrics/README.md) | 기준 전체 run과 sample 반복 3회의 summary/env 복사본 및 상세 로그 해시 |
| [v23 보존본](../legacy/build_notebook_v23.py) | 원본 빌더의 바이트 동일 복사본. 실행용 새 빌더가 아니라 구조 참조용 |
| [BACKLOG](../BACKLOG.md) | B1~B8 후속 작업과 선행 조건 |
| [작업계획서](../prompts/legacy/baseline1_레퍼런스_작업계획서.md) | 이 동결 작업의 범위·검증·중단 조건 |

## API 없는 재현

저장소 루트에서 실행한다. 키를 읽는 `.env`·Colab 키 셀은 스냅샷과 파서에서 실행하지 않는다.

```powershell
uv sync
$env:GACHON_DATA_DIR = "$PWD/data/dataset"
$env:OPENAI_API_KEY = $null
$env:VOYAGEAI_API_KEY = $null
$env:VOYAGE_API_KEY = $null
uv run python scripts/snapshot_parse.py --data-dir $env:GACHON_DATA_DIR
uv run python -m reference.baseline1.docparse_b1 $env:GACHON_DATA_DIR --out runs/baseline1_frozen
uv run python -m reference.baseline1.docparse_generic $env:GACHON_DATA_DIR --profile gachon_2027 --out reference/baseline1/snapshots/generic_gachon_2027
uv run python -m reference.baseline1.docparse_generic $env:GACHON_DATA_DIR --out reference/baseline1/snapshots/generic_neutral
uv run pytest -q
uv run python scripts/check_reference.py
```

기준 문맥 청크는 513개다. 동결판은 스냅샷 3종의 JSONL·manifest 전체가 같아야 하며, 범용판 문서군 프로필은 `locator`를 제외한 모든 텍스트·메타데이터가 같아야 한다. 중립 기본값은 설정이 달라 색인 텍스트 차이가 허용된다. jsonl은 원문을 포함해 Git에서 제외한다. 데이터 경로나 스냅샷이 없으면 데이터 의존 테스트는 skip하므로 해당 출력을 확인한다.

## 전체 RAG 평가 재현

이 명령은 API 키와 실제 API 호출이 필요한 별도 평가다. 이번 참조 패키지 작업에서는 실행하지 않았다. 키 로딩과 데이터 경로 준비는 [README_LOCAL](../README_LOCAL.md)에 따른다.

```powershell
uv run python scripts/run_eval.py --version v23 --sets sample3,hard20,holdout10,drive20 --repeat 1
uv run python scripts/run_eval.py --version v23 --sets sample3 --repeat 3
```

기존 수치는 저장된 파일만 사용했다. 파서 개선, F2 수정, VLM 비교와 중립 설정의 RAG 성능 평가는 [백로그](../BACKLOG.md)에 남긴다.
