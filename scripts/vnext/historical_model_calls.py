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

from .canonical import (canonical_json_bytes, content_hash, sha256_bytes, sha256_file,
                        strict_json_file, strict_json_loads)
from .normal_source_authority import ROOT
from .sources import resolve_repository_file

REQUIREMENT_ID = "issue_47_v1"
ALLOWANCE_PATH = "config/issue47_historical_model_calls_v1.json"
DELEGATION_TYPE = "ISSUE_47_HISTORICAL_MODEL_DELEGATION"
PURPOSE = "ISSUE47_HISTORICAL_SEMANTIC_ASSESSMENT"
REQUIRED_FIELDS = ("requirement_id", "repository", "approver_login", "delegation_url",
                   "delegation_body_sha256", "delegation_record_path", "budget_root",
                   "maximum_additional_provider_paid_sec_calls", "scope", "transport",
                   "retry_policy", "model_wiring_receipt_path")
RESTATED_BY_THE_COMMENT = ("maximum_additional_provider_paid_sec_calls", "budget_root",
                           "scope", "transport", "retry_policy")
SCOPE_FIELDS = ("purposes", "metric_ids", "company_ids", "earliest_report_end",
                "latest_report_end", "grants")
GRANT_FIELDS = ("grant", "metric_ids", "company_ids", "earliest_report_end",
                "latest_report_end")
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
LEDGER_TYPE = "ISSUE_47_HISTORICAL_MODEL_ALLOWANCE"
# The same stops as issue_28_v14's ledger: each is a terminal a later call must
# not be made after, because the count or the source can no longer be trusted.
STOPS = frozenset({"HTTP_402", "UNKNOWN_REMOTE_OUTCOME", "SOURCE_AUTHENTICITY_FAILED",
                   "USAGE_UNKNOWN", "CONTEXT_REFERENCE_MISMATCH"})
# Files a call executes that the Requirement's authority does not already list.
CALL_PATH_FILES = ("scripts/vnext/historical_model_calls.py",
                   "scripts/vnext/historical_model_egress.py")
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
        other = PurePosixPath(strict_json_file(path=sec)["budget_root"])
        mine = PurePosixPath(budget_root)
        _need(mine != other and other not in mine.parents and mine not in other.parents,
              "ISSUE_47_MODEL_LEDGER_OVERLAPS_THE_SEC_LEDGER:" + budget_root[:80])


def _typed(policy, *, repo_root):
    """Every field's shape, before anything downstream trusts its meaning."""
    from .ai_adapter import _DEEPSEEK_ENDPOINT_HOST, TransportPolicy
    from .historical_semantic_results import SUPPORTED_METRICS
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
    _need(len(names) == len(set(names)), "ISSUE_47_MODEL_GRANT_NAMES_REPEAT")
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
    from .historical_source_acquisition import _comment_url, _provenance
    path = Path(repo_root) / ALLOWANCE_PATH
    _need(path.is_file() and not path.is_symlink(),
          "ISSUE_47_MODEL_ALLOWANCE_NOT_GRANTED:" + ALLOWANCE_PATH + ":needs "
          + ",".join(REQUIRED_FIELDS))
    policy = json.loads(path.read_text(encoding="utf-8"))
    _need(type(policy) is dict, "ISSUE_47_MODEL_ALLOWANCE_MALFORMED")
    missing = [field for field in REQUIRED_FIELDS if field not in policy]
    _need(not missing, "ISSUE_47_MODEL_ALLOWANCE_INCOMPLETE:" + ",".join(missing))
    _typed(policy, repo_root=repo_root)
    record_path = Path(repo_root) / policy["delegation_record_path"]
    _need(record_path.is_file() and not record_path.is_symlink(),
          "ISSUE_47_MODEL_DELEGATION_RECORD_MISSING:" + policy["delegation_record_path"])
    comment = strict_json_file(path=record_path)
    _need(type(comment.get("body")) is str and comment["body"]
          and sha256_bytes(content=comment["body"].encode("utf-8"))
          == policy["delegation_body_sha256"], "ISSUE_47_MODEL_DELEGATION_BODY_DOES_NOT_MATCH")
    _provenance(comment=comment, policy=policy, where="saved_record")
    if delegation_reader is not None:
        number = _comment_url(repository=policy["repository"]).match(policy["delegation_url"])[1]
        fetched = delegation_reader("repos/" + policy["repository"] + "/issues/comments/" + number)
        _need(type(fetched) is dict, "ISSUE_47_MODEL_DELEGATION_FETCH_DID_NOT_RETURN_A_COMMENT")
        _provenance(comment=fetched, policy=policy, where="fetched")
        _need(fetched.get("body") == comment["body"],
              "ISSUE_47_MODEL_SAVED_DELEGATION_DIFFERS_FROM_GITHUB")
    try:
        approved = json.loads(comment["body"])
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


