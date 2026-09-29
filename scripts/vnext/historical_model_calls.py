"""Issue #47's model calls, everything except the socket: allowance, request, plan, ledger.

The historical D04 route (``historical_semantic_results``) consumes an
assessment registered for its pinned source. A registration made by real model
calls would rest on what is here - #47's own allowance, each request rebuilt
from the pinned filing, a WB-3 plan, and a cumulative ledger - and on the one
module that is not here: ``historical_model_egress``, the transport and the
single execution entry. That module is new code inside the registration patch
submitted for independent security review
(docs/evidence/issue47_history/model-egress/), because opening a provider socket
for #47 needs three frozen security-boundary files to change:

* ``invocation_control`` registers requirement generations by id and refuses
  any other. The patch adds an ``issue_47_v1`` branch whose fields come from
  ``invocation_authority_fields`` below, and lets its plans keep an unavailable
  price as null, as ``issue_28_v14``'s do.
* ``ai_adapter._scoped_transport_payload`` hands bytes to the socket only for
  request types it names. The patch names ``HistoricalSemanticRequest``, whose
  ``transport_payload`` rebuilds the request from the saved filing first.
* ``tools/check_provider_egress.py`` fixes the exact set of transport callers
  and egress-capability references. The patch adds the egress module's one
  ``_Transport.send``.

Nothing in this module calls the transport factory, touches the egress
capability or names a provider host, so the repository's egress gate passes
with it present and the patch absent - the state today. It is not a rule file:
no Run executes it. #28's workspace, allowance, ledger and assessments are not
read, borrowed or reused; every check is against #47's own records, and the
model ledger may not overlap #28's, the checkout or #47's SEC ledger.

What one call is bound to, in the order it is checked:

1. **#47's allowance** (``config/issue47_historical_model_calls_v1.json``,
   which does not exist): the owner's comment on issue 47, re-hashed and - on
   the live path - fetched from GitHub, restating the limits, ledger root,
   scope, transport and retry policy. Only wired metrics may be named.
2. **A request its pinned source partitions into**, byte for byte, rebuilt
   from the saved filing each time it is validated, inside one grant.
3. **A WB-3 plan** over the exact provider body, under the controller's own
   authority object, whose file map binds every rule file and this module.
4. **A counted slot**: one provider and one paid call claimed before the
   socket, never removed; a request is claimed at most once (no redraw); a
   slot without a terminal, or whose terminal records HTTP 402, an unknown
   outcome, unknown usage, a source that no longer rebuilds or a context
   reference mismatch, stops the channel. Resuming is an owner decision this
   module does not implement.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import fcntl
import json
import os
import re
import sys
import threading

from .canonical import (canonical_json_bytes, content_hash, sha256_bytes, sha256_file,
                        strict_json_file, strict_json_loads)
from .normal_source_authority import ROOT
from .sources import resolve_repository_file

REQUIREMENT_ID = "issue_47_v1"
# The metrics a #47 model allowance may name: D04's semantic review, E01's
# content confirmation and D02's Item 8 review. Each has its own request
# contract; all go through this module's allowance, request type and ledger,
# and the patch's one socket.
MODEL_METRICS = ("D04", "E01", "D02")
REQUEST_TYPES = {"D04": "D04_NATIVE_INTERPRETATION_REQUEST",
                 "E01": "E01_CONTENT_CONFIRMATION_REQUEST",
                 "D02": "D02_ITEM_8_LEGAL_REVIEW_REQUEST"}
# E01 and D02 make one request per position, built by the route from the saved
# filings; D04's pinned source partitions into several.
SINGLE_REQUEST_SOURCE_TYPES = {"E01": "ISSUE_47_E01_CONFIRMATION_REQUEST_SOURCE",
                               "D02": "ISSUE_47_D02_REVIEW_REQUEST_SOURCE"}


def ledger_digest(request, policy):
    """What an approval names and the no-redraw rule is keyed on: the exact bytes a call sends.

    The provider body - model, messages, decoding settings - hashed as it goes
    out, the same for every contract. An independent review found D04's
    previous digest, Issue #28's request digest over the request's semantic
    content, left out fields that are sent: the company, the document context
    beyond the filing, each unit's ids, ordinal and payload hash. An approval
    naming it did not pin what would go out. Now a request whose bytes differ
    in any way is a different digest, which an approval that never saw it does
    not name.
    """
    from .continuous_semantic_calls import request_body
    return "sha256:" + sha256_bytes(content=request_body(request, policy))


def _single_request_source(*, data_root, company_id, metric_id, period_selection):
    """E01's or D02's one request and the source proofs it was built from, as one source."""
    if metric_id == "E01":
        from .historical_zero_ai_results import e01_confirmation_request as build
    else:
        from .historical_text_input import d02_review_request as build
    request, proofs = build(repo_root=Path(data_root), company_id=company_id,
                            period_selection=period_selection)
    return {"record_type": SINGLE_REQUEST_SOURCE_TYPES[metric_id], "company_id": company_id,
            "metric_id": metric_id, "request": request, "source_proofs": proofs}


def _request_report_end(request):
    return request["window"]["period_end"] if "window" in request else request["period_end"]


ALLOWANCE_PATH = "config/issue47_historical_model_calls_v1.json"
DELEGATION_TYPE = "ISSUE_47_HISTORICAL_MODEL_DELEGATION"
PURPOSE = "ISSUE47_HISTORICAL_SEMANTIC_ASSESSMENT"
REQUIRED_FIELDS = ("requirement_id", "repository", "approver_login", "delegation_url",
                   "delegation_body_sha256", "delegation_record_path", "budget_root",
                   "maximum_additional_provider_paid_sec_calls", "scope", "transport",
                   "retry_policy", "model_wiring_receipt_path", "model_wiring_receipt_id")
# The approval names the verified code as well as the grant. An independent
# review found an approval bound no code identity: a receipt re-sealed after a
# code change, at the same path, would have been accepted under the old
# approval. With the receipt's id restated, a change to any file the receipt
# binds needs a new verification and a new approval.
RESTATED_BY_THE_COMMENT = ("maximum_additional_provider_paid_sec_calls", "budget_root",
                           "scope", "transport", "retry_policy", "model_wiring_receipt_id")
SCOPE_FIELDS = ("purposes", "metric_ids", "company_ids", "earliest_report_end",
                "latest_report_end", "grants")
GRANT_FIELDS = ("grant", "metric_ids", "company_ids", "earliest_report_end",
                "latest_report_end", "request_digests")
# A ledger digest as the ledger records it: the SHA-256 of the provider body.
_LEDGER_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
# The provider identity #47 may be granted. The endpoint host is compared with
# the adapter's own constant, not written here: provider hosts live in
# ai_adapter.py and nowhere else, which the egress gate enforces.
FIXED_TRANSPORT = {"provider": "deepseek", "model": "deepseek-flash", "api": "chat_completions",
                   "retry_count": 0, "filing_egress_policy": "PUBLIC_SEC_FILING_CONTENT_ONLY"}
FIXED_RETRY_POLICY = {"kind": "TRANSPORT_RETRY_POLICY", "automatic_retry_count": 0,
                      "unknown_remote_outcome_retry_allowed": False,
                      "http_402_automatic_retry_count": 0, "http_402_stops_execution": True,
                      "http_402_stops_batch": True, "actual_usage_required": True,
                      "context_ceiling_tokens": 200000}
# The ledger binding's formula lives with the checks a LIVE registration's
# consumer makes, so the ledger a call is counted in and the ledger a consumer
# accepts are described by one function.
from .historical_counted_calls import (GRANTED_LEDGER_PATH, LEDGER_TYPE,  # noqa: E402
                                       granted_ledger_record, ledger_binding)
# Where a registered approval lives, and the proposal the owner posts. The
# proposal's bytes are what the posted comment must be; nothing here pins its
# digest, because the proposal names the sealed verification receipt, which
# binds this module - a digest pinned here would have to be written before the
# receipt it describes exists.
APPROVAL_BODY_PATH = "docs/evidence/issue47_history/model-egress/approval-comment-body.json"
APPROVAL_RECORD_PATH = "docs/evidence/issue47_history/model-egress/approval-comment.json"
WIRING_RECEIPT_PATH = "docs/evidence/issue47_history/model-egress/offline-verification.json"
# issue_28_v14's stops, each a terminal a later call must not be made after
# because the count or the source can no longer be trusted - and one more: a
# call whose observed context exceeded the ceiling it was admitted under means
# the estimate that admitted it was wrong, which an independent review found
# was answered as a plain failure rather than a stop.
STOPS = frozenset({"HTTP_402", "UNKNOWN_REMOTE_OUTCOME", "SOURCE_AUTHENTICITY_FAILED",
                   "USAGE_UNKNOWN", "CONTEXT_REFERENCE_MISMATCH", "CONTEXT_LIMIT",
                   # The transport's own account of the call disagrees with the
                   # bytes it was given: what was sent cannot be trusted.
                   "TRANSPORT_OBSERVATION_CHANGED"})
# Files a call executes that the Requirement's authority does not already list.
# The files a live call runs through that the controller's authority does not
# already bind. The allowance's approval checks - the comment URL, its
# provenance and the gh reader that fetches it - live in the SEC acquisition
# module and are imported from there, and the owner's calls are driven by the
# patch's runner, so a change to either must refuse a model call until the
# path is verified again, like a change to the two model modules.
CALL_PATH_FILES = ("scripts/vnext/historical_model_calls.py",
                   "scripts/vnext/historical_model_egress.py",
                   "scripts/vnext/historical_source_acquisition.py",
                   # The start that outlives the container the ledger is in:
                   # the live path refuses without it, so it is on the path.
                   "scripts/vnext/historical_ledger_start.py",
                   "tools/vnext_historical_model.py",
                   # The generation's snapshot, which records every rule file's
                   # bytes - E01's answer check and the D04 checker it inherits
                   # among them. Without it a receipt held while those changed:
                   # a weaker answer check re-minted into the snapshot would run
                   # under an approval that named the old one's receipt.
                   "requirements/issue_47_v1/baseline_manifest.json")
_FACTORY = object()


class HistoricalModelCallError(ValueError):
    """A model call this Issue may not make; the reason names which check refused it."""


def _need(condition, reason):
    if not condition:
        raise HistoricalModelCallError(reason)


def _sealed(body, field):
    return {**body, field: content_hash(value=body)}


def _identity_holds(value, field):
    return (type(value) is dict and value.get(field)
            == content_hash(value={k: v for k, v in value.items() if k != field}))


def _read(root, relative):
    return strict_json_file(path=resolve_repository_file(repo_root=root, repo_relative_path=relative))


# ---------------------------------------------------------------- the allowance


def _typed_ledger_root(budget_root, *, repo_root):
    """#47's SEC rules for a ledger root, and apart from #47's SEC ledger too.

    Two ledgers under one root would let one channel's count be read as the
    other's; nested roots would let one reset the other.
    """
    from .historical_source_acquisition import POLICY_PATH as SEC_POLICY, _typed_budget_root
    _typed_budget_root(budget_root)
    sec = Path(repo_root) / SEC_POLICY
    if sec.is_file():
        # Compared as the directories they are - real paths, casefolded, both
        # ways - as the SEC root is compared with #28's, so a symlink, a
        # doubled slash or a case variant of the SEC root is refused too.
        def real(path):
            return PurePosixPath(os.path.realpath(str(path)).casefold())
        other = strict_json_file(path=sec)["budget_root"]
        for mine, theirs in ((real(budget_root), real(other)),
                             (PurePosixPath(budget_root.casefold()), PurePosixPath(other.casefold()))):
            _need(mine != theirs and theirs not in mine.parents and mine not in theirs.parents,
                  "ISSUE_47_MODEL_LEDGER_OVERLAPS_THE_SEC_LEDGER:" + budget_root[:80])


def _typed(policy, *, repo_root):
    """Every field's shape, before anything downstream trusts its meaning."""
    from .ai_adapter import _DEEPSEEK_ENDPOINT_HOST, TransportPolicy
    SUPPORTED_METRICS = MODEL_METRICS
    from .historical_source_acquisition import (_DATE, _HEX64, TRUSTED_APPROVER,
                                                TRUSTED_REPOSITORY, _comment_url)
    _need(policy["requirement_id"] == REQUIREMENT_ID,
          "ISSUE_47_MODEL_ALLOWANCE_IS_FOR_ANOTHER_REQUIREMENT:" + str(policy["requirement_id"]))
    _need(policy["repository"] == TRUSTED_REPOSITORY and policy["approver_login"] == TRUSTED_APPROVER,
          "ISSUE_47_MODEL_ALLOWANCE_NAMES_ANOTHER_REPOSITORY_OR_APPROVER")
    _need(bool(_HEX64.match(str(policy["delegation_body_sha256"]))),
          "ISSUE_47_MODEL_ALLOWANCE_DIGEST_IS_NOT_A_SHA256")
    _need(bool(_comment_url(repository=policy["repository"]).match(str(policy["delegation_url"]))),
          "ISSUE_47_MODEL_ALLOWANCE_URL_IS_NOT_THIS_ISSUE_S_COMMENT")
    for field in ("budget_root", "delegation_record_path", "model_wiring_receipt_path"):
        _need(type(policy[field]) is str and policy[field],
              "ISSUE_47_MODEL_ALLOWANCE_FIELD_MALFORMED:" + field)
    _need(type(policy["model_wiring_receipt_id"]) is str
          and policy["model_wiring_receipt_id"].startswith("sha256:")
          and bool(_HEX64.match(policy["model_wiring_receipt_id"][len("sha256:"):])),
          "ISSUE_47_MODEL_ALLOWANCE_FIELD_MALFORMED:model_wiring_receipt_id")
    limits = policy["maximum_additional_provider_paid_sec_calls"]
    # One call is one provider and one paid call; a model allowance grants no
    # SEC request - those have their own allowance, ledger and root.
    _need(type(limits) is list and len(limits) == 3
          and all(type(value) is int and value >= 0 for value in limits)
          and limits[0] == limits[1] and limits[2] == 0,
          "ISSUE_47_MODEL_ALLOWANCE_LIMITS_MALFORMED:" + str(limits)[:40])
    _typed_ledger_root(policy["budget_root"], repo_root=repo_root)
    transport = policy["transport"]
    try:
        compiled = TransportPolicy.from_mapping(value=dict(transport))
    except (TypeError, ValueError, RuntimeError) as error:
        raise HistoricalModelCallError("ISSUE_47_MODEL_TRANSPORT_MALFORMED:" + str(error)[:80])
    _need(all(transport.get(key) == value for key, value in FIXED_TRANSPORT.items())
          and compiled.endpoint_host == _DEEPSEEK_ENDPOINT_HOST,
          "ISSUE_47_MODEL_TRANSPORT_IS_NOT_THE_FIXED_ONE")
    _need(policy["retry_policy"] == FIXED_RETRY_POLICY, "ISSUE_47_MODEL_RETRY_POLICY_CHANGED")
    scope = policy["scope"]
    _need(type(scope) is dict and set(scope) == set(SCOPE_FIELDS),
          "ISSUE_47_MODEL_SCOPE_FIELDS_NOT_EXACT")
    for field in ("purposes", "metric_ids", "company_ids"):
        _need(type(scope[field]) is list and scope[field]
              and all(type(value) is str and value for value in scope[field]),
              "ISSUE_47_MODEL_SCOPE_LIST_MALFORMED:" + field)
    _need(scope["purposes"] == [PURPOSE], "ISSUE_47_MODEL_SCOPE_PURPOSE_IS_NOT_THE_ONE")
    _need(set(scope["metric_ids"]) <= set(SUPPORTED_METRICS),
          "ISSUE_47_MODEL_SCOPE_NAMES_AN_UNWIRED_METRIC:"
          + ",".join(sorted(set(scope["metric_ids"]) - set(SUPPORTED_METRICS))))
    for field in ("earliest_report_end", "latest_report_end"):
        _need(bool(_DATE.match(str(scope[field]))), "ISSUE_47_MODEL_SCOPE_DATE_MALFORMED")
    grants = scope["grants"]
    _need(type(grants) is list and grants, "ISSUE_47_MODEL_SCOPE_HAS_NO_GRANTS")
    names = []
    for grant in grants:
        _need(type(grant) is dict and set(grant) == set(GRANT_FIELDS)
              and type(grant["grant"]) is str and grant["grant"],
              "ISSUE_47_MODEL_GRANT_FIELDS_NOT_EXACT")
        names.append(grant["grant"])
        _need(all(type(grant[f]) is list and grant[f] and set(grant[f]) <= set(scope[f])
                  for f in ("metric_ids", "company_ids"))
              and all(_DATE.match(str(grant[f])) for f in ("earliest_report_end",
                                                           "latest_report_end"))
              and scope["earliest_report_end"] <= grant["earliest_report_end"]
              <= grant["latest_report_end"] <= scope["latest_report_end"],
              "ISSUE_47_MODEL_GRANT_OUTSIDE_THE_ENVELOPE:" + grant["grant"])
        # The exact requests the grant allows, by the digest the ledger claims
        # them under. A grant by position alone let any request built for that
        # position through - a changed prompt, contract or source included -
        # under an approval that had never seen it.
        digests = grant["request_digests"]
        _need(type(digests) is list and digests
              and all(type(value) is str and _LEDGER_DIGEST.match(value) for value in digests)
              and len(digests) == len(set(digests)),
              "ISSUE_47_MODEL_GRANT_REQUEST_DIGESTS_MALFORMED:" + grant["grant"])
    _need(len(names) == len(set(names)), "ISSUE_47_MODEL_GRANT_NAMES_REPEAT")
    every = [value for grant in grants for value in grant["request_digests"]]
    _need(len(every) == len(set(every)), "ISSUE_47_MODEL_GRANT_REQUEST_DIGEST_REPEATS")
    for field in ("metric_ids", "company_ids"):
        _need(set(scope[field]) == {value for grant in grants for value in grant[field]},
              "ISSUE_47_MODEL_ENVELOPE_WIDER_THAN_ITS_GRANTS:" + field)
    _need(scope["earliest_report_end"] == min(g["earliest_report_end"] for g in grants)
          and scope["latest_report_end"] == max(g["latest_report_end"] for g in grants),
          "ISSUE_47_MODEL_ENVELOPE_WIDER_THAN_ITS_GRANTS:window")


