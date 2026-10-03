"""Compare each re-run injection outcome with the committed record: outcome and catching cases.

Usage: python3 compare_reruns.py <clone the re-run ran in>
"""
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
R = Path(sys.argv[1])  # the clone the re-run ran in
H = "docs/evidence/issue47_history/"
PAIRS = {
    "model_start": H + "model-egress/model-start-injections.json",
    "vm_start": H + "acquisition-wiring/vm-start-injections.json",
    "batch": H + "acquisition-wiring/batch-injections.json",
    "visibility": H + "e01-item-text/visibility-injections.json",
    "block": H + "block-resident-filings/fault-injections.json",
    "part_iii": H + "part-iii-statement-review/fault-injections.json",
    "b03": H + "b03-depreciation-scope/fault-injections.json",
    "b03_route": H + "b03-depreciation-scope/route-fault-injections.json",
}


def rows(value):
    if isinstance(value, dict):
        value = value.get("results") or value.get("injections") or []
    return {row["id"]: row for row in value}


def caught(row):
    return sorted(row.get("failed_cases") or row.get("caught_by") or [])


report = {}
for name, relative in PAIRS.items():
    committed = rows(json.loads(subprocess.run(["git", "-C", str(REPO), "show", "6923b19e:" + relative],
                                                capture_output=True, text=True, check=True).stdout))
    rerun_path = R / relative
    # A script that stopped before writing leaves the clone's committed copy in
    # place, which would compare as "the same" without having run anything.
    written = rerun_path.exists() and rerun_path.stat().st_mtime > (R / ".git" / "HEAD").stat().st_mtime
    rerun = rows(json.loads(rerun_path.read_text())) if written else {}
    same = [i for i in committed if i in rerun and committed[i]["outcome"] == rerun[i]["outcome"]
            and caught(committed[i]) == caught(rerun[i])]
    differ = {i: {"committed": [committed[i]["outcome"], caught(committed[i])],
                  "rerun": [rerun[i]["outcome"], caught(rerun[i])]}
              for i in committed if i in rerun and i not in same}
    report[name] = {"written_by_the_rerun": written, "committed": len(committed), "rerun": len(rerun),
                    "same": len(same),
                    "differ": differ, "not_rerun": sorted(set(committed) - set(rerun)),
                    "only_in_rerun": sorted(set(rerun) - set(committed))}
print(json.dumps(report, indent=1))
