"""Run-level DEI probe: every metric at named periods, install -> Run -> public row -> cold read.

Records each re.fullmatch rejection of a DEI release namespace (a string the widened
pattern accepts and the frozen pattern refuses) with the chain of frames from the
first #47 historical_* frame down to the rejecting line, in the parent process and
in the separate-process cold read. Network and DNS are blocked throughout.

Usage (from the root of a runtime tree carrying the registration patch):
    SOURCE_ROOT=<root> python3 dei_run_probe.py <out dir> <company:report_end> ...
"""
import collections
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import traceback
from pathlib import Path
from unittest.mock import patch

RUNTIME = Path.cwd()
sys.path.insert(0, str(RUNTIME / "scripts"))
OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
CASES = [tuple(item.split(":")) for item in sys.argv[2:]]
SOURCE_ROOT = Path(os.environ["SOURCE_ROOT"])
ONLY = [m for m in os.environ.get("ONLY_METRICS", "").split(",") if m]

WATCH = r'''
import re, sys, collections
from pathlib import Path
_WIDE = r"https?://xbrl\.sec\.gov/dei/\d{4}(?:q[1-4]|-\d{2}-\d{2})?"
_original = re.fullmatch
CHAINS = collections.Counter()
def _chain():
    frames, frame = [], sys._getframe(2)
    while frame is not None:
        name = Path(frame.f_code.co_filename).name
        if "/scripts/vnext/" in frame.f_code.co_filename:
            frames.append("%s:%s" % (name, frame.f_code.co_name))
        frame = frame.f_back
    frames.reverse()
    first = next((i for i, f in enumerate(frames) if f.startswith("historical_")), 0)
    return " > ".join(frames[first:])
def _watched(pattern, string, flags=0):
    result = _original(pattern, string, flags)
    text = pattern.pattern if hasattr(pattern, "pattern") else str(pattern)
    if (result is None and "xbrl" in text and "dei" in text and isinstance(string, str)
            and _original(_WIDE, string) is not None):
        CHAINS[_chain()] += 1
    return result
re.fullmatch = _watched
'''
exec(WATCH)  # noqa: S102 - the probe's own watch, same code in the cold-read child

from vnext.historical_coverage import declared_metric_ids  # noqa: E402
from vnext.historical_projection import render_historical_run  # noqa: E402
from vnext.historical_run import create_historical_run, install_historical_run_inputs  # noqa: E402
from vnext.normal_period_selection import resolve_period_selection  # noqa: E402

REPLAY = WATCH.replace("%", "%%") + r'''
import json, socket
from unittest.mock import patch
sys.path.insert(0, %r)
out = {}
with patch.object(socket.socket, 'connect', side_effect=AssertionError('no net')), \
     patch.object(socket, 'getaddrinfo', side_effect=AssertionError('no dns')):
    from vnext.run_store import load_frozen_run
    try:
        m, records, _ = load_frozen_run(run_dir=Path(%r), repo_root=Path(%r))
        r = [x for x in records if x['record_type'] == 'METRIC_RESULT' and x.get('metric_id') == %r]
        out.update(status=m['status'], run_id=m['run_id'], result_id=r[0]['result_id'] if len(r) == 1 else None)
    except Exception as error:
        out.update(error=type(error).__name__ + ':' + str(error)[:300])
out['dei_chains'] = dict(CHAINS)
print(json.dumps(out))
'''
NO_NET = lambda: patch.object(socket.socket, "connect", side_effect=AssertionError("net"))  # noqa: E731
NO_DNS = lambda: patch.object(socket, "getaddrinfo", side_effect=AssertionError("dns"))  # noqa: E731

metrics, _ = declared_metric_ids(repo_root=RUNTIME)
metrics = [m for m in metrics if not ONLY or m in ONLY]
rows, started = [], time.time()
for company, report_end in CASES:
    label = company + "-" + report_end
    before = collections.Counter(CHAINS)
    try:
        with NO_NET(), NO_DNS():
            selection = resolve_period_selection(repo_root=SOURCE_ROOT, company_id=company,
                                                 report_end=report_end)
    except Exception as error:  # noqa: BLE001 - measured, reported
        rows.append({"case": label, "metric_id": None, "stage": "PERIOD_SELECTION",
                     "error": type(error).__name__ + ":" + str(error)[:300],
                     "dei_chains": dict(CHAINS - before)})
        continue
    for metric in metrics:
        before = collections.Counter(CHAINS)
        row = {"case": label, "company_id": company, "report_end": report_end, "metric_id": metric}
        data_root, run_dir = OUT / ("data-" + label + "-" + metric), OUT / ("run-" + label + "-" + metric)
        stage = "INSTALL"
        try:
            with NO_NET(), NO_DNS():
                installed = install_historical_run_inputs(data_root=data_root, company_id=company,
                                                          metric_id=metric, period_selection=selection,
                                                          source_root=SOURCE_ROOT)
                stage = "RUN"
                run = create_historical_run(data_root=data_root, run_dir=run_dir, company_id=company,
                                            metric_id=metric, binding_id=installed["binding"]["binding_id"],
                                            freeze=True)
                stage = "ROW"
                rendered = render_historical_run(data_root=data_root, run_dir=run_dir, frozen=True,
                                                 persist=True)
            row.update(stage="PUBLIC_ROW", run_id=run["manifest"]["run_id"],
                       result_id=run["result"]["result_id"], value=run["result"]["value"],
                       quality=run["result"]["quality"], publication=run["result"]["publication"],
                       reason_code=run["result"]["reason_code"], new_calls=run["new_calls"],
                       row_hash=rendered["receipt"]["row_hash"])
            completed = subprocess.run([sys.executable, "-c", REPLAY % (
                str(RUNTIME / "scripts"), str(run_dir), str(data_root), metric)],
                capture_output=True, text=True, cwd=str(OUT), timeout=1800)
            row["cold_read"] = (json.loads(completed.stdout.strip().splitlines()[-1])
                                if completed.returncode == 0 and completed.stdout.strip()
                                else {"error": completed.stderr[-600:]})
        except Exception as error:  # noqa: BLE001 - per position
            row.update(stage="FAILED_AT_" + stage, error_type=type(error).__name__,
                       error=str(error)[:400],
                       where=[("%s:%s" % (Path(f.filename).name, f.name))
                              for f in traceback.extract_tb(error.__traceback__)][-4:])
        row["dei_chains"] = dict(CHAINS - before)
        rows.append(row)
        shutil.rmtree(data_root, ignore_errors=True)
        (OUT / "probe.json").write_text(json.dumps({"rows": rows, "seconds": round(time.time() - started),
                                                    "chains_total": dict(CHAINS)},
                                                   indent=1, sort_keys=True, default=str) + "\n")
        print(label, metric, row["stage"], str(row.get("value") if row["stage"] == "PUBLIC_ROW"
                                                  else row.get("error"))[:100],
              sum(row["dei_chains"].values()), flush=True)
print("DONE", round(time.time() - started), flush=True)