def model_allowance(*, repo_root: Path = ROOT, delegation_reader=None):
    """#47's own model-call allowance, verified rather than merely present.

    The SEC allowance's three layers: every field typed; the comment the digest
    names read and re-hashed, carrying the provenance of an approval on this
    issue by the declared approver; and the comment required to restate what
    the policy grants, so the policy cannot widen it. With a reader - the live
    path always passes one - the comment is fetched from GitHub and the saved
    record must match it byte for byte.
    """
    from .historical_source_acquisition import _comment_url, _provenance, posted_text
    path = Path(repo_root) / ALLOWANCE_PATH
    _need(path.is_file() and not path.is_symlink(),
          "ISSUE_47_MODEL_ALLOWANCE_NOT_GRANTED:" + ALLOWANCE_PATH + ":needs "
          + ",".join(REQUIRED_FIELDS))
    # Strict JSON: a duplicate key is refused, not resolved last-wins. An
    # independent review had an approval showing [4,4,0] followed by a
    # duplicate [400,400,0] accepted as the larger grant.
    try:
        policy = strict_json_loads(text=path.read_text(encoding="utf-8"))
    except ValueError as error:
        raise HistoricalModelCallError("ISSUE_47_MODEL_ALLOWANCE_NOT_STRICT_JSON:" + str(error)[:80])
    _need(type(policy) is dict, "ISSUE_47_MODEL_ALLOWANCE_MALFORMED")
    missing = [field for field in REQUIRED_FIELDS if field not in policy]
    _need(not missing, "ISSUE_47_MODEL_ALLOWANCE_INCOMPLETE:" + ",".join(missing))
    _typed(policy, repo_root=repo_root)
    record_path = Path(repo_root) / policy["delegation_record_path"]
    _need(record_path.is_file() and not record_path.is_symlink(),
          "ISSUE_47_MODEL_DELEGATION_RECORD_MISSING:" + policy["delegation_record_path"])
    comment = strict_json_file(path=record_path)
    # The approved text, with only the line breaks a browser may add undone
    # (historical_source_acquisition.posted_text): the owner may paste the
    # approval into github.com.
    _need(type(comment.get("body")) is str and comment["body"]
          and sha256_bytes(content=posted_text(comment["body"]).encode("utf-8"))
          == policy["delegation_body_sha256"], "ISSUE_47_MODEL_DELEGATION_BODY_DOES_NOT_MATCH")
    _provenance(comment=comment, policy=policy, where="saved_record")
    _posted_by_the_approver_directly(comment, where="saved_record")
    if delegation_reader is not None:
        number = _comment_url(repository=policy["repository"]).match(policy["delegation_url"])[1]
        fetched = delegation_reader("repos/" + policy["repository"] + "/issues/comments/" + number)
        _need(type(fetched) is dict, "ISSUE_47_MODEL_DELEGATION_FETCH_DID_NOT_RETURN_A_COMMENT")
        _provenance(comment=fetched, policy=policy, where="fetched")
        _posted_by_the_approver_directly(fetched, where="fetched")
        _need(fetched.get("body") == comment["body"],
              "ISSUE_47_MODEL_SAVED_DELEGATION_DIFFERS_FROM_GITHUB")
    try:
        approved = strict_json_loads(text=posted_text(comment["body"]))
    except ValueError:
        raise HistoricalModelCallError("ISSUE_47_MODEL_DELEGATION_BODY_IS_NOT_A_RECORD")
    _need(type(approved) is dict and approved.get("record_type") == DELEGATION_TYPE
          and approved.get("requirement_id") == REQUIREMENT_ID,
          "ISSUE_47_MODEL_DELEGATION_RECORD_TYPE_OR_REQUIREMENT_CHANGED")
    for field in RESTATED_BY_THE_COMMENT:
        _need(approved.get(field) == policy[field],
              "ISSUE_47_MODEL_ALLOWANCE_WIDENS_THE_APPROVED_GRANT:" + field)
    _need(approved.get("production_authorized") is False,
          "ISSUE_47_MODEL_DELEGATION_MUST_NOT_AUTHORIZE_PRODUCTION")
    return {**policy, "provenance_verified_against_github": delegation_reader is not None}


