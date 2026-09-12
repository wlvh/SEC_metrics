"""Ordinary saved-source records for revenue, EBITDA margin and six events.

Reuse installed metric definitions, native source adapters and Calculator.
This module never invokes legacy release preparation, creates a Run, freezes
authority, fetches sources, or publishes. Other migrated routes remain outside
this bounded prototype rather than inheriting old answers or periods.
"""
from pathlib import Path

from sec_urls import accession_document_url, companyfacts_url, hdr_sgml_url, submissions_url, submissions_file_url
from .annual_update import AnnualUpdateError
from .annual_amendment_scope import prepare_saved_amendment_input
from .batch_workflow import BatchWorkflowError, _structured_concepts
from .calculator import calculate_metric, withheld_metric_result, calculate_observation_metric
from .canonical import canonical_json_bytes, content_hash, sha256_file, strict_json_loads
from .deterministic_router import (
    adapt_companyfacts, adapt_8k_item_index, project_event_result,
    load_event_route_catalog, _compiled_event_spec, source_set_manifest, acquisition_event_source_set_receipt,
)
from .normal_annual_input_v2 import prepare_saved_annual_input, exact_json_value, POLICY_PATH as FISCAL_LABEL_POLICY_PATH
from .normal_governance_input import _Sources, _filings, _history_index, history_body_alignment, NormalGovernanceInputError
from .normal_source_authority import ROOT
from .ordinary_source_authority import verify_ordinary_source_proofs
from .observations import scope_key, structured_observation
from .sources import companyfacts_structured_facts, resolve_repository_file, SourceError
from .specs import compile_spec_file
from .traits import repository_company_traits
from .zero_ai_r2 import _exact_filing_source_set, _event_collection_manifest, _acquired_event_filings


B01_SPEC_PATH = "catalog/metrics/B01_revenue.md"
B03_SPEC_PATH = "catalog/metrics/B03_ebitda_margin.md"
EVENT_METRICS = ("C01", "E01", "E02", "E03", "E04", "E05")
SUPPORTED_METRICS = ("B01", "B03", *EVENT_METRICS)
_AUTHORITY_FILES = (B01_SPEC_PATH, B03_SPEC_PATH, FISCAL_LABEL_POLICY_PATH, "catalog/event_routes.json", "catalog/zero_ai_public_projection.json",
                    "config/company_registry.csv", "catalog/company_traits.yaml", "config/metric_applicability.yaml")


class NormalZeroAiError(ValueError):
    def __init__(self, reason, category="IMPLEMENTATION_GAP"):
        super().__init__(reason)
        self.category = category


def _need(condition, reason, category="IMPLEMENTATION_GAP"):
    if not condition:
        raise NormalZeroAiError(reason, category)


def _authority(repo_root):
    files = {}
    for relative in _AUTHORITY_FILES:
        expected = sha256_file(path=ROOT / relative)
        _need(sha256_file(path=resolve_repository_file(repo_root=repo_root, repo_relative_path=relative)) == expected,
              "NORMAL_ZERO_AI_INSTALLED_AUTHORITY_REQUIRED:" + relative, "AUTHORITY_CONFLICT")
        files[relative] = expected
    return files


def _exact_set(prepared, inventory, source, role):
    return _exact_filing_source_set(company_id=prepared["company_id"], source_role=role,
        reference=source["source_reference"], inventory_reference=inventory["source_reference"],
        inventory_bytes=inventory["raw_bytes"])


