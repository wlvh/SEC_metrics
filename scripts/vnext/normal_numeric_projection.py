"""Independent presentation for verified ordinary numeric Runs.

The pure record renderer below is not an acceptance boundary. Only the frozen
Run entrypoint confers the FROZEN_RUN_VALIDATED receipt marker, after the native
loader and ordinary replay independently reconstruct the complete source case.
Neither entrypoint publishes files or changes an active pointer.
"""

import calendar
from datetime import date
import json
from pathlib import Path

from . import projector, publication
from .canonical import content_hash, sha256_file, strict_json_file
from .normal_source_authority import ROOT
from .records import validate_record
from .run_store import load_frozen_run
from .sources import resolve_repository_file
from .specs import compile_spec_file


POLICY_PATH = "config/normal_numeric_projection_v1.json"
_UNITS = {"A03": "ratio", "A04": "ratio", "A09": "ratio", "A11": "USD", "A12": "USD",
          "A13": "USD", "B06": "ratio", "C03": "USD", "C04": "flag"}


class NumericProjectionError(ValueError):
    """Refuse an unknown unit, unsupported state or unbound presentation."""


def _need(condition, reason):
    if not condition:
        raise NumericProjectionError(reason)


def _policy():
    path = resolve_repository_file(repo_root=ROOT, repo_relative_path=POLICY_PATH)
    policy = strict_json_file(path=path)
    _need(policy["record_type"] == "NORMAL_NUMERIC_PRESENTATION_POLICY" and policy["schema_version"] == 1
          and policy["production_authorized"] is False and policy["native_values_only"] is True
          and policy["probability_confidence_inferred"] is False and policy["withheld_status"] == "WITHHELD"
          and set(policy["metrics"]) == set(_UNITS), "NORMAL_NUMERIC_PRESENTATION_POLICY_INVALID")
    for metric, unit in _UNITS.items():
        item = policy["metrics"][metric]
        _need(item["canonical_unit"] == unit and item["projection"]["unit"] == unit
              and item["projection"]["value_multiplier"] == "1"
              and item["projection"]["confidence"] == ""
              and item["projection"]["evidence_unit_policy"] == "observation",
              "NORMAL_NUMERIC_UNIT_OR_VALUE_POLICY_CHANGED")
    return policy, sha256_file(path=path)


