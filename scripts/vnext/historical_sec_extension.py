"""A further SEC allowance that extends Issue #47's exhausted ledger by the owner's decision.

Purpose: The first approval (``config/issue47_historical_calls_v1.json``) was
spent to its cap: 1130 requests plus the 224 charged for the segment a lost
container may have sent. The acquisition then showed that part of what it saved
was stale - a history block whose rows SEC had since moved, an index fetched
before its blocks were renumbered - and that one Southwest request had failed.
Finishing the five-year frame needs more requests, some of them to URLs the
ledger has already requested once. The owner decided on one further approval
(in the session; the decision as the executor transcribed it is in the evidence).

What an extension is, and why it is not a second ledger: the checkpoint the
frozen validator replays covers every row past the trusted baseline, so a
second ledger over the first one's data root could not register what it
fetched without re-counting the first one's slots. An extension instead lets
the same ledger continue: the same root, binding, slots, claim log, start
marker and export, with the cap raised by what the owner approves and the
grants replaced by the ones the owner approves. Nothing about the first
approval changes; its body, record and policy stay as they were registered.

What the owner's comment says, in its own words: the ledger state it extends
(the claim log's digest and size, as the committed export carries them - so it
can extend that ledger and no other), how many more requests, which company may
draw which class over which window, and which already-requested URLs may be
requested once more - only rows the planner marks as a refresh of a saved copy
that disagrees with its index, or as the replacement of a copy whose last
request failed, and once per extension. A re-request carries the extension's
ordinal in its request, so its digest differs from the first request's and the
ledger's rule against drawing the same request twice holds within the
extension.

What this does not change: every check the first approval passes through - the
comment fetched back from GitHub, posted directly by the owner's account,
unedited, restating what the policy grants; the offline wiring receipt; the
published start or resume; the ledger's slot, terminal and claim-log rules -
applies to the extension the same way. And, as for the first approval, the
gates bind the executor's code path, not the executor.

Call relationships: ``historical_sec_session`` reads the extension on the live
path and pins it on the ledger; ``tools/vnext_historical_sec.py
register-extension`` writes it from the posted comment;
``tools/propose_historical_extension.py`` builds the body the owner posts.
Zero SEC or provider calls.
"""
import json
import re
from pathlib import Path

from .canonical import CanonicalError, sha256_bytes, strict_json_file, strict_json_loads
from .historical_source_acquisition import (REQUIREMENT_ID, TRUSTED_APPROVER,
                                            TRUSTED_REPOSITORY, SCOPE_FIELDS,
                                            HistoricalAcquisitionError, _comment_url,
                                            _posted_by_the_approver_directly, _provenance,
                                            _typed_grants, posted_text)

EXTENSION_TYPE = "ISSUE_47_HISTORICAL_SEC_DELEGATION_EXTENSION"
EXTENSION_ORDINAL = 1
EXTENSION_POLICY_PATH = "config/issue47_historical_calls_v1_extension_1.json"
EXTENSION_DIRECTORY = "docs/evidence/issue47_history/acquisition-extension"
EXTENSION_RECORD_PATH = EXTENSION_DIRECTORY + "/approval-comment.json"
EXTENSION_BODY_PATH = EXTENSION_DIRECTORY + "/approval-comment-body.json"
# What the owner approves, byte for byte: the body
# tools/propose_historical_extension.py wrote to EXTENSION_BODY_PATH (cap 513:
# the 471 first pinned, the independent review's findings fixed before that,
# plus the annual accessions' XBRL instances C04 and B06 read - 40 declarable
# today and 2 bounded by the most instances any saved index names). A proposal
# edited after the approval must not move what the approval means, so the
# digest is pinned here rather than read from the proposal.
EXTENSION_BODY_SHA256 = "090c60f25ab0883df25014c9772ab93884b70b2124df142fb92227742a6b75ec"
REQUIRED_EXTENSION_FIELDS = ("requirement_id", "repository", "approver_login",
                             "extension_ordinal", "delegation_url",
                             "delegation_body_sha256", "delegation_record_path", "extends",
                             "budget_root", "maximum_additional_provider_paid_sec_calls",
                             "scope", "reclaim")
# The two reasons an already-requested URL may be requested again, each named
# by the planner, never by the caller: a saved copy that disagrees with the
# index it was declared under, and a copy whose last request failed.
RECLAIM_KINDS = ("SNAPSHOT_REFRESH", "REPLACEMENT_ACQUISITION")
LEDGER_STATE_FIELDS = ("export_id", "claims", "claim_count", "resumes", "cumulative")
# The files an extension is registered as; the branch tip must carry the same.
EXTENSION_FILES = (EXTENSION_POLICY_PATH, EXTENSION_RECORD_PATH)
# The planner's reason for a saved copy whose last request failed
# (annual_update.saved_source).
FAILED_REQUEST_REASON = "LATEST_SOURCE_REQUEST_FAILED"
_HEX64 = re.compile(r"\A[0-9a-f]{64}\Z")


