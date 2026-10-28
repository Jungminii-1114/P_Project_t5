"""Run local pipeline evaluations and preserve per-question evidence and timings."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import sys
import threading
import time
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Iterable

from pydantic import BaseModel, Field


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATASET_FILES = {
    "hard20": "testset_hard.json",
    "holdout10": "testset_holdout.json",
    "drive20": "testset_drive20.json",
}


class Verdict(BaseModel):
    correct: bool = Field(description="예측 답변이 정답의 핵심 정보(수치·날짜·대상·조건)를 모두 포함하면 True")
    reason: str = Field(default="", description="판정 이유")


JUDGE = """정답과 예측 답변을 비교하세요. 표현이 달라도 핵심 정보(수치·날짜·대상·조건)가 모두 일치하면 정답입니다.
부분점수는 없습니다. 하나라도 빠지거나 틀리면 오답입니다."""


def _load_dotenv() -> None:
    """Load optional local settings without overriding the user's environment."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(ROOT / ".env", override=False)


def _records(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, dict):
        for key in ("questions", "samples", "items", "data"):
            if isinstance(raw.get(key), list):
                return [item for item in raw[key] if isinstance(item, dict)]
        if any(key in raw for key in ("question", "q")):
            return [raw]
        raise ValueError("평가 파일에서 질문 목록을 찾지 못했습니다.")
    if isinstance(raw, list):
        if not all(isinstance(item, dict) for item in raw):
            raise ValueError("평가 파일의 각 문항은 JSON object여야 합니다.")
        return raw
    raise ValueError("평가 파일은 JSON object 또는 목록이어야 합니다.")


def _sample_path(sample_path: str | Path | None) -> Path:
    if sample_path:
        path = Path(sample_path).expanduser()
        if not path.is_absolute():
            path = ROOT / path
        if path.is_file():
            return path
        raise FileNotFoundError(f"공식 sample.json을 찾지 못했습니다: {path}")

    env_path = os.environ.get("GACHON_SAMPLE_PATH")
    candidates = [
        Path(env_path).expanduser() if env_path else None,
        ROOT / "data" / "sample.json",
        ROOT / "eval" / "sample.json",
        Path(r"C:\Users\jspar\Downloads\중간평가-20261025T052820Z-1-001\중간평가\sample.json"),
    ]
    for path in candidates:
        if path is not None and path.is_file():
            return path
    locations = ", ".join(str(path) for path in candidates if path is not None)
    raise FileNotFoundError(
        "공식 sample.json이 없습니다. data/sample.json에 두거나 "
        f"--sample-path로 지정하세요. 확인한 위치: {locations}"
    )


