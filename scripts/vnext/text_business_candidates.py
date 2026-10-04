"""Source-bound governance, legal and going-concern excerpt candidates.

These methods identify inspectable source language and the local ranges that
were examined. They never infer absence of risk from a search miss, interpret
a clean audit opinion as no going-concern doubt, or turn prospective nominees
into the current board. Semantic decisions and native Run acceptance remain
separate from this deterministic source preparation.
"""

from __future__ import annotations

import re
from pathlib import Path

from .canonical import content_hash, sha256_bytes, strict_json_file
from .deterministic_router import parse_accession_xbrl_source, _numeric_xbrl_value
from .governance_signals import _FactAttributes
from .records import validate_record
from .resource_limits import RESOURCE_LIMITS
from .text_coverage import build_text_document, _Blocks, _byte_offsets, _heading as _form_heading


_POLICY_PATH = Path(__file__).resolve().parents[2] / "catalog/r6/text_business_candidates_v1.json"
_POLICY = strict_json_file(path=_POLICY_PATH)
_POLICY_HASH = content_hash(value=_POLICY)
_PATTERNS = {name: re.compile(pattern, re.I) for name, pattern in _POLICY["patterns"].items()}
_LEGAL = _PATTERNS["legal"]
_AUTHORITY = _PATTERNS["authority"]
_ACTION = _PATTERNS["action"]
_GOING = _PATTERNS["going"]
_PROSPECTIVE = _PATTERNS["prospective"]
_NEGATION = _PATTERNS["negation"]
_BOARD = _PATTERNS["board"]
_INDEPENDENCE = _PATTERNS["independence"]
_BOARD_NUMBER = _PATTERNS["board_number"]
_COMMITTEE = _PATTERNS["committee"]
_STATEMENT = _PATTERNS["statement"]
_NOTE_REFERENCE = _PATTERNS["note_reference"]
_NOTE_HEADING = _PATTERNS["note_heading"]
_AUDIT_HEADING = _PATTERNS["audit_heading"]
_FINANCIAL_HEADING = _PATTERNS["financial_heading"]


class TextBusinessCandidateError(ValueError):
    """Reject source identity or structural failure without claiming absence."""


def _need(condition, reason):
    if not condition:
        raise TextBusinessCandidateError(reason)


def _bound_source(*, raw_bytes, raw_blob, source_reference, company_id, cik, filing):
    blob, ref = validate_record(record=dict(raw_blob)), validate_record(record=dict(source_reference))
    _need(type(raw_bytes) is bytes and 0 < len(raw_bytes) <= RESOURCE_LIMITS.max_html_bytes,
          "TEXT_BUSINESS_SOURCE_SIZE_INVALID")
    _need(blob["record_type"] == "RAW_BLOB" and ref["record_type"] == "SOURCE_REFERENCE"
          and blob["media_type"] == "text/html" and blob["byte_length"] == len(raw_bytes)
          and blob["raw_asset_id"] == ref["raw_asset_id"] == "sha256:" + sha256_bytes(content=raw_bytes),
          "TEXT_BUSINESS_SOURCE_BYTES_CHANGED")
    expected = "https://www.sec.gov/Archives/edgar/data/{}/{}/{}".format(str(int(cik)), filing["accessionNumber"].replace("-", ""), filing["primaryDocument"])
    _need(ref["company_id"] == company_id and ref["accession"] == filing["accessionNumber"]
          and ref["document_name"] == filing["primaryDocument"] and ref["source_url"] == expected,
          "TEXT_BUSINESS_SOURCE_IDENTITY_CONFLICT")
    parsed = parse_accession_xbrl_source(raw_bytes=raw_bytes)
    metadata = _FactAttributes(); metadata.feed(raw_bytes.decode("utf-8-sig")); metadata.close()
    _need(metadata.ordinal == len(parsed.facts), "TEXT_BUSINESS_NATIVE_METADATA_CONFLICT")
    dei = [f for f in parsed.facts if re.fullmatch(r"https?://xbrl\.sec\.gov/dei/\d{4}", metadata.facts[f["ordinal"]]["concept"][0])]
    entities = {str(int(f["text"])) for f in dei if metadata.facts[f["ordinal"]]["concept"][1].casefold() == "entitycentralindexkey" and f["text"].isdigit()}
    forms = {f["text"].upper().replace(" ", "") for f in dei if metadata.facts[f["ordinal"]]["concept"][1].casefold() == "documenttype"}
    _need(entities == {str(int(cik))} and forms == {filing["form"].upper().replace(" ", "")}, "TEXT_BUSINESS_DEI_IDENTITY_CONFLICT")
    names = sorted({f["text"] for f in dei if metadata.facts[f["ordinal"]]["concept"][1].casefold() == "entityregistrantname"})
    return parsed, metadata, names


