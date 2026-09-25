"""Targeted native Runs under one closure: named metrics at one named period.

The full-frame driver's body - install, create, freeze, public row, and a
separate-process cold read of every Run - for the positions a change moved.
Run from the root of a runtime tree carrying the registration patch. With
SOURCE_ROOT set, the period is selected from that source root and installed
from it (a recorded root such as the repartitioned one in
tests/vnext/historical_block_fixture.py); its checkpoint must be registered in
this runtime tree's own trust journal, which means the root must have been
built by this tree.

Usage:
    [SOURCE_ROOT=<source root>] python3 \
        docs/evidence/issue47_history/targeted-round-30a7934b/targeted_runs.py \
        <output directory> <label> <company_id> <report_end> <metric,metric,...>
"""
import json, socket, subprocess, sys, time
from pathlib import Path
from unittest.mock import patch

import os
RUNTIME = Path(os.environ.get("RUNTIME") or Path.cwd())
sys.path.insert(0, str(RUNTIME / "scripts"))
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
label, company, report_end = sys.argv[2], sys.argv[3], sys.argv[4]
metrics = sys.argv[5].split(",")

from vnext.normal_period_selection import resolve_period_selection
from vnext.historical_run import install_historical_run_inputs, create_historical_run
from vnext.historical_projection import render_historical_run

NO_NET = lambda: patch.object(socket.socket, "connect", side_effect=AssertionError("Network forbidden"))
NO_DNS = lambda: patch.object(socket, "getaddrinfo", side_effect=AssertionError("DNS forbidden"))
REPLAY = """
import json, socket, sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, %r)
with patch.object(socket.socket, 'connect', side_effect=AssertionError('no net')), \\
     patch.object(socket, 'getaddrinfo', side_effect=AssertionError('no dns')):
    from vnext.run_store import load_frozen_run
    m, records, _ = load_frozen_run(run_dir=Path(%r), repo_root=Path(%r))
    r = [x for x in records if x['record_type'] == 'METRIC_RESULT' and x.get('metric_id') == %r]
    assert len(r) == 1
print(json.dumps({'run_id': m['run_id'], 'status': m['status'], 'value_sha256': __import__('hashlib').sha256(str(r[0]['value']).encode()).hexdigest(),
                  'quality': r[0]['quality'], 'publication': r[0]['publication'], 'result_id': r[0]['result_id']}))
"""
positions, started = [], time.time()
SOURCE_ROOT = Path(os.environ["SOURCE_ROOT"]) if os.environ.get("SOURCE_ROOT") else None
with NO_NET(), NO_DNS():
    selection = resolve_period_selection(repo_root=SOURCE_ROOT or RUNTIME, company_id=company, report_end=report_end)
for metric in metrics:
    row = {"case": label, "company_id": company, "report_end": report_end, "metric_id": metric,
           "selection_id": selection["selection_id"]}
    data_root = out / ("data-" + label + "-" + metric)
    run_dir = out / ("run-" + label + "-" + metric)
    try:
        with NO_NET(), NO_DNS():
            installed = install_historical_run_inputs(data_root=data_root, company_id=company,
                                                      metric_id=metric, period_selection=selection,
                                                      **({"source_root": SOURCE_ROOT} if SOURCE_ROOT else {}))
            run = create_historical_run(data_root=data_root, run_dir=run_dir, company_id=company,
                                        metric_id=metric, binding_id=installed["binding"]["binding_id"],
                                        freeze=True)
            rendered = render_historical_run(data_root=data_root, run_dir=run_dir, frozen=True, persist=True)
        row.update(stage="PUBLIC_ROW", run_id=run["manifest"]["run_id"],
                   requirement_closure_hash=run["manifest"]["requirement_closure_hash"],
                   result_id=run["result"]["result_id"], value=run["result"]["value"],
                   quality=run["result"]["quality"], publication=run["result"]["publication"],
                   reason_code=run["result"]["reason_code"], new_calls=run["new_calls"],
                   row_hash=rendered["receipt"]["row_hash"], evidence_count=len(rendered["evidence"]))
        completed = subprocess.run([sys.executable, "-c", REPLAY % (str(RUNTIME / "scripts"), str(run_dir), str(data_root), metric)],
                                   capture_output=True, text=True, cwd=str(out))
        row["separate_process_replay"] = (json.loads(completed.stdout.strip().splitlines()[-1])
                                          if completed.returncode == 0 else {"error": completed.stderr[-400:]})
    except Exception as error:  # noqa: BLE001 - per position
        row.update(stage="FAILED", error_type=type(error).__name__, error=str(error)[:300],
                   category=getattr(error, "category", None))
    positions.append(row)
    (out / ("matrix-" + label + ".json")).write_text(json.dumps({"positions": positions,
        "duration_seconds": round(time.time() - started, 1), "calls": {"provider": 0, "paid": 0, "sec": 0}},
        indent=1, sort_keys=True, default=str) + "\n")
    print(label, metric, row["stage"], str(row.get("value") or row.get("error") or "")[:120], flush=True)
