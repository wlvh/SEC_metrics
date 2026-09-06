"""R4 production execution composition, dormant without exact-head authority.

PR-C can invoke these frozen Python entrypoints to plan/execute/replay. This
module never acquires SEC sources, edits a Requirement, freezes production
semantics, creates Stage-A, switches publication or grants authority itself.
Recorded transports exercise the same invocation/Run graph with zero sockets.
"""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

from .canonical import canonical_json_bytes, content_hash, sha256_bytes, strict_json_loads
from .invocation_control import _exclusive_write_json
from .r4_live_authority import R4AuthorizationError, R4ExecutionPlanContext
from .r4_live_authority import RUNTIME_ROOT, VerifiedR4OwnerComment
from .r4_live_authority import authorization_fields, authorize_r4_live_entry
from .r4_live_authority import authorize_r4_recorded_test_entry, prepare_r4_execution_context
from .r4_live_authority import validate_r4_execution_plan
from .sources import resolve_repository_file


TERMINAL_FIELDS = {"record_type", "schema_version", "terminal_id", "pending_plan_id", "entry_id",
    "ordinal", "fixture_id", "execution_mode", "status", "run_id", "run_path", "run_status",
    "execution_receipt_id", "execution_status", "counters", "qualification_credit",
    "publication_credit", "response_reuse_authorized", "files"}


class R4QualificationError(ValueError):
    """Reject incomplete execution prefixes, mutated terminals or missing authority."""


def _identity_name(value):
    if (type(value) is not str or not value.startswith("sha256:") or len(value) != 71
            or any(character not in "0123456789abcdef" for character in value[7:])):
        raise R4QualificationError("R4 runtime content identity is malformed")
    return value[7:]


def _entry_root(context, plan, entry_id):
    return _runtime_path(context, RUNTIME_ROOT + "/" + _identity_name(plan["pending_plan_id"])
                         + "/entries/" + _identity_name(entry_id))


def _runtime_path(context, relative):
    """Reject every lexical ancestor before any native Run or terminal write."""
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise R4QualificationError("R4 runtime path is not repository-relative")
    current = context._root
    for part in path.parts:
        current /= part
        if current.is_symlink() or (current.exists() and not current.is_dir()):
            raise R4QualificationError("R4 runtime directory has an unsafe ancestor")
    return current


def _read_json(path):
    if path.is_symlink() or not path.is_file():
        raise R4QualificationError("R4 runtime object is absent or unsafe: " + path.name)
    return strict_json_loads(text=path.read_text(encoding="utf-8"))


def _tree_files(root):
    if root.is_symlink() or not root.is_dir():
        raise R4QualificationError("R4 execution entry is unsafe")
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or (not path.is_file() and not path.is_dir()):
            raise R4QualificationError("R4 execution tree contains a non-regular entry")
        if path.is_file() and path != root / "qualification_terminal.json":
            data = path.read_bytes()
            files[path.relative_to(root).as_posix()] = {"sha256": sha256_bytes(content=data), "size": len(data)}
    return files


