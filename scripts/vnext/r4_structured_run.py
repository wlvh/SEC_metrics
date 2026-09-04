"""Native zero-provider R4 structured-primary Result persistence and replay.

Only the three repository-certified structured positives enter this subtype.
The same accession-XBRL evaluator chooses claims; existing Observation and
Calculator constructors produce the Result/Trace.  No AI Candidate, Evidence
or Review is fabricated for a deterministic fact.
"""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

from .canonical import atomic_write_bytes, canonical_json_bytes, content_hash
from .canonical import sha256_bytes, sha256_file, strict_json_file, strict_json_loads
from .calculator import calculate_observation_metric
from .deterministic_router import validate_verified_claim
from .observations import structured_observation
from .records import EXPLICIT_ARTIFACT_GENERATION, R4_STRUCTURED_ARTIFACT_KINDS
from .records import R4_STRUCTURED_PROTOCOL, R4_STRUCTURED_RUN_TYPE, validate_record
from .r4_offline_qualification import replay_case_artifacts
from .r4_task_contracts import resolve_r4_task_contract
from .sources import raw_blob_record, resolve_repository_file
from .specs import SEMANTIC_SET_PATHS, compile_spec_file
from .table_task_contracts import _table_task_semantic, table_task_run_binding


_FACTORY = object()


class R4StructuredRunError(ValueError):
    """Reject a non-certified structured selection or a drifting native graph."""


def _plain(value):
    return strict_json_loads(text=canonical_json_bytes(value=value).decode("utf-8"))


def _task_plan(*, repo_root: Path, requirement: Mapping, task_contract_id: str) -> dict:
    runtime = resolve_r4_task_contract(repo_root=repo_root, requirement=requirement,
                                       task_contract_id=task_contract_id)
    if len(runtime["metric_spec_paths"]) != 1:
        raise R4StructuredRunError("Structured R4 task is not a single native MetricSpec")
    path = resolve_repository_file(repo_root=repo_root,
                                    repo_relative_path=runtime["metric_spec_paths"][0])
    metric = compile_spec_file(path=path, dependency_specs={})
    if (metric["compiled"]["source_mode"] != "structured_first_ai_fallback"
            or metric["spec_semantic_hash"] != runtime["metric_spec_semantic_hashes"][0]
            or metric["spec_closure_hash"] != runtime["metric_spec_closure_hashes"][0]
            or [metric["compiled"]["metric_id"]] != runtime["metric_ids"]):
        raise R4StructuredRunError("Structured R4 task/MetricSpec identity differs")
    semantic = _table_task_semantic(runtime=runtime, metric_semantic=metric["compiled"])
    semantic_hash = content_hash(value=semantic, set_paths=SEMANTIC_SET_PATHS)
    if semantic_hash != runtime["task_spec_semantic_hash"]:
        raise R4StructuredRunError("Structured R4 task semantic identity differs")
    return {"runtime_task_contract": runtime,
        "task_spec": {"compiled": semantic, "spec_semantic_hash": semantic_hash,
            "spec_closure_hash": content_hash(value={
                "catalog_task_contract_hash": runtime["catalog_task_contract_hash"],
                "metric_spec_closure_hashes": runtime["metric_spec_closure_hashes"]})},
        "metric_specs": {metric["compiled"]["metric_id"]: metric},
        "run_binding": table_task_run_binding(runtime=runtime)}