def load_dataset(
    set_name: str,
    *,
    eval_dir: str | Path | None = None,
    sample_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Load official questions and golds without embedding any evaluation text."""
    if set_name == "sample3":
        path = _sample_path(sample_path)
        gold_keys = ("sample answer", "sample_answer", "gold", "answer")
    elif set_name in DATASET_FILES:
        path = Path(eval_dir or ROOT / "eval") / DATASET_FILES[set_name]
        gold_keys = ("gold",)
    else:
        raise ValueError(f"알 수 없는 평가 세트입니다: {set_name}")

    with path.open("r", encoding="utf-8-sig") as handle:
        raw = json.load(handle)
    result = []
    for index, item in enumerate(_records(raw), start=1):
        question = item.get("question", item.get("q"))
        gold = next((item[key] for key in gold_keys if item.get(key) is not None), None)
        if not isinstance(question, str) or not isinstance(gold, str):
            raise ValueError(f"{path.name} 문항 {index}에 question 또는 gold 문자열이 없습니다.")
        result.append({"id": item.get("id", index), "question": question, "gold": gold})
    return result


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if number >= 0 else default


def time_score(ok: bool, seconds: float) -> float:
    """Award the specified latency score to correct answers only."""
    if not ok:
        return 0.0
    if seconds <= 5.0:
        return 0.4
    if seconds >= 10.0:
        return 0.0
    return max(0.0, 0.4 - (seconds - 5.0) * 0.08)


def _source_page(source: Any, page: Any) -> tuple[str, str] | None:
    if source is None or page is None:
        return None
    return str(source), str(page)


def _iter_evidence(value: Any) -> Iterable[dict[str, Any]]:
    """Yield normalized evidence dictionaries from pipeline docs or metadata."""
    if value is None:
        return
    if isinstance(value, dict):
        if "source" in value:
            doc = value.get("doc")
            doc_metadata = getattr(doc, "metadata", {}) if doc is not None else {}
            if not isinstance(doc_metadata, dict):
                doc_metadata = {}
            metadata = value.get("metadata") or doc_metadata
            source = value.get("source", metadata.get("source"))
            page = value.get("doc_page", metadata.get("page", value.get("page")))
            kind = value.get("kind", metadata.get("kind", ""))
            chunk = value.get(
                "chunk",
                value.get("page_content", value.get("raw", getattr(doc, "page_content", ""))),
            )
            if source is not None and page is not None:
                yield {
                    "source": str(source),
                    "page": page,
                    "kind": str(kind or ""),
                    "chunk": str(chunk or "")[:200],
                }
            return
        if "metadata" in value and isinstance(value["metadata"], dict):
            metadata = value["metadata"]
            source = metadata.get("source")
            page = metadata.get("page")
            if source is not None and page is not None:
                yield {
                    "source": str(source),
                    "page": page,
                    "kind": str(metadata.get("kind", "") or ""),
                    "chunk": str(value.get("page_content", metadata.get("raw", "")) or "")[:200],
                }
            return
        for nested in value.values():
            yield from _iter_evidence(nested)
        return

    metadata = getattr(value, "metadata", None)
    if isinstance(metadata, dict):
        source, page = metadata.get("source"), metadata.get("page")
        if source is not None and page is not None:
            yield {
                "source": str(source),
                "page": page,
                "kind": str(metadata.get("kind", "") or ""),
                "chunk": str(getattr(value, "page_content", metadata.get("raw", "")) or "")[:200],
            }
        return

    if isinstance(value, (list, tuple, set)):
        for nested in value:
            yield from _iter_evidence(nested)


def _dedupe_evidence(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    result = []
    for item in items:
        normalized = {
            "source": str(item.get("source", "")),
            "page": item.get("page"),
            "kind": str(item.get("kind", "") or ""),
            "chunk": str(item.get("chunk", item.get("page_content", item.get("raw", ""))) or "")[:200],
        }
        key = (normalized["source"], str(normalized["page"]), normalized["kind"], normalized["chunk"])
        if normalized["source"] and normalized["page"] is not None and key not in seen:
            seen.add(key)
            result.append(normalized)
    return result


def _meta_doc_refs(value: Any) -> set[tuple[str, str]]:
    """Extract source/page references from older v22 meta docs tuples."""
    refs: set[tuple[str, str]] = set()
    if value is None:
        return refs
    if isinstance(value, dict):
        metadata = value.get("metadata", {}) if isinstance(value.get("metadata", {}), dict) else {}
        ref = _source_page(value.get("source", metadata.get("source")), value.get("page", metadata.get("page")))
        if ref:
            refs.add(ref)
        else:
            for nested in value.values():
                refs.update(_meta_doc_refs(nested))
        return refs
    if hasattr(value, "metadata"):
        metadata = getattr(value, "metadata", {})
        ref = _source_page(metadata.get("source"), metadata.get("page")) if isinstance(metadata, dict) else None
        if ref:
            refs.add(ref)
        return refs
    if isinstance(value, (list, tuple, set)):
        if len(value) == 2 and isinstance(value[0], str) and not isinstance(value[1], (list, tuple, dict)):
            ref = _source_page(value[0], value[1])
            if ref:
                refs.add(ref)
                return refs
        for nested in value:
            refs.update(_meta_doc_refs(nested))
    return refs


class QuestionTrace:
    def __init__(self) -> None:
        self.timings = {"search": 0.0, "draft": 0.0, "repair": 0.0}
        self.evidence: list[dict[str, Any]] = []


class PipelineInstrumentation:
    """Time v22 internals and collect full evidence without changing ask behavior."""

    def __init__(self, pipeline: ModuleType | Any) -> None:
        self.pipeline = pipeline
        self.current: QuestionTrace | None = None
        self._lock = threading.RLock()
        self._active_searches = 0
        self._install()

    def begin(self) -> QuestionTrace:
        self.current = QuestionTrace()
        return self.current

    def finish(self) -> QuestionTrace:
        trace = self.current or QuestionTrace()
        self.current = None
        return trace

    def _capture(self, value: Any) -> None:
        with self._lock:
            if self.current is None:
                return
            self.current.evidence = _dedupe_evidence(
                [*self.current.evidence, *_iter_evidence(value)]
            )

    def _install(self) -> None:
        if getattr(self.pipeline, "__eval_instrumentation__", None) is not None:
            self._prior = self.pipeline.__eval_instrumentation__
            return

        for name in ("retrieve", "retrieve_multi", "retrieve_more", "toc_lookup"):
            original = getattr(self.pipeline, name, None)
            if not callable(original):
                continue
            setattr(self.pipeline, name, self._wrap_search(name, original))

        original_llm = getattr(self.pipeline, "_call_llm", None)
        if callable(original_llm):
            setattr(self.pipeline, "_call_llm", self._wrap_llm(original_llm))
        self.pipeline.__eval_instrumentation__ = self

    def _wrap_search(self, name: str, original: Callable[..., Any]) -> Callable[..., Any]:
        aggregate = name in {"retrieve_multi", "retrieve_more"}

        def wrapped(*args: Any, **kwargs: Any) -> Any:
            with self._lock:
                nested = self._active_searches > 0
                if aggregate:
                    self._active_searches += 1
            started = time.perf_counter()
            try:
                result = original(*args, **kwargs)
                self._capture(result)
                return result
            finally:
                elapsed = time.perf_counter() - started
                with self._lock:
                    trace = self.current
                    should_count = aggregate or not nested
                    if aggregate:
                        self._active_searches -= 1
                if trace is not None and should_count:
                    trace.timings["search"] += elapsed

        return wrapped

    def _wrap_llm(self, original: Callable[..., Any]) -> Callable[..., Any]:
        draft_prompt = getattr(self.pipeline, "DRAFT_PROMPT", None)
        repair_prompt = getattr(self.pipeline, "REPAIR_PROMPT", None)

        def wrapped(*args: Any, **kwargs: Any) -> Any:
            system = args[0] if args else kwargs.get("system")
            if system == draft_prompt:
                stage = "draft"
            elif system == repair_prompt:
                stage = "repair"
            else:
                stage = None
            started = time.perf_counter()
            try:
                return original(*args, **kwargs)
            finally:
                trace = self.current
                if trace is not None and stage:
                    trace.timings[stage] += time.perf_counter() - started

        return wrapped


def instrument_pipeline(pipeline: ModuleType | Any) -> PipelineInstrumentation:
    existing = getattr(pipeline, "__eval_instrumentation__", None)
    if isinstance(existing, PipelineInstrumentation):
        return existing
    return PipelineInstrumentation(pipeline)


def _meta_timings(meta: dict[str, Any], trace: QuestionTrace) -> dict[str, float]:
    supplied = meta.get("timings")
    if not isinstance(supplied, dict):
        return {key: round(value, 6) for key, value in trace.timings.items()}
    return {
        key: round(_safe_float(supplied.get(key), trace.timings[key]), 6)
        for key in ("search", "draft", "repair")
    }


def _meta_evidence(meta: dict[str, Any], trace: QuestionTrace) -> list[dict[str, Any]]:
    supplied = meta.get("evidence")
    evidence = _dedupe_evidence(_iter_evidence(supplied)) if supplied is not None else []
    if evidence:
        return evidence

    refs = _meta_doc_refs(meta.get("docs"))
    captured = trace.evidence
    if refs:
        selected = [
            item for item in captured
                if any(
                    (item["source"] == source or item["source"].startswith(source))
                    and str(item["page"]) == page
                    for source, page in refs
                )
        ]
        if selected:
            return _dedupe_evidence(selected)
    return _dedupe_evidence(captured)


def _judge_fields(verdict: Any) -> tuple[bool, str]:
    if isinstance(verdict, dict):
        correct, reason = verdict.get("correct", False), verdict.get("reason", "")
    else:
        correct, reason = getattr(verdict, "correct", False), getattr(verdict, "reason", "")
    return bool(correct), str(reason or "")


def evaluate_item(
    item: dict[str, Any],
    set_name: str,
    ask: Callable[..., Any],
    judge: Callable[[str, str, str], Any],
    *,
    tracker: PipelineInstrumentation | None = None,
    repeat: int = 1,
) -> dict[str, Any]:
    question = str(item.get("question", item.get("q", "")))
    gold = str(item.get("gold", ""))
    trace = tracker.begin() if tracker else QuestionTrace()
    started = time.perf_counter()
    meta: dict[str, Any] = {}
    prediction = ""
    error_type: str | None = None
    reason = ""
    ok = False
    try:
        try:
            output = ask(question, return_meta=True)
            if isinstance(output, dict):
                meta = output
                prediction = str(output.get("answer", "") or "")
            else:
                prediction = str(output or "")
        except Exception as exc:
            error_type = type(exc).__name__
            reason = f"Pipeline error: {error_type}"

        elapsed = time.perf_counter() - started
        seconds = _safe_float(meta.get("sec"), elapsed)
        if error_type is None:
            try:
                ok, reason = _judge_fields(judge(question, gold, prediction))
            except Exception as exc:
                error_type = type(exc).__name__
                reason = f"Judge error: {error_type}"
                ok = False
        timings = _meta_timings(meta, trace)
        evidence = _meta_evidence(meta, trace)
        sub_queries = meta.get("sub_queries", meta.get("n_sub_queries", 0))
        if isinstance(sub_queries, (list, tuple, set)):
            sub_queries = len(sub_queries)
        try:
            sub_queries = int(sub_queries or 0)
        except (TypeError, ValueError):
            sub_queries = 0
        heuristic_score = meta.get("heuristic_score", meta.get("conf"))
        if heuristic_score is not None:
            heuristic_score = _safe_float(heuristic_score)
        row = {
            "set": set_name,
            "repeat": repeat,
            "id": item.get("id"),
            "question": question,
            "gold": gold,
            "prediction": prediction,
            "ok": bool(ok),
            "reason": reason,
            "sec": round(seconds, 6),
            "timings": timings,
            "route": meta.get("route"),
            "action": meta.get("action", "none"),
            "sub_queries": sub_queries,
            "evidence": evidence,
            "heuristic_score": heuristic_score,
            "ground": meta.get("ground"),
            "events": meta.get("events", []),
            "time_score": round(time_score(bool(ok), seconds), 6),
        }
        if error_type:
            row["error_type"] = error_type
        return row
    finally:
        if tracker:
            tracker.finish()


def evaluate_items(
    items: Iterable[dict[str, Any]],
    set_name: str,
    ask: Callable[..., Any],
    judge: Callable[[str, str, str], Any],
    *,
    tracker: PipelineInstrumentation | None = None,
    repeat: int = 1,
    on_result: Callable[[dict[str, Any]], None] | None = None,
) -> list[dict[str, Any]]:
    rows = []
    for item in items:
        row = evaluate_item(item, set_name, ask, judge, tracker=tracker, repeat=repeat)
        rows.append(row)
        if on_result:
            on_result(row)
    return rows


def summarize_results(rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("set", "unknown"))].append(row)
    summaries = {}
    for set_name, group in grouped.items():
        seconds = [_safe_float(row.get("sec")) for row in group]
        correct = sum(bool(row.get("ok")) for row in group)
        scores = [_safe_float(row.get("time_score")) for row in group]
        summaries[set_name] = {
            "correct": correct,
            "total": len(group),
            "accuracy": correct / len(group) if group else 0.0,
            "mean_sec": round(sum(seconds) / len(seconds), 6) if seconds else 0.0,
            "max_sec": max(seconds, default=0.0),
            "over_5s": sum(value > 5.0 for value in seconds),
            "over_10s": sum(value > 10.0 for value in seconds),
            "over_19s": sum(value > 19.0 for value in seconds),
            "time_score": round(sum(scores), 6),
        }
    return summaries


def load_pipeline(version: str) -> ModuleType:
    if version not in {"v22", "v23"}:
        raise ValueError("--version은 v22 또는 v23이어야 합니다.")
    path = ROOT / f"pipeline_{version}.py"
    if not path.is_file():
        raise FileNotFoundError(f"{path.name}이 없습니다. 먼저 빌더로 파이프라인을 생성하세요.")
    module_name = f"_gachon_eval_{version}_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"파이프라인 모듈을 불러오지 못했습니다: {path.name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def make_judge(pipeline: ModuleType | Any) -> Callable[[str, str, str], Any]:
    """Reuse the pipeline's configured ChatOpenAI client with the fixed schema."""
    llm = getattr(pipeline, "llm", None)
    if llm is None:
        raise AttributeError("파이프라인에 LLM 인스턴스 `llm`이 없습니다.")
    structured = llm.with_structured_output(Verdict)

    def judge(question: str, gold: str, prediction: str) -> Any:
        prompt = f"[질문]\n{question}\n\n[정답]\n{gold}\n\n[예측]\n{prediction}"
        return structured.invoke([("system", JUDGE), ("human", prompt)])

    return judge


def _jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "model_dump"):
        return _jsonable(value.model_dump())
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _derive_manifest(pipeline: ModuleType | Any) -> dict[str, Any]:
    for name in ("manifest", "DATA_MANIFEST", "DOCUMENT_MANIFEST", "dataset_manifest", "document_manifest", "MANIFEST"):
        value = getattr(pipeline, name, None)
        if isinstance(value, (dict, list, tuple)):
            return _jsonable(value)

    data_dir_value = getattr(pipeline, "DATA_DIR", None) or os.environ.get("GACHON_DATA_DIR", ROOT / "data" / "dataset")
    data_dir = Path(data_dir_value)
    required = getattr(pipeline, "REQUIRED", None)
    names = list(required) if required else [p.name for p in sorted(data_dir.iterdir()) if p.suffix.lower() in {".pdf", ".hwp"}] if data_dir.is_dir() else []
    parser_version = getattr(pipeline, "PARSER_VERSION", {
        package: importlib.metadata.version(package)
        for package in ("pymupdf", "pdfplumber", "langchain-hwp-hwpx-loader", "pyhwp")
    })
    files = {}
    for name in names:
        path = data_dir / name
        if not path.is_file():
            continue
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        files[name] = {
            "sha256": digest.hexdigest(),
            "size_bytes": path.stat().st_size,
            "parser_version": parser_version,
        }
    return {"data_dir": str(data_dir), "files": files}


