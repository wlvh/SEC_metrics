"""Where the historical B06 cascade stops at each frame period, and why (zero calls).

Usage: python3 docs/evidence/issue47_history/b06-older-years/probe.py <source root> <plan.tsv> <out.json>
Resumable: a position already in the output is not asked again.
"""
import json, sys, time, traceback
from pathlib import Path
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "scripts"))
from vnext.historical_debt_results import resolve_historical_debt_metric
from vnext.normal_period_selection import resolve_period_selection
from vnext.normal_history_plan import checkpoint_replayed_once

def main(root, plan, out_path):
    root = Path(root).resolve()
    rows = [line.split("\t")[:3] for line in open(plan) if line.strip()]
    rows.sort(key=lambda r: (r[2] >= "2025-01-01", r[1], r[2]))   # older years first
    out = json.loads(Path(out_path).read_text()) if Path(out_path).exists() else {}
    with checkpoint_replayed_once():
        for label, company, end in rows:
            key = company + ":" + end
            if key in out:
                continue
            started = time.time()
            try:
                sel = resolve_period_selection(repo_root=root, company_id=company, report_end=end)
                comp = resolve_historical_debt_metric(repo_root=root, company_id=company,
                                                      metric_id="B06", period_selection=sel)
                result = comp["result"]
                row = {"stage": comp.get("cascade_stage"), "spec_path": comp.get("spec_path"),
                       "quality": result.get("quality"), "reason_code": result.get("reason_code"),
                       "publication": result.get("publication"), "value": result.get("value"),
                       "selection": json.loads(json.dumps(comp.get("selection"), default=str))}
            except Exception as error:
                row = {"error": type(error).__name__ + ":" + str(error)[:400],
                       "trace_tail": traceback.format_exc().splitlines()[-6:]}
            row["seconds"] = int(time.time() - started)
            out[key] = row
            sel_s = json.dumps(row.get("selection"))[:200] if "selection" in row else row.get("error")
            print(key, row.get("stage"), row.get("reason_code"), row.get("value"), sel_s, row["seconds"], "s", flush=True)
            Path(out_path + ".partial").write_text(json.dumps(out, indent=1, sort_keys=True))
            Path(out_path + ".partial").replace(out_path)

if __name__ == "__main__":
    main(*sys.argv[1:])
