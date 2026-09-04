"""Persist and natively replay explicit successor R4 scoped Runs.

This module is the narrow join between the existing Run store and the dormant
R4 scoped transport.  It does not create a provider, grant live authority,
qualify a cycle, or publish a Result.  Every large or security-relevant input
is reloaded from its exact repository or Run-relative bytes before a Run can
freeze.
"""

from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Mapping, Optional, Sequence, Tuple

from .canonical import (
    atomic_write_bytes,
    canonical_json_bytes,
    content_hash,
    sha256_bytes,
    sha256_file,
    strict_json_file,
    strict_json_loads,
)
from .records import (
    EXPLICIT_ARTIFACT_GENERATION,
    R4_EXECUTION_ARTIFACT_KINDS,
    R4_SCOPED_ATTEMPT_TYPE,
    R4_SCOPED_PROTOCOL,
    R4_SCOPED_RUN_TYPE,
    SOURCE_BOUND_CANDIDATE_TYPE,
    validate_record,
    validate_run_coordinates,
)
from .requirement_profile import validate_execution_authority
from .requirements import load_requirement_snapshot
from .sources import resolve_repository_file
from .specs import SEMANTIC_SET_PATHS, compile_spec_file
from .table_task_contracts import _table_task_semantic, table_task_run_binding
from .traits import repository_company_ciks, repository_company_traits


COMPANY_AUTHORITY_PATH = "config/r4_fixture_company_authority_v1.json"
COMPANY_AUTHORITY_FIELDS = frozenset({
    "record_type", "schema_version", "authority_id", "scope",
    "target_period_resolution", "annual_reinterpretation_allowed",
    "profile_catalog", "company_registry", "owner_source_designation",
    "entries",
})
COMPANY_ENTRY_FIELDS = frozenset({
    "source_id", "company_id", "cik", "profile_id", "company_traits",
    "profile_authority", "source_binding", "default_fiscal_period",
    "financial_nature_span",
})
FILE_BINDING_FIELDS = frozenset({"path", "sha256", "size"})
PERIOD_FIELDS = frozenset({"period_label", "period_start", "period_end", "authority"})
SPAN_FIELDS = frozenset({"byte_start", "byte_end", "span_sha256", "exact_text"})
_REGISTRY_PROFILE = "CANONICAL_COMPANY_REGISTRY"
_SOURCE_PROFILE = "OWNER_PINNED_SOURCE_EXACT_FINANCIAL_NATURE_SPAN"
_PERIOD_AUTHORITY = "NATIVE_SOURCE_BOUND_DEI_FISCAL_CONTEXT"
_EXECUTION_ROOT = "r4_execution"


class R4RunStoreError(ValueError):
    """Reject unsafe R4 fixture identity or persisted execution drift."""


def _exact(*, value: object, fields: Sequence[str], label: str) -> Mapping:
    if type(value) is not dict or set(value) != set(fields):
        raise R4RunStoreError(label + " fields are not exact")
    return value


def _file_binding(*, repo_root: Path, value: object, expected_path: str,
                  label: str) -> Path:
    binding = _exact(value=value, fields=FILE_BINDING_FIELDS, label=label)
    if (
        binding["path"] != expected_path
        or type(binding["sha256"]) is not str
        or len(binding["sha256"]) != 64
        or type(binding["size"]) is not int
        or binding["size"] <= 0
    ):
        raise R4RunStoreError(label + " binding is invalid")
    path = resolve_repository_file(
        repo_root=repo_root, repo_relative_path=expected_path,
    )
    if (
        path.stat().st_size != binding["size"]
        or sha256_file(path=path) != binding["sha256"]
    ):
        raise R4RunStoreError(label + " bytes differ")
    return path


def _native_dei_period(*, repo_root: Path, declaration: Mapping) -> Dict[str, str]:
    """Reconstruct exact CIK and fiscal duration from the pinned filing."""
    source_id = str(declaration["source_id"])
    if declaration.get("structured_source_authority") is None:
        from .r4_structured_sources import build_pinned_fixture_source_set
        fixture = build_pinned_fixture_source_set(
            repo_root=repo_root, source_id=source_id,
        )
        dei = fixture["inline_dei"]
        try:
            try:
                document_end = date.fromisoformat(dei["document_period_end"])
            except ValueError:
                document_end = datetime.strptime(
                    dei["document_period_end"], "%B %d, %Y",
                ).date()
            context_start = date.fromisoformat(dei["context_period_start"])
            context_end = date.fromisoformat(dei["context_period_end"])
        except (TypeError, ValueError) as error:
            raise R4RunStoreError("Native fixture fiscal dates are invalid") from error
        if document_end != context_end or context_start >= context_end:
            raise R4RunStoreError("Native fixture fiscal duration/end differs")
        return {
            "cik": str(int(dei["entity_central_index_key"])),
            "fiscal_year": dei["fiscal_year_focus"],
            "period_start": dei["context_period_start"],
            "period_end": dei["context_period_end"],
        }

    from .deterministic_router import parse_accession_xbrl_source
    xbrl = declaration["structured_source_authority"]["accession_xbrl"]
    path = resolve_repository_file(
        repo_root=repo_root, repo_relative_path=xbrl["path"],
    )
    if path.stat().st_size != xbrl["size"] or sha256_file(path=path) != xbrl["sha256"]:
        raise R4RunStoreError("Native fiscal XBRL bytes differ")
    parsed = parse_accession_xbrl_source(raw_bytes=path.read_bytes())
    names = {
        "cik": "dei:entitycentralindexkey",
        "document_type": "dei:documenttype",
        "fiscal_year": "dei:documentfiscalyearfocus",
        "fiscal_period": "dei:documentfiscalperiodfocus",
        "document_end": "dei:documentperiodenddate",
    }
    values: Dict[str, str] = {}
    context_ids = set()
    for field, name in names.items():
        facts = [
            fact for fact in parsed.facts
            if fact["qualified_name"].casefold() == name
        ]
        distinct = {str(fact["text"]) for fact in facts}
        if len(distinct) != 1:
            raise R4RunStoreError("Native fiscal DEI is absent or ambiguous")
        values[field] = distinct.pop()
        context_ids.update(str(fact["context_ref"]) for fact in facts)
    if len(context_ids) != 1:
        raise R4RunStoreError("Native fiscal DEI context is ambiguous")
    context = parsed.contexts[next(iter(context_ids))]
    if (
        values["document_type"] != "10-K"
        or values["fiscal_period"] != "FY"
        or context["dimensions"]
        or context["typed_dimension_count"]
        or int(context["entity_identifier"]) != int(values["cik"])
        or context["period_end"] != values["document_end"]
    ):
        raise R4RunStoreError("Native fiscal DEI identity differs")
    return {
        "cik": str(int(values["cik"])),
        "fiscal_year": values["fiscal_year"],
        "period_start": str(context["period_start"]),
        "period_end": str(context["period_end"]),
    }


