# baseline-2 마무리 및 GitHub 게시 작업계획서

## 0. 목표와 범위

이 저장소(`C:\dev\middle_test`)의 baseline-2를 마무리하고, baseline-1과 같은 방식으로 팀 저장소에 게시한다. 이 작업으로 이 프로젝트를 종료한다.

1. `pipeline_v24.py`의 렌더러 기본값을 `baseline1/baseline1`로 되돌리고, 그 이유를 문서에 반영한다.
2. V0~V4, 동률 재평가, 선정 후 확인 실행의 문항별 결과를 `eval/`에 보존한다.
3. 팀 저장소 `reportanchor`의 `JS` 브랜치에서 `references/gachon-admissions/`를 갱신하는 병합 커밋을 만들고, 사용자 확인 후 push한다.

**하지 않는 것**
- 파서·검색·검증·프롬프트·모델·마감 로직 변경. 바꾸는 코드는 기본값 두 줄과, 그에 맞춘 테스트·감사 스크립트뿐이다.
- API 호출과 재평가. 새 RAG 실행은 하지 않는다.
- 평가셋 gold 수정. holdout10 #6은 기록만 한다.
- 동결 대상 수정: `reference/baseline1/`, `legacy/`, `build_notebook.py`, `pipeline_v23.py`, 제출 노트북.
- 원문 문서, 원문 페이지 PNG, `runs/cache/`, 임베딩·Chroma 산출물 커밋.
- 팀 저장소의 `master`·`JM`·`NW`·`SY` 브랜치 수정, force push, 로컬 `master`를 원격에 push.
- `JS` 브랜치의 기존 파일(`temp_docs/chatgpt-connection-test.md` 포함) 수정이나 삭제.

**보안**: API 키 값은 출력·기록·커밋하지 않는다. 존재 여부와 길이만 확인한다.

## 1. 현재 상태 (계획서 작성 시점에 확인)

| 항목 | 값 |
|---|---|
| 로컬 브랜치 | `master` = `6bf6701`, 작업 트리 깨끗함 |
| 로컬 태그 | `v24`(1단계), `baseline-2`(annotated, `6bf6701`). 둘 다 원격에 없음 |
| 기본값 변경 위치 | `pipeline_v24.py:171-172`. `6bf6701`에서 `baseline1` → `header_records`로 바뀜 |
| 기본값을 가정하는 테스트 | `tests/test_pipeline_v24.py` 89·112·119행 부근 |
| 원격 | `reportanchor` = `https://github.com/Jungminii-1114/ReportAnchor.git` |
| 원격 `JS` | `d9fb9b3`(사용자의 연결 테스트 커밋). 그 부모가 baseline-1 병합 커밋 `04dd90b` |
| 원격 태그 | `v22`, `v23`, `baseline-1` |
| baseline-1 게시 방식 | `04dd90b`의 부모는 `e1d34e9`(팀 JS)과 `3fbba3f`(baseline-1). `04dd90b:references/gachon-admissions`의 tree가 `3fbba3f^{tree}`와 정확히 같음 (`e64c306…`) |
| 결과 보존 선례 | `eval/runs_v23_results.jsonl`(대표 v23 실행 53행). `runs/`는 gitignore |
| v24 실행 폴더 | `runs/*_v24_*` 16개: V0~V4 각 1개, `V3_tie_sample` 3, `V3_tie_drive` 1, `V0_tie_sample` 3, `V0_tie_drive` 1, `V3_selected_sample` 3. 각 폴더에 `env.json`, `results.jsonl`, `summary.json` |

## 2. 단계

### 단계 1 — 사전 확인

- `git status`가 깨끗하고 HEAD가 `6bf6701`인지 확인한다. 이 계획서 파일만 미추적 상태로 있는 것은 허용하며, 단계 4 커밋에 포함한다.
- `git fetch reportanchor` 후 `reportanchor/JS`가 여전히 `d9fb9b3`인지 확인한다. 다르면 새 커밋 목록을 보고하고 **멈춘다**.
- `git ls-remote --tags reportanchor`에 `v24`·`baseline-2`가 없는지 확인한다. 있으면 **멈춘다**.

### 단계 2 — 기본값 되돌리기

- `pipeline_v24.py:171-172`의 기본값을 `"baseline1"`로 되돌린다. 다른 줄은 바꾸지 않는다.
- `git diff 6129446 -- pipeline_v24.py`가 비어 있는지 확인한다. `6129446`은 평가에 쓴 코드이며, 그 시점 기본값은 `baseline1`이었다. 비어 있지 않으면 차이를 보고하고 멈춘다.
- `tests/test_pipeline_v24.py`에서 기본값을 `header_records`로 가정하는 부분이 있으면 `baseline1`에 맞춘다. 환경변수로 `header_records`를 지정하는 검사는 유지한다.
- `src/docparse`의 `ParserConfig` 기본값은 이미 `baseline1`이므로 건드리지 않는다.

