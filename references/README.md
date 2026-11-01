# Implementation references

## AutoRAG — RAG/Agent 설계 및 자동 평가 참고 (2026-11-01)

[AutoRAG 분석 노트](autorag/README.md): 공식 [AutoRAG v2.13.4](https://github.com/Marker-Inc-Korea/AutoRAG/releases/tag/v2.13.4) 기준 **Agent 2.0**(로컬 문서 검색·근거 인용·라우팅)과 **Legacy**(RAG 파이프라인 자동 평가·최적화)를 구분해 정리했다. ReportAnchor의 N-01/N-02/N-03, T-01, RRF 실험과의 관계, 실행·외부 API·라이선스 한계를 포함한다. **설계 참고 전용이며 코드/레거시 의존성은 복사·반입하지 않았다.**

## DeepSeek Harness (DSH) — 설계 참고

[DSH 분석 노트](deepseek-harness/README.md): Agent 루프 상태 머신, 도구 실행 파이프라인, 세션 이벤트 로그, 플러그인 구조와 LangGraph 대응. 2026-10-30 공식 문서 기준이며, 하네스는 DSH를 실행하지 않고 설계만 참고한다.

## Gachon admissions — baseline-1

[Browse the reference index](gachon-admissions/reference/README.md).

This folder preserves the v23 admissions RAG experiment as a reference for Report Agent's parsing, evidence contract, retrieval, evaluation, and known limitations. The source snapshot is commit `3fbba3fc45ea531bc76030631fae8055bacf8ec9` (tag `baseline-1`); the pipeline baseline is tag `v23` (`64ac263`).

- [Portable parser and profile guide](gachon-admissions/reference/baseline1/docparse_generic/README.md)
- [Parser output contract](gachon-admissions/reference/baseline1/INTERFACE.md)
- [Architecture and evaluation index](gachon-admissions/reference/README.md)
- [Validation results](gachon-admissions/reference/baseline1/VALIDATION.md)
- [Follow-up backlog](gachon-admissions/BACKLOG.md)

Run project commands from the imported project directory:

```powershell
cd references/gachon-admissions
uv sync
```

Then follow the reference index for local parsing and snapshot reproduction. Original documents and generated snapshot JSONL files are local inputs/outputs excluded by the project's `.gitignore`. The tracked manifests, metrics, source code, tests, and experiment history are preserved in the imported tree.

## Gachon admissions — baseline-2

Table IR and comparison of three renderers. Strict golden validation remains 2/11. Renderer superiority was not established; the final default is baseline1.

The complete source snapshot is commit `5303b8f016a74ec6c63d6c6301ad2be242203477` (annotated tag `baseline-2`); stage-1 tag `v24` remains at `5fe787380bc78337ac2c5ac054d7d29fab8612d4`.

- [Practical handoff and data contract lessons](gachon-admissions/reference/baseline2/HANDOFF.md)
- [Evaluation and final default rationale](gachon-admissions/reference/baseline2/EVAL.md)
- [Validation results and known failures](gachon-admissions/reference/baseline2/VALIDATION.md)
- [Table and cell IR contract](gachon-admissions/reference/baseline2/IR.md)
- [Renderer formats](gachon-admissions/reference/baseline2/RENDERERS.md)
- [Source golden validation](gachon-admissions/reference/baseline2/GOLDEN.md)
- [All 16 preserved runs and SHA-256 manifest](gachon-admissions/eval/runs_v24/MANIFEST.md)
