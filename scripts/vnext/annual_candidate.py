"""Bind saved annual input to one ordinary catalog execution; never publish.

Plans are data, not capabilities. Only fresh GitHub owner-comment verification
can issue the process-local capability. The existing WB-3 controller owns all
reservation, retry, terminal and response storage behavior.
"""
from dataclasses import dataclass
from pathlib import Path
import re
import subprocess

from git_workspace import sanitized_git_environment
from validation_provenance import capture_source_snapshot
from .annual_input import prepare_annual_input
from .canonical import canonical_json_bytes, content_hash, sha256_bytes, sha256_file
from .canonical import strict_json_file, strict_json_loads, parse_utc_timestamp
from .requirement_profile import validate_execution_authority, validate_transition_activation_receipt
from .requirement_profile_v5 import REQUIREMENT_ID, DECISION_ID
from .requirements import load_requirement_snapshot
from .sources import raw_blob_record, source_reference_record, load_raw_blob_bytes
from .sources import resolve_repository_file
from .table_grid import build_table_grid
from .reader_input import build_reader_input_manifest, prepare_reader_request
from .table_task_contracts import table_task_execution_plan

REPO_ROOT = Path(__file__).resolve().parents[2]
_BINDING_FILE = "annual_candidate_binding.json"
_AUTHORITY = object()


class AnnualCandidateError(ValueError):
    pass


def _require(condition, message):
    if not condition:
        raise AnnualCandidateError(message)


def _copy(value):
    return strict_json_loads(text=canonical_json_bytes(value=value).decode())


def _requirement():
    requirement = load_requirement_snapshot(snapshot_dir=REPO_ROOT / "requirements" / REQUIREMENT_ID)
    validate_execution_authority(repo_root=REPO_ROOT, requirement=requirement)
    return requirement


def _code_identity():
    snapshot = capture_source_snapshot(workdir=REPO_ROOT)
    _require(snapshot.checkout_status == "GIT_CLEAN", "CANDIDATE_CLEAN_CODE_REQUIRED")
    tree = subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=REPO_ROOT,
        env=sanitized_git_environment(), text=True, capture_output=True, check=True).stdout.strip()
    return {"exact_head": snapshot.source_commit, "exact_tree": tree,
            "source_input_tree": snapshot.tree_sha256}


def _output_root(path):
    _require(isinstance(path, Path) and path.is_absolute(), "CANDIDATE_ABSOLUTE_OUTPUT_REQUIRED")
    for part in (path, *path.parents):
        _require(not part.is_symlink(), "CANDIDATE_OUTPUT_ALIAS_FORBIDDEN")
        _require(not (part / ".git").exists(), "CANDIDATE_OUTPUT_MUST_BE_OUTSIDE_CHECKOUT")
    resolved = path.resolve()
    _require(REPO_ROOT not in resolved.parents and resolved not in (REPO_ROOT, *REPO_ROOT.parents),
             "CANDIDATE_OUTPUT_OVERLAPS_REPOSITORY")
    return resolved


