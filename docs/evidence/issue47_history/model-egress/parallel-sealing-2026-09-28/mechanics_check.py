"""Exercise verify.py's parallel machinery on a few injections, without the suite and without sealing.

Run from the root of a runtime tree (HEAD + both patches, minted) whose
verify.py is the parallel version:

    python3 mechanics_check.py <out.json> <copies> <injection id> [<injection id> ...]

It makes the copies, proves them identical to the tree by the manifest, runs
the named injections through _dispatch, proves the copies and the tree
identical again, removes the copies and reports. It seals nothing: a mechanics
check, not evidence about any injection.
"""
import importlib.util
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "verify_mechanics", Path.cwd() / "docs/evidence/issue47_history/model-egress/verify.py")
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)
out, copies, wanted = Path(sys.argv[1]), int(sys.argv[2]), sys.argv[3:]
index = {name: position for position, (name, _, _) in enumerate(verify.INJECTIONS)}
order = [index[name] for name in wanted]
report = {"copies": copies, "injections": wanted}
started = time.monotonic()
tree = verify._manifest(verify.ROOT)
report["manifest_entries"], report["manifest_digest"] = len(tree), verify._manifest_digest(tree)
report["manifest_seconds"] = round(time.monotonic() - started, 1)
results = Path(tempfile.mkdtemp(prefix="issue47-verify-results-"))
parent = None
try:
    phase = time.monotonic()
    parent, roots = verify._make_copies(copies)
    report["at_start"] = [verify._manifest(root) == tree for root in roots]
    report["copies_seconds"] = round(time.monotonic() - phase, 1)
    phase = time.monotonic()
    rows, stop = verify._dispatch(roots, order, results)
    report["dispatch_seconds"] = round(time.monotonic() - phase, 1)
    report["stop"] = stop
    report["rows"] = {verify.INJECTIONS[i][0]: {k: row.get(k) for k in (
        "outcome", "expected_class_outcome", "first_caught_by", "copy", "seconds")}
        for i, row in rows.items()}
    report["at_end"] = [verify._manifest(root) == tree for root in roots]
    report["sealing_tree_at_end"] = verify._manifest(verify.ROOT) == tree
    report["copy_names"] = [parent.name + "/" + root.name for root in roots]
finally:
    if parent is not None:
        shutil.rmtree(parent, ignore_errors=True)
    shutil.rmtree(results, ignore_errors=True)
report["copies_removed"] = parent is not None and not parent.exists()
out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
print(json.dumps(report, indent=1))
