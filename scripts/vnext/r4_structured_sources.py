"""Owner-pinned single-filing fixture provenance for the native XBRL adapter.

This explicit subtype claims neither a latest filing nor a complete submissions
inventory. Normal source-role/release planners continue to reject it. It only
supports offline inspection of newly acquired immutable fixture bytes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

from .canonical import content_hash, sha256_file, strict_json_file
from .records import validate_record
from .sources import resolve_repository_file


FIXTURE_SET_TYPE = "PINNED_SINGLE_FILING_FIXTURE_SOURCE_SET"
ACQUISITION_PLAN = "config/r4_fixture_acquisitions_v1.json"
ACQUISITION_RECEIPT = "docs/r4_offline/fixture_acquisition_receipt.json"
FIELDS = frozenset({
    "record_type", "schema_version", "source_set_manifest_id", "company_id",
    "source_role", "ordered_source_reference_ids", "source_reference", "raw_blob",
    "source_id", "inline_dei", "acquisition_plan", "acquisition_receipt",
    "selection_scope", "latest_filing_claim", "full_submissions_inventory_claim",
    "qualification_credit", "publication_credit", "provider_paid_sec_authorized",
})


class FixtureSourceSetError(ValueError):
    """Reject a source that is not the exact owner-pinned fresh observation."""


def validate_fixture_source_set(*, manifest: Mapping) -> dict:
    """Validate fixture subtype identity without broadening normal source sets."""
    if (type(manifest) is not dict or set(manifest) != FIELDS
            or manifest["record_type"] != FIXTURE_SET_TYPE
            or type(manifest["schema_version"]) is not int
            or manifest["schema_version"] != 1
            or manifest["selection_scope"] != "OWNER_PINNED_SINGLE_FILING_OFFLINE_ONLY"
            or manifest["latest_filing_claim"] is not False
            or manifest["full_submissions_inventory_claim"] is not False
            or manifest["qualification_credit"] != "NONE_OFFLINE_FIXTURE"
            or manifest["publication_credit"] != "NONE"
            or manifest["provider_paid_sec_authorized"] is not False):
        raise FixtureSourceSetError("Fixture source-set fields or scope differ")
    validate_record(record=manifest["source_reference"])
    validate_record(record=manifest["raw_blob"])
    ref = manifest["source_reference"]
    if (manifest["ordered_source_reference_ids"] != [ref["source_reference_id"]]
            or manifest["raw_blob"]["raw_asset_id"] != ref["raw_asset_id"]
            or manifest["company_id"] != ref["company_id"]
            or manifest["source_role"] != "offline_fixture_accession_xbrl"
            or ref["source_role"] != "target_primary"):
        raise FixtureSourceSetError("Fixture source identity differs")
    dei = manifest["inline_dei"]
    if (type(dei) is not dict or set(dei) != {
            "entity_central_index_key", "document_type", "fiscal_year_focus", "document_period_end",
            "context_period_start", "context_period_end"}
            or dei["document_type"] != "10-K"
            or not dei["entity_central_index_key"].isdecimal()
            or not dei["fiscal_year_focus"].isdecimal()):
        raise FixtureSourceSetError("Fixture inline DEI identity differs")
    for key, path in (("acquisition_plan", ACQUISITION_PLAN),
                      ("acquisition_receipt", ACQUISITION_RECEIPT)):
        binding = manifest[key]
        if (type(binding) is not dict or set(binding) != {"path", "sha256", "size"}
                or binding["path"] != path or type(binding["sha256"]) is not str
                or len(binding["sha256"]) != 64 or type(binding["size"]) is not int
                or binding["size"] <= 0):
            raise FixtureSourceSetError("Fixture acquisition binding differs")
    body = {key: value for key, value in manifest.items() if key != "source_set_manifest_id"}
    if content_hash(value=body) != manifest["source_set_manifest_id"]:
        raise FixtureSourceSetError("Fixture source-set content identity differs")
    return dict(manifest)


def build_pinned_fixture_source_set(*, repo_root: Path, source_id: str) -> dict:
    """Rebuild fresh attempt, exact acquisition inputs and inline filing identity."""
    from .deterministic_router import _XbrlContextParser, _XbrlFactParser
    from .r4_source_audit import source_authority

    plan_path = resolve_repository_file(repo_root=repo_root,
                                        repo_relative_path=ACQUISITION_PLAN)
    receipt_path = resolve_repository_file(repo_root=repo_root,
                                           repo_relative_path=ACQUISITION_RECEIPT)
    plan = strict_json_file(path=plan_path)
    receipt = strict_json_file(path=receipt_path)
    receipt_body = {k: v for k, v in receipt.items() if k != "receipt_id"}
    if (content_hash(value=receipt_body) != receipt["receipt_id"]
            or receipt["status"] != "PASSED"
            or receipt["qualification_credit"] != "NONE_OFFLINE_SOURCE_ONLY"):
        raise FixtureSourceSetError("Fixture acquisition receipt is invalid")
    planned = [s for s in plan["sources"] if s["source_id"] == source_id]
    observed = [s for s in receipt["sources"] if s["source_id"] == source_id]
    if len(planned) != 1 or len(observed) != 1:
        raise FixtureSourceSetError("Source was not in the exact owner acquisition set")
    declaration = observed[0]
    if (any(declaration.get(k) != v for k, v in planned[0].items())
            or declaration["status_code"] != 200 or declaration["retry_attempt"] != 0):
        raise FixtureSourceSetError("Acquisition observation differs from owner-pinned source")
    source = source_authority(repo_root=repo_root,
                              declaration={**declaration, "media_type": "text/html"})
    if source["source_reference"]["request_attempt_id"] != declaration["request_attempt_id"]:
        raise FixtureSourceSetError("Fixture native attempt identity changed")
    parser = _XbrlFactParser()
    parser.feed(source["source_bytes"].decode("utf-8"))
    parser.close()
    context_parser = _XbrlContextParser()
    context_parser.feed(source["source_bytes"].decode("utf-8"))
    context_parser.close()
    contexts = context_parser.contexts()
    names = {"entity_central_index_key": "dei:entitycentralindexkey",
             "document_type": "dei:documenttype",
             "fiscal_year_focus": "dei:documentfiscalyearfocus",
             "document_period_end": "dei:documentperiodenddate"}
    dei = {}
    context_ids = set()
    for field, name in names.items():
        facts = [fact for fact in parser.facts() if fact["qualified_name"].casefold() == name]
        values = {fact["text"] for fact in facts}
        if len(values) != 1:
            raise FixtureSourceSetError("Inline DEI field is absent or ambiguous: " + field)
        dei[field] = values.pop()
        context_ids.update(fact["context_ref"] for fact in facts)
    if len(context_ids) != 1:
        raise FixtureSourceSetError("Inline DEI fields use different entity/period contexts")
    context = contexts[context_ids.pop()]
    dei["context_period_start"] = context["period_start"]
    dei["context_period_end"] = context["period_end"]
    if (int(dei["entity_central_index_key"]) != int(declaration["cik"])
            or dei["document_type"] != declaration["form"]
            or int(dei["fiscal_year_focus"]) != declaration["fiscal_year"]
            or not dei["context_period_end"].startswith(str(declaration["fiscal_year"]))
            or int(context["entity_identifier"]) != int(declaration["cik"])
            or context["dimensions"] or context["typed_dimension_count"]):
        raise FixtureSourceSetError("Inline DEI disagrees with the pinned filing")
    body = {
        "record_type": FIXTURE_SET_TYPE, "schema_version": 1,
        "company_id": declaration["company_id"], "source_role": "offline_fixture_accession_xbrl",
        "ordered_source_reference_ids": [source["source_reference"]["source_reference_id"]],
        "source_reference": source["source_reference"], "raw_blob": source["raw_blob"],
        "source_id": source_id, "inline_dei": dei,
        "acquisition_plan": {"path": ACQUISITION_PLAN, "sha256": sha256_file(path=plan_path),
                             "size": plan_path.stat().st_size},
        "acquisition_receipt": {"path": ACQUISITION_RECEIPT, "sha256": sha256_file(path=receipt_path),
                                "size": receipt_path.stat().st_size},
        "selection_scope": "OWNER_PINNED_SINGLE_FILING_OFFLINE_ONLY",
        "latest_filing_claim": False, "full_submissions_inventory_claim": False,
        "qualification_credit": "NONE_OFFLINE_FIXTURE", "publication_credit": "NONE",
        "provider_paid_sec_authorized": False,
    }
    return validate_fixture_source_set(manifest={**body, "source_set_manifest_id": content_hash(value=body)})


def load_pinned_fixture_source_set(*, repo_root: Path, path: Path,
                                   expected_manifest_id: str) -> dict:
    regular = resolve_repository_file(repo_root=repo_root,
                                       repo_relative_path=path.relative_to(repo_root).as_posix())
    value = validate_fixture_source_set(manifest=strict_json_file(path=regular))
    expected = build_pinned_fixture_source_set(repo_root=repo_root, source_id=value["source_id"])
    if value != expected or value["source_set_manifest_id"] != expected_manifest_id:
        raise FixtureSourceSetError("Fixture source-set disk replay differs")
    return value