def _posted_by_the_approver_directly(comment, *, where):
    """A model approval posted by the approver's own hand, not by an app acting as them.

    An independent review found an approval proved only that the comment was
    posted as the approver's account. A GitHub App acting for the approver -
    the channel an agent working in this repository posts through - writes
    comments under that account too; GitHub marks them with the app. A model
    approval is the one decision here that spends money on requests an agent
    prepared, so it must come without that mark. The saved record must carry
    the field, as fetched, so an offline read can hold it too.
    """
    _need("performed_via_github_app" in comment and comment["performed_via_github_app"] is None,
          "ISSUE_47_MODEL_APPROVAL_WAS_POSTED_THROUGH_AN_APP:" + where)


def register_model_approval(*, repo_root: Path, comment_url, reader):
    """Write the model allowance from an approval comment that is already on GitHub.

    Nothing here writes to GitHub. The comment is read through ``reader``; its
    body must be byte for byte the committed proposal - what the owner read is
    what is registered - its author the trusted approver and its place this
    issue. The record and the policy are written from what was read, and the
    result is put through ``model_allowance`` with the same reader, so the file
    that grants is checked by the gate that will read it. Registering the same
    approval again is a no-op; a policy that already says something else is
    refused rather than overwritten. The SEC allowance's registration works the
    same way.
    """
    from .historical_source_acquisition import (_RECORD_FIELDS, TRUSTED_APPROVER,
                                                TRUSTED_REPOSITORY, _comment_url, _provenance,
                                                posted_text)
    repo_root = Path(repo_root)
    match = _comment_url(repository=TRUSTED_REPOSITORY).match(str(comment_url))
    _need(match is not None, "ISSUE_47_MODEL_APPROVAL_URL_IS_NOT_THIS_ISSUE_S_COMMENT:"
          + str(comment_url)[:120])
    proposal = repo_root / APPROVAL_BODY_PATH
    _need(proposal.is_file() and not proposal.is_symlink(),
          "ISSUE_47_MODEL_APPROVAL_PROPOSAL_MISSING:" + APPROVAL_BODY_PATH)
    proposed = proposal.read_bytes()
    fetched = reader("repos/" + TRUSTED_REPOSITORY + "/issues/comments/" + match[1])
    _need(type(fetched) is dict and type(fetched.get("body")) is str,
          "ISSUE_47_MODEL_DELEGATION_FETCH_DID_NOT_RETURN_A_COMMENT")
    _need(posted_text(fetched["body"]).encode("utf-8") == proposed,
          "ISSUE_47_MODEL_POSTED_BODY_IS_NOT_THE_PROPOSED_TEXT:sha256="
          + sha256_bytes(content=posted_text(fetched["body"]).encode("utf-8")))
    try:
        body = strict_json_loads(text=posted_text(fetched["body"]))
    except ValueError:
        raise HistoricalModelCallError("ISSUE_47_MODEL_DELEGATION_BODY_IS_NOT_A_RECORD")
    _need(type(body) is dict, "ISSUE_47_MODEL_DELEGATION_BODY_IS_NOT_A_RECORD")
    policy = {"requirement_id": REQUIREMENT_ID, "repository": TRUSTED_REPOSITORY,
              "approver_login": TRUSTED_APPROVER, "delegation_url": fetched.get("html_url"),
              "delegation_body_sha256": sha256_bytes(content=proposed),
              "delegation_record_path": APPROVAL_RECORD_PATH,
              "model_wiring_receipt_path": WIRING_RECEIPT_PATH,
              **{field: body.get(field) for field in RESTATED_BY_THE_COMMENT}}
    _provenance(comment=fetched, policy=policy, where="fetched")
    _posted_by_the_approver_directly(fetched, where="fetched")
    record = {field: fetched.get(field) for field in _RECORD_FIELDS}
    record["user"] = {key: fetched.get("user", {}).get(key) for key in ("login", "id", "type")}
    record["performed_via_github_app"] = fetched["performed_via_github_app"]
    outputs = {ALLOWANCE_PATH: policy, APPROVAL_RECORD_PATH: record}
    _write_registered(repo_root, outputs)
    allowance = model_allowance(repo_root=repo_root, delegation_reader=reader)
    # The ledger this approval grants, for the consumers of LIVE registrations,
    # written only once the gate that will read the allowance has accepted it.
    # This is the only place it is written, so a test's fixture ledger - which
    # never comes through here - is never one a Run accepts.
    granted = {GRANTED_LEDGER_PATH: granted_ledger_record(allowance)}
    _write_registered(repo_root, granted)
    outputs.update(granted)
    return {"status": "MODEL_APPROVAL_REGISTERED", "delegation_url": allowance["delegation_url"],
            "delegation_body_sha256": allowance["delegation_body_sha256"],
            "budget_root": allowance["budget_root"],
            "limits": allowance["maximum_additional_provider_paid_sec_calls"],
            "model_wiring_receipt_id": allowance["model_wiring_receipt_id"],
            "written": sorted(outputs), "calls": [0, 0, 0]}


