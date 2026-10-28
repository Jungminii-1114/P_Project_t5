import runpy
from pathlib import Path

from tests.source_helpers import ROOT


def test_builder_writes_both_artifacts_and_pins_runtime(tmp_path):
    import shutil
    for name in ["build_notebook.py", "uv.lock", "pyproject.toml"]:
        shutil.copy(ROOT / name, tmp_path / name)
    ns = runpy.run_path(str(tmp_path / "build_notebook.py"))
    assert (tmp_path / "pipeline_v23.py").exists()
    pipeline = (tmp_path / "pipeline_v23.py").read_text(encoding="utf-8")
    assert "자동 생성" in pipeline.splitlines()[0]
    assert "%pip" not in pipeline
    assert "DEMO_QUESTIONS" not in pipeline
    assert "query = " not in pipeline
    cells = ns["CELLS"]
    assert len(cells) == 27
    assert sum(kind == "code" for kind, _ in cells) == 13
    pip = next(s for kind, s in cells if "%pip" in s)
    assert " -U " not in pip
    assert "python-dotenv==" in pip
    assert "langchain==" in pip
    assert "load_dotenv" in pipeline
    assert 'os.environ.get("GACHON_DATA_DIR"' in pipeline
    compile(pipeline, str(tmp_path / "pipeline_v23.py"), "exec")
