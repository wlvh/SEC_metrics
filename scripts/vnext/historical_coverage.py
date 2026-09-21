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
import re
from pathlib import Path

from .canonical import content_hash, sha256_file, strict_json_file
from .normal_annual_input import _registry_rows
from .normal_history_plan import plan_historical_sources
from .historical_run_receipts import classify_result, collect_run_receipts, index_receipts
from .normal_period_selection import resolve_period_selection
from .normal_source_authority import ROOT
from . import historical_structural_results as structural
from .sources import resolve_repository_file


_SHA = re.compile(r"sha256:[0-9a-f]{64}\Z")
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
# Eight more, but only where the company's own registry traits put the metric
# outside its Spec's gate. Six are gated on `financial` and none of the
# companies whose periods are reachable is a bank; two are gated on `lodging`
# and eight of the ten are not hotels. That is why this is not in the list
# above: whether a route exists here is a fact about the pair, not about the
# metric, and reporting it per metric would say the route exists for Marriott's
# occupancy too - where it does not, and where saying "not applicable" would be
# a false statement about the issuer rather than a missing implementation.
STRUCTURAL_APPLICABILITY_METRICS = tuple(sorted(structural.SPEC_PATHS))


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
    for defect in register["defects"]:
        release = defect.get("released")
        if release is None:
            continue
        # A release that names nothing releases nothing, and an entry that
        # already names one bad result has nothing to release: it withdraws
        # that result, not the coordinate.
        _need(isinstance(release, dict) and isinstance(release.get("result_id"), str)
              and bool(_SHA.match(release["result_id"])),
              "COVERAGE_DEFECT_RELEASE_NAMES_NO_RESULT")
        # A release that does not name the version it was produced under is
        # refused at load rather than silently widened to every version.
        _need(isinstance(release.get("requirement_closure_hash"), str)
              and bool(_SHA.match(release["requirement_closure_hash"])),
              "COVERAGE_DEFECT_RELEASE_NAMES_NO_VERSION")
        _need(defect.get("result_id") is None,
              "COVERAGE_DEFECT_RELEASE_ON_RESULT_SCOPED_ENTRY")
    return register["defects"]


def _release_covers(*, defect, result, receipt):
    """Does this entry's release name the result in front of us?

    A coordinate-level entry has to be able to stop withdrawing, or a repaired
    defect withdraws its own repair forever. What it must not do is stop
    withdrawing because a field was edited to say the work was done. The first
    version released on ``repair_state`` ending in ``_RESULT_RECOMPUTED``,
    which meant the same unrepaired receipt and the same unrepaired result
    changed from withdrawn to verified when that string changed - the register
    was asserting the outcome rather than pointing at it.

    So the release names the repaired result by identity, and the version it
    was produced under. Any other result at that coordinate, including the one
    the defect was raised against, stays withdrawn.
    """
    release = defect.get("released")
    if not isinstance(release, dict):
        return False
    result_id = (result or {}).get("result_id")
    if result_id is None or release.get("result_id") != result_id:
        return False
    # Both fields are required. The first version read the version as
    # optional - "closure is None or it matches" - so an entry that simply
    # omitted it, or wrote null, released the coordinate under every version.
    # The case name said the version must be named and the code only checked
    # it when it happened to be there.
    closure = release.get("requirement_closure_hash")
    if not isinstance(closure, str) or not _SHA.match(closure):
        return False
    return (receipt or {}).get("requirement_closure_hash") == closure


def _matching_defect(*, defects, company_id, metric_id, report_end, result, receipt):
    """The defect entry that withdraws this position's result, if there is one.

    An entry naming a ``result_id`` withdraws exactly that result and nothing
    else - it names a specific bad result, which stays withdrawn whatever later
    Runs do. An entry without one names a coordinate whose defect is not tied
    to a single Run - an unresolved reference, for instance - and applies to
    whatever that coordinate produces until its release names a repaired
    result. A null ``result_id`` must not match a position that produced
    nothing: the first version of this compared None to None and marked all
    sixteen unwired metrics defective.
    """
    result_id = (result or {}).get("result_id")
    for defect in defects:
        named = defect.get("result_id")
        if named is not None:
            if result_id is not None and named == result_id:
                return defect
            continue
        if _release_covers(defect=defect, result=result, receipt=receipt):
            continue
        if (defect.get("company_id") == company_id
                and defect.get("metric_id") == metric_id
                and defect.get("period_end") == report_end):
            return defect
    return None