def load_r4_fixture_company_authority(
    *, repo_root: Path, requirement: Optional[Mapping] = None,
) -> Dict[str, object]:
    """Load subject traits and fiscal defaults without extending the registry.

    BAC and Citi are qualification-only source fixtures.  The owner-pinned
    acquisition choice selects their exact sources; native DEI binds entity and
    fiscal duration; an exact raw-source span proves the financial nature used
    by the existing profile catalog.  JPM retains the canonical registry path.
    """
    root = repo_root.resolve(strict=True)
    path = resolve_repository_file(
        repo_root=root, repo_relative_path=COMPANY_AUTHORITY_PATH,
    )
    authority = strict_json_file(path=path)
    _exact(
        value=authority, fields=COMPANY_AUTHORITY_FIELDS,
        label="R4 fixture company authority",
    )
    if (
        authority["record_type"] != "R4_FIXTURE_COMPANY_AUTHORITY"
        or type(authority["schema_version"]) is not int
        or authority["schema_version"] != 1
        or authority["scope"] != "R4_SUCCESSOR_FIXTURE_IDENTITY_ONLY"
        or authority["target_period_resolution"]
        != "SOURCE_SCOPE_DISCLOSED_PERIOD_ELSE_NATIVE_DEFAULT"
        or authority["annual_reinterpretation_allowed"] is not False
        or authority["authority_id"] != content_hash(
            value={key: value for key, value in authority.items()
                   if key != "authority_id"}
        )
    ):
        raise R4RunStoreError("R4 fixture company authority identity differs")
    if requirement is not None:
        validate_execution_authority(repo_root=root, requirement=requirement)
        expected = requirement["execution_authority"]["files"].get(
            COMPANY_AUTHORITY_PATH,
        )
        if expected != {
            "sha256": sha256_file(path=path), "size": path.stat().st_size,
        }:
            raise R4RunStoreError(
                "Requirement does not bind R4 fixture company authority"
            )

    profile_path = _file_binding(
        repo_root=root, value=authority["profile_catalog"],
        expected_path="catalog/company_traits.yaml", label="Profile catalog",
    )
    registry_path = _file_binding(
        repo_root=root, value=authority["company_registry"],
        expected_path="config/company_registry.csv", label="Company registry",
    )
    owner_binding = _exact(
        value=authority["owner_source_designation"],
        fields={"path", "sha256", "size", "body_sha256", "json_pointer"},
        label="Owner source designation",
    )
    owner_path = _file_binding(
        repo_root=root,
        value={key: owner_binding[key] for key in FILE_BINDING_FIELDS},
        expected_path="docs/evidence/issue_28_prb_policy_revision.json",
        label="Owner source designation",
    )
    owner = strict_json_file(path=owner_path)
    try:
        owner_body = strict_json_loads(text=owner["raw_body"])
    except (KeyError, TypeError, ValueError) as error:
        raise R4RunStoreError("Owner source designation body is invalid") from error
    if (
        owner_binding["body_sha256"] != owner.get("body_sha256")
        or owner_binding["body_sha256"]
        != sha256_bytes(content=owner["raw_body"].encode("utf-8"))
        or owner_binding["json_pointer"] != "/sec_acquisition/sources"
        or owner.get("evidence_scope") != "POLICY_CONTENT_ONLY"
        or owner.get("provider_paid_live_publication_authorization") is not False
        or owner.get("record_type") != "OWNER_POLICY_COMMENT_EVIDENCE"
        or owner_body.get("decision") != "APPROVE_R4_PRB_POLICY_REVISION"
        or owner_body.get("scope") != "PR_B_OFFLINE_IMPLEMENTATION_ONLY"
    ):
        raise R4RunStoreError("Owner source designation provenance differs")
    if requirement is not None:
        policy_sources = [
            source for source in requirement["baseline"]["policy_evidence"]
            if source.get("evidence_path") == owner_binding["path"]
        ]
        if len(policy_sources) != 1:
            raise R4RunStoreError("Requirement owner source provenance is absent")
        policy_source = policy_sources[0]
        if (
            policy_source["text"] != owner["raw_body"]
            or policy_source["author"] != owner["author"]
            or policy_source["source_url"] != owner["owner_comment_url"]
            or policy_source["published_at_utc"] != owner["published_at_utc"]
            or policy_source["source_sha256"] != owner["body_sha256"]
        ):
            raise R4RunStoreError("Owner source provenance differs from Requirement")
    selected_sources = owner_body.get("sec_acquisition", {}).get("sources")
    if type(selected_sources) is not list:
        raise R4RunStoreError("Owner source designation set is absent")

    profile_catalog = strict_json_file(path=profile_path)
    try:
        financial_traits = profile_catalog["profile_traits"]["financial_institution"]
    except (KeyError, TypeError) as error:
        raise R4RunStoreError("Financial profile trait mapping is absent") from error
    if financial_traits != ["financial"]:
        raise R4RunStoreError("Financial profile trait mapping differs")

    from .r4_fixture_authority import load_r4_fixture_authority
    fixture_authority = load_r4_fixture_authority(
        repo_root=root, requirement=requirement,
    )
    entries = authority["entries"]
    if type(entries) is not list or not entries:
        raise R4RunStoreError("R4 fixture company entries are absent")
    resolved = {}
    source_designated = []
    for entry in entries:
        _exact(value=entry, fields=COMPANY_ENTRY_FIELDS,
               label="R4 fixture company entry")
        source_id = entry["source_id"]
        if type(source_id) is not str or source_id in resolved:
            raise R4RunStoreError("R4 fixture company source is duplicated")
        if source_id not in fixture_authority["sources"]:
            raise R4RunStoreError("R4 fixture company source is absent")
        declaration = fixture_authority["sources"][source_id]
        source_binding = _exact(
            value=entry["source_binding"], fields=FILE_BINDING_FIELDS,
            label="R4 fixture source",
        )
        expected_source = {
            "path": declaration["source_repo_relative_path"],
            "sha256": declaration["source_sha256"],
            "size": declaration["source_size"],
        }
        if source_binding != expected_source:
            raise R4RunStoreError("R4 fixture source declaration differs")
        source_path = _file_binding(
            repo_root=root, value=source_binding,
            expected_path=expected_source["path"], label="R4 fixture source",
        )
        if (
            entry["company_id"] != declaration["company_id"]
            or str(int(entry["cik"])) != str(int(declaration["cik"]))
            or entry["profile_id"] != "financial_institution"
            or entry["company_traits"] != financial_traits
        ):
            raise R4RunStoreError("R4 fixture company/profile identity differs")
        native = _native_dei_period(repo_root=root, declaration=declaration)
        period = _exact(
            value=entry["default_fiscal_period"], fields=PERIOD_FIELDS,
            label="R4 fixture default period",
        )
        expected_period = {
            "period_label": "FY" + native["fiscal_year"],
            "period_start": native["period_start"],
            "period_end": native["period_end"],
            "authority": _PERIOD_AUTHORITY,
        }
        if str(int(entry["cik"])) != native["cik"] or period != expected_period:
            raise R4RunStoreError("R4 fixture native entity/period differs")

        profile_authority = entry["profile_authority"]
        if profile_authority == _REGISTRY_PROFILE:
            if entry["financial_nature_span"] is not None:
                raise R4RunStoreError("Registry profile has a foreign source span")
            try:
                traits = repository_company_traits(
                    repo_root=root, company_id=entry["company_id"],
                )
                ciks = repository_company_ciks(
                    repo_root=root, company_id=entry["company_id"],
                )
            except ValueError as error:
                raise R4RunStoreError("Registry fixture identity is invalid") from error
            if traits != entry["company_traits"] or str(int(entry["cik"])) not in ciks:
                raise R4RunStoreError("Registry fixture profile/CIK differs")
            with registry_path.open(mode="r", encoding="utf-8", newline="") as file_obj:
                rows = [row for row in csv.DictReader(file_obj)
                        if row.get("company_id") == entry["company_id"]]
            if len(rows) != 1 or rows[0].get("industry_profile") != entry["profile_id"]:
                raise R4RunStoreError("Registry fixture profile row differs")
        elif profile_authority == _SOURCE_PROFILE:
            source_designated.append(source_id)
            span = _exact(
                value=entry["financial_nature_span"], fields=SPAN_FIELDS,
                label="R4 fixture financial-nature span",
            )
            if (
                type(span["byte_start"]) is not int
                or type(span["byte_end"]) is not int
                or not 0 <= span["byte_start"] < span["byte_end"] <= source_path.stat().st_size
                or type(span["exact_text"]) is not str
                or not span["exact_text"]
            ):
                raise R4RunStoreError("R4 fixture financial-nature offsets are invalid")
            source_bytes = source_path.read_bytes()
            exact = span["exact_text"].encode("utf-8")
            observed = source_bytes[span["byte_start"]:span["byte_end"]]
            legal_financial_terms = (
                b"bank holding company", b"financial holding company",
                b"financial services holding company",
            )
            if (
                observed != exact
                or sha256_bytes(content=observed) != span["span_sha256"]
                or source_bytes.count(observed) != 1
                or not any(term in observed.lower() for term in legal_financial_terms)
            ):
                raise R4RunStoreError("R4 fixture financial-nature span differs")
        else:
            raise R4RunStoreError("R4 fixture profile authority is unknown")
        resolved[source_id] = dict(entry)
    if sorted(source_designated) != sorted(selected_sources):
        raise R4RunStoreError("Owner-designated R4 source exact set differs")
    execution_sources = {
        fixture["source_id"] for fixture in fixture_authority["fixtures"]
        if fixture["artifact_kind"] == "SCOPED_EXTRACTION"
        and fixture["fixture_class"] in {
            "POSITIVE_PRODUCTION", "POSITIVE_ALTERNATE_LAYOUT",
        }
    }
    if set(resolved) != execution_sources:
        raise R4RunStoreError("R4 fixture company execution-source exact set differs")
    return {
        "authority_id": authority["authority_id"],
        "entries": resolved,
        "target_period_resolution": authority["target_period_resolution"],
        "qualification_credit": "NONE_INDIVIDUAL_RUN",
    }