def _write_registered(repo_root, outputs):
    """Write each record once; the same bytes again is a no-op, different bytes a refusal."""
    for relative, value in outputs.items():
        data = (json.dumps(value, ensure_ascii=False, indent=1, sort_keys=True) + "\n").encode("utf-8")
        path = Path(repo_root) / relative
        if path.exists():
            _need(path.read_bytes() == data,
                  "ISSUE_47_MODEL_ALLOWANCE_ALREADY_REGISTERED_DIFFERENTLY:" + relative)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as handle:
            handle.write(data)


def request_in_scope(*, allowance, metric_id, company_id, report_end, purpose=PURPOSE,
                     request_digest=None):
    """The grants that cover this request whole; refuses when none does.

    With ``request_digest`` a grant covers the request only if it names that
    digest: a position inside a grant is not enough, the request has to be one
    the approval listed. Without it only the position is asked, which is what
    the runner asks before it builds a position's requests.
    """
    scope = allowance["scope"]
    _need(purpose in scope["purposes"], "ISSUE_47_MODEL_PURPOSE_NOT_IN_SCOPE:" + str(purpose))
    covering = sorted(grant["grant"] for grant in scope["grants"]
                      if metric_id in grant["metric_ids"] and company_id in grant["company_ids"]
                      and grant["earliest_report_end"] <= report_end <= grant["latest_report_end"])
    _need(bool(covering), "ISSUE_47_MODEL_REQUEST_OUTSIDE_EVERY_GRANT:" + metric_id + ":"
          + company_id + ":" + str(report_end))
    if request_digest is not None:
        named = {grant["grant"]: grant["request_digests"] for grant in scope["grants"]}
        covering = [name for name in covering if request_digest in named[name]]
        _need(bool(covering), "ISSUE_47_MODEL_REQUEST_DIGEST_NOT_GRANTED:" + metric_id + ":"
              + company_id + ":" + str(report_end) + ":" + str(request_digest))
    return covering


def planned_request_digests(*, company_id, metric_id, period_selection, transport,
                            data_root: Path = ROOT):
    """The ledger digest of every request a pinned period would send; no authority, no call.

    What an approval's grants list. Built by the functions the call path
    itself uses - the pinned source, its partition into requests and
    ``ledger_digest`` - so the digests an owner approves are the ones a claim
    computes, and a request whose prompt, contract or source bytes changed is a
    different digest the approval does not name.
    """
    from .ai_adapter import TransportPolicy
    _need(metric_id in MODEL_METRICS, "ISSUE_47_MODEL_METRIC_NOT_WIRED:" + metric_id)
    policy = TransportPolicy.from_mapping(value=dict(transport))
    if metric_id in SINGLE_REQUEST_SOURCE_TYPES:
        source = _single_request_source(data_root=data_root, company_id=company_id,
                                        metric_id=metric_id, period_selection=period_selection)
        return [ledger_digest(source["request"], policy)]
    from .historical_semantic_results import pinned_native_source, pinned_requests
    source = pinned_native_source(repo_root=data_root, company_id=company_id,
                                  metric_id=metric_id, period_selection=period_selection)
    return [ledger_digest(request, policy) for request in pinned_requests(source)]


def transport_policy(*, allowance, repo_root: Path = ROOT):
    """The granted transport, compiled by the adapter's own parser."""
    from .ai_adapter import TransportPolicy
    from .provider_runtime import load_provider_runtime_authority
    selected = TransportPolicy.from_mapping(value=dict(allowance["transport"]))
    load_provider_runtime_authority(repo_root=repo_root, provider=selected.provider,
                                    model=selected.model, api=selected.api)
    return selected


# ------------------------------------------------- what the controller would bind


def _allowance_hashes(allowance):
    """The three decision hashes an issue_47_v1 plan carries, from the allowance.

    The ledger root and the verified code are bound with the grant: an
    independent review passed a mapping that differed from the allowance only
    in its ledger root, with a fresh ledger there, and a request the granted
    ledger had stopped at HTTP 402 went out again.
    """
    return {"provider_transport_decision_hash": content_hash(value=allowance["transport"]),
            "transport_retry_decision_hash": content_hash(value=allowance["retry_policy"]),
            "live_call_bound_decision_hash": content_hash(value={
                "delegation_url": allowance["delegation_url"],
                "delegation_body_sha256": allowance["delegation_body_sha256"],
                "limits": allowance["maximum_additional_provider_paid_sec_calls"],
                "scope": allowance["scope"], "budget_root": allowance["budget_root"],
                "model_wiring_receipt_id": allowance["model_wiring_receipt_id"]})}


def _as_granted(allowance):
    """An allowance mapping without the one field that says how it was read."""
    return {key: value for key, value in allowance.items()
            if key != "provenance_verified_against_github"}


def allowance_is_the_file_s(allowance):
    """The caller's allowance mapping is the allowance file's, field for field.

    Every consumer that is handed a mapping - a prepared request, a ledger, a
    registration - asks this, so no field of a mapping the file does not hold
    reaches a check, whatever that check compares.
    """
    _need(type(allowance) is dict
          and _as_granted(allowance) == _as_granted(model_allowance(repo_root=ROOT)),
          "ISSUE_47_MODEL_ALLOWANCE_IS_NOT_THE_ONE_THE_AUTHORITY_BOUND")
    return allowance


def invocation_authority_fields(*, requirement, repo_root: Path):
    """(identity, policy, transport, files) for WB-3's issue_47_v1 authority.

    Called only by the controller branch the registration patch adds; the
    controller builds the authority with its own private factory, so this
    module can describe an authority but never hold one it made. The file map
    is the Requirement's execution authority plus the call path's own modules,
    the allowance and the saved approval: the controller re-hashes all of them
    at every check, so any of them changing mid-run refuses the call.
    """
    from .requirement_profile import requirement_authority_paths, validate_execution_authority
    _need(requirement.get("requirement_id") == REQUIREMENT_ID,
          "ISSUE_47_MODEL_AUTHORITY_IS_FOR_ISSUE_47_V1_ONLY")
    root = Path(repo_root).resolve(strict=True)
    validate_execution_authority(repo_root=root, requirement=requirement)
    allowance = model_allowance(repo_root=root)
    selected = transport_policy(allowance=allowance, repo_root=root)
    identity = {"artifact_requirement_generation": "EXPLICIT_REQUIREMENT_V1",
                "requirement_id": REQUIREMENT_ID,
                "requirement_closure_hash": requirement["requirement_closure_hash"],
                "requirement_hashes": requirement["hashes"]}
    policy = {**_allowance_hashes(allowance), "automatic_retry_count": 0,
              "response_reuse_authorized": False,
              "requirement_closure_hash": requirement["requirement_closure_hash"]}
    transport = {**selected.as_mapping(),
                 "pre_execution_context_tokens_max": FIXED_RETRY_POLICY["context_ceiling_tokens"]}
    paths = set(requirement_authority_paths(repo_root=root, requirement=requirement))
    paths |= {*CALL_PATH_FILES, ALLOWANCE_PATH, allowance["delegation_record_path"]}
    files = {}
    for relative in sorted(paths):
        raw = resolve_repository_file(repo_root=root, repo_relative_path=relative).read_bytes()
        files[relative] = {"sha256": sha256_bytes(content=raw), "size": len(raw)}
    return identity, policy, transport, files


# ------------------------------------------------------------------- the request


@dataclass(frozen=True)
class HistoricalSemanticRequest:
    """One request a pinned D04 source partitions into, bound to #47's authority."""

    _factory: object
    company_id: str
    metric_id: str
    report_end: str
    period_selection: dict
    source_bytes: bytes
    request_bytes: bytes
    provider_request_body_bytes: bytes
    output_schema_bytes: bytes
    authority: object
    allowance: dict
    data_root: Path

    def validate(self, policy):
        """The request is still one its source partitions into, over unchanged saved bytes.

        The source is rebuilt from the pinned filing and must be the bytes the
        request was prepared from; then its identity is recomputed, every
        unit's bytes re-hashed, every saved file it was read from re-proved,
        and the request required to be one the source partitions into.

        Returns:
            (request, admission): the request mapping and the source-proof
            admission of the saved files now.
        """
        from .continuous_semantic_calls import request_body, validate_source_unit_bytes
        from .historical_semantic_results import pinned_native_source, pinned_requests
        from .native_unit_index import evidence_json_bytes
        from .ordinary_source_authority import verify_ordinary_source_proofs
        from git_workspace import first_symlink_in_path
        _need(self._factory is _FACTORY, "ISSUE_47_MODEL_REQUEST_FACTORY_REQUIRED")
        _authority_is_issue_47(self.authority, self.allowance)
        _need(first_symlink_in_path(path=Path(self.data_root)) is None,
              "ISSUE_47_MODEL_SOURCE_ROOT_ALIAS")
        # Rebuilt from the saved filing, not only re-hashed. An independent
        # review edited a unit's text, recomputed every id over it, and the
        # request reached the opener: a content-addressed source proves only
        # that it is itself. The rebuild is what ties it to the filing.
        if self.metric_id in SINGLE_REQUEST_SOURCE_TYPES:
            return self._validate_single(policy)
        rebuilt = pinned_native_source(repo_root=self.data_root, company_id=self.company_id,
                                       metric_id=self.metric_id, period_selection=self.period_selection)
        _need(evidence_json_bytes(rebuilt) == self.source_bytes,
              "ISSUE_47_MODEL_SOURCE_DOES_NOT_REBUILD_FROM_THE_FILING")
        source = strict_json_loads(text=self.source_bytes.decode("utf-8"))
        _need(_identity_holds(source, "semantic_source_id")
              and source["company_id"] == self.company_id and source["metric_id"] == self.metric_id
              and source["prepared_annual_input"]["table_input"]["target_period"]["period_end"]
              == self.report_end, "ISSUE_47_MODEL_SOURCE_CHANGED")
        validate_source_unit_bytes(source)
        admission = verify_ordinary_source_proofs(data_root=self.data_root,
                                                  proofs=source["source_proofs"])
        request = strict_json_loads(text=self.request_bytes.decode("utf-8"))
        _need(request in pinned_requests(source), "ISSUE_47_MODEL_REQUEST_NOT_IN_ITS_SOURCE")
        _need(transport_policy(allowance=self.allowance, repo_root=ROOT) == policy
              and request_body(request, policy) == self.provider_request_body_bytes
              and canonical_json_bytes(value=request["response_protocol"])
              == self.output_schema_bytes, "ISSUE_47_MODEL_PROVIDER_PAYLOAD_CHANGED")
        return request, admission


