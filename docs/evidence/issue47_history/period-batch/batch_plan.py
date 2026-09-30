"""The full frame's runnable positions on a source root, from the coverage frame's own rules.

``../native-run-batch-2026-09-27/batch_plan.py`` planned over the runtime tree's
own saved sources. After the acquisition the originals live in a source root
restored from the export, so the plan is made there: for every company and
every target period whose original that root holds (PERIOD_ESTABLISHED), the
metrics that have a route - wired, structurally not applicable to the company,
or B13 outside the approved definition's scope, the same three tests
historical_coverage uses to say "implemented". Planning replays the
acquisition checkpoint once per ledger state (the planner's own block).

Written as one line per period for frame_batch.py; nothing runs here.

Usage (from the runtime tree):
    SOURCE_ROOT=<root> python3 batch_plan.py > plan.tsv   # label, company, report_end, metrics
"""
import os
import sys
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / "scripts"))

from vnext import historical_capacity_results as capacity  # noqa: E402
from vnext import historical_structural_results as structural  # noqa: E402
from vnext.historical_coverage import WIRED_HISTORICAL_METRICS, declared_metric_ids  # noqa: E402
from vnext.normal_history_plan import checkpoint_replayed_once, plan_historical_sources  # noqa: E402
from vnext.projector import _load_registry  # noqa: E402

SOURCE_ROOT = Path(os.environ["SOURCE_ROOT"])
metrics, _policy = declared_metric_ids(repo_root=ROOT)
with checkpoint_replayed_once():
    for company in _load_registry(repo_root=ROOT):
        company_id = company["company_id"]
        plan = plan_historical_sources(repo_root=SOURCE_ROOT, company_id=company_id, count=5)
        ready = set(plan["annual_identity_ready_report_dates"])
        for candidate in plan["target_candidates"]:
            report_end = candidate["report_date"]
            if candidate["metadata_status"] != "METADATA_CANDIDATE_READY" or report_end not in ready:
                continue
            runnable = [m for m in metrics
                        if m in WIRED_HISTORICAL_METRICS
                        or structural.structurally_not_applicable(repo_root=ROOT,
                                                                  company_id=company_id,
                                                                  metric_id=m)
                        or capacity.out_of_scope(repo_root=ROOT, company_id=company_id,
                                                 metric_id=m)]
            label = company_id.split("_")[0] + "-" + report_end[:4]
            print("\t".join([label, company_id, report_end, ",".join(runnable)]), flush=True)