def governance_source_document(*, raw_bytes, raw_blob, source_reference, company_id, cik, filing):
    """Parse a whole proxy/amendment without inventing a board as-of date."""
    _, _, names = _bound_source(raw_bytes=raw_bytes, raw_blob=raw_blob, source_reference=source_reference,
        company_id=company_id, cik=cik, filing=filing)
    _need(filing["form"] in {"DEF 14A", "10-K/A"}, "GOVERNANCE_TEXT_FORM_UNSUPPORTED")
    text = raw_bytes.decode("utf-8-sig")
    parser = _Blocks(text); parser.feed(text); parser.close(); parser._flush()
    reasons = list(parser.structural_errors)
    if (parser.html_count, parser.body_count, parser.html_closed, parser.body_closed) != (1, 1, 1, 1) or parser.stack:
        reasons.append("GOVERNANCE_TEXT_DOCUMENT_INCOMPLETE")
    blocks = parser.blocks
    offsets = _byte_offsets(text, [v for b in blocks for v in (b["start"], b["end"])])
    bom = 3 if raw_bytes.startswith(b"\xef\xbb\xbf") else 0
    for i, block in enumerate(blocks):
        block["block_index"] = i
        block["raw_start_byte"] = offsets[block.pop("start")] + bom
        block["raw_end_byte"] = offsets[block.pop("end")] + bom
        block["raw_span_sha256"] = sha256_bytes(content=raw_bytes[block["raw_start_byte"]:block["raw_end_byte"]])
        # Only full-block excerpts are proposed here. No unconverted inner
        # character offsets are advertised as byte locators.
        block.pop("leading_emphasis", None)
    body = {"record_type": "GOVERNANCE_SOURCE_TEXT_DOCUMENT", "company_id": company_id,
            "cik": str(int(cik)), "source_reference_id": source_reference["source_reference_id"],
            "raw_asset_id": raw_blob["raw_asset_id"], "source_filing": dict(filing), "registrant_names": names,
            "source_state": "INCOMPLETE" if reasons else "COMPLETE_LOCAL_DOCUMENT",
            "source_reasons": sorted(set(reasons)), "blocks": blocks,
            "board_measurement_date_assigned": False, "publication_credit": False}
    return {**body, "text_document_id": content_hash(value=body)}


def _check_document(document):
    _need(document["text_document_id"] == content_hash(value={k: v for k, v in document.items() if k != "text_document_id"}),
          "TEXT_BUSINESS_DOCUMENT_CHANGED")


def _excerpt(document, block, section_id, labels):
    return {"source_reference_id": document["source_reference_id"], "raw_asset_id": document["raw_asset_id"],
            "document_id": document["text_document_id"], "section_id": section_id, "labels": labels,
            **{k: block[k] for k in ("block_index", "text", "raw_start_byte", "raw_end_byte", "raw_span_sha256")}}


def _substantive(document, block):
    text = block["text"].strip()
    names = {re.sub(r"\W", "", n).casefold() for n in document.get("registrant_names", [])}
    return bool(len(text) >= 12 and re.search(r"[A-Za-z]", text)
                and re.sub(r"\W", "", text).casefold() not in names
                and not (block["linked"] and len(text) < 120)
                and not _PATTERNS["navigation_header"].match(text))


