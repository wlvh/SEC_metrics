"""Every routed metric for JPMorgan FY2025 on the recorded root with the re-derived index.

The one period here whose selection reads history blocks. Each metric is
installed from that root into its own fresh data root, run natively under
issue_47_v1, frozen and rendered; the first frozen Run of each route family is
read back in a separate process. Writes after every position. Run from the root
of a runtime tree carrying the registration patch; the recorded root is the one
``recorded_bank_run.py`` builds (``RECORDED_TEST_ONLY``).

Usage:
    python3 docs/evidence/issue47_history/financial-route/recorded_bank_sweep.py \
        <recorded source root> <output directory> [<metric_id> ...]
"""
import json, socket, subprocess, sys, time
from pathlib import Path
from unittest.mock import patch

RUNTIME = Path.cwd()
sys.path.insert(0, str(RUNTIME / "scripts"))
SOURCE = Path(sys.argv[1]); out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
ONLY = sys.argv[3:] or None
from vnext.historical_coverage import WIRED_HISTORICAL_METRICS, STRUCTURAL_APPLICABILITY_METRICS
from vnext.historical_structural_results import SPEC_PATHS as GATED, structurally_not_applicable
from vnext.historical_capacity_results import out_of_scope
from vnext.normal_period_selection import resolve_period_selection
from vnext.historical_run import install_historical_run_inputs, create_historical_run
from vnext.historical_projection import render_historical_run
COMPANY, END = "jpmorgan_chase", "2025-12-31"
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
print(json.dumps({'run_id': m['run_id'], 'status': m['status'], 'value': r[0]['value'], 'quality': r[0]['quality']}))
"""
with NO_NET(), NO_DNS():
    selection = resolve_period_selection(repo_root=SOURCE, company_id=COMPANY, report_end=END)
routed = sorted(set(WIRED_HISTORICAL_METRICS) | {m for m in GATED if structurally_not_applicable(
    repo_root=RUNTIME, company_id=COMPANY, metric_id=m)} | ({"B13"} if out_of_scope(
    repo_root=RUNTIME, company_id=COMPANY) else set()))
if ONLY: routed = [m for m in routed if m in ONLY]
positions, started, read_back = [], time.time(), set()
for metric in routed:
    row = {"metric_id": metric}
    data_root = out / ("data-" + metric); run_dir = out / ("run-" + metric)
    try:
        with NO_NET(), NO_DNS():
            installed = install_historical_run_inputs(data_root=data_root, company_id=COMPANY,
                metric_id=metric, period_selection=selection, source_root=SOURCE)
            row["installed_proofs"] = len(installed["installed"]["source_proofs"])
            run = create_historical_run(data_root=data_root, run_dir=run_dir, company_id=COMPANY,
                metric_id=metric, binding_id=installed["binding"]["binding_id"], freeze=True)
        row.update(stage="NATIVE_RUN_FROZEN", run_status=run["manifest"]["status"],
                   target_period=run["manifest"]["target_period"], value=run["result"]["value"],
                   quality=run["result"]["quality"], publication=run["result"]["publication"],
                   reason_code=run["result"]["reason_code"], applicability=run["result"]["applicability"],
                   new_calls=run["new_calls"])
        with NO_NET(), NO_DNS():
            rendered = render_historical_run(data_root=data_root, run_dir=run_dir, frozen=True, persist=True)
        row.update(stage="PUBLIC_ROW", row_status=rendered["row"]["status"], row_value=rendered["row"]["value"],
                   evidence_count=len(rendered["evidence"]))
        family = row["reason_code"] if row["applicability"] != "APPLICABLE" else metric[0]
        if family not in read_back:
            done = subprocess.run([sys.executable, "-c", REPLAY % (str(RUNTIME / "scripts"), str(run_dir),
                                   str(data_root), metric)], capture_output=True, text=True, cwd=str(out))
            row["separate_process_replay"] = (json.loads(done.stdout.strip().splitlines()[-1])
                                              if done.returncode == 0 else {"error": done.stderr[-300:]})
            read_back.add(family)
    except Exception as error:  # noqa: BLE001 - per position
        row.update(stage="FAILED", error_type=type(error).__name__, error=str(error)[:300])
    positions.append(row)
    (out / "bank-sweep.json").write_text(json.dumps({"record_type": "ISSUE_47_RECORDED_BANK_SWEEP",
        "source_root_is": "RECORDED_TEST_ONLY", "company_id": COMPANY, "report_end": END,
        "selection_loaded_inventories": selection["loaded_inventories"], "positions": positions,
        "duration_seconds": round(time.time() - started, 1),
        "calls": {"provider": 0, "paid": 0, "sec": 0}}, indent=1, sort_keys=True) + "\n")
    print("%-4s %-18s %-8s %s" % (metric, row["stage"], str(row.get("quality", ""))[:8],
          str(row.get("error") or row.get("value") or row.get("reason_code"))[:110]), flush=True)
