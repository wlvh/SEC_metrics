"""Public text rows from the verified ordinary successor, with no publication."""
from pathlib import Path

from . import projector, publication
from .canonical import content_hash, sha256_file, strict_json_file
from .normal_source_authority import ROOT
from .run_store import load_frozen_run
from .sources import resolve_repository_file
from .specs import compile_spec_file


POLICY_PATH = "config/normal_text_projection_v2.json"


def _need(condition, reason):
    if not condition:
        raise ValueError(reason)


def render_normal_text_run(*, data_root: Path, run_dir: Path):
    """Render one frozen D01/C02/D02 candidate using the existing CSV schemas."""
    manifest, records, _ = load_frozen_run(run_dir=run_dir, repo_root=data_root)
    return _render_verified_text_records(data_root=data_root, manifest=manifest, records=records)


def render_open_text_preview(*, data_root: Path, run_dir: Path):
    """Preview a complete verified OPEN candidate without freezing draft rules."""
    from .run_store import _mechanically_replay_open_run
    manifest, records, _ = _mechanically_replay_open_run(run_dir=run_dir,
        repo_root=data_root, require_complete_results=True)
    return _render_verified_text_records(data_root=data_root, manifest=manifest, records=records)


def _render_verified_text_records(*, data_root, manifest, records):
    _need(manifest["requirement_id"] == "issue_28_v12"
          and manifest["run_id"].startswith("run:normal-current:"),
          "NORMAL_TEXT_PROJECTION_CURRENT_RUN_REQUIRED")
    key = manifest["run_id"].split("run:normal-current:", 1)[1]
    binding = strict_json_file(path=resolve_repository_file(repo_root=data_root,
        repo_relative_path="normal_current_bindings/" + key + ".json"))
    _need(content_hash(value=binding) == "sha256:" + key,
          "NORMAL_TEXT_PROJECTION_INPUT_BINDING_CHANGED")
    results = [r for r in records if r["record_type"] == "METRIC_RESULT"]
    _need(len(results) == 1 and results[0]["metric_id"] in {"D01", "C02", "D02"}
          and results[0].get("value_kind") == "TEXT_V1"
          and results[0]["publication"] == "PUBLISHED",
          "NORMAL_TEXT_PROJECTION_ACCEPTED_RESULT_REQUIRED")
    result = results[0]
    metric = result["metric_id"]
    prepared = binding["input_binding"] if metric == "D01" else binding["input_binding"]["prepared_input"]
    annual = prepared["filing"]
    filings = ({r["source_reference_id"]: annual for r in manifest["source_references"]
                if r["source_role"] == "target_primary"} if metric == "D01"
               else binding["input_binding"]["source_filings"])
    spec = compile_spec_file(path=resolve_repository_file(repo_root=data_root,
        repo_relative_path=binding["spec_path"]), dependency_specs={})
    policy_path = resolve_repository_file(repo_root=ROOT, repo_relative_path=POLICY_PATH)
    policy = strict_json_file(path=policy_path)
    _need(policy["record_type"] == "NORMAL_CANDIDATE_PRESENTATION_POLICY"
          and policy["schema_version"] == 2 and policy["production_authorized"] is False
          and set(policy["metrics"]) == {"D01", "C02", "D02"},
          "NORMAL_TEXT_PRESENTATION_POLICY_INVALID")
    presentation = policy["metrics"][metric]
    _need(presentation["status_exact"] == "TEXT_QUAL" and presentation["unit"] == "text"
          and "value_multiplier" not in presentation, "NORMAL_TEXT_PRESENTATION_TYPE_CHANGED")
    companies = [r for r in projector._load_registry(repo_root=data_root)
                 if r["company_id"] == manifest["company_id"]]
    _need(len(companies) == 1, "NORMAL_TEXT_PROJECTION_COMPANY_NOT_UNIQUE")
    indexes = projector._record_indexes(runs=[(manifest, records)])
    trace = indexes["traces"][result["trace_id"]]
    sources = []
    for oid in trace["input_observation_ids"]:
        sid = indexes["observations"][oid]["source_binding"]["source_reference_id"]
        _need(sid in filings, "NORMAL_TEXT_PROJECTION_SOURCE_FILING_MISSING")
        if sid not in sources:
            sources.append(sid)
    source_filings = [filings[sid] for sid in sources]
    _need(source_filings, "NORMAL_TEXT_PROJECTION_DISCLOSURE_SOURCE_REQUIRED")
    # No executed Spec is changed. The receipt binds this separate view.
    view = {"compiled": {"name": spec["compiled"]["name"],
        "reported_unit": spec["compiled"]["reported_unit"], "legacy_projection": presentation}}
    baseline = {field: "" for field in publication.METRIC_FIELDS}
    baseline.update(form=annual["form"], filed_date=annual["filingDate"])
    row, evidence, count = projector._project_result(result=result, trace=trace,
        company=companies[0], spec=view, baseline_row=baseline, indexes=indexes,
        fiscal_year=str(manifest["target_period"]["fiscal_year"]), metric_fields=publication.METRIC_FIELDS)
    _need(count == len(result["text_payload"]["items"]) == len(evidence)
          and row["value"] == result["value"]
          and {e["accession"] for e in evidence} == {f["accessionNumber"] for f in source_filings},
          "NORMAL_TEXT_PUBLIC_EVIDENCE_SET_CHANGED")
    row.update(accession=";".join(f["accessionNumber"] for f in source_filings),
        form=";".join(dict.fromkeys(f["form"] for f in source_filings)),
        filed_date=";".join(f["filingDate"] for f in source_filings),
        concept_or_section=presentation["concept_or_section"],
        context_or_dimension=presentation["context_or_dimension"])
    if metric == "C02":
        row["source_class"] = "PROXY" if all(f["form"] == "DEF 14A" for f in source_filings) else "TEXT"
    if prepared["amendments"]:
        row["notes"] += " Later amendments are retained in the input decision; this is not a verified latest disclosure claim."
    _need(set(row) == set(publication.METRIC_FIELDS)
          and all(set(e) == set(publication.EVIDENCE_FIELDS) for e in evidence),
          "NORMAL_TEXT_PUBLIC_SCHEMA_CHANGED")
    receipt = {"record_type": "NORMAL_CANDIDATE_PUBLIC_ROW_RECEIPT", "status": "CANDIDATE_ONLY",
        "run_id": manifest["run_id"], "run_status": manifest["status"], "result_id": result["result_id"],
        "spec_closure_hash": spec["spec_closure_hash"], "input_binding_id": "sha256:" + key,
        "presentation_policy_sha256": sha256_file(path=policy_path),
        "renderer_sha256": sha256_file(path=Path(__file__)),
        "row_hash": content_hash(value=row), "evidence_hash": content_hash(value=evidence),
        "input_source_reference_ids": [r["source_reference_id"] for r in manifest["source_references"]],
        "contributing_source_filings": source_filings,
        "annual_grouping_period": prepared["table_input"]["target_period"],
        "as_filed_update_status": prepared["update_status"], "production_authorized": False}
    return {"row": row, "evidence": evidence,
        "receipt": {**receipt, "receipt_id": content_hash(value=receipt)},
        "files": {"metrics_matrix.csv": publication._csv_bytes(rows=[row], fieldnames=publication.METRIC_FIELDS),
                  "metric_evidence.csv": publication._csv_bytes(rows=evidence, fieldnames=publication.EVIDENCE_FIELDS)}}