def board_composition_candidates(*, document):
    """Return actual source statements, not inferred board/nominee counts."""
    _check_document(document)
    candidates = []
    for block in document["blocks"]:
        text = block["text"]
        if not _substantive(document, block): continue
        labels = []
        if _BOARD.search(text) and _BOARD_NUMBER.search(text) and _PATTERNS["board_size_statement"].search(text): labels.append("REPORTED_BOARD_OR_NOMINEE_SIZE_LANGUAGE")
        if _BOARD.search(text) and _INDEPENDENCE.search(text) and _PATTERNS["independence_statement"].search(text): labels.append("REPORTED_DIRECTOR_INDEPENDENCE_LANGUAGE")
        if _COMMITTEE.search(text) and _PATTERNS["committee_structure"].search(text): labels.append("REPORTED_COMMITTEE_INFORMATION")
        if labels:
            if _PATTERNS["prospective_board_context"].search(text): labels.append("PROSPECTIVE_OR_ELECTION_CONTEXT_PRESENT")
            candidates.append(_excerpt(document, block, "GOVERNANCE_DISCLOSURES", labels))
    body = {"record_type": "BOARD_COMPOSITION_SOURCE_CANDIDATES", "metric_id": "C02",
            "document_id": document["text_document_id"], "source_reference_id": document["source_reference_id"],
            "scope": "LOCAL_PROXY_OR_ANNUAL_AMENDMENT_TEXT", "source_filing": document["source_filing"],
            "coverage_status": document["source_state"], "source_reasons": document["source_reasons"],
            "finding_status": "SOURCE_EXCERPTS_FOUND" if candidates else "NO_SUPPORTED_STATEMENT_PATTERN",
            "candidates": candidates, "numeric_board_counts_asserted": False,
            "board_measurement_date_assigned": False, "not_disclosed_confirmed": False,
            "semantic_interpretation": "VERBATIM_GOVERNANCE_DISCLOSURES_NOT_AS_OF_BOARD_INFERENCE",
            "native_result_created": False, "publication_credit": False}
    return {**body, "policy_hash": _POLICY_HASH, "proposal_id": content_hash(value={**body, "policy_hash": _POLICY_HASH})}


def _ranges(document, required):
    ranges, reasons = [], list(document["source_reasons"])
    for name in required:
        entry = document["sections"].get(name)
        if not entry or entry["status"] != "LOCATED" or len(entry["candidates"]) != 1:
            reasons.append(name + "_NOT_UNIQUELY_LOCATED")
        else:
            ranges.append(entry["candidates"][0])
    return ranges, sorted(set(reasons))


def _note_references(document, ranges):
    item3 = [r for r in ranges if r["section_id"] == "ITEM_3"]
    references = {}
    for scope in item3:
        for block in document["blocks"][scope["start_block"]:scope["end_block_exclusive"]]:
            for match in _NOTE_REFERENCE.finditer(block["text"]):
                references.setdefault(match.group(1).upper(), []).append(block)
    headings = []
    blocks = document["blocks"]
    # Financial statements can be appended after the form's numbered items.
    # Search the complete source structure, not only the small Item 8 pointer.
    for i, block in enumerate(blocks):
        if block["linked"] or not block.get("emphasized") or len(block["text"]) > 300:
            continue
        match = _NOTE_HEADING.match(block["text"])
        end_index = i
        if match is None:
            identifier = _PATTERNS["note_identifier"].fullmatch(block["text"])
            if identifier and i + 1 < len(blocks) and blocks[i + 1].get("emphasized") and re.match(r"[A-Za-z]", blocks[i + 1]["text"]):
                match = _NOTE_HEADING.match(identifier.group(1) + ". " + blocks[i + 1]["text"])
                end_index = i + 1
        if match and not _PATTERNS["continued_heading"].search(block["text"]):
            headings.append({"number": match.group(1).upper(), "start": i, "heading_end": end_index,
                             "explicit_prefix": bool(_PATTERNS["explicit_note_prefix"].match(block["text"]))})
    result = []
    for number, reference_blocks in sorted(references.items()):
        exact = [h for h in headings if h["number"] == number]
        parent = re.sub(r"[A-Z]+$", "", number)
        matched = exact or [h for h in headings if h["number"] == parent]
        candidates = []
        for h in matched:
            base_number = int(re.match(r"\d+", h["number"])[0])
            possible = [other["start"] for other in headings if other["start"] > h["start"]
                        and int(re.match(r"\d+", other["number"])[0]) == base_number + 1
                        and (not h["explicit_prefix"] or other["explicit_prefix"])]
            possible.extend(r["end_block_exclusive"] for r in ranges if r["section_id"] == "ITEM_8"
                            and r["start_block"] <= h["start"] < r["end_block_exclusive"])
            end = min(possible) if possible else None
            if end is not None:
                candidates.append({"section_id": "NOTE_" + h["number"], "start_block": h["start"],
                                   "end_block_exclusive": end, "requested_reference": number,
                                   "scope_relation": "EXACT_NOTE" if h["number"] == number else "WIDER_PARENT_NOTE"})
        result.append({"reference": "Note " + number,
            "source_occurrences": [_excerpt(document, b, "ITEM_3", ["NOTE_REFERENCE"]) for b in reference_blocks],
            "heading_candidates": [_excerpt(document, blocks[h["start"]], "FULL_DOCUMENT_NOTES", ["NOTE_HEADING"]) for h in matched],
            "range_candidates": candidates,
            "status": "LOCATED_NOTE_RANGE" if len(candidates) == 1 else "REFERENCE_NAVIGATION_NOT_UNIQUE_OR_INCOMPLETE"})
    return result


