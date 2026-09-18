"""Fix the Issue #47 denominator and classify every historical target position.

The coverage frame is companies x declared metrics x the requested number of
most recent annual report ends. It is built before any of those positions can
be filled, so the denominator cannot quietly shrink to whatever happens to work:
the declared metric count is read from the installed policy and checked against
its own declared total, and a company with fewer reachable periods reports
fewer periods rather than fewer metrics.

Each position gets exactly one status, chosen by a fixed precedence so a later
limitation never hides an earlier one:

1. ``TARGET_PERIOD_METADATA_BLOCKED`` - the period itself is not established
   from saved submissions metadata, so nothing about it can be claimed.
2. ``SOURCE_MISSING_TARGET_ORIGINAL`` - the period is established but that
   filing's own original document is not saved.
3. ``SOURCE_MISSING_DEPENDENCY`` or ``HISTORICAL_ROUTE_NOT_WIRED`` - the period
   is established but resolving it stopped. Which one is decided by the
   failure's own category, because a missing source and a missing
   implementation are different conclusions and neither is a disclosure claim.
4. the metric's own resolved outcome, including a structural non-applicability
   the installed rules decide and a withheld result with its reason code.

Nothing here executes a metric that the wired routes cannot execute, and
nothing here turns a missing implementation into "the issuer did not disclose".
"""
from pathlib import Path

from .canonical import content_hash, sha256_file, strict_json_file
from .normal_annual_input import _registry_rows
from .normal_history_catalog import plan_historical_sources
from .normal_period_selection import resolve_period_selection
from .normal_source_authority import ROOT
from .sources import resolve_repository_file


POLICY_PATH = "config/issue28_normal_results_v2.json"
RECORD_TYPE = "HISTORICAL_COVERAGE_MATRIX"
# The historical routes that exist today. Everything else is an explicit gap.
WIRED_COMPANYFACTS_METRICS = ("A05", "A06", "A07", "A08", "A10",
                              "B02", "B04", "B05", "B07", "B08", "B09")
WIRED_REVENUE_METRICS = ("B01", "B03")
WIRED_ACCESSION_METRICS = ("A01", "A02", "B12")
WIRED_HISTORICAL_METRICS = tuple(sorted(WIRED_COMPANYFACTS_METRICS + WIRED_REVENUE_METRICS
                                        + WIRED_ACCESSION_METRICS))


class CoverageError(ValueError):
    pass


def _need(condition, reason):
    if not condition:
        raise CoverageError(reason)


def declared_metric_ids(*, repo_root: Path):
    """The declared Issue metric universe, checked against its own total."""
    policy = strict_json_file(path=resolve_repository_file(
        repo_root=repo_root, repo_relative_path=POLICY_PATH))
    _need(policy == strict_json_file(path=ROOT / POLICY_PATH),
          "COVERAGE_INSTALLED_POLICY_CHANGED")
    metrics = sorted(set(policy["metric_ids"]) | set(policy["pending_metric_ids"]))
    _need(len(metrics) == len(policy["metric_ids"]) + len(policy["pending_metric_ids"]),
          "COVERAGE_METRIC_SET_OVERLAPS")
    _need(len(metrics) == policy["declared_issue_metric_count"],
          "COVERAGE_DECLARED_METRIC_COUNT_CHANGED")
    return metrics, policy


def _classify(result):
    if result["applicability"] == "N_A_STRUCTURAL":
        return "N_A_STRUCTURAL"
    if result["publication"] == "WITHHELD":
        return "WITHHELD_SOURCE_OR_ROUTE"
    if result["value"] is None:
        return "NO_VALUE_PUBLISHED"
    return "VALUE_" + result["quality"]


def _row(result):
    return {"status": _classify(result), "value": result["value"], "unit": result["unit"],
            "quality": result["quality"], "publication": result["publication"],
            "reason_code": result["reason_code"], "period_start": result["period_start"],
            "period_end": result["period_end"]}