def _request(prepared, task_id):
    from .ai_adapter import approved_transport_policy, build_provider_request_body
    from .provider_runtime import load_provider_runtime_authority, estimate_context_tokens
    kwargs = prepared["table_input"]
    raw = raw_blob_record(repo_root=REPO_ROOT, repo_relative_path=kwargs["source_repo_relative_path"],
                          media_type=kwargs["source_media_type"])
    source = source_reference_record(raw_blob=raw, **{k:kwargs[k] for k in
        ("company_id", "source_url", "accession", "document_name", "source_role", "request_attempt_id")})
    grid = build_table_grid(html_bytes=load_raw_blob_bytes(repo_root=REPO_ROOT, raw_blob=raw),
        parent_raw_asset_ids=[raw["raw_asset_id"]],
        storage_uri="artifacts/vnext/derived/" + raw["raw_asset_id"].split(":")[1] + ".json")
    manifest = build_reader_input_manifest(derived_asset=grid, source_reference_ids=[source["source_reference_id"]])
    request = prepare_reader_request(repo_root=REPO_ROOT, task_contract_id=task_id,
                                     manifest=manifest, derived_asset=grid)
    parent = load_requirement_snapshot(snapshot_dir=REPO_ROOT / "requirements/issue_15_v1")
    transport = approved_transport_policy(requirement=parent)
    outbound, schema = build_provider_request_body(policy=transport, reader_request_bytes=request.request_bytes)
    runtime = load_provider_runtime_authority(repo_root=REPO_ROOT, provider=transport.provider,
                                               model=transport.model, api=transport.api)
    estimate = estimate_context_tokens(request_body=outbound, authority=runtime)
    _require(len(outbound) <= transport.maximum_payload_bytes, "PAYLOAD_LIMIT")
    _require(estimate <= runtime["maximum_context_tokens"], "MODEL_CONTEXT_LIMIT")
    return {"source_reference": source, "reader_input_manifest_id": manifest["reader_input_manifest_id"],
        "derived_asset_id": grid["derived_asset_id"], "table_count": len(manifest["tables"]),
        "reader_request_sha256": sha256_bytes(content=request.request_bytes),
        "provider_request_body_sha256": sha256_bytes(content=outbound), "provider_request_bytes": len(outbound),
        "output_schema_sha256": sha256_bytes(content=schema), "estimated_context_tokens": estimate,
        "maximum_payload_bytes": transport.maximum_payload_bytes,
        "model_context_tokens_max": runtime["maximum_context_tokens"],
        "provider": transport.provider, "model": transport.model, "api": transport.api}, outbound


def prepare_candidate_plan(*, output_root: Path, fiscal_year=None):
    """Create a pending plan from ordinary inputs; no authorization or network."""
    requirement = _requirement()
    policy = requirement["effective_decisions"][DECISION_ID]["choice"]
    code = _code_identity()
    prepared = prepare_annual_input(repo_root=REPO_ROOT, company_id=policy["company_id"], fiscal_year=fiscal_year)
    request, _ = _request(prepared, policy["task_contract_id"])
    task = table_task_execution_plan(repo_root=REPO_ROOT, task_contract_id=policy["task_contract_id"])
    body = {"record_type": "ANNUAL_CANDIDATE_EXECUTION_PLAN", "schema_version": 1,
        "state": "PENDING_ACTIVATION_AND_EXECUTION_APPROVAL", "requirement_id": REQUIREMENT_ID,
        "requirement_closure_hash": requirement["requirement_closure_hash"], "requirement_hashes": requirement["hashes"],
        "policy_decision_hash": content_hash(value=requirement["effective_decisions"][DECISION_ID]),
        "code_identity": code, "prepared_input": prepared, "task_contract_id": policy["task_contract_id"],
        "task_binding": task["run_binding"], "request": request,
        "output_root": str(_output_root(output_root)), "maximum_new_executions": 1, "automatic_retry_count": 0,
        "actual_input_tokens_max": policy["actual_input_tokens_max"], "qualification_credit": "NONE",
        "publication_credit": "NONE", "sec_calls_authorized": False}
    _require(code == _code_identity(), "CANDIDATE_CODE_CHANGED_DURING_PLAN")
    return {**body, "plan_id": content_hash(value=body)}


def validate_candidate_plan(plan):
    _require(type(plan) is dict, "CANDIDATE_PLAN_REQUIRED")
    try:
        expected = prepare_candidate_plan(output_root=Path(plan["output_root"]),
            fiscal_year=plan["prepared_input"]["table_input"]["target_period"]["fiscal_year"])
    except (KeyError, TypeError) as error:
        raise AnnualCandidateError("CANDIDATE_PLAN_INVALID") from error
    # Pinned fiscal year, accession, all proofs and request must remain equal;
    # execution never substitutes whatever the default selector now calls latest.
    _require(expected == plan, "CANDIDATE_PLAN_BINDING_CHANGED")
    return expected


def execution_paths(plan):
    workspace = _output_root(Path(plan["output_root"])) / plan["plan_id"].split(":")[1]
    _output_root(workspace)
    return workspace, workspace / "run", "run:annual-candidate:" + plan["plan_id"].split(":")[1]