def _validated_terminal(*, context, plan, entry, require_success):
    root = _entry_root(context, plan, entry["entry_id"])
    terminal = _read_json(root / "qualification_terminal.json")
    if type(terminal) is not dict or set(terminal) != TERMINAL_FIELDS:
        raise R4QualificationError("R4 qualification terminal fields differ")
    if (terminal["record_type"] != "R4_QUALIFICATION_ENTRY_TERMINAL"
            or type(terminal["schema_version"]) is not int or terminal["schema_version"] != 1
            or terminal["terminal_id"] != content_hash(value={k: v for k, v in terminal.items() if k != "terminal_id"})
            or terminal["pending_plan_id"] != plan["pending_plan_id"]
            or terminal["entry_id"] != entry["entry_id"] or terminal["ordinal"] != entry["ordinal"]
            or terminal["fixture_id"] != entry["fixture_id"] or terminal["execution_mode"] != plan["execution_mode"]
            or terminal["qualification_credit"] != "NONE_INDIVIDUAL_RUN"
            or terminal["publication_credit"] != "NONE" or terminal["response_reuse_authorized"] is not False
            or terminal["run_path"] != (root / "run").relative_to(context._root).as_posix()):
        raise R4QualificationError("R4 qualification terminal binding differs")
    if terminal["files"] != _tree_files(root):
        raise R4QualificationError("R4 sealed terminal files changed, were added or removed")
    if require_success and (terminal["status"] != "PASSED" or terminal["run_status"] != "FROZEN"
                            or terminal["execution_status"] != "SUCCEEDED"):
        raise R4QualificationError("Prior R4 failure/UNKNOWN blocks all later entries")
    pinned = context._terminal_pins.get(entry["entry_id"])
    if pinned is not None:
        if pinned != terminal:
            raise R4QualificationError("R4 completed terminal changed during session")
        return terminal
    # A resumed process replays each prior Run once, never once per child.
    from .live_scoped_reader import build_scoped_invocation_acceptance_context
    from .r4_run_store import replay_r4_scoped_run
    acceptance = build_scoped_invocation_acceptance_context(request=context._requests[entry["fixture_id"]],
                                                           execution_context=context)
    replayed = replay_r4_scoped_run(repo_root=context._root, run_dir=root / "run", acceptance_context=acceptance)
    if replayed["run_id"] != terminal["run_id"] or replayed["run_status"] != terminal["run_status"]:
        raise R4QualificationError("R4 native frozen Run differs from qualification terminal")
    manifest = _read_json(root / "run/manifest.json")
    artifacts = manifest["r4_execution_binding"]["artifact_files"]
    execution = _read_json(root / "run" / artifacts["execution_receipt"]["path"])
    authorization = _read_json(root / "run" / artifacts["authorization_binding"]["path"])
    if (execution["execution_receipt_id"] != terminal["execution_receipt_id"]
            or execution["status"] != terminal["execution_status"] or execution["counters"] != terminal["counters"]
            or authorization["pending_plan_id"] != plan["pending_plan_id"]
            or authorization["entry_id"] != entry["entry_id"]):
        raise R4QualificationError("R4 native invocation terminal differs from entry summary")
    context._terminal_pins[entry["entry_id"]] = terminal
    return terminal


