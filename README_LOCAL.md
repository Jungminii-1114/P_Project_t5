# 로컬 실행 및 평가

## 환경 준비

Python 3.13과 `uv`가 설치된 환경에서 프로젝트 폴더로 이동한 뒤 의존성을 동기화합니다.

```powershell
uv sync
```

API 키는 Windows 사용자 환경변수로 둘 수 있습니다. 또는 `.env.example`을 `.env`로 복사해 키와 설정을 입력합니다. 이미 지정한 환경변수 값은 `.env` 값보다 우선합니다. 최소한 `OPENAI_API_KEY`가 필요하고, `VOYAGEAI_API_KEY`가 없으면 파이프라인이 설정한 임베딩 대체 경로를 사용합니다. 키 값은 노트북이나 평가 로그에 저장하지 마세요.

```powershell
Copy-Item .env.example .env
```

입학 안내 원본 문서 5개를 `data/dataset/`에 둡니다. `GACHON_DATA_DIR`을 설정하면 다른 위치를 사용할 수 있습니다. 공식 샘플 질문 파일은 `data/sample.json`에 두거나 `GACHON_SAMPLE_PATH` 환경변수 또는 `--sample-path`로 경로를 지정합니다.

`.env`를 사용하지 않을 때는 다음처럼 데이터 경로를 명시합니다. 지정하지 않으면 노트북의 기존 Colab 탐색(`/content/dataset`)을 사용합니다.

```powershell
$env:GACHON_DATA_DIR = "$PWD/data/dataset"
```

환경변수를 등록하기 전에 시작한 PowerShell에서는 새 창을 열거나 현재 프로세스에 사용자 환경변수를 읽습니다. 값은 출력하지 않습니다.

```powershell
$env:OPENAI_API_KEY = [Environment]::GetEnvironmentVariable('OPENAI_API_KEY', 'User')
$env:VOYAGEAI_API_KEY = [Environment]::GetEnvironmentVariable('VOYAGEAI_API_KEY', 'User')
```

`build_notebook.py`가 v23의 단일 원본입니다. 다음 명령은 Colab용 노트북과 로컬 `pipeline_v23.py`를 함께 생성합니다. 생성된 모듈은 직접 수정하지 않습니다. 노트북 설치 셀의 런타임 의존성 버전은 `uv.lock`에서 읽습니다.

```powershell
uv run python build_notebook.py
uv run python legacy/build_notebook_v22.py
uv run python -c "import pipeline_v23; print(pipeline_v23.ask('입학 지원 절차를 안내해 주세요.'))"
```

v22 빌더는 보존용 노트북을 `legacy/`에, 로컬 모듈은 루트 `pipeline_v22.py`에 생성합니다. v22 코드 셀의 변경은 키 로딩·데이터 경로 shim으로 한정했습니다.

## 테스트

```powershell
uv run pytest
uv run python scripts/check_notebook.py
uv run python scripts/clean_notebook.py --capture-stdout
```

`check_notebook.py`는 키·문법·출력·정답값을 검사하고, gold와 동일한 8자 조각도 모두 보고합니다. 문서명·일반 표현 및 계획서가 요구한 유보 문구까지 잡으므로 현재 결과는 실패입니다. 이 충돌은 `eval/notebook_overlap_audit.json`과 보고서에 기록했습니다. `clean_notebook.py`는 새 Python 프로세스에서 데모를 포함한 13개 코드 셀을 실행하므로 실제 API를 호출합니다. `%pip`는 이미 `uv sync`한 환경을 사용하는 확인 문구로 대체하며, 제출 노트북에는 출력을 저장하지 않습니다.

## 평가

```powershell
uv run python scripts/run_eval.py --version v23 --sets sample3,hard20,holdout10,drive20 --repeat 1
uv run python scripts/run_eval.py --version v22 --sets sample3,hard20,holdout10,drive20 --repeat 1
uv run python scripts/run_eval.py --version v23 --sets sample3 --repeat 3
```

`--version`은 `v22` 또는 `v23`입니다. 세트는 `sample3`, `hard20`, `holdout10`, `drive20` 중 쉼표로 구분해 고릅니다. 각 반복은 파이프라인 모듈을 새로 불러와 색인을 준비하며, 색인 구축 시간은 문항 응답시간에 포함하지 않습니다. `--repeat 3`은 세 번의 별도 실행 폴더를 만듭니다.

