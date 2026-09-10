"""Read-only source audit using native records and the existing Evidence Checker.

Coordinates in an audit recipe are source-specific review inputs, not a runtime
selector. This module neither guesses windows nor sends requests. A successful
Evidence check alone is not a reconciled fixture or qualification credit.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping, Sequence
from urllib.parse import urlsplit

from sec_http import parse_request_log_rows, request_log_attempt_id
from sec_http import validate_request_log_manifest

from .batch_workflow import BatchWorkflowError, request_attempt_binding
from .canonical import content_hash, sha256_file
from .evidence import _bounded_raw_value_match, check_evidence
from .reader import validate_reader_output
from .reader_input import build_reader_input_manifest, build_reader_payload
from .records import validate_record
from .sources import raw_blob_record, resolve_repository_file
from .sources import source_reference_record
from .table_grid import _AllTablesParser, resolve_cell
from .table_task_contracts import resolve_table_task_contract


class R4SourceAuditError(ValueError):
    """Fail an offline audit when immutable source or native identities drift."""


def _ledger(*, repo_root: Path) -> list:
    path = repo_root / "evidence/requests_log.csv"
    validate_request_log_manifest(log_path=path)
    return parse_request_log_rows(text=path.read_text(encoding="utf-8"))


def inventory_immutable_sources(*, repo_root: Path,
                                issuer_ciks: Sequence[str]) -> dict:
    """Inventory existing bytes only; absence cannot trigger network activity."""
    if (not issuer_ciks or len(set(issuer_ciks)) != len(issuer_ciks)
            or any(not value.isdecimal() for value in issuer_ciks)):
        raise R4SourceAuditError("Inventory CIK set is invalid")
    rows = _ledger(repo_root=repo_root)
    issuers = []
    for cik in issuer_ciks:
        matched = []
        for index, row in enumerate(rows):
            path_parts = urlsplit(row["source_url"]).path.split("/")
            if len(path_parts) < 5 or path_parts[1:4] != ["Archives", "edgar", "data"]:
                continue
            if path_parts[4] != cik:
                continue
            matched.append((index, row))
        observations = []
        for index, row in matched:
            relative = row["repo_relative_path"]
            if (row["status_code"] != "200"
                    or not relative.startswith("evidence/request_attempts/")
                    or not row["document_name"].endswith((".htm", ".html", ".xml"))):
                continue
            path = resolve_repository_file(repo_root=repo_root,
                                           repo_relative_path=relative)
            if (sha256_file(path=path) != row["content_sha256"]
                    or path.stat().st_size != int(row["content_length"])):
                raise R4SourceAuditError("Immutable source bytes differ from ledger")
            observations.append({
                "request_attempt_id": request_log_attempt_id(row_index=index, row=row),
                "source_url": row["source_url"], "accession": row["accession"],
                "document_name": row["document_name"],
                "source_repo_relative_path": relative,
                "source_sha256": row["content_sha256"],
                "source_size": path.stat().st_size,
            })
        issuers.append({"cik": cik, "ledger_rows": len(matched),
                        "immutable_sources": observations})
    body = {"record_type": "R4_OFFLINE_SOURCE_INVENTORY", "schema_version": 1,
            "issuer_inventory": issuers, "request_ledger_rows": len(rows),
            "request_ledger_sha256": sha256_file(path=repo_root / "evidence/requests_log.csv"),
            "provider_paid_sec_calls": [0, 0, 0],
            "qualification_credit": "NONE_OFFLINE_AUDIT"}
    return {**body, "inventory_id": content_hash(value=body)}


def source_authority(*, repo_root: Path, declaration: Mapping) -> dict:
    """Resolve an exact committed immutable attempt, never a working mirror."""
    relative = declaration["source_repo_relative_path"]
    if not relative.startswith("evidence/request_attempts/"):
        raise R4SourceAuditError("Audit source is not an immutable request attempt")
    path = resolve_repository_file(repo_root=repo_root, repo_relative_path=relative)
    if (sha256_file(path=path) != declaration["source_sha256"]
            or path.stat().st_size != declaration["source_size"]):
        raise R4SourceAuditError("Declared source identity differs")
    try:
        binding = request_attempt_binding(
            repo_root=repo_root, source_url=declaration["source_url"],
            content_sha256=declaration["source_sha256"],
            accession=declaration["accession"],
            document_name=declaration["document_name"])
    except BatchWorkflowError as error:
        raise R4SourceAuditError("Native immutable attempt verification failed: " + str(error)) from error
    if (binding["request_locator_kind"] != "IMMUTABLE_ATTEMPT"
            or binding["request_repo_relative_path"] != relative):
        raise R4SourceAuditError("Native attempt locator differs from audit source")
    raw = raw_blob_record(repo_root=repo_root, repo_relative_path=relative,
                          media_type=declaration["media_type"])
    reference = source_reference_record(
        raw_blob=raw, company_id=declaration["company_id"],
        source_url=declaration["source_url"], accession=declaration["accession"],
        document_name=declaration["document_name"], source_role="target_primary",
        request_attempt_id=binding["request_attempt_id"],
    )
    return {"raw_blob": raw, "source_reference": reference,
            "source_bytes": path.read_bytes()}


def audit_scope_alias_coverage(*, repo_root: Path, declaration: Mapping,
                              task_contract_id: str) -> dict:
    """Exhaustively inventory existing raw-label support; never certify meaning.

    Raw cells include every native origin label before merged-cell expansion.
    Expansion cannot create missing scope text. This is diagnostic coverage,
    not a second Evidence verifier or permission to borrow neighboring prose.
    """
    source = source_authority(repo_root=repo_root, declaration=declaration)
    task = resolve_table_task_contract(repo_root=repo_root,
                                       task_contract_id=task_contract_id)
    parser = _AllTablesParser()
    parser.feed(source["source_bytes"].decode("utf-8"))
    parser.close()
    aliases = task["scope_contract"]["exact_enum_aliases"]
    matches = []
    for table in parser.tables:
        labels = [(-1, -1, "".join(table.caption_parts))] + [
            (row_index, cell_index, "".join(cell.raw_parts))
            for row_index, row in enumerate(table.rows)
            for cell_index, cell in enumerate(row)
        ]
        found = {}
        for dimension, values in aliases.items():
            occurrences = [
                {"row_index": row_index, "raw_cell_ordinal": ordinal,
                 "raw_value": alias, "raw_text": raw_text}
                for row_index, ordinal, raw_text in labels
                for enum_aliases in values.values() for alias in enum_aliases
                if _bounded_raw_value_match(raw_text=raw_text, raw_value=alias)
            ]
            if occurrences:
                found[dimension] = occurrences
        if found:
            matches.append({"table_id": "table_{:06d}".format(table.order + 1),
                            "scope_aliases": found})
    required = set(task["scope_contract"]["required_dimensions"])
    body = {
        "record_type": "R4_RAW_SCOPE_ALIAS_COVERAGE", "schema_version": 1,
        "source_sha256": declaration["source_sha256"],
        "task_contract_id": task["task_contract_id"],
        "task_contract_hash": task["catalog_task_contract_hash"],
        "table_count": len(parser.tables), "exact_enum_aliases": aliases,
        "any_alias_tables": matches,
        "complete_scope_tables": [row["table_id"] for row in matches
                                   if required.issubset(row["scope_aliases"])],
        "qualification_credit": "NONE_OFFLINE_AUDIT",
        "provider_paid_sec_calls": [0, 0, 0],
    }
    return {**body, "coverage_id": content_hash(value=body)}


def cell_locator(*, asset: Mapping, table_order: int,
                 row_index: int, column_index: int) -> dict:
    table = asset["tables"][table_order]
    cell = table["rows"][row_index]["cells"][column_index]
    return {"derived_asset_id": asset["derived_asset_id"],
            "table_id": table["table_id"], "row_index": row_index,
            "column_index": column_index,
            **{key: cell[key] for key in ("origin_row_index", "origin_column_index",
                                         "rowspan", "colspan")}}


def _native_probe(*, asset: Mapping, source: Mapping,
                  task: Mapping, recipe: Mapping, unit: str) -> dict:
    target = cell_locator(asset=asset, **recipe["target"])
    target_cell = resolve_cell(derived_asset=asset, locator=target)
    labels, claims = [], []
    for label in recipe["scope_labels"]:
        locator = cell_locator(asset=asset, **label["coordinate"])
        cell = resolve_cell(derived_asset=asset, locator=locator)
        labels.append({"id": label["id"], "location_type": "label",
                       "raw_text": cell["raw_text"], "locator": locator,
                       "supports_dimensions": list(label["claims"])})
        claims.extend({"dimension": dimension, "raw_value": value,
                       "evidence_locator_ids": [label["id"]]}
                      for dimension, value in label["claims"].items())
    response = {
        "disclosure_group": task["disclosure_group"],
        "table_locator": {"derived_asset_id": asset["derived_asset_id"],
                          "table_id": target["table_id"]},
        "candidates": [{"role": task["required_roles"][0],
                        "claimed_period": recipe["claimed_period"],
                        "claimed_raw_value": target_cell["text"],
                        "claimed_reported_unit": unit,
                        "claimed_scope": claims, "locator": target,
                        "scope_evidence_locators": labels,
                        "competing_candidates": []}],
        "unresolved_competing_claims": [],
    }
    manifest = build_reader_input_manifest(
        derived_asset=asset,
        source_reference_ids=[source["source_reference"]["source_reference_id"]])
    payload = build_reader_payload(manifest=manifest, derived_asset=asset,
                                   task_contract=task)
    candidate = validate_reader_output(
        response_text=json.dumps(response),
        attempt_id="offline-synthetic:" + content_hash(value=response)[7:],
        required_roles=task["required_roles"], scope_contract=task["scope_contract"],
        source_reference_ids=manifest["source_reference_ids"],
        derived_asset_ids=[asset["derived_asset_id"]],
    )
    evidence = check_evidence(
        candidate=candidate, derived_asset=asset, reader_manifest=manifest,
        reader_payload_body=payload["body"],
        source_references=[source["source_reference"]],
        identity_constraints=task["identity_constraints"],
        scope_contract=task["scope_contract"],
    )
    headers = []
    for coordinate in recipe["header_coordinates"]:
        locator = cell_locator(asset=asset, **coordinate)
        cell = resolve_cell(derived_asset=asset, locator=locator)
        headers.append({"locator": locator, "raw_text": cell["raw_text"],
                        "text": cell["text"]})
    return {"reported_unit": unit, "target_locator": target,
            "target_raw_text": target_cell["raw_text"],
            "target_text": target_cell["text"], "headers": headers,
            "response": response, "candidate": candidate, "evidence": evidence}


def probe_native_candidates(*, repo_root: Path, recipe: Mapping,
                            full_derived_asset: Mapping) -> dict:
    """Run exact source-cell probes, preserving native failures and values.

    This deliberately does not repair missing scale/scope or turn reviewed-only
    Evidence into a positive fixture. The full asset is built by the separately
    hard-guarded materializer before this function is called.
    """
    source = source_authority(repo_root=repo_root, declaration=recipe["source"])
    validate_record(record=full_derived_asset)
    if full_derived_asset["parent_raw_asset_ids"] != [source["raw_blob"]["raw_asset_id"]]:
        raise R4SourceAuditError("Full DerivedAsset belongs to another source")
    parser = _AllTablesParser()
    parser.feed(source["source_bytes"].decode("utf-8"))
    parser.close()
    if len(parser.tables) != len(full_derived_asset["tables"]):
        raise R4SourceAuditError("Full source table census differs")
    outcomes = []
    for probe in recipe["probes"]:
        task = resolve_table_task_contract(repo_root=repo_root,
                                           task_contract_id=probe["task_contract_id"])
        if task["metric_ids"] != [probe["metric_id"]]:
            raise R4SourceAuditError("Probe metric/task binding differs")
        variants = [_native_probe(asset=full_derived_asset, source=source, task=task,
                                  recipe=probe, unit=unit)
                    for unit in probe["reported_unit_variants"]]
        outcomes.append({"metric_id": probe["metric_id"],
                         "task_contract_id": task["task_contract_id"],
                         "task_contract_hash": task["catalog_task_contract_hash"],
                         "reference": probe["reference"], "variants": variants})
    body = {"record_type": "R4_NATIVE_SOURCE_PROBE", "schema_version": 1,
            "source": dict(recipe["source"]),
            "request_attempt_id": source["source_reference"]["request_attempt_id"],
            "full_derived_asset_id": full_derived_asset["derived_asset_id"],
            "table_count": len(full_derived_asset["tables"]),
            "expanded_cells": sum(t["row_count"] * t["column_count"]
                                  for t in full_derived_asset["tables"]),
            "outcomes": outcomes, "provider_paid_sec_calls": [0, 0, 0],
            "qualification_credit": "NONE_OFFLINE_AUDIT"}
    return {**body, "probe_id": content_hash(value=body)}
