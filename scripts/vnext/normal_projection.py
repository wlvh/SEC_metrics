"""Render a frozen normal candidate through the existing public row machinery.

Presentation is separately bound; the executed MetricSpec is never rewritten.
This component prepares rows and evidence, without a publication or pointer.
"""
from pathlib import Path

from . import projector, publication
from .canonical import content_hash, sha256_file, strict_json_file
from .normal_source_authority import ROOT
from .run_store import load_frozen_run
from .sources import resolve_repository_file
from .specs import compile_spec_file
from .text_run_validation import D01_SPEC_PATH


POLICY_PATH = "config/normal_public_projection_v1.json"


def _need(condition, reason):
    if not condition:
        raise ValueError(reason)


def render_normal_text_run(*, data_root: Path, run_dir: Path):
    """Read one verified D01 Run and produce the exact existing CSV schemas."""
    manifest, records, _ = load_frozen_run(run_dir=run_dir, repo_root=data_root)
    _need(manifest["requirement_id"] == "issue_28_v11"
          and manifest["run_id"].startswith("run:normal-saved:"),
          "NORMAL_PROJECTION_RUN_AUTHORITY_REQUIRED")
    key = manifest["run_id"].split("run:normal-saved:", 1)[1]
    binding = strict_json_file(path=resolve_repository_file(repo_root=data_root,
        repo_relative_path="normal_bindings/" + key + ".json"))
    _need(content_hash(value=binding) == "sha256:" + key,
          "NORMAL_PROJECTION_INPUT_BINDING_CHANGED")
    results = [r for r in records if r["record_type"] == "METRIC_RESULT"]
    _need(len(results) == 1 and results[0]["metric_id"] == "D01"
          and results[0].get("value_kind") == "TEXT_V1"
          and results[0]["publication"] == "PUBLISHED",
          "NORMAL_PROJECTION_ACCEPTED_TEXT_RESULT_REQUIRED")
    result = results[0]
    prepared = binding["prepared_input"]
    filing = prepared["filing"]
    spec = compile_spec_file(path=data_root / D01_SPEC_PATH, dependency_specs={})
    policy_path = resolve_repository_file(repo_root=ROOT, repo_relative_path=POLICY_PATH)
    policy = strict_json_file(path=policy_path)
    _need(policy["record_type"] == "NORMAL_CANDIDATE_PRESENTATION_POLICY"
          and policy["schema_version"] == 1 and policy["production_authorized"] is False
          and set(policy["metrics"]) == {"D01"}, "NORMAL_PRESENTATION_POLICY_INVALID")
    presentation = policy["metrics"]["D01"]
    _need(presentation["status_exact"] == "TEXT_QUAL" and presentation["unit"] == "text"
          and "value_multiplier" not in presentation, "NORMAL_TEXT_PRESENTATION_TYPE_CHANGED")
    companies = [r for r in projector._load_registry(repo_root=data_root)
                 if r["company_id"] == manifest["company_id"]]
    _need(len(companies) == 1, "NORMAL_PROJECTION_COMPANY_NOT_UNIQUE")
    indexes = projector._record_indexes(runs=[(manifest, records)])
    # This is deliberately a presentation view, without any Spec hash fields.
    # The true compiled Spec and independent policy identities are in receipt.
    view = {"compiled": {"name": spec["compiled"]["name"],
                        "reported_unit": spec["compiled"]["reported_unit"],
                        "legacy_projection": presentation}}
    baseline = {field: "" for field in publication.METRIC_FIELDS}
    baseline.update(form=filing["form"], filed_date=filing["filingDate"])
    row, evidence, count = projector._project_result(result=result,
        trace=indexes["traces"][result["trace_id"]], company=companies[0], spec=view,
        baseline_row=baseline, indexes=indexes,
        fiscal_year=str(manifest["target_period"]["fiscal_year"]),
        metric_fields=publication.METRIC_FIELDS)
    _need(count == len(result["text_payload"]["items"]) == len(evidence)
          and row["value"] == result["value"]
          and all(e["accession"] == filing["accessionNumber"] for e in evidence),
          "NORMAL_TEXT_PUBLIC_EVIDENCE_SET_CHANGED")
    # One filing and section should not be repeated once for every heading.
    row.update(accession=filing["accessionNumber"],
               concept_or_section=presentation["concept_or_section"],
               context_or_dimension=presentation["context_or_dimension"])
    if prepared["amendments"]:
        row["notes"] += " Later amendments require a separate current-period scope check."
    _need(set(row) == set(publication.METRIC_FIELDS)
          and all(set(r) == set(publication.EVIDENCE_FIELDS) for r in evidence),
          "NORMAL_PUBLIC_ROW_SCHEMA_CHANGED")
    receipt = {"record_type": "NORMAL_CANDIDATE_PUBLIC_ROW_RECEIPT",
        "status": "CANDIDATE_ONLY", "run_id": manifest["run_id"],
        "run_status": manifest["status"], "result_id": result["result_id"],
        "spec_closure_hash": spec["spec_closure_hash"],
        "presentation_policy_sha256": sha256_file(path=policy_path),
        "input_binding_id": "sha256:" + key, "row_hash": content_hash(value=row),
        "evidence_hash": content_hash(value=evidence),
        "input_source_reference_ids": [r["source_reference_id"] for r in manifest["source_references"]],
        "as_filed_update_status": prepared["update_status"],
        "production_authorized": False}
    return {"row": row, "evidence": evidence,
        "receipt": {**receipt, "receipt_id": content_hash(value=receipt)},
        "files": {"metrics_matrix.csv": publication._csv_bytes(rows=[row], fieldnames=publication.METRIC_FIELDS),
                  "metric_evidence.csv": publication._csv_bytes(rows=evidence, fieldnames=publication.EVIDENCE_FIELDS)}}