def _package_versions() -> dict[str, str | None]:
    packages = (
        "langchain",
        "langchain-openai",
        "langchain-community",
        "langchain-chroma",
        "langchain-hwp-hwpx-loader",
        "rank-bm25",
        "kiwipiepy",
        "pymupdf",
        "pdfplumber",
        "voyageai",
        "langchain-voyageai",
        "python-dotenv",
        "chromadb",
        "pydantic",
    )
    result: dict[str, str | None] = {}
    for package in packages:
        try:
            result[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            result[package] = None
    return result


def environment_record(pipeline: ModuleType | Any, version: str, repeat: int) -> dict[str, Any]:
    return {
        "pipeline": version,
        "repeat": repeat,
        "python": sys.version,
        "packages": _package_versions(),
        "document_manifest": _derive_manifest(pipeline),
        "model": getattr(pipeline, "LLM_MODEL", os.environ.get("LLM_MODEL", "gpt-6-luna")),
        "embedding_model": getattr(pipeline, "EMBED_MODEL", None),
    }


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(_jsonable(value), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _new_run_dir(runs_dir: Path, version: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = runs_dir / f"{stamp}_{version}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def run_once(
    version: str,
    sets: list[str],
    repeat: int,
    *,
    runs_dir: str | Path | None = None,
    eval_dir: str | Path | None = None,
    sample_path: str | Path | None = None,
) -> Path:
    """Import a fresh pipeline/index and execute one evaluation pass."""
    _load_dotenv()
    questions_by_set = {
        set_name: load_dataset(set_name, eval_dir=eval_dir, sample_path=sample_path)
        for set_name in sets
    }
    pipeline = load_pipeline(version)
    tracker = instrument_pipeline(pipeline)
    judge = make_judge(pipeline)
    output_dir = Path(runs_dir) if runs_dir else ROOT / "runs"
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    run_dir = _new_run_dir(output_dir, version)
    _write_json(run_dir / "env.json", environment_record(pipeline, version, repeat))

    all_rows: list[dict[str, Any]] = []
    results_path = run_dir / "results.jsonl"
    with results_path.open("w", encoding="utf-8", newline="\n") as handle:
        for set_name in sets:
            questions = questions_by_set[set_name]

            def append_result(row: dict[str, Any]) -> None:
                handle.write(json.dumps(_jsonable(row), ensure_ascii=False) + "\n")
                handle.flush()

            rows = evaluate_items(
                questions,
                set_name,
                pipeline.ask,
                judge,
                tracker=tracker,
                repeat=repeat,
                on_result=append_result,
            )
            all_rows.extend(rows)

    summary = {
        "pipeline": version,
        "repeat": repeat,
        "sets": summarize_results(all_rows),
    }
    _write_json(run_dir / "summary.json", summary)
    return run_dir


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="로컬 파이프라인 평가를 실행하고 문항별 결과를 저장합니다.")
    parser.add_argument("--version", required=True, choices=("v22", "v23"))
    parser.add_argument("--sets", default="sample3,hard20,holdout10,drive20")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--sample-path", help="공식 sample.json 경로 (기본: data/sample.json 또는 환경변수 경로)")
    parser.add_argument("--eval-dir", help="eval/testset_*.json이 있는 폴더")
    parser.add_argument("--runs-dir", default="runs", help="실행 결과 폴더 (기본: runs)")
    args = parser.parse_args(argv)
    args.sets = [name.strip() for name in args.sets.split(",") if name.strip()]
    if not args.sets:
        parser.error("--sets에 하나 이상의 세트 이름이 필요합니다.")
    unknown = sorted(set(args.sets) - {"sample3", *DATASET_FILES})
    if unknown:
        parser.error(f"알 수 없는 세트: {', '.join(unknown)}")
    if args.repeat < 1:
        parser.error("--repeat은 1 이상이어야 합니다.")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    _load_dotenv()
    for repeat_index in range(1, args.repeat + 1):
        run_dir = run_once(
            args.version,
            args.sets,
            repeat_index,
            runs_dir=args.runs_dir,
            eval_dir=args.eval_dir,
            sample_path=args.sample_path,
        )
        print(f"평가 결과 저장: {run_dir}")
        summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
        for set_name, stats in summary["sets"].items():
            print(
                f"  {set_name}: {stats['correct']}/{stats['total']} "
                f"({stats['accuracy']:.1%}) · 평균 {stats['mean_sec']:.2f}s · 최대 {stats['max_sec']:.2f}s"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
