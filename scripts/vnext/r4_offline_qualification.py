"""Versioned R4 offline cases: scoped native Evidence or structured-first facts.

No provider constructor, SEC client, qualification cycle, freeze, Stage-A,
publication or response reuse is present. Inputs are source-specific audits,
not a runtime table/window selector.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Mapping

from .canonical import atomic_write_bytes, canonical_json_bytes, content_hash
from .canonical import sha256_bytes, sha256_file, strict_json_file
from .calculator import metric_is_applicable
from .reader_input import build_reader_input_manifest, build_reader_payload
from .reader import validate_reader_output, validate_source_bound_reader_output
from .evidence import check_evidence
from .r4_fixture_authority import FIXTURE_FIELDS, load_r4_fixture_authority
from .r4_source_audit import source_authority, cell_locator
from .r4_structured_sources import build_pinned_fixture_source_set
from .r4_task_contracts import resolve_r4_task_contract
from .source_scope import build_source_scope_manifest
from .scoped_reader import prepare_scoped_reader_request, validate_scoped_reader_response
from .composite_scope import build_source_bound_proof
from .table_grid import build_table_grid, resolve_cell
from .sources import resolve_repository_file
from .traits import repository_company_traits
from .specs import compile_spec_file


from .r4_label_policy import corpus_root, corpus_index

INDEX_PATH = "docs/r4_offline/qualified_cases/index.json"
INDEX_FIELDS = {"record_type", "schema_version", "status", "requirement_id",
    "requirement_closure_hash", "matrix_id", "metric_ids", "cases", "provider_paid_sec_calls",
    "qualification_credit", "live_authorization", "index_id"}
CASE_FIELDS = FIXTURE_FIELDS | {"directory", "files", "summary", "structured_route"}


class R4OfflineQualificationError(ValueError):
    """Fail a source/task audit rather than silently repair or call a provider."""


def load_case_definitions(*, repo_root: Path) -> list:
    return load_r4_fixture_authority(repo_root=repo_root)["fixtures"]


def prepare_source_bundle(*, repo_root: Path, source_id: str,
                          full_derived_asset: Mapping = None) -> dict:
    matrix = load_r4_fixture_authority(repo_root=repo_root)
    if source_id not in matrix["sources"]:
        raise R4OfflineQualificationError("Source is absent from R4 input authority")
    declaration = matrix["sources"][source_id]
    source = source_authority(repo_root=repo_root, declaration=declaration)
    asset = full_derived_asset if full_derived_asset is not None else build_table_grid(
        html_bytes=source["source_bytes"], parent_raw_asset_ids=[source["raw_blob"]["raw_asset_id"]],
        storage_uri="offline://r4/full-grid")
    if (asset["parent_raw_asset_ids"] != [source["raw_blob"]["raw_asset_id"]]
            or asset["derived_asset_id"] != declaration["full_derived_asset_id"]
            or len(asset["tables"]) != declaration["table_count"]):
        raise R4OfflineQualificationError("Full source/asset identity differs")
    for expected in declaration["target_table_metadata"].values():
        table = asset["tables"][expected["order"]]
        if any(table.get(key) != value for key, value in expected.items()):
            raise R4OfflineQualificationError("Audited target table geometry/hash differs")
    manifest = build_reader_input_manifest(derived_asset=asset,
        source_reference_ids=[source["source_reference"]["source_reference_id"]])
    return {**source, "source_id": source_id, "declaration": declaration,
            "full_derived_asset": asset, "reader_manifest": manifest, "structured_context": None}


def prepare_source_bundle_from_context(*, repo_root: Path, source_id: str,
                                      evidence_context, task_contract_id: str) -> dict:
    """Adopt only factory-owned, fully verified inputs without another decode."""
    from .evidence import OfflineEvidenceContext
    if type(evidence_context) is not OfflineEvidenceContext:
        raise R4OfflineQualificationError("Source bundle requires an exact verified offline context")
    owned = evidence_context._scope_authority(task_contract_id=task_contract_id)
    if Path(owned["repo_root"]).resolve() != repo_root.resolve():
        raise R4OfflineQualificationError("Source context belongs to another repository")
    authority = load_r4_fixture_authority(repo_root=repo_root, requirement=owned["requirement"])
    if source_id not in authority["sources"]:
        raise R4OfflineQualificationError("Source context ID is absent from the fixture matrix")
    declaration = authority["sources"][source_id]
    evidence_context._check_files()
    raw, reference, asset = owned["raw_blob"], owned["source_reference"], owned["full_derived_asset"]
    if (raw["storage_uri"] != declaration["source_repo_relative_path"]
            or raw["raw_asset_id"] != "sha256:" + declaration["source_sha256"]
            or raw["byte_length"] != declaration["source_size"]
            or any(reference[key] != declaration[key] for key in ("company_id", "accession", "document_name", "source_url"))
            or asset["derived_asset_id"] != declaration["full_derived_asset_id"]
            or list(asset["parent_raw_asset_ids"]) != [raw["raw_asset_id"]]
            or len(asset["tables"]) != declaration["table_count"]):
        raise R4OfflineQualificationError("Verified source context differs from matrix identity")
    for expected in declaration["target_table_metadata"].values():
        if any(asset["tables"][expected["order"]].get(key) != value for key, value in expected.items()):
            raise R4OfflineQualificationError("Context target-table geometry differs from matrix")
    return {"source_id": source_id, "declaration": declaration, "source_bytes": owned["source_bytes"],
        "raw_blob": raw, "source_reference": reference, "full_derived_asset": asset,
        "reader_manifest": owned["reader_manifest"], "structured_context": None, "repo_root": str(repo_root)}


def _structured_context(*, repo_root: Path, bundle: Mapping) -> dict:
    from .deterministic_router import parse_accession_xbrl_source, source_set_manifest
    from .sources import raw_blob_record, source_reference_record
    from .batch_workflow import request_attempt_binding
    existing = bundle.get("structured_context")
    if existing is not None:
        if (existing.get("owner_source_id") != bundle["source_id"]
                or existing.get("primary_source_sha256") != bundle["declaration"]["source_sha256"]
                or existing["source_reference"]["company_id"] != bundle["declaration"]["company_id"]
                or existing["source_reference"]["accession"] != bundle["declaration"]["accession"]):
            raise R4OfflineQualificationError("Structured parsed context belongs to another source")
        for binding in existing["file_bindings"]:
            path = resolve_repository_file(repo_root=repo_root, repo_relative_path=binding["path"])
            if path.stat().st_size != binding["size"] or sha256_file(path=path) != binding["sha256"]:
                raise R4OfflineQualificationError("Structured immutable file binding changed")
        return existing
    source = bundle["declaration"]
    acquisition = strict_json_file(path=repo_root / "docs/r4_offline/fixture_acquisition_receipt.json")
    if source["source_id"] in {row["source_id"] for row in acquisition["sources"]}:
        raw_bytes = bundle["source_bytes"]
        parsed = parse_accession_xbrl_source(raw_bytes=raw_bytes)
        manifest = build_pinned_fixture_source_set(repo_root=repo_root,
            source_id=source["source_id"], parsed_source=parsed)
        reference = bundle["source_reference"]
        source_paths = [source["source_repo_relative_path"],
                        "config/r4_fixture_acquisitions_v1.json", "docs/r4_offline/fixture_acquisition_receipt.json"]
    else:
        pinned = source["structured_source_authority"]
        if pinned is None:
            raise R4OfflineQualificationError("Source has no pinned native structured authority")
        xml_input, inventory = pinned["accession_xbrl"], pinned["submissions"]
        xml_name = Path(xml_input["path"]).name
        xml_declaration = {**source, "document_name": xml_name,
            "source_url": source["source_url"].rsplit("/", 1)[0] + "/" + xml_name,
            "source_sha256": xml_input["sha256"], "source_size": xml_input["size"],
            "source_repo_relative_path": xml_input["path"], "media_type": "application/xml"}
        xml = source_authority(repo_root=repo_root, declaration=xml_declaration)
        raw_bytes, reference = xml["source_bytes"], xml["source_reference"]
        if any(reference[key] != xml_input[key] for key in ("source_reference_id", "request_attempt_id")):
            raise R4OfflineQualificationError("Pinned accession XML source/attempt identity differs")
        parsed = parse_accession_xbrl_source(raw_bytes=raw_bytes)
        inv_path, inv_url = inventory["path"], inventory["source_url"]
        name = Path(inv_path).name
        raw = raw_blob_record(repo_root=repo_root, repo_relative_path=inv_path, media_type="application/json")
        if raw["raw_asset_id"] != "sha256:" + inventory["sha256"] or raw["byte_length"] != inventory["size"]:
            raise R4OfflineQualificationError("Pinned submissions source bytes differ")
        binding = request_attempt_binding(repo_root=repo_root, source_url=inv_url,
            content_sha256=inventory["sha256"], accession=inventory["accession"], document_name=name)
        if binding["request_attempt_id"] != inventory["request_attempt_id"]:
            raise R4OfflineQualificationError("Pinned submissions attempt differs")
        inv_ref = source_reference_record(raw_blob=raw, company_id=source["company_id"],
            source_url=inv_url, accession=inventory["accession"], document_name=name,
            source_role="sec_submissions_inventory", request_attempt_id=binding["request_attempt_id"])
        manifest = source_set_manifest(company_id=source["company_id"], source_role="target_primary",
            form_types=["10-K"], fiscal_or_date_window=pinned["filing_date_window"],
            discovery_policy="PINNED_SUBMISSIONS_EXACT_FILING_V1", inventory_source_reference=inv_ref,
            inventory_bytes=(repo_root / inv_path).read_bytes(), ordered_source_references=[reference],
            cutoff_timestamp_or_pinned_submissions_attempt=inv_ref["request_attempt_id"])
        if manifest["source_set_manifest_id"] != pinned["source_set_manifest_id"]:
            raise R4OfflineQualificationError("Pinned native SourceSet identity differs")
        source_paths = [source["source_repo_relative_path"], xml_declaration["source_repo_relative_path"], inv_path]
    value = {"parsed": parsed, "raw_bytes": raw_bytes, "source_reference": reference,
             "source_set_manifest": manifest, "owner_source_id": bundle["source_id"],
             "primary_source_sha256": source["source_sha256"],
             "file_bindings": [{"path": relative, "sha256": sha256_file(path=repo_root / relative),
                                "size": (repo_root / relative).stat().st_size} for relative in source_paths]}
    bundle["structured_context"] = value
    return value


def _structured_fiscal_period(*, context: Mapping, recipe: Mapping,
                             source_bundle: Mapping) -> dict:
    """Use the filing's native DEI context, never a synthesized calendar year."""
    from .deterministic_router import ParsedAccessionXbrlSource
    parsed = context["parsed"]
    if (type(parsed) is not ParsedAccessionXbrlSource
            or parsed.source_sha256 != sha256_bytes(content=context["raw_bytes"])
            or parsed.source_size != len(context["raw_bytes"])
            or context["source_reference"]["raw_asset_id"] != "sha256:" + parsed.source_sha256):
        raise R4OfflineQualificationError("Structured fiscal metadata is not bound to the native source")
    names = {"entity_central_index_key": "dei:entitycentralindexkey",
        "document_type": "dei:documenttype", "fiscal_year_focus": "dei:documentfiscalyearfocus",
        "fiscal_period_focus": "dei:documentfiscalperiodfocus",
        "document_period_end": "dei:documentperiodenddate"}
    dei, context_ids = {}, set()
    for field, name in names.items():
        facts = [fact for fact in parsed.facts if fact["qualified_name"].casefold() == name]
        values = {fact["text"] for fact in facts}
        if len(values) != 1:
            raise R4OfflineQualificationError("Native fiscal DEI is absent or ambiguous: " + field)
        dei[field] = values.pop()
        context_ids.update(fact["context_ref"] for fact in facts)
    if len(context_ids) != 1 or not context_ids.issubset(parsed.contexts):
        raise R4OfflineQualificationError("Fiscal DEI does not share one native context")
    fiscal = parsed.contexts[next(iter(context_ids))]
    if (not dei["entity_central_index_key"].isdecimal()
            or not dei["fiscal_year_focus"].isdecimal()
            or not fiscal["entity_identifier"].isdecimal()
            or int(dei["entity_central_index_key"]) != int(source_bundle["declaration"]["cik"])
            or int(fiscal["entity_identifier"]) != int(source_bundle["declaration"]["cik"])
            or dei["document_type"] != "10-K" or dei["fiscal_period_focus"] != "FY"
            or recipe["period"] != "FY" + dei["fiscal_year_focus"]
            or fiscal["dimensions"] or fiscal["typed_dimension_count"]):
        raise R4OfflineQualificationError("Fixture fiscal period/entity differs from native filing DEI")
    try:
        start, end = date.fromisoformat(fiscal["period_start"]), date.fromisoformat(fiscal["period_end"])
        try:
            document_end = date.fromisoformat(dei["document_period_end"])
        except ValueError:
            document_end = datetime.strptime(dei["document_period_end"], "%B %d, %Y").date()
    except (TypeError, ValueError) as error:
        raise R4OfflineQualificationError("Native fiscal dates are absent or invalid") from error
    if start >= end or document_end != end:
        raise R4OfflineQualificationError("Native fiscal duration and document end disagree")
    return {"period_label": recipe["period"], "period_start": start.isoformat(),
        "period_end": end.isoformat(), "dei": dei, "context_ref": fiscal["context_ref"],
        "parsed_source_id": parsed.parsed_source_id,
        "authority": "NATIVE_SOURCE_BOUND_DEI_FISCAL_CONTEXT"}


