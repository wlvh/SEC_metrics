import sys, json, glob
from pathlib import Path
sys.path.insert(0, "scripts")
from vnext.normal_period_selection import resolve_period_selection
from vnext.historical_accession_results import resolve_historical_accession_metrics
from vnext.normal_history_plan import checkpoint_replayed_once
root = Path(sys.argv[1]); out = {}
for position in sys.argv[3:]:
    company, end = position.split(":")
    with checkpoint_replayed_once():
        sel = resolve_period_selection(repo_root=root, company_id=company, report_end=end)
        c = resolve_historical_accession_metrics(repo_root=root, company_id=company, period_selection=sel)
    for m, row in c["metrics"].items():
        insp = row["inspection"] or {}
        out[position + ":" + m] = {"result_id": row["result"]["result_id"], "value": row["result"]["value"],
                                   "reason": row["result"]["reason_code"],
                                   "successor": insp.get("dated_release_successor"),
                                   "status": insp.get("status"), "why": insp.get("reason")}
        print(position, m, json.dumps(out[position + ":" + m])[:400], flush=True)
Path(sys.argv[2]).write_text(json.dumps(out, indent=1, sort_keys=True))
