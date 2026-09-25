"""Pinned-period semantic sources for D04 and B13 (Issue #47).

The ordinary builders assemble a complete original annual source - every
visible block, every native XBRL fact and supplement, and every current-period
10-K/A in full - for "the latest annual input", which they read through two
functions: ``going_concern_source.prepare_saved_annual_input`` and
``r6_semantic_source.prepare_saved_annual_input``. Everything after those two
reads is a pure function of what they return.

This module is those builders with that input explicit: the pinned period's
original input (``historical_annual_input.prepare_original_historical_input``)
and its fiscal-label resolution (``prepare_historical_annual_input``). The
bodies are the frozen ones restated with that one change, and they are held to
it mechanically rather than by review: the differential test runs the frozen
builders with the two reads pointed at the same pinned inputs and requires the
output to be byte-identical, ``semantic_source_id`` included. That is why the
sources carry the frozen modules' own hashes (``module_sha256``,
``capacity_module_sha256``): the code that serialised the units is the frozen
code. This module's own bytes are bound where a Run binds its rules, in the
Requirement closure.

The frozen builders run in either of two admission modes; the historical data
root is an installed, registered root, so this is always the
``ordinary_registered=True`` one - policy files are read from the code tree and
source proofs are admitted by ``verify_ordinary_source_proofs``, as every other
historical route admits them.

Nothing here makes a request, reads a response or decides a result.
"""
from pathlib import Path

from sec_urls import accession_document_url

from . import capacity_semantic_source as frozen_capacity
from . import going_concern_source as frozen_going_concern
from . import r6_semantic_source as frozen_semantic
from .annual_update import saved_source
from .canonical import content_hash, sha256_file, strict_json_file
from .historical_annual_input import (prepare_historical_annual_input,
                                      prepare_original_historical_input)
from .normal_annual_input_v2 import exact_json_value
from .normal_source_authority import ROOT
from .ordinary_source_authority import verify_ordinary_source_proofs
from .regulatory_investigation_candidates import _quotation_ranges
from .sources import raw_blob_record, resolve_repository_file, source_reference_record

SUPPORTED_METRICS = ("B13", "D04")


class HistoricalSemanticSourceError(ValueError):
    """A pinned semantic source could not be assembled."""


def _need(condition, reason):
    if not condition:
        raise HistoricalSemanticSourceError(reason)


def pinned_inputs(*, repo_root: Path, company_id: str, period_selection):
    """The two inputs the frozen builders read as "latest", for the pinned period.

    Returns:
        ``(original, annual)``: the original-input body and its fiscal-label
        resolution, the second required to carry the first unchanged.
    """
    original = prepare_original_historical_input(repo_root=repo_root, company_id=company_id,
                                                 period_selection=period_selection)
    annual = prepare_historical_annual_input(repo_root=repo_root, company_id=company_id,
                                             period_selection=period_selection)
    _need(annual["original_input"] == original, "HISTORICAL_SEMANTIC_ANNUAL_INPUT_BINDING_CHANGED")
    return original, annual