def evaluate_structured_route(*, repo_root: Path, requirement: Mapping,
                              recipe: Mapping, source_bundle: Mapping) -> dict:
    from .deterministic_router import adapt_accession_xbrl_from_parsed
    selection = recipe["structured_route_input"]
    if selection is None:
        return {"outcome": "AI_TABLE_ROUTE", "provider_call_eligible": True,
                "qualification_credit": "NONE_OFFLINE_SYNTHETIC"}
    if selection["measure"] == "INTERNATIONAL_NET_REVENUE":
        policies = [d["choice"] for d in requirement["effective_decisions"].values()
            if d["status"] == "APPROVED" and d["choice"].get("kind") == "INTERNATIONAL_NET_REVENUE_POLICY"
            and d["choice"].get("metric_id") == recipe["metric_id"]]
        if (len(policies) != 1 or policies[0]["economic_measure"] != selection["measure"]
                or policies[0]["canonical_unit"] != recipe["reference"]["unit"]
                or any(name.rsplit(":", 1)[-1].casefold() not in {
                    "revenues", "revenuesnetofinterestexpense"} for name in selection["fact_names"])):
            raise R4OfflineQualificationError("Structured claim is not the approved native net-revenue family")
    context = _structured_context(repo_root=repo_root, bundle=source_bundle)
    fiscal_period = _structured_fiscal_period(context=context, recipe=recipe, source_bundle=source_bundle)
    claims = adapt_accession_xbrl_from_parsed(parsed_source=context["parsed"],
        raw_bytes=context["raw_bytes"], source_reference=context["source_reference"],
        source_set_manifest=context["source_set_manifest"], fact_names=selection["fact_names"])
    current, dispositions = [], []
    for claim in claims:
        ctx = claim["attributes"]["context"]
        reason = None
        if ctx["period_end"] != fiscal_period["period_end"]:
            reason = "DIFFERENT_PERIOD"
        elif ctx["typed_dimension_count"]:
            reason = "TYPED_DIMENSION_NOT_APPROVED"
        elif int(ctx["entity_identifier"]) != int(source_bundle["declaration"]["cik"]):
            reason = "DIFFERENT_ENTITY"
        elif selection["measure"] == "INTERNATIONAL_NET_REVENUE" and ctx["period_start"] != fiscal_period["period_start"]:
            reason = "DIFFERENT_DURATION"
        dimensions = ctx["dimensions"]
        preferred = (len(dimensions) == 1 and list(dimensions.values())[0]
                     in selection["direct_geography_members"] and next(iter(dimensions)) in {
                         "srt:StatementGeographicalAxis", "us-gaap:GeographicDistributionAxis"}
                     and claim["unit"].casefold() == "usd") if selection["measure"] == "INTERNATIONAL_NET_REVENUE" else (
                         not dimensions and claim["unit"].casefold() in {"number", "pure", "ratio"})
        direct = claim["attributes"]["canonical_name"].casefold() in {
            name.casefold() for name in selection["direct_concepts"]}
        if reason is None and preferred and direct:
            current.append(claim)
            reason = "SELECTED_DIRECT_SCOPE"
        elif reason is None:
            reason = "NOT_APPROVED_DIRECT_CONCEPT" if not direct else "DIFFERENT_SCOPE_OR_UNIT"
        dispositions.append({"claim_hash": content_hash(value=claim),
            "canonical_name": claim["attributes"]["canonical_name"], "context": ctx,
            "value": claim["value"], "unit": claim["unit"], "disposition": reason,
            "unresolved": False})
    semantic_values = {(claim["value"], claim["unit"].casefold()) for claim in current}
    outcome = "STRUCTURED_PRIMARY_RESOLVED" if len(semantic_values) == 1 else (
        "STRUCTURED_SOURCE_AMBIGUOUS" if claims else "STRUCTURED_SOURCE_UNAVAILABLE")
    if outcome != selection["expected_outcome"]:
        raise R4OfflineQualificationError("Actual structured route changed; do not force AI fallback")
    if outcome == "STRUCTURED_PRIMARY_RESOLVED":
        actual_value = next(iter(semantic_values))[0]
        if actual_value != recipe["reference"]["value"]:
            raise R4OfflineQualificationError("Structured policy value differs from audited reference")
    else:
        actual_value = None
    body = {"record_type": "R4_STRUCTURED_ROUTE_RECEIPT", "schema_version": 1,
        "requirement_id": requirement["requirement_id"],
        "requirement_closure_hash": requirement["requirement_closure_hash"],
        "fixture_id": recipe["fixture_id"], "metric_id": recipe["metric_id"],
        "route_id": selection["route_id"], "economic_measure": selection["measure"],
        "source_set_manifest": context["source_set_manifest"],
        "source_reference": context["source_reference"], "source_file_bindings": context["file_bindings"],
        "parsed_source_id": context["parsed"].parsed_source_id,
        "target_fiscal_period": fiscal_period,
        "all_claims_hash": content_hash(value=claims), "all_claims_count": len(claims),
        "selected_claims": current, "claim_dispositions": dispositions,
        "outcome": outcome, "value": actual_value,
        "provider_call_eligible": outcome == "STRUCTURED_SOURCE_AMBIGUOUS",
        "regional_sum_used": False, "qualification_credit": "NONE_OFFLINE_SYNTHETIC",
        "provider_paid_sec_calls": [0, 0, 0]}
    return {**body, "structured_route_receipt_id": content_hash(value=body)}