def resolve_r4_fixture_company_authority(
    *, repo_root: Path, requirement: Mapping, source_id: str,
) -> Dict[str, object]:
    """Return one exact subject/fiscal default with the authority identity."""
    authority = load_r4_fixture_company_authority(
        repo_root=repo_root, requirement=requirement,
    )
    if source_id not in authority["entries"]:
        raise R4RunStoreError("R4 fixture company source is absent")
    return {
        **dict(authority["entries"][source_id]),
        "fixture_company_authority_id": authority["authority_id"],
        "target_period_resolution": authority["target_period_resolution"],
    }


def resolve_r4_run_target_period(
    *, request_record: Mapping, fixture_company: Mapping,
) -> Dict[str, object]:
    """Prefer the certified disclosed period; otherwise use native fiscal DEI."""
    disclosed = request_record.get("disclosed_period")
    if disclosed is None:
        period = dict(fixture_company["default_fiscal_period"])
        if request_record.get("task_period") != period["period_label"]:
            raise R4RunStoreError("R4 request period differs from native fiscal default")
    else:
        _exact(
            value=disclosed,
            fields={"period_label", "period_start", "period_end",
                    "averaging_period", "must_not_claim_annual_average"},
            label="R4 disclosed period",
        )
        if (
            request_record.get("source_bound_proof_id") is None
            or request_record.get("task_period") != disclosed["period_label"]
            or disclosed["must_not_claim_annual_average"] is not True
            or disclosed["averaging_period"] != "AS_DISCLOSED_QUARTER_AVERAGE"
        ):
            raise R4RunStoreError("R4 disclosed-period proof binding differs")
        period = {
            "period_label": disclosed["period_label"],
            "period_start": disclosed["period_start"],
            "period_end": disclosed["period_end"],
            "authority": "SOURCE_BOUND_DISCLOSED_PERIOD_PROOF",
        }
    target = {
        "fiscal_year": int(fixture_company["default_fiscal_period"]["period_label"][2:]),
        "period_start": period["period_start"],
        "period_end": period["period_end"],
    }
    validate_run_coordinates(
        target_period=target,
        company_traits=list(fixture_company["company_traits"]),
    )
    default = fixture_company["default_fiscal_period"]
    if (target["period_start"] < default["period_start"]
            or target["period_end"] > default["period_end"]):
        raise R4RunStoreError("R4 target period leaves its native fiscal filing")
    if disclosed is not None and period["period_label"].startswith("FY"):
        raise R4RunStoreError("Disclosed quarter cannot be relabelled as an annual period")
    return target


def _load_run_requirement(*, repo_root: Path, manifest: Mapping) -> Dict[str, object]:
    requirement = load_requirement_snapshot(
        snapshot_dir=repo_root / "requirements" / str(manifest["requirement_id"]),
    )
    if (
        requirement["artifact_requirement_generation"] != EXPLICIT_ARTIFACT_GENERATION
        or requirement["requirement_id"] != manifest["requirement_id"]
        or requirement["requirement_closure_hash"] != manifest["requirement_closure_hash"]
        or requirement["hashes"] != manifest["requirement_hashes"]
    ):
        raise R4RunStoreError("R4 Run Requirement identity differs")
    validate_execution_authority(repo_root=repo_root, requirement=requirement)
    return requirement


def prepare_r4_run_replay_context(
    *, repo_root: Path, run_dir: Path, manifest: Mapping,
) -> object:
    """Build a fresh disk-owned native context; it is never an adapter/grant."""
    from .live_scoped_reader import (
        build_scoped_invocation_acceptance_context,
        prepare_live_scoped_reader_request,
    )
    request_record = _run_artifact(
        run_dir=run_dir, manifest=manifest, artifact_kind="request_record",
    )
    request = prepare_live_scoped_reader_request(
        repo_root=repo_root, fixture_id=request_record["fixture_id"],
        requirement_id=manifest["requirement_id"],
    )
    return build_scoped_invocation_acceptance_context(request=request)