def legal_risk_candidates(*, document):
    """Scan complete local legal/risk ranges; preserve ambiguity in interpretation."""
    _check_document(document)
    ranges, reasons = _ranges(document, ["ITEM_1A", "ITEM_3", "ITEM_8"])
    references = _note_references(document, ranges)
    for reference in references:
        if reference["status"] == "LOCATED_NOTE_RANGE":
            note = reference["range_candidates"][0]
            if not any(r["start_block"] <= note["start_block"] and note["end_block_exclusive"] <= r["end_block_exclusive"] for r in ranges):
                ranges.append(note)
        else:
            reasons.append("UNRESOLVED_" + reference["reference"].upper().replace(" ", "_"))
    legal, regulatory = [], []
    for scope in ranges:
        section = scope["section_id"]
        for block in document["blocks"][scope["start_block"]:scope["end_block_exclusive"]]:
            if not _substantive(document, block):
                if section == "ITEM_3" and block["text"].strip().casefold() in {"none", "none."}:
                    legal.append(_excerpt(document, block, section, ["EXPLICIT_NONE_IN_THIS_SECTION_ONLY"]))
                continue
            text = block["text"]
            if section == "ITEM_3" or section.startswith("NOTE_") or section == "ITEM_8" and _LEGAL.search(text):
                legal.append(_excerpt(document, block, section, ["EXPLICIT_LEGAL_SECTION_TEXT" if section == "ITEM_3" else "LEGAL_OR_CONTINGENCY_LANGUAGE_IN_NOTES"]))
            if _ACTION.search(text) or _AUTHORITY.search(text):
                labels = ["ACTION_LANGUAGE_PRESENT" if _ACTION.search(text) else "AUTHORITY_OR_GENERAL_REGULATION_MENTION"]
                if _PROSPECTIVE.search(text): labels.append("HYPOTHETICAL_OR_GENERAL_LANGUAGE_PRESENT")
                if _NEGATION.search(text): labels.append("NEGATION_OR_RESOLUTION_LANGUAGE_PRESENT")
                regulatory.append(_excerpt(document, block, section, labels))
    body = {"record_type": "LEGAL_REGULATORY_SOURCE_CANDIDATES", "document_id": document["text_document_id"],
            "source_reference_id": document["source_reference_id"], "checked_ranges": ranges,
            "coverage_status": "INCOMPLETE" if reasons else "LOCAL_REQUESTED_RANGES_SCANNED",
            "coverage_reasons": reasons, "note_references": references,
            "semantic_scope_completeness_asserted": False,
            "D02": {"finding_status": "SOURCE_EXCERPTS_FOUND" if legal else "NO_SUPPORTED_SOURCE_LANGUAGE", "candidates": legal,
                    "interpretation": "VERBATIM_LEGAL_DISCLOSURES_NOT_TOTAL_CASE_OR_LIABILITY_ASSERTION"},
            "D03": {"finding_status": "SOURCE_LANGUAGE_FOUND" if regulatory else "NO_MATCHED_SOURCE_LANGUAGE", "candidates": regulatory,
                    "semantic_review_required": True, "actual_investigation_asserted": False},
            "not_disclosed_confirmed": False, "native_result_created": False, "publication_credit": False}
    return {**body, "policy_hash": _POLICY_HASH, "proposal_id": content_hash(value={**body, "policy_hash": _POLICY_HASH})}