def _response(*, recipe: Mapping, task: Mapping, bundle: Mapping, evidence_context=None) -> dict:
    asset = bundle["full_derived_asset"] if evidence_context is None else evidence_context._scope_authority(
        task_contract_id=task["task_contract_id"])["full_derived_asset"]
    resolver = resolve_cell if evidence_context is None else evidence_context.resolve_cell
    target = cell_locator(asset=asset, **recipe["target"])
    cell = resolver(derived_asset=asset, locator=target)
    labels, claims = [], []
    for index, label in enumerate(recipe["scope_labels"]):
        locator = cell_locator(asset=asset, **label["coordinate"])
        raw = resolver(derived_asset=asset, locator=locator)["raw_text"]
        label_id = "scope_" + str(index)
        labels.append({"id": label_id, "location_type": "label", "raw_text": raw,
            "locator": locator, "supports_dimensions": list(label["claims"])})
        claims.extend({"dimension": key, "raw_value": value,
            "evidence_locator_ids": [label_id]} for key, value in label["claims"].items())
    spec = compile_spec_file(path=Path(bundle["repo_root"]) / task["metric_spec_paths"][0], dependency_specs={})
    return {"disclosure_group": task["disclosure_group"],
        "table_locator": {"derived_asset_id": asset["derived_asset_id"], "table_id": target["table_id"]},
        "candidates": [{"role": task["required_roles"][0], "claimed_period": recipe["period"],
            "claimed_raw_value": cell["text"], "claimed_reported_unit": spec["compiled"]["reported_unit"],
            "claimed_scope": claims, "locator": target, "scope_evidence_locators": labels,
            "competing_candidates": []}], "unresolved_competing_claims": []}