def _structured_terminals(*, context, plan, create=False):
    """Persist/replay the three structured positives, never as provider entries."""
    from .r4_structured_run import create_and_freeze_r4_structured_run
    from .r4_structured_run import prepare_r4_structured_run_context, replay_r4_structured_run
    fixtures = [entry for entry in plan.get("zero_call_fixtures", [])
                if entry["artifact_kind"] == "STRUCTURED_PRIMARY"]
    parent = _runtime_path(context, RUNTIME_ROOT + "/" + _identity_name(plan["pending_plan_id"]) + "/structured")
    if parent.exists() and (parent.is_symlink() or not parent.is_dir()
            or any(p.is_symlink() or not p.is_dir() or p.name not in {f["fixture_id"] for f in fixtures}
                   for p in parent.iterdir())):
        raise R4QualificationError("R4 structured terminal namespace differs from the exact fixture set")
    results = []
    for fixture in fixtures:
        root = parent / fixture["fixture_id"]
        terminal_path = root / "qualification_terminal.json"
        cache_key = "structured:" + fixture["fixture_id"]
        if create and not terminal_path.exists():
            manifest = create_and_freeze_r4_structured_run(repo_root=context._root, run_dir=root / "run",
                fixture_id=fixture["fixture_id"], plan=plan, execution_context=context)
            body = {"record_type": "R4_STRUCTURED_QUALIFICATION_TERMINAL", "schema_version": 1,
                "pending_plan_id": plan["pending_plan_id"], "fixture_id": fixture["fixture_id"],
                "run_id": manifest["run_id"], "run_status": manifest["status"],
                "execution_mode": plan["execution_mode"], "provider_paid_sec_calls": [0, 0, 0],
                "qualification_credit": "NONE_INDIVIDUAL_RUN", "publication_credit": "NONE",
                "files": _tree_files(root)}
            terminal = {**body, "terminal_id": content_hash(value=body)}
            _exclusive_write_json(path=terminal_path, value=terminal)
            context._terminal_pins[cache_key] = terminal
        terminal = _read_json(terminal_path)
        if (set(terminal) != {"record_type", "schema_version", "terminal_id", "pending_plan_id", "fixture_id",
                "run_id", "run_status", "execution_mode", "provider_paid_sec_calls", "qualification_credit",
                "publication_credit", "files"}
                or terminal["record_type"] != "R4_STRUCTURED_QUALIFICATION_TERMINAL"
                or type(terminal["schema_version"]) is not int or terminal["schema_version"] != 1
                or terminal["terminal_id"] != content_hash(value={k: v for k, v in terminal.items() if k != "terminal_id"})
                or terminal["pending_plan_id"] != plan["pending_plan_id"] or terminal["fixture_id"] != fixture["fixture_id"]
                or terminal["execution_mode"] != plan["execution_mode"] or terminal["run_status"] != "FROZEN"
                or terminal["provider_paid_sec_calls"] != [0, 0, 0]
                or any(type(v) is not int for v in terminal["provider_paid_sec_calls"])
                or terminal["qualification_credit"] != "NONE_INDIVIDUAL_RUN" or terminal["publication_credit"] != "NONE"
                or terminal["files"] != _tree_files(root)):
            raise R4QualificationError("R4 structured native terminal binding/bytes differ")
        if cache_key in context._terminal_pins:
            if context._terminal_pins[cache_key] != terminal:
                raise R4QualificationError("Structured terminal changed during execution session")
        else:
            structured_context = prepare_r4_structured_run_context(repo_root=context._root,
                fixture_id=fixture["fixture_id"], plan=plan, execution_context=context)
            replay = replay_r4_structured_run(repo_root=context._root, run_dir=root / "run",
                                              structured_context=structured_context)
            if replay["run_id"] != terminal["run_id"] or replay["run_status"] != "FROZEN":
                raise R4QualificationError("Native structured replay differs from qualification terminal")
            context._terminal_pins[cache_key] = terminal
        results.append(terminal)
    return results


def validate_r4_execution_prefix(*, context, plan, entry_id, for_socket=False):
    """Socket-adjacent ordering gate; an orchestration-loop check is insufficient."""
    if type(context) is not R4ExecutionPlanContext:
        raise R4QualificationError("R4 prefix requires its exact repository context")
    matches = [entry for entry in plan["entries"] if entry["entry_id"] == entry_id]
    if len(matches) != 1:
        raise R4QualificationError("R4 prefix entry is absent or ambiguous")
    current = matches[0]
    _structured_terminals(context=context, plan=plan)
    expected_names = {_identity_name(entry["entry_id"]) for entry in plan["entries"]}
    entries_dir = _entry_root(context, plan, entry_id).parent
    if entries_dir.exists():
        if entries_dir.is_symlink() or not entries_dir.is_dir():
            raise R4QualificationError("R4 prefix namespace is unsafe")
        for directory in entries_dir.iterdir():
            if directory.is_symlink() or not directory.is_dir() or directory.name not in expected_names:
                raise R4QualificationError("Unknown R4 execution namespace is not in the exact plan")
    for entry in plan["entries"]:
        if entry["ordinal"] < current["ordinal"]:
            _validated_terminal(context=context, plan=plan, entry=entry, require_success=True)
        elif entry["ordinal"] > current["ordinal"]:
            later = _entry_root(context, plan, entry["entry_id"])
            if later.exists() and any(later.iterdir()):
                raise R4QualificationError("Later R4 execution exists before the requested entry")
    if for_socket:
        root = _entry_root(context, plan, entry_id)
        executions = root / "invocation_control/executions"
        if (root / "qualification_terminal.json").exists() or (executions.exists() and any(executions.iterdir())):
            raise R4QualificationError("R4 entry already terminal; a second socket is forbidden")
        markers = list((root / "invocation_control/egress").rglob("*.json"))
        if len(markers) != 1:
            raise R4QualificationError("R4 socket requires its sole reservation-owned marker")
    return {"prior_terminal_count": current["ordinal"] - 1, "entry_ordinal": current["ordinal"]}


