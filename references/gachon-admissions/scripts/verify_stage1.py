"""Reproduce parser, tests and diagnostics with credentials and sockets disabled."""

import json
import os
from pathlib import Path
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]


def main():
    output = ROOT / "runs/baseline2"
    guard = output / "network_guard"
    guard.mkdir(parents=True, exist_ok=True)
    keys = ("OPENAI_API_KEY", "VOYAGEAI_API_KEY", "VOYAGE_API_KEY")
    (guard / "sitecustomize.py").write_text(
        "import os, socket\n"
        f"assert not any(os.environ.get(k) for k in {keys!r})\n"
        "def blocked(*args, **kwargs):\n    raise RuntimeError('stage1 network disabled')\n"
        "socket.socket.connect = blocked\nsocket.socket.connect_ex = blocked\n"
        "socket.socket.sendto = blocked\nsocket.create_connection = blocked\n", encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k not in keys}
    env["PYTHONPATH"] = str(guard) + os.pathsep + str(ROOT)
    env["GACHON_DATA_DIR"] = str(ROOT / "data/dataset")
    commands = [
        ["-m", "docparse", "data/dataset", "--profile", "gachon_2027", "--extract-table-ir", "--out", "runs/baseline2/ir"],
        ["-m", "scripts.diagnose_tables"],
        ["-m", "scripts.check_table_golden", "--strict"],
        ["-m", "scripts.diagnose_bm25"],
        ["-m", "pytest", "-q", "--junitxml=runs/baseline2/pytest.xml"],
    ]
    records = []
    for number, command in enumerate(commands):
        start = time.monotonic()
        completed = subprocess.run([sys.executable, *command], cwd=ROOT, env=env,
                                   capture_output=True, text=True, encoding="utf-8", errors="replace")
        (output / f"api_free_{number}.log").write_text(completed.stdout+completed.stderr, encoding="utf-8")
        record = {"command": command, "exit_code": completed.returncode,
                  "seconds": round(time.monotonic()-start, 3)}
        records.append(record)
        print(json.dumps(record), flush=True)
    result = {"credentials_removed": list(keys), "network_disabled": True, "commands": records,
              "execution_passed": all(r["exit_code"] == 0 for i, r in enumerate(records) if i != 2),
              "golden_acceptance_passed": records[2]["exit_code"] == 0}
    target = ROOT / "reference/baseline2/metrics/api_free.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    return 0 if result["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
