"""Offline source-backed regression for the bounded label repair; no Run credit."""
import copy
from pathlib import Path
from .canonical import content_hash, sha256_file, strict_json_file, strict_json_loads
from .reader import validate_reader_output
from .annual_evidence import check_annual_evidence
from .requirements import load_requirement_snapshot
from .requirement_profile_v7 import REQUIREMENT_ID

AUDIT = "docs/evidence/annual_runtime/live/native-candidate/b10"
CASE_NAMES = [
    "original_raw_rule",
    "original_new_rule",
    "existing_correct_label",
    "wrong_numeric_value",
    "wrong_unit",
    "wrong_claim_period",
    "wrong_period_column",
    "wrong_table",
    "wrong_origin_geometry",
    "wrong_scope_footnote",
    "unknown_scope_alias",
    "wrong_operating_scope",
    "different_row_same_label",
    "wrong_region_value",
    "same_numeric_value_wrong_group",
    "caller_added_whitespace",
    "conflicting_claims",
    "wrong_source_identity",
]
CODE_FILES = [
    "scripts/vnext/annual_evidence.py",
    "scripts/vnext/annual_regression.py",
    "scripts/vnext/evidence.py",
    "scripts/vnext/reader.py",
    "scripts/vnext/table_grid.py",
    "scripts/vnext/scope_contract.py",
]


def _fixture(repo_root):
    run = repo_root / AUDIT
    audit = strict_json_file(
        path=repo_root / "docs/evidence/annual_runtime/live/live-native-manifest.json"
    )
    expected = audit["files"]["b10/records.jsonl"]
    if sha256_file(path=run / "records.jsonl") != expected["sha256"]:
        raise ValueError("REGRESSION_ORIGINAL_RECORDS_CHANGED")
    records = [
        strict_json_loads(text=l)
        for l in (run / "records.jsonl").read_text().splitlines()
    ]
    attempt = next(r for r in records if r["record_type"] == "AI_EXTRACTION_ATTEMPT")
    response = run / attempt["assistant_output_path"]
    if sha256_file(path=response) != attempt["assistant_output_sha256"]:
        raise ValueError("REGRESSION_ORIGINAL_RESPONSE_CHANGED")
    return (
        records,
        attempt,
        response,
        strict_json_file(path=run / attempt["reader_payload_path"]),
    )