def _event_sources(*, repo_root, reader, prepared, inventory):
    """Discover only the actual annual event window, including history shards."""
    period = prepared["table_input"]["target_period"]
    payload = strict_json_loads(text=inventory["raw_bytes"].decode("utf-8"))
    shards = _history_index(payload, prepared["entity"])
    inventories = [inventory]
    for shard in shards:
        if shard["filingFrom"] <= period["period_end"] and shard["filingTo"] >= period["period_start"]:
            item = reader.read(submissions_file_url(file_name=shard["name"]),
                role="sec_submissions_history", media_type="application/json")
            data = strict_json_loads(text=item["raw_bytes"].decode("utf-8"))
            _need("cik" not in data or str(data["cik"]).isdigit() and int(data["cik"]) == int(prepared["entity"]),
                  "NORMAL_EVENT_HISTORY_ENTITY_CONFLICT", "SOURCE_INTEGRITY_ERROR")
            rows = _filings(data, inventory_name=shard["name"])
            _need(history_body_alignment(shard=shard, rows=rows) is None,
                  "NORMAL_EVENT_HISTORY_SNAPSHOT_CONFLICT", "SOURCE_COVERAGE_CONFLICT")
            inventories.append(item)
    sets, claims, seen, filing_rows = [], [], set(), []
    for item in inventories:
        reference = item["source_reference"]
        payload = strict_json_loads(text=item["raw_bytes"].decode("utf-8"))
        events = [f for f in _filings(payload, inventory_name=reference["document_name"])
                  if f["form"] in {"8-K", "8-K/A"} and period["period_start"] <= f["filingDate"] <= period["period_end"]]
        documents, references = [], []
        for filing in sorted(events, key=lambda f: (f["filingDate"], f["accessionNumber"])):
            accession = filing["accessionNumber"]
            _need(accession not in seen, "NORMAL_EVENT_INVENTORY_OVERLAP", "SOURCE_COVERAGE_CONFLICT")
            seen.add(accession)
            primary = reader.read(accession_document_url(cik=int(prepared["entity"]), accession=accession,
                document_name=filing["primaryDocument"]), accession=accession, role="fy_8k_primary", media_type="text/html")
            header = reader.read(hdr_sgml_url(cik=int(prepared["entity"]), accession=accession),
                accession=accession, role="fy_8k_header", media_type="text/plain")
            documents.append({"hdr_bytes": header["raw_bytes"], "hdr_source_reference": header["source_reference"],
                "primary_document_bytes": primary["raw_bytes"], "primary_source_reference": primary["source_reference"]})
            references.extend([header["source_reference"], primary["source_reference"]])
            filing_rows.append(filing)
        manifest = source_set_manifest(company_id=prepared["company_id"], source_role="fy_8k_item_inventory",
            form_types=["8-K", "8-K/A"], fiscal_or_date_window={k:period[k] for k in ("period_start", "period_end")},
            discovery_policy="PINNED_SUBMISSIONS", inventory_source_reference=reference, inventory_bytes=item["raw_bytes"],
            ordered_source_references=references, cutoff_timestamp_or_pinned_submissions_attempt=reference["request_attempt_id"])
        if documents:
            header_identity = acquisition_event_source_set_receipt(
                filing_documents=sorted(documents, key=lambda d:d["hdr_source_reference"]["accession"]),
                company_id=prepared["company_id"], period_start=period["period_start"], period_end=period["period_end"])
            _need({f["accession"]:f["filing_date"] for f in header_identity["filing_dates"]}
                  == {f["accessionNumber"]:f["filingDate"] for f in events},
                  "NORMAL_EVENT_HEADER_DATE_CONFLICT", "SOURCE_INTEGRITY_ERROR")
        claims.extend(adapt_8k_item_index(filing_documents=documents, source_set_manifest=manifest,
            inventory_source_reference=reference, inventory_bytes=item["raw_bytes"]))
        sets.append({"manifest":manifest, "references":references})
    # The historical zero-AI route also includes acquired filings omitted from
    # a saved submissions snapshot. An unimplemented supplement is an explicit
    # development gap, never permission to report a smaller successful count.
    acquired = _acquired_event_filings(repo_root=repo_root, company_id=prepared["company_id"],
        allowed_ciks=[prepared["entity"]], period_start=period["period_start"], period_end=period["period_end"])
    installed_acquired = _acquired_event_filings(repo_root=ROOT, company_id=prepared["company_id"],
        allowed_ciks=[prepared["entity"]], period_start=period["period_start"], period_end=period["period_end"])
    _need(acquired == installed_acquired, "NORMAL_EVENT_ACQUISITION_CENSUS_DIFFERS_FROM_INSTALLED_INPUT", "SOURCE_COVERAGE_CONFLICT")
    missing = [f for f in acquired if f["accession"] not in seen]
    _need(not missing, "NORMAL_EVENT_ACQUIRED_SUPPLEMENT_NOT_IMPLEMENTED:" + ",".join(f["accession"] for f in missing))
    collection = _event_collection_manifest(company_id=prepared["company_id"], target=period,
        inventory_reference=inventory["source_reference"], event_sets=sets, ordered_accessions=sorted(seen))
    return claims, [s["manifest"] for s in sets] + [collection], filing_rows