def _adapter_rows(*, repo_root, company_id, selection):
    """Run every wired adapter independently and keep each one's own outcome.

    One adapter's limitation is that adapter's metrics' own outcome. It must not
    remove the metrics another adapter resolved for the same period, because a
    Company Facts refusal about amendments says nothing about whether revenue or
    an instant fact could be read from the same selected filing.
    """
    from .historical_accession_results import resolve_historical_accession_metrics
    from .historical_results import resolve_historical_companyfacts_metrics
    from .historical_zero_ai_results import resolve_historical_zero_ai_metric

    rows, adapters, component = {}, {}, None

    def failed(error):
        return {"reason": str(error), "error_type": type(error).__name__,
                "category": getattr(error, "category", "IMPLEMENTATION_GAP")}

    try:
        component = resolve_historical_companyfacts_metrics(repo_root=repo_root,
                                                            company_id=company_id,
                                                            period_selection=selection)
        for metric_id in WIRED_COMPANYFACTS_METRICS:
            rows[metric_id] = _row(component["metrics"][metric_id]["result"])
        adapters["companyfacts"] = None
    except (ValueError, KeyError, TypeError, OSError) as error:
        adapters["companyfacts"] = failed(error)
        for metric_id in WIRED_COMPANYFACTS_METRICS:
            rows[metric_id] = {"status": _blocked_status(adapters["companyfacts"]),
                               **adapters["companyfacts"]}
    for metric_id in WIRED_REVENUE_METRICS:
        try:
            revenue = resolve_historical_zero_ai_metric(repo_root=repo_root,
                                                        company_id=company_id,
                                                        metric_id=metric_id,
                                                        period_selection=selection)
            rows[metric_id] = _row(revenue["result"])
            adapters.setdefault("revenue", None)
        except (ValueError, KeyError, TypeError, OSError) as error:
            detail = failed(error)
            adapters["revenue"] = detail
            rows[metric_id] = {"status": _blocked_status(detail), **detail}
    try:
        instants = resolve_historical_accession_metrics(repo_root=repo_root,
                                                        company_id=company_id,
                                                        period_selection=selection)
        for metric_id in WIRED_ACCESSION_METRICS:
            rows[metric_id] = _row(instants["metrics"][metric_id]["result"])
        adapters["accession"] = None
    except (ValueError, KeyError, TypeError, OSError) as error:
        adapters["accession"] = failed(error)
        for metric_id in WIRED_ACCESSION_METRICS:
            rows[metric_id] = {"status": _blocked_status(adapters["accession"]),
                               **adapters["accession"]}
    return component, rows, adapters


def _blocked_status(detail):
    """A missing source and a missing implementation are different conclusions."""
    return ("SOURCE_MISSING_DEPENDENCY"
            if detail["category"] in {"SOURCE_UNAVAILABLE", "SOURCE_ACCESS_FAILED",
                                      "SOURCE_INTEGRITY_ERROR"}
            else "HISTORICAL_ROUTE_NOT_WIRED")