def _validate_single(self, policy):
    """E01's or D02's request, rebuilt from the saved filings by the route, its proofs re-proved."""
    from .continuous_semantic_calls import request_body
    from .native_unit_index import evidence_json_bytes
    from .ordinary_source_authority import verify_ordinary_source_proofs
    rebuilt = _single_request_source(data_root=self.data_root, company_id=self.company_id,
                                     metric_id=self.metric_id, period_selection=self.period_selection)
    _need(evidence_json_bytes(rebuilt) == self.source_bytes,
          "ISSUE_47_MODEL_SOURCE_DOES_NOT_REBUILD_FROM_THE_FILING")
    request = strict_json_loads(text=self.request_bytes.decode("utf-8"))
    _need(request == rebuilt["request"] and request["company_id"] == self.company_id
          and request["record_type"] == REQUEST_TYPES[self.metric_id]
          and _request_report_end(request) == self.report_end,
          "ISSUE_47_MODEL_REQUEST_NOT_IN_ITS_SOURCE")
    admission = verify_ordinary_source_proofs(data_root=self.data_root,
                                              proofs=rebuilt["source_proofs"])
    _need(transport_policy(allowance=self.allowance, repo_root=ROOT) == policy
          and request_body(request, policy) == self.provider_request_body_bytes
          and canonical_json_bytes(value=request["response_protocol"]) == self.output_schema_bytes,
          "ISSUE_47_MODEL_PROVIDER_PAYLOAD_CHANGED")
    return request, admission


HistoricalSemanticRequest._validate_single = _validate_single


def _authority_is_issue_47(authority, allowance):
    """The controller's issue_47_v1 authority, made from this very allowance.

    The authority is made from the allowance file and re-hashes it at every
    check, so an allowance mapping a caller passes cannot widen the scope,
    limits or transport the controller bound: its hashes must be the ones the
    authority carries.
    """
    from .invocation_control import SuccessorInvocationAuthority
    _need(type(authority) is SuccessorInvocationAuthority,
          "ISSUE_47_MODEL_AUTHORITY_IS_FOR_ANOTHER_REQUIREMENT")
    identity, policy, _ = authority._check()
    _need(identity["requirement_id"] == REQUIREMENT_ID,
          "ISSUE_47_MODEL_AUTHORITY_IS_FOR_ANOTHER_REQUIREMENT")
    _need(all(policy[key] == value for key, value in _allowance_hashes(allowance).items()),
          "ISSUE_47_MODEL_ALLOWANCE_IS_NOT_THE_ONE_THE_AUTHORITY_BOUND")
    allowance_is_the_file_s(allowance)


def prepare_historical_requests(*, company_id, metric_id, period_selection, authority,
                                allowance, data_root: Path = ROOT):
    """Every request a pinned period's source partitions into, each bound to #47's authority.

    ``authority`` is the controller's ``issue_47_v1`` authority, which exists
    only where the registration patch is applied; elsewhere the controller
    refuses to make one and nothing below is reachable.
    """
    from .continuous_semantic_calls import request_body
    from .historical_semantic_results import (pinned_native_source,
                                              pinned_requests)
    from .native_unit_index import evidence_json_bytes
    _need(metric_id in MODEL_METRICS, "ISSUE_47_MODEL_METRIC_NOT_WIRED:" + metric_id)
    _authority_is_issue_47(authority, allowance)
    policy = transport_policy(allowance=allowance, repo_root=ROOT)
    if metric_id in SINGLE_REQUEST_SOURCE_TYPES:
        # One request per position: the route's own question, built from the
        # filings' saved bytes by the route itself.
        source = _single_request_source(data_root=data_root, company_id=company_id,
                                        metric_id=metric_id, period_selection=period_selection)
        request = source["request"]
        return [HistoricalSemanticRequest(_FACTORY, company_id, metric_id,
                                          period_selection["target_report_end"], period_selection,
                                          evidence_json_bytes(source), evidence_json_bytes(request),
                                          request_body(request, policy),
                                          canonical_json_bytes(value=request["response_protocol"]),
                                          authority, allowance, Path(data_root))]
    source = pinned_native_source(repo_root=data_root, company_id=company_id,
                                  metric_id=metric_id, period_selection=period_selection)
    raw = evidence_json_bytes(source)
    return [HistoricalSemanticRequest(_FACTORY, company_id, metric_id,
                                      period_selection["target_report_end"], period_selection,
                                      raw, evidence_json_bytes(request),
                                      request_body(request, policy),
                                      canonical_json_bytes(value=request["response_protocol"]),
                                      authority, allowance, Path(data_root))
            for request in pinned_requests(source)]


def loaded_code_holds(authority):
    """What this process runs is the checkout's bound source, compiled from source.

    Two findings of an independent review, answered at the last point before a
    socket. An unbound file placed in ``scripts/`` shadowed the pinned
    tokenizer's package; every hash still verified, since nothing names a file
    nobody bound, and a request of about 423,000 tokens was planned as 4,097
    and sent. And a changed bytecode file beside an unchanged source ran code
    the approval never saw, because the receipt, the approval and the
    controller all hash sources. So every module this process loaded from the
    checkout must be a file the controller's authority binds - the test
    package, which the runner never imports, excepted - and must have been
    compiled into a private cache outside the checkout (``sys.pycache_prefix``,
    which the runner sets before it imports anything of the checkout's), never
    read from the checkout's own ``__pycache__``.
    """
    root = Path(authority.root)
    prefix = sys.pycache_prefix
    _need(prefix is not None and Path(prefix).is_absolute() and Path(prefix).is_dir()
          and root not in Path(os.path.realpath(prefix)).parents
          and Path(os.path.realpath(prefix)) != root,
          "ISSUE_47_MODEL_CALL_WITHOUT_A_PRIVATE_BYTECODE_CACHE")
    private = os.path.realpath(prefix) + os.sep
    bound = set(strict_json_loads(text=authority._files.decode("utf-8")))
    unbound, cached_in_the_checkout = [], []
    for module in list(sys.modules.values()):
        where = getattr(module, "__file__", None)
        if not where:
            continue
        real = Path(os.path.realpath(where))
        if root not in real.parents:
            continue
        relative = real.relative_to(root).as_posix()
        if relative.startswith("tests/"):
            continue
        if relative not in bound:
            unbound.append(relative)
        spec = getattr(module, "__spec__", None)
        cached = getattr(spec, "cached", None)
        if cached and not os.path.realpath(cached).startswith(private):
            cached_in_the_checkout.append(relative)
    _need(not unbound, "ISSUE_47_MODEL_UNBOUND_CODE_LOADED:" + ",".join(sorted(unbound)[:8]))
    _need(not cached_in_the_checkout, "ISSUE_47_MODEL_CODE_READ_FROM_THE_CHECKOUT_S_BYTECODE:"
          + ",".join(sorted(cached_in_the_checkout)[:8]))


# The request each thread's counted send is sending right now, with its slot. The
# adapter's payload hook returns bytes for #47's request type only while that
# send holds it: an independent review built the adapter's transport directly,
# passed the egress capability it reached by attribute lookup and a prepared
# request, and the bytes reached the opener with no slot and no WB-3 plan - the
# egress gate's exact caller set is a static scan, which a lookup by name
# passes. Checked at the hook itself, every socket for #47 needs a counted
# claim whose WB-3 marker already exists, whoever called the transport.
_SENDING = {}


@contextmanager
def sending(*, prepared, ledger, path, intent, execution_id):
    """Hold ``prepared`` as this thread's one counted send, for the duration of the socket."""
    _need(type(prepared) is HistoricalSemanticRequest and prepared._factory is _FACTORY
          and type(ledger) is HistoricalModelLedger and ledger._factory is _FACTORY
          and ledger.claimed_slot(path=path, intent=intent),
          "ISSUE_47_MODEL_SEND_WITHOUT_A_COUNTED_SLOT")
    key = threading.get_ident()
    _need(key not in _SENDING, "ISSUE_47_MODEL_SEND_ALREADY_IN_PROGRESS")
    _SENDING[key] = (prepared, ledger, Path(path), intent, execution_id)
    try:
        yield
    finally:
        _SENDING.pop(key, None)