def r4_context_requirement(
    *, repo_root: Path, manifest: Mapping, replay_context: object,
) -> Dict[str, object]:
    """Reuse only a factory-owned Requirement whose exact files remain pinned."""
    from .live_scoped_reader import (
        ScopedInvocationAcceptanceContext,
        rebuild_live_scoped_reader_request,
    )
    if type(replay_context) is not ScopedInvocationAcceptanceContext:
        raise R4RunStoreError("R4 replay requires an exact native acceptance context")
    request = rebuild_live_scoped_reader_request(request=replay_context._request)
    if request.repository_root != repo_root.resolve(strict=True):
        raise R4RunStoreError("R4 replay context belongs to another repository")
    requirement = replay_context.authority["requirement"]
    if (
        requirement["artifact_requirement_generation"] != manifest["artifact_requirement_generation"]
        or requirement["requirement_id"] != manifest["requirement_id"]
        or requirement["requirement_closure_hash"] != manifest["requirement_closure_hash"]
        or requirement["hashes"] != manifest["requirement_hashes"]
    ):
        raise R4RunStoreError("R4 replay context Requirement differs")
    return requirement


def verify_r4_context_sources(
    *, repo_root: Path, manifest: Mapping, records: Sequence[Mapping],
    replay_context: object,
) -> Dict[str, bytes]:
    """Compare Run bytes with the same native-built immutable source context.

    A persisted asset is not accepted merely because it hashes to itself.  It
    must equal the canonical bytes produced by the guarded native parser in
    the exact context.  Current children reuse that context; an independent
    disk read creates it afresh before this function is reached.
    """
    r4_context_requirement(
        repo_root=repo_root, manifest=manifest, replay_context=replay_context,
    )
    authority = replay_context.authority
    raw = [record for record in records if record["record_type"] == "RAW_BLOB"]
    assets = [record for record in records if record["record_type"] == "DERIVED_ASSET"]
    readers = [record for record in records if record["record_type"] == "READER_INPUT_MANIFEST"]
    if len(raw) != 1 or len(assets) != 1 or len(readers) != 1:
        raise R4RunStoreError("R4 Run source/asset/Reader exact set differs")
    from .evidence import _plain_owned
    if (
        raw[0] != authority["raw_blob"]
        or manifest["source_references"] != [authority["source_reference"]]
        or readers[0] != _plain_owned(authority["reader_manifest"])
        or canonical_json_bytes(value=assets[0]) != replay_context.full_derived_asset_bytes
        or sha256_bytes(content=authority["source_bytes"]) != raw[0]["raw_asset_id"][7:]
        or len(authority["source_bytes"]) != raw[0]["byte_length"]
    ):
        raise R4RunStoreError("R4 Run source/asset bytes differ from native context")
    return {raw[0]["raw_asset_id"]: authority["source_bytes"]}


def load_r4_run_task_plans(
    *, repo_root: Path, manifest: Mapping, replay_context: object = None,
) -> Dict[str, Dict[str, object]]:
    """Reconstruct successor task plans without legacy task dispatch."""
    if manifest.get("record_type") != R4_SCOPED_RUN_TYPE:
        raise R4RunStoreError("R4 task-plan loader requires an explicit R4 Run")
    requirement = (
        _load_run_requirement(repo_root=repo_root, manifest=manifest)
        if replay_context is None else r4_context_requirement(
            repo_root=repo_root, manifest=manifest, replay_context=replay_context,
        )
    )
    bindings = manifest.get("task_contract_bindings")
    if type(bindings) is not list or not bindings:
        raise R4RunStoreError("R4 Run task bindings are absent")
    from .r4_task_contracts import resolve_r4_task_contract
    plans = {}
    for binding in bindings:
        if type(binding) is not dict or type(binding.get("task_contract_id")) is not str:
            raise R4RunStoreError("R4 Run task binding is invalid")
        identity = binding["task_contract_id"]
        if identity in plans:
            raise R4RunStoreError("R4 Run task binding is duplicated")
        runtime = resolve_r4_task_contract(
            repo_root=repo_root, requirement=requirement,
            task_contract_id=identity,
        )
        if table_task_run_binding(runtime=runtime) != binding:
            raise R4RunStoreError("R4 Run task binding differs")
        if len(runtime["metric_spec_paths"]) != 1:
            raise R4RunStoreError("R4 Run task MetricSpec set differs")
        path = resolve_repository_file(
            repo_root=repo_root,
            repo_relative_path=runtime["metric_spec_paths"][0],
        )
        metric = compile_spec_file(path=path, dependency_specs={})
        if (
            metric["spec_semantic_hash"] != runtime["metric_spec_semantic_hashes"][0]
            or metric["spec_closure_hash"] != runtime["metric_spec_closure_hashes"][0]
            or metric["compiled"]["metric_id"] != runtime["metric_ids"][0]
        ):
            raise R4RunStoreError("R4 Run task MetricSpec differs")
        semantic = _table_task_semantic(
            runtime=runtime, metric_semantic=metric["compiled"],
        )
        semantic_hash = content_hash(value=semantic, set_paths=SEMANTIC_SET_PATHS)
        if semantic_hash != runtime["task_spec_semantic_hash"]:
            raise R4RunStoreError("R4 Run task semantic identity differs")
        task_spec = {
            "compiled": semantic,
            "spec_semantic_hash": semantic_hash,
            "spec_closure_hash": content_hash(value={
                "catalog_task_contract_hash": runtime["catalog_task_contract_hash"],
                "metric_spec_closure_hashes": runtime["metric_spec_closure_hashes"],
            }),
        }
        plans[identity] = {
            "runtime_task_contract": runtime,
            "task_spec": task_spec,
            "metric_specs": {metric["compiled"]["metric_id"]: metric},
            "run_binding": dict(binding),
        }
    if list(plans) != sorted(plans):
        raise R4RunStoreError("R4 Run task bindings are not ordered")
    return plans


def _run_artifact(
    *, run_dir: Path, manifest: Mapping, artifact_kind: str,
) -> Mapping:
    if artifact_kind not in R4_EXECUTION_ARTIFACT_KINDS:
        raise R4RunStoreError("Unknown R4 execution artifact kind")
    binding = manifest["r4_execution_binding"]["artifact_files"][artifact_kind]
    if binding is None:
        raise R4RunStoreError("R4 execution artifact is absent: " + artifact_kind)
    relative = Path(binding["path"])
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or relative.parts[0] != _EXECUTION_ROOT
    ):
        raise R4RunStoreError("R4 execution artifact path is unsafe")
    path = run_dir / relative
    cursor = run_dir
    if cursor.is_symlink() or not cursor.is_dir():
        raise R4RunStoreError("R4 Run root is unsafe")
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise R4RunStoreError("R4 execution artifact path contains a symlink")
    if (
        path.is_symlink()
        or not path.is_file()
        or path.stat().st_size != binding["size"]
        or sha256_file(path=path) != binding["sha256"]
    ):
        raise R4RunStoreError("R4 execution artifact bytes differ")
    value = strict_json_file(path=path)
    if content_hash(value=value) != manifest["r4_execution_binding"]["identity_hashes"][artifact_kind + "_hash"]:
        raise R4RunStoreError("R4 execution artifact semantic identity differs")
    return value


