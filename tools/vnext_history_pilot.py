"""Resolve Issue #47 historical target periods and record the actual outcome.

Purpose:
    Run the explicit historical period selection and catalog resolution over the
    target periods a plan says are reachable from saved bytes, and write one
    machine-readable outcome per company-period-metric. Every outcome is the
    real one: a value, a source limitation, or an implementation gap, each with
    the filing identity it came from.

Call relationships:
    Developers and the Issue #47 evidence archive call this script. It calls
    ``scripts/vnext/normal_period_selection.py`` and
    ``scripts/vnext/historical_results.py``. It performs no SEC or model request
    and creates no publication.
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from vnext.historical_results import resolve_historical_companyfacts_metrics  # noqa: E402
from vnext.normal_history_catalog import plan_historical_sources  # noqa: E402
from vnext.normal_period_selection import resolve_period_selection  # noqa: E402


DEFAULT_METRICS = ("B02", "B04", "B05")


def _outcome(*, repo_root, company_id, report_end, metrics):
    try:
        selection = resolve_period_selection(repo_root=repo_root, company_id=company_id,
                                             report_end=report_end)
    except (ValueError, KeyError, TypeError, OSError) as error:
        return {"company_id": company_id, "report_end": report_end,
                "status": "PERIOD_SELECTION_BLOCKED", "reason": str(error),
                "error_type": type(error).__name__,
                "category": getattr(error, "category", "IMPLEMENTATION_ERROR")}
    try:
        component = resolve_historical_companyfacts_metrics(repo_root=repo_root,
                                                            company_id=company_id,
                                                            period_selection=selection)
    except (ValueError, KeyError, TypeError, OSError) as error:
        return {"company_id": company_id, "report_end": report_end,
                "selection_id": selection["selection_id"],
                "current_accession": selection["current_filing"]["accessionNumber"],
                "prior_accession": (selection["prior_filing"] or {}).get("accessionNumber"),
                "status": "SOURCE_BLOCKED", "reason": str(error),
                "error_type": type(error).__name__,
                "category": getattr(error, "category", "IMPLEMENTATION_ERROR")}
    rows = []
    for metric_id in metrics:
        result = component["metrics"][metric_id]["result"]
        rows.append({"metric_id": metric_id, "value": result["value"], "unit": result["unit"],
                     "quality": result["quality"], "publication": result["publication"],
                     "reason_code": result["reason_code"],
                     "period_start": result["period_start"], "period_end": result["period_end"],
                     "applicability": result["applicability"]})
    return {"company_id": company_id, "report_end": report_end,
            "selection_id": selection["selection_id"],
            "component_id": component["component_id"],
            "fiscal_year": component["periods"]["current"]["fiscal_year"],
            "period_start": component["periods"]["current"]["period_start"],
            "current_accession": component["filings"]["current"]["accessionNumber"],
            "prior_accession": (component["filings"]["prior"] or {}).get("accessionNumber"),
            "prior_fiscal_year": (component["periods"]["prior"] or {}).get("fiscal_year"),
            "prior_error": component["prior_error"],
            "status": "RESOLVED", "metrics": rows,
            "calls": component["calls"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--company", action="append", dest="companies", required=True,
                        help="Configured company_id; repeatable.")
    parser.add_argument("--years", type=int, default=5,
                        help="How many recent annual report ends to attempt per company.")
    parser.add_argument("--metric", action="append", dest="metrics",
                        help="Catalog Company Facts metric id; repeatable.")
    parser.add_argument("--output", type=Path, help="Write the JSON report to this path.")
    arguments = parser.parse_args(argv)
    metrics = tuple(arguments.metrics or DEFAULT_METRICS)
    outcomes = []
    with patch.object(socket.socket, "connect", side_effect=AssertionError("Network forbidden")), \
         patch.object(socket, "getaddrinfo", side_effect=AssertionError("DNS forbidden")):
        for company_id in arguments.companies:
            plan = plan_historical_sources(repo_root=REPO_ROOT, company_id=company_id,
                                           count=arguments.years)
            for candidate in plan["target_candidates"]:
                outcomes.append(_outcome(repo_root=REPO_ROOT, company_id=company_id,
                                         report_end=candidate["report_date"], metrics=metrics))
    resolved = [o for o in outcomes if o["status"] == "RESOLVED"]
    exact = sum(1 for o in resolved for row in o["metrics"] if row["quality"] == "EXACT")
    report = {"record_type": "HISTORICAL_PERIOD_PILOT_REPORT", "schema_version": 1,
              "requested_metrics": list(metrics), "requested_years": arguments.years,
              "companies": list(arguments.companies), "outcomes": outcomes,
              "target_period_count": len(outcomes), "resolved_period_count": len(resolved),
              "exact_metric_position_count": exact,
              "attempted_metric_position_count": len(outcomes) * len(metrics),
              "calls": {"provider": 0, "paid": 0, "sec": 0},
              "native_run_created": False, "production_authorized": False}
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(json.dumps(report, ensure_ascii=False, indent=1,
                                               sort_keys=True) + "\n", encoding="utf-8")
    for outcome in outcomes:
        if outcome["status"] != "RESOLVED":
            print("%-26s %s %-24s %s" % (outcome["company_id"], outcome["report_end"],
                                         outcome["status"], outcome.get("reason", "")[:80]))
            continue
        values = " ".join("%s=%s(%s)" % (row["metric_id"],
                                         row["value"] if row["quality"] != "NONE" else row["reason_code"],
                                         row["quality"]) for row in outcome["metrics"])
        print("%-26s %s FY%s %s" % (outcome["company_id"], outcome["report_end"],
                                    outcome["fiscal_year"], values))
    print("target periods %d, resolved %d, exact metric positions %d of %d"
          % (len(outcomes), len(resolved), exact, len(outcomes) * len(metrics)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
