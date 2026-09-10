"""Repository-owned scoped input and native acceptance, without a live grant.

The private request type is distinct from the offline preparation record. It
can be captured without credentials; only the separately authorized adapter
can dispatch it. Full source/asset/Reader authority remains local. Reuse is
limited to one explicit process-local session of exact immutable inputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Mapping

from .canonical import canonical_json_bytes, content_hash, sha256_bytes, strict_json_loads
from .evidence import prepare_offline_evidence_context_from_asset_bytes
from .evidence import _plain_owned
from .r4_fixture_authority import load_r4_fixture_authority
from .r4_materialization import materialize_full_source
from .r4_offline_qualification import INDEX_FIELDS, CASE_FIELDS
from .r4_label_policy import corpus_root, corpus_index, label_policy as bound_label_policy, RAW_LABEL_POLICY
from .r4_offline_qualification import prepare_source_bundle_from_context, replay_case_artifacts
from .r4_source_audit import source_authority
from .r4_task_contracts import resolve_r4_task_contract
from .requirement_profile import requirement_authority_paths, validate_execution_authority
from .requirements import load_requirement_snapshot
from .scoped_reader import prepare_offline_scoped_context
from .scoped_reader import prepare_scoped_reader_request_in_session
from .sources import resolve_repository_file
from .specs import compile_spec_file


_REQUEST_FACTORY = object()
_SESSION_FACTORY = object()
_ACCEPTANCE_FACTORY = object()
REQUEST_RECORD_TYPE = "LIVE_SCOPED_READER_REQUEST"
INPUT_RECORD_TYPE = "LIVE_SCOPED_READER_INPUT"
SCOPED_ACCEPTANCE_VERSION = "source-bound-scoped-reader-acceptance-v1"
SCOPED_ACCEPTANCE_HASH = content_hash(value={
    "semantic_version": SCOPED_ACCEPTANCE_VERSION,
    "checks": ["REPOSITORY_EXACT_IMMUTABLE_FILES", "CERTIFIED_ORIGINAL_TABLE_WINDOWS",
               "EXACT_SOURCE_TASK_REQUIREMENT", "NATIVE_SOURCE_BOUND_READER",
               "NATIVE_CHECK_EVIDENCE", "CERTIFIED_TARGET_REFERENCE_RECONCILIATION"],
})


class LiveScopedReaderError(ValueError):
    """Reject incomplete, caller-authored or drifting scoped authority."""


def _json_bytes(value) -> bytes:
    return canonical_json_bytes(value=_plain_owned(value))


def _file_binding(*, repo_root: Path, relative: str) -> dict:
    path = resolve_repository_file(repo_root=repo_root, repo_relative_path=relative)
    data = path.read_bytes()
    return {"sha256": sha256_bytes(content=data), "size": len(data)}


def _check_files(*, repo_root: Path, bindings: Mapping) -> None:
    for relative, binding in bindings.items():
        if _file_binding(repo_root=repo_root, relative=relative) != binding:
            raise LiveScopedReaderError("Live-scoped immutable file changed: " + relative)


def _source_ledger_paths(*, repo_root: Path, authority: Mapping) -> set:
    """Carry only matched immutable attempts plus the native complete CSV proof."""
    from sec_http import parse_request_log_rows, validate_request_log_manifest
    log = resolve_repository_file(repo_root=repo_root, repo_relative_path="evidence/requests_log.csv")
    validate_request_log_manifest(log_path=log)
    pairs = set()
    for source in authority["sources"].values():
        pairs.add((source["source_url"], source["source_sha256"]))
        structured = source["structured_source_authority"]
        if structured is not None:
            xml = structured["accession_xbrl"]
            pairs.add((source["source_url"].rsplit("/", 1)[0] + "/" + Path(xml["path"]).name,
                       xml["sha256"]))
            inventory = structured["submissions"]
            pairs.add((inventory["source_url"], inventory["sha256"]))
    paths = {"evidence/requests_log.csv", "evidence/requests_log_manifest.json"}
    for row in parse_request_log_rows(text=log.read_text(encoding="utf-8")):
        if (row["method"] == "GET" and row["status_code"] == "200" and not row["error"]
                and (row["source_url"], row["content_sha256"]) in pairs
                and row["repo_relative_path"].startswith("evidence/request_attempts/")):
            if not row["headers_repo_relative_path"].startswith("evidence/request_attempts/"):
                raise LiveScopedReaderError("Scoped source immutable header locator is absent")
            paths.update((row["repo_relative_path"], row["headers_repo_relative_path"]))
    return paths


def _read_corpus(*, repo_root: Path, requirement: Mapping, authority: Mapping) -> dict:
    path = resolve_repository_file(repo_root=repo_root, repo_relative_path=corpus_index(requirement["requirement_id"]))
    index = strict_json_loads(text=path.read_text(encoding="utf-8"))
    if (type(index) is not dict or set(index) != INDEX_FIELDS
            or index["record_type"] != "R4_OFFLINE_QUALIFICATION_INDEX"
            or type(index["schema_version"]) is not int or index["schema_version"] != 1
            or index["status"] != "OFFLINE_ONLY" or index["provider_paid_sec_calls"] != [0, 0, 0]
            or any(type(v) is not int for v in index["provider_paid_sec_calls"])
            or index["qualification_credit"] != "NONE_OFFLINE_SYNTHETIC"
            or index["live_authorization"] != "NOT_AUTHORIZED"
            or index["requirement_id"] != requirement["requirement_id"]
            or index["requirement_closure_hash"] != requirement["requirement_closure_hash"]
            or index["matrix_id"] != authority["matrix_id"]
            or index["metric_ids"] != authority["matrix"]["metric_ids"]
            or index["index_id"] != content_hash(value={k: v for k, v in index.items() if k != "index_id"})):
        raise LiveScopedReaderError("Scoped certificate corpus is not the exact current offline evidence")
    fixtures = {row["fixture_id"]: row for row in authority["fixtures"]}
    rows = index["cases"]
    if (type(rows) is not list or len(rows) != len(fixtures)
            or any(type(row) is not dict or set(row) != CASE_FIELDS for row in rows)
            or {row["fixture_id"] for row in rows} != set(fixtures)):
        raise LiveScopedReaderError("Scoped certificate corpus exact set differs")
    for row in rows:
        fixture = fixtures[row["fixture_id"]]
        if any(row[key] != fixture[key] for key in fixture):
            raise LiveScopedReaderError("Scoped certificate fixture differs from input authority")
        filenames = {"SCOPED_EXTRACTION": {"source_scope.json", "scoped_plan.json",
            "scoped_request.json", "scoped_attempt.json"},
            "STRUCTURED_PRIMARY": {"structured_route.json", "source_audit.json"},
            "ZERO_CALL_CLASSIFICATION": {"zero_call_result.json"}}[fixture["artifact_kind"]]
        directory = corpus_root(requirement["requirement_id"]) + "/" + fixture["fixture_id"]
        if (row["directory"] != directory or type(row["files"]) is not dict
                or set(row["files"]) != filenames
                or (repo_root / directory).is_symlink()
                or not (repo_root / directory).is_dir()
                or {p.name for p in (repo_root / directory).iterdir()} != filenames):
            raise LiveScopedReaderError("Scoped certificate directory or artifact kind differs")
        for name, binding in row["files"].items():
            if (type(binding) is not dict or set(binding) != {"sha256", "size"}
                    or _file_binding(repo_root=repo_root, relative=directory + "/" + name) != binding):
                raise LiveScopedReaderError("Scoped certificate artifact bytes differ")
    return index


class LiveScopedReaderSession:
    """Private, process-local immutable data ownership; never execution authority."""

    __slots__ = ("_factory", "_root", "_requirement", "_authority", "_index",
                 "_base_files", "_sources", "_fixtures", "_invocation_authority",
                 "_full_corpus_validation", "_company_authority_bytes")

    def __init__(self, *, factory, root, requirement, authority, index, base_files,
                 company_authority):
        if factory is not _SESSION_FACTORY:
            raise LiveScopedReaderError("Live-scoped session requires its repository factory")
        self._factory = factory
        self._root = root
        self._requirement = requirement
        self._authority = authority
        self._index = index
        self._base_files = base_files
        self._sources = {}
        self._fixtures = {}
        self._full_corpus_validation = None
        self._company_authority_bytes = canonical_json_bytes(value=company_authority)
        from .invocation_control import _prepare_successor_invocation_authority_from_requirement
        self._invocation_authority = _prepare_successor_invocation_authority_from_requirement(
            repo_root=root, requirement=requirement)

    def _check(self):
        if self._factory is not _SESSION_FACTORY:
            raise LiveScopedReaderError("Live-scoped session factory differs")
        _check_files(repo_root=self._root, bindings=self._base_files)

    def _company(self, source_id):
        self._check()
        authority = strict_json_loads(text=self._company_authority_bytes.decode("utf-8"))
        if source_id not in authority["entries"]:
            raise LiveScopedReaderError("Fixture company is absent from the pinned session authority")
        return {**authority["entries"][source_id],
                "fixture_company_authority_id": authority["authority_id"],
                "target_period_resolution": authority["target_period_resolution"]}

    def _source(self, source_id):
        self._check()
        if source_id not in self._sources:
            declaration = self._authority["sources"][source_id]
            source = source_authority(repo_root=self._root, declaration=declaration)
            materialized = materialize_full_source(repo_root=self._root,
                source_path=declaration["source_repo_relative_path"],
                source_sha256=declaration["source_sha256"], source_size=declaration["source_size"])
            asset_bytes = materialized["asset_bytes"]
            # The byte-owned context, not a mutable worker result, owns the graph.
            materialized.pop("asset")
            task_ids = sorted({row["task_contract_id"] for row in self._authority["fixtures"]
                               if row["source_id"] == source_id})
            tasks = [resolve_r4_task_contract(repo_root=self._root, requirement=self._requirement,
                                              task_contract_id=identity) for identity in task_ids]
            evidence = prepare_offline_evidence_context_from_asset_bytes(repo_root=self._root,
                requirement=self._requirement, source_bytes=source["source_bytes"],
                raw_blob=source["raw_blob"], source_reference=source["source_reference"],
                derived_asset_bytes=asset_bytes, task_contracts=tasks, task_generation="R4_V2")
            bundle = prepare_source_bundle_from_context(repo_root=self._root, source_id=source_id,
                evidence_context=evidence, task_contract_id=task_ids[0])
            scope_files = {}
            for entry in self._index["cases"]:
                if entry["source_id"] != source_id or entry["artifact_kind"] != "SCOPED_EXTRACTION":
                    continue
                if entry["fixture_class"] not in {"POSITIVE_PRODUCTION", "POSITIVE_ALTERNATE_LAYOUT"}:
                    raise LiveScopedReaderError("Non-positive fixture entered scoped certificate set")
                expected_directory = corpus_root(self._requirement["requirement_id"]) + "/" + entry["fixture_id"]
                if (entry["directory"] != expected_directory
                        or set(entry["files"]) != {"source_scope.json", "scoped_plan.json",
                                                  "scoped_request.json", "scoped_attempt.json"}):
                    raise LiveScopedReaderError("Scoped certificate file set differs")
                relative = expected_directory + "/source_scope.json"
                binding = entry["files"]["source_scope.json"]
                scope_files[entry["summary"]["source_scope_manifest_id"]] = {
                    "path": str(self._root / relative), **binding}
            scoped = (prepare_offline_scoped_context(evidence_context=evidence, scope_files=scope_files)
                      if scope_files else None)
            self._sources[source_id] = {"evidence": evidence, "scoped": scoped,
                "bundle": bundle, "asset_bytes": asset_bytes,
                "materialization_report": materialized["report"]}
        return self._sources[source_id]

    def _fixture(self, fixture_id):
        self._check()
        matches = [f for f in self._authority["fixtures"] if f["fixture_id"] == fixture_id]
        if (len(matches) != 1 or matches[0]["artifact_kind"] != "SCOPED_EXTRACTION"
                or matches[0]["fixture_class"] not in {"POSITIVE_PRODUCTION", "POSITIVE_ALTERNATE_LAYOUT"}):
            raise LiveScopedReaderError("ZERO_CALL_FIXTURE: no scoped provider request is permitted")
        fixture = matches[0]
        entry = next(row for row in self._index["cases"] if row["fixture_id"] == fixture_id)
        source = self._source(fixture["source_id"])
        if fixture_id not in self._fixtures:
            # These are synthetic source certificates, not responses eligible for reuse.
            replay_case_artifacts(repo_root=self._root, requirement=self._requirement,
                fixture=fixture, source_bundle=source["bundle"], evidence_context=source["evidence"],
                scoped_context=source["scoped"])
            self._fixtures[fixture_id] = (fixture, entry)
        scope_id = entry["summary"]["source_scope_manifest_id"]
        scope, authority = source["scoped"]._authority(source_scope_manifest_id=scope_id)
        if scope["schema_version"] != 2:
            raise LiveScopedReaderError("Live-scoped execution requires the explicit successor scope generation")
        return fixture, entry, source, scope, authority

    def validate_full_corpus(self):
        """Replay all 16 cases over four guarded sources, including model-zero N/A."""
        self._check()
        if self._full_corpus_validation is None:
            verified = []
            for source_id in sorted(self._authority["sources"]):
                source = self._source(source_id)
                for fixture in [row for row in self._authority["fixtures"]
                                if row["source_id"] == source_id]:
                    replay_case_artifacts(repo_root=self._root, requirement=self._requirement,
                        fixture=fixture, source_bundle=source["bundle"],
                        evidence_context=source["evidence"], scoped_context=source["scoped"])
                    verified.append(fixture["fixture_id"])
            expected = sorted(row["fixture_id"] for row in self._authority["fixtures"])
            if sorted(verified) != expected:
                raise LiveScopedReaderError("Live-scoped native corpus validation is incomplete")
            self._full_corpus_validation = tuple(expected)
        return list(self._full_corpus_validation)


def prepare_live_scoped_reader_session(*, repo_root: Path,
                                      requirement_id: str = "issue_28_v2") -> LiveScopedReaderSession:
    """Pin current repository data once, without issuing any execution grant."""
    if type(repo_root) is not Path and not isinstance(repo_root, Path):
        raise LiveScopedReaderError("Live-scoped repository root is not a path")
    if repo_root.is_symlink() or not repo_root.is_dir():
        raise LiveScopedReaderError("Live-scoped repository root is unsafe")
    root = repo_root.resolve(strict=True)
    requirement = load_requirement_snapshot(snapshot_dir=root / "requirements" / requirement_id)
    validate_execution_authority(repo_root=root, requirement=requirement)
    authority = load_r4_fixture_authority(repo_root=root, requirement=requirement)
    index = _read_corpus(repo_root=root, requirement=requirement, authority=authority)
    from .r4_run_store import load_r4_fixture_company_authority
    company_authority = load_r4_fixture_company_authority(repo_root=root, requirement=requirement)
    paths = set(requirement_authority_paths(repo_root=root, requirement=requirement))
    paths.add(corpus_index(requirement["requirement_id"]))
    paths.add("outputs/active_publication.json")
    paths.update(_source_ledger_paths(repo_root=root, authority=authority))
    paths.update(entry["directory"] + "/" + name for entry in index["cases"]
                 for name in entry["files"])
    for declaration in authority["sources"].values():
        paths.add(declaration["source_repo_relative_path"])
        structured = declaration["structured_source_authority"]
        if structured is not None:
            paths.update(structured[key]["path"] for key in ("accession_xbrl", "submissions"))
    bindings = {p: _file_binding(repo_root=root, relative=p) for p in sorted(paths)}
    return LiveScopedReaderSession(factory=_SESSION_FACTORY, root=root, requirement=requirement,
        authority=authority, index=index, base_files=bindings, company_authority=company_authority)


@dataclass(frozen=True, init=False)
class LiveScopedReaderRequest:
    """Exact private repository capture, distinct from an offline Reader plan."""

    record_bytes: bytes
    request_bytes: bytes
    provider_request_body_bytes: bytes
    output_schema_bytes: bytes
    task_contract_bytes: bytes
    _session: LiveScopedReaderSession
    _factory: object

    def __init__(self, *, factory, record_bytes, request_bytes, provider_request_body_bytes,
                 output_schema_bytes, task_contract_bytes, session):
        if factory is not _REQUEST_FACTORY or type(session) is not LiveScopedReaderSession:
            raise LiveScopedReaderError("Live-scoped request requires its repository factory")
        for name, value in (("record_bytes", record_bytes), ("request_bytes", request_bytes),
                            ("provider_request_body_bytes", provider_request_body_bytes),
                            ("output_schema_bytes", output_schema_bytes),
                            ("task_contract_bytes", task_contract_bytes)):
            if type(value) is not bytes or not value:
                raise LiveScopedReaderError("Live-scoped captured bytes are incomplete")
            object.__setattr__(self, name, value)
        object.__setattr__(self, "_session", session)
        object.__setattr__(self, "_factory", factory)

    @property
    def identity(self):
        return strict_json_loads(text=self.record_bytes.decode("utf-8"))

    @property
    def repository_root(self):
        return self._session._root


def _capture(*, session: LiveScopedReaderSession, fixture_id: str) -> LiveScopedReaderRequest:
    from .ai_adapter import approved_scoped_transport_policy, build_scoped_provider_request_body
    from .r4_run_store import resolve_r4_run_target_period
    fixture, entry, source, scope, authority = session._fixture(fixture_id)
    scoped = prepare_scoped_reader_request_in_session(context=source["scoped"],
        source_scope_manifest_id=scope["source_scope_manifest_id"])
    body = strict_json_loads(text=scoped.request_bytes.decode("utf-8"))
    body.pop("scoped_plan_id")
    body["record_type"] = INPUT_RECORD_TYPE
    reader_bytes = canonical_json_bytes(value=body)
    task_bytes = _json_bytes(authority["task_contract"])
    policy = approved_scoped_transport_policy(requirement=session._requirement)
    outbound, schema = build_scoped_provider_request_body(policy=policy, reader_request_bytes=reader_bytes)
    declaration = session._authority["sources"][fixture["source_id"]]
    company = session._company(fixture["source_id"])
    if (company["company_id"] != declaration["company_id"]
            or str(int(company["cik"])) != str(int(declaration["cik"]))):
        raise LiveScopedReaderError("Fixture company authority differs from source identity")
    relative_paths = set(session._base_files)
    relative_paths.add(declaration["source_repo_relative_path"])
    relative_paths.update(entry["directory"] + "/" + name for name in entry["files"])
    structured = declaration["structured_source_authority"]
    if structured is not None:
        relative_paths.update(structured[k]["path"] for k in ("accession_xbrl", "submissions"))
    bindings = {p: _file_binding(repo_root=session._root, relative=p) for p in sorted(relative_paths)}
    for name, binding in entry["files"].items():
        if bindings[entry["directory"] + "/" + name] != binding:
            raise LiveScopedReaderError("Scoped corpus changed after its native read-back")
    fields = ("artifact_requirement_generation", "requirement_id", "requirement_closure_hash",
        "requirement_hashes", "source_scope_manifest_id", "source_sha256",
        "full_derived_asset_id", "full_reader_input_manifest_id", "task_contract_id", "task_contract_hash",
        "task_contract_generation", "task_period")
    record = {key: scope[key] for key in fields}
    proof = scope["source_bound_proof"]
    disclosed = None if proof is None else proof["disclosed_period"]
    record.update(record_type=REQUEST_RECORD_TYPE, schema_version=1,
        fixture_id=fixture_id, fixture_class=fixture["fixture_class"], metric_id=fixture["metric_id"],
        source_id=fixture["source_id"], source_repo_relative_path=declaration["source_repo_relative_path"],
        source_size=declaration["source_size"], raw_asset_id=authority["raw_blob"]["raw_asset_id"],
        source_reference_ids=list(authority["reader_manifest"]["source_reference_ids"]),
        fixture_company_authority_id=company["fixture_company_authority_id"],
        company_traits=list(company["company_traits"]),
        source_metadata={key: declaration[key] for key in
            ("company_id", "cik", "accession", "document_name", "source_url", "media_type")},
        disclosed_period=None if disclosed is None else {key: disclosed[key] for key in
            ("period_label", "period_start", "period_end", "averaging_period", "must_not_claim_annual_average")},
        source_bound_proof_id=None if proof is None else proof["source_bound_proof_id"],
        task_spec_semantic_hash=authority["task_contract"]["task_spec_semantic_hash"],
        output_schema_hash=authority["task_contract"]["output_schema_hash"],
        system_prompt_hash=authority["task_contract"]["system_prompt_hash"],
        catalog_task_contract_hash=authority["task_contract"]["catalog_task_contract_hash"],
        window_binding=body["window_binding"], corpus_index_id=session._index["index_id"],
        reader_payload_sha256=sha256_bytes(content=reader_bytes),
        provider_request_body_sha256=sha256_bytes(content=outbound),
        provider_request_body_size=len(outbound), provider_output_schema_sha256=sha256_bytes(content=schema),
        task_contract_bytes_sha256=sha256_bytes(content=task_bytes),
        provider_policy_record_hash=content_hash(value=session._requirement["effective_decisions"]["S-PROVIDER-TRANSPORT"]),
        file_bindings=bindings, execution_authorization="NOT_ISSUED")
    record["target_period"] = resolve_r4_run_target_period(
        request_record=record, fixture_company=company)
    record["target_period_identity"] = content_hash(value={
        "task_period": record["task_period"], "target_period": record["target_period"],
        "source_bound_proof_id": record["source_bound_proof_id"],
        "fixture_company_authority_id": record["fixture_company_authority_id"]})
    record["live_scoped_reader_request_id"] = content_hash(value=record)
    return LiveScopedReaderRequest(factory=_REQUEST_FACTORY, record_bytes=canonical_json_bytes(value=record),
        request_bytes=reader_bytes, provider_request_body_bytes=outbound, output_schema_bytes=schema,
        task_contract_bytes=task_bytes, session=session)


def prepare_live_scoped_reader_request(*, repo_root: Path, fixture_id: str,
    requirement_id: str = "issue_28_v2", session: LiveScopedReaderSession = None) -> LiveScopedReaderRequest:
    """Build from a repository fixture and certified scope, never caller bytes."""
    if session is None:
        session = prepare_live_scoped_reader_session(repo_root=repo_root, requirement_id=requirement_id)
    if (type(session) is not LiveScopedReaderSession or session._root != repo_root.resolve(strict=True)
            or session._requirement["requirement_id"] != requirement_id):
        raise LiveScopedReaderError("Live-scoped session/repository/Requirement differs")
    return _capture(session=session, fixture_id=fixture_id)


def rebuild_live_scoped_reader_request(*, request: object) -> LiveScopedReaderRequest:
    """Recheck files and recompute proof/packing/envelope before socket dispatch."""
    if type(request) is not LiveScopedReaderRequest or request._factory is not _REQUEST_FACTORY:
        raise LiveScopedReaderError("An exact repository LiveScopedReaderRequest is required")
    record = request.identity
    _check_files(repo_root=request.repository_root, bindings=record["file_bindings"])
    fixture, entry, source, scope, authority = request._session._fixture(record["fixture_id"])
    proof = scope["source_bound_proof"]
    if proof is not None:
        source["evidence"].verify_source_bound_proof(proof=proof,
            expected_proof_id=proof["source_bound_proof_id"], task_contract_id=fixture["task_contract_id"])
    rebuilt = _capture(session=request._session, fixture_id=record["fixture_id"])
    if any(getattr(rebuilt, field) != getattr(request, field) for field in
           ("record_bytes", "request_bytes", "provider_request_body_bytes", "output_schema_bytes", "task_contract_bytes")):
        raise LiveScopedReaderError("Live-scoped request identity or captured bytes drifted")
    return rebuilt


@dataclass(frozen=True, init=False)
class ScopedInvocationAcceptanceContext:
    """Private full-source acceptance inputs; no caller Candidate or verdict."""

    _request: LiveScopedReaderRequest
    _factory: object
    execution_context: object

    def __init__(self, *, factory, request, execution_context=None):
        if factory is not _ACCEPTANCE_FACTORY or type(request) is not LiveScopedReaderRequest:
            raise LiveScopedReaderError("Scoped acceptance requires its repository factory")
        if execution_context is not None:
            from .r4_live_authority import R4ExecutionPlanContext
            if (type(execution_context) is not R4ExecutionPlanContext
                    or execution_context._session is not request._session):
                raise LiveScopedReaderError("Scoped acceptance execution context differs")
        object.__setattr__(self, "_request", request)
        object.__setattr__(self, "_factory", factory)
        object.__setattr__(self, "execution_context", execution_context)

    @property
    def authority(self):
        record = self._request.identity
        prepared = self._request._session._fixture(record["fixture_id"])
        scope, owned = prepared[-2:]
        # Expose immutable large graphs and fresh bounded metadata copies. A
        # caller must not obtain mutable aliases to the private acceptance state.
        copied = {key: strict_json_loads(text=_json_bytes(owned[key]).decode("utf-8"))
                  for key in ("requirement", "raw_blob", "source_reference", "task_contract")}
        copied.update(repo_root=owned["repo_root"], source_bytes=owned["source_bytes"],
            full_derived_asset=owned["full_derived_asset"], reader_manifest=owned["reader_manifest"],
            source_scope_manifest=strict_json_loads(text=_json_bytes(scope).decode("utf-8")),
            fixture_company_authority=self._request._session._company(record["source_id"]),
            evidence_authority_payload={
                "system_contract": dict(owned["evidence_authority_payload"]["system_contract"]),
                "task_contract": copied["task_contract"], "reader_input_manifest": owned["reader_manifest"],
                "untrusted_table_data": owned["evidence_authority_payload"]["untrusted_table_data"]})
        return copied

    @property
    def full_derived_asset_bytes(self):
        source = self._request._session._fixture(self._request.identity["fixture_id"])[2]
        return source["asset_bytes"]

    @property
    def compiled_spec(self):
        authority = self.authority
        metric = self._request.identity["metric_id"]
        task = authority["task_contract"]
        if task["metric_ids"] != [metric] or len(task["metric_spec_paths"]) != 1:
            raise LiveScopedReaderError("Scoped acceptance task MetricSpec set differs")
        path = resolve_repository_file(repo_root=self._request.repository_root,
                                       repo_relative_path=task["metric_spec_paths"][0])
        compiled = compile_spec_file(path=path)
        if (compiled["spec_semantic_hash"] != task["metric_spec_semantic_hashes"][0]
                or compiled["spec_closure_hash"] != task["metric_spec_closure_hashes"][0]):
            raise LiveScopedReaderError("Scoped acceptance MetricSpec differs from task authority")
        return compiled


def build_scoped_invocation_acceptance_context(*,
    request: LiveScopedReaderRequest, execution_context=None) -> ScopedInvocationAcceptanceContext:
    rebuilt = rebuild_live_scoped_reader_request(request=request)
    return ScopedInvocationAcceptanceContext(factory=_ACCEPTANCE_FACTORY, request=rebuilt,
                                              execution_context=execution_context)


def _acceptance_inputs(*, context: ScopedInvocationAcceptanceContext):
    if (type(context) is not ScopedInvocationAcceptanceContext
            or context._factory is not _ACCEPTANCE_FACTORY):
        raise LiveScopedReaderError("An exact repository scoped acceptance context is required")
    request = rebuild_live_scoped_reader_request(request=context._request)
    return request, request._session._fixture(request.identity["fixture_id"])


def parse_scoped_invocation_candidate(*, response_body: bytes, execution_id: str,
                                     context: ScopedInvocationAcceptanceContext) -> dict:
    """Use the existing Reader and approved deterministic enrichment only."""
    from .reader import validate_reader_output, validate_source_bound_reader_output
    from .invocation_control import SchemaViolationError
    try:
        request, (fixture, entry, source, scope, authority) = _acceptance_inputs(context=context)
        if type(response_body) is not bytes:
            raise LiveScopedReaderError("Scoped response must be exact bytes")
        attempt_id = "attempt:" + execution_id.split(":", maxsplit=1)[1]
        text = response_body.decode("utf-8")
        proof = scope["source_bound_proof"]
        if proof is None:
            task = authority["task_contract"]
            candidate = validate_reader_output(response_text=text, attempt_id=attempt_id,
                required_roles=task["required_roles"], scope_contract=task["scope_contract"],
                source_reference_ids=list(authority["reader_manifest"]["source_reference_ids"]),
                derived_asset_ids=[authority["full_derived_asset"]["derived_asset_id"]])
        else:
            candidate = validate_source_bound_reader_output(response_text=text, attempt_id=attempt_id,
                source_bound_proof=proof, expected_proof_id=proof["source_bound_proof_id"],
                requirement=authority["requirement"], repo_root=request.repository_root,
                source_bytes=authority["source_bytes"], raw_blob=authority["raw_blob"],
                source_reference=authority["source_reference"], full_derived_asset=authority["full_derived_asset"],
                task_contract=authority["task_contract"], _offline_context=source["evidence"])
        if candidate["disclosure_group"] != authority["task_contract"]["disclosure_group"]:
            raise LiveScopedReaderError("Scoped response disclosure task differs")
        return candidate
    except (ValueError, UnicodeError, KeyError, IndexError, TypeError) as error:
        raise SchemaViolationError("Native scoped Reader rejected the response") from error


def validate_scoped_invocation_acceptance(*, response_body: bytes, execution_id: str,
    context: ScopedInvocationAcceptanceContext) -> dict:
    """Produce native controller acceptance, never an offline attempt record."""
    from .invocation_control import EvidenceFailureError
    from .scoped_reader import check_scoped_reader_response
    try:
        request, (fixture, entry, source, scope, authority) = _acceptance_inputs(context=context)
        prepared = prepare_scoped_reader_request_in_session(context=source["scoped"],
            source_scope_manifest_id=scope["source_scope_manifest_id"])
        label_rule = bound_label_policy(request._session._requirement)
        checked = check_scoped_reader_response(prepared_request=prepared,
            response_text=response_body.decode("utf-8"),
            attempt_id="attempt:" + execution_id.split(":", maxsplit=1)[1],
            source_scope_manifest=scope, expected_manifest_id=scope["source_scope_manifest_id"],
            _verified_scope_context=source["scoped"], _label_policy=label_rule, **authority)
        candidate, evidence = checked["candidate"], checked["evidence"]
        if evidence["status"] != "PASS" or evidence["system_approval_eligible"] is not True:
            raise LiveScopedReaderError("Native scoped Evidence did not certify the response")
        return {
            "reader_input_manifest_id": authority["reader_manifest"]["reader_input_manifest_id"],
            "derived_asset_id": authority["full_derived_asset"]["derived_asset_id"],
            "source_reference_ids": list(authority["reader_manifest"]["source_reference_ids"]),
            "task_contract_hash": "sha256:" + sha256_bytes(content=request.task_contract_bytes),
            "spec_semantic_hash": authority["task_contract"]["task_spec_semantic_hash"],
            "candidate_hash": candidate["candidate_hash"], "candidate_record": candidate,
            "evidence_check_id": evidence["evidence_check_id"], "evidence_record": evidence,
            "evidence_candidate_hash": evidence["candidate_hash"], "evidence_status": evidence["status"],
            "validator_semantic_version": (SCOPED_ACCEPTANCE_VERSION if label_rule == RAW_LABEL_POLICY
                else "source-bound-scoped-reader-acceptance-v2"),
            "validator_semantic_hash": (SCOPED_ACCEPTANCE_HASH if label_rule == RAW_LABEL_POLICY
                else content_hash(value={"parent":SCOPED_ACCEPTANCE_HASH,"label_policy":label_rule})),
        }
    except (ValueError, UnicodeError, KeyError, IndexError, TypeError) as error:
        raise EvidenceFailureError("Native scoped Evidence rejected the response") from error


def _replay_scoped_attempt(*, repo_root: Path, request_record: Mapping, payloads: Mapping,
    invocation_plan: Mapping, execution_receipt: Mapping, acceptance_receipt: Mapping,
    authorization_binding: Mapping, terminal_bundle: Mapping,
    acceptance_context: ScopedInvocationAcceptanceContext = None, execution_context=None) -> dict:
    """Read-only replay of exact persisted scoped bytes and native terminals.

    A current child may provide its exact private immutable context. Independent
    disk replay omits it and reconstructs the source, full asset and certificate
    through the guarded repository factory. No adapter or opener is created.
    """
    from .ai_adapter import approved_scoped_transport_policy, executed_scoped_request_record
    from .ai_adapter import _controller_usage, _qualification_usage_error
    from .ai_adapter import _deepseek_chat_output_text, _provider_output_text
    from .ai_adapter import validate_scoped_wire_journal, _scoped_native_attempt
    from .ai_adapter import _failed_controlled_observation, _no_egress_policy_observation
    from .invocation_control import validate_successor_execution_receipt
    from .r4_live_authority import REQUEST_BINDING_FIELDS, RUNTIME_ROOT
    from .r4_live_authority import R4ExecutionPlanContext, prepare_r4_execution_context
    from .r4_live_authority import validate_portable_authorization_binding
    if type(request_record) is not dict or request_record.get("record_type") != "R4_EXECUTED_SCOPED_READER_REQUEST":
        raise LiveScopedReaderError("Persisted scoped request subtype is not explicit")
    if (type(authorization_binding) is not dict
            or authorization_binding.get("record_type") != "R4_EXECUTION_AUTHORIZATION_BINDING"
            or type(authorization_binding.get("schema_version")) is not int
            or authorization_binding["schema_version"] != 1
            or authorization_binding.get("authorization_id") != content_hash(value={
                k: v for k, v in authorization_binding.items() if k != "authorization_id"})):
        raise LiveScopedReaderError("Portable scoped authorization binding is invalid")
    mode = authorization_binding.get("execution_mode")
    if (mode not in {"LIVE", "RECORDED_TEST"}
            or (mode == "RECORDED_TEST" and authorization_binding.get("owner_receipt_id") is not None)
            or (mode == "LIVE" and not authorization_binding.get("owner_receipt_id"))
            or authorization_binding.get("automatic_retry_count") != 0
            or authorization_binding.get("context_limit_tokens") != 200000
            or authorization_binding.get("response_reuse_authorized") is not False
            or authorization_binding.get("sec_calls_authorized") is not False
            or "owner_token" in authorization_binding or "invocation_workspace" in authorization_binding):
        raise LiveScopedReaderError("Portable scoped authorization mode or safety bounds differ")
    for key in ("pending_plan_id", "entry_id", "owner_token_hash"):
        if (type(authorization_binding.get(key)) is not str
                or re.fullmatch(r"sha256:[0-9a-f]{64}", authorization_binding[key]) is None):
            raise LiveScopedReaderError("Portable scoped authorization identity is malformed: " + key)
    namespace = RUNTIME_ROOT + "/" + authorization_binding["pending_plan_id"].split(":", 1)[1]
    namespace += "/entries/" + authorization_binding["entry_id"].split(":", 1)[1]
    if authorization_binding.get("invocation_namespace") != namespace:
        raise LiveScopedReaderError("Portable invocation namespace differs from plan/entry")
    if acceptance_context is None:
        request = prepare_live_scoped_reader_request(repo_root=repo_root,
            fixture_id=request_record["fixture_id"], requirement_id=request_record["requirement_id"])
        acceptance_context = build_scoped_invocation_acceptance_context(request=request)
    else:
        if type(acceptance_context) is not ScopedInvocationAcceptanceContext:
            raise LiveScopedReaderError("Warm replay requires the exact private acceptance context")
        request = rebuild_live_scoped_reader_request(request=acceptance_context._request)
        if request.repository_root != repo_root.resolve(strict=True):
            raise LiveScopedReaderError("Warm replay context belongs to another repository")
    if execution_context is None:
        execution_context = acceptance_context.execution_context
    if execution_context is None:
        execution_context = prepare_r4_execution_context(repo_root=request.repository_root,
                                                         session=request._session)
    if (type(execution_context) is not R4ExecutionPlanContext
            or execution_context._session is not request._session):
        raise LiveScopedReaderError("Portable authorization uses another execution source context")
    validate_portable_authorization_binding(binding=authorization_binding, context=execution_context)
    capture = request.identity
    expected_record = executed_scoped_request_record(capture=capture,
        authorization=authorization_binding, execution_id=execution_receipt["execution_id"])
    if request_record != expected_record:
        raise LiveScopedReaderError("Executed scoped request differs from independent repository capture")
    if (authorization_binding.get("request_identity") != {key: capture[key] for key in REQUEST_BINDING_FIELDS}
            or any(authorization_binding[key] != capture[key] for key in
                   ("artifact_requirement_generation", "requirement_id", "requirement_closure_hash", "requirement_hashes", "fixture_id"))):
        raise LiveScopedReaderError("Portable authorization names another exact scoped request")
    required_payloads = {"request_body", "reader_payload", "task_contract", "output_schema"}
    if (type(payloads) is not dict or not required_payloads.issubset(payloads)
            or set(payloads) - required_payloads - {"assistant_output", "raw_response"}
            or any(type(value) is not bytes for value in payloads.values())
            or payloads["request_body"] != request.provider_request_body_bytes
            or payloads["reader_payload"] != request.request_bytes
            or payloads["task_contract"] != request.task_contract_bytes
            or payloads["output_schema"] != request.output_schema_bytes):
        raise LiveScopedReaderError("Persisted scoped payload bytes differ from their exact capture")
    if (invocation_plan.get("release_input_plan_id") != authorization_binding["entry_id"]
            or invocation_plan.get("source_identity_hash") != capture["full_reader_input_manifest_id"]
            or invocation_plan.get("selected_representation_hash") != capture["full_derived_asset_id"]
            or invocation_plan.get("task_contract_hash") != "sha256:" + capture["task_contract_bytes_sha256"]
            or invocation_plan.get("output_schema_hash") != "sha256:" + capture["provider_output_schema_sha256"]
            or invocation_plan.get("provider_request_body_sha256") != capture["provider_request_body_sha256"]):
        raise LiveScopedReaderError("Persisted invocation plan differs from scoped payload authority")
    response = payloads.get("assistant_output", payloads.get("raw_response", b""))
    validate_successor_execution_receipt(receipt=dict(execution_receipt), plan=dict(invocation_plan),
        authorization_binding=authorization_binding, response_body=response,
        acceptance_receipt=acceptance_receipt, terminal_bundle=terminal_bundle,
        repo_root=request.repository_root, authority=request._session._invocation_authority)
    raw = payloads.get("raw_response")
    attempts = execution_receipt["attempts"]
    journal = terminal_bundle.get("wire_journal")
    policy = approved_scoped_transport_policy(requirement=request._session._requirement)
    if journal is not None:
        observed = validate_scoped_wire_journal(journal=journal, plan=invocation_plan,
            execution_receipt=execution_receipt, terminal_bundle=terminal_bundle,
            request_body=request.provider_request_body_bytes, raw_response_bytes=raw,
            assistant_output_bytes=payloads.get("assistant_output"))
        provider_request_id = journal["provider_request_id"]
    else:
        if "raw_response" in payloads or "assistant_output" in payloads or execution_receipt["status"] == "SUCCEEDED":
            raise LiveScopedReaderError("Known scoped response lacks its original-wire journal")
        observed = (_failed_controlled_observation(policy=policy, outbound=request.provider_request_body_bytes,
                    egress_attempted=True) if mode == "LIVE" and execution_receipt["status"] == "UNKNOWN_REMOTE_OUTCOME"
                    else _no_egress_policy_observation(policy=policy, request_bytes=request.provider_request_body_bytes))
        provider_request_id = attempts[0]["provider_request_id"] if attempts else ""
    if attempts and attempts[0]["usage"] != _controller_usage(raw_response_bytes=raw):
        raise LiveScopedReaderError("Persisted usage differs from the original provider wire bytes")
    candidate = evidence = None
    if execution_receipt["status"] == "SUCCEEDED":
        if raw is None or "assistant_output" not in payloads:
            raise LiveScopedReaderError("Successful scoped replay lacks original provider/assistant bytes")
        parser = _deepseek_chat_output_text if policy.provider == "deepseek" else _provider_output_text
        response_id, returned_model, text = parser(raw_response_bytes=raw)
        if returned_model != policy.model or text.encode("utf-8") != response:
            raise LiveScopedReaderError("Provider wire response does not reconstruct the accepted scoped output")
        if mode == "RECORDED_TEST" and attempts[0]["provider_request_id"] != response_id:
            raise LiveScopedReaderError("Recorded provider response identity differs")
        if _qualification_usage_error(raw_response_bytes=raw,
            policy={"actual_prompt_tokens_max": 200000, "terminal_error_class": "CONTEXT_LIMIT"}):
            raise LiveScopedReaderError("Accepted scoped response lacks valid terminal usage")
        draft = validate_scoped_invocation_acceptance(response_body=response,
            execution_id=execution_receipt["execution_id"], context=acceptance_context)
        body = {"schema_version": 1, "record_type": "INVOCATION_ACCEPTANCE_RECEIPT",
            "ai_invocation_plan_id": invocation_plan["ai_invocation_plan_id"],
            "provider_request_identity": invocation_plan["provider_request_identity"],
            "response_body_sha256": sha256_bytes(content=response), **draft}
        expected_acceptance = {**body, "acceptance_receipt_id": content_hash(value=body)}
        if acceptance_receipt != expected_acceptance:
            raise LiveScopedReaderError("Persisted acceptance differs from native scoped Evidence replay")
        candidate, evidence = draft["candidate_record"], draft["evidence_record"]
    elif acceptance_receipt is not None:
        raise LiveScopedReaderError("Failed scoped replay cannot carry accepted Candidate/Evidence")
    native_attempt = _scoped_native_attempt(request=request, context=acceptance_context,
        execution=execution_receipt, observation=observed, provider_request_id=provider_request_id,
        raw_response=raw, assistant_output=payloads.get("assistant_output"),
        started=terminal_bundle["egress_markers"][0]["egress_started_at_utc"],
        finished=execution_receipt["finished_at_utc"])
    return {"prepared_request": request, "acceptance_context": acceptance_context,
        "authority": acceptance_context.authority, "compiled_spec": acceptance_context.compiled_spec,
        "candidate_record": candidate, "evidence_record": evidence,
        "native_attempt_record": native_attempt, "transport_observation": observed.as_mapping(),
        "full_derived_asset_bytes": acceptance_context.full_derived_asset_bytes}


def replay_scoped_attempt(*, repo_root: Path, request_record: Mapping, payloads: Mapping,
    invocation_plan: Mapping, execution_receipt: Mapping, acceptance_receipt: Mapping,
    authorization_binding: Mapping, terminal_bundle: Mapping,
    acceptance_context: ScopedInvocationAcceptanceContext = None, execution_context=None) -> dict:
    """Turn malformed persisted artifacts into a stable scoped replay failure."""
    from .ai_adapter import AIAdapterError
    try:
        return _replay_scoped_attempt(repo_root=repo_root, request_record=request_record,
            payloads=payloads, invocation_plan=invocation_plan, execution_receipt=execution_receipt,
            acceptance_receipt=acceptance_receipt, authorization_binding=authorization_binding,
            terminal_bundle=terminal_bundle, acceptance_context=acceptance_context,
            execution_context=execution_context)
    except (KeyError, TypeError, IndexError, UnicodeError, AIAdapterError) as error:
        raise LiveScopedReaderError("Malformed persisted scoped execution: " + str(error)) from error