def prepare_historical_going_concern_source(*, repo_root: Path, company_id: str, prepared):
    """``prepare_ordinary_going_concern_source`` over an explicit original input.

    The original filing and every current-period 10-K/A are supplied in full,
    as the frozen builder supplies them; no amendment is judged irrelevant here.
    """
    root = Path(repo_root).resolve()
    filings = [prepared["filing"], *sorted(prepared["amendments"],
                                           key=lambda f: (f["filingDate"], f["accessionNumber"]))]
    proofs, source_rows = list(prepared["source_proofs"]), []
    for filing in filings:
        url = accession_document_url(cik=int(prepared["entity"]),
                                     accession=filing["accessionNumber"],
                                     document_name=filing["primaryDocument"])
        saved = saved_source(repo_root=root, url=url, accession=filing["accessionNumber"])
        _need(saved is not None, "SAVED_SOURCE_MISSING:" + url)
        proof = saved["proof"]
        if proof not in proofs:
            proofs.append(proof)
        source_rows.append((filing, proof))
    admission = verify_ordinary_source_proofs(data_root=root, proofs=proofs)
    components = []
    for filing, proof in source_rows:
        blob = raw_blob_record(repo_root=root, repo_relative_path=proof["request_repo_relative_path"],
                               media_type="text/html")
        reference = source_reference_record(
            raw_blob=blob, company_id=company_id, source_url=proof["source_url"],
            accession=filing["accessionNumber"], document_name=proof["document_name"],
            source_role="target_primary" if filing["form"] == "10-K" else "annual_amendment",
            request_attempt_id=proof["request_attempt_id"])
        raw = resolve_repository_file(repo_root=root,
                                      repo_relative_path=proof["request_repo_relative_path"]).read_bytes()
        components.append(frozen_going_concern.inspect_going_concern_source(
            raw_bytes=raw, raw_blob=blob, source_reference=reference, company_id=company_id,
            cik=prepared["entity"], filing=filing))
    return frozen_going_concern._seal({
        "record_type": "ORDINARY_GOING_CONCERN_SOURCE_PACKET", "method": frozen_going_concern.METHOD,
        "metric_id": "D04", "company_id": company_id, "prepared_annual_input": prepared,
        "source_proofs": proofs, "source_admission": admission, "components": components,
        "required_filing_accessions": [f["accessionNumber"] for f in filings],
        "required_document_ids": [c["document"]["text_document_id"] for c in components],
        "required_source_unit_ids": [u["source_unit_id"] for c in components
                                     for u in c["semantic_source_units"]],
        "semantic_obligations": ["CURRENT_REGISTRANT_VERSUS_PREDECESSOR_OR_ACQUIRED_ENTITY",
                                 "CURRENT_VERSUS_HISTORICAL_CONDITIONAL_NEGATED_OR_RESOLVED_STATEMENT",
                                 "AUDITOR_REPORT_ATTRIBUTION_AND_MANAGEMENT_DISCLOSURES",
                                 "FULL_DOCUMENT_AND_ANNUAL_AMENDMENT_INTERPRETATION",
                                 "SOURCE_CONTRADICTIONS_AND_CROSS_REFERENCES",
                                 "CLOSED_WORLD_ABSENCE_REQUIRES_COMPLETE_SEMANTIC_COVERAGE"],
        "status": "SEMANTIC_REVIEW_REQUIRED", "semantic_coverage_complete": False,
        "not_disclosed_confirmed": False, "native_result_created": False,
        "current_latest_verified": False, "publication_credit": False,
        "calls": {"provider": 0, "paid": 0, "sec": 0}}, "packet_id")


