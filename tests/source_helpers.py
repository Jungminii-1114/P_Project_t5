"""Read notebook-cell literals without building, parsing data, or calling APIs."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def cell_sources(builder="build_notebook.py"):
    tree = ast.parse((ROOT / builder).read_text(encoding="utf-8"))
    return [ast.literal_eval(n.value.args[0]) for n in tree.body
            if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
            and isinstance(n.value.func, ast.Name) and n.value.func.id == "code"]


def load_definitions(*markers, builder="build_notebook.py", namespace=None,
                     definitions_only=False):
    ns = {} if namespace is None else namespace
    for src in cell_sources(builder):
        if not any(marker in src for marker in markers):
            continue
        src = "\n".join(line for line in src.splitlines() if not line.startswith("%"))
        tree = ast.parse(src)
        node_types = (ast.FunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom)
        if not definitions_only:
            node_types += (ast.Assign, ast.AnnAssign)
        nodes = [n for n in tree.body if isinstance(n, node_types)]
        # Module initialization (LLM/network/indexes/demo) is never executed here.
        for n in nodes:
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                continue
            if isinstance(n, (ast.Assign, ast.AnnAssign)):
                names = [x.id for x in ast.walk(n) if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Store)]
                if any(x in {"llm", "_", "_docs", "_route", "_q"} for x in names):
                    continue
            exec(compile(ast.Module(body=[n], type_ignores=[]), builder, "exec"), ns)
    return ns