def resolve_ordinary_zero_ai_metric(*, repo_root: Path, company_id: str, metric_id: str):
    """Derive native records from current saved annual input, without a Run.

    No caller fact, period, filing, answer, compiled Spec or source receipt is
    accepted. Unsupported input returns a source-bound WITHHELD state where an
    annual coordinate exists; source authenticity/authority errors propagate.
    """
    _need(metric_id in SUPPORTED_METRICS, "NORMAL_ZERO_AI_METRIC_NOT_IN_PROTOTYPE")
    authority = _authority(repo_root)
    prepared = prepare_saved_annual_input(repo_root=repo_root, company_id=company_id)
    admission = verify_ordinary_source_proofs(data_root=repo_root, proofs=prepared["source_proofs"])
    period = prepared["table_input"]["target_period"]
    reader = _Sources(repo_root, company_id, prepared["entity"])
    inventory = reader.read(submissions_url(cik=int(prepared["entity"])), role="sec_submissions_inventory", media_type="application/json")
    reader.primary(prepared["filing"])
    facts_source = reader.read(companyfacts_url(cik=int(prepared["entity"])), accession=prepared["filing"]["accessionNumber"],
        role="companyfacts", media_type="application/json")
    traits = repository_company_traits(repo_root=repo_root, company_id=company_id)
    claims, source_sets, observations, filing_rows, selection = [], [], [], [prepared["filing"]], {}
    dependency_specs, dependency_records = {}, []
    amendment_input = None
    if metric_id in {"B01", "B03"}:
        spec_path = B01_SPEC_PATH if metric_id == "B01" else B03_SPEC_PATH
        if metric_id == "B03":
            dependency_specs["B01"] = compile_spec_file(path=repo_root / B01_SPEC_PATH, dependency_specs={})
        spec_origin = {"spec_path":spec_path}
        spec = compile_spec_file(path=repo_root / spec_path, dependency_specs=dependency_specs)
        scope = {"entity_scope":"registrant", "period_basis":"source_annual_duration"}
    else:
        catalog = load_event_route_catalog(repo_root=repo_root)
        spec_path, spec_origin = None, {"catalog_path":"catalog/event_routes.json", "metric_id":metric_id}
        spec = _compiled_event_spec(metric_id=metric_id, route=catalog["routes"][metric_id])
        scope = {"coverage":"fiscal_year_source_set", "fiscal_year":period["fiscal_year"],
                 "shared_claim_group_id":catalog["routes"][metric_id]["shared_claim_group_id"]}
    target = {"company_id":company_id, "period_start":period["period_start"], "period_end":period["period_end"],
        "scope":scope, "scope_key":scope_key(scope=scope)}
    try:
        _need(prepared["subject_policy"]["mode"] == "CONTINUOUS_PRIMARY", "NORMAL_ZERO_AI_SUCCESSOR_SCOPE_NOT_IMPLEMENTED")
        if prepared["amendments"]:
            amendment_input = prepare_saved_amendment_input(repo_root=repo_root,company_id=company_id,
                input_class="ORIGINAL_STATEMENT_VALUES" if metric_id in {"B01","B03"} else "FISCAL_EVENT_WINDOW")
            _need(amendment_input["prepared_input"] == prepared.get("original_input",prepared),
                  "NORMAL_AMENDMENT_ORIGINAL_INPUT_DIFFERS", "SOURCE_INTEGRITY_ERROR")
            _need(amendment_input["decision"] == "INPUT_PROPERTY_PROVEN", "NORMAL_AMENDMENT_INPUT_SCOPE_UNRESOLVED")
            filing_rows.extend(s["amendment"]["filing"] for s in amendment_input["scopes"])
        if metric_id in {"B01", "B03"}:
            manifest = _exact_set(prepared, inventory, facts_source, "companyfacts")
            source_sets = [manifest]
            approved = sorted(set(_structured_concepts(compiled_spec=spec)) | {
                concept for dependency in dependency_specs.values()
                for concept in _structured_concepts(compiled_spec=dependency)})
            facts = companyfacts_structured_facts(raw_bytes=facts_source["raw_bytes"], source_reference=facts_source["source_reference"],
                approved_concepts=approved, allowed_ciks=[prepared["entity"]], include_instant=False)
            claims = adapt_companyfacts(raw_bytes=facts_source["raw_bytes"], source_reference=facts_source["source_reference"],
                source_set_manifest=manifest, approved_concepts=approved, allowed_ciks=[prepared["entity"]], include_instant=False)
            execution_target = {**target,"entity":prepared["entity"],"accession":prepared["filing"]["accessionNumber"]}
            reusable = []
            for dependency in dependency_specs.values():
                dep_result, dep_trace, dep_observations = calculate_metric(compiled_spec=dependency,
                    target=execution_target, company_traits=traits, structured_facts=facts, verified_observations=[])
                dependency_records.extend([*dep_observations, dep_trace, dep_result])
                reusable.extend(dep_observations)
            result, trace, observations = calculate_metric(compiled_spec=spec,
                target=execution_target, company_traits=traits, structured_facts=facts, verified_observations=reusable)
            selection = {"source_candidate_count":len(facts), "selected_fact_ids":[o["source_binding"]["fact_id"] for o in observations],
                "source_reported_periods":sorted({(f["period_start"],f["period_end"]) for f in facts}), "reason_code":result["reason_code"]}
        else:
            claims, source_sets, events = _event_sources(repo_root=repo_root, reader=reader, prepared=prepared, inventory=inventory)
            filing_rows.extend(events)
            graph = project_event_result(metric_id=metric_id, claims=claims, source_set_manifest=source_sets[-1],
                inventory_source_reference=inventory["source_reference"], target_period=period, catalog=catalog)
            original = graph["observation"]
            # The inventory reference and the event collection have distinct
            # roles. Preserve both rather than binding the collection role to
            # a different SourceReference in a complete native Run.
            binding = {**original["source_binding"],"source_role":inventory["source_reference"]["source_role"],
                       "source_set_role":source_sets[-1]["source_role"]}
            observation = structured_observation(metric_id=metric_id,semantic_role=original["semantic_role"],company_id=company_id,
                period_start=period["period_start"],period_end=period["period_end"],scope=original["scope"],
                value=original["value"],unit=original["unit"],quality=original["quality"],source_binding=binding)
            result,trace = calculate_observation_metric(compiled_spec=spec,target=target,company_traits=traits,observation=observation)
            observations = [observation]
            selection = {"reason_code":result["reason_code"], "matched_verified_claim_ids":graph["matched_verified_claim_ids"],
                         "source_event_accessions":sorted({f["accessionNumber"] for f in events})}
    except (NormalZeroAiError, NormalGovernanceInputError, AnnualUpdateError, BatchWorkflowError, SourceError) as error:
        reason = str(error)
        category = getattr(error, "category", "SOURCE_ACCESS_FAILED" if reason.startswith("LATEST_SOURCE_REQUEST_FAILED") else "SOURCE_INTEGRITY_ERROR")
        result, trace = withheld_metric_result(compiled_spec=spec, target=target, reason_code="NORMAL_ZERO_AI_SOURCE_ROUTE_UNRESOLVED")
        observations = []
        selection = {**selection, "reason_code":result["reason_code"], "reason":reason, "category":category}
    proofs = prepared["source_proofs"] + [entry["proof"] for entry in reader.proofs.values()]
    if amendment_input is not None: proofs.extend(amendment_input["source_proofs"])
    proofs = list({content_hash(value=p):p for p in proofs}.values())
    admission = verify_ordinary_source_proofs(data_root=repo_root, proofs=proofs)
    source_records = list(reader.records.values())
    if amendment_input is not None:
        source_records = list({content_hash(value=r):r for r in [*source_records,*amendment_input["source_records"]]}.values())
    input_binding = {"prepared_input":prepared,"target":target,"target_period":period,"amendment_input":amendment_input,
        "spec_origin":spec_origin,"spec_closure_hash":spec["spec_closure_hash"],"authority_file_hashes":authority,
        "dependency_spec_closure_hashes":{key:value["spec_closure_hash"] for key,value in dependency_specs.items()},
        "source_proofs":proofs,"source_admission":admission,"source_set_manifests":source_sets,
        "failed_source_attempts":list(reader.failed_attempts.values()),"selection":selection,
        "resolver_sha256":sha256_file(path=Path(__file__))}
    body = {"record_type":"NORMAL_ZERO_AI_SOURCE_RESULT_PROTOTYPE", "company_id":company_id,"metric_id":metric_id,
        "spec_path":spec_path,"spec_origin":spec_origin,"compiled_spec":spec,"authority_file_hashes":authority,
        "dependency_specs":dependency_specs,"dependency_records":dependency_records,
        "input_binding":input_binding,"prepared_input":prepared,"target_period":period,"target":target,"source_records":source_records,
        "source_references":[r for r in source_records if r["record_type"]=="SOURCE_REFERENCE"],
        "source_proofs":proofs,"source_admission":admission,"source_set_manifests":source_sets,"filings":filing_rows,
        "claims":claims,"selection":selection,"observations":observations,"result":result,"trace":trace,
        "records":list({content_hash(value=r):r for r in [*source_records,*dependency_records,*observations,trace,result]}.values()),
        "failed_source_attempts":list(reader.failed_attempts.values()),
        "native_run_status":"NOT_CREATED","current_latest_verified":False,"calls":{"provider":0,"paid":0,"sec":0},
        "production_authorized":False}
    body = exact_json_value(body)
    return {**body,"input_binding_id":content_hash(value=body["input_binding"]),"component_id":content_hash(value=body)}


def verify_ordinary_zero_ai_metric(*, candidate, repo_root: Path, company_id: str, metric_id: str):
    rebuilt = resolve_ordinary_zero_ai_metric(repo_root=repo_root, company_id=company_id, metric_id=metric_id)
    _need(candidate == rebuilt, "NORMAL_ZERO_AI_SOURCE_REPLAY_CHANGED", "SOURCE_REPLAY_CONFLICT")
    return rebuilt