class R4StructuredRunContext:
    """Private source-local native interpretation; never an execution grant."""

    __slots__ = ("_factory", "_execution", "_plan_bytes", "_fixture_id")

    def __init__(self, *, factory, execution, plan, fixture_id):
        if factory is not _FACTORY:
            raise R4StructuredRunError("Structured Run context requires its repository factory")
        self._factory, self._execution = factory, execution
        self._plan_bytes = canonical_json_bytes(value=plan)
        self._fixture_id = fixture_id

    def _check(self):
        from .r4_live_authority import R4ExecutionPlanContext, validate_r4_execution_plan
        if self._factory is not _FACTORY or type(self._execution) is not R4ExecutionPlanContext:
            raise R4StructuredRunError("Structured Run context type/factory differs")
        self._execution._check()
        plan = strict_json_loads(text=self._plan_bytes.decode("utf-8"))
        validate_r4_execution_plan(plan=plan, context=self._execution,
            expected_plan_id=plan["pending_plan_id"], mode=plan["execution_mode"])
        return plan

    def _native_graph(self):
        """Reapply the existing source evaluator; no caller value is accepted."""
        plan = self._check()
        session = self._execution._session
        root, requirement = self._execution._root, session._requirement
        matches = [fixture for fixture in session._authority["fixtures"]
                   if fixture["fixture_id"] == self._fixture_id]
        if (len(matches) != 1 or matches[0]["artifact_kind"] != "STRUCTURED_PRIMARY"
                or matches[0]["fixture_class"] not in {"POSITIVE_PRODUCTION", "POSITIVE_ALTERNATE_LAYOUT"}):
            raise R4StructuredRunError("Fixture is not a certified structured-positive R4 case")
        fixture = matches[0]
        zero = [row for row in plan["zero_call_fixtures"] if row["fixture_id"] == self._fixture_id]
        if (len(zero) != 1 or zero[0]["reason"] != "STRUCTURED_PRIMARY_RESOLVED"
                or zero[0]["planned_provider_calls"] != 0
                or any(entry["fixture_id"] == self._fixture_id for entry in plan["entries"])):
            raise R4StructuredRunError("Structured fixture entered a provider plan or lost zero-call status")
        source = session._source(fixture["source_id"])
        bundle = source["bundle"]
        # The existing dispatcher reconstructs the native route and the source
        # audit from the same bound recipe before accepting the stored receipt.
        replay_case_artifacts(repo_root=root, requirement=requirement, fixture=fixture,
            source_bundle=bundle, evidence_context=source["evidence"], scoped_context=source["scoped"])
        entry = next(row for row in session._index["cases"] if row["fixture_id"] == self._fixture_id)
        relative = entry["directory"] + "/structured_route.json"
        path = resolve_repository_file(repo_root=root, repo_relative_path=relative)
        data = path.read_bytes()
        if entry["files"]["structured_route.json"] != {"sha256": sha256_bytes(content=data), "size": len(data)}:
            raise R4StructuredRunError("Structured route receipt changed after native replay")
        route = strict_json_loads(text=data.decode("utf-8"))
        if (route["outcome"] != "STRUCTURED_PRIMARY_RESOLVED"
                or route["provider_call_eligible"] is not False
                or route["regional_sum_used"] is not False
                or route["provider_paid_sec_calls"] != [0, 0, 0]
                or route["requirement_id"] != requirement["requirement_id"]
                or route["requirement_closure_hash"] != requirement["requirement_closure_hash"]):
            raise R4StructuredRunError("Structured route does not justify a zero-provider Result")
        selected = [validate_verified_claim(claim=claim) for claim in route["selected_claims"]]
        if not selected or len({claim["verified_claim_id"] for claim in selected}) != len(selected):
            raise R4StructuredRunError("Structured selected claim set is empty or duplicated")
        reference = validate_record(record=route["source_reference"])
        if any(claim["source_reference_id"] != reference["source_reference_id"]
               or claim["company_id"] != reference["company_id"] for claim in selected):
            raise R4StructuredRunError("Structured claims name another source/entity")
        subject = session._company(fixture["source_id"])
        task_plan = _task_plan(repo_root=root, requirement=requirement,
                               task_contract_id=fixture["task_contract_id"])
        metric = task_plan["metric_specs"][fixture["metric_id"]]
        runtime = task_plan["runtime_task_contract"]
        recipe = session._authority["recipes"][fixture["fixture_id"]]
        scope = dict(metric["compiled"]["required_claims"])
        if (recipe["reference"]["scope"] != scope
                or recipe["reference"]["unit"] != metric["compiled"]["canonical_unit"]
                or route["value"] != recipe["reference"]["value"]
                or {claim["value"] for claim in selected} != {route["value"]}
                or len(runtime["required_roles"]) != 1):
            raise R4StructuredRunError("Native structured selection differs from approved scope/value/unit")
        fiscal = route["target_fiscal_period"]
        default = subject["default_fiscal_period"]
        if (fiscal["period_label"] != default["period_label"]
                or fiscal["period_start"] != default["period_start"]
                or fiscal["period_end"] != default["period_end"]
                or reference["company_id"] != subject["company_id"]):
            raise R4StructuredRunError("Structured subject/fiscal period differs from native DEI")
        target_period = {"fiscal_year": int(default["period_label"][2:]),
            "period_start": fiscal["period_start"], "period_end": fiscal["period_end"]}
        raw_sha = reference["raw_asset_id"][7:]
        raw_paths = [binding["path"] for binding in route["source_file_bindings"]
                     if binding["sha256"] == raw_sha]
        if len(raw_paths) != 1:
            raise R4StructuredRunError("Structured raw source file is absent or ambiguous")
        media_type = "application/xml" if bundle["declaration"]["structured_source_authority"] is not None else bundle["declaration"]["media_type"]
        raw = raw_blob_record(repo_root=root, repo_relative_path=raw_paths[0], media_type=media_type)
        if raw["raw_asset_id"] != reference["raw_asset_id"]:
            raise R4StructuredRunError("Structured native RawBlob identity differs")
        observation = structured_observation(metric_id=fixture["metric_id"],
            semantic_role=runtime["required_roles"][0], company_id=subject["company_id"],
            period_start=target_period["period_start"], period_end=target_period["period_end"],
            scope=scope, value=route["value"], unit=metric["compiled"]["canonical_unit"], quality="EXACT",
            source_binding={**{key: reference[key] for key in (
                "raw_asset_id", "source_reference_id", "accession", "document_name", "source_role")},
                "source_set_manifest_id": route["source_set_manifest"]["source_set_manifest_id"],
                "matched_verified_claim_ids": [claim["verified_claim_id"] for claim in selected],
                "structured_route_receipt_id": route["structured_route_receipt_id"],
                "parsed_source_id": route["parsed_source_id"]})
        target = {"company_id": subject["company_id"], "period_start": target_period["period_start"],
            "period_end": target_period["period_end"], "scope": scope, "scope_key": content_hash(value=scope)}
        result, trace = calculate_observation_metric(compiled_spec=metric, target=target,
            company_traits=subject["company_traits"], observation=observation)
        return {"plan": plan, "route": route, "fixture": fixture, "subject": subject,
            "task_plan": task_plan, "target_period": target_period, "requirement": requirement,
            "raw_bytes": bundle["structured_context"]["raw_bytes"],
            "records": [raw, reference, *selected, observation, result, trace]}