def _objects(value):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _objects(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _objects(item)


def _filings(binding):
    result = {}
    for item in _objects(binding):
        if {"accessionNumber", "form", "filingDate"} <= set(item):
            identity = {key: item[key] for key in ("accessionNumber", "form", "filingDate")}
            previous = result.get(identity["accessionNumber"])
            _need(previous is None or previous == identity, "PRESENTATION_FILING_METADATA_CONFLICT")
            result[identity["accessionNumber"]] = identity
    return result


def _annual(binding, company_id):
    matches = [item["table_input"]["target_period"] for item in _objects(binding)
               if item.get("company_id") == company_id and isinstance(item.get("table_input"), dict)
               and isinstance(item["table_input"].get("target_period"), dict)]
    unique = {content_hash(value=item): item for item in matches}
    _need(len(unique) == 1, "PRESENTATION_ANNUAL_GROUP_NOT_UNIQUE")
    return next(iter(unique.values()))


def _period_label(result, annual):
    if result["applicability"] == "N_A_STRUCTURAL":
        return "STRUCTURAL", "No financial measurement is asserted; dates retain the filing group."
    if result["publication"] == "WITHHELD":
        return "TARGET_PERIOD", "No accepted value is asserted for this target period."
    start, end = date.fromisoformat(result["period_start"]), date.fromisoformat(result["period_end"])
    if start == end:
        return "INSTANT", "Measurement is as of " + end.isoformat() + "."
    if result["period_start"] == annual["period_start"] and result["period_end"] == annual["period_end"]:
        return "ANNUAL", "Measurement covers the source fiscal-year interval."
    months = (end.year - start.year) * 12 + end.month - start.month + 1
    if months == 3 and start.day == 1 and end.day == calendar.monthrange(end.year, end.month)[1]:
        return "QUARTER", "Measurement is the disclosed quarter, not an annualized value."
    return "DURATION", "Measurement retains its exact disclosed start and end dates."


def _selected_financial_locators(metric, selection):
    fact = selection.get("source_fact") if isinstance(selection, dict) else None
    if not isinstance(fact, dict):
        return []
    if metric == "A03":
        values = [x["locator"] for x in fact.get("selected", [])]
    elif metric == "A04":
        values = [x["rate_locator"] for x in fact.get("relations", [])]
    elif metric in {"A11", "A12"}:
        values = [x["value"]["locator"] for x in fact.get("disclosures", fact.get("totals", []))]
    elif metric == "A13":
        values = [x["source_witness"]["table_cell"] for x in fact.get("selected", [])]
    elif metric == "A09":
        fallback = fact.get("html_fallback")
        values = ([x["locator"] for x in fallback.get("selected", [])] if fallback
                  else [x["source_witness"]["table_cell"] for x in fact.get("structured_primary", {}).get("selected", [])])
    else:
        return []
    return values


def _evidence_context(observation, locators):
    binding = observation["source_binding"]
    fields = ("xbrl_context_ref", "xbrl_fact_ordinal", "fact_locators", "locator", "table_locator",
              "value_locator", "amount_locator", "derived_asset_id", "selection_id", "source_fact_hash", "input_binding_id",
              "denominator_proof_hash", "source_reference_ids", "event_source_set_manifest_ids")
    return json.dumps({"semantic_role": observation["semantic_role"], "scope": observation["scope"],
                       "source_binding": {k: binding[k] for k in fields if k in binding},
                       "selected_source_cells": locators}, ensure_ascii=False, sort_keys=True)


def _raw_value(observation, locators, selection):
    """Expose only source text retained by the native resolver, never a guess.

    Some derived observations (notably the auditor flag) have no literal
    numeric source cell. Their raw value remains empty, with the full native
    source locator and normalized result kept separately.
    """
    texts = [item["raw_text"] for item in locators if isinstance(item.get("raw_text"), str)]
    if observation["metric_id"] == "C03" and isinstance(selection, dict):
        texts += [item["source_text"] for item in selection.get("candidates", []) if "source_text" in item]
        texts += [item["amount"]["raw_text"] for item in selection.get("candidates", [])
                  if isinstance(item.get("amount"), dict) and "raw_text" in item["amount"]]
    unique = list(dict.fromkeys(texts))
    return unique[0] if len(unique) == 1 else json.dumps(unique, ensure_ascii=False) if unique else ""


def _source_scope(indexes, filing_map):
    return [{**source, "repo_relative_path": indexes["raw"][source["raw_asset_id"]]["storage_uri"],
             "content_sha256": source["raw_asset_id"].split(":", 1)[1],
             "filing": filing_map.get(source["accession"])} for source in indexes["sources"].values()]


def _nonmeaningful_guard(result, trace, spec, path, policy):
    """The only supported early terminal says nothing about computed debt."""
    guard = policy["nonmeaningful_guard"]
    expected = {key: guard[key] for key in ("role", "condition", "debt_completeness")}
    steps = [step for step in trace["steps"] if step.get("event") == "DENOMINATOR_GUARD"]
    _need(result["metric_id"] == "B06" and path == guard["spec_path"]
          and result["reason_code"] == guard["reason_code"]
          and spec["quality_rule"].get("resolver") == guard["resolver"]
          and all(spec["quality_rule"].get("early_terminal_guard", {}).get(k) == v for k, v in expected.items())
          and len(steps) == 1 and steps[0].get("resolver") == guard["resolver"]
          and steps[0].get("numerator_evaluated") is False
          and all(steps[0].get(k) == v for k, v in expected.items()),
          "NUMERIC_NOT_MEANINGFUL_GUARD_UNSUPPORTED")


def project_normal_numeric_records(*, repo_root: Path, manifest: dict, records: list,
                                   compiled_spec: dict, input_binding: dict, selection=None) -> dict:
    """Render records without claiming they were independently source-validated.

    Used by the verified frozen entrypoint and bounded rendering tests. It has
    no caller value/unit/policy override and never modifies the executed Spec.
    """
    policy, policy_sha = _policy()
    for record in records:
        validate_record(record=record)
    results = [r for r in records if r["record_type"] == "METRIC_RESULT"]
    _need(len(results) == 1 and results[0].get("value_kind") != "TEXT_V1", "ONE_NATIVE_NUMERIC_RESULT_REQUIRED")
    result = results[0]
    metric = result["metric_id"]
    _need(metric in policy["metrics"], "NUMERIC_PRESENTATION_METRIC_UNSUPPORTED")
    spec = compiled_spec["compiled"]
    item = policy["metrics"][metric]
    paths = list(manifest["spec_file_hashes"])
    _need(len(paths) == 1 and paths[0] in item["allowed_spec_paths"]
          and spec["metric_id"] == metric and result["spec_closure_hash"] == compiled_spec["spec_closure_hash"],
          "NUMERIC_PRESENTATION_EXECUTED_SPEC_DIFFERS")
    _need(spec["canonical_unit"] == item["canonical_unit"]
          and (result["value"] is None or result["unit"] == item["canonical_unit"]), "NUMERIC_UNIT_UNKNOWN_OR_CHANGED")
    if metric == "C04" and result["value"] is not None:
        _need(result["value"] in {"0", "1"}, "AUDITOR_CHANGE_FLAG_IS_NOT_BINARY")
    _need(result["company_id"] == manifest["company_id"]
          and all(result[k] == manifest["target_period"][k] for k in ("period_start", "period_end")),
          "NUMERIC_PRESENTATION_TARGET_DIFFERS")
    companies = [r for r in projector._load_registry(repo_root=repo_root) if r["company_id"] == result["company_id"]]
    _need(len(companies) == 1, "NUMERIC_PRESENTATION_COMPANY_NOT_UNIQUE")
    company = companies[0]
    annual = _annual(input_binding, result["company_id"])
    _need(annual["fiscal_year"] == manifest["target_period"]["fiscal_year"], "NUMERIC_PRESENTATION_FISCAL_GROUP_DIFFERS")
    period_label, period_note = _period_label(result, annual)
    projection = {**item["projection"], **item.get("spec_presentation_overrides", {}).get(paths[0], {})}
    view = {"compiled": {"name": spec["name"], "reported_unit": spec["reported_unit"], "legacy_projection": projection}}
    indexes = projector._record_indexes(runs=[(manifest, records)])
    trace = indexes["traces"][result["trace_id"]]
    _need(trace["metric_id"] == metric and trace["result"] == result["value"], "NUMERIC_PRESENTATION_TRACE_DIFFERS")
    ordered, _ = projector._ordered_observations(trace=trace, observations=indexes["observations"], projection=projection)
    filing_map = _filings(input_binding)
    source_filings = [filing_map.get(o["source_binding"]["accession"]) for o in ordered]
    known = [f for f in source_filings if f]
    baseline = {field: "" for field in publication.METRIC_FIELDS}
    baseline.update(company=company["display_name"], cik=company["primary_cik"], metric_id=metric,
        metric_name=spec["name"], unit=projection["unit"], status=result["quality"],
        source_class=projection["source_class"], formula=projection["formula"],
        period_start=result["period_start"], period_end=result["period_end"], fiscal_year=str(annual["fiscal_year"]),
        fiscal_period=period_label, concept_or_section=projection["concept_or_section"],
        form=";".join(dict.fromkeys(f["form"] for f in known)),
        filed_date=";".join(dict.fromkeys(f["filingDate"] for f in known)), notes=projection["notes"])
    if result["publication"] == "WITHHELD":
        _need(result["value"] is None, "WITHHELD_RESULT_CANNOT_HAVE_PUBLIC_VALUE")
        row, evidence, contributors = dict(baseline), [], 0
        row["status"] = policy["withheld_status"]
    else:
        row, evidence, contributors = projector._project_result(result=result, trace=trace, company=company,
            spec=view, baseline_row=baseline, indexes=indexes, fiscal_year=str(annual["fiscal_year"]),
            metric_fields=publication.METRIC_FIELDS)
    if result["quality"] == "NOT_MEANINGFUL":
        _nonmeaningful_guard(result, trace, spec, paths[0], policy)
        # The core preserves the null ratio; evidence still shows only the
        # actual evaluated equity, never an invented debt amount or ratio.
        evidence = [projector._evidence_row(observation=o, result=result, company=company, projection=projection,
            source_index=indexes["sources"], raw_index=indexes["raw"], fiscal_year=str(annual["fiscal_year"])) for o in ordered]
        contributors = len(evidence)
    locators = _selected_financial_locators(metric, selection)
    for observation, entry in zip(ordered, evidence):
        entry["context_or_dimension"] = _evidence_context(observation, locators)
        entry["value_raw"] = _raw_value(observation, locators, selection)
        entry["evidence_quote"] = "Normalized verified observation: " + entry["evidence_quote"]
    row["fiscal_period"] = period_label
    row["confidence"] = ""
    source_scope = _source_scope(indexes, filing_map)
    context = {"scope": trace["calculation_target"]["scope"],
        "measurement_kind": period_label, "annual_filing_group": annual}
    if result["publication"] == "WITHHELD":
        context.update(source_scope=source_scope, reason_code=result["reason_code"],
                       resolution_details=selection or {})
    row["context_or_dimension"] = json.dumps(context, sort_keys=True)
    if ordered:
        row["accession"] = ";".join(dict.fromkeys(o["source_binding"]["accession"] for o in ordered))
    row["notes"] = " ".join([str(row["notes"]), period_note, "Native state: " + result["publication"] +
                                "; reason: " + result["reason_code"] + "."])
    if result["quality"] == "NOT_MEANINGFUL":
        row["notes"] += " Debt completeness: NOT_EVALUATED; no debt-to-equity value is asserted."
    _need(set(row) == set(publication.METRIC_FIELDS) and all(set(e) == set(publication.EVIDENCE_FIELDS) for e in evidence),
          "NUMERIC_PUBLIC_ROW_SCHEMA_CHANGED")
    receipt = {"record_type": "NORMAL_NUMERIC_PUBLIC_ROW_RECEIPT", "status": "RECORDS_ONLY_RENDERING",
        "source_validation": "NOT_ASSERTED_BY_PURE_RENDERER", "run_id": manifest["run_id"],
        "run_status": manifest["status"], "result_id": result["result_id"], "trace_id": trace["trace_id"],
        "spec_closure_hash": compiled_spec["spec_closure_hash"], "executed_spec_path": paths[0],
        "executed_spec_file_sha256": manifest["spec_file_hashes"][paths[0]],
        "presentation_policy_sha256": policy_sha, "renderer_sha256": sha256_file(path=Path(__file__)),
        "input_binding_hash": content_hash(value=input_binding), "native_result_state": result["publication"],
        "native_reason_code": result["reason_code"], "measurement_kind": period_label,
        "filing_period": annual, "observation_ids": [o["observation_id"] for o in ordered],
        "supporting_source_references": manifest["source_references"],
        "source_scope": source_scope,
        "row_hash": content_hash(value=row), "evidence_hash": content_hash(value=evidence),
        "contributing_evidence_count": contributors, "production_authorized": False}
    return {"row": row, "evidence": evidence,
        "receipt": {**receipt, "receipt_id": content_hash(value=receipt)},
        "files": {"metrics_matrix.csv": publication._csv_bytes(rows=[row], fieldnames=publication.METRIC_FIELDS),
                  "metric_evidence.csv": publication._csv_bytes(rows=evidence, fieldnames=publication.EVIDENCE_FIELDS)}}


def render_normal_numeric_run(*, data_root: Path, run_dir: Path) -> dict:
    """Read one independently verified FROZEN V13 Run; never freeze or publish."""
    policy, _ = _policy()
    manifest, records, _ = load_frozen_run(run_dir=run_dir, repo_root=data_root)
    _need(manifest["requirement_id"] == policy["requirement_id"] and manifest["status"] == "FROZEN"
          and manifest["run_id"].startswith(policy["run_prefix"]), "NORMAL_NUMERIC_FROZEN_RUN_REQUIRED")
    paths = list(manifest["spec_file_hashes"])
    _need(len(paths) == 1, "NORMAL_NUMERIC_ONE_EXECUTED_SPEC_REQUIRED")
    spec = compile_spec_file(path=resolve_repository_file(repo_root=data_root, repo_relative_path=paths[0]), dependency_specs={})
    from .normal_run_v2 import replay_case
    case = replay_case(data_root=data_root, manifest=manifest, spec=spec)
    _need(case["kind"] == "STRUCTURED", "NORMAL_NUMERIC_STRUCTURED_RUN_REQUIRED")
    key = manifest["run_id"][len(policy["run_prefix"]):]
    binding = strict_json_file(path=resolve_repository_file(repo_root=data_root,
        repo_relative_path="normal_current_bindings/" + key + ".json"))
    _need(content_hash(value=binding) == "sha256:" + key, "NORMAL_NUMERIC_RUN_BINDING_CHANGED")
    rendered = project_normal_numeric_records(repo_root=data_root, manifest=manifest, records=records,
        compiled_spec=spec, input_binding=binding, selection=case["selection"])
    receipt = {k: v for k, v in rendered["receipt"].items() if k != "receipt_id"}
    receipt.update(status="CANDIDATE_ONLY", source_validation="FROZEN_RUN_VALIDATED",
                   requirement_closure_hash=manifest["requirement_closure_hash"], run_binding_id="sha256:" + key)
    rendered["receipt"] = {**receipt, "receipt_id": content_hash(value=receipt)}
    return rendered
