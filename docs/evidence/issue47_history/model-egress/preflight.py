"""Pre-flight for verify.py: does each injection's own expected class catch it?

Run from the root of a worker copy of the verification tree (HEAD + both
patches, minted). Imports that tree's verify.py and reuses its injection list,
its edit/compile/mint discipline, its _suite and _outcome, but runs only the
expected class for each assigned injection - never the whole-suite fallback -
because the question is which injections the class written for them misses.
Every file is restored and the snapshot must come back byte for byte after
each injection, as in verify.py.

Usage (from the root of a copy of the verification tree; several copies can
run disjoint index lists at once, since injections edit files in place):
    python3 docs/evidence/issue47_history/model-egress/preflight.py <output.jsonl> <index> [<index> ...]

It seals nothing and proves nothing on its own: the receipt is verify.py's,
which runs every injection again in one tree. What this answers is which
injections the class written for them misses, in hours rather than a
sequential run that falls back to the whole suite for each miss.

The creator journal must come back after each injection as well. The first
pre-flight did not check it: an injection that dropped E01's "LIVE needs
counted calls" check let a case register LIVE and fail before any cleanup,
and every later case in that copy that read the window met the record - so
catches there after it may have been the leftover's, not the injection's. The
suite now puts the journal back after every case (``_Isolated.setUp``); a
run whose journal does not come back stops by name.
"""
import importlib.util
import json
import sys
import time
from pathlib import Path

HERE = "docs/evidence/issue47_history/model-egress/verify.py"
spec = importlib.util.spec_from_file_location("verify_preflight", Path.cwd() / HERE)
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)
ROOT = verify.ROOT
out = Path(sys.argv[1])
indices = [int(i) for i in sys.argv[2:]]
snapshot = verify._snapshot()
recorded = verify._recorded_by_the_snapshot()
journal = verify._journal()
for index in indices:
    name, path, edits = verify.INJECTIONS[index]
    target = ROOT / path
    original = target.read_bytes()
    text = original.decode("utf-8")
    row = {"index": index, "id": name, "file": path, "expected_class": verify.EXPECTED[name],
           "minted_for_the_injection": path in recorded}
    hits = [text.count(old) for old, _ in edits]
    if hits != [1] * len(edits):
        row["outcome"] = "EDIT_DOES_NOT_HIT_EXACTLY_ONCE:" + str(hits)
    else:
        for old, new in edits:
            text = text.replace(old, new)
        try:
            compile(text, path, "exec")
        except SyntaxError as error:
            row["outcome"] = "INJECTION_DOES_NOT_COMPILE:" + str(error)
    started = time.time()
    if "outcome" not in row:
        try:
            target.write_text(text, encoding="utf-8")
            if row["minted_for_the_injection"]:
                assert verify._mint().returncode == 0, name
            code, failures, summary, ran = verify._suite(fail_fast=True, classes=(row["expected_class"],))
            row.update(outcome=verify._outcome(code, failures), ran=ran, summary=summary,
                       first_caught_by=[f["case"] for f in failures], failures=failures)
        finally:
            target.write_bytes(original)
            if row["minted_for_the_injection"]:
                verify._mint()
        if verify._snapshot() != snapshot:
            row["stopped"] = "SNAPSHOT_DID_NOT_COME_BACK"
        moved_journal = verify._journal_moved(journal)
        if any(moved_journal.values()):
            row["stopped"] = "CREATOR_JOURNAL_DID_NOT_COME_BACK"
            row["journal"] = moved_journal
    row["seconds"] = round(time.time() - started, 1)
    with out.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")
    print(json.dumps({k: row.get(k) for k in ("index", "id", "outcome", "seconds")}), flush=True)
    if row.get("stopped"):
        sys.exit(2)