def _audit(*, recipe: Mapping, bundle: Mapping, candidate: Mapping,
           comparison: Mapping = None) -> dict:
    from .constraints import parse_numeric_claim, ConstraintError
    asset = bundle["full_derived_asset"]
    target = cell_locator(asset=asset, **recipe["target"])
    rows = {(r["table_order"], r["row_index"]): r for r in recipe["candidate_rows"]}
    audit, outside = [], []
    window_orders = {n for w in recipe["windows"] for n in range(w["start_order"], w["end_order"] + 1)}
    for table in asset["tables"]:
        dispositions = []
        for row in table["rows"]:
            declaration = rows.get((table["order"], row["row_index"]))
            if declaration is None:
                continue
            for cell in row["cells"]:
                if not cell["is_origin"] or not cell["text"]:
                    continue
                try:
                    parse_numeric_claim(raw_value=cell["text"], reported_unit="USD")
                except (ConstraintError, ValueError):
                    continue
                locator = cell_locator(asset=asset, table_order=table["order"],
                    row_index=row["row_index"], column_index=cell["column_index"])
                disposition = "TARGET" if locator == target else declaration["disposition"]
                item = {"locator": locator, "disposition": disposition, "unresolved": False,
                    "evidence": "Audited original row/cell: {} r{} c{} raw={!r}; {}. Source-specific period/role/scope is retained in the complete row/header and audited recipe.".format(
                        table["table_id"], row["row_index"], cell["column_index"], cell["raw_text"], disposition)}
                dispositions.append(item)
        if target["table_id"] == table["table_id"] and not any(d["locator"] == target for d in dispositions):
            raise R4OfflineQualificationError("Candidate audit omitted the primary target")
        audit.append({"table_id": table["table_id"], "grid_sha256": table["grid_sha256"],
            "disposition": "TARGET" if any(d["disposition"] == "TARGET" for d in dispositions) else
                           "CANDIDATES_CLOSED" if dispositions else "NO_TARGET_CANDIDATE",
            "evidence": "Complete original-table census; candidate rows are pinned by the independent source/task audit recipe.",
            "candidate_locator_ids": [content_hash(value=d["locator"]) for d in dispositions],
            "candidate_dispositions": dispositions})
        if table["order"] not in window_orders:
            outside.extend(dispositions)
    ref = {**recipe["reference"], "period": recipe["period"]}
    paths = [{**path, "source_sha256": bundle["declaration"]["source_sha256"],
        "anchor": "original:{}:{}".format(target["table_id"], path["method"]),
        "target_locator": target} for path in recipe["navigation_paths"]]
    source = bundle["declaration"]
    alternate = recipe["fixture_class"] == "POSITIVE_ALTERNATE_LAYOUT"
    differences = []
    layout_facts = "Production source and full original target-table identity are pinned."
    if alternate:
        if comparison is None or source["cik"] == comparison["cik"]:
            raise R4OfflineQualificationError("Alternate lacks an independent production comparison")
        own_table = source["target_table_metadata"][recipe["metric_id"]]
        prior_table = comparison["target_table_metadata"][recipe["metric_id"]]
        differences.append("different_issuer_cik:{}!={}".format(source["cik"], comparison["cik"]))
        if source["table_count"] != comparison["table_count"]:
            differences.append("different_document_table_count:{}!={}".format(
                source["table_count"], comparison["table_count"]))
        own_geometry = (own_table["row_count"], own_table["column_count"])
        prior_geometry = (prior_table["row_count"], prior_table["column_count"])
        if own_geometry != prior_geometry:
            differences.append("different_original_target_geometry:{}x{}!={}x{}".format(
                *own_geometry, *prior_geometry))
        if len(differences) < 2 or own_table["grid_sha256"] == prior_table["grid_sha256"]:
            raise R4OfflineQualificationError("Alternate lacks a material original layout difference")
        layout_facts = "Execution-bound full source census and original target geometry: {} / {}; original grid hashes {} / {}. No same-issuer substitute.".format(
            own_table["table_id"], prior_table["table_id"], own_table["grid_sha256"], prior_table["grid_sha256"])
    layout = {"kind": "MATERIAL_ALTERNATE_LAYOUT" if alternate else "PRODUCTION_BASELINE",
        "source_cik": source["cik"], "source_sha256": source["source_sha256"],
        "comparison_source_cik": comparison["cik"] if alternate else None,
        "comparison_source_sha256": comparison["source_sha256"] if alternate else None,
        "differences": differences, "evidence": layout_facts}
    return {"fixture_id": recipe["fixture_id"], "fixture_class": recipe["fixture_class"],
        "windows": recipe["windows"], "target_locator": target, "reference": ref,
        "synthetic_candidate": candidate, "out_of_window_candidates": outside,
        "table_audit": audit, "material_layout_proof": layout, "navigation_paths": paths}


