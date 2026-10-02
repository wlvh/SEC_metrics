"""Exercise the actual unchanged source-case runner for the three selectors."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time

import run_fast_tests_v2 as runner

HERE = Path(__file__).resolve().parent
PREFIX = "tests.vnext.test_d03_native_assessment.D03NativeAssessmentTest."
names = [name for name in runner.SOURCE_TESTS if name.startswith(PREFIX)]
assert len(names) == 3 and len(set(names)) == 3
assert PREFIX[:-1] not in runner.SOURCE_TESTS
start = time.monotonic()
with ThreadPoolExecutor(max_workers=2) as pool:
    rows = list(pool.map(runner._run_source_case, names))
result = {
    "head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
    "worktree_changes": ["tools/run_fast_tests_v2.py: selector decomposition only"],
    "code_root": str(runner.inherited.REPO_ROOT),
    "interpreter": str(Path(__import__("sys").executable).resolve()),
    "completed_at": datetime.now(timezone.utc).isoformat(),
    "jobs": 2,
    "duration_seconds": round(time.monotonic() - start, 3),
    "tests": rows,
    "status": "PASSED" if all(row["return_code"] == 0 for row in rows) else "FAILED",
    "business_calls": [0, 0, 0],
}
(HERE / "split-run-result.json").write_text(json.dumps(result, indent=2) + "\n")
(HERE / "split-run.done").write_text(result["status"] + "\n")
print(json.dumps(result, indent=2), flush=True)
raise SystemExit(0 if result["status"] == "PASSED" else 1)