def request_in_scope(*, allowance, metric_id, company_id, report_end, purpose=PURPOSE):
    """The grants that cover this request whole; refuses when none does."""
    scope = allowance["scope"]
    _need(purpose in scope["purposes"], "ISSUE_47_MODEL_PURPOSE_NOT_IN_SCOPE:" + str(purpose))
    covering = sorted(grant["grant"] for grant in scope["grants"]
                      if metric_id in grant["metric_ids"] and company_id in grant["company_ids"]
                      and grant["earliest_report_end"] <= report_end <= grant["latest_report_end"])
    _need(bool(covering), "ISSUE_47_MODEL_REQUEST_OUTSIDE_EVERY_GRANT:" + metric_id + ":"
          + company_id + ":" + str(report_end))
    return covering


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
    """The three decision hashes an issue_47_v1 plan carries, from the allowance."""
    return {"provider_transport_decision_hash": content_hash(value=allowance["transport"]),
            "transport_retry_decision_hash": content_hash(value=allowance["retry_policy"]),
            "live_call_bound_decision_hash": content_hash(value={
                "delegation_url": allowance["delegation_url"],
                "delegation_body_sha256": allowance["delegation_body_sha256"],
                "limits": allowance["maximum_additional_provider_paid_sec_calls"],
                "scope": allowance["scope"]})}


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

        The source was built from the pinned filing when the request was
        prepared, and it is content-addressed; here its identity is recomputed,
        every unit's bytes re-hashed, every saved file it was read from
        re-proved, and the request required to be one the source partitions
        into - the checks issue_28_v14's request makes at the same points, not
        a second parse of the filing at each of them.

        Returns:
            (request, admission): the request mapping and the source-proof
            admission of the saved files now.
        """
        from .continuous_semantic_calls import request_body, validate_source_unit_bytes
        from .historical_semantic_results import pinned_requests
        from .ordinary_source_authority import verify_ordinary_source_proofs
        from git_workspace import first_symlink_in_path
        _need(self._factory is _FACTORY, "ISSUE_47_MODEL_REQUEST_FACTORY_REQUIRED")
        _authority_is_issue_47(self.authority, self.allowance)
        _need(first_symlink_in_path(path=Path(self.data_root)) is None,
              "ISSUE_47_MODEL_SOURCE_ROOT_ALIAS")
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


def prepare_historical_requests(*, company_id, metric_id, period_selection, authority,
                                allowance, data_root: Path = ROOT):
    """Every request a pinned period's source partitions into, each bound to #47's authority.

    ``authority`` is the controller's ``issue_47_v1`` authority, which exists
    only where the registration patch is applied; elsewhere the controller
    refuses to make one and nothing below is reachable.
    """
    from .continuous_semantic_calls import request_body
    from .historical_semantic_results import (SUPPORTED_METRICS, pinned_native_source,
                                              pinned_requests)
    from .native_unit_index import evidence_json_bytes
    _need(metric_id in SUPPORTED_METRICS, "ISSUE_47_MODEL_METRIC_NOT_WIRED:" + metric_id)
    _authority_is_issue_47(authority, allowance)
    policy = transport_policy(allowance=allowance, repo_root=ROOT)
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


def transport_payload(*, request, policy):
    """What the adapter's scoped-payload hook returns for #47's request type.

    Only ``ai_adapter._scoped_transport_payload`` calls this (registration
    patch), immediately before it builds the socket request. The request is
    rebuilt from the saved filing first, so bytes that no longer rebuild never
    reach the wire.
    """
    _need(type(request) is HistoricalSemanticRequest, "ISSUE_47_MODEL_REQUEST_TYPE_REQUIRED")
    request.validate(policy)
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


class HistoricalModelLedger:
    """#47's cumulative provider and paid count, with a process lock over its root.

    One claim is one provider call and one paid call, written before the socket
    and never removed, so a failure counts. A request is claimed at most once:
    an unchanged request is not redrawn. A slot with no terminal may have
    reached the endpoint, so it counts in full and stops the channel until an
    owner reconciles it; so does any terminal whose stop reason is in STOPS.
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

    @contextmanager
    def locked(self):
        self.root.mkdir(parents=True, exist_ok=True)
        handle = os.open(str(self.root / ".lock"), os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(handle, fcntl.LOCK_EX)
            self._locked = True
            yield self
        finally:
            self._locked = False
            fcntl.flock(handle, fcntl.LOCK_UN)
            os.close(handle)

    def snapshot(self):
        """Counts, stops and claimed requests, re-read from every slot."""
        calls = self.root / "calls"
        slots = sorted(calls.iterdir()) if calls.is_dir() else []
        counts, stopped, requests, rows = [0, 0, 0], [], set(), []
        for ordinal, slot in enumerate(slots, start=1):
            _need(slot.name == "%04d" % ordinal, "ISSUE_47_MODEL_LEDGER_SLOT_SEQUENCE_CHANGED")
            intent = _read(slot, "intent.json")
            _need(_identity_holds(intent, "intent_id") and intent["ordinal"] == ordinal
                  and intent["requirement_id"] == REQUIREMENT_ID
                  and intent["allowance_binding_id"] == self.binding["binding_id"]
                  and intent["execution_mode"] == self.mode,
                  "ISSUE_47_MODEL_LEDGER_SLOT_CHANGED:" + slot.name)
            _need(intent["request_digest"] not in requests,
                  "ISSUE_47_MODEL_LEDGER_REQUEST_CLAIMED_TWICE:" + slot.name)
            requests.add(intent["request_digest"])
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
            if terminal["stop_reason"]:
                _need(terminal["stop_reason"] in STOPS, "ISSUE_47_MODEL_LEDGER_STOP_REASON_INVALID")
                stopped.append(slot.name + "=" + terminal["stop_reason"])
            rows.append({"ordinal": ordinal, "status": terminal["status"]})
        _need(all(a <= b for a, b in zip(counts, self.binding["limits"])),
              "ISSUE_47_MODEL_LEDGER_COUNT_EXCEEDS_THE_ALLOWANCE")
        return {"counts": counts, "limits": list(self.binding["limits"]), "stopped": stopped,
                "requests": sorted(requests), "rows": rows}

    def claim(self, *, request_digest, plan_id, purpose, grants, request_identity,
              authority_files_hash):
        """Write the counted intent before any socket; refuses when a stop or limit holds."""
        _need(self._locked, "ISSUE_47_MODEL_LEDGER_LOCK_REQUIRED")
        _need(purpose in self.binding["purposes"], "ISSUE_47_MODEL_PURPOSE_NOT_IN_ALLOWANCE")
        state = self.snapshot()
        _need(not state["stopped"], "ISSUE_47_MODEL_CHANNEL_STOPPED:" + ",".join(state["stopped"]))
        _need(request_digest not in state["requests"],
              "ISSUE_47_MODEL_REQUEST_ALREADY_CLAIMED_NO_REDRAW")
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
                          "request_digest": request_digest, "plan_id": plan_id,
                          "request_identity": request_identity, "purpose": purpose,
                          "grants": list(grants), "authority_files_hash": authority_files_hash,
                          "counts_before": state["counts"], "counts_claimed": [1, 1, 0],
                          "automatic_retry_count": 0, "production_authorized": False},
                         "intent_id")
        path.mkdir(parents=True, exist_ok=False)
        _write_once(path / "intent.json", intent)
        return path, intent

    def finish(self, *, path, intent, execution, wire):
        """Seal the slot from the controller's own files, never the caller's labels."""
        _need(self._locked and path == self.root / "calls" / ("%04d" % intent["ordinal"])
              and _read(path, "intent.json") == intent, "ISSUE_47_MODEL_LEDGER_SLOT_CHANGED")
        identity = execution["execution_id"].split(":", 1)[1]
        _need(_read(path, "invocation_control/executions/" + identity + ".json") == execution
              and _identity_holds(execution, "execution_receipt_id"),
              "ISSUE_47_MODEL_NATIVE_TERMINAL_CHANGED")
        marker = _read(path, "invocation_control/egress/" + identity + "/01.json")
        _need(_identity_holds(marker, "egress_marker_id")
              and marker["ai_invocation_plan_id"] == intent["plan_id"]
              and marker["execution_id"] == execution["execution_id"]
              and marker["attempt_ordinal"] == 1
              and marker["transport_kind"] == ("REAL_MODEL_PROVIDER" if self.live else "MOCK"),
              "ISSUE_47_MODEL_NATIVE_MARKER_CHANGED")
        _need(execution["counters"] == {"real_model_provider_egress_count": int(self.live),
                                        "paid_model_provider_call_count": int(self.live),
                                        "mock_transport_invocation_count": int(not self.live)},
              "ISSUE_47_MODEL_NATIVE_COUNT_CHANGED")
        _need(wire is not None and _read(path, "wire/journal.json") == wire,
              "ISSUE_47_MODEL_WIRE_CHANGED")
        stop = wire["error_class"] if wire["error_class"] in STOPS else ""
        if execution["status"] == "UNKNOWN_REMOTE_OUTCOME":
            stop = "UNKNOWN_REMOTE_OUTCOME"
        if wire["usage"]["input_tokens"] is None or wire["usage"]["output_tokens"] is None:
            stop = stop or "USAGE_UNKNOWN"
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