def build_regression_receipt(*, repo_root):
    """Re-evaluate unmodified original bytes and deliberate error counterexamples."""
    records, attempt, response, payload = _fixture(repo_root)
    grid = next(r for r in records if r["record_type"] == "DERIVED_ASSET")
    manifest = next(r for r in records if r["record_type"] == "READER_INPUT_MANIFEST")
    sources = [r for r in records if r["record_type"] == "SOURCE_REFERENCE"]
    task = payload["task_contract"]
    period = strict_json_file(path=repo_root / AUDIT / "manifest.json")["target_period"]
    requirement = load_requirement_snapshot(
        snapshot_dir=repo_root / "requirements" / REQUIREMENT_ID
    )
    old = load_requirement_snapshot(snapshot_dir=repo_root / "requirements/issue_28_v5")
    original = strict_json_file(path=response)
    cases = []

    def evaluate(
        name, body, *, old_rule=False, source_override=None, expected="REJECTED"
    ):
        try:
            candidate = validate_reader_output(
                response_text=body
                if isinstance(body, str)
                else __import__("json").dumps(body),
                attempt_id=attempt["attempt_id"],
                required_roles=task["required_roles"],
                scope_contract=task["scope_contract"],
                source_reference_ids=manifest["source_reference_ids"],
                derived_asset_ids=[grid["derived_asset_id"]],
            )
            evidence = check_annual_evidence(
                requirement=old if old_rule else requirement,
                target_period=period,
                candidate=candidate,
                derived_asset=grid,
                reader_manifest=manifest,
                reader_payload_body=payload,
                source_references=sources
                if source_override is None
                else source_override,
                identity_constraints=task["identity_constraints"],
                scope_contract=task["scope_contract"],
            )
            observed = evidence["status"]
            reasons = evidence["reason_codes"]
        except ValueError as error:
            observed = "REJECTED"
            reasons = [str(error)]
        cases.append(
            {
                "case": name,
                "expected": expected,
                "observed": observed,
                "reason_codes": reasons,
            }
        )

    # The repair acceptance case is the original response, byte-for-byte.
    evaluate("original_raw_rule", response.read_text(), old_rule=True)
    evaluate("original_new_rule", response.read_text(), expected="PASS")
    historical = (
        repo_root
        / "artifacts/vnext/qualification/cycles/0c4569437b1bac3ad353394c8d8b1f59b1a1ee7c229c8fa5ee51a22269b6a448/runs/0799ec7f91b6bc0472fd80c6c655beb90ddd7db583dcd13cae0bfab506e6412c"
    )
    hrs = [
        strict_json_loads(text=l)
        for l in (historical / "records.jsonl").read_text().splitlines()
    ]
    ha = next(r for r in hrs if r["record_type"] == "AI_EXTRACTION_ATTEMPT")
    hresponse = historical / ha["assistant_output_path"]
    if sha256_file(path=hresponse) != ha["assistant_output_sha256"]:
        raise ValueError("REGRESSION_HISTORICAL_RESPONSE_CHANGED")
    evaluate("existing_correct_label", hresponse.read_text(), expected="PASS")
    table = next(
        t
        for t in grid["tables"]
        if t["table_id"] == original["candidates"][0]["locator"]["table_id"]
    )

    def cell(row, col):
        return next(c for c in table["rows"][row]["cells"] if c["column_index"] == col)

    def locator(row, col):
        c = cell(row, col)
        return {
            "derived_asset_id": grid["derived_asset_id"],
            "table_id": table["table_id"],
            **{
                k: c[k]
                for k in (
                    "row_index",
                    "column_index",
                    "origin_row_index",
                    "origin_column_index",
                    "rowspan",
                    "colspan",
                )
            },
        }

    def mutate(name, fn):
        b = copy.deepcopy(original)
        fn(b, b["candidates"][0])
        evaluate(name, b)

    mutate("wrong_numeric_value", lambda b, c: c.update(claimed_raw_value="0"))
    mutate("wrong_unit", lambda b, c: c.update(claimed_reported_unit="ratio"))
    mutate(
        "wrong_claim_period",
        lambda b, c: c.update(claimed_period="FY" + str(period["fiscal_year"] - 1)),
    )
    mutate(
        "wrong_period_column",
        lambda b, c: c.update(
            locator=locator(26, 21), claimed_raw_value=cell(26, 21)["text"]
        ),
    )
    mutate(
        "wrong_table",
        lambda b, c: c["locator"].update(table_id=grid["tables"][0]["table_id"]),
    )
    mutate(
        "wrong_origin_geometry", lambda b, c: c["locator"].update(origin_row_index=0)
    )
    mutate(
        "wrong_scope_footnote",
        lambda b, c: c["scope_evidence_locators"][1].update(raw_text="Worldwide (3)"),
    )
    mutate(
        "unknown_scope_alias",
        lambda b, c: c["claimed_scope"][2].update(raw_value="Worldwide (2)"),
    )
    mutate(
        "wrong_operating_scope",
        lambda b, c: c["claimed_scope"][1].update(raw_value="Company-operated"),
    )
    mutate(
        "different_row_same_label",
        lambda b, c: c["scope_evidence_locators"][1].update(locator=locator(17, 0)),
    )
    mutate(
        "wrong_region_value",
        lambda b, c: c.update(
            locator=locator(19, 15), claimed_raw_value=cell(19, 15)["text"]
        ),
    )

    def wrong_group(b, c):
        c.update(locator=locator(17, 15), claimed_raw_value=cell(17, 15)["text"])
        c["scope_evidence_locators"][1]["locator"] = locator(17, 0)

    mutate("same_numeric_value_wrong_group", wrong_group)
    mutate(
        "caller_added_whitespace",
        lambda b, c: c["scope_evidence_locators"][1].update(raw_text="Worldwide  (2)"),
    )
    mutate(
        "conflicting_claims",
        lambda b, c: b.update(
            unresolved_competing_claims=[{"description": "scope conflict"}]
        ),
    )
    evaluate("wrong_source_identity", original, source_override=[])
    if [c["case"] for c in cases] != CASE_NAMES:
        raise ValueError("REGRESSION_CASE_SET_INVALID")
    body = {
        "record_type": "ANNUAL_REPAIR_REGRESSION",
        "schema_version": 1,
        "requirement_id": REQUIREMENT_ID,
        "status": "PASS"
        if all(c["observed"] == c["expected"] for c in cases)
        else "FAIL",
        "evidence_scope": "OFFLINE_UNMODIFIED_ORIGINAL_RESPONSE_AND_NEGATIVES_NO_RUN_CREDIT",
        "original_response_sha256": sha256_file(path=response),
        "original_records_sha256": sha256_file(
            path=repo_root / AUDIT / "records.jsonl"
        ),
        "historical_correct_response_sha256": sha256_file(path=hresponse),
        "code_files": {s: sha256_file(path=repo_root / s) for s in CODE_FILES},
        "cases": cases,
        "additional_provider_paid_sec_calls": [0, 0, 0],
    }
    return {**body, "receipt_id": content_hash(value=body)}


def verify_regression_receipt(receipt):
    """Recheck the exact signed regression/corpus/code identity, without model calls."""
    root = Path(__file__).resolve().parents[2]
    if (
        receipt.get("receipt_id")
        != content_hash(value={k: v for k, v in receipt.items() if k != "receipt_id"})
        or receipt.get("status") != "PASS"
        or receipt.get("requirement_id") != REQUIREMENT_ID
        or [c["case"] for c in receipt["cases"]] != CASE_NAMES
        or any(c["expected"] != c["observed"] for c in receipt["cases"])
        or receipt["code_files"] != {s: sha256_file(path=root / s) for s in CODE_FILES}
    ):
        raise ValueError("REPAIR_REGRESSION_STALE_OR_FAILED")
    _, _, response, _ = _fixture(root)
    if receipt["original_response_sha256"] != sha256_file(path=response) or receipt[
        "original_records_sha256"
    ] != sha256_file(path=root / AUDIT / "records.jsonl"):
        raise ValueError("REPAIR_REGRESSION_SOURCE_CHANGED")