def r4_run_company_authority(
    *, repo_root: Path, run_dir: Path, manifest: Mapping,
    replay_context: object = None,
) -> Tuple[list, list]:
    """Rebind Run company/period to request, source and fixture authority."""
    requirement = (
        _load_run_requirement(repo_root=repo_root, manifest=manifest)
        if replay_context is None else r4_context_requirement(
            repo_root=repo_root, manifest=manifest, replay_context=replay_context,
        )
    )
    request = _run_artifact(
        run_dir=run_dir, manifest=manifest, artifact_kind="request_record",
    )
    source_id = request.get("source_id")
    fixture = None if replay_context is None else replay_context.authority.get(
        "fixture_company_authority",
    )
    if fixture is None:
        fixture = resolve_r4_fixture_company_authority(
            repo_root=repo_root, requirement=requirement, source_id=source_id,
        )
    metadata = request.get("source_metadata")
    if (
        type(metadata) is not dict
        or fixture.get("source_id") != source_id
        or request.get("fixture_company_authority_id") != fixture["fixture_company_authority_id"]
        or request.get("company_traits") != fixture["company_traits"]
        or metadata.get("company_id") != fixture["company_id"]
        or str(int(metadata.get("cik", "0"))) != str(int(fixture["cik"]))
        or manifest["company_id"] != fixture["company_id"]
        or manifest["company_traits"] != fixture["company_traits"]
        or manifest["target_period"] != resolve_r4_run_target_period(
            request_record=request, fixture_company=fixture,
        )
    ):
        raise R4RunStoreError("R4 Run company/period authority differs")
    return list(fixture["company_traits"]), [str(int(fixture["cik"]))]


def validate_r4_record_set(
    *, manifest: Mapping, records: Sequence[Mapping],
) -> None:
    """Require one complete explicit R4 child graph, never a relabelled legacy set."""
    if manifest.get("record_type") != R4_SCOPED_RUN_TYPE:
        raise R4RunStoreError("R4 record-set validation requires R4 Run subtype")
    if len(manifest["task_contract_bindings"]) != 1 or any(
        record["record_type"] == "TABLE_QUALIFICATION_EVIDENCE" for record in records
    ):
        raise R4RunStoreError("R4 Run cannot inherit legacy qualification/cycle credit")
    attempts = [record for record in records
                if record["record_type"] == R4_SCOPED_ATTEMPT_TYPE]
    if len(attempts) != 1:
        raise R4RunStoreError("R4 Run requires exactly one scoped attempt")
    attempt = attempts[0]
    identity = manifest["r4_execution_binding"]["identity_hashes"]
    if attempt["r4_binding"] != identity:
        raise R4RunStoreError("R4 Run/attempt execution identity differs")
    for field in (
        "artifact_requirement_generation", "requirement_id",
        "requirement_closure_hash", "requirement_hashes",
    ):
        if attempt[field] != manifest[field]:
            raise R4RunStoreError("R4 Run/attempt Requirement identity differs")
    candidates = [record for record in records
                  if record["record_type"] in {
                      "OBSERVATION_CANDIDATE", SOURCE_BOUND_CANDIDATE_TYPE,
                  }]
    evidence = [record for record in records
                if record["record_type"] == "EVIDENCE_CHECK"]
    if attempt["status"] == "SUCCEEDED":
        if len(candidates) != 1 or len(evidence) != 1:
            raise R4RunStoreError("Successful R4 Run requires exact Candidate/Evidence")
        if evidence[0]["candidate_hash"] != candidates[0]["candidate_hash"]:
            raise R4RunStoreError("R4 Candidate/Evidence identity differs")
    elif candidates or evidence:
        raise R4RunStoreError("Failed R4 attempt cannot carry accepted Evidence")
    if attempt["status"] == "FAILED" and any(
        record["record_type"] in {
            "REVIEW_UNIT", "VERIFIED_OBSERVATION", "METRIC_RESULT", "EXECUTION_TRACE",
        }
        for record in records
    ):
        raise R4RunStoreError("Failed R4 attempt cannot carry reviewed/calculated results")


def _artifact_closure(*, values: Mapping[str, Optional[Mapping]]) -> Tuple[dict, dict]:
    if set(values) != set(R4_EXECUTION_ARTIFACT_KINDS):
        raise R4RunStoreError("R4 execution artifact exact set differs")
    identities, files = {}, {}
    for kind in R4_EXECUTION_ARTIFACT_KINDS:
        value = values[kind]
        if value is None:
            if kind != "acceptance_receipt":
                raise R4RunStoreError("Required R4 execution artifact is absent")
            identities[kind + "_hash"] = None
            files[kind] = None
            continue
        if type(value) is not dict:
            raise R4RunStoreError("R4 execution artifact must be an object")
        data = canonical_json_bytes(value=value)
        digest = sha256_bytes(content=data)
        identities[kind + "_hash"] = "sha256:" + digest
        files[kind] = {
            "path": _EXECUTION_ROOT + "/{}_{}.json".format(kind, digest),
            "sha256": digest,
            "size": len(data),
        }
    return identities, files


def _write_execution_artifacts(
    *, run_dir: Path, values: Mapping[str, Optional[Mapping]], files: Mapping,
) -> None:
    for kind in R4_EXECUTION_ARTIFACT_KINDS:
        value = values[kind]
        binding = files[kind]
        if value is None:
            continue
        path = run_dir / binding["path"]
        data = canonical_json_bytes(value=value)
        if path.exists():
            if path.is_symlink() or not path.is_file() or path.read_bytes() != data:
                raise R4RunStoreError("R4 execution artifact path has other bytes")
        else:
            atomic_write_bytes(path=path, content=data)


def _successor_attempt(
    *, native: Mapping, requirement: Mapping, identity_hashes: Mapping,
) -> Dict[str, object]:
    validated = validate_record(record=native)
    if validated["record_type"] != "AI_EXTRACTION_ATTEMPT":
        raise R4RunStoreError("R4 scoped result did not provide a native AI attempt")
    record = {
        **validated,
        "record_type": R4_SCOPED_ATTEMPT_TYPE,
        "artifact_requirement_generation": EXPLICIT_ARTIFACT_GENERATION,
        "requirement_id": requirement["requirement_id"],
        "requirement_closure_hash": requirement["requirement_closure_hash"],
        "requirement_hashes": requirement["hashes"],
        "r4_binding": dict(identity_hashes),
    }
    return validate_record(record=record)