_AMBIGUITY_NOTES = {
    "RUN_RECEIPT_VERSION_AMBIGUOUS":
        "receipts for this coordinate were written under more than one Requirement "
        "closure and no closure was requested",
    "RUN_RECEIPT_AMBIGUOUS":
        "several receipts under one closure record different results",
    "RUN_RECEIPT_IDENTITY_CONFLICT":
        "receipts sharing one result identity disagree on the measurement that "
        "identity is supposed to distinguish",
}


def _completeness(entry):
    """How much of a receipt was actually checkable, strongest first."""
    receipt = entry["receipt"]
    return (receipt["run_status"] != "FROZEN",
            receipt["validation_status"] != "PASSED",
            not receipt["manifest_file_hashes_verified"])


def _select_receipt(*, found, closure, selection_id=None):
    """Which receipt this position reports, in three separate steps.

    Version, then status, then duplicates - answering them together is what
    made the answer depend on the order the run directories were read in.

    First, which Requirement version is being reported? A coordinate run under
    two versions has two receipts, and taking whichever came first is picking a
    version by filename. The caller names the version it is asking about; with
    no name and more than one present, that is an ambiguity to report.

    Second, within that version, what state is each receipt in? A result
    recorded in a Run that never froze, never validated, or whose files no
    longer hash to its manifest is weaker evidence than the same result in a
    Run that did all three, so the receipts are ordered by that and the
    strongest is the one reported. ``receipt_status_uniform`` says whether
    there was anything to order.

    Third, and only then: are the remaining receipts one outcome recorded twice
    or two outcomes that disagree? A dependency metric's result is recorded in
    its own Run and again in the Run that consumes it - B01 appears in the B01
    Run and in the B03 Run - and those carry the same result_id, so they are
    one outcome seen twice. Ambiguity is when the result identities differ.
    """
    empty = {"candidates": [], "receipt": None, "result": None,
             "ambiguity": None, "status_uniform": True,
             "row": None, "row_ambiguity": None, "identity": None}
    if not found:
        return empty
    if closure is not None:
        candidates = [entry for entry in found
                      if entry["receipt"]["requirement_closure_hash"] == closure]
    else:
        versions = {entry["receipt"]["requirement_closure_hash"] for entry in found}
        if len(versions) > 1:
            return {**empty, "candidates": list(found),
                    "ambiguity": "RUN_RECEIPT_VERSION_AMBIGUOUS"}
        candidates = list(found)
    if not candidates:
        return empty
    ranked = sorted(candidates,
                    key=lambda entry: (_completeness(entry),
                                       str(entry["receipt"]["run_id"]),
                                       str(entry["result"]["result_id"])))
    uniform = len({_completeness(entry) for entry in ranked}) == 1
    if len({entry["result"]["result_id"] for entry in ranked}) > 1:
        return {"candidates": candidates, "receipt": None, "result": None,
                "ambiguity": "RUN_RECEIPT_AMBIGUOUS", "status_uniform": uniform,
                "row": None, "row_ambiguity": None, "identity": None}
    # The reason duplicates may be merged is that result_id is said to differ
    # whenever the measurement does. Merging on that claim without checking it
    # is assuming it; these entries carry what the coordinate key does not, so
    # the claim is checked here and a disagreement is reported rather than
    # averaged away. run_id is excluded because it is the one field two runs
    # recording one result are expected to differ on.
    measurements = {content_hash(value={key: value
                                        for key, value in entry["identity"].items()
                                        if key != "run_id"})
                    for entry in ranked}
    if len(measurements) > 1:
        return {"candidates": candidates, "receipt": None, "result": None,
                "ambiguity": "RUN_RECEIPT_IDENTITY_CONFLICT", "status_uniform": uniform,
                "row": None, "row_ambiguity": None, "identity": None}
    row, row_ambiguity = _row_evidence(candidates=ranked, selection_id=selection_id)
    return {"candidates": candidates, "receipt": ranked[0]["receipt"],
            "result": ranked[0]["result"], "ambiguity": None,
            "status_uniform": uniform, "row": row, "row_ambiguity": row_ambiguity,
            "identity": ranked[0]["identity"]}


