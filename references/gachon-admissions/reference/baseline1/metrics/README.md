# baseline-1 평가 메트릭 파일

아래 네 원본 실행 폴더에서 `summary.json`과 `env.json`을 그대로 복사했다. 문항별 `results.jsonl`은 포함하지 않는다. 각 로그는 원본 `runs/` 경로와 SHA-256만 기록한다.

| 실행 | 원본 로그 경로 | 보존 파일 | `results.jsonl` SHA-256 |
|---|---|---|---|
| 전체 v23 | `runs/20261028_123828_709846_v23/results.jsonl` | `summary.json`, `env.json` | `61f1be9395826d8f9d68ad815eee50a8c5956ada2358dcf9b40fa49abe5f4387` |
| sample3 반복 1 | `runs/20261028_124701_995010_v23/results.jsonl` | `summary.json`, `env.json` | `469c1dec351be3e5f7a874d094c4ac7e699c7e26bcc82c52c4b661ff813208e0` |
| sample3 반복 2 | `runs/20261028_124757_442570_v23/results.jsonl` | `summary.json`, `env.json` | `14e00bac1a4a71eb6886546d0330902da0afa7e987b6bd52b6c868711de88c47` |
| sample3 반복 3 | `runs/20261028_124851_799805_v23/results.jsonl` | `summary.json`, `env.json` | `ef252c01838f0589e96d9e86aa4b9563aa7634f4c504cff3602e2e849b98295e` |

SHA-256은 각 원본 `results.jsonl` 바이트에 대해 계산했다. JSONL의 질문·정답·예측 내용은 여기에 포함하지 않았다.