def going_concern_candidates(*, document):
    """Locate auditor-report context and relevant language without a no-risk inference."""
    _check_document(document)
    ranges, reasons = _ranges(document, ["ITEM_8"])
    reports = []
    blocks = document["blocks"]
    starts = [i for i, b in enumerate(blocks) if _AUDIT_HEADING.fullmatch(b["text"].strip()) and not b["linked"]
              and _PATTERNS["audit_opening"].search(" ".join(x["text"] for x in blocks[i + 1:i + 9]))]
    form_boundaries = [i for i in range(len(blocks)) if _form_heading(blocks, i) is not None]
    for start in starts:
        endings = [i for i in range(start + 1, len(blocks))
                   if (i in starts or blocks[i].get("emphasized") and _FINANCIAL_HEADING.match(blocks[i]["text"]))
                   and len(blocks[i]["text"]) < 250 and not blocks[i]["linked"]]
        endings.extend(r["end_block_exclusive"] for r in ranges if r["start_block"] <= start < r["end_block_exclusive"])
        endings.extend(i for i in form_boundaries if i > start)
        end = min(endings) if endings else None
        if end is None:
            reports.append({"start_block": start, "status": "CLOSING_BOUNDARY_NOT_LOCATED"})
        else:
            reports.append({"start_block": start, "end_block_exclusive": end, "status": "LOCAL_REPORT_RANGE_LOCATED",
                            "opening_heading": _excerpt(document, blocks[start], "FULL_LOCAL_DOCUMENT", ["AUDITOR_REPORT_HEADING"]),
                            "closing_heading": _excerpt(document, blocks[end], "FULL_LOCAL_DOCUMENT", ["NEXT_REPORT_FINANCIAL_STATEMENT_OR_ITEM_BOUNDARY"]),
                            "report_subject_and_period_review_required": True})
    if not reports: reasons.append("AUDITOR_REPORT_STRUCTURE_NOT_LOCATED")
    if any(r["status"] != "LOCAL_REPORT_RANGE_LOCATED" for r in reports):
        reasons.append("AUDITOR_REPORT_CLOSING_BOUNDARY_NOT_LOCATED")
    candidates = [_excerpt(document, b, "FULL_LOCAL_DOCUMENT", ["GOING_CONCERN_LANGUAGE_PRESENT"] +
                          (["NEGATION_OR_RESOLUTION_LANGUAGE_PRESENT"] if _NEGATION.search(b["text"]) else []))
                  for b in document["blocks"] if _substantive(document, b) and _GOING.search(b["text"])]
    body = {"record_type": "GOING_CONCERN_SOURCE_CANDIDATES", "metric_id": "D04",
            "document_id": document["text_document_id"], "source_reference_id": document["source_reference_id"],
            "checked_scope": "ENTIRE_LOCAL_VISIBLE_DOCUMENT_PLUS_AUDITOR_REPORT_BOUNDARIES",
            "coverage_status": "INCOMPLETE" if reasons else "LOCAL_DOCUMENT_SCANNED",
            "coverage_reasons": sorted(set(reasons)), "auditor_report_ranges": reports,
            "finding_status": "SOURCE_LANGUAGE_FOUND" if candidates else "NO_MATCHED_SOURCE_LANGUAGE",
            "candidates": candidates, "semantic_review_required": True, "not_disclosed_confirmed": False,
            "going_concern_doubt_asserted": False, "clean_opinion_used_as_absence": False,
            "native_result_created": False, "publication_credit": False}
    return {**body, "policy_hash": _POLICY_HASH, "proposal_id": content_hash(value={**body, "policy_hash": _POLICY_HASH})}


