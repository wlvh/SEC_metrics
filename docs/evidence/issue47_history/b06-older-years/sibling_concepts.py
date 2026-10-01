"""Experiment only: how far the B06 fallback gets if its required text blocks accept the
taxonomy's sibling concepts some older filings use. Monkeypatches b06_disclosure._note in
this process; nothing is written to the repository. Zero calls."""
import json, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "scripts"))
from vnext import b06_disclosure as disclosure
from vnext.historical_debt_results import resolve_historical_debt_metric
from vnext.normal_period_selection import resolve_period_selection
from vnext.normal_history_plan import checkpoint_replayed_once

ALTERNATIVES = {
    "us-gaap:DebtDisclosureTextBlock": ["us-gaap:LongTermDebtTextBlock"],
    "us-gaap:ScheduleOfDebtInstrumentsTextBlock": ["us-gaap:ScheduleOfDebtTableTextBlock"],
}
frozen = disclosure._note
def widened(parsed, name, target):
    try:
        return frozen(parsed, name, target)
    except Exception as error:
        if "DISCLOSURE_NOTE_MISSING_OR_AMBIGUOUS" not in str(error):
            raise
        for alt in ALTERNATIVES.get(name, []):
            try:
                return frozen(parsed, alt, target)
            except Exception:
                continue
        raise
disclosure._note = widened

root = Path(sys.argv[1]).resolve()
out = {}
with checkpoint_replayed_once():
    for position in sys.argv[2:]:
        company, end = position.rsplit(":", 1)
        sel = resolve_period_selection(repo_root=root, company_id=company, report_end=end)
        try:
            comp = resolve_historical_debt_metric(repo_root=root, company_id=company, metric_id="B06",
                                                  period_selection=sel)
            r = comp["result"]; s = comp.get("selection") or {}
            out[position] = {"stage": comp.get("cascade_stage"), "reason_code": r.get("reason_code"),
                             "value": r.get("value"), "reason": (s.get("reason") if isinstance(s, dict) else None)}
        except Exception as error:
            out[position] = {"error": type(error).__name__ + ":" + str(error)[:300]}
        print(position, json.dumps(out[position])[:400], flush=True)