def prepare_r4_structured_run_context(*, repo_root: Path, fixture_id: str,
                                     plan: Mapping, execution_context=None):
    from .r4_live_authority import R4ExecutionPlanContext, prepare_r4_execution_context
    if execution_context is None:
        execution_context = prepare_r4_execution_context(repo_root=repo_root)
    if type(execution_context) is not R4ExecutionPlanContext or execution_context._root != repo_root.resolve():
        raise R4StructuredRunError("Structured context belongs to another repository")
    context = R4StructuredRunContext(factory=_FACTORY, execution=execution_context,
                                     plan=plan, fixture_id=fixture_id)
    context._native_graph()
    return context


def _binding(graph):
    files, hashes = {}, {}
    for kind, value in (("plan", graph["plan"]), ("structured_route", graph["route"])):
        data = canonical_json_bytes(value=value)
        digest = sha256_bytes(content=data)
        files[kind] = {"path": "r4_structured/{}_{}.json".format(kind, digest),
                       "sha256": digest, "size": len(data)}
        hashes[kind + "_hash"] = "sha256:" + digest
    return {"protocol": R4_STRUCTURED_PROTOCOL, "fixture_id": graph["fixture"]["fixture_id"],
        "source_id": graph["fixture"]["source_id"], "artifact_hashes": hashes, "artifact_files": files,
        "fixture_company_authority_id": graph["subject"]["fixture_company_authority_id"],
        "execution_mode": graph["plan"]["execution_mode"], "qualification_credit": "NONE_INDIVIDUAL_RUN",
        "publication_credit": "NONE", "provider_paid_sec_calls": [0, 0, 0]}