def transport_payload(*, request, policy):
    """What the adapter's scoped-payload hook returns for #47's request type.

    Only ``ai_adapter._scoped_transport_payload`` calls this (registration
    patch), immediately before it builds the socket request. The request must
    be the one this thread's counted send holds - its slot still open and its
    WB-3 egress marker written - and it is rebuilt from the saved filing, so
    bytes that no longer rebuild never reach the wire.
    """
    from . import invocation_control as control
    _need(type(request) is HistoricalSemanticRequest, "ISSUE_47_MODEL_REQUEST_TYPE_REQUIRED")
    held = _SENDING.get(threading.get_ident())
    _need(held is not None and held[0] is request, "ISSUE_47_MODEL_TRANSPORT_WITHOUT_A_COUNTED_SEND")
    prepared, ledger, path, intent, execution_id = held
    loaded_code_holds(prepared.authority)
    markers = control._egress_markers_for_execution(root=path / "invocation_control",
                                                    execution_id=execution_id)
    _need(ledger.claimed_slot(path=path, intent=intent) and len(markers) == 1
          and markers[0]["ai_invocation_plan_id"] == intent["plan_id"],
          "ISSUE_47_MODEL_TRANSPORT_WITHOUT_A_COUNTED_SEND")
    fields, _ = request.validate(policy)
    _need(ledger_digest(fields, policy) == intent["request_digest"],
          "ISSUE_47_MODEL_TRANSPORT_WITHOUT_A_COUNTED_SEND")
    return request.request_bytes, request.provider_request_body_bytes, request.output_schema_bytes


def build_plan(prepared):
    """The WB-3 successor plan for one prepared request, under #47's authority."""
    from .continuous_request_context import measure_request
    from .invocation_control import build_successor_ai_invocation_plan
    from .provider_runtime import load_provider_runtime_authority
    policy = transport_policy(allowance=prepared.allowance, repo_root=ROOT)
    request, _ = prepared.validate(policy)
    runtime = load_provider_runtime_authority(repo_root=ROOT, provider=policy.provider,
                                              model=policy.model, api=policy.api)
    context = measure_request(prepared.provider_request_body_bytes, provider=policy.provider,
                              model=policy.model, api=policy.api)
    plan = build_successor_ai_invocation_plan(
        repo_root=ROOT, requirement_id=REQUIREMENT_ID, authority=prepared.authority,
        release_input_plan_id=content_hash(value={"purpose": PURPOSE + ":" + prepared.metric_id,
                                                  "source": request["source_id"]}),
        source_identity_hash=request["source_id"],
        selected_representation_hash=request["request_id"],
        task_contract_hash=content_hash(value={"metric": prepared.metric_id,
                                               "prompt": request["system_prompt"]}),
        output_schema_hash=content_hash(value=request["response_protocol"]),
        serialization_version="issue47-historical-" + prepared.metric_id.lower() + "-chat-v1",
        provider=policy.provider, model=policy.model, api=policy.api,
        request_body=prepared.provider_request_body_bytes,
        maximum_payload_bytes=policy.maximum_payload_bytes,
        maximum_context_tokens=FIXED_RETRY_POLICY["context_ceiling_tokens"],
        estimated_context_tokens=context["context_tokens"],
        context_authority_hash=content_hash(value={
            "provider_runtime": runtime["context_authority_hash"],
            "bounded_chat_context": context["context_authority_hash"]}),
        estimator_id=context["estimator_id"], estimator_version=context["estimator_version"],
        estimator_method=context["estimator_method"], billing_class=runtime["billing_class"],
        paid_call_observation_source=runtime["paid_call_observation_source"],
        pricing_snapshot_hash=content_hash(value={"provider": policy.provider,
                                                  "model": policy.model,
                                                  "status": "NON_BLOCKING_PRICE_UNAVAILABLE"}),
        estimated_cost=None)
    _need(plan["observability"]["estimated_context_tokens"]
          <= FIXED_RETRY_POLICY["context_ceiling_tokens"]
          and len(prepared.provider_request_body_bytes) <= policy.maximum_payload_bytes,
          "ISSUE_47_MODEL_REQUEST_RESOURCE_LIMIT")
    return policy, plan, request


# --------------------------------------------------------------------- the ledger


def _slot_evidence(*, path, intent, live):
    """What a slot's own files say happened, and the stop that follows from it.

    Read from the controller's execution receipt, its single egress marker and
    the wire journal the transport wrote - never from the terminal, which is
    only a seal over these. So the stop a ledger acts on cannot be edited away
    by rewriting the terminal and recomputing its hash: an independent review
    had the stop read back from the self-hashed terminal alone.
    """
    executions = sorted((path / "invocation_control" / "executions").glob("*.json"))
    _need(len(executions) == 1, "ISSUE_47_MODEL_SLOT_EXECUTION_NOT_EXACTLY_ONE:" + path.name)
    execution = strict_json_file(path=executions[0])
    identity = execution["execution_id"].split(":", 1)[1]
    _need(executions[0].name == identity + ".json" and _identity_holds(execution, "execution_receipt_id"),
          "ISSUE_47_MODEL_NATIVE_TERMINAL_CHANGED")
    marker = _read(path, "invocation_control/egress/" + identity + "/01.json")
    _need(_identity_holds(marker, "egress_marker_id")
          and marker["ai_invocation_plan_id"] == intent["plan_id"]
          and marker["execution_id"] == execution["execution_id"]
          and marker["attempt_ordinal"] == 1
          and marker["transport_kind"] == ("REAL_MODEL_PROVIDER" if live else "MOCK"),
          "ISSUE_47_MODEL_NATIVE_MARKER_CHANGED")
    _need(execution["counters"] == {"real_model_provider_egress_count": int(live),
                                    "paid_model_provider_call_count": int(live),
                                    "mock_transport_invocation_count": int(not live)},
          "ISSUE_47_MODEL_NATIVE_COUNT_CHANGED")
    wire = _read(path, "wire/journal.json")
    _need(_identity_holds(wire, "wire_id") and wire["intent_id"] == intent["intent_id"]
          and wire["execution_id"] == execution["execution_id"]
          and wire["mode"] == ("LIVE" if live else "RECORDED_TEST_ONLY"),
          "ISSUE_47_MODEL_WIRE_CHANGED")
    for name, field in (("raw-response.bin", "raw_response_sha256"),
                        ("assistant-output.bin", "assistant_output_sha256")):
        present = (path / "wire" / name).is_file()
        _need(present == (wire[field] is not None)
              and (not present or sha256_file(path=path / "wire" / name) == wire[field]),
              "ISSUE_47_MODEL_WIRE_BYTES_CHANGED:" + name)
    stop = wire["error_class"] if wire["error_class"] in STOPS else ""
    if execution["status"] == "UNKNOWN_REMOTE_OUTCOME":
        stop = "UNKNOWN_REMOTE_OUTCOME"
    if wire["usage"]["input_tokens"] is None or wire["usage"]["output_tokens"] is None:
        stop = stop or "USAGE_UNKNOWN"
    return execution, wire, stop


