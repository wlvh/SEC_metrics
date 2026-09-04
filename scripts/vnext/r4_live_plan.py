"""Repository-derived R4 call schedule DRAFT, never a live execution grant.

The existing offline corpus proves eligibility; it supplies no reusable model
response to a future call. A separate pending-live factory must bind real
live-shaped request/envelope identities, an exact head and an owner grant.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Mapping

from .canonical import canonical_json_bytes, content_hash, sha256_bytes, strict_json_loads
from .evidence import prepare_offline_evidence_context_from_asset_bytes
from .r4_fixture_authority import FIXTURE_FIELDS, MATRIX_PATH, load_r4_fixture_authority
from .r4_offline_qualification import CASE_FIELDS, INDEX_FIELDS, INDEX_PATH
from .r4_offline_qualification import prepare_source_bundle, prepare_source_bundle_from_context
from .r4_offline_qualification import replay_case_artifacts
from .r4_task_contracts import resolve_r4_task_contract
from .records import EXPLICIT_ARTIFACT_GENERATION
from .requirement_profile import validate_execution_authority
from .requirements import load_requirement_snapshot
from .scoped_reader import ARTIFACT_FILENAMES, PLAN_FIELDS, V2_IDENTITY_FIELDS
from .scoped_reader import prepare_offline_scoped_context
from .source_scope import SCOPE_V2_FIELDS, read_scope_repository_bytes
from .sources import resolve_repository_file


DRAFT_TYPE = "R4_CALL_SCHEDULE_DRAFT"
PLANNER_PATH = "scripts/vnext/r4_live_plan.py"
ALGORITHM = "R4_MARGINAL_RISK_COVERAGE_V1"
BASE_CALLS = 9
STABILITY_CALLS = 3
PLANNED_CALLS = 12
MAXIMUM_CALLS = 24
RISK_PRIORITY = (
    "ALTERNATE_DISCLOSED_PERIOD", "NO_INDEPENDENT_LEGACY_ANCHOR",
    "MIXED_TABLE_NARRATIVE_SCOPE", "COMPOSITE_SCOPE", "NUMERIC_NORMALIZATION",
)
DRAFT_FIELDS = frozenset({
    "record_type", "schema_version", "draft_plan_id", "artifact_requirement_generation",
    "requirement_id", "requirement_closure_hash", "requirement_hashes", "ratchet_id",
    "planning_mode", "exact_head", "owner_authorization", "provider_paid_sec_authorized",
    "qualification_credit", "publication_credit", "response_reuse_authorized",
    "corpus_binding", "fixture_matrix_id", "planner_binding", "selection_policy",
    "call_bounds", "counts", "entries", "zero_call_fixtures", "stability_selection",
    "native_validation", "required_future_binding",
})
_DRAFT_CONTEXT_FACTORY = object()


class R4DraftPlanError(ValueError):
    """Reject relabelled, drifting or non-repository call schedules."""


def _exact(value, fields, label):
    if type(value) is not dict or set(value) != set(fields):
        raise R4DraftPlanError(label + " fields are not exact")
    return value


def _read(root: Path, relative: str):
    path = resolve_repository_file(repo_root=root, repo_relative_path=relative)
    data = path.read_bytes()
    return data, {"sha256": sha256_bytes(content=data), "size": len(data)}


def _object(root: Path, relative: str, binding=None):
    data, observed = _read(root, relative)
    if binding is not None and observed != binding:
        raise R4DraftPlanError("Pinned draft input bytes differ: " + relative)
    return strict_json_loads(text=data.decode("utf-8")), observed


def _self_id(value: Mapping, field: str):
    if value.get(field) != content_hash(value={k: v for k, v in value.items() if k != field}):
        raise R4DraftPlanError("Draft input content identity differs: " + field)


def _choice(requirement: Mapping, kind: str):
    matches = [record["choice"] for record in requirement["effective_decisions"].values()
        if record.get("status") == "APPROVED" and record.get("choice", {}).get("kind") == kind
        and record["choice"].get("ratchet_id") == "R4"]
    if len(matches) != 1:
        raise R4DraftPlanError("R4 policy is absent or ambiguous: " + kind)
    return matches[0]


def _risk_features(recipe: Mapping, scope: Mapping):
    """Read certified mechanisms, not issuer names, values or filing text."""
    features = []
    proof = scope["source_bound_proof"]
    if recipe["reference"]["status"] != scope["reference"]["status"]:
        raise R4DraftPlanError("Draft reference classification differs from recipe")
    if recipe["reference"]["status"] == "NO_INDEPENDENT_LEGACY_ANCHOR":
        features.append({"kind": "NO_INDEPENDENT_LEGACY_ANCHOR"})
    for recipe_key, proof_key in (("numeric_locator", "numeric_normalization"),
                                  ("composite_scope_recipe", "composite_scope"),
                                  ("disclosed_period_recipe", "disclosed_period")):
        actual = None if proof is None else proof[proof_key]
        if (recipe[recipe_key] is not None) != (actual is not None):
            raise R4DraftPlanError("Draft risk proof presence differs from recipe")
    if proof is not None:
        if proof["composite_scope"] is not None:
            if proof["composite_scope"]["recipe"] != recipe["composite_scope_recipe"]:
                raise R4DraftPlanError("Draft composite recipe differs from certificate")
            features.append({"kind": "COMPOSITE_SCOPE"})
            if proof["composite_scope"]["table_disambiguation_dimensions"]:
                features.append({"kind": "MIXED_TABLE_NARRATIVE_SCOPE"})
        if proof["numeric_normalization"] is not None:
            numeric = proof["numeric_normalization"]
            features.append({"kind": "NUMERIC_NORMALIZATION", **{key: numeric[key] for key in (
                "mechanism", "factor", "reported_unit", "canonical_unit")}})
        if proof["disclosed_period"] is not None:
            if recipe["fixture_class"] != "POSITIVE_ALTERNATE_LAYOUT":
                raise R4DraftPlanError("Disclosed alternate period is not an alternate fixture")
            features.append({"kind": "ALTERNATE_DISCLOSED_PERIOD"})
    return sorted(features, key=lambda f: (RISK_PRIORITY.index(f["kind"]), content_hash(value=f)))


def _scope_identity(scope: Mapping, offline_plan: Mapping):
    fields = ("artifact_requirement_generation", "requirement_id", "requirement_closure_hash",
        "requirement_hashes", "fixture_id", "fixture_class", "source_sha256", "full_derived_asset_id",
        "full_reader_input_manifest_id", "task_contract_id", "task_contract_hash", "task_contract_generation",
        "source_scope_manifest_id", "task_period")
    if any(offline_plan[key] != scope[key] for key in fields):
        raise R4DraftPlanError("Offline plan/certificate identity differs")
    proof = scope["source_bound_proof"]
    proof_id = None if proof is None else proof["source_bound_proof_id"]
    if offline_plan["source_bound_proof_id"] != proof_id:
        raise R4DraftPlanError("Offline source-bound proof identity differs")
    return {**{key: scope[key] for key in fields}, "source_bound_proof_id": proof_id,
        "raw_asset_id": scope["raw_blob"]["raw_asset_id"],
        "source_reference_ids": [scope["source_reference"]["source_reference_id"]],
        "window_binding": {key: scope[key] for key in (
            "windows", "ordered_table_ids", "ordered_table_orders", "ordered_grid_hashes")},
        **{key: offline_plan[key] for key in (
            "task_spec_semantic_hash", "output_schema_hash", "system_prompt_hash")}}


def _basis(root: Path, requirement: Mapping, *, company_authority=None):
    authority = load_r4_fixture_authority(repo_root=root, requirement=requirement)
    from .r4_run_store import load_r4_fixture_company_authority, resolve_r4_run_target_period
    if company_authority is None:
        company_authority = load_r4_fixture_company_authority(repo_root=root, requirement=requirement)
    else:
        # Only the trusted live-session bridge supplies this value. Recheck its
        # exact data/file binding; native DEI/profile validation belongs to the
        # private session factory that already owns these immutable bytes.
        relative = "config/r4_fixture_company_authority_v1.json"
        company_file, binding = _object(root, relative)
        if requirement["execution_authority"]["files"].get(relative) != binding:
            raise R4DraftPlanError("Reused subject authority is not execution-bound")
        expected_company = {"authority_id": company_file["authority_id"],
            "entries": {entry["source_id"]: entry for entry in company_file["entries"]},
            "target_period_resolution": company_file["target_period_resolution"],
            "qualification_credit": "NONE_INDIVIDUAL_RUN"}
        if type(company_authority) is not dict or company_authority != expected_company:
            raise R4DraftPlanError("Reused subject authority differs from its exact repository file")
    index, index_binding = _object(root, INDEX_PATH)
    _exact(index, INDEX_FIELDS, "Offline corpus index")
    _self_id(index, "index_id")
    if (index["record_type"] != "R4_OFFLINE_QUALIFICATION_INDEX" or index["schema_version"] != 1
            or index["requirement_id"] != requirement["requirement_id"]
            or index["requirement_closure_hash"] != requirement["requirement_closure_hash"]
            or index["matrix_id"] != authority["matrix_id"] or index["status"] != "OFFLINE_ONLY"
            or index["qualification_credit"] != "NONE_OFFLINE_SYNTHETIC"
            or index["live_authorization"] != "NOT_AUTHORIZED"
            or index["provider_paid_sec_calls"] != [0, 0, 0]
            or index["metric_ids"] != _choice(requirement, "RATCHET_SCOPE")["metric_ids"]):
        raise R4DraftPlanError("Corpus is not the current exact offline Requirement evidence")
    expected = {fixture["fixture_id"]: fixture for fixture in authority["fixtures"]}
    if (type(index["cases"]) is not list or len(index["cases"]) != len(expected)
            or any(type(entry) is not dict or set(entry) != CASE_FIELDS for entry in index["cases"])
            or {entry["fixture_id"] for entry in index["cases"]} != set(expected)):
        raise R4DraftPlanError("Corpus fixture exact set differs")
    bindings = {INDEX_PATH: index_binding}
    directories = {}
    eligible, zero = [], []
    for entry in index["cases"]:
        fixture = expected[entry["fixture_id"]]
        recipe = authority["recipes"][fixture["fixture_id"]]
        if any(entry[key] != fixture[key] for key in FIXTURE_FIELDS):
            raise R4DraftPlanError("Corpus fixture fields differ from repository inputs")
        directory = "docs/r4_offline/qualified_cases/" + fixture["fixture_id"]
        filenames = {"SCOPED_EXTRACTION": set(ARTIFACT_FILENAMES),
            "STRUCTURED_PRIMARY": {"structured_route.json", "source_audit.json"},
            "ZERO_CALL_CLASSIFICATION": {"zero_call_result.json"}}[fixture["artifact_kind"]]
        if (entry["directory"] != directory or set(entry["files"]) != filenames
                or (root / directory).is_symlink()
                or {p.name for p in (root / directory).iterdir()} != filenames):
            raise R4DraftPlanError("Corpus artifact path/kind exact set differs")
        directories[directory] = sorted(filenames)
        objects = {}
        for name, binding in entry["files"].items():
            _exact(binding, {"sha256", "size"}, "Corpus file binding")
            objects[name], bindings[directory + "/" + name] = _object(root, directory + "/" + name, binding)
        summary = entry["summary"]
        if summary["qualification_credit"] != "NONE_OFFLINE_SYNTHETIC":
            raise R4DraftPlanError("Offline corpus cannot supply qualification credit")
        if fixture["artifact_kind"] != "SCOPED_EXTRACTION":
            if summary["provider_call_eligible"] is not False:
                raise R4DraftPlanError("Structured/zero-call fixture cannot enter provider plan")
            if fixture["artifact_kind"] == "STRUCTURED_PRIMARY" and entry["structured_route"]["outcome"] != "STRUCTURED_PRIMARY_RESOLVED":
                raise R4DraftPlanError("Structured positive is not a resolved native route")
            zero.append({"fixture_id": fixture["fixture_id"], "metric_id": fixture["metric_id"],
                "fixture_class": fixture["fixture_class"], "artifact_kind": fixture["artifact_kind"],
                "planned_provider_calls": 0, "reason": "STRUCTURED_PRIMARY_RESOLVED" if
                    fixture["artifact_kind"] == "STRUCTURED_PRIMARY" else fixture["fixture_class"]})
            continue
        scope, offline_plan = objects["source_scope.json"], objects["scoped_plan.json"]
        _exact(scope, SCOPE_V2_FIELDS, "Scope certificate")
        _exact(offline_plan, PLAN_FIELDS | V2_IDENTITY_FIELDS, "Offline scoped plan")
        _self_id(scope, "source_scope_manifest_id")
        _self_id(offline_plan, "scoped_plan_id")
        if (scope["record_type"] != "SOURCE_SCOPE_MANIFEST" or scope["schema_version"] != 2
                or offline_plan["record_type"] != "SCOPED_READER_PLAN"
                or offline_plan["planning_mode"] != "OFFLINE_ONLY"
                or offline_plan["live_authorization"] != "NOT_AUTHORIZED"
                or offline_plan["provider_paid_sec_authorized"] is not False
                or summary["provider_call_eligible"] is not True
                or fixture["fixture_class"] not in _choice(requirement, "LIVE_CALL_BOUND")["positive_fixture_classes"]
                or scope["requirement_hashes"] != requirement["hashes"]
                or scope["requirement_closure_hash"] != requirement["requirement_closure_hash"]
                or scope["reference"] != {**recipe["reference"], "period": recipe["period"]}
                or scope["windows"] != recipe["windows"]
                or scope["check_evidence_result"]["status"] != "PASS"
                or scope["check_evidence_result"]["system_approval_eligible"] is not True
                or entry["structured_route"]["provider_call_eligible"] is not True):
            raise R4DraftPlanError("Fixture is not a current certified scoped base case")
        company = company_authority["entries"].get(fixture["source_id"])
        if (type(company) is not dict or company["source_id"] != fixture["source_id"]
                or company["company_id"] != authority["sources"][fixture["source_id"]]["company_id"]
                or str(int(company["cik"])) != str(int(authority["sources"][fixture["source_id"]]["cik"]))):
            raise R4DraftPlanError("Fixture subject authority differs from source identity")
        proof = scope["source_bound_proof"]
        disclosed = None if proof is None else proof["disclosed_period"]
        request_period = {"task_period": scope["task_period"],
            "source_bound_proof_id": None if proof is None else proof["source_bound_proof_id"],
            "disclosed_period": None if disclosed is None else {key: disclosed[key] for key in (
                "period_label", "period_start", "period_end", "averaging_period", "must_not_claim_annual_average")}}
        target_period = resolve_r4_run_target_period(request_record=request_period, fixture_company=company)
        span = company["financial_nature_span"]
        subject = {"fixture_company_authority_id": company_authority["authority_id"],
            "source_id": company["source_id"], "company_id": company["company_id"], "cik": company["cik"],
            "profile_id": company["profile_id"], "company_traits": company["company_traits"],
            "profile_authority": company["profile_authority"], "source_binding": company["source_binding"],
            "financial_nature_span_binding": None if span is None else {key: span[key] for key in (
                "byte_start", "byte_end", "span_sha256")}}
        period_identity = {"period_label": scope["task_period"],
            "resolution": "SOURCE_BOUND_DISCLOSED_PERIOD" if disclosed is not None else "NATIVE_DEFAULT_FISCAL_PERIOD",
            "source_bound_proof_id": None if disclosed is None else proof["source_bound_proof_id"]}
        eligible.append({"fixture_id": fixture["fixture_id"], "metric_id": fixture["metric_id"],
            "fixture_class": fixture["fixture_class"], "source_id": fixture["source_id"],
            "task_contract_id": fixture["task_contract_id"],
            "scope_certificate_identity": _scope_identity(scope, offline_plan),
            "fixture_subject_identity": subject, "target_period": target_period,
            "target_period_identity": period_identity,
            "recipe_binding": {"path": fixture["recipe_path"], "sha256": fixture["recipe_sha256"]},
            "risk_features": _risk_features(recipe, scope)})
    if len(eligible) != BASE_CALLS or len(zero) != 7:
        raise R4DraftPlanError("R4 draft requires nine scoped and seven zero-call corpus members")
    return authority, index, bindings, directories, eligible, zero


def _native_corpus_replay(root: Path, requirement: Mapping, authority: Mapping, index: Mapping):
    """One read-only native corpus verification, retaining no response cache."""
    indexed = {entry["fixture_id"]: entry for entry in index["cases"]}
    fixtures = authority["fixtures"]
    verified, guarded_sources = [], []
    for source_id in sorted({fixture["source_id"] for fixture in fixtures}):
        selected = [f for f in fixtures if f["source_id"] == source_id]
        declaration = authority["sources"][source_id]
        from .r4_materialization import materialize_full_source
        materialized = materialize_full_source(repo_root=root,
            source_path=declaration["source_repo_relative_path"],
            source_sha256=declaration["source_sha256"], source_size=declaration["source_size"])
        bundle = prepare_source_bundle(repo_root=root, source_id=source_id,
                                       full_derived_asset=materialized["asset"])
        asset_bytes = materialized["asset_bytes"]
        guarded_sources.append(source_id)
        del materialized
        context = scoped_context = None
        if any(f["fixture_class"] != "NOT_APPLICABLE" for f in selected):
            tasks = [resolve_r4_task_contract(repo_root=root, requirement=requirement, task_contract_id=identity)
                     for identity in sorted({f["task_contract_id"] for f in selected})]
            del bundle["full_derived_asset"], bundle["reader_manifest"]
            context = prepare_offline_evidence_context_from_asset_bytes(repo_root=root, requirement=requirement,
                source_bytes=bundle["source_bytes"], raw_blob=bundle["raw_blob"], source_reference=bundle["source_reference"],
                derived_asset_bytes=asset_bytes, task_contracts=tasks, task_generation="R4_V2")
            bundle = prepare_source_bundle_from_context(repo_root=root, source_id=source_id,
                evidence_context=context, task_contract_id=tasks[0]["task_contract_id"])
            scope_files = {indexed[f["fixture_id"]]["summary"]["source_scope_manifest_id"]: {
                "path": str(root / indexed[f["fixture_id"]]["directory"] / "source_scope.json"),
                **indexed[f["fixture_id"]]["files"]["source_scope.json"]}
                for f in selected if f["artifact_kind"] == "SCOPED_EXTRACTION"}
            if scope_files:
                scoped_context = prepare_offline_scoped_context(evidence_context=context, scope_files=scope_files)
        for fixture in selected:
            replay_case_artifacts(repo_root=root, requirement=requirement, fixture=fixture,
                source_bundle=bundle, evidence_context=context, scoped_context=scoped_context)
            verified.append(fixture["fixture_id"])
    return {"fixture_ids": sorted(verified), "guarded_source_ids": guarded_sources}


def _schedule(eligible):
    rank = {"POSITIVE_PRODUCTION": 0, "POSITIVE_ALTERNATE_LAYOUT": 1}
    base = sorted(eligible, key=lambda entry: (entry["metric_id"], rank[entry["fixture_class"]], entry["fixture_id"]))
    entries = [{**entry, "ordinal": ordinal, "fixture_execution_ordinal": 1, "phase": "BASE",
        "repeats_base_ordinal": None, "selection_reason": "EVERY_CERTIFIED_SCOPED_POSITIVE_ONCE",
        "fresh_response_required": True, "response_reuse_authorized": False}
        for ordinal, entry in enumerate(base, 1)]
    seen, chosen = set(), []
    available = list(entries)
    for ordinal in range(BASE_CALLS + 1, PLANNED_CALLS + 1):
        def score(entry):
            new = [f for f in entry["risk_features"] if content_hash(value=f) not in seen]
            return tuple(sum(f["kind"] == kind for f in new) for kind in RISK_PRIORITY) + (-entry["ordinal"],)
        winner = max(available, key=score)
        uncovered = [f for f in winner["risk_features"] if content_hash(value=f) not in seen]
        if not uncovered:
            raise R4DraftPlanError("No distinct certified risk remains for stability selection")
        chosen.append({"ordinal": ordinal, "fixture_id": winner["fixture_id"],
                       "new_risk_features": uncovered, "base_ordinal": winner["ordinal"]})
        entries.append({**winner, "ordinal": ordinal, "fixture_execution_ordinal": 2,
            "phase": "STABILITY", "repeats_base_ordinal": winner["ordinal"],
            "selection_reason": "MARGINAL_CERTIFIED_RISK_COVERAGE"})
        seen.update(content_hash(value=f) for f in winner["risk_features"])
        available.remove(winner)
    for entry in entries:
        entry["draft_entry_id"] = content_hash(value=entry)
    return entries, chosen


def _body(root: Path, requirement: Mapping, authority, index, eligible, zero):
    policy = _choice(requirement, "LIVE_CALL_BOUND")
    lower, upper, hard = (policy[key] for key in (
        "target_minimum_provider_calls", "target_maximum_provider_calls", "hard_maximum_provider_calls"))
    if (any(type(value) is not int for value in (lower, upper, hard))
            or not lower <= PLANNED_CALLS <= upper <= hard <= MAXIMUM_CALLS
            or policy["response_reuse"] != "NOT_AUTHORIZED"):
        raise R4DraftPlanError("Draft call bounds or no-reuse policy differ")
    entries, selection = _schedule(eligible)
    _, corpus_binding = _read(root, INDEX_PATH)
    _, planner_binding = _read(root, PLANNER_PATH)
    return {"record_type": DRAFT_TYPE, "schema_version": 1,
        "artifact_requirement_generation": EXPLICIT_ARTIFACT_GENERATION,
        "requirement_id": requirement["requirement_id"],
        "requirement_closure_hash": requirement["requirement_closure_hash"], "requirement_hashes": requirement["hashes"],
        "ratchet_id": "R4", "planning_mode": "DRAFT_SHAPE_ONLY", "exact_head": None,
        "owner_authorization": "NOT_ISSUED", "provider_paid_sec_authorized": False,
        "qualification_credit": "NONE_DRAFT_ONLY", "publication_credit": "NONE",
        "response_reuse_authorized": False,
        "corpus_binding": {"path": INDEX_PATH, "index_id": index["index_id"], **corpus_binding},
        "fixture_matrix_id": authority["matrix_id"], "planner_binding": {"path": PLANNER_PATH, **planner_binding},
        "selection_policy": {"algorithm": ALGORITHM, "risk_priority": list(RISK_PRIORITY),
            "base_order": ["metric_id", "production_before_alternate", "fixture_id"],
            "stability_tie_breaker": "LOWEST_BASE_ORDINAL", "distinct_repeat_fixtures": True},
        "call_bounds": {"target_minimum": lower, "target_maximum": upper, "hard_maximum": hard},
        "counts": {"base_provider_calls": BASE_CALLS, "stability_provider_calls": STABILITY_CALLS,
            "planned_provider_calls": len(entries), "structured_positive_zero_calls": sum(
                entry["artifact_kind"] == "STRUCTURED_PRIMARY" for entry in zero),
            "zero_class_fixtures": sum(entry["artifact_kind"] == "ZERO_CALL_CLASSIFICATION" for entry in zero),
            "actual_provider_calls": 0, "actual_paid_calls": 0, "actual_sec_calls": 0},
        "entries": entries, "zero_call_fixtures": sorted(zero, key=lambda entry: entry["fixture_id"]),
        "stability_selection": selection,
        "native_validation": {"tier": "EXISTING_OFFLINE_CORPUS_NATIVE_REPLAY", "verified_case_count": len(index["cases"]),
            "live_accuracy_credit": "NONE", "model_responses_reused_for_planning": False},
        "required_future_binding": "DISTINCT_PENDING_LIVE_FACTORY_REQUEST_ENVELOPE_EXACT_HEAD_AND_OWNER_GRANT"}


def _derive_r4_repository_schedule_from_requirement(*, repo_root: Path, requirement: Mapping,
                                                   company_authority=None) -> dict:
    """Trusted integration seam for a factory-owned, already loaded Requirement."""
    root = repo_root.resolve()
    if (type(requirement) is not dict or requirement.get("artifact_requirement_generation") != EXPLICIT_ARTIFACT_GENERATION
            or requirement.get("requirement_closure_hash") != content_hash(value=requirement.get("hashes"))):
        raise R4DraftPlanError("Schedule input is not an exact successor Requirement identity")
    validate_execution_authority(repo_root=root, requirement=requirement)
    authority, index, _files, _directories, eligible, zero = _basis(
        root, requirement, company_authority=company_authority)
    body = _body(root, requirement, authority, index, eligible, zero)
    body.update(record_type="R4_REPOSITORY_CALL_SCHEDULE_INPUTS", planning_mode="IDENTITY_BOUND_SHAPE_INPUTS",
        qualification_credit="NONE_SCHEDULE_INPUTS",
        native_validation={"tier": "NOT_RUN_BY_SHAPE_INSPECTION", "verified_case_count": 0,
            "live_accuracy_credit": "NONE", "model_responses_reused_for_planning": False})
    return {**body, "schedule_input_id": content_hash(value=body)}


def derive_r4_repository_schedule(*, repo_root: Path, requirement_id="issue_28_v2") -> dict:
    """Read current repository identities/risk shape before any source replay.

    This is deliberately a separate input subtype, not a verified draft or a
    pending-live plan. A consumer must independently rebuild certified live
    request identities with its repository-owned native source session.
    """
    root = repo_root.resolve()
    if type(requirement_id) is not str or re.fullmatch(r"issue_[1-9][0-9]*_v[1-9][0-9]*", requirement_id) is None:
        raise R4DraftPlanError("Schedule Requirement ID is not an explicit successor revision")
    requirement = load_requirement_snapshot(snapshot_dir=root / "requirements" / requirement_id)
    if requirement["requirement_id"] != requirement_id:
        raise R4DraftPlanError("Schedule Requirement directory and identity differ")
    return _derive_r4_repository_schedule_from_requirement(repo_root=root, requirement=requirement)


class R4DraftPlanContext:
    """Exact process-local verified shape bytes; no source or response cache."""

    __slots__ = ("_factory", "_root", "_requirement_id", "_body_bytes", "_files", "_directories")

    def __init__(self, *, factory, root, requirement_id, body_bytes, files, directories):
        if factory is not _DRAFT_CONTEXT_FACTORY:
            raise R4DraftPlanError("Draft context requires the repository verifier")
        self._factory, self._root, self._requirement_id = factory, root, requirement_id
        self._body_bytes = bytes(body_bytes)
        self._files = {path: dict(binding) for path, binding in files.items()}
        self._directories = {path: tuple(names) for path, names in directories.items()}

    def _verified_body(self, *, root, requirement_id):
        if (self._factory is not _DRAFT_CONTEXT_FACTORY or self._root != root.resolve()
                or self._requirement_id != requirement_id):
            raise R4DraftPlanError("Draft context belongs to another repository/Requirement")
        for relative, names in self._directories.items():
            path = root / relative
            if path.is_symlink() or {p.name for p in path.iterdir()} != set(names):
                raise R4DraftPlanError("Draft input directory exact set changed")
        for relative, binding in self._files.items():
            read_scope_repository_bytes(path=root / relative, repo_root=root,
                expected_sha256=binding["sha256"], expected_size=binding["size"])
        return strict_json_loads(text=self._body_bytes.decode("utf-8"))


def prepare_r4_draft_plan_context(*, repo_root: Path, requirement_id="issue_28_v2") -> R4DraftPlanContext:
    """Verify once, retain only immutable shape/identity for local rebuilds."""
    root = repo_root.resolve()
    if type(requirement_id) is not str or re.fullmatch(r"issue_[1-9][0-9]*_v[1-9][0-9]*", requirement_id) is None:
        raise R4DraftPlanError("Draft Requirement ID is not an explicit successor revision")
    requirement = load_requirement_snapshot(snapshot_dir=root / "requirements" / requirement_id)
    if requirement["requirement_id"] != requirement_id:
        raise R4DraftPlanError("Draft Requirement directory and identity differ")
    validate_execution_authority(repo_root=root, requirement=requirement)
    authority, index, files, directories, eligible, zero = _basis(root, requirement)
    files.update({relative: dict(binding) for relative, binding in requirement["execution_authority"]["files"].items()})
    for relative in (MATRIX_PATH, PLANNER_PATH, "evidence/requests_log.csv", "evidence/requests_log_manifest.json"):
        _, files[relative] = _read(root, relative)
    for source in authority["sources"].values():
        _, files[source["source_repo_relative_path"]] = _read(root, source["source_repo_relative_path"])
    for entry in index["cases"]:
        for binding in (entry.get("structured_route") or {}).get("source_file_bindings", []):
            _, files[binding["path"]] = _read(root, binding["path"])
    for relative in list(files):
        if not relative.startswith("evidence/request_attempts/"):
            continue
        directory = str(Path(relative).parent)
        paths = list((root / directory).iterdir())
        directories[directory] = sorted(path.name for path in paths)
        for path in paths:
            if path.is_file():
                sibling = path.relative_to(root).as_posix()
                _, files[sibling] = _read(root, sibling)
    current, seen = requirement, set()
    while isinstance(current, Mapping) and current.get("requirement_id") not in seen:
        seen.add(current["requirement_id"])
        directory = "requirements/" + current["requirement_id"]
        paths = list((root / directory).iterdir())
        directories[directory] = sorted(path.name for path in paths)
        for path in paths:
            if path.is_file():
                relative = path.relative_to(root).as_posix()
                _, files[relative] = _read(root, relative)
        embedded = current.get("parent_snapshot")
        if isinstance(embedded, Mapping):
            current = embedded
            continue
        parent_id = current.get("baseline", {}).get("parent_requirement_id")
        if not parent_id:
            break
        parent_baseline, _ = _object(root, "requirements/" + parent_id + "/baseline_manifest.json")
        current = {"requirement_id": parent_id, "baseline": parent_baseline}
    verified = _native_corpus_replay(root, requirement, authority, index)
    if verified["fixture_ids"] != sorted(entry["fixture_id"] for entry in index["cases"]):
        raise R4DraftPlanError("Native corpus verification is incomplete")
    body = _body(root, requirement, authority, index, eligible, zero)
    body["native_validation"].update(
        materialization_boundary="PINNED_DOCKER_512_MIB_NETWORK_NONE_READ_ONLY",
        guarded_source_ids=verified["guarded_source_ids"])
    context = R4DraftPlanContext(factory=_DRAFT_CONTEXT_FACTORY, root=root, requirement_id=requirement_id,
        body_bytes=canonical_json_bytes(value=body),
        files=files, directories=directories)
    context._verified_body(root=root, requirement_id=requirement_id)
    return context


def build_r4_draft_plan(*, repo_root: Path, requirement_id="issue_28_v2", context=None) -> dict:
    if context is None:
        context = prepare_r4_draft_plan_context(repo_root=repo_root, requirement_id=requirement_id)
    if type(context) is not R4DraftPlanContext:
        raise R4DraftPlanError("Draft plan rejects caller-owned validation contexts")
    body = context._verified_body(root=repo_root.resolve(), requirement_id=requirement_id)
    return {**body, "draft_plan_id": content_hash(value=body)}


def validate_r4_draft_plan(*, plan: Mapping, repo_root: Path, expected_plan_id: str,
                           requirement_id="issue_28_v2", context=None) -> dict:
    _exact(plan, DRAFT_FIELDS, "R4 draft plan")
    if (plan["record_type"] != DRAFT_TYPE or type(plan["schema_version"]) is not int
            or plan["schema_version"] != 1 or plan["draft_plan_id"] != expected_plan_id
            or plan["planning_mode"] != "DRAFT_SHAPE_ONLY" or plan["exact_head"] is not None
            or plan["owner_authorization"] != "NOT_ISSUED"
            or plan["provider_paid_sec_authorized"] is not False
            or plan["qualification_credit"] != "NONE_DRAFT_ONLY"
            or plan["publication_credit"] != "NONE" or plan["response_reuse_authorized"] is not False):
        raise R4DraftPlanError("Draft plan was relabelled or claims execution authority")
    _self_id(plan, "draft_plan_id")
    rebuilt = build_r4_draft_plan(repo_root=repo_root, requirement_id=requirement_id, context=context)
    if dict(plan) != rebuilt:
        raise R4DraftPlanError("Draft exact membership/order/risk/count/identity differs from repository")
    return rebuilt


def load_r4_draft_plan(*, repo_root: Path, path: Path, expected_plan_id: str,
                       requirement_id="issue_28_v2", context=None) -> dict:
    root = repo_root.resolve()
    if path.is_absolute():
        if path.is_symlink():
            raise R4DraftPlanError("Draft plan path is a symlink")
        relative = path.resolve(strict=True).relative_to(root).as_posix()
    else:
        relative = path.as_posix()
    plan, _ = _object(root, relative)
    return validate_r4_draft_plan(plan=plan, repo_root=root, expected_plan_id=expected_plan_id,
                                 requirement_id=requirement_id, context=context)