def expected_owner_approval(plan):
    """Review template only. Returning this object issues no authority."""
    return {"decision": "AUTHORIZE_ORDINARY_ANNUAL_CANDIDATE", "plan_id": plan["plan_id"],
        "requirement_id": plan["requirement_id"], "requirement_closure_hash": plan["requirement_closure_hash"],
        **plan["code_identity"], "provider_request_body_sha256": plan["request"]["provider_request_body_sha256"],
        "output_root": plan["output_root"], "maximum_new_executions": 1, "automatic_retry_count": 0,
        "actual_input_tokens_max": 200000, "usage_is_post_execution_acceptance": True,
        "provider_calls_authorized": True, "paid_model_calls_authorized": True,
        "sec_calls_authorized": False, "qualification_credit": "NONE", "publication_authorized": False}


def expected_activation_approval(plan):
    return {"decision": "APPROVE_REQUIREMENT_TRANSITION", "exact_head": plan["code_identity"]["exact_head"],
        "requirement_id": plan["requirement_id"], "requirement_closure_hash": plan["requirement_closure_hash"],
        "scope": "TRANSITION_ONLY", "provider_paid_sec_authorized": False}


def _github(path):
    """External governance boundary; tests inject only here and at provider I/O."""
    result = subprocess.run(["gh", "api", "--hostname", "github.com", path], cwd=REPO_ROOT,
                             text=True, capture_output=True, check=False)
    _require(result.returncode == 0, "CANDIDATE_OWNER_PROVENANCE_UNAVAILABLE")
    return strict_json_loads(text=result.stdout)


def _validate_comment(*, plan, repository, url, comment, pull, expected):
    match = re.fullmatch(r"https://github\.com/" + re.escape(repository)
        + r"/pull/([1-9][0-9]*)#issuecomment-([1-9][0-9]*)", url)
    _require(match is not None, "CANDIDATE_OWNER_COMMENT_URL_INVALID")
    _require(type(comment) is dict and type(pull) is dict
        and comment.get("html_url") == url and str(comment.get("id")) == match[2]
        and comment.get("issue_url") == "https://api.github.com/repos/" + repository + "/issues/" + match[1]
        and comment.get("user", {}).get("login") == repository.split("/")[0]
        and comment.get("created_at") == comment.get("updated_at")
        and pull.get("number") == int(match[1]) and pull.get("state") == "open" and pull.get("merged") is False
        and pull.get("head", {}).get("sha") == plan["code_identity"]["exact_head"]
        and pull.get("head", {}).get("repo", {}).get("full_name") == repository
        and pull.get("base", {}).get("ref") == "main", "CANDIDATE_OWNER_PROVENANCE_INVALID")
    parse_utc_timestamp(value=comment["created_at"])
    _require(strict_json_loads(text=comment["body"]) == expected, "CANDIDATE_OWNER_APPROVAL_MISMATCH")


def _validate_binding(binding, *, check_plan=True):
    _require(type(binding) is dict and set(binding) == {"plan", "activation_comment", "owner_comment", "pull"},
             "CANDIDATE_BINDING_INVALID")
    plan = binding["plan"]
    if check_plan:
        validate_candidate_plan(plan)
    requirement = _requirement()
    _require(plan["plan_id"] == content_hash(value={k:v for k,v in plan.items() if k != "plan_id"}),
             "CANDIDATE_PLAN_ID_INVALID")
    _require(plan["requirement_id"] == requirement["requirement_id"]
        and plan["requirement_hashes"] == requirement["hashes"]
        and plan["requirement_closure_hash"] == requirement["requirement_closure_hash"], "CANDIDATE_REQUIREMENT_CHANGED")
    repository = requirement["baseline"]["repository"]["identity"]
    for key, expected in (("activation_comment", expected_activation_approval(plan)),
                          ("owner_comment", expected_owner_approval(plan))):
        comment = binding[key]
        _validate_comment(plan=plan, repository=repository, url=comment["html_url"],
                          comment=comment, pull=binding["pull"], expected=expected)
    activation = binding["activation_comment"]
    receipt = {"record_type": "REQUIREMENT_TRANSITION_ACTIVATION", "schema_version": 1,
        "requirement_id": plan["requirement_id"], "requirement_closure_hash": plan["requirement_closure_hash"],
        "exact_head": plan["code_identity"]["exact_head"], "authorization_scope": "TRANSITION_ONLY",
        "provider_paid_sec_authorized": False, "approval_kind": "EXACT_HEAD_TRANSITION_APPROVAL",
        "owner": "github:" + activation["user"]["login"], "approved_at_utc": activation["created_at"],
        "source_url": activation["html_url"], "approval_text": activation["body"],
        "approval_text_sha256": sha256_bytes(content=activation["body"].encode())}
    receipt["receipt_id"] = content_hash(value=receipt)
    validate_transition_activation_receipt(receipt=receipt, requirement=requirement,
                                          exact_head=plan["code_identity"]["exact_head"])
    return requirement