### 단계 3 — 문항별 실험 결과 보존

- `eval/runs_v24/<run 폴더명>/`에 16개 실행의 `results.jsonl`, `summary.json`, `env.json`을 복사한다. 내용은 바꾸지 않는다.
- `eval/runs_v24/MANIFEST.md`를 만든다. 실행마다 아래를 적는다.
  - 변형, 용도(기본 비교 / 동률 재평가 / 선정 후 확인), 세트, 정답 수
  - `results.jsonl`의 SHA-256
- 복사본의 SHA-256이 `reference/baseline2/metrics/rag_comparison.json`, `repeat_comparison.json`, `selection.json`에 기록된 값과 같은지 대조한다. 기록이 없는 실행은 "기록 없음"으로 표시한다. 다른 값이 있으면 **멈춘다**.
- 복사 전에 `env.json`과 `results.jsonl`에서 비밀값을 검사한다. 대상은 `sk-` 접두어, `pa-` 접두어, 그리고 환경변수 키 값과 일치하는 문자열이며, 키 값은 메모리에서만 비교한다. 하나라도 있으면 **멈춘다**.
- 정적 유출 감사(`scripts/check_baseline2.py` 등)가 새 결과 파일을 질문 유출로 판정하면, 허용 경로에 `eval/runs_v24/`만 명시적으로 추가한다. 근거는 `eval/`이 선례상 테스트 데이터 경로(`eval/testset_*.json`, `eval/runs_v23_results.jsonl`)라는 점이다.
  - 코드·문서 경로의 유출 검사는 약화하지 않는다.
  - 허용 경로가 그 밖의 경로에는 적용되지 않음을 확인하는 테스트를 추가한다.

### 단계 4 — 문서 갱신

`reference/baseline2/`의 기존 결과 기록은 지우지 않는다. 아래 내용을 추가한다.

- **EVAL.md**: "최종 기본값" 절을 추가한다.
  - V3는 계획서 규칙에 따라 선정됐다.
  - 같은 설정의 V0가 drive20에서 11/20 → 8/20으로 3문항 변동했다. 재평가에서 V3가 앞선 폭이 이 변동 폭과 같으므로 V3가 낫다는 근거로 보지 않는다.
  - 그래서 실행 기본값을 `baseline1`로 되돌렸다. V3는 환경변수로 재현한다.
  - holdout10 #6을 원문 기준으로 다시 센 참고 집계를 넣는다: V0 41, V1 39, V2 39, V3 41, V4 36 (/53). 공식 점수는 바꾸지 않았다고 명시한다. 이 숫자는 저장된 판정에서 직접 다시 계산해 확인하고, 다르면 계산한 값을 쓰고 차이를 보고한다.
- **HANDOFF.md**
  - 최종 기본값 문단을 위 내용으로 고친다.
  - "데이터 계약 교훈"을 2~4줄 추가한다. 한 청크의 `raw`가 LLM 입력, 페이지 색인, 근거 검증에 함께 쓰여 V1·V2·V4에서 색인과 LLM 렌더러가 분리되지 않았다. 실무에서는 색인용, LLM용, 검증용 텍스트 필드를 계약에서 나눈다. `PAGE_INDEX_PROPOSAL.diff`를 링크한다.
- **VALIDATION.md**: 기본값 복귀, 단계 3의 결과 보존과 해시 대조, 최종 pytest 결과를 행으로 추가한다.
- **BACKLOG.md**: B1 설명에 "기본값은 baseline1, 렌더러 우열 미확인"을 덧붙인다.
- **README_LOCAL.md**: 결과 보존 문장에 `eval/runs_v24/`를 추가한다.
- **REPORT_중간평가_진행상황.md**: 마지막 세션 절에 기본값 복귀와 게시를 짧게 추가한다.
- 이 계획서를 `prompts/legacy/baseline2_마무리_작업계획서.md`로 옮긴다.

### 단계 5 — 검증과 로컬 커밋

- `uv run pytest -q`를 실행한다. API 키 3종(`OPENAI_API_KEY`, `VOYAGEAI_API_KEY`, `VOYAGE_API_KEY`)을 제거한 환경에서 실행하고, `GACHON_DATA_DIR`이 있으면 지정해 데이터 의존 테스트까지 돌린다. 실패가 있으면 멈춘다.
- `uv run python -m scripts.check_table_golden --strict`의 종료 코드가 기존과 같이 1인지 확인한다. 기대값을 고치지 않는다.
- 동결 대상의 `git diff baseline-1 HEAD`가 비어 있어야 한다. 대상: `reference/baseline1/`, `legacy/`, `build_notebook.py`, `pipeline_v23.py`, 제출 노트북.
- 정적 유출·비밀값 감사가 통과해야 한다.
- 커밋한다: `chore: restore baseline1 renderer default and preserve v24 run results`.
- 태그를 정리한다.
  - `baseline-2`를 이 커밋으로 옮긴다. annotated tag로 만들고, 메시지에 "평가 코드 = 6129446, 기본값만 복귀"를 적는다. 원격에 없음을 단계 1에서 확인한 경우에만 옮긴다.
  - `v24`는 그대로 둔다.