def _production_comparison(*, authority: Mapping, recipe: Mapping) -> Mapping:
    source_id = next(f["source_id"] for f in authority["fixtures"]
        if f["metric_id"] == recipe["metric_id"] and f["fixture_class"] == "POSITIVE_PRODUCTION")
    return authority["sources"][source_id]


def _structured_source_audit(*, authority: Mapping, recipe: Mapping,
                             source_bundle: Mapping, route: Mapping) -> dict:
    """Independent original-table census; this is not a Reader certificate.

    A native structured success must not manufacture an AI request to obtain a
    second positive. Its original human-readable disclosure and every audited
    outside candidate remain separately inspectable beside the native claims.
    """
    audit = _audit(recipe=recipe, bundle=source_bundle, candidate=None,
        comparison=_production_comparison(authority=authority, recipe=recipe))
    body = {"record_type": "R4_STRUCTURED_SOURCE_AUDIT", "schema_version": 1,
        "fixture_id": recipe["fixture_id"], "recipe": recipe,
        "source_sha256": source_bundle["declaration"]["source_sha256"],
        "full_derived_asset_id": source_bundle["full_derived_asset"]["derived_asset_id"],
        "original_table_audit": audit,
        "structured_route_receipt_id": route["structured_route_receipt_id"],
        "native_claim_dispositions": route["claim_dispositions"],
        "evidence_kind": "NATIVE_DETERMINISTIC_CLAIMS_NO_READER_CALL",
        "reader_candidate_check": "NOT_APPLICABLE_STRUCTURED_PRIMARY",
        "provider_call_eligible": False, "qualification_credit": "NONE_OFFLINE_SYNTHETIC"}
    return {**body, "source_audit_id": content_hash(value=body)}


def _scoped_summary(*, recipe: Mapping, scope: Mapping, attempt: Mapping) -> dict:
    """Derive fixed semantics from native replay, not a self-signed summary."""
    return {"fixture_id": recipe["fixture_id"], "fixture_class": recipe["fixture_class"],
        "metric_id": recipe["metric_id"], "source_scope_manifest_id": scope["source_scope_manifest_id"],
        "scoped_plan_id": attempt["scoped_plan_id"], "scoped_request_id": attempt["scoped_request_id"],
        "scoped_attempt_id": attempt["scoped_attempt_id"],
        "evidence_check_id": attempt["evidence"]["evidence_check_id"],
        "value": next(iter(attempt["evidence"]["normalized_values"].values())),
        "period": recipe["period"], "provider_call_eligible": True,
        "actual_provider_usage": "NOT_RUN", "qualification_credit": "NONE_OFFLINE_SYNTHETIC"}


def _validate_recipe_scope_binding(*, scope: Mapping, attempt: Mapping, recipe: Mapping,
                                   authority: Mapping, source_bundle: Mapping,
                                   task: Mapping, evidence_context=None) -> None:
    """Re-render approved coordinates; never rediscover or select a new window.

    SourceScope's native replay proves byte/locator/semantic consistency. This
    additional boundary prevents replacing a derived index and scope together
    with a different, otherwise valid source-specific audit recipe.
    """
    expected = _audit(recipe=recipe, bundle=source_bundle,
        candidate=scope["synthetic_candidate"],
        comparison=_production_comparison(authority=authority, recipe=recipe))
    if any(scope.get(key) != value for key, value in expected.items()):
        raise R4OfflineQualificationError("Stored SourceScope differs from execution-bound audit recipe")
    response = _response(recipe=recipe, task=task, bundle=source_bundle,
                         evidence_context=evidence_context)
    if attempt["response_text"] != canonical_json_bytes(value=response).decode():
        raise R4OfflineQualificationError("Stored synthetic response differs from execution-bound recipe")
    proof = scope["source_bound_proof"]
    needs_proof = recipe["numeric_locator"] is not None or recipe["composite_scope_recipe"] is not None
    if (proof is not None) != needs_proof:
        raise R4OfflineQualificationError("Source-bound proof presence differs from audit recipe")
    if proof is None:
        return
    asset = source_bundle["full_derived_asset"]
    expected_numeric = None if recipe["numeric_locator"] is None else cell_locator(
        asset=asset, **recipe["numeric_locator"])
    actual_numeric = None if proof["numeric_normalization"] is None else proof["numeric_normalization"]["unit_locator"]
    actual_composite = None if proof["composite_scope"] is None else proof["composite_scope"]["recipe"]
    expected_period = recipe["disclosed_period_recipe"]
    actual_period = proof["disclosed_period"]
    if expected_period is not None:
        expected_period = dict(expected_period)
        expected_period["period_header_locator"] = cell_locator(asset=asset,
            **expected_period.pop("period_header_coordinate"))
        actual_period = None if actual_period is None else {key: actual_period.get(key) for key in expected_period}
    if (proof["target_locator"] != expected["target_locator"] or expected_numeric != actual_numeric
            or actual_composite != recipe["composite_scope_recipe"] or actual_period != expected_period):
        raise R4OfflineQualificationError("Source-bound numeric/composite/period proof differs from input recipe")