class HistoricalModelLedger:
    """#47's cumulative provider and paid count, with a process lock over its root.

    One claim is one provider call and one paid call, written before the socket
    and never removed, so a failure counts. A request is claimed at most once:
    an unchanged request is not redrawn. A slot with no terminal may have
    reached the endpoint, so it counts in full and stops the channel until an
    owner reconciles it; so does any slot whose own evidence implies a stop.

    An independent review found the previous version rebuilt every count from
    whichever slot directories existed: deleting a stopped slot released the
    stop and the same request could be claimed again, and deleting the root
    reset the cap. This one keeps #47's SEC ledger's protections, which follow
    issue #28's: the lock is on the root directory, which with its parents may
    not be a symlink; a binding written on first use must still be there and
    unchanged, with a copy beside the root that deleting the root does not take
    with it; every claim is appended to a synced log before its slot exists,
    each naming the one before it; and the slots must be exactly the log.
    """

    def __init__(self, *, factory, root, binding, live):
        _need(factory is _FACTORY, "ISSUE_47_MODEL_LEDGER_FACTORY_REQUIRED")
        self._factory = factory
        self.root = Path(root)
        self.binding = binding
        self.live = live
        self._locked = False

    @property
    def mode(self):
        return "LIVE" if self.live else "RECORDED_TEST_ONLY"

    @staticmethod
    def anchor_path(root):
        """Where the initialization anchor of a ledger at ``root`` lives: beside it."""
        root = Path(root)
        return root.parent / ("." + root.name + ".initialized.json")

    @staticmethod
    def mirror_path(root):
        """Where the claim log's copy outside the root lives: beside it, with the anchor.

        An independent review deleted the slots and the claim log together,
        kept the binding and the anchor, and the ledger read as unused: the
        count, the stops and the no-redraw rule all started again. Every claim
        is now appended here first, and the log inside the root must be this
        copy, so emptying the root no longer empties the ledger.
        """
        root = Path(root)
        return root.parent / ("." + root.name + ".claims.jsonl")

    @contextmanager
    def locked(self):
        self.granted()
        _need(self.root.is_absolute()
              and not any(path.is_symlink() for path in [self.root, *self.root.parents]),
              "ISSUE_47_MODEL_LEDGER_PATH_ALIAS:" + str(self.root))
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        handle = os.open(str(self.root), os.O_RDONLY)
        try:
            fcntl.flock(handle, fcntl.LOCK_EX)
            self._locked = True
            self._check_binding()
            yield self
        finally:
            self._locked = False
            fcntl.flock(handle, fcntl.LOCK_UN)
            os.close(handle)

    def _check_binding(self):
        binding_path, anchor = self.root / "binding.json", self.anchor_path(self.root)
        mirror = self.mirror_path(self.root)
        if not binding_path.exists():
            # A new ledger. A slot, a claim log, an anchor or a mirror without
            # a binding is a ledger that was reset, and is refused rather than
            # restarted.
            present = sorted(path.name for path in self.root.iterdir())
            _need(not anchor.exists() and not mirror.exists() and not present,
                  "ISSUE_47_MODEL_LEDGER_BINDING_MISSING_OR_RESET:" + ",".join(present))
            _write_once(anchor, self.binding)
            os.close(os.open(str(mirror), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600))
            _write_once(binding_path, self.binding)
        _need(anchor.is_file() and not anchor.is_symlink(),
              "ISSUE_47_MODEL_LEDGER_INITIALIZATION_ANCHOR_MISSING:" + str(anchor))
        _need(mirror.is_file() and not mirror.is_symlink(),
              "ISSUE_47_MODEL_LEDGER_CLAIM_MIRROR_MISSING:" + str(mirror))
        _need(strict_json_file(path=anchor) == self.binding,
              "ISSUE_47_MODEL_LEDGER_INITIALIZATION_ANCHOR_CHANGED")
        _need(strict_json_file(path=binding_path) == self.binding, "ISSUE_47_MODEL_LEDGER_BINDING_CHANGED")

    def _claims(self):
        """The claim log inside the root, which must be its copy beside the root line for line.

        A ledger nothing has initialized - no binding, no log and no copy - has
        no claims; any one of them present means it was initialized, and then
        the copy must be there. (Initializing, and refusing a ledger whose
        binding went while its anchor stayed, is the lock's.)
        """
        path = self.root / "claims.jsonl"
        mirror = self.mirror_path(self.root)
        if not ((self.root / "binding.json").exists() or path.exists() or mirror.exists()):
            return []
        claims = []
        if path.exists():
            _need(path.is_file() and not path.is_symlink(), "ISSUE_47_MODEL_LEDGER_CLAIM_LOG_UNSAFE")
            claims = [strict_json_loads(text=line)
                      for line in path.read_text(encoding="utf-8").splitlines()]
        _need(mirror.is_file() and not mirror.is_symlink(),
              "ISSUE_47_MODEL_LEDGER_CLAIM_MIRROR_MISSING:" + str(mirror))
        copy = [strict_json_loads(text=line) for line in mirror.read_text(encoding="utf-8").splitlines()]
        _need(copy == claims, "ISSUE_47_MODEL_LEDGER_CLAIM_LOG_DIFFERS_FROM_ITS_MIRROR:"
              + str(len(claims)) + " in the root, " + str(len(copy)) + " beside it")
        return claims

    def snapshot(self):
        """Counts, stops and claimed requests: the slots, checked against the claim log.

        A missing slot, a missing claim or a slot in the wrong place is a
        refusal, not a smaller count; each slot's stop is recomputed from its
        own evidence and must be the one its terminal records.
        """
        calls = self.root / "calls"
        slots = sorted(calls.iterdir()) if calls.is_dir() else []
        claims = self._claims()
        _need(len(slots) == len(claims), "ISSUE_47_MODEL_LEDGER_CLAIM_SET_CHANGED:"
              + str(len(slots)) + " slots, " + str(len(claims)) + " claims")
        _need([slot.name for slot in slots] == ["%04d" % (i + 1) for i in range(len(slots))],
              "ISSUE_47_MODEL_LEDGER_SLOT_SEQUENCE_CHANGED")
        counts, stopped, requests, rows, previous = [0, 0, 0], [], set(), [], None
        for ordinal, (slot, claim) in enumerate(zip(slots, claims), start=1):
            _need(slot.is_dir() and not slot.is_symlink(), "ISSUE_47_MODEL_LEDGER_SLOT_UNSAFE:" + slot.name)
            intent = _read(slot, "intent.json")
            _need(intent == claim, "ISSUE_47_MODEL_LEDGER_CLAIM_CHANGED:" + slot.name)
            _need(_identity_holds(intent, "intent_id") and intent["ordinal"] == ordinal
                  and intent["requirement_id"] == REQUIREMENT_ID
                  and intent["allowance_binding_id"] == self.binding["binding_id"]
                  and intent["execution_mode"] == self.mode
                  and intent["previous_intent_id"] == previous,
                  "ISSUE_47_MODEL_LEDGER_SLOT_CHANGED:" + slot.name)
            _need(intent["request_digest"] not in requests,
                  "ISSUE_47_MODEL_LEDGER_REQUEST_CLAIMED_TWICE:" + slot.name)
            requests.add(intent["request_digest"])
            previous = intent["intent_id"]
            counts = [counts[0] + 1, counts[1] + 1, counts[2]]
            if not (slot / "terminal.json").is_file():
                stopped.append(slot.name + "=UNKNOWN_PENDING_RECONCILIATION")
                rows.append({"ordinal": ordinal, "status": "UNKNOWN_PENDING_RECONCILIATION"})
                continue
            terminal = _read(slot, "terminal.json")
            _need(_identity_holds(terminal, "terminal_id")
                  and terminal["intent_id"] == intent["intent_id"]
                  and terminal["counts"] == [1, 1, 0],
                  "ISSUE_47_MODEL_LEDGER_TERMINAL_CHANGED:" + slot.name)
            for relative, digest in terminal["evidence"].items():
                _need(sha256_file(path=resolve_repository_file(
                    repo_root=slot, repo_relative_path=relative)) == digest,
                    "ISSUE_47_MODEL_LEDGER_EVIDENCE_CHANGED:" + slot.name + "/" + relative)
            execution, _wire, stop = _slot_evidence(path=slot, intent=intent, live=self.live)
            _need(terminal["stop_reason"] == stop and terminal["status"] == execution["status"]
                  and terminal["execution_receipt_id"] == execution["execution_receipt_id"],
                  "ISSUE_47_MODEL_LEDGER_TERMINAL_DISAGREES_WITH_ITS_EVIDENCE:" + slot.name)
            if stop:
                stopped.append(slot.name + "=" + stop)
            rows.append({"ordinal": ordinal, "status": terminal["status"]})
        _need(all(a <= b for a, b in zip(counts, self.binding["limits"])),
              "ISSUE_47_MODEL_LEDGER_COUNT_EXCEEDS_THE_ALLOWANCE")
        return {"counts": counts, "limits": list(self.binding["limits"]), "stopped": stopped,
                "requests": sorted(requests), "rows": rows, "previous_intent_id": previous}

    def granted(self):
        """A live ledger is the one the allowance file grants, not one a mapping described.

        A ledger built from a caller's mapping carries that mapping's limits,
        request list and root: an independent review built one at a fresh root
        and a request the granted ledger had stopped went out again. So a live
        ledger's binding is derived again from the allowance file itself, at
        the file's root, before the lock creates anything and before each
        claim. A recorded ledger opens no socket and registers nothing a Run
        reads by default, so it is not held to the grant.
        """
        if not self.live:
            return self
        allowance = model_allowance(repo_root=ROOT)
        root = Path(allowance["budget_root"])
        _need(self.root == root
              and self.binding == _ledger(allowance=allowance, root=root, live=True).binding,
              "ISSUE_47_MODEL_LEDGER_IS_NOT_THE_GRANTED_ONE")
        return self

    def claim(self, *, request_digest, plan_id, purpose, grants, request_identity,
              authority_files_hash):
        """Write the counted intent before any socket; refuses when a stop or limit holds."""
        _need(self._locked, "ISSUE_47_MODEL_LEDGER_LOCK_REQUIRED")
        self.granted()
        _need(purpose in self.binding["purposes"], "ISSUE_47_MODEL_PURPOSE_NOT_IN_ALLOWANCE")
        state = self.snapshot()
        _need(not state["stopped"], "ISSUE_47_MODEL_CHANNEL_STOPPED:" + ",".join(state["stopped"]))
        _need(request_digest not in state["requests"],
              "ISSUE_47_MODEL_REQUEST_ALREADY_CLAIMED_NO_REDRAW")
        # The ledger holds the approval's request list itself, so a claim for a
        # request no grant names is refused here too, whatever a caller passed.
        allowed = self.binding["request_digests_by_grant"]
        _need(bool(grants) and all(name in allowed and request_digest in allowed[name]
                                   for name in grants),
              "ISSUE_47_MODEL_REQUEST_DIGEST_NOT_GRANTED:" + str(request_digest))
        _need(state["counts"][0] + 1 <= self.binding["limits"][0]
              and state["counts"][1] + 1 <= self.binding["limits"][1],
              "ISSUE_47_MODEL_CUMULATIVE_LIMIT_REACHED:" + str(state["counts"]) + " of "
              + str(self.binding["limits"]))
        ordinal = len(state["rows"]) + 1
        path = self.root / "calls" / ("%04d" % ordinal)
        intent = _sealed({"record_type": "ISSUE_47_HISTORICAL_MODEL_CALL_INTENT",
                          "requirement_id": REQUIREMENT_ID, "ordinal": ordinal,
                          "execution_mode": self.mode,
                          "allowance_binding_id": self.binding["binding_id"],
                          "previous_intent_id": state["previous_intent_id"],
                          "request_digest": request_digest, "plan_id": plan_id,
                          "request_identity": request_identity, "purpose": purpose,
                          "grants": list(grants), "authority_files_hash": authority_files_hash,
                          "counts_before": state["counts"], "counts_claimed": [1, 1, 0],
                          "automatic_retry_count": 0, "production_authorized": False},
                         "intent_id")
        # The claim is logged before its slot exists, append-only and synced -
        # beside the root first, then inside it - so a removed slot, the last
        # one included, disagrees with the log, an emptied root disagrees with
        # the copy beside it, and a crash between any two writes refuses
        # before the next socket.
        line = canonical_json_bytes(value=intent).rstrip(b"\n") + b"\n"
        for log in (self.mirror_path(self.root), self.root / "claims.jsonl"):
            _append_synced(log, line)
        path.mkdir(parents=True, exist_ok=False)
        _write_once(path / "intent.json", intent)
        return path, intent

    def claimed_slot(self, *, path, intent):
        """True only for this ledger's last claim, open, for exactly this intent, under the lock."""
        if not (self._locked and type(intent) is dict and type(intent.get("ordinal")) is int):
            return False
        claims = self._claims()
        return (bool(claims) and claims[-1] == intent
                and Path(path) == self.root / "calls" / ("%04d" % intent["ordinal"])
                and (Path(path) / "intent.json").is_file() and _read(path, "intent.json") == intent
                and not (Path(path) / "terminal.json").exists())

    def finish(self, *, path, intent, execution, wire):
        """Seal the slot from the controller's own files, never the caller's labels."""
        _need(self._locked and path == self.root / "calls" / ("%04d" % intent["ordinal"])
              and _read(path, "intent.json") == intent, "ISSUE_47_MODEL_LEDGER_SLOT_CHANGED")
        found, journal, stop = _slot_evidence(path=path, intent=intent, live=self.live)
        _need(found == execution, "ISSUE_47_MODEL_NATIVE_TERMINAL_CHANGED")
        _need(wire is not None and journal == wire, "ISSUE_47_MODEL_WIRE_CHANGED")
        evidence = {p.relative_to(path).as_posix(): sha256_file(path=p)
                    for p in sorted(path.rglob("*")) if p.is_file()}
        terminal = _sealed({"record_type": "ISSUE_47_HISTORICAL_MODEL_CALL_TERMINAL",
                            "intent_id": intent["intent_id"], "status": execution["status"],
                            "stop_reason": stop, "counts": [1, 1, 0],
                            "counts_kind": ("ACTUAL_OR_UNKNOWN_CHARGED" if self.live
                                            else "RECORDED_TEST_SIMULATION"),
                            "execution_receipt_id": execution["execution_receipt_id"],
                            "evidence": evidence, "production_authorized": False}, "terminal_id")
        _write_once(path / "terminal.json", terminal)
        return terminal


