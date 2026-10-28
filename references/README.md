# Implementation references

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