def build_offline_case(*, repo_root: Path, requirement: Mapping, fixture_id: str,
                       source_bundle: Mapping, task_contract: Mapping = None,
                       evidence_context=None) -> dict:
    authority = load_r4_fixture_authority(repo_root=repo_root, requirement=requirement)
    recipe = authority["recipes"][fixture_id]
    if recipe["source_id"] != source_bundle["source_id"]:
        raise R4OfflineQualificationError("Fixture and source bundle differ")
    task = task_contract or resolve_r4_task_contract(repo_root=repo_root,
        requirement=requirement, task_contract_id=recipe["task_contract_id"])
    source_bundle["repo_root"] = str(repo_root)
    if recipe["artifact_kind"] == "ZERO_CALL_CLASSIFICATION":
        negative_candidate = negative_evidence = None
        if recipe["fixture_class"] == "NOT_APPLICABLE":
            traits = repository_company_traits(repo_root=repo_root,
                company_id=source_bundle["declaration"]["company_id"])
            spec = compile_spec_file(path=repo_root / task["metric_spec_paths"][0], dependency_specs={})
            if metric_is_applicable(applicability=spec["compiled"]["applicability"], traits=traits):
                raise R4OfflineQualificationError("NOT_APPLICABLE fixture is actually applicable")
        elif recipe["fixture_class"] in {"NEGATIVE_EXPECTED", "AMBIGUOUS_EXCLUDED"}:
            probe = recipe["negative_probe"]
            base = dict(authority["recipes"][probe["base_fixture_id"]])
            if base["source_id"] != recipe["source_id"] or base["metric_id"] != recipe["metric_id"]:
                raise R4OfflineQualificationError("Negative probe changes source/task identity")
            if probe["target"] is not None:
                base["target"] = probe["target"]
            if probe["scope_labels"] is not None:
                base["scope_labels"] = probe["scope_labels"]
            negative_response = _response(recipe=base, task=task, bundle=source_bundle, evidence_context=evidence_context)
            negative_response["unresolved_competing_claims"] = probe["unresolved_competing_claims"]
            negative_candidate = validate_reader_output(
                response_text=canonical_json_bytes(value=negative_response).decode(),
                attempt_id="offline-zero:" + fixture_id, required_roles=task["required_roles"],
                scope_contract=task["scope_contract"],
                source_reference_ids=[source_bundle["source_reference"]["source_reference_id"]],
                derived_asset_ids=[source_bundle["full_derived_asset"]["derived_asset_id"]])
            if evidence_context is None:
                negative_payload = build_reader_payload(manifest=source_bundle["reader_manifest"],
                    derived_asset=source_bundle["full_derived_asset"], task_contract=task)["body"]
                negative_evidence = check_evidence(candidate=negative_candidate,
                    derived_asset=source_bundle["full_derived_asset"], reader_manifest=source_bundle["reader_manifest"],
                    reader_payload_body=negative_payload, source_references=[source_bundle["source_reference"]],
                    identity_constraints=task["identity_constraints"], scope_contract=task["scope_contract"])
            else:
                from .evidence import check_evidence_in_offline_session
                negative_evidence = check_evidence_in_offline_session(context=evidence_context,
                    candidate=negative_candidate, task_contract_id=task["task_contract_id"])
            if negative_evidence["system_approval_eligible"]:
                raise R4OfflineQualificationError("Negative fixture unexpectedly became auto-eligible")
        body = {"record_type": "R4_ZERO_CALL_FIXTURE_RESULT", "fixture_id": fixture_id,
            "fixture_class": recipe["fixture_class"], "reason": recipe["zero_call_reason"],
            "requirement_closure_hash": requirement["requirement_closure_hash"],
            "source_sha256": source_bundle["declaration"]["source_sha256"],
            "full_derived_asset_id": source_bundle["full_derived_asset"]["derived_asset_id"],
            "provider_call_eligible": False, "provider_paid_sec_calls": [0, 0, 0],
            "qualification_credit": "NONE_OFFLINE_SYNTHETIC",
            "synthetic_candidate": negative_candidate, "native_evidence": negative_evidence}
        return {"summary": body, "zero_call_result": {**body, "result_id": content_hash(value=body)}}
    route = evaluate_structured_route(repo_root=repo_root, requirement=requirement,
                                      recipe=recipe, source_bundle=source_bundle)
    if recipe["artifact_kind"] == "STRUCTURED_PRIMARY":
        if route["provider_call_eligible"] or route["outcome"] != "STRUCTURED_PRIMARY_RESOLVED":
            raise R4OfflineQualificationError("Structured-positive fixture must remain zero-provider")
        summary = {"fixture_id": fixture_id, "fixture_class": recipe["fixture_class"],
            "metric_id": recipe["metric_id"], "outcome": route["outcome"],
            "value": route["value"], "period": recipe["period"],
            "structured_route_receipt_id": route["structured_route_receipt_id"],
            "provider_call_eligible": False, "qualification_credit": "NONE_OFFLINE_SYNTHETIC"}
        return {"summary": summary, "structured_route": route,
                "source_audit": _structured_source_audit(authority=authority, recipe=recipe,
                    source_bundle=source_bundle, route=route)}
    if not route["provider_call_eligible"]:
        raise R4OfflineQualificationError("Structured-first success forbids an AI fallback plan")
    asset = source_bundle["full_derived_asset"]
    response = _response(recipe=recipe, task=task, bundle=source_bundle, evidence_context=evidence_context)
    target = response["candidates"][0]["locator"]
    owned = None if evidence_context is None else evidence_context._scope_authority(
        task_contract_id=task["task_contract_id"])
    proof_authority = {
        "requirement": requirement, "repo_root": repo_root,
        "source_bytes": source_bundle["source_bytes"], "raw_blob": source_bundle["raw_blob"],
        "source_reference": source_bundle["source_reference"], "full_derived_asset": asset,
        "task_contract": task,
    } if owned is None else {key: owned[key] for key in (
        "requirement", "repo_root", "source_bytes", "raw_blob", "source_reference",
        "full_derived_asset", "task_contract")}
    proof = None
    if recipe["numeric_locator"] is not None or recipe["composite_scope_recipe"] is not None:
        period = recipe["disclosed_period_recipe"]
        if period is not None:
            period = dict(period)
            period["period_header_locator"] = cell_locator(asset=asset, **period.pop("period_header_coordinate"))
        proof = build_source_bound_proof(**proof_authority, target_locator=target,
            numeric_locator=None if recipe["numeric_locator"] is None else cell_locator(asset=asset, **recipe["numeric_locator"]),
            composite_scope_recipe=recipe["composite_scope_recipe"], disclosed_period_recipe=period,
            _offline_context=evidence_context)
    response_text = canonical_json_bytes(value=response).decode()
    attempt_id = "offline-r4:" + fixture_id
    if proof is None:
        candidate = validate_reader_output(response_text=response_text, attempt_id=attempt_id,
            required_roles=task["required_roles"], scope_contract=task["scope_contract"],
            source_reference_ids=[source_bundle["source_reference"]["source_reference_id"]],
            derived_asset_ids=[asset["derived_asset_id"]])
    else:
        candidate = validate_source_bound_reader_output(response_text=response_text,
            attempt_id=attempt_id, source_bound_proof=proof, expected_proof_id=proof["source_bound_proof_id"],
            **proof_authority, _offline_context=evidence_context)
    comparison = _production_comparison(authority=authority, recipe=recipe)
    audit = _audit(recipe=recipe, bundle=source_bundle, candidate=candidate, comparison=comparison)
    payload = owned["evidence_authority_payload"] if owned is not None else build_reader_payload(
        manifest=source_bundle["reader_manifest"], derived_asset=asset, task_contract=task)["body"]
    args = owned if owned is not None else {"requirement": requirement, "raw_blob": source_bundle["raw_blob"],
        "source_reference": source_bundle["source_reference"], "full_derived_asset": asset,
        "reader_manifest": source_bundle["reader_manifest"], "task_contract": task,
        "evidence_authority_payload": payload, "repo_root": repo_root,
        "source_bytes": source_bundle["source_bytes"]}
    scope = build_source_scope_manifest(audit=audit, scope_schema_version=2,
                                        source_bound_proof=proof, _offline_context=evidence_context, **args)
    prepared = prepare_scoped_reader_request(source_scope_manifest=scope,
        expected_manifest_id=scope["source_scope_manifest_id"], _offline_evidence_context=evidence_context, **args)
    attempt = validate_scoped_reader_response(prepared_request=prepared, response_text=response_text,
        attempt_id=attempt_id, source_scope_manifest=scope,
        expected_manifest_id=scope["source_scope_manifest_id"], _offline_evidence_context=evidence_context, **args)
    summary = _scoped_summary(recipe=recipe, scope=scope, attempt=attempt)
    return {"scope": scope, "prepared_request": prepared, "attempt": attempt,
            "structured_route": route, "summary": summary}