def _write_once(path, value):
    from .invocation_control import _exclusive_write_json
    _exclusive_write_json(path=path, value=value)


def _ledger(*, allowance, root, live):
    binding = _sealed({"record_type": LEDGER_TYPE, "requirement_id": REQUIREMENT_ID,
                       "root": str(root),
                       "limits": list(allowance["maximum_additional_provider_paid_sec_calls"]),
                       "purposes": list(allowance["scope"]["purposes"]),
                       "delegation_url": allowance["delegation_url"],
                       "delegation_body_sha256": allowance["delegation_body_sha256"],
                       "execution_mode": "LIVE" if live else "RECORDED_TEST_ONLY"}, "binding_id")
    return HistoricalModelLedger(factory=_FACTORY, root=root, binding=binding, live=live)


def live_model_ledger():
    """The granted ledger, after the allowance and its offline wiring receipt are verified."""
    from .historical_source_acquisition import github_comment_reader
    allowance = model_allowance(repo_root=ROOT, delegation_reader=github_comment_reader)
    verify_model_wiring(receipt_path=allowance["model_wiring_receipt_path"])
    return allowance, _ledger(allowance=allowance, root=Path(allowance["budget_root"]), live=True)


def recorded_model_ledger(*, root, allowance):
    """Offline tests only: a recorded ledger in a root no allowance grants."""
    root = Path(root).resolve()
    granted = Path(str(allowance.get("budget_root") or "/nonexistent-granted-root"))
    _need(root != granted and granted not in root.parents and root not in granted.parents
          and root != ROOT and ROOT not in root.parents,
          "ISSUE_47_MODEL_TEST_CANNOT_USE_A_GRANTED_OR_CHECKOUT_LEDGER")
    return _ledger(allowance=allowance, root=root, live=False)


def verify_model_wiring(*, receipt_path):
    """The offline verification the live path requires, still true of this tree.

    The receipt is sealed by the verification harness in a tree where the
    registration patch is applied; every file it binds - this module, the
    egress module, the three patched boundary files, the harness and its
    tests - must be byte-identical here, so the live path cannot run on code
    other than the code that was verified.
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
