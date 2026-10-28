# v24 실행 결과 보존

V0–V4 기본 비교, 동률 재평가 및 V3 선정 후 확인 실행의 저장 결과를 보존한다. 각 실행의 `env.json`, `results.jsonl`, `summary.json`은 원본과 바이트 단위로 동일하다.

## 검증

- 16개 실행, 48개 파일을 복사하고 원본과 바이트 단위로 비교했다.
- `rag_comparison.json` 및 `repeat_comparison.json`에 기록된 48개 파일 SHA-256이 모두 일치했다. 기록 누락 0건, 불일치 0건이다.
- `selection.json`에는 실행 목록과 선택 정보가 있고 실행 파일 SHA-256은 기록되어 있지 않다. 16개 실행 파일 해시는 앞의 두 metrics 파일에서 모두 찾았다.
- 복사 전 보안 감사: `sk-` 및 `pa-` 접두어 0건, 프로세스 환경의 API 키 값과 정확히 일치하는 문자열 0건. 로컬 `.env` 파일 없음 (`.env.example`은 템플릿). 값은 출력하거나 기록하지 않았다.
- `.gitattributes`의 JSON/JSONL `-text` 설정으로 Git 줄바꿈 변환을 막아 원본 CRLF/LF와 SHA-256을 커밋에서도 보존한다.

## 실행 목록

| 실행 폴더 | 변형 | 용도 | 세트별 정답 수 | 총 정답 | `results.jsonl` SHA-256 | 해시 기록 |
|---|---|---|---|---:|---|---|
| `20261028_171336_786587_v24_V0` | `V0` | 기본 비교 | holdout10 7/10; drive20 11/20; hard20 19/20; sample3 3/3 | 40/53 | `2941cd5fb25a99626f4763733b9c89fa0ac085ca381e3d6aaa167175be946691` | `rag_comparison` |
| `20261028_172302_266413_v24_V1` | `V1` | 기본 비교 | holdout10 7/10; drive20 10/20; hard20 18/20; sample3 3/3 | 38/53 | `b4fb76bb1fb18ea9ed45de24558ae7ae29f7753fe060cd767efc8943e8433f77` | `rag_comparison` |
| `20261028_173016_112736_v24_V2` | `V2` | 기본 비교 | holdout10 7/10; drive20 8/20; hard20 20/20; sample3 3/3 | 38/53 | `f0ae3abd2b7e8d8027e7ef05556a64ef7136786afcbb057d0baed5b9e79b777c` | `rag_comparison` |
| `20261028_173756_812329_v24_V3` | `V3` | 기본 비교 | holdout10 8/10; drive20 10/20; hard20 19/20; sample3 3/3 | 40/53 | `46cbbef8b8dc6a2b17b35da8cdcb44a948844544ce15a0eb7ae008af184d71f4` | `rag_comparison` |
| `20261028_174535_624062_v24_V4` | `V4` | 기본 비교 | holdout10 8/10; drive20 8/20; hard20 18/20; sample3 3/3 | 37/53 | `543e952a6dc74f894b3b1052b2a0673218ddab66d8871a5bffb8109f32395d81` | `rag_comparison` |
| `20261028_181823_794465_v24_V3_tie_sample` | `V3_tie_sample` | 동률 재평가 | sample3 3/3 | 3/3 | `bb2bfe9964267f2a67a853b834bed9b885267226f35bb2281e20b2ea91a3b17b` | `repeat_comparison` |
| `20261028_181909_524199_v24_V3_tie_sample` | `V3_tie_sample` | 동률 재평가 | sample3 3/3 | 3/3 | `944b9d2f0c3322db13d11ed052bf03849b361f3322ab402420a5f9223f956eec` | `repeat_comparison` |
| `20261028_181956_926587_v24_V3_tie_sample` | `V3_tie_sample` | 동률 재평가 | sample3 3/3 | 3/3 | `3db2f7a56932b626c8136ccf0fe0210fcc466eafe73b09c3d50d74dcc54e280b` | `repeat_comparison` |
| `20261028_182058_796221_v24_V3_tie_drive` | `V3_tie_drive` | 동률 재평가 | drive20 11/20 | 11/20 | `0c4aac9d6151c73b66d1a07f85842439853a377cda99df2622db6cf753fab606` | `repeat_comparison` |
| `20261028_182435_199358_v24_V0_tie_sample` | `V0_tie_sample` | 동률 재평가 | sample3 3/3 | 3/3 | `27e77ffd0e55118b6f045583b6b98c5b85e1a9e878444eb6252a03b1ce2c056a` | `repeat_comparison` |
| `20261028_182513_745664_v24_V0_tie_sample` | `V0_tie_sample` | 동률 재평가 | sample3 3/3 | 3/3 | `2e07d2983f4cde57ac877c0222a4dc90d33d83a9af037ab559f37af31078f565` | `repeat_comparison` |
| `20261028_182552_158144_v24_V0_tie_sample` | `V0_tie_sample` | 동률 재평가 | sample3 3/3 | 3/3 | `5e93c99a77fa90eed0d7ae49996925c4433aa2b362e28bc5844cec917676dad1` | `repeat_comparison` |
| `20261028_182634_390242_v24_V0_tie_drive` | `V0_tie_drive` | 동률 재평가 | drive20 8/20 | 8/20 | `bf77d1c54ab37cb50f92b3a4ae346bc3226cf9b57b1e6c7752d4fccf0861cb50` | `repeat_comparison` |
| `20261028_183145_103228_v24_V3_selected_sample` | `V3_selected_sample` | 선정 후 확인 | sample3 3/3 | 3/3 | `cee1f840e43189a87a235e65fa1fa588e00154f2d3b06d47759ae822ca878929` | `repeat_comparison` |
| `20261028_183229_792758_v24_V3_selected_sample` | `V3_selected_sample` | 선정 후 확인 | sample3 3/3 | 3/3 | `d32579ef1fafb6d1cee884d7c30fdf6fcfbc86496471f66e15c362cf29a7faec` | `repeat_comparison` |
| `20261028_183312_984137_v24_V3_selected_sample` | `V3_selected_sample` | 선정 후 확인 | sample3 3/3 | 3/3 | `208ff2279ab1f68f2a4608ab3fcbba258755687e8425a376751a9fcf7fe9efb8` | `repeat_comparison` |

## holdout10 #6 원문 기준 참고 집계

`reference/baseline2/metrics/source_gold_audit.json`의 `holdout10` 6번 원문 감사 판정을 사용했다. 저장된 각 기본 비교 결과에서 해당 행의 `ok` 판정만 원문 기준으로 대체해 다시 합산했다. 질문·정답 문장은 이 문서에 인용하지 않았다.

| 변형 | 저장된 공식 집계 | #6 저장 판정 | 원문 기준 재판정 | 참고 집계 |
|---|---:|---|---|---:|
| V0 | 40/53 | 오답 | 정답 | 41/53 |
| V1 | 38/53 | 오답 | 정답 | 39/53 |
| V2 | 38/53 | 오답 | 정답 | 39/53 |
| V3 | 40/53 | 오답 | 정답 | 41/53 |
| V4 | 37/53 | 정답 | 오답 | 36/53 |

이 참고 집계는 원문 감사와 저장된 예측을 이용한 재계산이다. 평가셋 gold와 보존된 run 파일은 수정하지 않았으며, 공식 집계도 변경하지 않았다.