def create_r4_scoped_run(
    *, repo_root: Path, run_dir: Path, attempt_result: object,
    acceptance_context: object = None,
) -> Dict[str, object]:
    """Persist one exact terminal scoped attempt as an OPEN successor Run.

    The result must be the private ``ScopedAttemptResult`` returned by the
    socket-adjacent adapter.  This prevents callers from manufacturing a loose
    dictionary that happens to resemble an execution receipt.
    """
    from .ai_adapter import ScopedAttemptResult
    from .run_store import (
        append_run_records_atomically,
        create_run,
        load_open_run,
        write_attempt_payloads,
    )
    if type(attempt_result) is not ScopedAttemptResult:
        raise R4RunStoreError("R4 Run requires an exact scoped-attempt result")
    values = {
        "request_record": dict(attempt_result.request_identity),
        "invocation_plan": dict(attempt_result.invocation_plan),
        "execution_receipt": dict(attempt_result.execution_receipt),
        "acceptance_receipt": (
            None if attempt_result.acceptance_receipt is None
            else dict(attempt_result.acceptance_receipt)
        ),
        "authorization_binding": dict(attempt_result.authorization_binding),
        "terminal_bundle": dict(attempt_result.terminal_bundle),
    }
    identity_hashes, files = _artifact_closure(values=values)
    identity_hashes = {"protocol": R4_SCOPED_PROTOCOL, **identity_hashes}
    execution_binding = {
        "protocol": R4_SCOPED_PROTOCOL,
        "identity_hashes": identity_hashes,
        "artifact_files": files,
        "qualification_credit": "NONE_INDIVIDUAL_RUN",
    }
    request = values["request_record"]
    requirement = (
        load_requirement_snapshot(
            snapshot_dir=repo_root / "requirements" / str(request["requirement_id"]),
        )
        if acceptance_context is None else r4_context_requirement(
            repo_root=repo_root, manifest=request,
            replay_context=acceptance_context,
        )
    )
    if (
        request.get("artifact_requirement_generation") != EXPLICIT_ARTIFACT_GENERATION
        or request.get("requirement_closure_hash") != requirement["requirement_closure_hash"]
        or request.get("requirement_hashes") != requirement["hashes"]
    ):
        raise R4RunStoreError("Executed R4 request Requirement identity differs")
    validate_execution_authority(repo_root=repo_root, requirement=requirement)
    fixture = None if acceptance_context is None else acceptance_context.authority.get(
        "fixture_company_authority",
    )
    if fixture is None:
        fixture = resolve_r4_fixture_company_authority(
            repo_root=repo_root, requirement=requirement,
            source_id=str(request["source_id"]),
        )
    target_period = resolve_r4_run_target_period(
        request_record=request, fixture_company=fixture,
    )
    authority = attempt_result.authority
    if type(authority) is not dict:
        raise R4RunStoreError("R4 scoped acceptance authority is absent")
    from .evidence import _plain_owned
    raw_blob = validate_record(record=authority["raw_blob"])
    source_reference = validate_record(record=authority["source_reference"])
    derived_asset = validate_record(record=strict_json_loads(
        text=attempt_result.full_derived_asset_bytes.decode("utf-8"),
    ))
    reader_manifest = validate_record(record=_plain_owned(authority["reader_manifest"]))
    task_contract = authority["task_contract"]
    if (
        fixture.get("source_id") != request.get("source_id")
        or request.get("fixture_company_authority_id") != fixture["fixture_company_authority_id"]
        or request.get("company_traits") != fixture["company_traits"]
        or request.get("target_period") != target_period
        or source_reference["company_id"] != fixture["company_id"]
        or request.get("raw_asset_id") != raw_blob["raw_asset_id"]
        or request.get("full_derived_asset_id") != derived_asset["derived_asset_id"]
        or request.get("full_reader_input_manifest_id")
        != reader_manifest["reader_input_manifest_id"]
        or request.get("task_contract_id") != task_contract["task_contract_id"]
    ):
        raise R4RunStoreError("R4 request/source/company/task identity differs")
    from .r4_task_contracts import resolve_r4_task_contract
    rebuilt_task = resolve_r4_task_contract(
        repo_root=repo_root, requirement=requirement,
        task_contract_id=task_contract["task_contract_id"],
    )
    if rebuilt_task != task_contract:
        raise R4RunStoreError("R4 scoped task differs from repository")
    task_binding = table_task_run_binding(runtime=rebuilt_task)
    spec_paths = list(rebuilt_task["metric_spec_paths"])
    spec_hashes = {
        relative: sha256_file(path=resolve_repository_file(
            repo_root=repo_root, repo_relative_path=relative,
        ))
        for relative in spec_paths
    }
    run_id = "run:r4:" + content_hash(value={
        "protocol": R4_SCOPED_PROTOCOL,
        "request_record_hash": identity_hashes["request_record_hash"],
        "invocation_plan_hash": identity_hashes["invocation_plan_hash"],
        "authorization_binding_hash": identity_hashes["authorization_binding_hash"],
    }).split(":", 1)[1]
    create_run(
        run_dir=run_dir, run_id=run_id,
        company_id=fixture["company_id"],
        company_traits=fixture["company_traits"],
        target_period=target_period,
        source_references=[source_reference],
        missing_required_source_roles=[],
        spec_file_hashes=spec_hashes,
        requirement_hashes=requirement["hashes"],
        task_contract_bindings=[task_binding],
        requirement_id=requirement["requirement_id"],
        requirement_closure_hash=requirement["requirement_closure_hash"],
        artifact_requirement_generation=EXPLICIT_ARTIFACT_GENERATION,
        run_record_type=R4_SCOPED_RUN_TYPE,
        r4_execution_binding=execution_binding,
    )
    _write_execution_artifacts(run_dir=run_dir, values=values, files=files)
    attempt = _successor_attempt(
        native=attempt_result.attempt_record, requirement=requirement,
        identity_hashes=identity_hashes,
    )
    write_attempt_payloads(
        run_dir=run_dir, attempt=attempt, payloads=attempt_result.payloads,
    )
    initial = [raw_blob, source_reference, derived_asset, reader_manifest, attempt]
    if attempt["status"] == "SUCCEEDED":
        if attempt_result.candidate_record is None or attempt_result.evidence_record is None:
            raise R4RunStoreError("Successful R4 result lacks Candidate/Evidence")
        initial.extend((
            validate_record(record=attempt_result.candidate_record),
            validate_record(record=attempt_result.evidence_record),
        ))
    elif attempt_result.candidate_record is not None or attempt_result.evidence_record is not None:
        raise R4RunStoreError("Failed R4 result carries accepted Candidate/Evidence")
    manifest, _records, _decisions = load_open_run(run_dir=run_dir)
    append_run_records_atomically(
        run_dir=run_dir, records=initial,
        expected_records_file_hash=manifest["records_file_hash"],
        expected_review_decisions_file_hash=manifest["review_decisions_file_hash"],
    )
    return load_open_run(run_dir=run_dir)[0]


