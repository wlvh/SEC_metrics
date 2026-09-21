"""Issue #47's own declared SEC dependency set, and the gate a fetch must pass.

The acquisition CLI gates a URL on ``normal_source_requirements.
discover_saved_source_requirements``, whose scope is the current annual period.
Measured, it reaches exactly one year back: salesforce ``crm-20250131.htm`` is
accepted and ``crm-20240131.htm`` is refused with "URL is not a declared
dependency of this company". The five-year frame needs four.

So class A of the acquisition plan was not only waiting for permission. The
declaration already exists - ``plan_historical_sources`` produces it,
deduplicated, with every URL, accession, role and saved state - and the
acquisition entry point does not read it. This reads it.

What this is not: a way around the gate. The gate is what stops an arbitrary
URL from being fetched, and the fix is to give it the historical declaration
rather than to remove it. A URL this module does not find in the plan is
refused by name.

Why a separate module: ``tools/vnext_continuous_sec.py`` and
``scripts/vnext/normal_source_requirements.py`` are both named in
``config/issue28_continuous_calls_v1.json``'s ``rule_paths`` and in
``issue_28_v14``'s baseline, so editing either would break the approved call
policy's own binding. This one is not a rule file for the same reason
``historical_coverage.py`` is not: it plans and gates, it does not execute a
Run, so nothing about a Run's meaning depends on its bytes.

Execution is deliberately absent. ``continuous_sec_acquisition.live_sec_session``
hard-binds ``issue_28_v14`` and its ledger reads that issue's delegation, budget
root and limits, so reusing it for Issue #47 would be drawing on Issue #28's
allowance - which this issue's own text forbids. Issue #47 needs its own
allowance record before any request, and ``acquisition_allowance`` names
exactly what is missing rather than failing vaguely.
"""
import json
from pathlib import Path

from .normal_history_plan import plan_historical_sources

RECORD_TYPE = "ISSUE_47_HISTORICAL_SOURCE_DEPENDENCY"
REQUIREMENT_ID = "issue_47_v1"
# The allowance record this issue would need, mirroring the shape Issue #28's
# own policy has. It does not exist, and that is the point: the refusal below
# names a path rather than a feeling.
POLICY_PATH = "config/issue47_historical_calls_v1.json"
REQUIRED_POLICY_FIELDS = ("requirement_id", "delegation_url", "delegation_body_sha256",
                          "budget_root", "maximum_additional_provider_paid_sec_calls",
                          "scope")


class HistoricalAcquisitionError(ValueError):
    """A URL is not a declared dependency, or no allowance exists for Issue #47."""


def _need(condition, reason):
    if not condition:
        raise HistoricalAcquisitionError(reason)


def historical_dependencies(*, repo_root: Path, company_id: str, years: int = 5):
    """Every source this company's frame needs that is not already saved.

    Args:
        repo_root: Data root holding the saved submissions metadata.
        company_id: Configured company.
        years: How many annual report ends the frame asks for.

    Returns:
        The planner's own ``new_acquisition_required`` requirements, in its
        order. Deduplicated by the planner: a year serving as both a target and
        the next year's prior-period input is one requirement, not two.
    """
    plan = plan_historical_sources(repo_root=Path(repo_root), company_id=company_id,
                                   count=years)
    return [row for row in plan["requirements"] if row["new_acquisition_required"]]


def historical_dependency(*, repo_root: Path, company_id: str, url: str, years: int = 5):
    """The one declared dependency this URL is, or a refusal naming the URL.

    Raises:
        HistoricalAcquisitionError: When the URL is not in the declaration, or
            is in it more than once. Both are refusals rather than a choice:
            fetching a URL nothing declared is what the gate exists to stop,
            and a URL the plan lists twice means the plan stopped being
            deduplicated, which is a different problem from a missing file.
    """
    matches = [row for row in historical_dependencies(repo_root=repo_root,
                                                      company_id=company_id, years=years)
               if row["source_url"] == url]
    _need(matches, "HISTORICAL_URL_IS_NOT_A_DECLARED_DEPENDENCY:" + url)
    _need(len(matches) == 1, "HISTORICAL_URL_IS_DECLARED_MORE_THAN_ONCE:" + url)
    return matches[0]


def offline_source_plan(*, repo_root: Path, company_id: str, url: str, years: int = 5):
    """One dependency, checked and recorded, with nothing fetched.

    Returns:
        The dependency record with its plan status and a zero call triple. This
        is the whole of what can be produced without an allowance.
    """
    dependency = historical_dependency(repo_root=repo_root, company_id=company_id,
                                       url=url, years=years)
    return {"record_type": RECORD_TYPE, "schema_version": 1, "status": "OFFLINE_SOURCE_PLAN",
            "requirement_id": REQUIREMENT_ID, "company_id": company_id,
            "dependency": dependency, "calls": [0, 0, 0],
            "allowance": "NOT_GRANTED", "production_authorized": False}


def acquisition_allowance(*, repo_root: Path):
    """Issue #47's own SEC allowance, or a refusal naming what is missing.

    Issue #28's allowance is bound to ``requirement_id`` ``issue_28_v14`` and to
    its own coordinate scope, and this issue's text forbids drawing on it. So
    the check is for Issue #47's own record and never falls back.

    Raises:
        HistoricalAcquisitionError: Always, while no such record exists. The
            reason names the path and the fields it would have to carry, so the
            ask is a described object rather than a number in a document.
    """
    path = Path(repo_root) / POLICY_PATH
    _need(path.is_file() and not path.is_symlink(),
          "ISSUE_47_SEC_ALLOWANCE_NOT_GRANTED:" + POLICY_PATH + ":needs "
          + ",".join(REQUIRED_POLICY_FIELDS))
    policy = json.loads(path.read_text(encoding="utf-8"))
    missing = [field for field in REQUIRED_POLICY_FIELDS if field not in policy]
    _need(not missing, "ISSUE_47_SEC_ALLOWANCE_INCOMPLETE:" + ",".join(missing))
    _need(policy["requirement_id"] == REQUIREMENT_ID,
          "ISSUE_47_SEC_ALLOWANCE_IS_FOR_ANOTHER_REQUIREMENT:"
          + str(policy["requirement_id"]))
    return policy