def reported_legal_fact_candidates(*, raw_bytes, raw_blob, source_reference, company_id, cik, filing):
    """Expose exact declared fact identities/contexts; do not sum legal exposure."""
    parsed, metadata, _ = _bound_source(raw_bytes=raw_bytes, raw_blob=raw_blob, source_reference=source_reference,
        company_id=company_id, cik=cik, filing=filing)
    candidates = []
    for fact in parsed.facts:
        uri, local = metadata.facts[fact["ordinal"]]["concept"]
        if not re.fullmatch(r"https?://fasb\.org/us-gaap/\d{4}", uri) or not _PATTERNS["legal_fact_concepts"].search(local):
            continue
        context = parsed.contexts[fact["context_ref"]]
        row = {"source_reference_id": source_reference["source_reference_id"], "raw_asset_id": raw_blob["raw_asset_id"],
               "concept_namespace": uri, "concept_local_name": local, "source_text": fact["text"],
               "locator": {"qualified_name": fact["qualified_name"], "context_ref": fact["context_ref"], "ordinal": fact["ordinal"]},
               "context": {**dict(context), "dimensions": dict(context["dimensions"])},
               "unit_ref": fact["unit_ref"],
               "declared_unit": ({"measures": [list(m) for m in metadata.units[fact["unit_ref"]]["measures"]],
                                  "divided": metadata.units[fact["unit_ref"]]["divided"]}
                                 if fact["unit_ref"] in metadata.units else None),
               "metric_role_interpretation_required": True}
        if fact["unit_ref"]:
            try: row["source_numeric_value"] = _numeric_xbrl_value(text=fact["text"], scale=fact["scale"], sign=fact["sign"])
            except ValueError as error: row["numeric_parse_issue"] = str(error)
        candidates.append(row)
    body = {"record_type": "REPORTED_LEGAL_FACT_CANDIDATES", "source_reference_id": source_reference["source_reference_id"],
            "candidates": candidates, "complete_legal_liability_asserted": False,
            "not_disclosed_confirmed": False, "native_result_created": False, "publication_credit": False}
    return {**body, "policy_hash": _POLICY_HASH, "proposal_id": content_hash(value={**body, "policy_hash": _POLICY_HASH})}


def prepare_business_candidates(*, raw_bytes, raw_blob, source_reference, company_id, cik, filing):
    """Rebuild proposals from original source inputs; no supplied quote is trusted."""
    common = dict(raw_bytes=raw_bytes, raw_blob=raw_blob, source_reference=source_reference,
                  company_id=company_id, cik=cik, filing=filing)
    _bound_source(**common)
    proposals = {}
    if filing["form"] in {"DEF 14A", "10-K/A"}:
        governance = governance_source_document(**common)
        proposals["C02"] = board_composition_candidates(document=governance)
    if filing["form"] in {"10-K", "10-K/A"}:
        annual = build_text_document(raw_bytes=raw_bytes, raw_blob=raw_blob, source_reference=source_reference,
            expected_company_id=company_id, expected_cik=cik, expected_period_end=filing["reportDate"])
        proposals["legal_regulatory"] = legal_risk_candidates(document=annual)
        proposals["D04"] = going_concern_candidates(document=annual)
        proposals["reported_facts"] = reported_legal_fact_candidates(**common)
    body = {"record_type": "TEXT_BUSINESS_CANDIDATE_BUNDLE", "company_id": company_id,
            "source_reference_id": source_reference["source_reference_id"], "raw_asset_id": raw_blob["raw_asset_id"],
            "source_filing": filing, "policy_hash": _POLICY_HASH, "proposals": proposals,
            "business_calls": [0, 0, 0], "native_result_created": False, "publication_credit": False}
    return {**body, "candidate_bundle_id": content_hash(value=body)}


def replay_business_candidates(*, bundle, **source_arguments):
    """Verify the proposal bundle by replaying the source parser and rules."""
    rebuilt = prepare_business_candidates(**source_arguments)
    _need(rebuilt == bundle, "TEXT_BUSINESS_CANDIDATE_REPLAY_CHANGED")
    return rebuilt
