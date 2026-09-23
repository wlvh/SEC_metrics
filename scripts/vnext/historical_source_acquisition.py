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
# ``repository`` and ``approver_login`` exist because the previous version
# proved only that two local files agreed with each other. Measured: a comment
# record and a policy written side by side in a temporary tree, with any author
# and any repository's URL, were accepted - so an approval could be written by
# the executor and then confirmed by the executor's other file.
REQUIRED_POLICY_FIELDS = ("requirement_id", "repository", "approver_login",
                          "delegation_url", "delegation_body_sha256",
                          "delegation_record_path", "budget_root",
                          "maximum_additional_provider_paid_sec_calls",
                          "scope", "sec_wiring_receipt_path")
DELEGATION_TYPE = "ISSUE_47_HISTORICAL_SEC_DELEGATION"
ISSUE_NUMBER = 47
# The trust anchor, and deliberately not a field of the allowance. An earlier
# version read ``repository`` and ``approver_login`` out of the same file it
# was verifying, so the file named its own approver. Measured against that:
# changing the comment author alone was refused, but changing the author *and*
# ``approver_login`` together was accepted, and so was moving the URL, the
# issue and ``repository`` to another repository together. A policy that picks
# its own authority proves only that it agrees with itself.
#
# This is the project's own identity, not a business literal: it says which
# repository's issue 47 can carry this issue's delegation. It follows the shape
# the repository already uses - Issue #28's frozen ``validate_comment`` binds
# the repository from outside the record and requires the comment's author to
# be that repository's owner.
TRUSTED_REPOSITORY = "wlvh/SEC_metrics"
TRUSTED_APPROVER = TRUSTED_REPOSITORY.split("/")[0]
# Not every declared dependency serves one named period, and requiring that it
# does refused the majority of the real declaration. Measured on the planner's
# own rows: a submissions index and the history shards carry
# ``historical_catalog``, and Company Facts carries metric ids - 71 of
# JPMorgan's 75 rows, including all 69 shards and the 12 SNAPSHOT_REFRESH rows
# the previous fix was supposed to unblock. A frame-level dependency is checked
# against the frame's own target window instead.
PERIOD_CONSUMER = "period:"
FRAME_BASIS = "FRAME_TARGET_WINDOW"
PERIOD_BASIS = "PERIOD_CONSUMERS"
SCOPE_FIELDS = ("purposes", "company_ids", "dependency_classes",
                "earliest_report_end", "latest_report_end")
