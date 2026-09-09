"""Small synthetic header graphs; never SEC provenance, Runs, or live credit."""
import copy
import html
import json
from .canonical import sha256_bytes
from .table_grid import build_table_grid
from .sources import source_reference_record
from .reader_input import build_reader_input_manifest, prepare_reader_request
from .reader import validate_reader_output


def header_case(*, repo_root, records, attempt, original, period, variant):
    claim = original["candidates"][0]
    year = period["fiscal_year"]
    role = html.escape(claim["role"].replace("_", " ").title())
    group = html.escape(claim["scope_evidence_locators"][0]["raw_text"])
    geo = html.escape(claim["scope_evidence_locators"][1]["raw_text"])
    value = html.escape(claim["claimed_raw_value"])
    if variant == "same_value_prior_year":
        source = (
            f'<table><tr><td></td><td colspan="4">{role}</td></tr>'
            f'<tr><td></td><td colspan="2">{year}</td><td colspan="2">{year-1}</td></tr>'
            f'<tr><td>{group}</td><td colspan="4"></td></tr>'
            f"<tr><td>{geo}</td><td>{value}</td><td>%</td><td>{value}</td><td>%</td></tr></table>"
        )
        group_row, value_row, value_col = 2, 3, 3
    else:
        extras = {
            "synthetic_supported_header": "",
            "conflicting_year_header": str(year - 1),
            "conflicting_role_header": "Different measure",
            "conflicting_year_with_row_stub": str(year - 1),
        }
        extra = extras[variant]
        source = (
            f"<table><tr><td></td><td>{role}</td><td></td></tr>"
            f"<tr><td></td><td>{year}</td><td></td></tr>"
            + (
                (
                    f"<tr><td>Fiscal year</td><td>{extra}</td><td></td></tr>"
                    if variant == "conflicting_year_with_row_stub"
                    else f'<tr><td colspan="3">{extra}</td></tr>'
                )
                if extra
                else ""
            )
            + f"<tr><td>{group}</td><td></td><td></td></tr>"
            + f"<tr><td>{geo}</td><td>{value}</td><td>%</td></tr></table>"
        )
        group_row = 3 if extra else 2
        value_row = group_row + 1
        value_col = 1
    raw_bytes = source.encode()
    raw = {
        "record_type": "RAW_BLOB",
        "raw_asset_id": "sha256:" + sha256_bytes(content=raw_bytes),
        "byte_length": len(raw_bytes),
        "media_type": "text/html",
        "storage_uri": "evidence/SYNTHETIC-header.html",
    }
    old = next(r for r in records if r["record_type"] == "SOURCE_REFERENCE")
    source = source_reference_record(
        raw_blob=raw,
        **{
            k: old[k]
            for k in (
                "company_id",
                "source_url",
                "accession",
                "document_name",
                "source_role",
                "request_attempt_id",
            )
        },
    )
    grid = build_table_grid(
        html_bytes=raw_bytes,
        parent_raw_asset_ids=[raw["raw_asset_id"]],
        storage_uri="artifacts/SYNTHETIC-header.json",
    )
    table = grid["tables"][0]

    def locator(row, col):
        cell = table["rows"][row]["cells"][col]
        return {
            "derived_asset_id": grid["derived_asset_id"],
            "table_id": table["table_id"],
            **{
                k: cell[k]
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

    body = copy.deepcopy(original)
    body["table_locator"] = {
        "derived_asset_id": grid["derived_asset_id"],
        "table_id": table["table_id"],
    }
    c = body["candidates"][0]
    c["locator"] = locator(value_row, value_col)
    c["scope_evidence_locators"][0]["locator"] = locator(group_row, 0)
    c["scope_evidence_locators"][1]["locator"] = locator(value_row, 0)
    manifest = build_reader_input_manifest(
        derived_asset=grid, source_reference_ids=[source["source_reference_id"]]
    )
    request = prepare_reader_request(
        repo_root=repo_root,
        task_contract_id=attempt["task_contract_id"],
        manifest=manifest,
        derived_asset=grid,
    )
    payload = json.loads(request.request_bytes)
    task = payload["task_contract"]
    candidate = validate_reader_output(
        response_text=json.dumps(body),
        attempt_id=attempt["attempt_id"],
        required_roles=task["required_roles"],
        scope_contract=task["scope_contract"],
        source_reference_ids=[source["source_reference_id"]],
        derived_asset_ids=[grid["derived_asset_id"]],
    )
    return dict(
        candidate=candidate,
        derived_asset=grid,
        reader_manifest=manifest,
        reader_payload_body=payload,
        source_references=[source],
        identity_constraints=task["identity_constraints"],
        scope_contract=task["scope_contract"],
    )