### 단계 6 — 게시 브랜치 준비 (로컬)

- `reportanchor/JS`에서 `publish/baseline2-reference` 브랜치를 만든다.
- 로컬 `master`를 병합하되, 변경이 `references/gachon-admissions/` 아래에만 들어가게 한다.
  - 권장: `git merge --no-ff -s recursive -X subtree=references/gachon-admissions master`
  - 병합 기준점은 `3fbba3f`이다.
- 병합 커밋 메시지는 `04dd90b` 형식을 따른다.
  ```
  docs: import baseline-2 table IR and renderer reference

  Preserve the complete source snapshot under references/gachon-admissions.
  Source: <최종 커밋 해시> (baseline-2), stage-1 v24 <v24 해시>.
  Validation: <pytest 결과>; strict golden 2/11 preserved as a known failure.
  ```
- **필수 검사**: `git rev-parse HEAD:references/gachon-admissions`가 `git rev-parse master^{tree}`와 같아야 한다. 다르면 병합을 취소하고 대체 방법을 쓴 뒤 다시 검사한다.
  - 대체 방법: `-s ours --no-commit`로 병합한 뒤 해당 경로를 `git rm -r`하고, `git read-tree --prefix=references/gachon-admissions/ -u master`로 채운다.
- `git diff reportanchor/JS HEAD --stat -- . ':!references/gachon-admissions'`가 비어 있어야 한다. 폴더 밖의 파일은 바뀌면 안 된다.
- 별도 커밋으로 `references/README.md`에 "Gachon admissions — baseline-2" 절을 추가한다.
  - 기존 baseline-1 절은 유지한다.
  - 링크: `reference/baseline2/HANDOFF.md`, `EVAL.md`, `VALIDATION.md`, `IR.md`, `RENDERERS.md`, `GOLDEN.md`, `eval/runs_v24/MANIFEST.md`.
  - 한 줄 요약: 표 IR과 렌더러 3종 비교. 엄격 골든은 2/11. 렌더러 우열은 확인되지 않았고 기본값은 baseline1이다.
  - 커밋 메시지: `docs: link baseline-2 reference`.
- 이 커밋 뒤에도 subtree tree 검사가 같아야 한다.

### 단계 7 — push 전 사용자 확인 (멈춤)

push하기 전에 아래 내용을 보고하고, 사용자가 명시적으로 승인할 때까지 **기다린다**.

- `reportanchor/JS..publish/baseline2-reference`의 커밋 목록. 병합으로 함께 올라갈 로컬 커밋 `2e2375b`…최종 커밋도 포함한다.
- `references/gachon-admissions/` 밖 변경이 `references/README.md` 하나뿐이라는 확인
- subtree tree 해시가 일치한다는 확인
- 새로 올라가는 파일 수와 총 크기, 1MB가 넘는 파일 목록
- 비밀값·유출 감사 결과
- 실행할 명령:
  ```
  git push reportanchor publish/baseline2-reference:JS
  git push reportanchor v24 baseline-2
  ```

### 단계 8 — push와 확인 (승인 후)

- 위 두 명령만 실행한다. `--force`는 쓰지 않는다. fast-forward가 아니라서 거부되면 원격을 다시 fetch하고 보고한 뒤 멈춘다.
- `git ls-remote reportanchor`로 `JS`, `v24`, `baseline-2`가 기대 해시와 같은지 확인한다.

## 3. 보고 형식

1. 단계별 결과(완료 / 멈춤과 이유)
2. 기본값 diff, 그리고 `6129446` 대비 diff가 비어 있다는 확인
3. `eval/runs_v24/` 실행 16개의 해시 대조표
4. 다시 센 참고 집계
5. pytest 결과와 엄격 골든 종료 코드
6. 게시 브랜치 검사 결과(tree 해시, 폴더 밖 diff)
7. push 결과와 `ls-remote` 해시. push 전이면 단계 7의 확인 요청 내용

## 4. 멈춤 조건

- 원격 `JS`가 `d9fb9b3`가 아니거나, 원격에 `v24`·`baseline-2` 태그가 이미 있다.
- 기본값을 되돌린 뒤 `pipeline_v24.py`가 `6129446`과 다르다.
- 결과 파일 해시가 metrics 기록과 다르거나, 비밀값이 발견됐다.
- pytest가 실패하거나, 동결 대상 diff가 비어 있지 않다.
- subtree tree 해시가 일치하지 않거나, 폴더 밖 파일이 바뀐다.
- push 전 사용자 승인이 없거나, push가 거부됐다.
