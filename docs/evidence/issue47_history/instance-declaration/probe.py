import sys, json
from pathlib import Path
sys.path.insert(0, "scripts")
from vnext.normal_history_plan import checkpoint_replayed_once
from vnext.normal_period_selection import resolve_period_selection
from vnext.historical_governance_results import resolve_historical_governance_metric
from vnext.historical_debt_results import resolve_historical_debt_metric
ROOT = Path(sys.argv[1])
out = {}
with checkpoint_replayed_once():
    for label in sys.argv[2:]:
        company, end = label.split("@")
        try:
            sel = resolve_period_selection(repo_root=ROOT, company_id=company, report_end=end)
        except Exception as e:
            out[label] = {"selection_error": str(e)[:300]}; print(label, "SELECTION", str(e)[:200], flush=True); continue
        for metric, fn in (("C04", resolve_historical_governance_metric), ("B06", resolve_historical_debt_metric)):
            try:
                comp = fn(repo_root=ROOT, company_id=company, metric_id=metric, period_selection=sel)
                lim = comp.get("limitation") or (comp.get("case") or {}).get("selection") or comp.get("selection")
                res = comp.get("result") or (comp.get("case") or {}).get("result") or {}
                txt = json.dumps(lim)[:400] if lim else None
                out[label + ":" + metric] = {"reason_code": res.get("reason_code"), "limitation": txt, "keys": sorted(comp)[:20]}
                print(label, metric, res.get("reason_code"), txt, flush=True)
            except Exception as e:
                out[label + ":" + metric] = {"error": type(e).__name__ + ":" + str(e)[:400]}
                print(label, metric, "ERROR", type(e).__name__, str(e)[:300], flush=True)
json.dump(out, open(sys.argv[0] + ".json", "w"), indent=1)