@dataclass(frozen=True, init=False)
class AnnualCandidateAuthorization:
    _factory: object
    _bytes: bytes

    def __init__(self, *, factory, binding):
        _require(factory is _AUTHORITY, "CANDIDATE_VERIFIED_OWNER_REQUIRED")
        object.__setattr__(self, "_factory", factory)
        object.__setattr__(self, "_bytes", canonical_json_bytes(value=binding))


def verify_candidate_authorization(*, plan, activation_url, owner_url):
    """Future execute preflight. Dictionaries and historical grants cannot issue authority."""
    validate_candidate_plan(plan)
    requirement = _requirement()
    repository = requirement["baseline"]["repository"]["identity"]
    comments, pull_number = [], None
    for url in (activation_url, owner_url):
        match = re.fullmatch(r"https://github\.com/" + re.escape(repository)
            + r"/pull/([1-9][0-9]*)#issuecomment-([1-9][0-9]*)", url)
        _require(match is not None, "CANDIDATE_OWNER_COMMENT_URL_INVALID")
        _require(pull_number in (None, match[1]), "CANDIDATE_APPROVALS_DIFFERENT_PR")
        pull_number = match[1]
        comments.append(_github("repos/" + repository + "/issues/comments/" + match[2]))
    binding = {"plan": plan, "activation_comment": comments[0], "owner_comment": comments[1],
               "pull": _github("repos/" + repository + "/pulls/" + pull_number)}
    _validate_binding(binding)
    return AnnualCandidateAuthorization(factory=_AUTHORITY, binding=binding)


def authorization_fields(authorization):
    _require(type(authorization) is AnnualCandidateAuthorization and authorization._factory is _AUTHORITY,
             "CANDIDATE_AUTHORIZATION_REQUIRED")
    binding = strict_json_loads(text=authorization._bytes.decode())
    requirement = _validate_binding(binding, check_plan=False)
    plan = binding["plan"]
    _require(_code_identity() == plan["code_identity"], "CANDIDATE_CODE_BINDING_CHANGED")
    prepared = prepare_annual_input(repo_root=REPO_ROOT,
        company_id=plan["prepared_input"]["table_input"]["company_id"],
        fiscal_year=plan["prepared_input"]["table_input"]["target_period"]["fiscal_year"])
    _require(prepared == plan["prepared_input"], "CANDIDATE_PINNED_INPUT_CHANGED")
    workspace, run_dir, run_id = execution_paths(plan)
    return {"binding": binding, "plan": plan, "requirement": requirement, "workspace_dir": workspace,
            "run_dir": run_dir, "run_id": run_id,
            # Neither re-captured comments nor a new process can create a new execution identity.
            "owner_token": plan["plan_id"], "authorized_at_utc": binding["owner_comment"]["created_at"]}


def validate_workflow_authorization(*, authorization, adapter, repo_root, run_dir, run_id,
                                    task_contract_id, **source):
    fields = authorization_fields(authorization)
    plan = fields["plan"]
    context = getattr(adapter, "invocation_context", None)
    _require(repo_root.resolve() == REPO_ROOT and run_dir == fields["run_dir"] and run_id == fields["run_id"]
        and task_contract_id == plan["task_contract_id"] and source == plan["prepared_input"]["table_input"]
        and context is not None and context.annual_candidate_authorization is authorization
        and context.qualification_usage_policy is None and context.workspace_dir == fields["workspace_dir"]
        and context.release_input_plan_id == plan["plan_id"] and context.owner_token == fields["owner_token"],
        "CANDIDATE_WORKFLOW_BINDING_MISMATCH")
    return fields


def write_run_binding(*, run_dir, authorization):
    from .canonical import atomic_write_json
    fields = authorization_fields(authorization)
    _require(run_dir == fields["run_dir"] and not (run_dir / _BINDING_FILE).exists(), "CANDIDATE_RUN_BINDING_EXISTS")
    atomic_write_json(path=run_dir / _BINDING_FILE, value=fields["binding"])


