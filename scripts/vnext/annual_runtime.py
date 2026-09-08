"""A reviewed code version runs bounded annual candidates against saved inputs.

The data directory contains verified authority copies, never imported Python.
A fresh owner issue comment delegates one stage, not one filing. The retained
WB-3 controller still owns every actual request and terminal record.
"""
from dataclasses import dataclass
from pathlib import Path
import os
import re
import subprocess

from git_workspace import sanitized_git_environment
from . import annual_candidate as prior, annual_input, annual_update as update
from .canonical import atomic_write_json, canonical_json_bytes, content_hash
from .canonical import (
    parse_utc_timestamp,
    sha256_bytes,
    sha256_file,
    strict_json_file,
    strict_json_loads,
)
from .requirement_profile import (
    requirement_authority_paths,
    validate_execution_authority,
)
from .requirement_profile_v6 import REQUIREMENT_ID, DECISION_ID
from .requirements import load_requirement_snapshot
from .sources import (
    raw_blob_record,
    source_reference_record,
    load_raw_blob_bytes,
    resolve_repository_file,
)
from .reader_input import build_reader_input_manifest, prepare_reader_request
from .table_grid import build_table_grid
from .table_task_contracts import table_task_execution_plan

CODE_ROOT = Path(__file__).resolve().parents[2]
_FACTORY = object()
BINDING_FILE = "annual_candidate_binding.json"


class AnnualRuntimeError(ValueError):
    """A failed or uncertain stage never receives another execution."""


def require(condition, reason):
    if not condition:
        raise AnnualRuntimeError(reason)


