"""Finish the sequential baseline the container restart cut at 66 of 78 injections.

The 2026-09-28 sequential sealing run (the owner's contract change asked for it
to finish as the baseline the parallel run is compared with) had judged the
first 66 injections in list order when the container restarted and ended it;
its log is ``sequential-interrupted-2026-09-28.log``. This runs the other 12,
one after another in list order, in a single copy of the verification tree,
with verify.py's own copy, dispatch and judging code - one copy is a sequential
run. It seals nothing: the receipt is verify.py's.

Run from the root of the verification tree (HEAD + both patches, minted):

    python3 docs/evidence/issue47_history/model-egress/complete_sequential_baseline.py <out.json>

The copy is proven identical to the tree by verify.py's manifest before the
first injection and after the last, and removed afterwards.
"""
import importlib.util
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

HERE = Path("docs/evidence/issue47_history/model-egress")
spec = importlib.util.spec_from_file_location("verify_baseline", Path.cwd() / HERE / "verify.py")
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)
out = Path(sys.argv[1])
interrupted = [json.loads(line) for line in
               (Path.cwd() / HERE / "sequential-interrupted-2026-09-28.log").read_text().splitlines()
               if line.startswith("{")]
done = [row["id"] for row in interrupted]
names = [name for name, _, _ in verify.INJECTIONS]
assert done == names[:len(done)], "the interrupted run's rows are not a prefix of the list"
order = list(range(len(done), len(names)))
tree = verify._manifest(verify.ROOT)
report = {"record_type": "ISSUE_47_EGRESS_SEQUENTIAL_BASELINE_COMPLETION",
          "interrupted_rows": len(done), "completed_here": [names[i] for i in order],
          "manifest_digest": verify._manifest_digest(tree), "calls": {"provider": 0, "paid": 0, "sec": 0}}
results = Path(tempfile.mkdtemp(prefix="issue47-verify-results-"))
parent = None
started = time.monotonic()
try:
    parent, roots = verify._make_copies(1)
    report["copy_was_the_tree_when_made"] = verify._manifest(roots[0]) == tree
    assert report["copy_was_the_tree_when_made"]
    rows, stop = verify._dispatch(roots, order, results)
    report["stop"] = stop
    report["rows"] = [rows[i] for i in sorted(rows)]
    report["copy_was_the_tree_after_the_last_injection"] = verify._manifest(roots[0]) == tree
    report["tree_unchanged"] = verify._manifest(verify.ROOT) == tree
finally:
    if parent is not None:
        shutil.rmtree(parent, ignore_errors=True)
    shutil.rmtree(results, ignore_errors=True)
report["seconds"] = round(time.monotonic() - started, 1)
out.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(json.dumps({key: report.get(key) for key in ("stop", "copy_was_the_tree_when_made",
                                                   "copy_was_the_tree_after_the_last_injection",
                                                   "tree_unchanged", "seconds")}))
sys.exit(0 if report.get("stop") is None and report.get("tree_unchanged")
         and report.get("copy_was_the_tree_after_the_last_injection") else 2)