class HistoricalExtensionError(HistoricalAcquisitionError):
    """An extension is absent where required, malformed, or not what the owner approved."""


def _need(condition, reason):
    if not condition:
        raise HistoricalExtensionError(reason)


def _typed_limits(limits, where):
    _need(type(limits) is list and len(limits) == 3
          and all(type(value) is int and value >= 0 for value in limits),
          "ISSUE_47_EXTENSION_LIMITS_MALFORMED:" + where)


def _typed_ledger_state(state):
    """The ledger state an extension continues from: the claim log, as an export carries it."""
    _need(type(state) is dict and set(state) == set(LEDGER_STATE_FIELDS),
          "ISSUE_47_EXTENSION_LEDGER_STATE_FIELDS_NOT_EXACT")
    _need(type(state["export_id"]) is str and state["export_id"].startswith("sha256:"),
          "ISSUE_47_EXTENSION_LEDGER_STATE_EXPORT_ID_MALFORMED")
    claims = state["claims"]
    _need(type(claims) is dict and set(claims) == {"sha256", "size"}
          and _HEX64.match(str(claims["sha256"])) and type(claims["size"]) is int
          and claims["size"] > 0, "ISSUE_47_EXTENSION_LEDGER_STATE_CLAIMS_MALFORMED")
    _need(type(state["claim_count"]) is int and state["claim_count"] > 0,
          "ISSUE_47_EXTENSION_LEDGER_STATE_CLAIM_COUNT_MALFORMED")
    # The resume chain as the export carried it: the charge for lost segments
    # that the stated spending includes.
    resumes = state["resumes"]
    _need(type(resumes) is dict and set(resumes) == {"sha256", "size"}
          and _HEX64.match(str(resumes["sha256"])) and type(resumes["size"]) is int
          and resumes["size"] >= 0, "ISSUE_47_EXTENSION_LEDGER_STATE_RESUMES_MALFORMED")
    _typed_limits(state["cumulative"], "ledger_state.cumulative")


def _typed_reclaim(reclaim, scope):
    """Which kinds of already-requested rows may be requested once more, and of which classes."""
    _need(type(reclaim) is list, "ISSUE_47_EXTENSION_RECLAIM_MALFORMED")
    kinds = []
    for entry in reclaim:
        _need(type(entry) is dict and set(entry) == {"acquisition_kind", "dependency_classes"},
              "ISSUE_47_EXTENSION_RECLAIM_FIELDS_NOT_EXACT")
        _need(entry["acquisition_kind"] in RECLAIM_KINDS,
              "ISSUE_47_EXTENSION_RECLAIM_KIND_NOT_ALLOWED:" + str(entry["acquisition_kind"]))
        kinds.append(entry["acquisition_kind"])
        classes = entry["dependency_classes"]
        _need(type(classes) is list and classes
              and all(type(value) is str and value for value in classes)
              and set(classes) <= set(scope["dependency_classes"]),
              "ISSUE_47_EXTENSION_RECLAIM_CLASS_OUTSIDE_THE_GRANTS:"
              + str(entry["acquisition_kind"]))
    _need(len(kinds) == len(set(kinds)), "ISSUE_47_EXTENSION_RECLAIM_KIND_REPEATS")