def _read_artifact(*, run_dir: Path, manifest: Mapping, kind: str):
    binding = manifest["r4_structured_binding"]["artifact_files"][kind]
    cursor = run_dir
    if cursor.is_symlink() or not cursor.is_dir():
        raise R4StructuredRunError("Structured Run root is unsafe")
    for part in Path(binding["path"]).parts:
        cursor /= part
        if cursor.is_symlink():
            raise R4StructuredRunError("Structured Run artifact contains a symlink")
    if not cursor.is_file():
        raise R4StructuredRunError("Structured Run artifact is absent")
    data = cursor.read_bytes()
    if len(data) != binding["size"] or sha256_bytes(content=data) != binding["sha256"]:
        raise R4StructuredRunError("Structured Run artifact bytes differ")
    value = strict_json_loads(text=data.decode("utf-8"))
    if content_hash(value=value) != manifest["r4_structured_binding"]["artifact_hashes"][kind + "_hash"]:
        raise R4StructuredRunError("Structured Run artifact semantic identity differs")
    return value


def prepare_r4_structured_disk_context(*, repo_root: Path, run_dir: Path, manifest: Mapping):
    plan = _read_artifact(run_dir=run_dir, manifest=manifest, kind="plan")
    return prepare_r4_structured_run_context(repo_root=repo_root,
        fixture_id=manifest["r4_structured_binding"]["fixture_id"], plan=plan)


def structured_context_requirement(*, repo_root: Path, manifest: Mapping, replay_context):
    if type(replay_context) is not R4StructuredRunContext or replay_context._factory is not _FACTORY:
        raise R4StructuredRunError("An exact native structured Run context is required")
    replay_context._check()
    if replay_context._execution._root != repo_root.resolve():
        raise R4StructuredRunError("Structured Run context repository differs")
    requirement = replay_context._execution._session._requirement
    if (any(manifest[key] != requirement[key] for key in (
            "artifact_requirement_generation", "requirement_id", "requirement_closure_hash"))
            or manifest["requirement_hashes"] != requirement["hashes"]):
        raise R4StructuredRunError("Structured Run Requirement identity differs")
    return requirement


def structured_task_plans(*, repo_root: Path, manifest: Mapping, replay_context):
    requirement = structured_context_requirement(repo_root=repo_root, manifest=manifest,
                                                  replay_context=replay_context)
    bindings = manifest["task_contract_bindings"]
    if len(bindings) != 1:
        raise R4StructuredRunError("Structured Run requires one native task")
    task = _task_plan(repo_root=repo_root, requirement=requirement,
                      task_contract_id=bindings[0]["task_contract_id"])
    if bindings != [task["run_binding"]]:
        raise R4StructuredRunError("Structured Run task binding differs")
    return {bindings[0]["task_contract_id"]: task}


def _verify_graph(*, repo_root: Path, run_dir: Path, manifest: Mapping,
                  records, replay_context):
    structured_context_requirement(repo_root=repo_root, manifest=manifest, replay_context=replay_context)
    graph = replay_context._native_graph()
    if (manifest["r4_structured_binding"] != _binding(graph)
            or manifest["company_id"] != graph["subject"]["company_id"]
            or manifest["company_traits"] != graph["subject"]["company_traits"]
            or manifest["target_period"] != graph["target_period"]
            or manifest["source_references"] != [graph["route"]["source_reference"]]
            or list(records) != graph["records"]):
        raise R4StructuredRunError("Structured Run differs from native claim/Observation/Result replay")
    for kind, value in (("plan", graph["plan"]), ("structured_route", graph["route"])):
        if _read_artifact(run_dir=run_dir, manifest=manifest, kind=kind) != value:
            raise R4StructuredRunError("Structured Run plan/route differs from native disk authority")
    return graph