def write_offline_case(*, repo_root: Path, fixture: Mapping, result: Mapping, requirement=None) -> dict:
    """Write only the additive offline case directory; never historical evidence."""
    directory = repo_root / corpus_root("issue_28_v2" if requirement is None else requirement["requirement_id"]) / fixture["fixture_id"]
    if directory.is_symlink():
        raise R4OfflineQualificationError("Offline output directory is a symlink")
    directory.mkdir(parents=True, exist_ok=True)
    if fixture["artifact_kind"] == "SCOPED_EXTRACTION":
        prepared = result["prepared_request"]
        files = {"source_scope.json": canonical_json_bytes(value=result["scope"]),
            "scoped_plan.json": prepared.plan_bytes, "scoped_request.json": prepared.request_bytes,
            "scoped_attempt.json": canonical_json_bytes(value=result["attempt"])}
    elif fixture["artifact_kind"] == "STRUCTURED_PRIMARY":
        files = {"structured_route.json": canonical_json_bytes(value=result["structured_route"]),
                 "source_audit.json": canonical_json_bytes(value=result["source_audit"])}
    else:
        files = {"zero_call_result.json": canonical_json_bytes(value=result["zero_call_result"])}
    if set(p.name for p in directory.iterdir()) - set(files):
        raise R4OfflineQualificationError("Offline case directory has unexpected existing artifacts")
    bindings = {}
    for name, data in files.items():
        path = directory / name
        if path.is_symlink():
            raise R4OfflineQualificationError("Offline artifact path is a symlink")
        atomic_write_bytes(path=path, content=data)
        bindings[name] = {"sha256": sha256_bytes(content=data), "size": len(data)}
    return {**dict(fixture), "directory": directory.relative_to(repo_root).as_posix(),
            "files": bindings, "summary": result["summary"],
            "structured_route": result.get("structured_route")}


def write_offline_index(*, repo_root: Path, requirement: Mapping, cases: list) -> dict:
    authority = load_r4_fixture_authority(repo_root=repo_root, requirement=requirement)
    if {c["fixture_id"] for c in cases} != {f["fixture_id"] for f in authority["fixtures"]}:
        raise R4OfflineQualificationError("Offline index case exact set is incomplete")
    body = {"record_type": "R4_OFFLINE_QUALIFICATION_INDEX", "schema_version": 1,
        "status": "OFFLINE_ONLY", "requirement_id": requirement["requirement_id"],
        "requirement_closure_hash": requirement["requirement_closure_hash"],
        "matrix_id": authority["matrix_id"], "metric_ids": authority["matrix"]["metric_ids"],
        "cases": sorted(cases, key=lambda c: c["fixture_id"]),
        "provider_paid_sec_calls": [0, 0, 0], "qualification_credit": "NONE_OFFLINE_SYNTHETIC",
        "live_authorization": "NOT_AUTHORIZED"}
    index = {**body, "index_id": content_hash(value=body)}
    atomic_write_bytes(path=repo_root / corpus_index(requirement["requirement_id"]), content=canonical_json_bytes(value=index))
    return index