def _row_evidence(*, candidates, selection_id):
    """Which of these runs rendered the row, which is not the same question.

    Choosing one receipt to represent the position and then reading every
    layer off it loses evidence that is really there. A dependency metric's
    result is recorded in its own Run and again in the Run that consumes it -
    B01 in the B01 Run and in the B03 Run - and the row for B01 is rendered
    beside the B01 Run. Whichever of the two happened to sort first decided
    whether the position read as having reached a public row at all, so the
    same result read as rendered or not rendered depending on two run_ids.

    So the version, the result identity and the period selection are settled
    first - they are what makes these runs comparable - and then each layer is
    associated with the evidence that actually carries it. The row layer names
    its own run, which is how a reader can tell it is not the one the native
    layer names.

    Bundles that disagree on the period selection are not two views of one
    measurement, so that is reported rather than resolved. A bundle the reader
    refused, a bundle that was rendered from another result and no bundle at
    all are three different facts, and each is named rather than collapsed
    into "no row".

    ``selection_id`` is the period selection this coordinate resolves to now.
    The bundle carries the one the renderer used, and until they were compared
    the field sat beside the key without being checked - a row rendered for a
    different filing choice of the same coordinate would have counted.
    """
    bundles = [(entry, entry["receipt"].get("public_row")) for entry in candidates]
    refused = [bundle["refusal"] for _, bundle in bundles
               if bundle is not None and not bundle["accepted"]]
    with_row = [entry for entry, bundle in bundles
                if bundle is not None and bundle["accepted"]
                and bundle["result_id"] == entry["result"]["result_id"]]
    if not with_row:
        if refused:
            return None, sorted(refused)[0]
        if any(bundle is not None for _, bundle in bundles):
            return None, "ROW_BUNDLE_IS_FOR_ANOTHER_RESULT"
        return None, None
    selections = {entry["receipt"]["public_row"]["period_selection_id"]
                  for entry in with_row}
    if len(selections) > 1:
        return None, "ROW_BUNDLE_PERIOD_SELECTION_AMBIGUOUS"
    if selection_id is not None and selections != {selection_id}:
        return None, "ROW_BUNDLE_PERIOD_SELECTION_IS_NOT_THIS_COORDINATE_S"
    # The renderer is bound by the Requirement closure these candidates already
    # share, so agreement here is that binding holding rather than a second
    # policy. Checking it is how a bundle written by something other than the
    # renderer that closure names stops being indistinguishable from one that
    # was, and the digests are reported so the reader need not take it on trust.
    renderers = {(entry["receipt"]["public_row"]["renderer_sha256"],
                  entry["receipt"]["public_row"]["presentation_policy_sha256"])
                 for entry in with_row}
    if len(renderers) > 1:
        return None, "ROW_BUNDLE_RENDERER_AMBIGUOUS"
    # Prefer a row rendered from a frozen Run over one rendered from an open
    # replay; among equals, the run_id keeps it deterministic.
    ordered = sorted(with_row,
                     key=lambda entry: (entry["receipt"]["public_row"]["status"]
                                        != "FROZEN_CANDIDATE",
                                        _completeness(entry),
                                        str(entry["receipt"]["run_id"])))
    chosen = ordered[0]
    return {"receipt": chosen["receipt"], "bundle": chosen["receipt"]["public_row"],
            "rendered_by_other_runs": len(with_row) - 1}, None


NOT_PROVEN = "NOT_PROVEN"


