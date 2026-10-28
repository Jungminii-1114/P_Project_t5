# baseline-2 최종 검증

실험과 인계를 완료했다. 아래 실패·미검토 항목을 포함하므로 모든 수용 검사를 통과했다는 뜻은 아니다.

| 검증 항목 | 결과 | 저장 근거 |
|---|---|---|
| baseline-1 출력 동일성 | 통과: raw 382, chunks/contextual 513; locator 제외 바이트 동일 | 패키지 동일성 테스트, baseline-1 manifest |
| API 없는 파싱·구조·BM25 | 통과: 키 3종 제거 및 소켓 차단 | metrics/api_free.json |
| 전체 pytest | 최종 API-free 환경 68개 통과, 생략 0개 | runs/baseline2/pytest_final.xml |
| 원문 엄격 골든 | **실패**: 표 2/11, 셀 삼중항 11/60, 값만 37/60 | metrics/golden.json, GOLDEN.md |
| V0 재현 게이트 | 통과: 기준 대비 세트별 ±2 이내, 최대 15.26초 | metrics/v0_gate.json |
| V0~V4 평가·동률 재평가 | 완료: 기본 265문항 + 동률 58문항 | metrics/rag_comparison.json, metrics/repeat_comparison.json |
| V3 선정 후 기본 설정 확인 | 통과: 새 sample3 ×3 모두 3/3, 최대 4.16초 | metrics/selection.json, metrics/repeats/ |
| 모든 변형의 응답 19초 미만 | **실패**: V4에서 1,411.35초와 연결 오류 | metrics/latency_outlier.json |
| 동결 파일 및 파이프라인 범위 | 통과: 공통 함수 46개 중 _context만 변경, 보호 설정 동일 | metrics/scope_audit.json, PIPELINE_V23_V24.diff |
| 비밀값·평가셋 전체 문장 유출 | 신규 유출 0, 비밀값 0; 기존 세션 기록의 질문 1건은 baseline-1과 동일 | metrics/static_audit.json |
| 골든 기대값 사용자 검토 | **대기**: 원문에서 작성한 11개 표의 기대값 | GOLDEN.md의 원문 PNG/JSON 경로 |
| 최종 실행 기본값 복귀 | 통과: baseline1/baseline1, pipeline_v24.py와 평가 코드 6129446의 diff 없음 | EVAL.md의 최종 기본값, 기본값·환경변수 재정의 테스트 |
| 문항별 결과 보존 및 해시 대조 | 통과: 16개 실행 ×3파일을 바이트 그대로 복사, 48개 SHA-256 모두 기존 metrics와 일치; selection.json에는 파일 해시 기록 없음 | [MANIFEST.md](../../eval/runs_v24/MANIFEST.md), metrics/rag_comparison.json, metrics/repeat_comparison.json |
| 마무리 전체 pytest | 통과: 77 passed, 생략 0개, 100.51초; 키 3종 제거·소켓 차단·GACHON_DATA_DIR 지정 | runs/baseline2/finalization/pytest.xml 및 pytest_execution.json |
| 마무리 엄격 골든 | 기존 실패 보존: 표 2/11, 셀 삼중항 11/60, 값만 37/60; 종료 코드 1 | metrics/golden.json, runs/baseline2/finalization/golden.log |
| 마무리 정적 감사 | 통과: 동결 범위 동일, 비밀값 0건, 신규 전체 문장 유출 0건; 기존 세션 기록 질문 1건 유지 | runs/baseline2/finalization/static_audit.json, scripts/check_baseline2.py |

pytest는 IR·렌더러·분할·동일성·비교기 계약을 확인한다. 원문 셀 정확도 수용 검사는 별도 명령
`uv run python -m scripts.check_table_golden --strict`이며 종료 코드 1을 보존했다.
따라서 키 없는 환경에서 골든까지 모두 성공해야 한다는 계획서의 수용 조건은 충족하지 못했다.
특정 표 전용 예외를 추가하거나 기대값을 추출 결과에 맞추지 않았다.

원문 경로 없이 실행한 추가 pytest는 64개 통과·3개 생략이었다. 최종 검사는 GACHON_DATA_DIR을
지정하고 키 제거·소켓 차단 환경에서 생략된 데이터 의존 검사까지 다시 실행했다.
유출 검사는 같은 파일의 baseline-1 등장 횟수와 대조한다. 기존 문장이 같은 파일에서 늘거나 새 파일에
복사되면 실패한다. 이 동작은 실제 임시 Git 저장소를 사용하는 별도 회귀 테스트로 확인했다.

동결 범위는 reference/baseline1/, legacy/, 원본 build_notebook.py, pipeline_v23.py,
제출 노트북이다. 새 reference/baseline2/ 문서가 있으므로 reference/ 전체 diff가 비어야 한다는
문자 그대로의 조건과는 구별한다. 기존 v24 태그는 1단계 시점을 유지하며 최종 결과는 baseline-2 태그로 표시한다.
사용 완료 계획서는 prompts/legacy/baseline2_작업계획서.md로 이동했다.

마무리 계획서는 prompts/legacy/baseline2_마무리_작업계획서.md에 보존한다. 결과 복사 전
48개 파일의 sk-/pa- 키 접두어와 메모리에 있는 환경변수 API 키 값 일치를 검사했고 비밀값은 없었다.
정적 감사는 eval/runs_v24/에만 평가 문장 보존을 허용하고, 이 경로의 비밀값 검사는 유지한다.
유사 경로·그 밖의 결과 경로·코드·문서에서 허용되지 않음과 JSONL 비밀값 탐지는 회귀 테스트로 확인한다.
저장소의 core.autocrlf=true가 원본 env/summary의 CRLF를 변환하므로 eval/runs_v24/.gitattributes에서
이 경로의 JSON/JSONL만 -text로 지정했다. 커밋에 저장된 48개 blob도 원본 SHA-256과 대조한다.

페이지 색인의 raw 결합은 사용자 결정에 따라 보존했다. holdout10 #6의 원문과 고정 gold 충돌도
채점값을 변경하지 않고 기록했다. V4 시간 이상치의 원인은 확정하지 못했다. 세 항목의 해석 범위와
표 관련 문항별 예측·판정 비교는 [EVAL](EVAL.md), 실무 연결 지점은 [HANDOFF](HANDOFF.md)에 있다.