def finalize_r4_scoped_run(
    *, repo_root: Path, run_dir: Path, acceptance_context: object = None,
) -> Dict[str, object]:
    """Apply native Review/Observation/Calculator gates, then freeze one child.

    The optional context must be the exact private C acceptance object.  It
    avoids repeating full source and authority construction within a process
    session; it does not suppress any native record or disk-byte check.
    """
    from .calculator import calculate_observation_metric
    from .observations import reviewed_observation
    from .render import build_review_context, render_review_markdown
    from .review import (
        build_review_unit,
        create_system_review_decision,
        effective_review_decision,
    )
    from .run_store import (
        _mechanically_replay_open_run,
        _read_manifest,
        _r4_context_for_run,
        append_review_decision,
        append_run_record,
        append_run_records_atomically,
        fail_run,
        load_frozen_run,
        load_open_run,
        validate_and_freeze_run,
        write_review_assets,
        write_validation_receipt,
    )
    manifest = _read_manifest(run_dir=run_dir)
    if manifest["record_type"] != R4_SCOPED_RUN_TYPE:
        raise R4RunStoreError("R4 finalization requires an explicit scoped Run")
    acceptance_context = _r4_context_for_run(
        repo_root=repo_root, run_dir=run_dir, manifest=manifest,
        replay_context=acceptance_context,
    )
    if manifest["status"] == "FROZEN":
        return load_frozen_run(
            repo_root=repo_root, run_dir=run_dir,
            r4_replay_context=acceptance_context,
        )[0]
    manifest, records, decisions = load_open_run(run_dir=run_dir)
    validate_r4_record_set(manifest=manifest, records=records)
    attempt = next(record for record in records
                   if record["record_type"] == R4_SCOPED_ATTEMPT_TYPE)
    if attempt["status"] != "SUCCEEDED":
        _mechanically_replay_open_run(
            repo_root=repo_root, run_dir=run_dir,
            require_complete_results=False,
            r4_replay_context=acceptance_context,
        )
        write_validation_receipt(
            run_dir=run_dir, status="FAILED",
            checks=[{
                "check": "R4_SCOPED_TERMINAL_EXECUTION",
                "status": "FAIL",
                "error_class": attempt["error_class"],
            }],
        )
        return fail_run(run_dir=run_dir)

    requirement = r4_context_requirement(
        repo_root=repo_root, manifest=manifest,
        replay_context=acceptance_context,
    )
    plans = load_r4_run_task_plans(
        repo_root=repo_root, manifest=manifest,
        replay_context=acceptance_context,
    )
    plan = plans[attempt["task_contract_id"]]
    candidate = next(record for record in records if record["record_type"] in {
        "OBSERVATION_CANDIDATE", SOURCE_BOUND_CANDIDATE_TYPE,
    })
    evidence = next(record for record in records if record["record_type"] == "EVIDENCE_CHECK")
    derived = next(record for record in records if record["record_type"] == "DERIVED_ASSET")
    sources = list(manifest["source_references"])
    if len(sources) != 1:
        raise R4RunStoreError("R4 finalization source exact set differs")
    context = build_review_context(
        candidate=candidate, evidence_check=evidence,
        derived_asset=derived, source_bindings=sources,
        spec_semantic_hash=plan["task_spec"]["spec_semantic_hash"],
        required_claims=plan["task_spec"]["compiled"]["required_claims"],
    )
    rendered = render_review_markdown(review_context=context["review_context"])
    unit = build_review_unit(
        candidate=candidate, evidence_check=evidence,
        source_bindings=sources, compiled_spec=plan["task_spec"],
        review_context_hash=context["review_context_hash"],
        rendered_review_hash=rendered["rendered_review_hash"],
        renderer_semantic_version=rendered["review_renderer_semantic_version"],
    )
    units = [record for record in records if record["record_type"] == "REVIEW_UNIT"]
    if units:
        if units != [unit]:
            raise R4RunStoreError("Existing R4 ReviewUnit differs from native reconstruction")
    else:
        write_review_assets(
            run_dir=run_dir, review_unit=unit,
            review_context_bytes=context["review_context_bytes"],
            rendered_review_bytes=rendered["bytes"],
        )
        append_run_record(run_dir=run_dir, record=unit)
    if decisions:
        decision = effective_review_decision(review_unit=unit, decisions=decisions)
        if decision["decision"] != "APPROVE":
            raise R4RunStoreError("R4 finalization cannot override a rejected Review")
    else:
        decision = create_system_review_decision(
            review_unit=unit,
            required_claims=plan["task_spec"]["compiled"]["required_claims"],
            decided_at_utc=attempt["finished_at_utc"],
            requirement=requirement,
        )
        append_review_decision(run_dir=run_dir, decision=decision)

    projection = plan["task_spec"]["compiled"]["legacy_projection"]
    if len(projection["roles"]) != 1 or projection["supporting_roles"]:
        raise R4RunStoreError("R4 finalization requires one native direct role")
    role = projection["roles"][0]
    metric_id = projection["role_metric_ids"][role]
    metric = plan["metric_specs"][metric_id]
    observation = reviewed_observation(
        metric_id=metric_id, role=role,
        company_id=manifest["company_id"],
        period_start=manifest["target_period"]["period_start"],
        period_end=manifest["target_period"]["period_end"],
        canonical_unit=metric["compiled"]["canonical_unit"],
        candidate=candidate, evidence_check=evidence,
        review_unit=unit, decision=decision,
        source_reference=sources[0], derived_asset_id=derived["derived_asset_id"],
        quality="EXACT",
    )
    scope = dict(decision["approved_claims"])
    target = {
        "company_id": manifest["company_id"],
        "period_start": manifest["target_period"]["period_start"],
        "period_end": manifest["target_period"]["period_end"],
        "scope": scope,
        "scope_key": content_hash(value=scope),
    }
    result, trace = calculate_observation_metric(
        compiled_spec=metric, target=target,
        company_traits=manifest["company_traits"], observation=observation,
    )
    final_records = [observation, result, trace]
    _manifest, records, _decisions = load_open_run(run_dir=run_dir)
    existing = [record for record in records if record["record_type"] in {
        "VERIFIED_OBSERVATION", "METRIC_RESULT", "EXECUTION_TRACE",
    }]
    if existing:
        if existing != final_records:
            raise R4RunStoreError("R4 finalization batch is partial or differs")
    else:
        append_run_records_atomically(
            run_dir=run_dir, records=final_records,
            expected_records_file_hash=sha256_file(path=run_dir / "records.jsonl"),
            expected_review_decisions_file_hash=sha256_file(path=run_dir / "review_decisions.jsonl"),
        )
    return validate_and_freeze_run(
        run_dir=run_dir, repo_root=repo_root,
        r4_replay_context=acceptance_context,
    )


