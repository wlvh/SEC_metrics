"""The full frame's runnable positions, derived from the coverage frame's own rules.

For every company and every target period whose original is saved
(PERIOD_ESTABLISHED), the metrics that have a route there: wired, structurally
not applicable to this company, or B13 outside the approved definition's
scope - the same three tests historical_coverage uses to say "implemented".
Written as one line per period for a shell driver; nothing runs here.

Usage (from a runtime tree):
    python3 batch_plan.py > plan.tsv    # label, company, report_end, metrics
"""
import sys
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / "scripts"))

from vnext import historical_capacity_results as capacity  # noqa: E402
from vnext import historical_structural_results as structural  # noqa: E402
from vnext.historical_coverage import WIRED_HISTORICAL_METRICS, declared_metric_ids  # noqa: E402
from vnext.normal_history_plan import plan_historical_sources  # noqa: E402
from vnext.projector import _load_registry  # noqa: E402

metrics, _policy = declared_metric_ids(repo_root=ROOT)
for company in _load_registry(repo_root=ROOT):
    company_id = company["company_id"]
    plan = plan_historical_sources(repo_root=ROOT, company_id=company_id, count=5)
    ready = set(plan["annual_identity_ready_report_dates"])
    for candidate in plan["target_candidates"]:
        report_end = candidate["report_date"]
        if candidate["metadata_status"] != "METADATA_CANDIDATE_READY" or report_end not in ready:
            continue
        runnable = [m for m in metrics
                    if m in WIRED_HISTORICAL_METRICS
                    or structural.structurally_not_applicable(repo_root=ROOT, company_id=company_id,
                                                              metric_id=m)
                    or capacity.out_of_scope(repo_root=ROOT, company_id=company_id, metric_id=m)]
        label = company_id.split("_")[0] + "-" + report_end[:4]
        print("\t".join([label, company_id, report_end, ",".join(runnable)]))
