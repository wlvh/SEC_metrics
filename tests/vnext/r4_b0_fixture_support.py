"""Complete-file synthetic A03 fixture; never business/reference evidence."""

import json
from pathlib import Path

from tests.vnext.common import cell_locator
from vnext.reader import validate_reader_output
from vnext.reader_input import build_reader_input_manifest, build_reader_payload
from vnext.requirements import load_requirement_snapshot
from vnext.sources import raw_blob_record, source_reference_record
from vnext.source_scope import build_source_scope_manifest
from vnext.table_grid import build_table_grid
from vnext.table_task_contracts import resolve_table_task_contract


REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_PATH = "tests/fixtures/vnext/r4_offline/b0_source.html"


def b0_fixture():
    """Create real source/asset/task/Candidate/Evidence objects without sockets."""
    raw = raw_blob_record(repo_root=REPO_ROOT, repo_relative_path=SOURCE_PATH,
                          media_type="text/html")
    source = source_reference_record(
        raw_blob=raw, company_id="synthetic_r4_issuer",
        source_url="https://www.sec.gov/Archives/edgar/data/123/000000012326000001/test.htm",
        accession="0000000123-26-000001", document_name="test.htm",
        source_role="target_primary", request_attempt_id="sha256:" + "e" * 64,
    )
    asset = build_table_grid(
        html_bytes=(REPO_ROOT / SOURCE_PATH).read_bytes(),
        parent_raw_asset_ids=[raw["raw_asset_id"]], storage_uri="offline://b0/full-grid",
    )
    manifest = build_reader_input_manifest(
        derived_asset=asset, source_reference_ids=[source["source_reference_id"]],
    )
    task = resolve_table_task_contract(
        repo_root=REPO_ROOT,
        task_contract_id="financial_liquidity_coverage_ratio_table_v1",
    )
    payload = build_reader_payload(manifest=manifest, derived_asset=asset, task_contract=task)
    locator = cell_locator(asset=asset, table_id="table_000002", row_index=1, column_index=1)
    response = {
        "disclosure_group": task["disclosure_group"],
        "table_locator": {"derived_asset_id": asset["derived_asset_id"], "table_id": "table_000002"},
        "candidates": [{
            "role": task["required_roles"][0], "claimed_period": "FY2025",
            "claimed_raw_value": "111%", "claimed_reported_unit": "percent",
            "claimed_scope": [
                {"dimension": "entity_scope", "raw_value": "Firm", "evidence_locator_ids": ["scope"]},
                {"dimension": "aggregation", "raw_value": "average", "evidence_locator_ids": ["scope"]},
            ],
            "locator": locator,
            "scope_evidence_locators": [{
                "id": "scope", "location_type": "caption", "raw_text": "Firm average",
                "supports_dimensions": ["entity_scope", "aggregation"],
                "locator": {"derived_asset_id": asset["derived_asset_id"], "table_id": "table_000002"},
            }],
            "competing_candidates": [],
        }],
        "unresolved_competing_claims": [],
    }
    response_text = json.dumps(response)
    candidate = validate_reader_output(
        response_text=response_text, attempt_id="attempt:b0:synthetic",
        required_roles=task["required_roles"], scope_contract=task["scope_contract"],
        source_reference_ids=[source["source_reference_id"]],
        derived_asset_ids=[asset["derived_asset_id"]],
    )
    requirement = load_requirement_snapshot(snapshot_dir=REPO_ROOT / "requirements/issue_28_v1")
    audit = {
        "fixture_id": "b0_synthetic_a03", "fixture_class": "POSITIVE_PRODUCTION",
        "windows": [{"start_order": 1, "end_order": 1}],
        "target_locator": locator,
        "reference": {"status": "SYNTHETIC_INTERFACE_REFERENCE", "value": "1.11", "unit": "ratio"},
        "synthetic_candidate": candidate, "out_of_window_candidates": [],
        "table_audit": [{
            "table_id": t["table_id"], "grid_sha256": t["grid_sha256"],
            "disposition": "TARGET" if t["order"] == 1 else "NO_TARGET_CANDIDATE",
            "evidence": "Complete synthetic table inventory; not a real filing audit",
        } for t in asset["tables"]],
        "material_layout_proof": {"kind": "SYNTHETIC_INTERFACE_ONLY"},
        "navigation_paths": [
            {"path_id": "A", "method": "SYNTHETIC_SECTION_ANCHOR"},
            {"path_id": "B", "method": "SYNTHETIC_REVERSE_VALUE_TRACE"},
        ],
    }
    authority = {
        "requirement": requirement, "raw_blob": raw, "source_reference": source,
        "full_derived_asset": asset, "reader_manifest": manifest,
        "task_contract": task, "evidence_authority_payload": payload["body"],
    }
    scope = build_source_scope_manifest(audit=audit, **authority)
    return {"authority": authority, "audit": audit, "scope": scope,
            "response_text": response_text, "response": response}