def _seal_terminal(*, context, plan, entry, run_manifest, attempt_result):
    root = _entry_root(context, plan, entry["entry_id"])
    execution = attempt_result.execution_receipt
    success = run_manifest["status"] == "FROZEN" and execution["status"] == "SUCCEEDED"
    body = {"record_type": "R4_QUALIFICATION_ENTRY_TERMINAL", "schema_version": 1,
        "pending_plan_id": plan["pending_plan_id"], "entry_id": entry["entry_id"],
        "ordinal": entry["ordinal"], "fixture_id": entry["fixture_id"], "execution_mode": plan["execution_mode"],
        "status": "PASSED" if success else "FAILED", "run_id": run_manifest["run_id"],
        "run_path": (root / "run").relative_to(context._root).as_posix(), "run_status": run_manifest["status"],
        "execution_receipt_id": execution["execution_receipt_id"], "execution_status": execution["status"],
        "counters": execution["counters"], "qualification_credit": "NONE_INDIVIDUAL_RUN",
        "publication_credit": "NONE", "response_reuse_authorized": False, "files": _tree_files(root)}
    terminal = {**body, "terminal_id": content_hash(value=body)}
    _exclusive_write_json(path=root / "qualification_terminal.json", value=terminal)
    # Already natively checked by finalization. Later siblings only hash these exact bytes.
    context._terminal_pins[entry["entry_id"]] = terminal
    return terminal


def _execution_summary(*, context, plan, terminals, structured):
    """One exact summary builder shared by execution and independent replay."""
    mode = plan["execution_mode"]
    counters = {key: sum(t["counters"][key] for t in terminals) for key in
                ("real_model_provider_egress_count", "paid_model_provider_call_count", "mock_transport_invocation_count")}
    expected = (12, 12, 0) if mode == "LIVE" else (0, 0, 12)
    if (tuple(counters.values()) != expected or len({t["execution_receipt_id"] for t in terminals}) != 12
            or len(structured) != 3):
        raise R4QualificationError("R4 exact twelve fresh executions/accounting differs")
    body = {"record_type": "R4_QUALIFICATION_EXECUTION_SUMMARY", "schema_version": 1,
        "pending_plan_id": plan["pending_plan_id"], "requirement_id": plan["requirement_id"],
        "requirement_closure_hash": plan["requirement_closure_hash"], "execution_mode": mode,
        "status": "PASSED_RECORDED_ONLY" if mode == "RECORDED_TEST" else "PASSED_PENDING_INDEPENDENT_REPLAY",
        "terminal_ids": [t["terminal_id"] for t in terminals], "counters": counters, "sec_calls": 0,
        "structured_terminal_ids": [t["terminal_id"] for t in structured],
        "zero_call_fixtures": plan["zero_call_fixtures"], "stability_selection": plan["stability_selection"],
        "response_reuse_authorized": False, "publication_credit": "NONE",
        "qualification_credit": "NONE_RECORDED_TEST" if mode == "RECORDED_TEST" else "PENDING_INDEPENDENT_REPLAY",
        "active_publication_id": context._pointer["publication_id"]}
    return {**body, "summary_id": content_hash(value=body)}


