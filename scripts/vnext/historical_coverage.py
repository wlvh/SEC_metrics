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
4. whether a native Run recorded an outcome for it, read from that Run's own
   receipt.

This module plans and reports. It does not execute. It used to build a second
candidate, a second Evidence check, a second system review decision and a
second Result for every wired position, purely to fill a status column - and
the two implementations disagreed in both directions, reporting
``native_run_wired`` as a hard-coded ``False`` beside 114 real Runs and
reporting B01 and B03 EXACT while the public renderer refused them. Outcomes
now come from ``historical_run_receipts``, which reads a frozen Run.

Four states stay apart because they are four different things: whether a route
exists, whether a Run produced a result, whether that result passed its own
validation, and whether its content has been checked. A position can be
implemented and never run; a Run can be FROZEN and PASSED and hold another
item's text. Nothing here turns a missing implementation into "the issuer did
not disclose", and nothing here promotes EXACT into business acceptance.
"""
from pathlib import Path

from .canonical import content_hash, sha256_file, strict_json_file
from .normal_annual_input import _registry_rows
from .normal_history_plan import plan_historical_sources
from .historical_run_receipts import classify_result, collect_run_receipts, index_receipts
from .normal_period_selection import resolve_period_selection
from .normal_source_authority import ROOT
from .sources import resolve_repository_file


POLICY_PATH = "config/issue28_normal_results_v2.json"
DEFECT_REGISTER_PATH = "docs/evidence/issue47_history/known_result_defects.json"
RECORD_TYPE = "HISTORICAL_COVERAGE_MATRIX"
# The historical routes that exist today. Everything else is an explicit gap.
WIRED_COMPANYFACTS_METRICS = ("A05", "A06", "A07", "A08", "A10",
                              "B02", "B04", "B05", "B07", "B08", "B09")
WIRED_REVENUE_METRICS = ("B01", "B03")
WIRED_ACCESSION_METRICS = ("A01", "A02", "B12")
# The 8-K event windows. Their window is the pinned period's own start and end,
# taken from prepare_historical_annual_input's target_period, so nothing here
# reads the latest filing. They share historical_zero_ai_results with the
# revenue route exactly as they share normal_zero_ai_results in the current one.
WIRED_EVENT_METRICS = ("C01", "E01", "E02", "E03", "E04", "E05")
# The first text route. C02 shares its adapter and is not wired: its plan needs
# the annual meeting's DEF 14A, and of the 82 proxies the saved submissions
# indexes list, ten have accession material and all ten were filed in 2026.
WIRED_TEXT_METRICS = ("D02",)
WIRED_HISTORICAL_METRICS = tuple(sorted(WIRED_COMPANYFACTS_METRICS + WIRED_REVENUE_METRICS
                                        + WIRED_ACCESSION_METRICS + WIRED_EVENT_METRICS
                                        + WIRED_TEXT_METRICS))


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


def known_result_defects(*, repo_root: Path):
    """Results this repository has confirmed hold wrong content.

    A defect entry withdraws a result from current delivery. It does not delete
    it, re-sign it or relabel it as a structural non-applicability: the original
    Run stays readable so the defect can be demonstrated and the repair checked.
    """
    path = repo_root / DEFECT_REGISTER_PATH
    if not path.is_file():
        return []
    register = strict_json_file(path=path)
    _need(register["record_type"] == "KNOWN_RESULT_DEFECT_REGISTER",
          "COVERAGE_DEFECT_REGISTER_TYPE_INVALID")
    return register["defects"]


def _matching_defect(*, defects, company_id, metric_id, report_end, result):
    """The defect entry that withdraws this position's result, if there is one.

    An entry naming a ``result_id`` withdraws exactly that result. An entry
    without one names a coordinate whose defect is not tied to a single Run -
    an unresolved reference, for instance - and applies to whatever that
    coordinate produces. A null ``result_id`` must not match a position that
    produced nothing: the first version of this compared None to None and
    marked all sixteen unwired metrics defective.
    """
    result_id = (result or {}).get("result_id")
    for defect in defects:
        named = defect.get("result_id")
        if named is not None:
            if result_id is not None and named == result_id:
                return defect
            continue
        if (defect.get("company_id") == company_id
                and defect.get("metric_id") == metric_id
                and defect.get("period_end") == report_end):
            return defect
    return None


def _position(*, company_id, report_end, ordinal, metric_id, established,
              original_saved, implemented, found, defects, candidate, closure=None):
    """One target position, with its four states kept apart.

    A route can exist without a Run, and a Run can record a result whose
    content is wrong. Neither collapses into the other, so the status names
    which of the two is missing and the defect flag is separate from both.
    """
    fiscal_year, receipt, result, detail, ambiguous = None, None, None, None, False
    if found:
        # More than one receipt for a coordinate means the position was run
        # under more than one Requirement closure. Taking found[-1] took
        # whichever run directory sorted last by name, and then called it "the
        # last written" - it is neither. The caller names the closure it is
        # asking about; without one, several receipts is an ambiguity to report
        # rather than a winner to pick.
        candidates = ([entry for entry in found
                       if entry["receipt"]["requirement_closure_hash"] == closure]
                      if closure is not None else list(found))
        if len(candidates) == 1:
            receipt = candidates[0]["receipt"]
            result = candidates[0]["result"]
        elif len(candidates) > 1:
            ambiguous = True
        fiscal_year = next(((entry["receipt"]["target_period"] or {}).get("fiscal_year")
                            for entry in (candidates or found)), None)
    if not established:
        status = "TARGET_PERIOD_METADATA_BLOCKED"
        detail = {"reasons": candidate["metadata_blocking_reasons"]}
    elif not original_saved:
        status = "SOURCE_MISSING_TARGET_ORIGINAL"
        detail = {"accession": candidate["current_filing"]["accessionNumber"],
                  "document_name": candidate["current_filing"]["primaryDocument"]}
    elif not implemented:
        status = "HISTORICAL_ROUTE_NOT_WIRED"
        detail = {"note": "no historical route for this metric yet"}
    elif ambiguous:
        # Several receipts and nothing to choose between them. Reporting any
        # one of their outcomes would be reporting a guess.
        status = "RUN_RECEIPT_AMBIGUOUS"
        detail = {"note": "several receipts for this coordinate and no closure was requested",
                  "requirement_closure_hashes": sorted(
                      {entry["receipt"]["requirement_closure_hash"] for entry in found})}
    elif result is None:
        # Implemented and not run is not the same as not implemented, and it is
        # not a disclosure claim either. A requested closure that no receipt
        # carries lands here too, which is correct: that closure has not run it.
        status = "ROUTE_IMPLEMENTED_NOT_RUN"
        detail = {"note": "a historical route exists and no Run receipt was found",
                  "receipts_under_other_closures": len(found)}
    else:
        status = classify_result(result)
        detail = {key: result[key] for key in ("value", "unit", "quality", "publication",
                                               "reason_code", "period_start", "period_end")}
    defect = _matching_defect(defects=defects, company_id=company_id, metric_id=metric_id,
                              report_end=report_end, result=result)
    ran = result is not None
    return {"company_id": company_id, "report_end": report_end,
            "target_ordinal": ordinal, "fiscal_year": fiscal_year, "metric_id": metric_id,
            "first_blocking_reason": status, "status": status, "detail": detail,
            "target_period_established": established,
            "target_original_saved": original_saved,
            "historical_route_implemented": implemented,
            "native_run_receipt": ran,
            "run_receipt_count": len(found),
            "run_id": receipt["run_id"] if receipt else None,
            "run_status": receipt["run_status"] if receipt else None,
            "requirement_closure_hash": receipt["requirement_closure_hash"] if receipt else None,
            "validation_status": receipt["validation_status"] if receipt else None,
            "result_id": (result or {}).get("result_id"),
            "known_content_defect": defect["defect_id"] if defect else None,
            # A recorded result is not a checked one. Content acceptance is a
            # separate state that no field of a Run receipt can supply.
            "business_content_accepted": False,
            "run_receipt_hashes_verified": bool(receipt
                                                and receipt["manifest_file_hashes_verified"]),
            # An outcome counts as verified only when a single unambiguous
            # receipt supplied it, that Run is FROZEN and its own validation
            # passed, its manifest hashes were actually checked, and no
            # confirmed content defect withdraws it. A receipt that is OPEN,
            # unvalidated, unverifiable or one of several is evidence of
            # something, but not of a verified outcome.
            "verified_outcome": (ran and defect is None
                                 and status.startswith(("VALUE_", "N_A_STRUCTURAL"))
                                 and receipt["run_status"] == "FROZEN"
                                 and receipt["validation_status"] == "PASSED"
                                 and receipt["manifest_file_hashes_verified"])}


def build_coverage_matrix(*, repo_root: Path, company_ids=None, years=5,
                          runs_root=None, requirement_closure_hash=None):
    """Enumerate every target position with independent status dimensions.

    ``first_blocking_reason`` is a display convenience: it names what this
    position hit first. It is NOT a claim that it is the only thing missing. A
    position can lack its target original AND have no historical route, so the
    four dimensions are recorded separately and counted separately. Reading the
    first blocker as the only blocker is what makes a source budget look like
    the whole remaining cost.

    ``requirement_closure_hash`` names which version's receipts to report. A
    coordinate run under more than one closure has more than one receipt, and
    without a selector the position reports ``RUN_RECEIPT_AMBIGUOUS`` rather
    than picking whichever directory happened to sort last.
    """
    metrics, policy = declared_metric_ids(repo_root=repo_root)
    configured = [c["company_id"] for c in _registry_rows(repo_root=repo_root)]
    selected = configured if company_ids is None else list(company_ids)
    _need(bool(selected) and len(selected) == len(set(selected))
          and set(selected) <= set(configured), "COVERAGE_COMPANY_SET_INVALID")
    wired = set(WIRED_HISTORICAL_METRICS)
    defects = known_result_defects(repo_root=repo_root)
    receipt_list = [] if runs_root is None else collect_run_receipts(runs_root=runs_root)
    receipts = index_receipts(receipts=receipt_list)
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
            if entry["period_status"] == "PERIOD_ESTABLISHED":
                selection = resolve_period_selection(repo_root=repo_root,
                                                     company_id=company_id,
                                                     report_end=report_end)
                entry["selection_id"] = selection["selection_id"]
            for metric_id in metrics:
                established = entry["period_status"] != "METADATA_BLOCKED"
                original_saved = entry["period_status"] == "PERIOD_ESTABLISHED"
                implemented = metric_id in wired
                found = receipts.get((company_id, metric_id, report_end), [])
                position = _position(company_id=company_id, report_end=report_end,
                                     ordinal=candidate["target_ordinal"],
                                     metric_id=metric_id, established=established,
                                     original_saved=original_saved,
                                     implemented=implemented, found=found,
                                     defects=defects, candidate=candidate,
                                     closure=requirement_closure_hash)
                if position["fiscal_year"] is not None and entry["fiscal_year"] is None:
                    entry["fiscal_year"] = position["fiscal_year"]
                positions.append(position)
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
                    "native_run_receipt": False, "run_receipt_count": 0,
                    "run_id": None, "run_status": None,
                    "requirement_closure_hash": None, "validation_status": None,
                    "run_receipt_hashes_verified": False,
                    "result_id": None, "known_content_defect": None,
                    "business_content_accepted": False, "verified_outcome": False})
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
        "native_run_receipt": sum(p["native_run_receipt"] for p in positions),
        "known_content_defect": sum(p["known_content_defect"] is not None for p in positions),
        "business_content_accepted": sum(p["business_content_accepted"] for p in positions),
        "run_receipt_hashes_verified": sum(p["run_receipt_hashes_verified"]
                                           for p in positions),
        "verified_outcome": sum(p["verified_outcome"] for p in positions)}
    blocked_by_both = sum(1 for p in positions
                          if not p["target_original_saved"] and not p["historical_route_implemented"])
    body = {"record_type": RECORD_TYPE, "schema_version": 3,
            "declared_metric_ids": metrics, "declared_metric_count": len(metrics),
            "requested_years": years, "companies": selected,
            "requested_requirement_closure_hash": requirement_closure_hash,
            "target_frame_positions": len(selected) * len(metrics) * years,
            "enumerated_positions": len(positions),
            "wired_historical_metric_ids": list(WIRED_HISTORICAL_METRICS),
            "first_blocking_reason_counts": counts, "status_counts": counts,
            "dimension_counts": dimensions,
            "positions_missing_source_and_route": blocked_by_both,
            "first_blocking_reason_is_not_the_only_blocker": True,
            # This frame stops at the metric result. It never renders a public
            # row, so an EXACT position here is a resolved value, not a
            # publishable one: B01 and B03 were counted EXACT while the
            # historical renderer still refused them. Read the counts as
            # resolution, and the native Run matrix for rows.
            "public_row_rendering_not_measured": True,
            "company_reports": company_reports, "positions": positions,
            "run_receipts_read": len(receipt_list),
            "runs_root_supplied": runs_root is not None,
            "business_execution_invoked": False,
            "policy_sha256": sha256_file(path=ROOT / POLICY_PATH),
            "module_sha256": sha256_file(path=Path(__file__)),
            "calls": {"provider": 0, "paid": 0, "sec": 0},
            "native_run_created": False, "production_authorized": False}
    _need(body["enumerated_positions"] == body["target_frame_positions"],
          "COVERAGE_FRAME_NOT_FULLY_ENUMERATED")
    return {**body, "matrix_id": content_hash(value=body)}
