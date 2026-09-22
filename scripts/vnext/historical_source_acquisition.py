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
import re
from pathlib import Path

from .normal_history_plan import plan_historical_sources

RECORD_TYPE = "ISSUE_47_HISTORICAL_SOURCE_DEPENDENCY"
REQUIREMENT_ID = "issue_47_v1"
# The allowance record this issue would need, mirroring the shape Issue #28's
# own policy has. It does not exist, and that is the point: the refusal below
# names a path rather than a feeling.
POLICY_PATH = "config/issue47_historical_calls_v1.json"
# ``sec_wiring_receipt_path`` mirrors the field Issue #28's own policy carries.
# A grant has to name a receipt proving the execution chain was exercised
# offline first, because an execution path that first runs on the day it is
# authorized is a path nobody has run - which is how this issue's own
# "each part worked alone and the seam did not" failures happened.
#
# ``delegation_record_path`` exists because the previous version checked only
# that ``delegation_url`` and ``delegation_body_sha256`` were non-empty.
# Measured: a policy carrying ``delegation_url = "NOT-A-URL-AT-ALL"`` and
# ``delegation_body_sha256 = "NOT-A-DIGEST"`` built a LIVE session and passed
# the pre-request check, because no code path ever read the body those fields
# describe. A digest nothing is hashed against is decoration.
REQUIRED_POLICY_FIELDS = ("requirement_id", "delegation_url", "delegation_body_sha256",
                          "delegation_record_path", "budget_root",
                          "maximum_additional_provider_paid_sec_calls",
                          "scope", "sec_wiring_receipt_path")
DELEGATION_TYPE = "ISSUE_47_HISTORICAL_SEC_DELEGATION"
SCOPE_FIELDS = ("purposes", "company_ids", "dependency_classes",
                "earliest_report_end", "latest_report_end")