def _git(*args):
    result = subprocess.run(
        ["git", *args],
        cwd=CODE_ROOT,
        env=sanitized_git_environment(),
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def code_identity():
    """Keep code clean and bind runtime files independently of annual data."""
    require(
        not _git("status", "--porcelain", "--untracked-files=all"),
        "RUNTIME_CLEAN_CODE_REQUIRED",
    )
    paths = _git(
        "ls-tree",
        "-r",
        "--name-only",
        "HEAD",
        "scripts",
        "tools",
        "catalog",
        "config",
        "requirements",
        "docs/evidence/issue_28_annual_runtime_policy.json",
    ).splitlines()
    files = {}
    for relative in paths:
        path = resolve_repository_file(repo_root=CODE_ROOT, repo_relative_path=relative)
        files[relative] = {
            "sha256": sha256_file(path=path),
            "size": path.stat().st_size,
        }
    return {
        "exact_head": _git("rev-parse", "HEAD"),
        "runtime_tree": content_hash(value=files),
    }


def _requirement():
    requirement = load_requirement_snapshot(
        snapshot_dir=CODE_ROOT / "requirements" / REQUIREMENT_ID
    )
    validate_execution_authority(repo_root=CODE_ROOT, requirement=requirement)
    return requirement


def _external(path):
    require(
        isinstance(path, Path) and path.is_absolute(), "RUNTIME_ABSOLUTE_PATH_REQUIRED"
    )
    for p in (path, *path.parents):
        require(not p.is_symlink(), "RUNTIME_PATH_ALIAS_FORBIDDEN")
        require(not (p / ".git").exists(), "RUNTIME_DATA_MUST_BE_OUTSIDE_GIT")
    result = path.resolve()
    require(
        result != CODE_ROOT
        and result not in CODE_ROOT.parents
        and CODE_ROOT not in result.parents,
        "RUNTIME_DATA_CODE_OVERLAP",
    )
    require(
        not (result / "outputs/active_publication.json").exists()
        and not (result / "outputs/publication_state.json").exists(),
        "RUNTIME_ACTIVE_ROOT_FORBIDDEN",
    )
    return result


def _authority_files(requirement):
    foundation = strict_json_file(
        path=CODE_ROOT / "requirements/issue_15_v1/foundation_verification_receipt.json"
    )
    return sorted(
        set(requirement_authority_paths(repo_root=CODE_ROOT, requirement=requirement))
        | set(_git("ls-files", "catalog", "config").splitlines())
        | {row["path"] for row in foundation["receipt_bindings"]}
    )


def verify_data_root(data_root, requirement=None):
    data_root = _external(data_root)
    requirement = requirement or _requirement()
    expected = set(_authority_files(requirement))
    # Only evidence receives fresh inputs. Extra executable/rule files cannot
    # silently become a new authority or a second imported implementation.
    actual = {
        p.relative_to(data_root).as_posix()
        for top in {p.split("/")[0] for p in expected}
        for p in (data_root / top).rglob("*")
        if p.is_file() or p.is_symlink()
    }
    require(actual == expected, "RUNTIME_AUTHORITY_FILE_SET_CHANGED")
    for relative in sorted(expected):
        copied = resolve_repository_file(
            repo_root=data_root, repo_relative_path=relative
        )
        original = resolve_repository_file(
            repo_root=CODE_ROOT, repo_relative_path=relative
        )
        require(
            copied.read_bytes() == original.read_bytes(),
            "RUNTIME_AUTHORITY_BYTES_CHANGED: " + relative,
        )
    update._rows(data_root)
    return data_root


def initialize_data_root(*, data_root):
    """Copy authority and existing exact request evidence; no acquisition."""
    requirement = _requirement()
    before = code_identity()
    data_root = _external(data_root)
    require(not data_root.exists(), "RUNTIME_DATA_ROOT_ALREADY_EXISTS")
    company = update.supported_company(repo_root=CODE_ROOT)
    prepared = annual_input.prepare_annual_input(
        repo_root=CODE_ROOT, company_id=company["company_id"]
    )
    _copy_inputs(
        source_root=CODE_ROOT,
        data_root=data_root,
        prepared=prepared,
        requirement=requirement,
    )
    verify_data_root(data_root, requirement)
    require(code_identity() == before, "RUNTIME_CODE_CHANGED_DURING_SEED")
    return {
        "status": "SAVED_INPUTS_COPIED",
        "data_root": str(data_root),
        "code_identity": before,
        "input_id": prepared["input_id"],
        "provider_paid_sec_calls": [0, 0, 0],
    }


def _copy_inputs(*, source_root, data_root, prepared, requirement):
    """Preserve the exact ledger and source bytes as one Run input snapshot."""
    data_root = _external(data_root)
    require(not data_root.exists(), "RUNTIME_INPUT_SNAPSHOT_ALREADY_EXISTS")
    paths = set(_authority_files(requirement)) | {
        "evidence/requests_log.csv",
        "evidence/requests_log_manifest.json",
    }
    for proof in prepared["source_proofs"]:
        paths.update(
            (
                proof["request_repo_relative_path"],
                proof["request_headers_repo_relative_path"],
            )
        )
    for relative in sorted(paths):
        source = resolve_repository_file(
            repo_root=source_root, repo_relative_path=relative
        )
        target = data_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as output:
            output.write(source.read_bytes())


def _request(prepared, data_root, task_id):
    # Same factories and full document as PR36. Only the verified byte root differs.
    from .ai_adapter import approved_transport_policy, build_provider_request_body
    from .provider_runtime import (
        load_provider_runtime_authority,
        estimate_context_tokens,
    )

    kwargs = prepared["table_input"]
    raw = raw_blob_record(
        repo_root=data_root,
        repo_relative_path=kwargs["source_repo_relative_path"],
        media_type=kwargs["source_media_type"],
    )
    source = source_reference_record(
        raw_blob=raw,
        **{
            k: kwargs[k]
            for k in (
                "company_id",
                "source_url",
                "accession",
                "document_name",
                "source_role",
                "request_attempt_id",
            )
        }
    )
    grid = build_table_grid(
        html_bytes=load_raw_blob_bytes(repo_root=data_root, raw_blob=raw),
        parent_raw_asset_ids=[raw["raw_asset_id"]],
        storage_uri="artifacts/vnext/derived/"
        + raw["raw_asset_id"].split(":")[1]
        + ".json",
    )
    manifest = build_reader_input_manifest(
        derived_asset=grid, source_reference_ids=[source["source_reference_id"]]
    )
    request = prepare_reader_request(
        repo_root=CODE_ROOT,
        task_contract_id=task_id,
        manifest=manifest,
        derived_asset=grid,
    )
    parent = load_requirement_snapshot(
        snapshot_dir=CODE_ROOT / "requirements/issue_15_v1"
    )
    transport = approved_transport_policy(requirement=parent)
    outbound, schema = build_provider_request_body(
        policy=transport, reader_request_bytes=request.request_bytes
    )
    runtime = load_provider_runtime_authority(
        repo_root=CODE_ROOT,
        provider=transport.provider,
        model=transport.model,
        api=transport.api,
    )
    estimate = estimate_context_tokens(request_body=outbound, authority=runtime)
    require(len(outbound) <= transport.maximum_payload_bytes, "PAYLOAD_LIMIT")
    require(estimate <= runtime["maximum_context_tokens"], "MODEL_CONTEXT_LIMIT")
    return {
        "source_reference": source,
        "reader_input_manifest_id": manifest["reader_input_manifest_id"],
        "derived_asset_id": grid["derived_asset_id"],
        "table_count": len(manifest["tables"]),
        "reader_request_sha256": sha256_bytes(content=request.request_bytes),
        "provider_request_body_sha256": sha256_bytes(content=outbound),
        "provider_request_bytes": len(outbound),
        "output_schema_sha256": sha256_bytes(content=schema),
        "estimated_context_tokens": estimate,
        "maximum_payload_bytes": transport.maximum_payload_bytes,
        "model_context_tokens_max": runtime["maximum_context_tokens"],
        "provider": transport.provider,
        "model": transport.model,
        "api": transport.api,
    }


def stage_proposal(*, stage_root, data_root, baseline_run, review_path):
    """Reviewable delegation template, not an execution capability."""
    requirement = _requirement()
    identity = code_identity()
    review = strict_json_file(path=review_path)
    require(
        review["reviewer_kind"] == "INDEPENDENT_MODEL_SUBTASK"
        and review["conclusion"] == "NO_BLOCKING_FINDINGS"
        and review["reviewed_head"] == identity["exact_head"]
        and review["runtime_tree"] == identity["runtime_tree"],
        "RUNTIME_INDEPENDENT_REVIEW_REQUIRED",
    )
    root, data = _external(stage_root), verify_data_root(data_root, requirement)
    require(data != root and data not in root.parents, "RUNTIME_STAGE_DATA_OVERLAP")
    company = update.supported_company(repo_root=CODE_ROOT)
    baseline = update.candidate_baseline(company=company, run_dir=baseline_run)
    policy = requirement["effective_decisions"][DECISION_ID]["choice"]
    body = {
        "decision": "AUTHORIZE_ANNUAL_RUNTIME_STAGE",
        "approval_kind": "USER_DELEGATED_CONDITIONAL_STAGE_APPROVAL",
        "delegation_source": "codex-task:01a081bb-9220-7de3-a311-b481906b3146",
        "statement": "Recorded by Codex under the user stage delegation after independent code review; not a claim that the user personally reviewed this future head.",
        "requirement_id": REQUIREMENT_ID,
        "requirement_closure_hash": requirement["requirement_closure_hash"],
        "reviewed_code": identity,
        "independent_review": review,
        "independent_review_sha256": sha256_file(path=review_path),
        "stage_root": str(root),
        "data_root": str(data),
        "initial_candidate": baseline,
        "baseline_mode": "ISOLATED_HISTORICAL_START_NOT_PRODUCTION",
        "policy": policy,
        "maximum_provider_paid_sec_calls": [1, 1, 0],
        "automatic_retry_count": 0,
        "publication_authorized": False,
        "long_running_schedule_authorized": False,
    }
    return {**body, "stage_id": content_hash(value=body)}


def _validate_stage(stage):
    require(
        type(stage) is dict
        and stage.get("stage_id")
        == content_hash(value={k: v for k, v in stage.items() if k != "stage_id"}),
        "RUNTIME_STAGE_ID_INVALID",
    )
    requirement = _requirement()
    require(
        stage["decision"] == "AUTHORIZE_ANNUAL_RUNTIME_STAGE"
        and stage["approval_kind"] == "USER_DELEGATED_CONDITIONAL_STAGE_APPROVAL"
        and stage["requirement_id"] == REQUIREMENT_ID
        and stage["requirement_closure_hash"] == requirement["requirement_closure_hash"]
        and stage["policy"] == requirement["effective_decisions"][DECISION_ID]["choice"]
        and stage["maximum_provider_paid_sec_calls"] == [1, 1, 0]
        and stage["automatic_retry_count"] == 0
        and stage["publication_authorized"] is False
        and stage["long_running_schedule_authorized"] is False,
        "RUNTIME_STAGE_SCOPE_INVALID",
    )
    identity = code_identity()
    require(
        identity["runtime_tree"] == stage["reviewed_code"]["runtime_tree"],
        "RUNTIME_REVIEWED_CODE_CHANGED",
    )
    review = stage["independent_review"]
    require(
        review["reviewer_kind"] == "INDEPENDENT_MODEL_SUBTASK"
        and review["conclusion"] == "NO_BLOCKING_FINDINGS"
        and review["reviewed_head"] == stage["reviewed_code"]["exact_head"]
        and review["runtime_tree"] == identity["runtime_tree"],
        "RUNTIME_INDEPENDENT_REVIEW_REQUIRED",
    )
    # A later evidence-only commit/merge may run identical code. The actual
    # execution head is reported separately; arbitrary unrelated code cannot.
    require(
        _git("merge-base", stage["reviewed_code"]["exact_head"], "HEAD")
        == stage["reviewed_code"]["exact_head"],
        "RUNTIME_REVIEWED_HEAD_NOT_ANCESTOR",
    )
    _external(Path(stage["stage_root"]))
    verify_data_root(Path(stage["data_root"]), requirement)
    company = update.supported_company(repo_root=CODE_ROOT)
    old = stage["initial_candidate"]
    require(
        update.candidate_baseline(
            company=company, run_dir=Path(old["provenance"]["run_directory"])
        )
        == old,
        "RUNTIME_INITIAL_SUCCESS_CHANGED",
    )
    return requirement


def _github(path):
    return prior._github(path)


def _validate_owner_comment(*, comment, stage, approval_url=None):
    repository = _requirement()["baseline"]["repository"]["identity"]
    url = approval_url or comment.get("html_url", "")
    match = re.fullmatch(
        r"https://github\.com/"
        + re.escape(repository)
        + r"/issues/28#issuecomment-([1-9][0-9]*)",
        url,
    )
    require(match is not None, "RUNTIME_STAGE_APPROVAL_URL_INVALID")
    require(
        comment.get("html_url") == url
        and str(comment.get("id")) == match[1]
        and comment.get("issue_url")
        == "https://api.github.com/repos/" + repository + "/issues/28"
        and comment.get("user", {}).get("login") == repository.split("/")[0]
        and comment.get("created_at") == comment.get("updated_at")
        and strict_json_loads(text=comment.get("body", "")) == stage,
        "RUNTIME_STAGE_OWNER_PROVENANCE_INVALID",
    )
    parse_utc_timestamp(value=comment["created_at"])


def verify_stage(*, approval_url):
    """Reload a real owner issue comment; no PR existence or state dependency."""
    repository = _requirement()["baseline"]["repository"]["identity"]
    match = re.fullmatch(
        r"https://github\.com/"
        + re.escape(repository)
        + r"/issues/28#issuecomment-([1-9][0-9]*)",
        approval_url,
    )
    require(match is not None, "RUNTIME_STAGE_APPROVAL_URL_INVALID")
    comment = _github("repos/" + repository + "/issues/comments/" + match[1])
    stage = strict_json_loads(text=comment["body"])
    _validate_owner_comment(comment=comment, stage=stage, approval_url=approval_url)
    _validate_stage(stage)
    return {"stage": stage, "owner_comment": comment}


def prepare_plan(*, binding):
    stage = binding["stage"]
    requirement = _validate_stage(stage)
    data = Path(stage["data_root"])
    policy = stage["policy"]
    prepared = annual_input.prepare_annual_input(
        repo_root=data, company_id=policy["company_id"]
    )
    return _plan(
        stage=stage, requirement=requirement, prepared=prepared, source_root=data
    )


def _plan(*, stage, requirement, prepared, source_root):
    policy = stage["policy"]
    input_root = (
        Path(stage["stage_root"]) / "inputs" / prepared["input_id"].split(":")[1]
    )
    task = table_task_execution_plan(
        repo_root=CODE_ROOT, task_contract_id=policy["task_contract_id"]
    )
    body = {
        "record_type": "ANNUAL_RUNTIME_EXECUTION_PLAN",
        "schema_version": 1,
        "stage_id": stage["stage_id"],
        "requirement_id": REQUIREMENT_ID,
        "requirement_closure_hash": requirement["requirement_closure_hash"],
        "requirement_hashes": requirement["hashes"],
        "reviewed_code": stage["reviewed_code"],
        "data_root": str(input_root),
        "stage_root": stage["stage_root"],
        "prepared_input": prepared,
        "source_ledger": {
            name: {
                "sha256": sha256_file(path=source_root / "evidence" / name),
                "size": (source_root / "evidence" / name).stat().st_size,
            }
            for name in ("requests_log.csv", "requests_log_manifest.json")
        },
        "task_contract_id": policy["task_contract_id"],
        "task_binding": task["run_binding"],
        "request": _request(prepared, source_root, policy["task_contract_id"]),
        "maximum_new_executions": 1,
        "automatic_retry_count": 0,
        "actual_input_tokens_max": 200000,
        "qualification_credit": "NONE",
        "publication_credit": "NONE",
    }
    return {**body, "plan_id": content_hash(value=body)}


@dataclass(frozen=True, init=False)
class RuntimeAuthorization:
    _factory: object
    _bytes: bytes

    def __init__(self, *, factory, binding):
        require(factory is _FACTORY, "RUNTIME_VERIFIED_STAGE_REQUIRED")
        object.__setattr__(self, "_factory", factory)
        object.__setattr__(self, "_bytes", canonical_json_bytes(value=binding))


def _binding(authorization):
    require(
        type(authorization) is RuntimeAuthorization
        and authorization._factory is _FACTORY,
        "RUNTIME_AUTHORIZATION_REQUIRED",
    )
    return strict_json_loads(text=authorization._bytes.decode())


def _paths(plan):
    root = _external(Path(plan["stage_root"]))
    workspace = root / "candidates" / plan["plan_id"].split(":")[1]
    return (
        workspace,
        workspace / "b10",
        "run:annual-runtime:" + plan["plan_id"].split(":")[1],
    )


def authorization_fields(authorization):
    binding = _binding(authorization)
    stage = binding["stage"]
    plan = binding["plan"]
    requirement = _validate_stage(stage)
    _validate_owner_comment(comment=binding["owner_comment"], stage=stage)
    input_root = (
        Path(stage["stage_root"])
        / "inputs"
        / plan["prepared_input"]["input_id"].split(":")[1]
    )
    require(plan["data_root"] == str(input_root), "RUNTIME_INPUT_ROOT_MISMATCH")
    verify_data_root(input_root, requirement)
    prepared = annual_input.prepare_annual_input(
        repo_root=input_root, company_id=stage["policy"]["company_id"]
    )
    require(
        plan
        == _plan(
            stage=stage,
            requirement=requirement,
            prepared=prepared,
            source_root=input_root,
        ),
        "RUNTIME_PINNED_INPUT_CHANGED",
    )
    workspace, run_dir, run_id = _paths(plan)
    slot = resolve_repository_file(
        repo_root=Path(stage["stage_root"]), repo_relative_path="execution-slot.json"
    )
    require(
        strict_json_file(path=slot)
        == {"stage_id": stage["stage_id"], "plan_id": plan["plan_id"]},
        "RUNTIME_STAGE_ALREADY_CONSUMED",
    )
    return {
        "binding": binding,
        "plan": plan,
        "requirement": requirement,
        "workspace_dir": workspace,
        "run_dir": run_dir,
        "run_id": run_id,
        "owner_token": stage["stage_id"],
        "authorized_at_utc": binding["owner_comment"]["created_at"],
        "data_root": input_root,
    }


@dataclass(frozen=True, init=False)
class _RuntimeLiveRequest:
    request: object
    authorization: object
    _factory: object

    def __init__(self, *, factory, request, authorization):
        require(factory is _FACTORY, "RUNTIME_REQUEST_FACTORY_REQUIRED")
        object.__setattr__(self, "request", request)
        object.__setattr__(self, "authorization", authorization)
        object.__setattr__(self, "_factory", factory)


def wrap_live_request(*, authorization, request):
    authorization_fields(authorization)
    return _RuntimeLiveRequest(
        factory=_FACTORY, request=request, authorization=authorization
    )


def unwrap_live_request(*, request):
    if type(request) is not _RuntimeLiveRequest:
        return request, None
    require(request._factory is _FACTORY, "RUNTIME_REQUEST_FACTORY_REQUIRED")
    fields = authorization_fields(request.authorization)
    return request.request, fields["data_root"]


def validate_runtime_request_pair(*, adapter, request):
    """A runtime wrapper cannot authorize a generic or differently bound adapter."""
    auth = getattr(
        getattr(adapter, "invocation_context", None),
        "annual_candidate_authorization",
        None,
    )
    if type(request) is _RuntimeLiveRequest:
        require(
            request._factory is _FACTORY
            and type(auth) is RuntimeAuthorization
            and request.authorization is auth,
            "RUNTIME_REQUEST_ADAPTER_MISMATCH",
        )
    elif type(auth) is RuntimeAuthorization:
        raise AnnualRuntimeError("RUNTIME_BOUND_REQUEST_REQUIRED")


def validate_runtime_adapter_root(*, adapter, data_root):
    auth = getattr(
        getattr(adapter, "invocation_context", None),
        "annual_candidate_authorization",
        None,
    )
    fields = authorization_fields(auth)
    require(data_root == fields["data_root"], "RUNTIME_ADAPTER_ROOT_MISMATCH")


def validate_workflow_authorization(
    *, authorization, adapter, repo_root, run_dir, run_id, task_contract_id, **source
):
    fields = authorization_fields(authorization)
    plan = fields["plan"]
    context = adapter.invocation_context
    require(
        repo_root == fields["data_root"]
        and run_dir == fields["run_dir"]
        and run_id == fields["run_id"]
        and task_contract_id == plan["task_contract_id"]
        and source == plan["prepared_input"]["table_input"]
        and context.annual_candidate_authorization is authorization
        and context.qualification_usage_policy is None
        and context.workspace_dir == fields["workspace_dir"]
        and context.release_input_plan_id == plan["plan_id"]
        and context.owner_token == fields["owner_token"],
        "RUNTIME_WORKFLOW_BINDING_MISMATCH",
    )
    return fields


def write_run_binding(*, run_dir, authorization):
    fields = authorization_fields(authorization)
    require(
        run_dir == fields["run_dir"] and not (run_dir / BINDING_FILE).exists(),
        "RUNTIME_BINDING_EXISTS",
    )
    atomic_write_json(path=run_dir / BINDING_FILE, value=fields["binding"])


def validate_run_binding(*, repo_root, run_dir, manifest, records):
    binding = strict_json_file(
        path=resolve_repository_file(repo_root=run_dir, repo_relative_path=BINDING_FILE)
    )
    auth = RuntimeAuthorization(factory=_FACTORY, binding=binding)
    fields = authorization_fields(auth)
    plan = fields["plan"]
    require(
        repo_root == fields["data_root"]
        and run_dir == fields["run_dir"]
        and manifest["run_id"] == fields["run_id"]
        and manifest["record_type"] == "SUCCESSOR_RUN"
        and manifest["requirement_id"] == REQUIREMENT_ID
        and manifest["requirement_hashes"] == plan["requirement_hashes"]
        and manifest["requirement_closure_hash"] == plan["requirement_closure_hash"]
        and manifest["company_id"]
        == plan["prepared_input"]["table_input"]["company_id"]
        and manifest["target_period"]
        == plan["prepared_input"]["table_input"]["target_period"]
        and manifest["source_references"] == [plan["request"]["source_reference"]]
        and manifest["task_contract_bindings"] == [plan["task_binding"]]
        and manifest.get("qualification_authorization") is None,
        "RUNTIME_RUN_BINDING_MISMATCH",
    )
    attempts = [r for r in records if r["record_type"] == "AI_EXTRACTION_ATTEMPT"]
    require(len(attempts) <= 1, "RUNTIME_ATTEMPT_COUNT_INVALID")
    for attempt in attempts:
        require(
            "qualification_authorization" not in attempt,
            "RUNTIME_QUALIFICATION_FORBIDDEN",
        )
        require(
            sha256_file(path=run_dir / attempt["request_body_path"])
            == plan["request"]["provider_request_body_sha256"],
            "RUNTIME_PERSISTED_REQUEST_CHANGED",
        )
        if attempt["status"] == "SUCCEEDED":
            require(
                not prior.usage_error(
                    (run_dir / attempt["raw_response_path"]).read_bytes()
                ),
                "RUNTIME_USAGE_INVALID",
            )
        _validate_terminal(fields=fields, attempt=attempt)


def _validate_terminal(*, fields, attempt):
    from . import invocation_control as controller

    if not attempt["transport_observation"]["egress_attempted"]:
        require(attempt["status"] == "FAILED", "RUNTIME_HISTORICAL_RESPONSE_FORBIDDEN")
        return
    plan = fields["plan"]
    root = fields["workspace_dir"] / "invocation_control"
    plans = list((root / "plans").glob("*.json"))
    require(
        len(plans) == 1 and not plans[0].is_symlink(), "RUNTIME_CONTROLLER_PLAN_MISSING"
    )
    invocation = strict_json_file(path=plans[0])
    authority = controller.prepare_annual_candidate_invocation_authority(
        requirement=fields["requirement"], repo_root=CODE_ROOT
    )
    with controller._successor_plan_context(repo_root=CODE_ROOT, authority=authority):
        controller.validate_ai_invocation_plan(plan=invocation)
        require(
            invocation["release_input_plan_id"] == plan["plan_id"]
            and invocation["provider_request_body_sha256"]
            == plan["request"]["provider_request_body_sha256"]
            and invocation["source_identity_hash"]
            == plan["request"]["reader_input_manifest_id"]
            and invocation["selected_representation_hash"]
            == plan["request"]["derived_asset_id"],
            "RUNTIME_CONTROLLER_PLAN_MISMATCH",
        )
        eid = controller.execution_identity(
            ai_invocation_plan_id=invocation["ai_invocation_plan_id"],
            owner_token=fields["owner_token"],
            authorized_at_utc=fields["authorized_at_utc"],
        )
        receipt = controller._load_execution_receipt(
            root=root,
            path=controller._execution_path(root=root, execution_id=eid),
            execution_id=eid,
        )
        markers = controller._egress_markers_for_execution(root=root, execution_id=eid)
        require(
            len(markers) == 1
            and markers[0]["attempt_ordinal"] == 1
            and receipt["counters"]
            == controller._counters_from_egress_markers(
                markers=markers, plan=invocation
            ),
            "RUNTIME_CONTROLLER_COUNTERS_INVALID",
        )
        if attempt["status"] == "SUCCEEDED":
            from .ai_adapter import _controller_usage

            saved = controller.load_successful_response(
                workspace_dir=fields["workspace_dir"], plan=invocation
            )
            require(
                receipt["status"] == "SUCCEEDED"
                and len(receipt["attempts"]) == 1
                and saved["provider_request_id"] == attempt["provider_request_id"]
                and sha256_bytes(content=saved["response_body"])
                == attempt["assistant_output_sha256"]
                and receipt["attempts"][0]["usage"]
                == _controller_usage(
                    raw_response_bytes=(
                        fields["run_dir"] / attempt["raw_response_path"]
                    ).read_bytes()
                ),
                "RUNTIME_RESPONSE_EXECUTION_MISMATCH",
            )
        else:
            require(
                receipt["status"]
                in {
                    "UNKNOWN_REMOTE_OUTCOME",
                    "FAILED_TERMINAL",
                    "FAILED_RETRYABLE_FINAL",
                },
                "RUNTIME_FAILURE_TERMINAL_MISMATCH",
            )


def stage_counts(stage_root):
    """Count durable WB-3 markers, including terminals without a Run."""
    root = _external(stage_root)
    markers = list(root.glob("candidates/*/invocation_control/egress/*/*.json"))
    provider, paid = 0, 0
    for path in markers:
        marker = strict_json_file(
            path=resolve_repository_file(
                repo_root=root, repo_relative_path=path.relative_to(root).as_posix()
            )
        )
        require(
            marker.get("egress_marker_id")
            == content_hash(
                value={k: v for k, v in marker.items() if k != "egress_marker_id"}
            )
            and marker.get("transport_kind") == "REAL_MODEL_PROVIDER"
            and marker.get("paid_model_provider_call_observed") is True,
            "RUNTIME_STAGE_COUNT_UNCERTAIN",
        )
        provider += 1
        paid += 1
    require(provider <= 1 and paid <= 1, "RUNTIME_STAGE_BUDGET_EXCEEDED")
    return [provider, paid, 0]


def _exclusive_slot(stage, plan):
    root = _external(Path(stage["stage_root"]))
    root.mkdir(parents=True, exist_ok=True)
    path = root / "execution-slot.json"
    require(
        not (root / "candidates").exists()
        and not (root / "stage-approval.json").exists()
        and not (root / "inputs").exists(),
        "RUNTIME_CONSUMPTION_EVIDENCE_WITHOUT_SLOT",
    )
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as error:
        raise AnnualRuntimeError("RUNTIME_STAGE_ALREADY_CONSUMED") from error
    with os.fdopen(descriptor, "wb") as out:
        out.write(
            canonical_json_bytes(
                value={"stage_id": stage["stage_id"], "plan_id": plan["plan_id"]}
            )
        )
        out.flush()
        os.fsync(out.fileno())


def _credential_error():
    """Missing local credentials do not consume the stage's execution slot."""
    from .ai_adapter import _load_transport_policy, api_key_environment_name
    from .ai_adapter import api_key_required_error_code

    policy, _ = _load_transport_policy()
    if not os.environ.get(api_key_environment_name(policy=policy), "").strip():
        return api_key_required_error_code(policy=policy)
    return ""


def run_update(*, approval_url):
    """Inspect, prepare, execute if needed, and retain explicit candidate refs."""
    from .ai_adapter import build_annual_candidate_transport_adapter
    from .batch_workflow import create_companyfacts_release_run
    from .workflow import create_table_task_review_run, finalize_reviewed_direct_results
    from .run_store import load_run_for_status, _mechanically_replay_open_run

    binding = verify_stage(approval_url=approval_url)
    stage = binding["stage"]
    root = Path(stage["stage_root"])
    company = update.supported_company(repo_root=CODE_ROOT)
    published = update.published_baseline(company=company, publication_root=CODE_ROOT)
    old = stage["initial_candidate"]
    baseline = old
    success = root / "successful-candidate.json"
    if success.exists():
        ref = strict_json_file(
            path=resolve_repository_file(
                repo_root=root, repo_relative_path=success.name
            )
        )
        baseline = update.candidate_baseline(
            company=company, run_dir=Path(ref["run_directory"])
        )
        saved = strict_json_file(
            path=resolve_repository_file(
                repo_root=root, repo_relative_path="stage-approval.json"
            )
        )
        plan = saved["plan"]
        workspace, b10, expected_id = _paths(plan)
        require(
            saved["stage"] == stage
            and saved["owner_comment"] == binding["owner_comment"]
            and ref
            == {
                "run_directory": str(b10),
                "run_id": expected_id,
                "stage_id": stage["stage_id"],
                "b01_run_directory": str(workspace / "b01"),
            }
            and baseline["run_id"] == expected_id,
            "RUNTIME_SUCCESS_REFERENCE_CHANGED",
        )
        _mechanically_replay_open_run(
            run_dir=b10,
            repo_root=Path(plan["data_root"]),
            require_complete_results=False,
        )
        _mechanically_replay_open_run(
            run_dir=workspace / "b01",
            repo_root=Path(plan["data_root"]),
            require_complete_results=False,
        )
        _, structured_records, _ = load_run_for_status(
            run_dir=workspace / "b01", repo_root=Path(plan["data_root"])
        )
        b01 = [
            r
            for r in structured_records
            if r["record_type"] == "METRIC_RESULT" and r["metric_id"] == "B01"
        ]
        require(
            len(b01) == 1
            and b01[0]["reason_code"] == "PASS"
            and b01[0]["publication"] == "PUBLISHED"
            and b01[0]["period_end"] == baseline["filing"]["period_end"],
            "RUNTIME_BOTH_METRICS_SUCCESS_REQUIRED",
        )
    report = update.inspect_annual_update(
        repo_root=Path(stage["data_root"]),
        company=company,
        successful_candidate=baseline,
    )
    report.update(
        stage_id=stage["stage_id"],
        baseline_mode=stage["baseline_mode"],
        old_successful_candidate=old,
        current_published=published,
        new_candidate=None,
        execution_code=code_identity(),
        reviewed_code=stage["reviewed_code"],
    )
    if report["status"] != "INPUT_READY":
        report["stage_provider_paid_sec_calls"] = stage_counts(root)
        return report
    plan = prepare_plan(binding=binding)
    binding = {**binding, "plan": plan}
    workspace, b10, run_id = _paths(plan)
    if (root / "execution-slot.json").exists():
        report.update(
            status="STAGE_STOPPED",
            execution="NOT_EXECUTED",
            error="RUNTIME_STAGE_ALREADY_CONSUMED",
            stage_provider_paid_sec_calls=stage_counts(root),
        )
        return report
    require(
        plan["prepared_input"] == report["prepared_input"],
        "RUNTIME_INPUT_CHANGED_DURING_CHECK",
    )
    credential_error = _credential_error()
    if credential_error:
        report.update(
            status="STAGE_BLOCKED",
            execution="NOT_EXECUTED",
            error=credential_error,
            stage_provider_paid_sec_calls=stage_counts(root),
        )
        return report
    _exclusive_slot(stage, plan)
    _copy_inputs(
        source_root=Path(stage["data_root"]),
        data_root=Path(plan["data_root"]),
        prepared=plan["prepared_input"],
        requirement=_requirement(),
    )
    workspace.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path=workspace / "plan.json", value=plan)
    atomic_write_json(path=root / "stage-approval.json", value=binding)
    authorization = RuntimeAuthorization(factory=_FACTORY, binding=binding)
    structured = create_companyfacts_release_run(
        repo_root=Path(plan["data_root"]),
        run_dir=workspace / "b01",
        run_id=run_id + ":structured",
        **plan["prepared_input"]["companyfacts_input"]
    )
    structured_manifest, structured_records, _ = load_run_for_status(
        run_dir=workspace / "b01", repo_root=Path(plan["data_root"])
    )
    b01_result = next(
        r
        for r in structured_records
        if r["record_type"] == "METRIC_RESULT" and r["metric_id"] == "B01"
    )
    report["structured_candidate"] = {
        "run_directory": str(workspace / "b01"),
        "B01": b01_result,
        "source_references": structured_manifest["source_references"],
        "native_attached_metric_ids": sorted(
            k for k in structured["results"] if k != "B01"
        ),
    }
    adapter = build_annual_candidate_transport_adapter(authorization=authorization)
    created = create_table_task_review_run(
        repo_root=Path(plan["data_root"]),
        run_dir=b10,
        run_id=run_id,
        task_contract_id=plan["task_contract_id"],
        adapter=adapter,
        clock=None,
        candidate_authorization=authorization,
        **plan["prepared_input"]["table_input"]
    )
    if created["status"] == "PENDING_HUMAN_REVIEW":
        finalize_reviewed_direct_results(repo_root=Path(plan["data_root"]), run_dir=b10)
    _mechanically_replay_open_run(
        run_dir=b10, repo_root=Path(plan["data_root"]), require_complete_results=False
    )
    manifest, records, decisions = load_run_for_status(
        run_dir=b10, repo_root=Path(plan["data_root"])
    )
    results = [r for r in records if r["record_type"] == "METRIC_RESULT"]
    good = [
        r
        for r in results
        if r["metric_id"] == "B10"
        and r["reason_code"] == "PASS"
        and r["publication"] == "PUBLISHED"
    ]
    success_b01 = (
        b01_result["reason_code"] == "PASS" and b01_result["publication"] == "PUBLISHED"
    )
    report.update(
        status="CANDIDATE_UPDATE_SUCCEEDED"
        if good and success_b01
        else "CANDIDATE_UPDATE_FAILED",
        execution="EXECUTED",
        new_candidate={
            "run_directory": str(b10),
            "run_id": run_id,
            "run_status": manifest["status"],
            "results": results,
            "attempts": [
                r for r in records if r["record_type"] == "AI_EXTRACTION_ATTEMPT"
            ],
            "reviewers": [d["reviewer_type"] for d in decisions],
        },
        stage_provider_paid_sec_calls=stage_counts(root),
    )
    report["provider_paid_sec_calls"] = report["stage_provider_paid_sec_calls"]
    if report["status"] == "CANDIDATE_UPDATE_SUCCEEDED":
        new = update.candidate_baseline(company=company, run_dir=b10)
        report["new_successful_candidate"] = new
        atomic_write_json(
            path=success,
            value={
                "run_directory": str(b10),
                "run_id": run_id,
                "stage_id": stage["stage_id"],
                "b01_run_directory": str(workspace / "b01"),
            },
        )
    atomic_write_json(path=workspace / "outcome.json", value=report)
    return report