def validate_run_binding(*, repo_root, run_dir, manifest, records):
    _require(repo_root.resolve() == REPO_ROOT and manifest.get("record_type") == "SUCCESSOR_RUN"
        and manifest.get("requirement_id") == REQUIREMENT_ID and manifest.get("qualification_authorization") is None,
        "CANDIDATE_RUN_IDENTITY_INVALID")
    path = run_dir / _BINDING_FILE
    _require(path.is_file() and not path.is_symlink(), "CANDIDATE_RUN_BINDING_MISSING")
    binding = strict_json_file(path=path)
    _validate_binding(binding)
    plan = binding["plan"]
    _, expected_dir, run_id = execution_paths(plan)
    expected = {"run_id": run_id, "target_period": plan["prepared_input"]["table_input"]["target_period"],
        "company_id": plan["prepared_input"]["table_input"]["company_id"], "task_contract_bindings": [plan["task_binding"]],
        "source_references": [plan["request"]["source_reference"]], "requirement_id": plan["requirement_id"],
        "requirement_closure_hash": plan["requirement_closure_hash"], "requirement_hashes": plan["requirement_hashes"]}
    _require(run_dir == expected_dir and all(manifest.get(k) == v for k,v in expected.items()), "CANDIDATE_RUN_BINDING_MISMATCH")
    attempts = [r for r in records if r["record_type"] == "AI_EXTRACTION_ATTEMPT"]
    _require(len(attempts) <= 1, "CANDIDATE_ATTEMPT_COUNT_INVALID")
    for attempt in attempts:
        _require("qualification_authorization" not in attempt, "CANDIDATE_CANNOT_BORROW_QUALIFICATION")
        _require(sha256_file(path=run_dir / attempt["request_body_path"]) == plan["request"]["provider_request_body_sha256"],
                 "CANDIDATE_PERSISTED_REQUEST_MISMATCH")
        if attempt["status"] == "SUCCEEDED":
            _require(not usage_error((run_dir / attempt["raw_response_path"]).read_bytes()), "CANDIDATE_ACTUAL_USAGE_INVALID")
        _validate_controller_terminal(binding=binding, attempt=attempt, run_dir=run_dir)


def _validate_controller_terminal(*, binding, attempt, run_dir):
    from . import invocation_control as controller
    plan = binding["plan"]
    if not attempt["transport_observation"]["egress_attempted"]:
        _require(attempt["status"] == "FAILED", "CANDIDATE_HISTORICAL_RESPONSE_FORBIDDEN")
        return
    workspace, _, _ = execution_paths(plan)
    root = workspace / "invocation_control"
    paths = list((root / "plans").glob("*.json"))
    _require(len(paths) == 1 and not paths[0].is_symlink(), "CANDIDATE_CONTROLLER_PLAN_MISSING")
    invocation = strict_json_file(path=paths[0])
    requirement = _requirement()
    authority = controller.prepare_annual_candidate_invocation_authority(requirement=requirement, repo_root=REPO_ROOT)
    with controller._successor_plan_context(repo_root=REPO_ROOT, authority=authority):
        controller.validate_ai_invocation_plan(plan=invocation)
        _require(invocation["release_input_plan_id"] == plan["plan_id"]
            and invocation["provider_request_body_sha256"] == plan["request"]["provider_request_body_sha256"]
            and invocation["source_identity_hash"] == plan["request"]["reader_input_manifest_id"]
            and invocation["selected_representation_hash"] == plan["request"]["derived_asset_id"],
            "CANDIDATE_CONTROLLER_PLAN_MISMATCH")
        execution_id = controller.execution_identity(ai_invocation_plan_id=invocation["ai_invocation_plan_id"],
            owner_token=plan["plan_id"], authorized_at_utc=binding["owner_comment"]["created_at"])
        receipt = controller._load_execution_receipt(root=root,
            path=controller._execution_path(root=root, execution_id=execution_id), execution_id=execution_id)
        markers = controller._egress_markers_for_execution(root=root, execution_id=execution_id)
        _require(len(markers) == 1 and markers[0]["attempt_ordinal"] == 1,
                 "CANDIDATE_CONTROLLER_EGRESS_COUNT_INVALID")
        if attempt["status"] == "SUCCEEDED":
            saved = controller.load_successful_response(workspace_dir=workspace, plan=invocation)
            _require(receipt["status"] == "SUCCEEDED" and len(receipt["attempts"]) == 1
                and saved["provider_request_id"] == attempt["provider_request_id"]
                and sha256_bytes(content=saved["response_body"]) == attempt["assistant_output_sha256"],
                "CANDIDATE_RESPONSE_NOT_FROM_THIS_EXECUTION")
            from .ai_adapter import _controller_usage
            _require(receipt["attempts"][0]["usage"] == _controller_usage(
                raw_response_bytes=(run_dir / attempt["raw_response_path"]).read_bytes()), "CANDIDATE_USAGE_RECEIPT_MISMATCH")
        elif receipt["status"] == "UNKNOWN_REMOTE_OUTCOME":
            _require(attempt["error_class"] == "UNKNOWN_REMOTE_OUTCOME", "CANDIDATE_UNKNOWN_TERMINAL_MISMATCH")
        else:
            _require(receipt["status"] in {"FAILED_TERMINAL", "FAILED_RETRYABLE_FINAL"}
                and len(receipt["attempts"]) == 1
                and receipt["attempts"][0]["error_class"] == attempt["error_class"], "CANDIDATE_FAILURE_TERMINAL_MISMATCH")


