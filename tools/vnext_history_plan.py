"""Emit the Issue #47 historical source catalog and deduplicated gap plan.

Purpose:
    Turn the repository's own saved SEC submissions metadata into an executable
    five-year target inventory and the deduplicated list of documents that are
    still missing. It reads saved bytes only: no SEC request is made, no metric
    is executed, and no acquisition is authorized by running it.

Call relationships:
    Developers and the Issue #47 evidence archive call this script. It calls
    ``scripts/vnext/normal_history_catalog.py`` and writes one JSON report.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from vnext.normal_history_catalog import inspect_historical_plans  # noqa: E402


def _summary(report):
    lines = []
    for plan in report["companies"]:
        if plan.get("plan_status") != "PLAN_READY":
            lines.append("%-36s %s %s" % (plan["company_id"], plan.get("plan_status"),
                                          str(plan.get("reason"))[:80]))
            continue
        kinds = plan["new_acquisition_by_kind"]
        lines.append("%-36s targets=%d declared_get=%d new_acquisition=%d (%s) limitations=%d "
                     "identity_ready=%s"
                     % (plan["company_id"], len(plan["target_candidates"]),
                        plan["deduplicated_known_get_count"], plan["new_acquisition_count"],
                        ",".join("%s=%d" % item for item in sorted(kinds.items())) or "-",
                        len(plan["catalog_limitations"]),
                        ",".join(plan["annual_identity_ready_report_dates"]) or "-"))
    ready = [p for p in report["companies"] if p.get("plan_status") == "PLAN_READY"]
    totals = {}
    for plan in ready:
        for kind, count in plan["new_acquisition_by_kind"].items():
            totals[kind] = totals.get(kind, 0) + count
    lines.append("TOTAL new acquisitions across %d planned companies: %d (%s)"
                 % (len(ready), sum(p["new_acquisition_count"] for p in ready),
                    ",".join("%s=%d" % item for item in sorted(totals.items())) or "-"))
    # Index discovery is not complete everywhere, so this total is a floor.
    pending = [p for p in ready if p["further_requests_pending_index_discovery"]]
    lines.append("This total is a FLOOR: %d of %d companies still have undiscovered accession "
                 "indexes, and each one can declare further documents."
                 % (len(pending), len(ready)))
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--company", action="append", dest="companies",
                        help="Restrict to one configured company_id; repeatable.")
    parser.add_argument("--years", type=int, default=5,
                        help="Number of most recent annual report ends to target.")
    parser.add_argument("--output", type=Path,
                        help="Write the full JSON report to this path.")
    arguments = parser.parse_args(argv)
    report = inspect_historical_plans(repo_root=REPO_ROOT, company_ids=arguments.companies,
                                      count=arguments.years)
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(json.dumps(report, ensure_ascii=False, indent=1,
                                               sort_keys=True) + "\n", encoding="utf-8")
    print(_summary(report))
    blocked = [p for p in report["companies"] if p.get("plan_status") != "PLAN_READY"]
    return 2 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