def replay_r4_scoped_run(
    *, repo_root: Path, run_dir: Path, acceptance_context: object = None,
) -> Dict[str, object]:
    """Replay one terminal R4 Run with explicit absence of qualification credit.

    Independent callers omit ``acceptance_context``.  An aggregate final disk
    replay may instead create a fresh disk session and pass its exact contexts
    across sibling Runs; it must not reuse the execution session.
    """
    from .replay import replay_frozen_results
    from .run_store import (
        _read_manifest, _r4_context_for_run, _validate_record_graph,
        _verify_repository_bindings, load_failed_run,
    )
    manifest = _read_manifest(run_dir=run_dir)
    if manifest["record_type"] != R4_SCOPED_RUN_TYPE:
        raise R4RunStoreError("R4 replay requires an explicit scoped Run")
    if manifest["status"] == "FROZEN":
        replayed = replay_frozen_results(
            run_dir=run_dir, repo_root=repo_root,
            r4_replay_context=acceptance_context,
        )
    elif manifest["status"] == "FAILED":
        manifest, records, decisions = load_failed_run(run_dir=run_dir)
        if decisions:
            raise R4RunStoreError("Failed R4 Run cannot carry review decisions")
        acceptance_context = _r4_context_for_run(
            repo_root=repo_root, run_dir=run_dir, manifest=manifest,
            replay_context=acceptance_context,
        )
        specs, raw, ciks, requirement = _verify_repository_bindings(
            repo_root=repo_root, run_dir=run_dir, manifest=manifest,
            records=records, r4_replay_context=acceptance_context,
        )
        _validate_record_graph(
            repo_root=repo_root, run_dir=run_dir, manifest=manifest,
            records=records, effective_decisions={}, compiled_specs=specs,
            raw_bytes_by_id=raw, company_ciks=ciks, requirement=requirement,
            r4_replay_context=acceptance_context,
        )
        replayed = {
            "results": [], "traces": [],
            "replay_content_hash": content_hash(value={
                "content_manifest_hash": manifest["content_manifest_hash"],
                "audit_manifest_hash": manifest["audit_manifest_hash"],
                "status": "FAILED",
            }),
        }
    else:
        raise R4RunStoreError("R4 terminal replay rejects an OPEN Run")
    authorization = _run_artifact(
        run_dir=run_dir, manifest=manifest, artifact_kind="authorization_binding",
    )
    return {
        **replayed,
        "run_id": manifest["run_id"],
        "run_status": manifest["status"],
        "execution_mode": authorization["execution_mode"],
        "qualification_credit": "NONE_INDIVIDUAL_RUN",
        "publication_credit": "NONE",
        "response_reuse_authorized": False,
    }


def replay_r4_persisted_attempt(
    *, repo_root: Path, run_dir: Path, manifest: Mapping,
    attempt: Mapping, stored_payloads: Mapping, task_plan: Mapping,
    reader_manifest: Mapping, derived_asset: Mapping,
    replay_context: object = None,
) -> Dict[str, object]:
    """Rebuild one persisted attempt through C's native scoped disk replay."""
    from .live_scoped_reader import replay_scoped_attempt
    request = _run_artifact(
        run_dir=run_dir, manifest=manifest, artifact_kind="request_record",
    )
    invocation = _run_artifact(
        run_dir=run_dir, manifest=manifest, artifact_kind="invocation_plan",
    )
    execution = _run_artifact(
        run_dir=run_dir, manifest=manifest, artifact_kind="execution_receipt",
    )
    authorization = _run_artifact(
        run_dir=run_dir, manifest=manifest, artifact_kind="authorization_binding",
    )
    terminal_bundle = _run_artifact(
        run_dir=run_dir, manifest=manifest, artifact_kind="terminal_bundle",
    )
    acceptance = None
    if manifest["r4_execution_binding"]["artifact_files"]["acceptance_receipt"] is not None:
        acceptance = _run_artifact(
            run_dir=run_dir, manifest=manifest,
            artifact_kind="acceptance_receipt",
        )
    replayed = replay_scoped_attempt(
        repo_root=repo_root,
        request_record=request,
        payloads=stored_payloads,
        invocation_plan=invocation,
        execution_receipt=execution,
        acceptance_receipt=acceptance,
        authorization_binding=authorization,
        terminal_bundle=terminal_bundle,
        acceptance_context=replay_context,
    )
    from .evidence import _plain_owned
    if (
        _plain_owned(replayed["authority"]["reader_manifest"]) != reader_manifest
        or replayed["full_derived_asset_bytes"] != canonical_json_bytes(value=derived_asset)
        or replayed["authority"]["task_contract"]
        != task_plan["runtime_task_contract"]
        or replayed["compiled_spec"] != task_plan["metric_specs"][request["metric_id"]]
    ):
        raise R4RunStoreError("R4 persisted replay authority differs")
    _verify_native_attempt(
        attempt=attempt, stored_payloads=stored_payloads,
        execution=execution, authorization=authorization, replayed=replayed,
    )
    return {
        "task_contract": task_plan["runtime_task_contract"],
        "task_spec": task_plan["task_spec"],
        "reader_manifest": reader_manifest,
        "payload": {"body": strict_json_loads(
            text=stored_payloads["reader_payload"].decode("utf-8"),
        )},
        "replayed_candidate": replayed.get("candidate_record"),
        "replayed_evidence": replayed.get("evidence_record"),
    }


def _verify_native_attempt(
    *, attempt: Mapping, stored_payloads: Mapping, execution: Mapping,
    authorization: Mapping, replayed: Mapping,
) -> None:
    """Rebuild the native AI attempt from verified terminal/payload authority."""
    from .ai_adapter import (
        TransportObservation,
        _no_egress_policy_observation,
        approved_scoped_transport_policy,
        transport_observation_mismatch,
    )
    from .canonical import parse_utc_timestamp
    observation = TransportObservation.from_mapping(value=attempt["transport_observation"])
    policy = approved_scoped_transport_policy(requirement=replayed["authority"]["requirement"])
    if authorization["execution_mode"] == "RECORDED_TEST":
        expected = _no_egress_policy_observation(
            policy=policy, request_bytes=stored_payloads["request_body"],
        )
        if observation != expected:
            raise R4RunStoreError("Recorded scoped attempt claims a different transport boundary")
    elif attempt["status"] == "SUCCEEDED":
        mismatch = transport_observation_mismatch(
            policy=policy, observation=observation,
            request_bytes=stored_payloads["request_body"],
        )
        if mismatch is not None:
            raise R4RunStoreError("R4 live attempt transport policy differs: " + mismatch)
    else:
        expected = _no_egress_policy_observation(
            policy=policy, request_bytes=stored_payloads["request_body"],
        ).as_mapping()
        actual = observation.as_mapping()
        mutable_observations = {"egress_attempted", "endpoint_host", "model_returned"}
        if any(actual[key] != value for key, value in expected.items()
               if key not in mutable_observations):
            raise R4RunStoreError("Failed R4 attempt transport policy differs")
        if actual["endpoint_host"] != (policy.endpoint_host if actual["egress_attempted"] else "none"):
            raise R4RunStoreError("Failed R4 attempt endpoint/egress differs")
    if (
        parse_utc_timestamp(value=attempt["started_at_utc"])
        > parse_utc_timestamp(value=execution["finished_at_utc"])
        or parse_utc_timestamp(value=attempt["finished_at_utc"])
        < parse_utc_timestamp(value=execution["finished_at_utc"])
    ):
        raise R4RunStoreError("R4 attempt audit time does not enclose execution")
    expected_native = replayed["native_attempt_record"]
    projected = {key: value for key, value in attempt.items() if key not in {
        "artifact_requirement_generation", "requirement_id",
        "requirement_closure_hash", "requirement_hashes", "r4_binding",
    }}
    projected["record_type"] = "AI_EXTRACTION_ATTEMPT"
    if projected != expected_native:
        raise R4RunStoreError("R4 attempt differs from native terminal reconstruction")