_HEX64 = re.compile(r"\A[0-9a-f]{64}\Z")
_DATE = re.compile(r"\A[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
def _comment_url(*, repository):
    """The one URL shape this issue's delegation may have.

    Bound to the declared repository and to issue 47 rather than to "some
    GitHub issue comment", which is what let a URL from another repository
    through.
    """
    return re.compile(r"\Ahttps://github\.com/" + re.escape(repository)
                      + r"/issues/" + str(ISSUE_NUMBER)
                      + r"#issuecomment-([1-9][0-9]*)\Z")


class HistoricalAcquisitionError(ValueError):
    """A URL is not a declared dependency, or no allowance exists for Issue #47."""


def _need(condition, reason):
    if not condition:
        raise HistoricalAcquisitionError(reason)


def declared_frame(*, repo_root: Path, company_id: str, years: int = 5):
    """The whole declaration, plus the target window the frame is asking for.

    Two kinds of dependency live in here and the difference matters to scope.
    Some serve named periods - an annual primary, an accession index. Others
    serve the frame itself: a submissions index and its history shards are what
    make the target periods discoverable at all, and Company Facts answers
    several metrics across every period. Those carry no ``period:`` consumer,
    and the target window they serve is the frame's.
    """
    # Imported here because that module imports this one's error type; the
    # declaration is a successor to the planner, not a layer above it.
    from .historical_event_sources import declare_event_sources
    plan = plan_historical_sources(repo_root=Path(repo_root), company_id=company_id,
                                   count=years)
    targets = sorted({candidate["report_date"] for candidate in plan["target_candidates"]
                      if candidate.get("report_date")})
    # The planner declares four dependency classes and no event class, so the
    # fiscal-year 8-K bodies and headers the zero-AI route reads for C01 and
    # E01-E05 were refused by the gate as undeclared - every one of them. The
    # planner is a NEW_RULE_FILE of this generation and extending it would move
    # the closure the last batch's frozen Runs were produced under, so the
    # event declaration is made beside it and unioned here.
    events = declare_event_sources(repo_root=Path(repo_root), company_id=company_id,
                                   count=years)
    requirements = _union(planned=plan["requirements"], added=events["requirements"])
    # The same hole, for the same reason, one metric later: C02's second source
    # is the annual meeting's proxy, or the amendment that adds Part III where
    # a company puts its governance information there, and the planner declares
    # neither. Ten of the 82 proxies the saved indexes list have accession
    # material and all ten were filed in 2026, so every earlier period names a
    # document the gate would refuse as undeclared.
    from .historical_governance_sources import governance_dependencies
    governance = governance_dependencies(repo_root=Path(repo_root), company_id=company_id,
                                         report_ends=targets)
    requirements = _union(planned=requirements, added=governance["requirements"])
    return {"requirements": requirements, "target_report_dates": targets,
            "company_id": company_id, "plan_id": plan["plan_id"],
            "event_declaration_limitations": events["limitations"],
            "governance_declaration_limitations": governance["limitations"]}


def _union(*, planned, added):
    """One row per URL, with both declarations' roles and consumers kept.

    A URL both sides declare is one requirement, not two: ``historical_dependency``
    refuses a URL the declaration lists twice, because a plan that stopped
    being deduplicated is a different problem from a missing file. The planner's
    row wins on the saved-state fields - it and the successor classify through
    the same ``_saved_state``, so they agree, and preferring one of them keeps
    that agreement checkable instead of assumed.
    """
    merged = {row["source_url"]: dict(row) for row in planned}
    for row in added:
        existing = merged.get(row["source_url"])
        if existing is None:
            merged[row["source_url"]] = dict(row)
            continue
        existing["source_roles"] = sorted(set(existing["source_roles"])
                                          | set(row["source_roles"]))
        existing["consumers"] = sorted(set(existing["consumers"]) | set(row["consumers"]))
        existing.setdefault("also_declared_by", []).append(row["declared_by"])
    return [merged[url] for url in sorted(merged)]


def declared_dependencies(*, repo_root: Path, company_id: str, years: int = 5):
    """Every source this company's five-year frame declares, saved or not.

    Whether a URL belongs to the task and whether it still needs fetching are
    two questions, and an earlier version answered only the second. Measured
    against that: a dependency already saved was refused as "not a declared
    dependency", so the reuse branch behind the gate could never be reached,
    and a row the planner marks ``SNAPSHOT_REFRESH`` - stale bytes that are
    intact but disagree with the index - was short-circuited as a reuse and
    never reached a request.
    """
    return declared_frame(repo_root=repo_root, company_id=company_id,
                          years=years)["requirements"]


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
    # The allowance may restate the anchor; it may not choose it. Both fields
    # are compared against the constants above rather than merely typed, so a
    # policy cannot move the approval to another repository or another approver
    # by editing itself and the record it points at in the same breath.
    _need(policy["repository"] == TRUSTED_REPOSITORY,
          "ISSUE_47_ALLOWANCE_NAMES_ANOTHER_REPOSITORY:" + str(policy["repository"])[:60]
          + " (trusted: " + TRUSTED_REPOSITORY + ")")
    _need(policy["approver_login"] == TRUSTED_APPROVER,
          "ISSUE_47_ALLOWANCE_NAMES_ANOTHER_APPROVER:" + str(policy["approver_login"])[:60]
          + " (trusted: " + TRUSTED_APPROVER + ")")
    _need(_comment_url(repository=policy["repository"]).match(
        str(policy["delegation_url"]) or ""),
        "ISSUE_47_ALLOWANCE_URL_IS_NOT_THIS_ISSUE_S_COMMENT:"
        + str(policy["delegation_url"])[:70])
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


def github_comment_reader(path):
    """Read one comment from GitHub, through the boundary the repository uses.

    Kept as a named function so the live path has one, and so a test can pass
    a different reader without the production path ever having a default that
    returns a local file.
    """
    from .annual_candidate import _github
    return _github(path)


def _provenance(*, comment, policy, where):
    """The fields that say this comment is the approval, not a copy of one."""
    match = _comment_url(repository=policy["repository"]).match(policy["delegation_url"])
    issue_api = ("https://api.github.com/repos/" + policy["repository"]
                 + "/issues/" + str(ISSUE_NUMBER))
    _need(comment.get("html_url") == policy["delegation_url"]
          and str(comment.get("id")) == match[1]
          and comment.get("issue_url") == issue_api,
          "ISSUE_47_DELEGATION_IS_NOT_ON_THIS_ISSUE:" + where)
    _need(comment.get("user", {}).get("login") == policy["approver_login"],
          "ISSUE_47_DELEGATION_AUTHOR_IS_NOT_THE_APPROVER:" + where + ":"
          + str(comment.get("user", {}).get("login")))


def _delegation(*, repo_root: Path, policy, reader=None):
    """The approved text itself, re-hashed, and required to say the same thing.

    Three layers, because the previous two were not enough. The body the digest
    names is read and re-hashed - a digest nothing is hashed against is
    decoration. The body must restate the limits, budget root and scope, so the
    policy cannot grant more than the approval did. And the comment must carry
    the provenance of an approval on this issue by the declared approver.

    ``reader`` is what separates a real approval from a local copy of one.
    Verified against the previous version: a comment record and a policy
    written side by side in a temporary tree were accepted, with any author and
    any repository's URL. When a reader is supplied - the live path always
    supplies one - the comment is fetched from GitHub and the local record must
    match it byte for byte, so a pair the executor wrote cannot authorize.
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
    _provenance(comment=comment, policy=policy, where="saved_record")
    if reader is not None:
        match = _comment_url(repository=policy["repository"]).match(policy["delegation_url"])
        fetched = reader("repos/" + policy["repository"] + "/issues/comments/" + match[1])
        _need(type(fetched) is dict, "ISSUE_47_DELEGATION_FETCH_DID_NOT_RETURN_A_COMMENT")
        _provenance(comment=fetched, policy=policy, where="fetched")
        _need(fetched.get("body") == comment["body"],
              "ISSUE_47_SAVED_DELEGATION_DIFFERS_FROM_THE_ONE_ON_GITHUB")
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
    return {**approved, "provenance_verified_against_github": reader is not None}


def acquisition_allowance(*, repo_root: Path, delegation_reader=None):
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
    policy["approved_delegation"] = _delegation(repo_root=repo_root, policy=policy,
                                                reader=delegation_reader)
    return policy


def request_is_in_scope(*, allowance, company_id, dependency, purpose,
                       frame_report_dates=None):
    """Whether this exact request is one the approval covers.

    A URL being a real dependency is not the same as this grant allowing it to
    be fetched. Both have to hold: the declaration answers the first, and this
    answers the second, over the company, the dependency class and the periods
    the dependency serves.

    ``frame_report_dates`` is what a frame-level dependency is checked against.
    Requiring a ``period:`` consumer on every row refused the submissions index,
    every history shard and Company Facts - most of the real declaration - and
    the case that was supposed to prove refresh worked did not catch it,
    because it reused an annual row that happens to carry a period tag. The
    fix is not to drop the window check but to name the right window: a
    dependency that makes the targets discoverable is in scope when the targets
    are.
    """
    scope = allowance["scope"]
    _need(purpose in scope["purposes"],
          "ISSUE_47_PURPOSE_NOT_IN_SCOPE:" + str(purpose))
    _need(company_id in scope["company_ids"],
          "ISSUE_47_COMPANY_NOT_IN_SCOPE:" + str(company_id))
    _need(dependency["dependency_class"] in scope["dependency_classes"],
          "ISSUE_47_DEPENDENCY_CLASS_NOT_IN_SCOPE:"
          + str(dependency["dependency_class"]))
    named = sorted({consumer.split(":")[1]
                    for consumer in dependency.get("consumers", [])
                    if str(consumer).startswith(PERIOD_CONSUMER)
                    and len(str(consumer).split(":")) > 1})
    if named:
        periods, basis = named, PERIOD_BASIS
    else:
        periods = sorted(frame_report_dates or ())
        basis = FRAME_BASIS
        _need(periods,
              "ISSUE_47_FRAME_TARGET_WINDOW_UNKNOWN:"
              + str(dependency["dependency_class"]))
    outside = [period for period in periods
               if not scope["earliest_report_end"] <= period <= scope["latest_report_end"]]
    _need(not outside, "ISSUE_47_TARGET_PERIOD_NOT_IN_SCOPE:" + ",".join(outside))
    return {"company_id": company_id, "purpose": purpose,
            "dependency_class": dependency["dependency_class"],
            "periods": periods, "period_basis": basis}