_HEX64 = re.compile(r"\A[0-9a-f]{64}\Z")
_DATE = re.compile(r"\A[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
_COMMENT_URL = re.compile(
    r"\Ahttps://github\.com/[^/]+/[^/]+/issues/[0-9]+#issuecomment-[0-9]+\Z")


class HistoricalAcquisitionError(ValueError):
    """A URL is not a declared dependency, or no allowance exists for Issue #47."""


def _need(condition, reason):
    if not condition:
        raise HistoricalAcquisitionError(reason)


def declared_dependencies(*, repo_root: Path, company_id: str, years: int = 5):
    """Every source this company's five-year frame declares, saved or not.

    Whether a URL belongs to the task and whether it still needs fetching are
    two questions, and the previous version answered only the second. Measured
    against that: a dependency already saved was refused as "not a declared
    dependency", so the reuse branch behind the gate could never be reached,
    and a row the planner marks ``SNAPSHOT_REFRESH`` - stale bytes that are
    intact but disagree with the index - was short-circuited as a reuse and
    never reached a request.
    """
    plan = plan_historical_sources(repo_root=Path(repo_root), company_id=company_id,
                                   count=years)
    return list(plan["requirements"])


def historical_dependencies(*, repo_root: Path, company_id: str, years: int = 5):
    """The declared sources that still need acquiring, in the planner's order.

    Deduplicated by the planner: a year serving as both a target and the next
    year's prior-period input is one requirement, not two. This is the listing
    view; admission uses ``declared_dependencies`` so that being saved is not
    the same as being unknown.
    """
    return [row for row in declared_dependencies(repo_root=repo_root,
                                                 company_id=company_id, years=years)
            if row["new_acquisition_required"]]


def historical_dependency(*, repo_root: Path, company_id: str, url: str, years: int = 5):
    """The one declared dependency this URL is, or a refusal naming the URL.

    Searches everything the frame declares, not only what is still outstanding,
    so an already-saved source resolves to its row and the caller can answer
    "needs no fetch" instead of "nothing declared this".

    Raises:
        HistoricalAcquisitionError: When the URL is not in the declaration, or
            is in it more than once. Both are refusals rather than a choice:
            fetching a URL nothing declared is what the gate exists to stop,
            and a URL the plan lists twice means the plan stopped being
            deduplicated, which is a different problem from a missing file.
    """
    matches = [row for row in declared_dependencies(repo_root=repo_root,
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


def _typed(policy):
    """Every field's shape, before anything downstream trusts its meaning."""
    _need(_HEX64.match(str(policy["delegation_body_sha256"]) or ""),
          "ISSUE_47_ALLOWANCE_DIGEST_IS_NOT_A_SHA256:"
          + str(policy["delegation_body_sha256"])[:40])
    _need(_COMMENT_URL.match(str(policy["delegation_url"]) or ""),
          "ISSUE_47_ALLOWANCE_URL_IS_NOT_AN_ISSUE_COMMENT:"
          + str(policy["delegation_url"])[:60])
    limits = policy["maximum_additional_provider_paid_sec_calls"]
    _need(type(limits) is list and len(limits) == 3
          and all(type(value) is int and value >= 0 for value in limits),
          "ISSUE_47_ALLOWANCE_LIMITS_MALFORMED:" + str(limits)[:40])
    for field in ("budget_root", "delegation_record_path", "sec_wiring_receipt_path"):
        _need(type(policy[field]) is str and policy[field],
              "ISSUE_47_ALLOWANCE_FIELD_MALFORMED:" + field)
    scope = policy["scope"]
    _need(type(scope) is dict, "ISSUE_47_ALLOWANCE_SCOPE_MALFORMED")
    missing = [field for field in SCOPE_FIELDS if field not in scope]
    _need(not missing, "ISSUE_47_ALLOWANCE_SCOPE_INCOMPLETE:" + ",".join(missing))
    for field in ("purposes", "company_ids", "dependency_classes"):
        _need(type(scope[field]) is list and scope[field]
              and all(type(value) is str and value for value in scope[field]),
              "ISSUE_47_ALLOWANCE_SCOPE_LIST_MALFORMED:" + field)
    for field in ("earliest_report_end", "latest_report_end"):
        _need(_DATE.match(str(scope[field]) or ""),
              "ISSUE_47_ALLOWANCE_SCOPE_DATE_MALFORMED:" + field)
    _need(scope["earliest_report_end"] <= scope["latest_report_end"],
          "ISSUE_47_ALLOWANCE_SCOPE_WINDOW_INVERTED")


def _delegation(*, repo_root: Path, policy):
    """The approved text itself, re-hashed, and required to say the same thing.

    This is the check whose absence the review reproduced. Reading the body the
    digest describes is what makes the digest mean anything, and requiring the
    body to restate the limits, budget root and scope is what stops a policy
    file from widening a grant the approver never gave: the policy is a pointer
    to an approval, not a second place the approval can be written.
    """
    from .canonical import sha256_bytes, strict_json_file
    path = Path(repo_root) / policy["delegation_record_path"]
    _need(path.is_file() and not path.is_symlink(),
          "ISSUE_47_DELEGATION_RECORD_MISSING:" + policy["delegation_record_path"])
    comment = strict_json_file(path=path)
    _need(type(comment.get("body")) is str and comment["body"],
          "ISSUE_47_DELEGATION_RECORD_HAS_NO_BODY")
    _need(sha256_bytes(content=comment["body"].encode("utf-8"))
          == policy["delegation_body_sha256"],
          "ISSUE_47_DELEGATION_BODY_DOES_NOT_MATCH_ITS_DIGEST")
    _need(comment.get("html_url") == policy["delegation_url"],
          "ISSUE_47_DELEGATION_RECORD_IS_FOR_ANOTHER_COMMENT:"
          + str(comment.get("html_url"))[:60])
    try:
        approved = json.loads(comment["body"])
    except ValueError:
        raise HistoricalAcquisitionError("ISSUE_47_DELEGATION_BODY_IS_NOT_A_RECORD")
    _need(approved.get("record_type") == DELEGATION_TYPE,
          "ISSUE_47_DELEGATION_RECORD_TYPE_CHANGED:" + str(approved.get("record_type")))
    _need(approved.get("requirement_id") == REQUIREMENT_ID,
          "ISSUE_47_DELEGATION_IS_FOR_ANOTHER_REQUIREMENT:"
          + str(approved.get("requirement_id")))
    for field in ("maximum_additional_provider_paid_sec_calls", "budget_root", "scope"):
        _need(approved.get(field) == policy[field],
              "ISSUE_47_ALLOWANCE_WIDENS_THE_APPROVED_GRANT:" + field)
    _need(approved.get("production_authorized") is False,
          "ISSUE_47_DELEGATION_MUST_NOT_AUTHORIZE_PRODUCTION")
    return approved


def acquisition_allowance(*, repo_root: Path):
    """Issue #47's own SEC allowance, verified rather than merely present.

    Issue #28's allowance is bound to ``requirement_id`` ``issue_28_v14`` and to
    its own coordinate scope, and this issue's text forbids drawing on it. So
    the check is for Issue #47's own record and never falls back.

    Field presence is not authorization. The shapes are checked, then the
    approved body the digest names is read and re-hashed, then the body is
    required to restate the limits, budget root and scope so the policy cannot
    grant more than the approval did.

    Raises:
        HistoricalAcquisitionError: While no such record exists, naming the
            path and the fields it must carry; or when any of the above fails,
            naming which one.
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
    _typed(policy)
    policy["approved_delegation"] = _delegation(repo_root=repo_root, policy=policy)
    return policy


def request_is_in_scope(*, allowance, company_id, dependency, purpose):
    """Whether this exact request is one the approval covers.

    A URL being a real dependency of the task is not the same as this grant
    allowing it to be fetched. Both have to hold: the gate above answers the
    first, and this answers the second, over the company, the dependency class
    and the target periods the dependency serves.
    """
    scope = allowance["scope"]
    _need(purpose in scope["purposes"],
          "ISSUE_47_PURPOSE_NOT_IN_SCOPE:" + str(purpose))
    _need(company_id in scope["company_ids"],
          "ISSUE_47_COMPANY_NOT_IN_SCOPE:" + str(company_id))
    _need(dependency["dependency_class"] in scope["dependency_classes"],
          "ISSUE_47_DEPENDENCY_CLASS_NOT_IN_SCOPE:"
          + str(dependency["dependency_class"]))
    periods = sorted({consumer.split(":")[1] for consumer in dependency.get("consumers", [])
                      if consumer.startswith("period:") and len(consumer.split(":")) > 1})
    _need(periods, "ISSUE_47_DEPENDENCY_SERVES_NO_NAMED_PERIOD")
    outside = [period for period in periods
               if not scope["earliest_report_end"] <= period <= scope["latest_report_end"]]
    _need(not outside, "ISSUE_47_TARGET_PERIOD_NOT_IN_SCOPE:" + ",".join(outside))
    return {"company_id": company_id, "purpose": purpose,
            "dependency_class": dependency["dependency_class"], "periods": periods}