def _typed(policy, *, allowance):
    """Every field's shape, and every tie to the first approval, before anything trusts it."""
    _need(policy["requirement_id"] == REQUIREMENT_ID,
          "ISSUE_47_EXTENSION_IS_FOR_ANOTHER_REQUIREMENT:" + str(policy["requirement_id"]))
    _need(policy["repository"] == TRUSTED_REPOSITORY
          and policy["approver_login"] == TRUSTED_APPROVER,
          "ISSUE_47_EXTENSION_NAMES_ANOTHER_REPOSITORY_OR_APPROVER")
    _need(policy["extension_ordinal"] == EXTENSION_ORDINAL,
          "ISSUE_47_EXTENSION_ORDINAL_UNEXPECTED:" + str(policy["extension_ordinal"]))
    _need(_comment_url(repository=policy["repository"]).match(str(policy["delegation_url"])),
          "ISSUE_47_EXTENSION_URL_IS_NOT_THIS_ISSUE_S_COMMENT:"
          + str(policy["delegation_url"])[:70])
    _need(policy["delegation_url"] != allowance["delegation_url"],
          "ISSUE_47_EXTENSION_IS_THE_FIRST_APPROVAL_S_COMMENT")
    _need(_HEX64.match(str(policy["delegation_body_sha256"]) or ""),
          "ISSUE_47_EXTENSION_DIGEST_IS_NOT_A_SHA256")
    _need(type(policy["delegation_record_path"]) is str and policy["delegation_record_path"],
          "ISSUE_47_EXTENSION_RECORD_PATH_MALFORMED")
    extends = policy["extends"]
    _need(type(extends) is dict
          and set(extends) == {"delegation_url", "delegation_body_sha256", "ledger_state"},
          "ISSUE_47_EXTENSION_EXTENDS_FIELDS_NOT_EXACT")
    _need(extends["delegation_url"] == allowance["delegation_url"]
          and extends["delegation_body_sha256"] == allowance["delegation_body_sha256"],
          "ISSUE_47_EXTENSION_EXTENDS_ANOTHER_APPROVAL")
    _typed_ledger_state(extends["ledger_state"])
    # The same ledger: an extension continues the root the first approval
    # granted, so the count it raises is the one already kept there.
    _need(policy["budget_root"] == allowance["budget_root"],
          "ISSUE_47_EXTENSION_NAMES_ANOTHER_LEDGER_ROOT")
    _typed_limits(policy["maximum_additional_provider_paid_sec_calls"], "limits")
    scope = policy["scope"]
    _need(type(scope) is dict and not [field for field in SCOPE_FIELDS if field not in scope],
          "ISSUE_47_EXTENSION_SCOPE_INCOMPLETE")
    for field in ("purposes", "company_ids", "dependency_classes"):
        _need(type(scope[field]) is list and scope[field]
              and all(type(value) is str and value for value in scope[field]),
              "ISSUE_47_EXTENSION_SCOPE_LIST_MALFORMED:" + field)
    # The ledger's binding names the purposes it may count; an extension raises
    # the count, it does not add a purpose the binding never saw.
    _need(set(scope["purposes"]) <= set(allowance["scope"]["purposes"]),
          "ISSUE_47_EXTENSION_ADDS_A_PURPOSE")
    _typed_grants(scope)
    _typed_reclaim(policy["reclaim"], scope)


def _approved_body(*, repo_root, policy, reader):
    """The approved text, re-hashed, fetched back from GitHub, and required to say the same thing."""
    path = Path(repo_root) / policy["delegation_record_path"]
    _need(path.is_file() and not path.is_symlink(),
          "ISSUE_47_EXTENSION_RECORD_MISSING:" + policy["delegation_record_path"])
    comment = strict_json_file(path=path)
    _need(type(comment.get("body")) is str and comment["body"],
          "ISSUE_47_EXTENSION_RECORD_HAS_NO_BODY")
    _need(sha256_bytes(content=posted_text(comment["body"]).encode("utf-8"))
          == policy["delegation_body_sha256"],
          "ISSUE_47_EXTENSION_BODY_DOES_NOT_MATCH_ITS_DIGEST")
    _provenance(comment=comment, policy=policy, where="saved_extension_record")
    _posted_by_the_approver_directly(comment, where="saved_extension_record")
    if reader is not None:
        match = _comment_url(repository=policy["repository"]).match(policy["delegation_url"])
        fetched = reader("repos/" + policy["repository"] + "/issues/comments/" + match[1])
        _need(type(fetched) is dict, "ISSUE_47_EXTENSION_FETCH_DID_NOT_RETURN_A_COMMENT")
        _provenance(comment=fetched, policy=policy, where="fetched_extension")
        _posted_by_the_approver_directly(fetched, where="fetched_extension")
        _need(fetched.get("body") == comment["body"],
              "ISSUE_47_SAVED_EXTENSION_DIFFERS_FROM_THE_ONE_ON_GITHUB")
    try:
        approved = strict_json_loads(text=posted_text(comment["body"]))
    except CanonicalError:
        raise HistoricalExtensionError("ISSUE_47_EXTENSION_BODY_IS_NOT_A_RECORD")
    _need(type(approved) is dict and approved.get("record_type") == EXTENSION_TYPE,
          "ISSUE_47_EXTENSION_RECORD_TYPE_CHANGED:" + str(
              approved.get("record_type") if type(approved) is dict else type(approved)))
    _need(approved.get("requirement_id") == REQUIREMENT_ID,
          "ISSUE_47_EXTENSION_BODY_IS_FOR_ANOTHER_REQUIREMENT")
    for field in ("extension_ordinal", "extends", "budget_root",
                  "maximum_additional_provider_paid_sec_calls", "scope", "reclaim"):
        _need(approved.get(field) == policy[field],
              "ISSUE_47_EXTENSION_WIDENS_THE_APPROVED_GRANT:" + field)
    _need(approved.get("production_authorized") is False,
          "ISSUE_47_EXTENSION_MUST_NOT_AUTHORIZE_PRODUCTION")
    return {**approved, "provenance_verified_against_github": reader is not None}