def _delivery(*, receipt, result, status, defect, defects, row=None, row_ambiguity=None):
    """The three layers a delivered position has, each proved or not.

    verified_outcome answers one question - did an unambiguous, frozen,
    validated Run record this result. That is the first layer only, and
    reporting it as a delivery rate would be reading "a Run exists" as "the
    number is right and it reached the output". So the layers are named and
    each carries its own reason when it is not proven:

    * ``native_run`` - which version produced what, frozen and validated;
    * ``public_row`` - whether the renderer produced a row and its evidence,
      read from the bundle it wrote rather than re-rendered here;
    * ``content_acceptance`` - whether the value or excerpt range was checked
      against the filing by something other than the code that produced it.

    The third is NOT_PROVEN for every position in this repository today and
    says so rather than being left out. A defect register entry is a recorded
    finding, not an acceptance: it can withdraw a result and it can release a
    named repaired one, and neither is a statement that the content is right.
    """
    layers = {}
    if result is None:
        layers["native_run"] = {"proven": False, "reason": status}
    elif receipt["run_status"] != "FROZEN":
        layers["native_run"] = {"proven": False,
                                "reason": "RUN_NOT_FROZEN:" + str(receipt["run_status"])}
    elif receipt["validation_status"] != "PASSED":
        layers["native_run"] = {"proven": False,
                                "reason": "VALIDATION_NOT_PASSED:"
                                          + str(receipt["validation_status"])}
    elif not receipt["manifest_file_hashes_verified"]:
        layers["native_run"] = {"proven": False, "reason": "RUN_FILE_HASHES_UNVERIFIED"}
    else:
        layers["native_run"] = {"proven": True, "run_id": receipt["run_id"],
                                "requirement_closure_hash": receipt["requirement_closure_hash"],
                                "result_id": result["result_id"]}
    # The row layer is associated with the run that rendered it, which is not
    # always the run the native layer reports.
    bundle = (row or {}).get("bundle")
    if result is None:
        layers["public_row"] = {"proven": False, "reason": NOT_PROVEN + ":NO_RESULT"}
    elif row_ambiguity is not None:
        layers["public_row"] = {"proven": False, "reason": row_ambiguity}
    elif bundle is None:
        # No bundle beside any of this version's runs for this result. Three
        # things produce that and none of them is readable from here: the
        # renderer was never called, it refused, or - on a runs root a batch is
        # still writing - the Run has frozen and its bundle is not written yet.
        # The third was measured: a scan of a live batch found a FROZEN, PASSED,
        # EXACT run with no bundle, and re-reading the same directory a moment
        # later found the bundle present and accepted. Guessing which of the
        # three it is would be inventing a state.
        layers["public_row"] = {"proven": False,
                                "reason": NOT_PROVEN + ":NO_ROW_BUNDLE_BESIDE_THE_RUN"}
    elif bundle["status"] != "FROZEN_CANDIDATE":
        # A row rendered from a mechanical replay of an open Run is evidence of
        # something; it is not evidence that a frozen Run reached a public row.
        layers["public_row"] = {"proven": False,
                                "reason": "ROW_BUNDLE_IS_AN_OPEN_RUN_PREVIEW",
                                "rendered_by": row["receipt"]["run_id"]}
    else:
        layers["public_row"] = {"proven": True, "row_hash": bundle["row_hash"],
                                "evidence_count": bundle["evidence_count"],
                                "receipt_id": bundle["receipt_id"],
                                "period_selection_id": bundle["period_selection_id"],
                                # Named because it can differ from the run the
                                # native layer reports, and a reader should not
                                # have to assume they are the same.
                                "rendered_by": row["receipt"]["run_id"],
                                "renderer_sha256": bundle["renderer_sha256"],
                                "presentation_policy_sha256":
                                    bundle["presentation_policy_sha256"],
                                "also_rendered_by": row["rendered_by_other_runs"]}
    # The same predicate the withdrawal uses. Comparing only the result
    # identity here let one entry appear as both withdrawn_by and released.
    released = [entry["defect_id"] for entry in defects
                if _release_covers(defect=entry, result=result, receipt=receipt)]
    layers["content_acceptance"] = {
        "proven": False,
        "reason": NOT_PROVEN + ":NO_INDEPENDENT_CONTENT_CHECK_IS_RECORDED_FOR_THIS_ISSUE",
        "withdrawn_by": defect["defect_id"] if defect else None,
        "released_defect_ids": sorted(released)}
    return layers