def usage_error(raw_response_bytes):
    """Strict actual usage, independent of historical usage and the byte estimator."""
    try:
        usage = strict_json_loads(text=raw_response_bytes.decode())["usage"]
        def count(*names):
            values = [usage[name] for name in names if name in usage]
            if not values or any(type(v) is not int or v < 0 for v in values) or len(set(values)) != 1:
                raise ValueError("Inconsistent usage")
            return values[0]
        prompt, completion, total = count("prompt_tokens", "input_tokens"), count("completion_tokens", "output_tokens"), count("total_tokens")
        return "" if prompt <= 200000 and total == prompt + completion else "CONTEXT_LIMIT"
    except (KeyError, TypeError, ValueError, AttributeError):
        return "CONTEXT_LIMIT"


def execute_candidate(*, plan, authorization):
    """Enter the existing workflow, or return a saved local terminal without egress."""
    from .ai_adapter import build_annual_candidate_transport_adapter
    from .workflow import create_table_task_review_run, finalize_reviewed_direct_results
    from .run_store import load_open_run
    fields = authorization_fields(authorization)
    _require(fields["plan"] == plan, "CANDIDATE_EXECUTION_PLAN_MISMATCH")
    run_dir = fields["run_dir"]
    if run_dir.exists():
        manifest, records, _ = load_open_run(run_dir=run_dir)
        validate_run_binding(repo_root=REPO_ROOT, run_dir=run_dir, manifest=manifest, records=records)
        # Partial local materialization is inspectable, never grounds for another request.
        return candidate_status(plan=plan, status="SAVED_RUN_ONLY")
    adapter = build_annual_candidate_transport_adapter(authorization=authorization)
    created = create_table_task_review_run(repo_root=REPO_ROOT, run_dir=run_dir, run_id=fields["run_id"],
        task_contract_id=plan["task_contract_id"], adapter=adapter, clock=None,
        candidate_authorization=authorization, **plan["prepared_input"]["table_input"])
    status = created["status"]
    if status == "PENDING_HUMAN_REVIEW":
        finalize_reviewed_direct_results(repo_root=REPO_ROOT, run_dir=run_dir)
        status = "CANDIDATE_COMPUTED"
    return candidate_status(plan=plan, status=status)


def candidate_status(*, plan, status):
    from .run_store import load_run_for_status
    _, run_dir, _ = execution_paths(plan)
    manifest, records, decisions = load_run_for_status(run_dir=run_dir, repo_root=REPO_ROOT)
    return {"status": status, "run_id": manifest["run_id"], "run_directory": str(run_dir),
        "run_status": manifest["status"], "qualification_credit": "NONE", "publication_credit": "NONE",
        "attempts": [{k:r[k] for k in ("attempt_id", "status", "error_class", "provider_request_id")}
            for r in records if r["record_type"] == "AI_EXTRACTION_ATTEMPT"],
        "results": [r for r in records if r["record_type"] == "METRIC_RESULT"],
        "reviewers": [d["reviewer_type"] for d in decisions]}