def acquisition_extension(*, repo_root: Path, allowance, delegation_reader=None):
    """The owner's extension of the first approval, verified; None while none is registered.

    The first approval is verified by ``acquisition_allowance`` before this is
    asked, and ``allowance`` is what that returned: an extension is read only
    as a continuation of an approval that holds on its own.
    """
    path = Path(repo_root) / EXTENSION_POLICY_PATH
    if not path.exists() and not path.is_symlink():
        return None
    _need(path.is_file() and not path.is_symlink(), "ISSUE_47_EXTENSION_POLICY_UNSAFE")
    try:
        policy = strict_json_loads(text=path.read_text(encoding="utf-8"))
    except CanonicalError:
        raise HistoricalExtensionError("ISSUE_47_EXTENSION_POLICY_IS_NOT_STRICT_JSON")
    _need(type(policy) is dict and set(policy) == set(REQUIRED_EXTENSION_FIELDS),
          "ISSUE_47_EXTENSION_POLICY_FIELDS_NOT_EXACT")
    _typed(policy, allowance=allowance)
    policy["approved_extension"] = _approved_body(repo_root=repo_root, policy=policy,
                                                  reader=delegation_reader)
    return policy


def extended_allowance(*, allowance, extension):
    """The allowance a session holds requests to once an extension is registered.

    The first approval's delegation, root and limits stay - they are what the
    ledger's binding, the start marker and the export name - and the scope is
    the extension's, so every request made from here on is held to the grants
    the owner approved for it. The extension itself rides along for the ledger
    (its limits and the state it extends) and for the re-request rule.
    """
    if extension is None:
        return allowance
    return {**allowance, "scope": extension["scope"], "first_approval_scope": allowance["scope"],
            "extension": {
                "extension_ordinal": extension["extension_ordinal"],
                "delegation_url": extension["delegation_url"],
                "delegation_body_sha256": extension["delegation_body_sha256"],
                # Whether the comment was read back from GitHub on this path.
                # The live ledger raises its cap only for one that was.
                "provenance_verified_against_github":
                    extension["approved_extension"]["provenance_verified_against_github"],
                "maximum_additional_provider_paid_sec_calls":
                    list(extension["maximum_additional_provider_paid_sec_calls"]),
                "ledger_state": extension["extends"]["ledger_state"],
                "reclaim": extension["reclaim"]}}


def reclaim_ordinal(*, allowance, dependency, claimed_ordinals):
    """The extension ordinal under which an already-requested URL may be requested again, or None.

    ``claimed_ordinals`` are the slots that already requested this URL. It may
    be requested again only while every one of them came before the state the
    extension continues from - so at most once per extension - and only when
    the planner says why: a refresh of a saved copy that disagrees with its
    index, or the replacement of one whose last request failed, of a class the
    owner named for that reason.
    """
    extension = allowance.get("extension")
    if extension is None or not claimed_ordinals:
        return None
    if max(claimed_ordinals) > extension["ledger_state"]["claim_count"]:
        return None
    # The planner marks any saved copy it cannot read as a replacement - a
    # conflicting attempt selection or a changed hash among them. The owner's
    # exception is narrower: a copy whose last request failed. The planner's
    # reason says which, and nothing else is requested again as a replacement.
    if (dependency.get("acquisition_kind") == "REPLACEMENT_ACQUISITION"
            and not str(dependency.get("reason") or "").startswith(FAILED_REQUEST_REASON)):
        return None
    for entry in extension["reclaim"]:
        if (dependency.get("acquisition_kind") == entry["acquisition_kind"]
                and dependency["dependency_class"] in entry["dependency_classes"]):
            return extension["extension_ordinal"]
    return None