def _append_synced(path, line):
    """Append one line to a log that may not be a symlink, and sync it before returning."""
    handle = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
    try:
        written = 0
        while written < len(line):
            count = os.write(handle, line[written:])
            _need(count > 0, "ISSUE_47_MODEL_LEDGER_CLAIM_WRITE_FAILED")
            written += count
        os.fsync(handle)
    finally:
        os.close(handle)


def _write_once(path, value):
    from .invocation_control import _exclusive_write_json
    _exclusive_write_json(path=path, value=value)


def _ledger(*, allowance, root, live):
    return HistoricalModelLedger(factory=_FACTORY, root=root,
                                 binding=ledger_binding(allowance, root=root, live=live), live=live)


def live_model_ledger():
    """The granted ledger, after the allowance, its wiring receipt and its published start are verified.

    The owner decided the calls run in the executor's cloud container, where
    gh is not installed; ``live_github_reader`` reads the same comment over the
    REST API there. The ledger lives in the container too, so before anything
    else the start must be the one published on issue 47
    (historical_ledger_start): a new container with an empty ledger meets a
    marker it cannot match.
    """
    from .historical_source_acquisition import live_github_reader
    reader = live_github_reader()
    allowance = model_allowance(repo_root=ROOT, delegation_reader=reader)
    verify_model_wiring(receipt_path=allowance["model_wiring_receipt_path"],
                        receipt_id=allowance["model_wiring_receipt_id"])
    require_published_model_start(allowance=allowance, reader=reader)
    return allowance, _ledger(allowance=allowance, root=Path(allowance["budget_root"]), live=True)


# ------------------------------------------------ a start that outlives the host
# The model ledger's names for the start shared with the SEC ledger: its own
# record type, refusal prefix and export index, so neither ledger's marker or
# export stands in for the other's.
MODEL_EXPORT_DIRECTORY = "evidence/issue47_model_calls"
MODEL_EXPORT_INDEX = "export.json"


def _model_ledger_paths(root):
    return (HistoricalModelLedger.anchor_path(root), HistoricalModelLedger.mirror_path(root))


def _model_start():
    from .historical_ledger_start import LedgerKind
    from .historical_source_acquisition import ISSUE_NUMBER, TRUSTED_REPOSITORY
    return LedgerKind(record_type="ISSUE_47_MODEL_LEDGER_START", prefix="ISSUE_47_MODEL_LEDGER",
                      title="Issue #47 model ledger", error=HistoricalModelCallError,
                      ledger_paths=_model_ledger_paths,
                      export_index=MODEL_EXPORT_DIRECTORY + "/" + MODEL_EXPORT_INDEX,
                      repository=TRUSTED_REPOSITORY, issue_number=ISSUE_NUMBER,
                      requirement_id=REQUIREMENT_ID)


def start_model_ledger(*, allowance, reader, now=None, checkout=None):
    """Start the model ledger here, once; see historical_ledger_start.start_ledger."""
    from .historical_ledger_start import start_ledger
    return start_ledger(_model_start(), allowance=allowance, reader=reader, now=now,
                        checkout=ROOT if checkout is None else checkout)


def require_published_model_start(*, allowance, reader):
    """The model ledger was started here and its start is on GitHub, or a named refusal."""
    from .historical_ledger_start import require_published_start
    return require_published_start(_model_start(), allowance=allowance, reader=reader)


def recorded_model_ledger(*, root, allowance):
    """Offline tests only: a recorded ledger in a root no allowance grants."""
    root = Path(root).resolve()
    granted = Path(str(allowance.get("budget_root") or "/nonexistent-granted-root"))
    _need(root != granted and granted not in root.parents and root not in granted.parents
          and root != ROOT and ROOT not in root.parents,
          "ISSUE_47_MODEL_TEST_CANNOT_USE_A_GRANTED_OR_CHECKOUT_LEDGER")
    return _ledger(allowance=allowance, root=root, live=False)


def verify_model_wiring(*, receipt_path, receipt_id):
    """The offline verification the live path requires, still true of this tree.

    The receipt is sealed by the verification harness in a tree where the
    registration patch is applied; every file it binds - this module, the
    egress module, the three patched boundary files, the harness and its
    tests - must be byte-identical here, so the live path cannot run on code
    other than the code that was verified. And it must be the receipt the
    approval names: a receipt re-sealed after a change, even one that passes,
    describes code nobody approved.
    """
    path = Path(ROOT) / receipt_path
    _need(path.is_file() and not path.is_symlink(),
          "ISSUE_47_MODEL_WIRING_RECEIPT_MISSING:" + receipt_path)
    receipt = strict_json_file(path=path)
    _need(_identity_holds(receipt, "receipt_id")
          and receipt.get("record_type") == "ISSUE_47_MODEL_EGRESS_OFFLINE_VERIFICATION"
          and receipt.get("requirement_id") == REQUIREMENT_ID
          and receipt.get("all_checks_passed") is True
          and receipt.get("calls") == {"provider": 0, "paid": 0, "sec": 0},
          "ISSUE_47_MODEL_WIRING_NOT_VERIFIED")
    _need(receipt["receipt_id"] == receipt_id, "ISSUE_47_MODEL_WIRING_RECEIPT_IS_NOT_THE_APPROVED_ONE")
    _need(set(CALL_PATH_FILES) <= set(receipt["bound_files"]),
          "ISSUE_47_MODEL_WIRING_DOES_NOT_BIND_THE_CALL_PATH")
    for relative, binding in sorted(receipt["bound_files"].items()):
        # A file the verified tree had and this one lacks - the egress module,
        # wherever the patch is not applied - is named, not a lookup error.
        _need((Path(ROOT) / relative).is_file(), "ISSUE_47_MODEL_WIRING_FILE_MISSING:" + relative)
        raw = resolve_repository_file(repo_root=ROOT, repo_relative_path=relative).read_bytes()
        _need({"sha256": sha256_bytes(content=raw), "size": len(raw)} == binding,
              "ISSUE_47_MODEL_WIRING_FILE_CHANGED:" + relative)
    return receipt