def build_coverage_matrix(*, repo_root: Path, company_ids=None, years=5):
    """Enumerate every target position with independent status dimensions.

    ``first_blocking_reason`` is a display convenience: it names what this
    position hit first. It is NOT a claim that it is the only thing missing. A
    position can lack its target original AND have no historical route, so the
    four dimensions are recorded separately and counted separately. Reading the
    first blocker as the only blocker is what makes a source budget look like
    the whole remaining cost.
    """
    metrics, policy = declared_metric_ids(repo_root=repo_root)
    configured = [c["company_id"] for c in _registry_rows(repo_root=repo_root)]
    selected = configured if company_ids is None else list(company_ids)
    _need(bool(selected) and len(selected) == len(set(selected))
          and set(selected) <= set(configured), "COVERAGE_COMPANY_SET_INVALID")
    wired = set(WIRED_HISTORICAL_METRICS)
    positions = []
    company_reports = []
    for company_id in selected:
        plan = plan_historical_sources(repo_root=repo_root, company_id=company_id, count=years)
        identity_ready = set(plan["annual_identity_ready_report_dates"])
        periods = []
        for candidate in plan["target_candidates"]:
            report_end = candidate["report_date"]
            entry = {"report_end": report_end, "target_ordinal": candidate["target_ordinal"],
                     "fiscal_year": None, "selection_id": None,
                     "period_status": "METADATA_BLOCKED"
                     if candidate["metadata_status"] != "METADATA_CANDIDATE_READY"
                     else "ORIGINAL_NOT_SAVED" if report_end not in identity_ready
                     else "PERIOD_ESTABLISHED"}
            rows, adapters, component = {}, {}, None
            if entry["period_status"] == "PERIOD_ESTABLISHED":
                selection = resolve_period_selection(repo_root=repo_root,
                                                     company_id=company_id,
                                                     report_end=report_end)
                entry["selection_id"] = selection["selection_id"]
                component, rows, adapters = _adapter_rows(repo_root=repo_root,
                                                          company_id=company_id,
                                                          selection=selection)
                entry["adapter_errors"] = {name: detail for name, detail in adapters.items()
                                           if detail is not None}
                if component is not None:
                    entry["fiscal_year"] = component["periods"]["current"]["fiscal_year"]
                    entry["prior_error"] = component["prior_error"]
            for metric_id in metrics:
                established = entry["period_status"] != "METADATA_BLOCKED"
                original_saved = entry["period_status"] == "PERIOD_ESTABLISHED"
                implemented = metric_id in wired
                row = rows.get(metric_id)
                verified = bool(row) and row["status"].startswith(("VALUE_", "N_A_STRUCTURAL"))
                if not established:
                    first, detail = "TARGET_PERIOD_METADATA_BLOCKED", {
                        "reasons": candidate["metadata_blocking_reasons"]}
                elif not original_saved:
                    first, detail = "SOURCE_MISSING_TARGET_ORIGINAL", {
                        "accession": candidate["current_filing"]["accessionNumber"],
                        "document_name": candidate["current_filing"]["primaryDocument"]}
                elif not implemented:
                    first, detail = "HISTORICAL_ROUTE_NOT_WIRED", {
                        "note": "no historical route for this metric yet"}
                else:
                    first, detail = row["status"], row
                positions.append({
                    "company_id": company_id, "report_end": report_end,
                    "target_ordinal": candidate["target_ordinal"],
                    "fiscal_year": entry["fiscal_year"], "metric_id": metric_id,
                    "first_blocking_reason": first, "status": first, "detail": detail,
                    "target_period_established": established,
                    "target_original_saved": original_saved,
                    "historical_route_implemented": implemented,
                    "native_run_wired": False,
                    "verified_outcome": verified})
            periods.append(entry)
        # Positions whose target period was never discovered still belong to the
        # frame. They are enumerated with the company and the ordinal that is
        # missing, and never with an invented fiscal-year label.
        for ordinal in range(len(plan["target_candidates"]) + 1, years + 1):
            for metric_id in metrics:
                positions.append({
                    "company_id": company_id, "report_end": None,
                    "target_ordinal": ordinal, "fiscal_year": None, "metric_id": metric_id,
                    "first_blocking_reason": "TARGET_PERIOD_NOT_DISCOVERED",
                    "status": "TARGET_PERIOD_NOT_DISCOVERED",
                    "detail": {"reason": "fewer annual report ends are reachable from saved "
                                         "submissions metadata than the requested window",
                               "reachable_period_count": len(plan["target_candidates"]),
                               "catalog_limitation_count": len(plan["catalog_limitations"])},
                    "target_period_established": False, "target_original_saved": False,
                    "historical_route_implemented": metric_id in wired,
                    "native_run_wired": False, "verified_outcome": False})
        company_reports.append({"company_id": company_id, "requested_years": years,
                                "target_period_count": len(plan["target_candidates"]),
                                "periods": periods,
                                "catalog_limitation_count": len(plan["catalog_limitations"]),
                                "new_acquisition_count": plan["new_acquisition_count"]})
    counts = {}
    for position in positions:
        counts[position["status"]] = counts.get(position["status"], 0) + 1
    dimensions = {
        "target_period_established": sum(p["target_period_established"] for p in positions),
        "target_original_saved": sum(p["target_original_saved"] for p in positions),
        "historical_route_implemented": sum(p["historical_route_implemented"] for p in positions),
        "native_run_wired": sum(p["native_run_wired"] for p in positions),
        "verified_outcome": sum(p["verified_outcome"] for p in positions)}
    blocked_by_both = sum(1 for p in positions
                          if not p["target_original_saved"] and not p["historical_route_implemented"])
    body = {"record_type": RECORD_TYPE, "schema_version": 2,
            "declared_metric_ids": metrics, "declared_metric_count": len(metrics),
            "requested_years": years, "companies": selected,
            "target_frame_positions": len(selected) * len(metrics) * years,
            "enumerated_positions": len(positions),
            "wired_historical_metric_ids": list(WIRED_HISTORICAL_METRICS),
            "first_blocking_reason_counts": counts, "status_counts": counts,
            "dimension_counts": dimensions,
            "positions_missing_source_and_route": blocked_by_both,
            "first_blocking_reason_is_not_the_only_blocker": True,
            "company_reports": company_reports, "positions": positions,
            "policy_sha256": sha256_file(path=ROOT / POLICY_PATH),
            "module_sha256": sha256_file(path=Path(__file__)),
            "calls": {"provider": 0, "paid": 0, "sec": 0},
            "native_run_created": False, "production_authorized": False}
    _need(body["enumerated_positions"] == body["target_frame_positions"],
          "COVERAGE_FRAME_NOT_FULLY_ENUMERATED")
    return {**body, "matrix_id": content_hash(value=body)}