def require_extension_on_branch(*, repo_root, branch_files):
    """The extension files in the checkout are the ones on the branch tip, or refused.

    The branch is where a lost container's successor reads what it was spent
    under: an extension registered here but never pushed would let requests be
    made that a resume, reading the branch, cannot charge for. So a request
    under an extension is made only once the branch carries it, and a branch
    carrying one the checkout lacks is refused as well. ``branch_files`` maps
    each of ``EXTENSION_FILES`` to its bytes at the tip, or None.
    """
    _need(type(branch_files) is dict and set(branch_files) == set(EXTENSION_FILES),
          "ISSUE_47_BRANCH_TIP_DOES_NOT_SAY_WHICH_EXTENSION")
    for relative in EXTENSION_FILES:
        path = Path(repo_root) / relative
        held = path.read_bytes() if path.is_file() and not path.is_symlink() else None
        _need(held == branch_files[relative],
              "ISSUE_47_EXTENSION_NOT_ON_THE_BRANCH:" + relative
              + (": commit and push it before any request under it" if held is not None
                 else ": the branch carries one this checkout does not"))


_RECORD_FIELDS = ("id", "html_url", "issue_url", "author_association", "created_at",
                  "updated_at", "body")


def register_extension(*, repo_root: Path, comment_url, reader, allowance):
    """Write the extension from the owner's comment that is already on GitHub.

    The comment's body must be the approved bytes (pinned in
    ``EXTENSION_BODY_SHA256`` and equal to the committed body file), posted by
    the trusted approver directly, on this issue. The record and the policy are
    written from what was read, then put through ``acquisition_extension`` with
    the same reader, so the file that grants is checked by the gate that will
    read it. Registering the same extension again is a no-op; one that already
    says something else is refused rather than overwritten.
    """
    repo_root = Path(repo_root)
    _need(EXTENSION_BODY_SHA256 is not None, "ISSUE_47_EXTENSION_BODY_NOT_PINNED")
    match = _comment_url(repository=TRUSTED_REPOSITORY).match(str(comment_url))
    _need(match is not None, "ISSUE_47_EXTENSION_URL_IS_NOT_THIS_ISSUE_S_COMMENT:"
          + str(comment_url)[:120])
    approved = (repo_root / EXTENSION_BODY_PATH).read_bytes()
    _need(sha256_bytes(content=approved) == EXTENSION_BODY_SHA256,
          "ISSUE_47_EXTENSION_BODY_FILE_CHANGED:" + EXTENSION_BODY_PATH)
    fetched = reader("repos/" + TRUSTED_REPOSITORY + "/issues/comments/" + match[1])
    _need(type(fetched) is dict and type(fetched.get("body")) is str,
          "ISSUE_47_EXTENSION_FETCH_DID_NOT_RETURN_A_COMMENT")
    _need(posted_text(fetched["body"]).encode("utf-8") == approved,
          "ISSUE_47_POSTED_EXTENSION_IS_NOT_THE_APPROVED_TEXT:sha256="
          + sha256_bytes(content=posted_text(fetched["body"]).encode("utf-8")))
    body = strict_json_loads(text=approved.decode("utf-8"))
    policy = {"requirement_id": body["requirement_id"], "repository": TRUSTED_REPOSITORY,
              "approver_login": TRUSTED_APPROVER,
              "extension_ordinal": body["extension_ordinal"],
              "delegation_url": fetched.get("html_url"),
              "delegation_body_sha256": EXTENSION_BODY_SHA256,
              "delegation_record_path": EXTENSION_RECORD_PATH, "extends": body["extends"],
              "budget_root": body["budget_root"],
              "maximum_additional_provider_paid_sec_calls":
                  body["maximum_additional_provider_paid_sec_calls"],
              "scope": body["scope"], "reclaim": body["reclaim"]}
    _provenance(comment=fetched, policy=policy, where="fetched_extension")
    _posted_by_the_approver_directly(fetched, where="fetched_extension")
    record = {field: fetched.get(field) for field in _RECORD_FIELDS}
    record["user"] = {key: fetched.get("user", {}).get(key) for key in ("login", "id", "type")}
    record["performed_via_github_app"] = fetched["performed_via_github_app"]
    outputs = {EXTENSION_POLICY_PATH: policy, EXTENSION_RECORD_PATH: record}
    for relative, value in outputs.items():
        data = (json.dumps(value, ensure_ascii=False, indent=1, sort_keys=True)
                + "\n").encode("utf-8")
        path = repo_root / relative
        if path.exists():
            _need(path.read_bytes() == data,
                  "ISSUE_47_EXTENSION_ALREADY_REGISTERED_DIFFERENTLY:" + relative)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as handle:
            handle.write(data)
    extension = acquisition_extension(repo_root=repo_root, allowance=allowance,
                                      delegation_reader=reader)
    return {"status": "EXTENSION_REGISTERED", "delegation_url": extension["delegation_url"],
            "delegation_body_sha256": extension["delegation_body_sha256"],
            "extends": extension["extends"],
            "additional_limits": extension["maximum_additional_provider_paid_sec_calls"],
            "written": sorted(outputs), "calls": [0, 0, 0]}