def _position(*, company_id, report_end, ordinal, metric_id, established,
              original_saved, implemented, found, defects, candidate, closure=None,
              selection_id=None):
    """One target position, with its four states kept apart.

    A route can exist without a Run, and a Run can record a result whose
    content is wrong. Neither collapses into the other, so the status names
    which of the two is missing and the defect flag is separate from both.
    """
    fiscal_year, detail = None, None
    selection = _select_receipt(found=found, closure=closure,
                                selection_id=selection_id)
    receipt, result, ambiguity = (selection["receipt"], selection["result"],
                                  selection["ambiguity"])
    if found:
        fiscal_year = next(((entry["receipt"]["target_period"] or {}).get("fiscal_year")
                            for entry in (selection["candidates"] or found)), None)
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
    elif ambiguity is not None:
        # Nothing to choose between the receipts. Reporting any one of their
        # outcomes would be reporting a guess, and which guess would depend on
        # the order the run directories happened to be read in.
        status = ambiguity
        detail = {"note": _AMBIGUITY_NOTES[ambiguity],
                  "requirement_closure_hashes": sorted(
                      {entry["receipt"]["requirement_closure_hash"] for entry in found}),
                  "result_ids": sorted({entry["result"]["result_id"] for entry in found}),
                  # What the coordinate key does not distinguish, shown rather
                  # than summarised, because that is what the disagreement is
                  # about when the result identities are equal.
                  "measurements": sorted(
                      ({key: value for key, value in entry["identity"].items()
                        if key != "run_id"} for entry in found),
                      key=lambda measurement: content_hash(value=measurement))}
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
                              report_end=report_end, result=result, receipt=receipt)
    ran = result is not None
    return {"company_id": company_id, "report_end": report_end,
            "target_ordinal": ordinal, "fiscal_year": fiscal_year, "metric_id": metric_id,
            "first_blocking_reason": status, "status": status, "detail": detail,
            "target_period_established": established,
            "target_original_saved": original_saved,
            "historical_route_implemented": implemented,
            "native_run_receipt": ran,
            "run_receipt_count": len(found),
            # Several receipts for one coordinate that are not all in the same
            # state. The reported one is the strongest; this says the others
            # were not equal to it, so "FROZEN and PASSED" here does not mean
            # every Run recording this result froze and passed.
            "receipt_status_uniform": selection["status_uniform"],
            "run_id": receipt["run_id"] if receipt else None,
            "run_status": receipt["run_status"] if receipt else None,
            "requirement_closure_hash": receipt["requirement_closure_hash"] if receipt else None,
            "validation_status": receipt["validation_status"] if receipt else None,
            "result_id": (result or {}).get("result_id"),
            # The measurement behind the coordinate: the window actually
            # measured, the scope and the value kind. Carried out of the
            # selector so the summary reports what it merged on rather than
            # leaving the fields beside the key unread.
            "result_identity": selection["identity"],
            "period_selection_id": selection_id,
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
            # The three delivery layers, each with its own reason when it is
            # not proven. verified_outcome below is the first of them and is
            # not a delivery rate.
            "delivery": _delivery(receipt=receipt, result=result, status=status,
                                  defect=defect, defects=defects,
                                  row=selection["row"],
                                  row_ambiguity=selection["row_ambiguity"]),
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
    collected = ({"receipts": [], "unreadable": []} if runs_root is None
                 else collect_run_receipts(runs_root=runs_root))
    receipt_list = collected["receipts"]
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
                implemented = metric_id in wired or structural.structurally_not_applicable(
                    repo_root=repo_root, company_id=company_id, metric_id=metric_id)
                found = receipts.get((company_id, metric_id, report_end), [])
                position = _position(company_id=company_id, report_end=report_end,
                                     ordinal=candidate["target_ordinal"],
                                     metric_id=metric_id, established=established,
                                     original_saved=original_saved,
                                     implemented=implemented, found=found,
                                     defects=defects, candidate=candidate,
                                     closure=requirement_closure_hash,
                                     selection_id=entry["selection_id"])
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
                    "result_id": None, "result_identity": None,
                    "period_selection_id": None, "known_content_defect": None,
                    "receipt_status_uniform": True,
                    "delivery": _delivery(receipt=None, result=None,
                                          status="TARGET_PERIOD_NOT_DISCOVERED",
                                          defect=None, defects=defects),
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
    # The same frame counted by delivery layer. These are cumulative in
    # meaning, not by construction: a public row is only proven where a
    # bundle beside the Run names this result, and the third layer is zero
    # everywhere because nothing in this repository records an independent
    # content check.
    delivery = {name: sum(p["delivery"][name]["proven"] for p in positions)
                for name in ("native_run", "public_row", "content_acceptance")}
    # Reaching a public row and delivering a value are different facts, and the
    # layer count alone cannot tell them apart: a WITHHELD result renders a row
    # too, and so does a structural non-applicability. Measured on one company's
    # real material, 29 positions reached a public row and 7 of them carried a
    # value. Reporting 29 as delivery would be reading "the machinery ran" as
    # "the number is there", so the layers are crossed with what the position
    # actually says.
    # The bucket names are coarse on purpose, and each carries the statuses it
    # is made of so the grouping can be checked rather than trusted. An explicit
    # WITHHELD and a result that published no value are both "ran without a
    # value" and are not the same thing, so they are counted apart inside it.
    delivery_by_outcome = {}
    for position in positions:
        status = position["status"]
        outcome = ("VALUE" if status.startswith("VALUE_")
                   else "STRUCTURALLY_NOT_APPLICABLE" if status == "N_A_STRUCTURAL"
                   else "RAN_WITHOUT_A_VALUE" if status in {"WITHHELD_SOURCE_OR_ROUTE",
                                                            "NO_VALUE_PUBLISHED"}
                   else "NO_RESULT")
        row = delivery_by_outcome.setdefault(
            outcome, {"positions": 0, "native_run": 0, "public_row": 0,
                      "content_acceptance": 0, "statuses": {}})
        row["positions"] += 1
        row["statuses"][status] = row["statuses"].get(status, 0) + 1
        for name in ("native_run", "public_row", "content_acceptance"):
            row[name] += bool(position["delivery"][name]["proven"])
    unproven = {}
    for position in positions:
        for name, layer in position["delivery"].items():
            if layer["proven"]:
                continue
            reasons = unproven.setdefault(name, {})
            reasons[layer["reason"]] = reasons.get(layer["reason"], 0) + 1
    blocked_by_both = sum(1 for p in positions
                          if not p["target_original_saved"] and not p["historical_route_implemented"])
    body = {"record_type": RECORD_TYPE, "schema_version": 4,
            "declared_metric_ids": metrics, "declared_metric_count": len(metrics),
            "requested_years": years, "companies": selected,
            "requested_requirement_closure_hash": requirement_closure_hash,
            "target_frame_positions": len(selected) * len(metrics) * years,
            "enumerated_positions": len(positions),
            "wired_historical_metric_ids": list(WIRED_HISTORICAL_METRICS),
            "structural_applicability_metric_ids": list(STRUCTURAL_APPLICABILITY_METRICS),
            "a_route_can_be_company_specific": (
                "historical_route_implemented is per position, not per metric: eight "
                "metrics have a route only where the company's traits put them outside "
                "their own gate."),
            "first_blocking_reason_counts": counts, "status_counts": counts,
            "dimension_counts": dimensions,
            "delivery_layer_counts": delivery,
            "delivery_layer_unproven_reasons": unproven,
            "delivery_layers_are_not_one_number": (
                "a frozen validated Run, a rendered public row and an independent "
                "content check are three separate facts. Reporting the first as a "
                "delivery rate would read 'a Run exists' as 'the number is right and "
                "it reached the output'."),
            "positions_missing_source_and_route": blocked_by_both,
            "first_blocking_reason_is_not_the_only_blocker": True,
            # This frame renders nothing. A public row counts here only when
            # the renderer wrote a bundle beside the Run and that bundle names
            # this result; a position whose row was rendered into a driver's
            # memory and never persisted reads as NOT_PROVEN, which is what it
            # is from here.
            "public_rows_are_read_not_rendered": True,
            "company_reports": company_reports, "positions": positions,
            "run_receipts_read": len(receipt_list),
            # Directories under the runs root that hold a manifest their own
            # files do not match. Reported here rather than raised, because one
            # of them used to make the whole matrix unbuildable - and a runs
            # root read while a batch is writing always holds one. Each says
            # whether it reads as a run being written or as a directory that is
            # not the Run it claims.
            "unreadable_run_directories": collected["unreadable"],
            # Each delivery layer crossed with what the position says. A value,
            # a structural non-applicability and a frozen refusal all reach a
            # public row; only the first is a delivered number.
            "delivery_by_outcome": delivery_by_outcome,
            "runs_root_supplied": runs_root is not None,
            "business_execution_invoked": False,
            "policy_sha256": sha256_file(path=ROOT / POLICY_PATH),
            "module_sha256": sha256_file(path=Path(__file__)),
            "calls": {"provider": 0, "paid": 0, "sec": 0},
            "native_run_created": False, "production_authorized": False}
    _need(body["enumerated_positions"] == body["target_frame_positions"],
          "COVERAGE_FRAME_NOT_FULLY_ENUMERATED")
    return {**body, "matrix_id": content_hash(value=body)}