def _existing_run_attempt(*, run_dir, plan, entry, attempt_result=None):
    """Compare native persisted execution bytes before completing a crash gap."""
    manifest = _read_json(run_dir / "manifest.json")
    artifacts = manifest.get("r4_execution_binding", {}).get("artifact_files", {})
    auth_file = artifacts.get("authorization_binding")
    if type(auth_file) is not dict:
        raise R4QualificationError("Existing R4 Run has no exact execution binding")
    path = resolve_repository_file(repo_root=run_dir, repo_relative_path=auth_file["path"])
    data = path.read_bytes()
    if {"sha256": sha256_bytes(content=data), "size": len(data)} != {k: auth_file[k] for k in ("sha256", "size")}:
        raise R4QualificationError("Existing R4 Run authorization bytes differ")
    auth = strict_json_loads(text=data.decode("utf-8"))
    if auth.get("pending_plan_id") != plan["pending_plan_id"] or auth.get("entry_id") != entry["entry_id"]:
        raise R4QualificationError("Existing R4 Run belongs to a different plan entry")
    if attempt_result is None:
        return
    values = {"request_record": attempt_result.request_identity,
        "invocation_plan": attempt_result.invocation_plan, "execution_receipt": attempt_result.execution_receipt,
        "acceptance_receipt": attempt_result.acceptance_receipt,
        "authorization_binding": attempt_result.authorization_binding, "terminal_bundle": attempt_result.terminal_bundle}
    for kind, value in values.items():
        binding = artifacts.get(kind)
        if value is None:
            if binding is not None:
                raise R4QualificationError("Existing R4 failure contains acceptance bytes")
            continue
        if type(binding) is not dict:
            raise R4QualificationError("Existing R4 execution artifact is incomplete")
        expected = canonical_json_bytes(value=dict(value))
        actual = resolve_repository_file(repo_root=run_dir, repo_relative_path=binding["path"]).read_bytes()
        if actual != expected or binding["sha256"] != sha256_bytes(content=expected) or binding["size"] != len(expected):
            raise R4QualificationError("Existing R4 Run differs from the same recovered invocation: " + kind)


def execute_r4_qualification(*, repo_root: Path, plan: Mapping, owner_comment=None,
                             recorded_transports=None, context=None, clock=None):
    """Execute the frozen engine, LIVE only with verified exact-head owner capability."""
    from .ai_adapter import build_scoped_qualification_transport_adapter, run_scoped_ai_attempt
    from .live_scoped_reader import build_scoped_invocation_acceptance_context
    from .r4_run_store import create_r4_scoped_run, finalize_r4_scoped_run
    if context is None:
        context = prepare_r4_execution_context(repo_root=repo_root)
    if type(context) is not R4ExecutionPlanContext or context._root != repo_root.resolve():
        raise R4QualificationError("R4 execution repository/context differs")
    mode = plan.get("execution_mode")
    validate_r4_execution_plan(plan=plan, context=context,
        expected_plan_id=plan.get("pending_plan_id"), mode=mode)
    if mode == "LIVE":
        if type(owner_comment) is not VerifiedR4OwnerComment or recorded_transports is not None:
            raise R4AuthorizationError("R4 live execution requires a verified owner comment, not raw receipt fields")
    elif mode != "RECORDED_TEST" or owner_comment is not None or type(recorded_transports) is not dict:
        raise R4AuthorizationError("R4 recorded/live execution types cannot be mixed")
    if mode == "RECORDED_TEST" and set(recorded_transports) != {entry["entry_id"] for entry in plan["entries"]}:
        raise R4QualificationError("Recorded transport exact entry set differs")
    # Native structured route first. Three resolved positives and four exclusion
    # classes remain model-zero; no synthetic response is consumed as live credit.
    verified = context._session.validate_full_corpus()
    if len(verified) != 16 or len(plan["zero_call_fixtures"]) != 7:
        raise R4QualificationError("R4 full fixture/zero-call closure is incomplete")
    structured = _structured_terminals(context=context, plan=plan, create=True)
    if len(structured) != 3:
        raise R4QualificationError("R4 requires exactly three native structured-primary terminals")
    terminals = []
    for entry in plan["entries"]:
        context._check()
        root = _entry_root(context, plan, entry["entry_id"])
        if (root / "qualification_terminal.json").exists():
            terminal = _validated_terminal(context=context, plan=plan, entry=entry, require_success=True)
            terminals.append(terminal)
            continue
        validate_r4_execution_prefix(context=context, plan=plan, entry_id=entry["entry_id"])
        if (root / "run").exists():
            _existing_run_attempt(run_dir=root / "run", plan=plan, entry=entry)
        authorization = (authorize_r4_live_entry(context=context, plan=plan, entry_id=entry["entry_id"],
            owner_receipt=owner_comment) if mode == "LIVE" else authorize_r4_recorded_test_entry(
                context=context, plan=plan, entry_id=entry["entry_id"]))
        fields = authorization_fields(authorization)
        if fields["invocation_workspace"] != root:
            raise R4QualificationError("R4 invocation workspace differs from plan-owned entry")
        request = context._requests[entry["fixture_id"]]
        acceptance = build_scoped_invocation_acceptance_context(request=request, execution_context=context)
        adapter = build_scoped_qualification_transport_adapter(authorization=authorization,
            recorded_transport=None if mode == "LIVE" else recorded_transports[entry["entry_id"]])
        attempt = run_scoped_ai_attempt(adapter=adapter, prepared_request=request,
                                       acceptance_context=acceptance, clock=clock)
        run_dir = root / "run"
        if not run_dir.exists():
            create_r4_scoped_run(repo_root=repo_root, run_dir=run_dir, attempt_result=attempt,
                                 acceptance_context=acceptance)
        elif run_dir.is_symlink() or not (run_dir / "manifest.json").is_file():
            raise R4QualificationError("Existing R4 Run is incomplete or unsafe")
        else:
            _existing_run_attempt(run_dir=run_dir, plan=plan, entry=entry, attempt_result=attempt)
        # Existing OPEN/FROZEN owned Runs go through native exact graph replay;
        # incomplete/mutated records still fail closed, without another socket.
        manifest = finalize_r4_scoped_run(repo_root=repo_root, run_dir=root / "run", acceptance_context=acceptance)
        terminal = _seal_terminal(context=context, plan=plan, entry=entry, run_manifest=manifest,
                                  attempt_result=attempt)
        terminals.append(terminal)
        if terminal["status"] != "PASSED":
            raise R4QualificationError("R4 execution stopped on terminal " + terminal["execution_status"])
    context._check()
    result = _execution_summary(context=context, plan=plan, terminals=terminals, structured=structured)
    _exclusive_write_json(path=_runtime_path(context, RUNTIME_ROOT + "/" + _identity_name(plan["pending_plan_id"]))
                          / "execution_summary.json", value=result)
    return result


