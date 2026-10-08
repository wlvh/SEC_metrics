"""What the route implementation loaded right now does with a position.

This is a diagnostic, not a report. It exists because "why does this position
have no Run" is a real question, and the honest answer has two halves that
must not be merged:

* what a batch attempted, where it stopped, and under which version. That is
  in the batch's own records and is read by ``historical_attempt_records``;
* what the implementation loaded in this process does with the position today.
  That is this module.

Neither is stronger than the other. A position that ran yesterday and failed at
freeze leaves no result receipt, and code fixed since then prepares it without
complaint - so "it prepares today" is not evidence that nothing was attempted.
A position nothing ever touched can be declined by today's policy - so "it is
declined today" is not evidence that something was. **This module therefore
never reports on the past**, and says so in every record it returns.

Two properties it owes its caller:

* it runs the real route assembly, which reaches the metric calculator. That is
  the point of a diagnostic and the reason it must not be called from the
  coverage summary, whose contract is that it computes no outcome. Every record
  says ``business_execution_invoked`` is true;
* a route declining a position and the program breaking are different answers.
  Only the routes' own error classes are read as a decline. Anything else is a
  program fault, reported as one. ``AssertionError`` is never caught at all: a
  test that forbids a call by asserting must fail the diagnostic, not be turned
  into a tidy refusal.
"""
from pathlib import Path

RECORD_TYPE = "HISTORICAL_ROUTE_DIAGNOSIS"
DECLINED = "ROUTE_DECLINED"
PREPARED = "ROUTE_PREPARED_THE_POSITION"
FAULT = "PROGRAM_FAULT"

_CANNOT_SAY = ("This is the implementation loaded in this process, applied to the "
               "sources on disk now. It says nothing about whether this position "
               "was ever attempted, or about what any past attempt did.")


def _route_error_classes():
    """The error classes the historical routes raise to decline a position.

    Collected from the modules that own the declines rather than matched on
    message text, so a reworded reason stays a decline and an unrelated
    ``ValueError`` does not become one.
    """
    from .historical_amendment_admission import AmendmentAdmissionError
    from .historical_debt_results import HistoricalDebtError
    from .historical_filing_inventory import HistoricalFilingInventoryError
    from .historical_governance_input import HistoricalGovernanceError
    from .historical_metadata_context import HistoricalMetadataError
    from .historical_run import HistoricalRunError
    from .historical_structural_results import HistoricalStructuralError
    from .normal_companyfacts_results import NormalCompanyfactsError
    from .normal_zero_ai_results import NormalZeroAiError
    from .normal_period_selection import PeriodSelectionError
    return (AmendmentAdmissionError, HistoricalDebtError, HistoricalFilingInventoryError,
            HistoricalGovernanceError, HistoricalMetadataError, HistoricalRunError,
            HistoricalStructuralError, NormalCompanyfactsError, NormalZeroAiError,
            PeriodSelectionError)


def execution_identity(*, repo_root: Path) -> dict:
    """Which code and rules this diagnosis actually exercised.

    A diagnosis that does not name its own version can be read as a statement
    about the version a report is scoped to, which it is not. It cannot always
    name a Requirement closure: the engine a generation's snapshot needs is
    registered by the registration patch, so a tree without that patch can
    assemble a route and could not freeze a Run under it. That is recorded
    rather than worked around, because it bounds what the diagnosis means.
    """
    from .canonical import sha256_file
    from .historical_run import REQUIREMENT_ID
    from .requirement_profile import PROFILE_ENGINES
    from .canonical import strict_json_file
    root = Path(repo_root)
    manifest_path = root / "requirements" / REQUIREMENT_ID / "baseline_manifest.json"
    generation = None
    closure = None
    if manifest_path.is_file():
        manifest = strict_json_file(path=manifest_path)
        generation = manifest.get("requirement_generation")
        if generation in PROFILE_ENGINES:
            from .historical_run import _requirement
            closure = _requirement(root)["requirement_closure_hash"]
    return {"repo_root": str(root),
            "requirement_id": REQUIREMENT_ID,
            "requirement_generation": generation,
            "engine_registered_in_this_tree": generation in PROFILE_ENGINES,
            "requirement_closure_hash": closure,
            "closure_note": ("read from this tree's own snapshot" if closure else
                             "not readable here: this tree does not register the engine "
                             "this generation needs, so it can assemble a route and "
                             "could not freeze a Run under it"),
            "baseline_manifest_sha256": (sha256_file(path=manifest_path)
                                         if manifest_path.is_file() else None),
            "diagnosis_module_sha256": sha256_file(path=Path(__file__)),
            "closure_is_this_tree_not_a_reports_selector": True}


def diagnose_route(*, repo_root: Path, company_id: str, metric_id: str,
                   period_selection) -> dict:
    """Apply the loaded route to one position and report what it did.

    Args:
        repo_root: Repository or installed data root to read from.
        company_id: Configured company.
        metric_id: The metric whose route is exercised.
        period_selection: The pinned period selection for this position.

    Returns:
        A record whose ``outcome`` is ``ROUTE_DECLINED`` when a route error
        class was raised, ``PROGRAM_FAULT`` when anything else was, and
        ``ROUTE_PREPARED_THE_POSITION`` when assembly completed. A prepared
        position is not a claim that its Result would be published: assembly
        can return a withheld Result, and this does not inspect it.

    Raises:
        AssertionError: Never caught. A guard that asserts must be able to stop
            this, or a test that forbids a call would see its assertion
            reported as a refusal and pass.
    """
    from .historical_results import prepare_historical_run_input
    body = {"record_type": RECORD_TYPE, "company_id": company_id, "metric_id": metric_id,
            "period_selection_id": (period_selection or {}).get("selection_id"),
            "execution_identity": execution_identity(repo_root=repo_root),
            "what_this_cannot_say": _CANNOT_SAY,
            # The route assembly reaches the calculator. Saying so is the
            # difference between a diagnostic and a report.
            "business_execution_invoked": True,
            "calls": {"provider": 0, "paid": 0, "sec": 0},
            "native_run_created": False, "production_authorized": False}
    try:
        prepare_historical_run_input(repo_root=repo_root, company_id=company_id,
                                     metric_id=metric_id,
                                     period_selection=period_selection)
    except AssertionError:
        raise
    except _route_error_classes() as declined:
        return {**body, "outcome": DECLINED, "reason": str(declined),
                "error_type": type(declined).__name__,
                "category": getattr(declined, "category", None)}
    except Exception as fault:  # noqa: BLE001 - classified, not absorbed
        return {**body, "outcome": FAULT, "reason": str(fault),
                "error_type": type(fault).__name__,
                "category": getattr(fault, "category", None),
                "not_a_decline": ("no route error class was raised, so this is the "
                                  "program breaking rather than a route declining")}
    return {**body, "outcome": PREPARED, "reason": None, "error_type": None,
            "category": None,
            "result_content_not_inspected": ("assembly completed; whether its Result "
                                             "would be published is not read here")}