def prepare_historical_d04_semantic_source(*, repo_root: Path, company_id: str,
                                           period_selection):
    """``prepare_d04_semantic_source`` for the pinned period."""
    path = resolve_repository_file(repo_root=ROOT, repo_relative_path=frozen_semantic.POLICY_PATH)
    _need(strict_json_file(path=path) == frozen_semantic.POLICY
          == strict_json_file(path=ROOT / frozen_semantic.POLICY_PATH),
          "SEMANTIC_SOURCE_INSTALLED_POLICY_CHANGED")
    original, annual = pinned_inputs(repo_root=repo_root, company_id=company_id,
                                     period_selection=period_selection)
    source = prepare_historical_going_concern_source(repo_root=repo_root, company_id=company_id,
                                                     prepared=original)
    _need(annual["original_input"] == source["prepared_annual_input"],
          "SEMANTIC_ANNUAL_SOURCE_BINDING_CHANGED")
    units, documents = [], []
    for component in source["components"]:
        document = component["document"]
        document_id = document["text_document_id"]
        _need(set(document["source_reasons"]) <= {"TEXT_AMENDMENT_SOURCE_SET_REQUIRED"},
              "SEMANTIC_ORIGINAL_DOCUMENT_NOT_COMPLETE")
        raw = resolve_repository_file(repo_root=repo_root,
                                      repo_relative_path=component["raw_blob"]["storage_uri"]).read_bytes()
        quotation_ranges = _quotation_ranges(raw)
        blocks = [{**{k: b[k] for k in ("block_index", "text", "raw_start_byte", "raw_end_byte",
                                        "raw_span_sha256")},
                   "html_quotation_context": any(a < b["raw_end_byte"] and b["raw_start_byte"] < z
                                                 for a, z in quotation_ranges)}
                  for b in document["blocks"]]
        visible = frozen_semantic._group(blocks, lambda rows: {"blocks": rows}, document_id,
                                         "VISIBLE_TEXT")
        _need([b for u in visible for b in u["payload"]["blocks"]] == blocks,
              "SEMANTIC_VISIBLE_ROUNDTRIP_CHANGED")
        native, coverage = frozen_semantic._native_units(raw, component)
        units.extend(visible + native)
        documents.append({
            "document_id": document_id, "source_reference": component["source_reference"],
            "raw_blob": component["raw_blob"], "filing": component["source_filing"],
            "registrant_name_binding": component["registrant_name_binding"],
            "visible_block_count": len(blocks), "native_coverage": coverage,
            "language_candidate_block_indices": [r["block_index"]
                                                 for r in component["language_candidates"]],
            "native_candidate_ordinals": [r["fact"]["ordinal"]
                                          for r in component["native_concept_candidates"]],
            "source_unit_ids": [u["unit_id"] for u in visible + native]})
    ids = [u["unit_id"] for u in units]
    _need(len(ids) == len(set(ids)), "SEMANTIC_SOURCE_UNIT_DUPLICATE")
    body = exact_json_value({
        "record_type": "D04_COMPLETE_SEMANTIC_SOURCE", "company_id": company_id, "metric_id": "D04",
        "prepared_annual_input": annual, "original_source_packet_id": source["packet_id"],
        "source_proofs": source["source_proofs"], "source_admission": source["source_admission"],
        "documents": documents, "units": units, "required_unit_ids": ids,
        "source_serialization_complete": True, "semantic_coverage_verified": False,
        "interpretation_created": False, "provider_request_created": False,
        "source_freshness_verified": False, "production_authorized": False,
        "calls": {"provider": 0, "paid": 0, "sec": 0},
        "policy_sha256": sha256_file(path=path),
        "module_sha256": sha256_file(path=Path(frozen_semantic.__file__))})
    return {**body, "semantic_source_id": content_hash(value=body)}


def prepare_historical_capacity_semantic_source(*, repo_root: Path, company_id: str,
                                                period_selection, request_context_format):
    """``prepare_capacity_semantic_source`` for the pinned period.

    The approved company set is checked first, as the frozen builder checks it:
    outside it B13 is answered by ``historical_capacity_results`` without any
    source assembly. The set is read where that route reads it, from the
    approved definition's own heading. The frozen builder reads it from Issue
    #28's continuous-call policy, which also carries that Issue's budget and
    delegation, so its answer here would depend on another Issue's spending
    authority; the two sources name the same two companies, and
    ``historical_capacity_results``' differential test holds them to each other.
    The capacity rules are the same rules file the frozen builder uses.
    """
    from .historical_capacity_results import out_of_scope
    _need(not out_of_scope(repo_root=ROOT, company_id=company_id),
          "B13_OUTSIDE_APPROVED_APPLICABILITY")
    rules = strict_json_file(path=ROOT / frozen_capacity.POLICY_PATH)
    source = prepare_historical_d04_semantic_source(repo_root=repo_root, company_id=company_id,
                                                    period_selection=period_selection)
    result = frozen_capacity.capacity_source_from_complete_annual(source=source, rules=rules)
    body = {k: v for k, v in result.items() if k != "semantic_source_id"}
    body.update(capacity_rule_sha256=sha256_file(path=ROOT / frozen_capacity.POLICY_PATH),
                capacity_module_sha256=sha256_file(path=Path(frozen_capacity.__file__)))
    if request_context_format is not None:
        from .continuous_request_context import FORMAT_VERSION
        _need(request_context_format == FORMAT_VERSION, "B13_CONTEXT_FORMAT_UNSUPPORTED")
        body["request_context_format"] = FORMAT_VERSION
    result = {**body, "semantic_source_id": content_hash(value=body)}
    if request_context_format is not None:
        from .capacity_quantity_scope import attach_quantity_scope
        raw = {d["raw_blob"]["raw_asset_id"]: resolve_repository_file(
            repo_root=repo_root, repo_relative_path=d["raw_blob"]["storage_uri"]).read_bytes()
            for d in result["documents"]}
        result = attach_quantity_scope(source=result, raw_bytes_by_id=raw)
    return result