def replay_r4_qualification(*, repo_root: Path, plan, context=None):
    """Independent disk replay; caller must supply a new disk-owned source session."""
    if context is None:
        context = prepare_r4_execution_context(repo_root=repo_root)
    if context._terminal_pins:
        raise R4QualificationError("Independent R4 replay cannot reuse an execution prefix cache")
    validate_r4_execution_plan(plan=plan, context=context,
        expected_plan_id=plan.get("pending_plan_id"), mode=plan.get("execution_mode"))
    verified = context._session.validate_full_corpus()
    structured = _structured_terminals(context=context, plan=plan)
    terminals = [_validated_terminal(context=context, plan=plan, entry=entry, require_success=True)
                 for entry in plan["entries"]]
    summary_path = _runtime_path(context, RUNTIME_ROOT + "/" + _identity_name(plan["pending_plan_id"])) / "execution_summary.json"
    summary = _read_json(summary_path)
    if summary != _execution_summary(context=context, plan=plan, terminals=terminals, structured=structured):
        raise R4QualificationError("R4 aggregate terminal summary differs from independent Run replay")
    context._check()
    body = {"record_type": "R4_QUALIFICATION_DISK_REPLAY", "schema_version": 1,
        "pending_plan_id": plan["pending_plan_id"], "summary_id": summary["summary_id"],
        "status": "PASSED", "execution_mode": plan["execution_mode"],
        "replayed_run_count": len(terminals) + len(structured),
        "scoped_run_count": len(terminals), "structured_run_count": len(structured),
        "verified_fixture_count": len(verified), "provider_paid_sec_calls": [0, 0, 0],
        "publication_credit": "NONE", "active_publication_id": context._pointer["publication_id"],
        "qualification_credit": "NONE_RECORDED_TEST" if plan["execution_mode"] == "RECORDED_TEST"
            else "EXACT_PLAN_LIVE_QUALIFICATION_ONLY"}
    return {**body, "replay_id": content_hash(value=body)}
