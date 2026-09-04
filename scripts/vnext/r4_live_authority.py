"""Dormant R4 plan and exact-head authorization, independent of offline credit.

Private process capabilities prevent raw plan/receipt dictionaries reaching a
socket. Captured owner comments are governance evidence, not cryptographic
attestation of GitHub or a same-process hostile-code sandbox. Production uses
the fixed repository and rechecks every frozen input immediately before egress.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
from typing import Mapping

from .canonical import canonical_json_bytes, content_hash, parse_utc_timestamp
from .canonical import sha256_bytes, strict_json_loads
from .records import EXPLICIT_ARTIFACT_GENERATION
from .sources import resolve_repository_file


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
REQUIREMENT_ID = "issue_28_v2"
RUNTIME_ROOT = "artifacts/vnext/qualification/r4_scoped"
_PLAN_FACTORY = object()
_AUTH_FACTORY = object()
_OWNER_CAPTURE_FACTORY = object()
_GIT_OID = re.compile(r"[0-9a-f]{40}")
_CONTENT_ID = re.compile(r"sha256:[0-9a-f]{64}")
IDENTITY_FIELDS = ("artifact_requirement_generation", "requirement_id",
                   "requirement_closure_hash", "requirement_hashes")
REQUEST_BINDING_FIELDS = (
    *IDENTITY_FIELDS, "fixture_id", "source_scope_manifest_id", "task_contract_id",
    "task_contract_hash", "full_derived_asset_id", "full_reader_input_manifest_id",
    "reader_payload_sha256", "provider_request_body_sha256", "live_scoped_reader_request_id",
    "fixture_company_authority_id", "target_period", "target_period_identity",
)
PENDING_FIELDS = {
    "record_type", "schema_version", "pending_plan_id", *IDENTITY_FIELDS,
    "execution_mode", "ratchet_id", "plan_state", "owner_authorization",
    "provider_paid_sec_authorized", "qualification_credit", "publication_credit",
    "response_reuse_authorized", "implementation_head", "implementation_tree",
    "implementation_authority", "schedule_input_id", "fixture_matrix_id",
    "corpus_binding", "active_predecessor", "entries", "zero_call_fixtures",
    "call_bounds", "counts", "stability_selection",
}
OWNER_RECEIPT_FIELDS = {
    "record_type", "schema_version", "receipt_id", *IDENTITY_FIELDS,
    "exact_head", "exact_tree", "pending_plan_id", "authorized_entry_ids",
    "owner", "approved_at_utc", "source_url", "approval_text", "approval_text_sha256",
    "authorization_scope", "provider_calls_authorized", "paid_model_calls_authorized",
    "sec_calls_authorized", "automatic_retry_count", "response_reuse_authorized",
}
AUTHORIZATION_BINDING_FIELDS = {
    "record_type", "schema_version", "authorization_id", *IDENTITY_FIELDS,
    "execution_mode", "pending_plan_id", "entry_id", "fixture_id", "fixture_execution_ordinal",
    "plan_ordinal", "exact_head", "exact_tree", "owner_receipt_id", "owner_token_hash",
    "authorized_at_utc", "invocation_namespace", "context_limit_tokens", "automatic_retry_count",
    "response_reuse_authorized", "sec_calls_authorized", "qualification_credit", "publication_credit",
    "request_identity", "pending_plan", "owner_receipt",
}


class R4AuthorizationError(ValueError):
    """Reject absent, relabelled, stale or unsafe R4 execution authority."""


def _plain(value):
    return strict_json_loads(text=canonical_json_bytes(value=value).decode("utf-8"))


def _exact(value, fields, label):
    if type(value) is not dict or set(value) != set(fields):
        raise R4AuthorizationError(label + " fields are not exact")


def _self_id(value, key):
    if (type(value.get(key)) is not str or not _CONTENT_ID.fullmatch(value[key])
            or value[key] != content_hash(value={k: v for k, v in value.items() if k != key})):
        raise R4AuthorizationError("R4 content identity differs: " + key)


def _git_state(*, repo_root: Path, clean: bool) -> dict:
    from git_workspace import git_checkout_metadata_error, sanitized_git_environment
    error = git_checkout_metadata_error(repo_root=repo_root)
    if error:
        raise R4AuthorizationError(error)
    def git(*args):
        result = subprocess.run(["git", *args], cwd=repo_root, check=False,
            env=sanitized_git_environment(), text=True, capture_output=True)
        if result.returncode:
            raise R4AuthorizationError("R4 repository Git identity is unavailable")
        return result.stdout.strip()
    if Path(git("rev-parse", "--show-toplevel")).resolve() != repo_root.resolve():
        raise R4AuthorizationError("R4 Git toplevel differs")
    head, tree = git("rev-parse", "HEAD"), git("rev-parse", "HEAD^{tree}")
    if not _GIT_OID.fullmatch(head) or not _GIT_OID.fullmatch(tree):
        raise R4AuthorizationError("R4 Git head/tree is malformed")
    if clean and git("status", "--porcelain=v1", "--untracked-files=all"):
        raise R4AuthorizationError("R4 live authorization requires a clean committed checkout")
    return {"head": head, "tree": tree}


def _validate_live_implementation(*, repo_root, plan):
    """Permit PR-C evidence commits, never arbitrary or changed Python ancestry."""
    from git_workspace import sanitized_git_environment
    state = _git_state(repo_root=repo_root, clean=True)
    head, tree = plan["implementation_head"], plan["implementation_tree"]
    def run(*args):
        return subprocess.run(["git", *args], cwd=repo_root, text=True, capture_output=True,
                              env=sanitized_git_environment(), check=False)
    observed = run("rev-parse", "--verify", head + "^{tree}")
    ancestor = run("merge-base", "--is-ancestor", head, state["head"])
    changed = run("diff", "--name-only", head, state["head"], "--", "scripts", "tools")
    if (observed.returncode or observed.stdout.strip() != tree or ancestor.returncode
            or changed.returncode or any(name.endswith(".py") for name in changed.stdout.splitlines())):
        raise R4AuthorizationError("Pending plan does not name the unchanged reviewed implementation ancestor")
    return state


def _pointer(*, repo_root, requirement):
    path = resolve_repository_file(repo_root=repo_root,
        repo_relative_path="outputs/active_publication.json")
    data = path.read_bytes()
    pointer = strict_json_loads(text=data.decode("utf-8"))
    policy = requirement["effective_decisions"]["S-PUBLICATION-PREDECESSOR"]["choice"]
    if (pointer.get("publication_id") != policy["required_predecessor"]
            or policy["failure_active_publication"] != pointer["publication_id"]):
        raise R4AuthorizationError("R4 requires the exact active R3 predecessor")
    return {"path": "outputs/active_publication.json", "sha256": sha256_bytes(content=data),
        "size": len(data), "publication_id": pointer["publication_id"],
        "previous_publication_id": pointer["previous_publication_id"],
        "bundle_manifest_sha256": pointer["bundle_manifest_sha256"]}


def _verified_predecessor(*, repo_root, requirement):
    """Open R3/R2/R1 once, then pin all verified bytes for cheap later checks."""
    from .publication import PublicationView, verify_publication_bundle, ROOT_MIRROR_RELATIVE_PATHS
    view = PublicationView.open(publication_root=repo_root)
    pointer = _pointer(repo_root=repo_root, requirement=requirement)
    if (view.publication_id != pointer["publication_id"]
            or view.manifest["previous_publication_id"] != pointer["previous_publication_id"]):
        raise R4AuthorizationError("Verified R3 predecessor edge differs from active pointer")
    files, chain = {}, []
    current = view
    for ordinal in range(3):
        relative_dir = current.bundle_dir.relative_to(repo_root).as_posix()
        manifest_relative = relative_dir + "/publication_manifest.json"
        data = resolve_repository_file(repo_root=repo_root, repo_relative_path=manifest_relative).read_bytes()
        files[manifest_relative] = {"sha256": sha256_bytes(content=data), "size": len(data)}
        for entry in current.manifest["files"]:
            files[relative_dir + "/" + entry["path"]] = {"sha256": entry["sha256"], "size": entry["size"]}
        chain.append({"publication_id": current.publication_id,
            "previous_publication_id": current.manifest["previous_publication_id"],
            "manifest": {"path": manifest_relative, **files[manifest_relative]}})
        if ordinal < 2:
            identity = current.manifest["previous_publication_id"]
            directory = repo_root / "outputs/publications" / identity
            current = PublicationView(publication_id=identity, bundle_dir=directory,
                manifest=verify_publication_bundle(bundle_dir=directory))
    for relative, mirror in ROOT_MIRROR_RELATIVE_PATHS.items():
        data = resolve_repository_file(repo_root=repo_root, repo_relative_path=mirror).read_bytes()
        if data != view.read_bytes(relative_path=relative):
            raise R4AuthorizationError("R3 public/root mirror differs: " + mirror)
        files[mirror] = {"sha256": sha256_bytes(content=data), "size": len(data)}
    index_path = "outputs/ratchet_release_receipts/r3/index.json"
    data = resolve_repository_file(repo_root=repo_root, repo_relative_path=index_path).read_bytes()
    index = strict_json_loads(text=data.decode("utf-8"))
    _self_id(index, "receipt_index_id")
    if index.get("status") != "PASSED" or set(index.get("receipts", {})) != {
            "active_terminal", "immutable_read_back", "predecessor_r2", "successor_publication"}:
        raise R4AuthorizationError("R3 receipt index is not the passed exact set")
    files[index_path] = {"sha256": sha256_bytes(content=data), "size": len(data)}
    for entry in index["receipts"].values():
        files[entry["path"]] = {key: entry[key] for key in ("sha256", "size")}
    return pointer, files, {"chain": chain, "receipt_index_id": index["receipt_index_id"],
        "verified_files_hash": content_hash(value=files), "root_mirror_count": len(ROOT_MIRROR_RELATIVE_PATHS)}


class R4ExecutionPlanContext:
    """One immutable source session; a plan context never permits egress."""

    __slots__ = ("_factory", "_root", "_session", "_schedule", "_requests", "_pointer", "_state",
                 "_historical_files", "_historical_proof", "_terminal_pins")

    def __init__(self, *, factory, root, session, schedule, requests, pointer, state,
                 historical_files, historical_proof):
        if factory is not _PLAN_FACTORY:
            raise R4AuthorizationError("R4 plan context requires its repository factory")
        self._factory, self._root, self._session = factory, root, session
        self._schedule = canonical_json_bytes(value=schedule)
        self._requests, self._pointer, self._state = requests, _plain(pointer), _plain(state)
        self._historical_files = canonical_json_bytes(value=historical_files)
        self._historical_proof = _plain(historical_proof)
        self._terminal_pins = {}

    def _check(self):
        if self._factory is not _PLAN_FACTORY:
            raise R4AuthorizationError("R4 plan context factory differs")
        self._session._check()
        if _pointer(repo_root=self._root, requirement=self._session._requirement) != self._pointer:
            raise R4AuthorizationError("Active R3 pointer changed during R4 execution")
        from .live_scoped_reader import _check_files
        _check_files(repo_root=self._root, bindings=strict_json_loads(
            text=self._historical_files.decode("utf-8")))
        # Full asset construction belongs to the source session, not each child.
        for request in self._requests.values():
            _check_files(repo_root=self._root, bindings=request.identity["file_bindings"])


def prepare_r4_execution_context(*, repo_root: Path, session=None) -> R4ExecutionPlanContext:
    """Rebuild nine unique requests from certified source bytes, offline only."""
    from .live_scoped_reader import LiveScopedReaderSession, prepare_live_scoped_reader_session
    from .live_scoped_reader import prepare_live_scoped_reader_request
    from .r4_live_plan import _derive_r4_repository_schedule_from_requirement
    root = repo_root.resolve(strict=True)
    if session is None:
        session = prepare_live_scoped_reader_session(repo_root=root, requirement_id=REQUIREMENT_ID)
    if (type(session) is not LiveScopedReaderSession or session._root != root
            or session._requirement["requirement_id"] != REQUIREMENT_ID):
        raise R4AuthorizationError("R4 execution source session differs")
    schedule = _derive_r4_repository_schedule_from_requirement(
        repo_root=root, requirement=session._requirement,
        company_authority=strict_json_loads(text=session._company_authority_bytes.decode("utf-8")))
    requests = {}
    for entry in schedule["entries"]:
        fixture = entry["fixture_id"]
        if fixture not in requests:
            requests[fixture] = prepare_live_scoped_reader_request(
                repo_root=root, fixture_id=fixture, session=session)
    if len(requests) != 9 or len(schedule["entries"]) != 12:
        raise R4AuthorizationError("R4 exact base/stability call set differs")
    # A copied release workspace may replay recorded data without borrowed Git.
    state = _git_state(repo_root=root, clean=False) if (root / ".git").exists() else {
        "head": None, "tree": None}
    pointer, historical_files, historical_proof = _verified_predecessor(
        repo_root=root, requirement=session._requirement)
    context = R4ExecutionPlanContext(factory=_PLAN_FACTORY, root=root, session=session,
        schedule=schedule, requests=requests, pointer=pointer, state=state,
        historical_files=historical_files, historical_proof=historical_proof)
    context._check()
    return context


def _build_plan(context, *, mode, state):
    if type(context) is not R4ExecutionPlanContext or mode not in {"LIVE", "RECORDED_TEST"}:
        raise R4AuthorizationError("R4 plan requires an exact repository context/mode")
    context._check()
    schedule = strict_json_loads(text=context._schedule.decode("utf-8"))
    entries = []
    for planned in schedule["entries"]:
        request = context._requests[planned["fixture_id"]].identity
        for key in ("source_scope_manifest_id", "task_contract_hash", "full_derived_asset_id",
                    "full_reader_input_manifest_id", "requirement_closure_hash"):
            if planned["scope_certificate_identity"][key] != request[key]:
                raise R4AuthorizationError("Live request differs from certified draft scope")
        subject = planned["fixture_subject_identity"]
        if (subject["fixture_company_authority_id"] != request["fixture_company_authority_id"]
                or planned["target_period"] != request["target_period"]
                or any(subject[key] != request["source_metadata"][key] for key in ("company_id", "cik"))):
            raise R4AuthorizationError("Live request subject/period differs from certified plan")
        row = {"ordinal": planned["ordinal"], "fixture_id": planned["fixture_id"],
            "metric_id": planned["metric_id"], "fixture_class": planned["fixture_class"],
            "fixture_execution_ordinal": planned["fixture_execution_ordinal"],
            "phase": planned["phase"], "repeats_base_ordinal": planned["repeats_base_ordinal"],
            "risk_features": planned["risk_features"], "selection_reason": planned["selection_reason"],
            "fresh_response_required": True, "response_reuse_authorized": False,
            **{key: planned[key] for key in ("fixture_subject_identity", "target_period", "target_period_identity")},
            "request_identity": {key: request[key] for key in REQUEST_BINDING_FIELDS}}
        entries.append({**row, "entry_id": content_hash(value=row)})
    body = {"record_type": "R4_PENDING_LIVE_PLAN" if mode == "LIVE" else "R4_RECORDED_TEST_PLAN",
        "schema_version": 1, **{key: schedule[key] for key in IDENTITY_FIELDS},
        "execution_mode": mode, "ratchet_id": "R4", "plan_state": "PENDING_OWNER_AUTHORIZATION"
        if mode == "LIVE" else "RECORDED_TEST_ONLY", "owner_authorization": "NOT_ISSUED",
        "provider_paid_sec_authorized": False, "qualification_credit": "NONE_PLAN_ONLY",
        "publication_credit": "NONE", "response_reuse_authorized": False,
        "implementation_head": state["head"], "implementation_tree": state["tree"],
        "implementation_authority": context._session._requirement["execution_authority"],
        "schedule_input_id": schedule["schedule_input_id"],
        **{key: schedule[key] for key in ("fixture_matrix_id", "corpus_binding", "zero_call_fixtures",
                                        "call_bounds", "counts", "stability_selection")},
        "active_predecessor": {**context._pointer, "immutable_read_back": context._historical_proof},
        "entries": entries}
    return {**body, "pending_plan_id": content_hash(value=body)}


def build_r4_pending_live_plan(*, repo_root: Path, context=None):
    """PR-C factory, still blocked until a separate exact-head owner receipt."""
    if repo_root.resolve() != REPOSITORY_ROOT.resolve():
        raise R4AuthorizationError("Pending live plan requires the implementation repository")
    state = _git_state(repo_root=repo_root, clean=True)
    if context is None:
        context = prepare_r4_execution_context(repo_root=repo_root)
    if type(context) is not R4ExecutionPlanContext or context._root != repo_root.resolve():
        raise R4AuthorizationError("Pending live plan context belongs to another repository")
    return _build_plan(context, mode="LIVE", state=state)


def build_r4_recorded_test_plan(*, context: R4ExecutionPlanContext):
    """Explicit non-egress subtype; cannot be converted by deleting a field."""
    return _build_plan(context, mode="RECORDED_TEST", state=context._state)


def validate_r4_execution_plan(*, plan, context, expected_plan_id, mode):
    _exact(plan, PENDING_FIELDS, "R4 execution plan")
    _self_id(plan, "pending_plan_id")
    if plan["pending_plan_id"] != expected_plan_id or plan["execution_mode"] != mode:
        raise R4AuthorizationError("R4 plan ID or execution generation differs")
    state = {"head": plan["implementation_head"], "tree": plan["implementation_tree"]}
    if mode == "LIVE" and (not _GIT_OID.fullmatch(str(state["head"]))
                            or not _GIT_OID.fullmatch(str(state["tree"]))):
        raise R4AuthorizationError("Pending live plan implementation head/tree is absent")
    if plan != _build_plan(context, mode=mode, state=state):
        raise R4AuthorizationError("R4 plan membership/order/request/call count differs")
    return _plain(plan)


def expected_r4_owner_approval(*, plan, exact_head, exact_tree):
    """Return the PR-C review format, not an approval or live grant."""
    return {"decision": "AUTHORIZE_R4_LIVE_EXACT_HEAD", "scope": "R4_LIVE_QUALIFICATION_ONLY",
        "exact_head": exact_head, "exact_tree": exact_tree,
        "requirement_id": plan["requirement_id"],
        "requirement_closure_hash": plan["requirement_closure_hash"],
        "pending_plan_id": plan["pending_plan_id"],
        "authorized_entry_ids": [entry["entry_id"] for entry in plan["entries"]],
        "provider_calls_authorized": True, "paid_model_calls_authorized": True,
        "sec_calls_authorized": False, "maximum_provider_calls": 12,
        "automatic_retry_count": 0, "response_reuse_authorized": False,
        "publication_authorized": False}


def validate_r4_live_authorization_receipt(*, receipt, plan, requirement, exact_head, exact_tree):
    """Pure replay validation only; a dictionary can never issue a live capability."""
    _exact(receipt, OWNER_RECEIPT_FIELDS, "R4 owner live receipt")
    _self_id(receipt, "receipt_id")
    repository = requirement["baseline"]["repository"]["identity"]
    owner = "github:" + repository.split("/", maxsplit=1)[0]
    if (plan.get("record_type") != "R4_PENDING_LIVE_PLAN" or plan.get("execution_mode") != "LIVE"
            or receipt["record_type"] != "R4_EXACT_HEAD_LIVE_AUTHORIZATION"
            or type(receipt["schema_version"]) is not int or receipt["schema_version"] != 1
            or not _GIT_OID.fullmatch(str(exact_head)) or not _GIT_OID.fullmatch(str(exact_tree))
            or receipt["exact_head"] != exact_head or receipt["exact_tree"] != exact_tree
            or receipt["owner"] != owner or any(receipt[key] != plan[key] for key in IDENTITY_FIELDS)
            or receipt["requirement_hashes"] != requirement["hashes"]
            or receipt["requirement_id"] != REQUIREMENT_ID
            or receipt["requirement_closure_hash"] != requirement["requirement_closure_hash"]
            or receipt["pending_plan_id"] != plan["pending_plan_id"]
            or receipt["authorized_entry_ids"] != [e["entry_id"] for e in plan["entries"]]
            or receipt["authorization_scope"] != "R4_LIVE_QUALIFICATION_ONLY"
            or receipt["provider_calls_authorized"] is not True
            or receipt["paid_model_calls_authorized"] is not True
            or receipt["sec_calls_authorized"] is not False
            or type(receipt["automatic_retry_count"]) is not int or receipt["automatic_retry_count"] != 0
            or receipt["response_reuse_authorized"] is not False
            or re.fullmatch(r"https://github\.com/" + re.escape(repository)
                            + r"/pull/[1-9][0-9]*#issuecomment-[1-9][0-9]*", str(receipt["source_url"])) is None):
        raise R4AuthorizationError("R4 owner live authorization is missing, forged or not exact-head")
    parse_utc_timestamp(value=receipt["approved_at_utc"])
    text = receipt["approval_text"]
    if (type(text) is not str or receipt["approval_text_sha256"] != sha256_bytes(content=text.encode("utf-8"))
            or strict_json_loads(text=text) != expected_r4_owner_approval(
                plan=plan, exact_head=exact_head, exact_tree=exact_tree)):
        raise R4AuthorizationError("R4 owner approval content differs from the exact plan")
    return _plain(receipt)


@dataclass(frozen=True, init=False)
class VerifiedR4OwnerComment:
    """A real owner-comment preflight, not caller-authored provenance fields."""

    _factory: object
    _root: Path
    _receipt_bytes: bytes
    _github_capture_bytes: bytes

    def __init__(self, *, factory, root, receipt, capture):
        if factory is not _OWNER_CAPTURE_FACTORY:
            raise R4AuthorizationError("Verified owner comment requires repository preflight")
        object.__setattr__(self, "_factory", factory)
        object.__setattr__(self, "_root", root)
        object.__setattr__(self, "_receipt_bytes", canonical_json_bytes(value=receipt))
        object.__setattr__(self, "_github_capture_bytes", canonical_json_bytes(value=capture))

    @property
    def receipt(self):
        return strict_json_loads(text=self._receipt_bytes.decode("utf-8"))


def verify_r4_live_owner_comment(*, context, plan, source_url: str) -> VerifiedR4OwnerComment:
    """Future explicit PR-C governance preflight; never invoked by PR-B tests.

    Fetch the real GitHub comment and open PR head exactly once, before any
    invocation or socket. Persisting/reloading the resulting receipt is useful
    for replay but does not reconstruct this private capability. A new live
    process performs the preflight again; socket-adjacent checks use its pinned
    bytes without querying GitHub.
    """
    if type(context) is not R4ExecutionPlanContext or context._root != REPOSITORY_ROOT.resolve():
        raise R4AuthorizationError("Owner preflight requires the implementation repository")
    validate_r4_execution_plan(plan=plan, context=context,
        expected_plan_id=plan.get("pending_plan_id"), mode="LIVE")
    requirement = context._session._requirement
    repository = requirement["baseline"]["repository"]["identity"]
    match = re.fullmatch(r"https://github\.com/" + re.escape(repository)
        + r"/pull/([1-9][0-9]*)#issuecomment-([1-9][0-9]*)", source_url)
    if match is None:
        raise R4AuthorizationError("Owner preflight requires an exact PR comment URL")
    state = _validate_live_implementation(repo_root=context._root, plan=plan)

    def github(path):
        result = subprocess.run(["gh", "api", "--hostname", "github.com", path],
            cwd=context._root, text=True, capture_output=True, check=False)
        if result.returncode:
            raise R4AuthorizationError("Owner GitHub provenance could not be verified")
        return strict_json_loads(text=result.stdout)

    comment = github("repos/" + repository + "/issues/comments/" + match.group(2))
    pull = github("repos/" + repository + "/pulls/" + match.group(1))
    if (type(comment) is not dict or comment.get("html_url") != source_url
            or str(comment.get("id")) != match.group(2)
            or comment.get("user", {}).get("login") != repository.split("/")[0]
            or type(comment.get("body")) is not str
            or pull.get("state") != "open" or pull.get("merged") is not False
            or pull.get("head", {}).get("sha") != state["head"]
            or pull.get("head", {}).get("repo", {}).get("full_name") != repository
            or pull.get("base", {}).get("ref") != "main"):
        raise R4AuthorizationError("Owner GitHub comment/author/open exact-head PR differs")
    # Reject an edited approval; the owner can issue a new exact-head comment.
    if comment.get("updated_at") != comment.get("created_at"):
        raise R4AuthorizationError("Edited owner approval requires a new immutable comment")
    text = comment["body"]
    receipt = {"record_type": "R4_EXACT_HEAD_LIVE_AUTHORIZATION", "schema_version": 1,
        **{key: plan[key] for key in IDENTITY_FIELDS}, "exact_head": state["head"],
        "exact_tree": state["tree"], "pending_plan_id": plan["pending_plan_id"],
        "authorized_entry_ids": [entry["entry_id"] for entry in plan["entries"]],
        "owner": "github:" + comment["user"]["login"], "approved_at_utc": comment["created_at"],
        "source_url": source_url, "approval_text": text,
        "approval_text_sha256": sha256_bytes(content=text.encode("utf-8")),
        "authorization_scope": "R4_LIVE_QUALIFICATION_ONLY", "provider_calls_authorized": True,
        "paid_model_calls_authorized": True, "sec_calls_authorized": False,
        "automatic_retry_count": 0, "response_reuse_authorized": False}
    receipt["receipt_id"] = content_hash(value=receipt)
    validate_r4_live_authorization_receipt(receipt=receipt, plan=plan, requirement=requirement,
        exact_head=state["head"], exact_tree=state["tree"])
    if _git_state(repo_root=context._root, clean=True) != state:
        raise R4AuthorizationError("R4 execution head changed during owner preflight")
    return VerifiedR4OwnerComment(factory=_OWNER_CAPTURE_FACTORY, root=context._root,
        receipt=receipt, capture={"repository": repository, "comment": comment,
            "pull_head": state["head"], "pull_number": int(match.group(1))})


@dataclass(frozen=True, init=False)
class R4ExecutionAuthorization:
    """Private capability; RECORDED_TEST is permanently incapable of a socket."""

    _factory: object
    _context: R4ExecutionPlanContext
    _plan_bytes: bytes
    _receipt_bytes: bytes
    _binding_bytes: bytes
    _owner_token: str
    _owner_capture: object

    def __init__(self, *, factory, context, plan, receipt, binding, owner_token, owner_capture):
        if factory is not _AUTH_FACTORY or type(context) is not R4ExecutionPlanContext:
            raise R4AuthorizationError("R4 execution authorization requires its repository factory")
        for key, value in {"_factory": factory, "_context": context,
            "_plan_bytes": canonical_json_bytes(value=plan),
            "_receipt_bytes": canonical_json_bytes(value=receipt),
            "_binding_bytes": canonical_json_bytes(value=binding), "_owner_token": owner_token,
            "_owner_capture": owner_capture}.items():
            object.__setattr__(self, key, value)


def _issue(*, context, plan, entry_id, receipt, mode, authorized_at_utc, state, owner_capture=None):
    validate_r4_execution_plan(plan=plan, context=context,
        expected_plan_id=plan.get("pending_plan_id"), mode=mode)
    matches = [entry for entry in plan["entries"] if entry["entry_id"] == entry_id]
    if len(matches) != 1:
        raise R4AuthorizationError("R4 provider plan entry is absent or duplicated")
    entry = matches[0]
    parse_utc_timestamp(value=authorized_at_utc)
    receipt_id = None if receipt is None else receipt["receipt_id"]
    owner_token = content_hash(value={"mode": mode, "plan": plan["pending_plan_id"],
        "entry": entry_id, "receipt": receipt_id, "authorized_at_utc": authorized_at_utc})
    namespace = RUNTIME_ROOT + "/" + plan["pending_plan_id"].split(":")[1] + "/entries/" + entry_id.split(":")[1]
    binding = {"record_type": "R4_EXECUTION_AUTHORIZATION_BINDING", "schema_version": 1,
        **{key: plan[key] for key in IDENTITY_FIELDS}, "execution_mode": mode,
        "pending_plan_id": plan["pending_plan_id"], "entry_id": entry_id,
        "fixture_id": entry["fixture_id"], "fixture_execution_ordinal": entry["fixture_execution_ordinal"],
        "plan_ordinal": entry["ordinal"], "exact_head": state["head"], "exact_tree": state["tree"],
        "owner_receipt_id": receipt_id, "owner_token_hash": content_hash(value=owner_token),
        "authorized_at_utc": authorized_at_utc, "invocation_namespace": namespace,
        "context_limit_tokens": 200000, "automatic_retry_count": 0,
        "response_reuse_authorized": False, "sec_calls_authorized": False,
        "qualification_credit": "NONE_INDIVIDUAL_RUN", "publication_credit": "NONE",
        "request_identity": entry["request_identity"], "pending_plan": plan, "owner_receipt": receipt}
    binding["authorization_id"] = content_hash(value=binding)
    return R4ExecutionAuthorization(factory=_AUTH_FACTORY, context=context, plan=plan,
        receipt=receipt, binding=binding, owner_token=owner_token, owner_capture=owner_capture)


def authorize_r4_live_entry(*, context, plan, entry_id, owner_receipt):
    """The only production issuer; ordinary non-empty strings are not authority."""
    if type(context) is not R4ExecutionPlanContext or context._root != REPOSITORY_ROOT.resolve():
        raise R4AuthorizationError("R4 live execution requires the implementation repository")
    if (type(owner_receipt) is not VerifiedR4OwnerComment
            or owner_receipt._factory is not _OWNER_CAPTURE_FACTORY
            or owner_receipt._root != context._root):
        raise R4AuthorizationError("Caller receipt fields are not verified owner-comment authority")
    state = _validate_live_implementation(repo_root=context._root, plan=plan)
    receipt = validate_r4_live_authorization_receipt(receipt=owner_receipt.receipt, plan=plan,
        requirement=context._session._requirement, exact_head=state["head"], exact_tree=state["tree"])
    return _issue(context=context, plan=plan, entry_id=entry_id, receipt=receipt, mode="LIVE",
                  authorized_at_utc=receipt["approved_at_utc"], state=state, owner_capture=owner_receipt)


def authorize_r4_recorded_test_entry(*, context, plan, entry_id,
                                   authorized_at_utc="2026-09-04T00:00:00Z"):
    """Explicit recorded tests exercise the graph, never grant live authority."""
    return _issue(context=context, plan=plan, entry_id=entry_id, receipt=None,
        mode="RECORDED_TEST", authorized_at_utc=authorized_at_utc, state=context._state)


def authorization_binding(authorization):
    if (type(authorization) is not R4ExecutionAuthorization or authorization._factory is not _AUTH_FACTORY):
        raise R4AuthorizationError("A repository R4ExecutionAuthorization is required")
    return strict_json_loads(text=authorization._binding_bytes.decode("utf-8"))


def validate_portable_authorization_binding(*, binding, context):
    """Rebuild complete persisted plan and owner evidence, without issuing live credit."""
    _exact(binding, AUTHORIZATION_BINDING_FIELDS, "Portable R4 authorization binding")
    _self_id(binding, "authorization_id")
    plan, mode = binding["pending_plan"], binding["execution_mode"]
    validate_r4_execution_plan(plan=plan, context=context, expected_plan_id=binding["pending_plan_id"], mode=mode)
    entry = [entry for entry in plan["entries"] if entry["entry_id"] == binding["entry_id"]]
    if len(entry) != 1:
        raise R4AuthorizationError("Portable R4 authorization entry is absent")
    entry = entry[0]
    receipt = binding["owner_receipt"]
    if mode == "LIVE":
        validate_r4_live_authorization_receipt(receipt=receipt, plan=plan,
            requirement=context._session._requirement, exact_head=binding["exact_head"], exact_tree=binding["exact_tree"])
    elif mode != "RECORDED_TEST" or receipt is not None or binding["owner_receipt_id"] is not None:
        raise R4AuthorizationError("Portable recorded authorization was relabelled")
    receipt_id = None if receipt is None else receipt["receipt_id"]
    owner_token = content_hash(value={"mode": mode, "plan": plan["pending_plan_id"],
        "entry": entry["entry_id"], "receipt": receipt_id, "authorized_at_utc": binding["authorized_at_utc"]})
    namespace = RUNTIME_ROOT + "/" + plan["pending_plan_id"].split(":")[1] + "/entries/" + entry["entry_id"].split(":")[1]
    if (binding["record_type"] != "R4_EXECUTION_AUTHORIZATION_BINDING"
            or type(binding["schema_version"]) is not int or binding["schema_version"] != 1
            or any(binding[key] != plan[key] for key in IDENTITY_FIELDS)
            or any(binding[key] != entry[key] for key in ("fixture_id", "fixture_execution_ordinal", "request_identity"))
            or binding["plan_ordinal"] != entry["ordinal"] or binding["owner_receipt_id"] != receipt_id
            or binding["owner_token_hash"] != content_hash(value=owner_token)
            or binding["invocation_namespace"] != namespace
            or type(binding["context_limit_tokens"]) is not int or binding["context_limit_tokens"] != 200000
            or type(binding["automatic_retry_count"]) is not int or binding["automatic_retry_count"] != 0
            or binding["response_reuse_authorized"] is not False or binding["sec_calls_authorized"] is not False
            or binding["qualification_credit"] != "NONE_INDIVIDUAL_RUN" or binding["publication_credit"] != "NONE"):
        raise R4AuthorizationError("Portable R4 authorization body differs from exact plan and owner evidence")
    parse_utc_timestamp(value=binding["authorized_at_utc"])
    return _plain(binding)


def authorization_fields(authorization, request_binding=None, for_socket=False):
    """Revalidate at send/socket; no mutable map can select policy or request."""
    binding = authorization_binding(authorization)
    _self_id(binding, "authorization_id")
    context = authorization._context
    plan = strict_json_loads(text=authorization._plan_bytes.decode("utf-8"))
    mode = binding["execution_mode"]
    validate_r4_execution_plan(plan=plan, context=context, expected_plan_id=binding["pending_plan_id"], mode=mode)
    validate_portable_authorization_binding(binding=binding, context=context)
    if request_binding is not None and any(request_binding.get(key) != value
                                         for key, value in binding["request_identity"].items()):
        raise R4AuthorizationError("Authorized R4 request identity differs")
    if content_hash(value=authorization._owner_token) != binding["owner_token_hash"]:
        raise R4AuthorizationError("R4 reservation owner binding differs")
    if for_socket and mode != "LIVE":
        raise R4AuthorizationError("RECORDED_TEST authorization can never open a provider socket")
    if mode == "LIVE":
        if context._root != REPOSITORY_ROOT.resolve():
            raise R4AuthorizationError("R4 socket repository differs")
        state = _validate_live_implementation(repo_root=context._root, plan=plan)
        receipt = strict_json_loads(text=authorization._receipt_bytes.decode("utf-8"))
        capture = authorization._owner_capture
        if (type(capture) is not VerifiedR4OwnerComment or capture._factory is not _OWNER_CAPTURE_FACTORY
                or capture._root != context._root or capture.receipt != receipt
                or receipt["receipt_id"] != binding["owner_receipt_id"]):
            raise R4AuthorizationError("R4 live owner provenance capability differs")
        validate_r4_live_authorization_receipt(receipt=receipt, plan=plan,
            requirement=context._session._requirement, exact_head=state["head"], exact_tree=state["tree"])
        if state != {"head": binding["exact_head"], "tree": binding["exact_tree"]}:
            raise R4AuthorizationError("R4 execution head changed after authorization")
        from .r4_live_qualification import validate_r4_execution_prefix
        validate_r4_execution_prefix(context=context, plan=plan, entry_id=binding["entry_id"],
                                     for_socket=for_socket)
    elif mode != "RECORDED_TEST" or binding["owner_receipt_id"] is not None:
        raise R4AuthorizationError("R4 authorization generation differs")
    workspace = context._root / binding["invocation_namespace"]
    cursor = context._root
    for part in Path(binding["invocation_namespace"]).parts:
        cursor /= part
        if cursor.is_symlink():
            raise R4AuthorizationError("R4 runtime namespace contains a symlink")
    return {**binding, "owner_token": authorization._owner_token,
        "invocation_workspace": workspace, "repo_root": context._root}


def authorized_request(authorization):
    fields = authorization_fields(authorization)
    request = authorization._context._requests[fields["fixture_id"]]
    authorization_fields(authorization, request_binding=request.identity)
    return request