def replay_case_artifacts(*, repo_root: Path, requirement: Mapping, fixture: Mapping,
                          source_bundle: Mapping, evidence_context=None,
                          scoped_context=None) -> dict:
    """One native kind-dispatch replay used identically by both benchmark modes."""
    from .source_scope import read_scope_repository_bytes
    from .scoped_reader import replay_scoped_offline_artifact_set
    from .scoped_reader import replay_scoped_offline_attempt_in_session
    authority = load_r4_fixture_authority(repo_root=repo_root, requirement=requirement)
    if fixture not in authority["fixtures"] or fixture["source_id"] != source_bundle["source_id"]:
        raise R4OfflineQualificationError("Replay fixture/source is not execution-bound")
    source_bundle["repo_root"] = str(repo_root)
    index = strict_json_file(path=resolve_repository_file(repo_root=repo_root, repo_relative_path=corpus_index(requirement["requirement_id"])))
    if (type(index) is not dict or set(index) != INDEX_FIELDS
            or index["record_type"] != "R4_OFFLINE_QUALIFICATION_INDEX"
            or type(index["schema_version"]) is not int or index["schema_version"] != 1
            or index["status"] != "OFFLINE_ONLY" or index["provider_paid_sec_calls"] != [0, 0, 0]
            or any(type(count) is not int for count in index["provider_paid_sec_calls"])
            or index["qualification_credit"] != "NONE_OFFLINE_SYNTHETIC"
            or index["live_authorization"] != "NOT_AUTHORIZED"
            or index["metric_ids"] != authority["matrix"]["metric_ids"]
            or index["requirement_id"] != requirement["requirement_id"]
            or index["requirement_closure_hash"] != requirement["requirement_closure_hash"]
            or index["matrix_id"] != authority["matrix_id"]
            or index["index_id"] != content_hash(value={k: v for k, v in index.items() if k != "index_id"})):
        raise R4OfflineQualificationError("Offline index Requirement/matrix/content identity differs")
    expected_fixtures = {f["fixture_id"] for f in authority["fixtures"]}
    if (type(index["cases"]) is not list or len(index["cases"]) != len(expected_fixtures)
            or any(type(c) is not dict or set(c) != CASE_FIELDS for c in index["cases"])
            or {c["fixture_id"] for c in index["cases"]} != expected_fixtures):
        raise R4OfflineQualificationError("Offline index fixture exact set differs")
    entries = [c for c in index["cases"] if c["fixture_id"] == fixture["fixture_id"]]
    if len(entries) != 1:
        raise R4OfflineQualificationError("Offline case is absent or duplicated")
    entry = entries[0]
    if any(entry[k] != fixture[k] for k in fixture):
        raise R4OfflineQualificationError("Offline indexed fixture identity differs")
    expected_files = {"SCOPED_EXTRACTION": {"source_scope.json", "scoped_plan.json", "scoped_request.json", "scoped_attempt.json"},
                      "STRUCTURED_PRIMARY": {"structured_route.json", "source_audit.json"},
                      "ZERO_CALL_CLASSIFICATION": {"zero_call_result.json"}}[fixture["artifact_kind"]]
    if (entry["directory"] != corpus_root(requirement["requirement_id"]) + "/" + fixture["fixture_id"]
            or type(entry["files"]) is not dict or set(entry["files"]) != expected_files
            or any(type(binding) is not dict or set(binding) != {"sha256", "size"}
                   or type(binding["size"]) is not int or binding["size"] <= 0
                   for binding in entry["files"].values())):
        raise R4OfflineQualificationError("Offline artifact path/kind exact set differs")
    directory = repo_root / entry["directory"]
    if directory.is_symlink() or {p.name for p in directory.iterdir()} != set(entry["files"]):
        raise R4OfflineQualificationError("Offline case directory exact set differs")
    contents = {name: read_scope_repository_bytes(path=directory / name, repo_root=repo_root,
                 expected_sha256=b["sha256"], expected_size=b["size"])
                for name, b in entry["files"].items()}
    if fixture["artifact_kind"] == "SCOPED_EXTRACTION":
        expected = entry["summary"]
        recipe = authority["recipes"][fixture["fixture_id"]]
        route = evaluate_structured_route(repo_root=repo_root, requirement=requirement,
            recipe=recipe, source_bundle=source_bundle)
        if not route["provider_call_eligible"] or route != entry["structured_route"]:
            raise R4OfflineQualificationError("Scoped fallback no longer matches the native structured route")
        scope = json.loads(contents["source_scope.json"])
        stored_attempt = json.loads(contents["scoped_attempt.json"])
        task = (resolve_r4_task_contract(repo_root=repo_root, requirement=requirement,
                    task_contract_id=fixture["task_contract_id"]) if evidence_context is None else
                evidence_context._scope_authority(task_contract_id=fixture["task_contract_id"])["task_contract"])
        _validate_recipe_scope_binding(scope=scope, attempt=stored_attempt, recipe=recipe,
            authority=authority, source_bundle=source_bundle, task=task, evidence_context=evidence_context)
        if scoped_context is not None:
            attempt = replay_scoped_offline_attempt_in_session(context=scoped_context,
                attempt=stored_attempt,
                expected_attempt_id=expected["scoped_attempt_id"])
            if (sha256_bytes(content=contents["scoped_plan.json"]) != attempt["plan_sha256"]
                    or sha256_bytes(content=contents["scoped_request.json"]) != attempt["request_sha256"]):
                raise R4OfflineQualificationError("Stored plan/request differ from independently rebuilt attempt")
        else:
            payload = build_reader_payload(manifest=source_bundle["reader_manifest"],
                derived_asset=source_bundle["full_derived_asset"], task_contract=task)["body"]
            attempt = replay_scoped_offline_artifact_set(directory=directory, repo_root=repo_root,
                file_bindings=entry["files"], expected_manifest_id=expected["source_scope_manifest_id"],
                expected_plan_id=expected["scoped_plan_id"], expected_request_id=expected["scoped_request_id"],
                expected_attempt_id=expected["scoped_attempt_id"], requirement=requirement,
                raw_blob=source_bundle["raw_blob"], source_reference=source_bundle["source_reference"],
                full_derived_asset=source_bundle["full_derived_asset"], reader_manifest=source_bundle["reader_manifest"],
                task_contract=task, evidence_authority_payload=payload, source_bytes=source_bundle["source_bytes"])
        if "attempt" in attempt:
            attempt = attempt["attempt"]
        summary = _scoped_summary(recipe=recipe, scope=scope, attempt=attempt)
    else:
        result = build_offline_case(repo_root=repo_root, requirement=requirement,
            fixture_id=fixture["fixture_id"], source_bundle=source_bundle, evidence_context=evidence_context)
        summary = result["summary"]
        file_key = "structured_route.json" if fixture["artifact_kind"] == "STRUCTURED_PRIMARY" else "zero_call_result.json"
        result_key = "structured_route" if fixture["artifact_kind"] == "STRUCTURED_PRIMARY" else "zero_call_result"
        if contents[file_key] != canonical_json_bytes(value=result[result_key]):
            raise R4OfflineQualificationError("Offline native structured/zero-call replay differs")
        if fixture["artifact_kind"] == "STRUCTURED_PRIMARY" and contents["source_audit.json"] != canonical_json_bytes(
                value=result["source_audit"]):
            raise R4OfflineQualificationError("Stored structured source audit differs from execution-bound recipe")
        if result.get("structured_route") != entry["structured_route"]:
            raise R4OfflineQualificationError("Stored route receipt differs from native replay")
    if summary != entry["summary"]:
        raise R4OfflineQualificationError("Offline semantic result differs on disk replay")
    return summary