def verify_structured_sources(*, repo_root: Path, run_dir: Path, manifest: Mapping,
                              records, replay_context):
    graph = _verify_graph(repo_root=repo_root, run_dir=run_dir, manifest=manifest,
                          records=records, replay_context=replay_context)
    return {graph["records"][0]["raw_asset_id"]: graph["raw_bytes"]}


def structured_company_authority(*, repo_root: Path, manifest: Mapping, replay_context):
    structured_context_requirement(repo_root=repo_root, manifest=manifest, replay_context=replay_context)
    subject = replay_context._execution._session._company(manifest["r4_structured_binding"]["source_id"])
    return list(subject["company_traits"]), [str(int(subject["cik"]))]


def validate_structured_record_graph(*, repo_root: Path, run_dir: Path, manifest: Mapping,
                                    records, effective_decisions, replay_context):
    if effective_decisions:
        raise R4StructuredRunError("Deterministic structured facts cannot acquire fabricated AI Review")
    _verify_graph(repo_root=repo_root, run_dir=run_dir, manifest=manifest,
                  records=records, replay_context=replay_context)


def create_and_freeze_r4_structured_run(*, repo_root: Path, run_dir: Path,
                                      fixture_id: str, plan: Mapping, execution_context):
    from .run_store import create_run, append_run_records_atomically, validate_and_freeze_run
    context = prepare_r4_structured_run_context(repo_root=repo_root, fixture_id=fixture_id,
                                                plan=plan, execution_context=execution_context)
    graph = context._native_graph()
    binding = _binding(graph)
    requirement, subject = graph["requirement"], graph["subject"]
    runtime = graph["task_plan"]["runtime_task_contract"]
    manifest = create_run(run_dir=run_dir,
        run_id="run:r4:structured:" + content_hash(value=binding).split(":", 1)[1],
        company_id=subject["company_id"], company_traits=subject["company_traits"],
        target_period=graph["target_period"], source_references=[graph["route"]["source_reference"]],
        missing_required_source_roles=[], task_contract_bindings=[graph["task_plan"]["run_binding"]],
        spec_file_hashes={relative: sha256_file(path=repo_root / relative)
                          for relative in runtime["metric_spec_paths"]},
        requirement_hashes=requirement["hashes"], requirement_id=requirement["requirement_id"],
        requirement_closure_hash=requirement["requirement_closure_hash"],
        artifact_requirement_generation=EXPLICIT_ARTIFACT_GENERATION,
        run_record_type=R4_STRUCTURED_RUN_TYPE, r4_structured_binding=binding)
    for kind, value in (("plan", graph["plan"]), ("structured_route", graph["route"])):
        atomic_write_bytes(path=run_dir / binding["artifact_files"][kind]["path"],
                           content=canonical_json_bytes(value=value))
    append_run_records_atomically(run_dir=run_dir, records=graph["records"],
        expected_records_file_hash=manifest["records_file_hash"],
        expected_review_decisions_file_hash=manifest["review_decisions_file_hash"])
    return validate_and_freeze_run(run_dir=run_dir, repo_root=repo_root, r4_replay_context=context)


def replay_r4_structured_run(*, repo_root: Path, run_dir: Path, structured_context=None):
    from .replay import replay_frozen_results
    manifest = validate_record(record=strict_json_file(path=run_dir / "manifest.json"))
    if manifest["record_type"] != R4_STRUCTURED_RUN_TYPE:
        raise R4StructuredRunError("Structured replay requires its explicit Run subtype")
    replayed = replay_frozen_results(run_dir=run_dir, repo_root=repo_root,
                                     r4_replay_context=structured_context)
    return {**replayed, "run_id": manifest["run_id"], "run_status": manifest["status"],
        "execution_mode": manifest["r4_structured_binding"]["execution_mode"],
        "qualification_credit": "NONE_INDIVIDUAL_RUN", "publication_credit": "NONE",
        "provider_paid_sec_calls": [0, 0, 0], "response_reuse_authorized": False}
