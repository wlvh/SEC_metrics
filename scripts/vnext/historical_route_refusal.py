"""Why a wired position has no Run: refused today, or simply not run yet.

``ROUTE_IMPLEMENTED_NOT_RUN`` conflates two different facts. A position the
batch never reached and a position the batch reached and was refused by an
approved policy both arrive there, because the coverage summary reads Run
receipts and a refusal leaves no receipt. The consequence is not cosmetic: the
table says "never run" about positions that have a determinate, reproducible
blocker, so whoever continues has to remember a conversation to pick the next
step.

The fix is not to remember the failure. A route that refuses a position today
refuses it for anyone who asks, so the refusal is derivable from the repository
alone - which is stronger than an attempt log, because a recorded attempt is an
assertion about the past and this is a measurement of the present. What an
attempt log would add is the distinction between "was attempted" and "was
never attempted", and that distinction does not change what to do next: a
refused position needs its refusal resolved whether or not anyone has already
tried it.

Asking costs a route preparation per position - measured at 6 to 14 seconds on
this repository's filings - so the caller opts in. The summary never claims
"never attempted" either way: without the derivation it says the distinction
was not computed.

This module only asks. It creates no Run, writes nothing, and makes no SEC or
model request.
"""
from pathlib import Path

REFUSAL_RECORD_TYPE = "HISTORICAL_ROUTE_REFUSAL"


def probe_route_refusal(*, repo_root: Path, company_id: str, metric_id: str,
                        period_selection) -> dict:
    """Ask the historical route what it does with this position right now.

    Args:
        repo_root: Repository or installed data root to read from.
        company_id: Configured company.
        metric_id: The metric whose route is asked.
        period_selection: The pinned period selection for this position.

    Returns:
        A record whose ``refused`` says whether the route declined. When it
        did, ``reason`` and ``error_type`` carry the route's own words; the
        reason is not translated, because a reason code that has been reworded
        by the reporting layer cannot be matched against the route that emits
        it. When it did not, the position is genuinely unrun: a Run could be
        created from the inputs this returned.
    """
    from .historical_results import prepare_historical_run_input
    body = {"record_type": REFUSAL_RECORD_TYPE, "company_id": company_id,
            "metric_id": metric_id,
            "period_selection_id": period_selection.get("selection_id"),
            "calls": {"provider": 0, "paid": 0, "sec": 0},
            "native_run_created": False, "production_authorized": False}
    try:
        prepare_historical_run_input(repo_root=repo_root, company_id=company_id,
                                     metric_id=metric_id,
                                     period_selection=period_selection)
    except Exception as refusal:  # noqa: BLE001 - the route's own class is the answer
        return {**body, "refused": True, "reason": str(refusal),
                "error_type": type(refusal).__name__,
                "category": getattr(refusal, "category", None)}
    return {**body, "refused": False, "reason": None, "error_type": None,
            "category": None}