결과는 `runs/<timestamp>_<version>/`에 저장합니다.

- `results.jsonl`: 문항별 질문, 정답, 예측 전문, 판정과 이유, 응답·단계별 시간, 검색 경로, 근거 및 heuristic score
- `summary.json`: 세트별 정확도, 평균·최대 응답시간, 5·10·19초 초과 문항 수, 시간 점수 합계
- `env.json`: Python·패키지 버전, 문서 manifest, 모델명

각 문항의 오류는 실패 행으로 기록한 뒤 다음 문항으로 진행합니다. 로그에는 API 키를 기록하지 않습니다.

평가 폴더가 준비되면 저장된 로그만으로 비교 보고서를 생성할 수 있습니다. 아래 폴더 이름은 이번 실행의 실제 산출물이며 재실행 시 새 폴더로 바꿉니다.

```powershell
uv run python scripts/compare_eval.py --v22 runs/20261028_122601_013520_v22 --v23 runs/20261028_123828_709846_v23 --samples runs/20261028_124701_995010_v23 --samples runs/20261028_124757_442570_v23 --samples runs/20261028_124851_799805_v23 --clean runs/20261028_123656_053985_clean/clean.json
```

비교 도구는 정확도 하락을 두 버전의 정답 수 차이로 계산하고, 상쇄될 수 있는 개별 정답→오답 회귀도 따로 기록합니다. API-free F2 교정 trace는 `eval/f2_repair_trace.json`에서 읽습니다.

`heuristic_score`는 규칙 기반 검사 점수입니다. 정답 가능성을 추정하는 값으로 해석하지 않습니다. 시간 점수는 정답 문항에만 적용하며 5초까지 0.4점, 이후 초당 0.08점 감점, 10초부터 0점입니다. 원 질문이 유실된 orig20은 평가하지 않습니다.

`runs/`, `.venv/`, `.env`, `data/`는 Git에서 제외됩니다. 대표 v23 실행의 상세 결과는 `eval/runs_v23_results.jsonl`, 집계·비교는 `eval/results_v23.json`에 보존합니다. 사용 완료 계획서는 `prompts/legacy/v23_작업계획서.md`에 둡니다.

## baseline-2 / v24

v23 빌더와 제출 노트북은 동결 상태다. 새 `build_pipeline_v24.py`는 로컬 `pipeline_v24.py`만 생성한다.
파서는 설치 패키지 `src/docparse/`를 사용한다.

```powershell
uv sync
uv run python build_pipeline_v24.py
uv run python -m docparse data/dataset --profile gachon_2027 --extract-table-ir --out runs/baseline2/ir
uv run python -m scripts.diagnose_tables
uv run python -m scripts.check_table_golden --strict
uv run python -m scripts.diagnose_bm25
```

위 파싱·진단은 API를 호출하지 않는다. 엄격 골든 검사는 현재 실패를 그대로 반환하며, 테스트 통과와
골든 정확도는 별개다. `uv run python -m scripts.verify_stage1`은 키를 제거하고 소켓을 차단한 별도
프로세스에서 전체 재현을 실행한다.

v24 평가도 기존 러너로 실행한다. 이 명령은 임베딩·답변·채점 API를 사용한다.

```powershell
$env:DOCPARSE_PROFILE = 'gachon_2027'
$env:DOCPARSE_INDEX_RENDER = 'baseline1'
$env:DOCPARSE_LLM_RENDER = 'baseline1'
uv run python scripts/run_eval.py --version v24 --variant V0 --sets sample3,hard20,holdout10,drive20
```

색인은 `baseline1/header_records`, LLM 근거는 `baseline1/html_full/header_records` 중 고른다.
`--variant`와 유효 설정은 run 이름·env.json·summary.json에 남는다. 임베딩 캐시는 `runs/cache/`에 있다.
기존 페이지 색인은 LLM raw를 사용하므로 형식 변경이 페이지 검색에도 영향을 주는 한계가 있다.

결과·구조 한계는 [STAGE1](reference/baseline2/STAGE1.md), [EVAL](reference/baseline2/EVAL.md),
이식 지침은 [HANDOFF](reference/baseline2/HANDOFF.md)를 참고한다.
