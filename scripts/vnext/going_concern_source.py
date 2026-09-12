"""Ordinary D04 source preparation, independent of frozen Run policies.

This component prepares the complete visible original and amendment documents
for semantic review. A source-language candidate, a report-opening match and a
missing keyword are deliberately separate from a D04 judgment. It neither
calls a model nor creates an EvidenceCheck, Review, Result or coverage receipt.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from collections.abc import Mapping
import json
import re

from sec_urls import accession_document_url
from .annual_update import saved_source
from .canonical import canonical_json_bytes, content_hash, sha256_bytes, strict_json_loads, strict_json_file
from .normal_annual_input import prepare_saved_annual_input
from .normal_source_authority import verify_saved_source_proofs
from .sources import raw_blob_record, source_reference_record, resolve_repository_file
from .text_business_candidates import _bound_source, _excerpt, going_concern_candidates
from .text_coverage import build_text_document


METHOD = "GOING_CONCERN_SOURCE_PREPARATION_V1"
# Source payload bytes only: this is not a provider request/token limit. Blocks
# remain whole; a block larger than this size is retained and explicitly marked.
UNIT_SOURCE_BYTES = 65536
_RULES = strict_json_file(path=Path(__file__).resolve().parents[2] / "catalog/r6/going_concern_source_rules_v1.json")
if (_RULES["record_type"] != "GOING_CONCERN_SOURCE_LANGUAGE_RULES"
        or _RULES["schema_version"] != 1 or _RULES["semantic_verdict_authorized"] is not False):
    raise ValueError("D04 source language policy is invalid")
_RULES_HASH = content_hash(value=_RULES)
_LANGUAGE = re.compile(_RULES["language_pattern"], re.I)
_CONCEPT = re.compile(_RULES["concept_pattern"], re.I)
_MONTHS = ("January February March April May June July August September October November December").split()
_DATE = r"(?:" + "|".join(_MONTHS) + r")\s+\d{1,2},\s*\d{4}"
_FINANCIAL_OPENING = re.compile(_RULES["financial_opening_pattern"].replace("{date}", _DATE), re.I)
_CONTEXT_QUALIFIER = re.compile(_RULES["context_qualifier_pattern"], re.I)


class GoingConcernSourceError(ValueError):
    """The source packet cannot be trusted; no business conclusion follows."""


def _need(condition, reason):
    if not condition:
        raise GoingConcernSourceError(reason)


def _json(value):
    # Validate JSON types without applying NFC to verbatim source characters.
    # Semantic IDs still use the existing canonicalizer. The source payload
    # has an additional exact-byte SHA, and replay compares original strings.
    canonical_json_bytes(value=value)
    def plain(item):
        if isinstance(item, Mapping):
            return {k: plain(v) for k,v in item.items()}
        if isinstance(item, (list, tuple)):
            return [plain(v) for v in item]
        return item
    return strict_json_loads(text=json.dumps(plain(value), ensure_ascii=False, allow_nan=False))


def _source_bytes(rows):
    return json.dumps(rows, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")


def _seal(value, key):
    value = _json(value)
    return {**value, key: content_hash(value=value)}


def _name(value):
    # Keep substantive word boundaries; Motor and Credit cannot collapse.
    return tuple(re.findall(r"[a-z0-9]+|&", value.casefold()))


def _cover_name_relation(dei_name, cover_name):
    """A finite name relation, usable only with an explicit same-source cover."""
    marker = re.search(r"\s+/([A-Za-z]{2})/\s*$", dei_name)
    core = dei_name[:marker.start()] if marker else dei_name
    left, right = list(_name(core)), list(_name(cover_name))
    if not left or not right:
        return None
    endings = {"co": "company", "company": "company", "inc": "incorporated",
               "incorporated": "incorporated", "corp": "corporation", "corporation": "corporation"}
    # Legal-form expansion is restricted to the last token. No middle words,
    # subsidiaries, locations or different organizational forms are removed.
    left[-1] = endings.get(left[-1], left[-1])
    right[-1] = endings.get(right[-1], right[-1])
    if left != right:
        return None
    return {"relation": "SAME_SUBSTANTIVE_WORDS_AND_TERMINAL_LEGAL_FORM",
            "removed_dei_terminal_marker": marker[0].strip() if marker else None,
            "marker_jurisdiction_meaning_asserted": False,
            "terminal_legal_form": left[-1]}


def _registrant_name_binding(document, parsed, metadata):
    """Prove an alias using the explicit cover name and current official DEI.

    SEC name markers are not treated as current incorporation states; their
    letters may differ from the jurisdiction reported in the same filing.
    """
    dei_facts, invalid_contexts = [], []
    for fact in parsed.facts:
        namespace, local = metadata.facts[fact["ordinal"]]["concept"]
        if local.casefold() != "entityregistrantname" or not re.fullmatch(r"https?://xbrl\.sec\.gov/dei/\d{4}", namespace):
            continue
        context = parsed.contexts[fact["context_ref"]]
        entity = context["entity_identifier"]
        record = {"namespace": namespace, "fact": dict(fact), "context": dict(context)}
        if (not str(entity).isdigit() or str(int(entity)) != document["cik"]
                or context["period_end"] != document["period_end"]
                or context["dimensions"] or context["typed_dimension_count"]):
            invalid_contexts.append(record)
        else:
            dei_facts.append(record)
    names = sorted({r["fact"]["text"] for r in dei_facts})
    body = {"dei_facts": dei_facts, "invalid_dei_contexts": invalid_contexts,
            "cover_name": None, "cover_caption": None, "relation": None,
            "accepted_source_names": [], "status": "DEI_NAME_MISSING_OR_AMBIGUOUS"}
    if len(names) != 1 or invalid_contexts:
        return body
    body.update(accepted_source_names=names, status="EXACT_DEI_NAME_ONLY")
    blocks = document["blocks"]
    form = next((i for i,b in enumerate(blocks)
                 if re.fullmatch(r"FORM\s+10-K(?:/A)?", b["text"].strip(), re.I) and not b["linked"]), None)
    if form is None:
        return body
    # Cover identity precedes securities listings, body items and signatures.
    end = next((i for i in range(form + 1,len(blocks)) if re.match(
        r"(?:Securities registered|DOCUMENTS INCORPORATED|PART\s+[IVX]+\b|ITEM\s+\d+\b|SIGNATURES\b)",
        blocks[i]["text"].strip(), re.I)), len(blocks))
    captions = [i for i in range(form + 1,end) if re.fullmatch(
        r"\(?Exact name of (?:the )?registrant as specified in its charter\)?", blocks[i]["text"].strip(), re.I)
        and not blocks[i]["linked"]]
    if not captions:
        return body
    if len(captions) != 1:
        body.update(accepted_source_names=[], status="COVER_NAME_AMBIGUOUS")
        return body
    i = captions[0]
    name_block = blocks[i - 1]
    if i - 1 <= form or name_block["linked"] or len(name_block["text"]) > 250:
        body.update(accepted_source_names=[], status="COVER_NAME_STRUCTURE_UNSUPPORTED")
        return body
    body["cover_name"] = _excerpt(document, name_block, "ANNUAL_COVER", ["EXPLICIT_REGISTRANT_CHARTER_NAME"])
    body["cover_caption"] = _excerpt(document, blocks[i], "ANNUAL_COVER", ["EXACT_NAME_OF_REGISTRANT_LABEL"])
    relation = _cover_name_relation(names[0], name_block["text"])
    if relation is None:
        body.update(accepted_source_names=[], status="COVER_DEI_NAME_CONFLICT")
        return body
    body.update(relation=relation, accepted_source_names=sorted(set([*names,name_block["text"]])),
                status="SAME_SOURCE_COVER_AND_CURRENT_DEI_NAME_BOUND")
    return body


def _opening_subject(value):
    value = re.sub(r"\((?:the\s+)?[\"“”]?(?:company|firm|successor|predecessor)[\"“”]?\)", "", value, flags=re.I)
    value = re.sub(r"\s+and (?:its )?(?:subsidiaries|subsidiary companies)\s*$", "", value.strip(), flags=re.I)
    return _name(value)


def _date_text(value):
    d = date.fromisoformat(value)
    return f"{_MONTHS[d.month - 1]} {d.day}, {d.year}"


def _report_openings(document, proposal, name_binding):
    reports = []
    names = {_name(n) for n in name_binding["accepted_source_names"]}
    for source_range in proposal["auditor_report_ranges"]:
        start = source_range["start_block"]
        end = source_range.get("end_block_exclusive", start + 9)
        opening = next((b for b in document["blocks"][start + 1:min(end, start + 9)]
                        if re.match(r"^We have audited\b", b["text"], re.I)), None)
        result = {"range": source_range, "opening": None,
                  "report_kind": "UNRESOLVED", "target_name_match": False,
                  "target_balance_sheet_date_match": False,
                  "identity_status": "OPENING_SYNTAX_UNSUPPORTED",
                  "report_authorship_and_semantics_verified": False}
        if opening:
            result["opening"] = _excerpt(document, opening, "AUDITOR_REPORT", ["AUDIT_OPENING"])
            match = _FINANCIAL_OPENING.match(opening["text"])
            if match:
                result.update(report_kind="FINANCIAL_STATEMENTS",
                    source_subject=match["subject"], source_balance_sheet_date=match["date"],
                    target_name_match=_opening_subject(match["subject"]) in names,
                    target_balance_sheet_date_match=(re.sub(r"\s+", " ", match["date"]).casefold()
                                                      == _date_text(document["period_end"]).casefold()))
                result["identity_status"] = ("TARGET_NAME_AND_CURRENT_BALANCE_SHEET_DATE_MATCHED"
                    if result["target_name_match"] and result["target_balance_sheet_date_match"]
                    else "OTHER_OR_UNRESOLVED_SUBJECT_OR_PERIOD")
            elif re.search(r"^We have audited .*?internal control over financial reporting", opening["text"], re.I):
                result.update(report_kind="INTERNAL_CONTROL", identity_status="NOT_A_FINANCIAL_STATEMENT_AUDIT_OPENING")
        reports.append(result)
    return reports


def _language_candidates(document, name_binding):
    """Match finite complete declarations; never accept a D04 judgment.

    Named/dated statements are useful review candidates, not proof that nearby
    qualifications, later amendments or report attribution are settled.
    Unfamiliar syntax remains supplied in the complete semantic source input.
    """
    candidates = []
    current_date = _date_text(document["period_end"])
    for block in document["blocks"]:
        text = block["text"].strip()
        if not _LANGUAGE.search(text):
            continue
        labels = []
        if re.search(_RULES["valuation_pattern"], text, re.I):
            labels.append("GOING_CONCERN_VALUATION_LANGUAGE")
        if _CONTEXT_QUALIFIER.search(text):
            labels.append("QUALIFIED_OR_OTHER_CONTEXT_LANGUAGE")
        # The whole block must be an explicit dated sentence with the target
        # name as grammatical subject. Embedded examples, pronoun antecedents
        # and date matches elsewhere do not satisfy this. Container quotation
        # and wider discourse remain part of the mandatory semantic review.
        direct = re.fullmatch(_RULES["direct_declaration_pattern"].replace("{date}", _DATE), text, re.I)
        status = "SEMANTIC_REVIEW_REQUIRED"
        if direct and _name(direct[2]) in {_name(n) for n in name_binding["accepted_source_names"]}:
            if re.sub(r"\s+", " ", direct[1]).casefold() == current_date.casefold():
                labels.append("EXPLICIT_NAMED_CURRENT_NEGATIVE_DECLARATION" if direct[3]
                              else "EXPLICIT_NAMED_CURRENT_DOUBT_DECLARATION")
                status = "DIRECT_SOURCE_DECLARATION_CANDIDATE"
            else:
                labels.append("EXPLICIT_OTHER_DATE_DECLARATION")
        candidates.append({**_excerpt(document, block, "FULL_LOCAL_DOCUMENT", labels),
                           "candidate_status": status,
                           "semantic_review_required": True,
                           "current_company_doubt_asserted": False,
                           "not_disclosed_confirmed": False})
    return candidates


def _input_units(document):
    """Supply every visible block in original order without clipping or selection."""
    groups, group, size = [], [], 2  # Compact JSON list brackets.
    for block in document["blocks"]:
        row = [block["block_index"], block["text"]]
        added = len(_source_bytes(row)) + bool(group)
        if group and size + added > UNIT_SOURCE_BYTES:
            groups.append(group); group, size = [], 2
            added = len(_source_bytes(row))
        group.append(row); size += added
    if group:
        groups.append(group)
    units = []
    for i, rows in enumerate(groups):
        source_bytes = _source_bytes(rows)
        nbytes = len(source_bytes)
        units.append(_seal({"ordinal": i, "document_id": document["text_document_id"],
            "source_reference_id": document["source_reference_id"],
            "start_block": rows[0][0], "end_block_exclusive": rows[-1][0] + 1,
            "blocks": rows, "source_payload_bytes": nbytes,
            "source_payload_sha256": sha256_bytes(content=source_bytes),
            "oversized_single_block": nbytes > UNIT_SOURCE_BYTES,
            "provider_request_created": False}, "source_unit_id"))
    return units


def inspect_going_concern_source(*, raw_bytes, raw_blob, source_reference, company_id, cik, filing):
    """Rebuild one source component; this low-level API grants no source admission."""
    parsed, metadata, names = _bound_source(raw_bytes=raw_bytes, raw_blob=raw_blob,
        source_reference=source_reference, company_id=company_id, cik=cik, filing=filing)
    document = build_text_document(raw_bytes=raw_bytes, raw_blob=raw_blob,
        source_reference=source_reference, expected_company_id=company_id,
        expected_cik=cik, expected_period_end=filing["reportDate"])
    proposal = going_concern_candidates(document=document)
    name_binding = _registrant_name_binding(document, parsed, metadata)
    facts = []
    for fact in parsed.facts:
        namespace, local = metadata.facts[fact["ordinal"]]["concept"]
        if _CONCEPT.search(local):
            facts.append({"concept_namespace": namespace, "concept_local_name": local,
                "fact": dict(fact), "context": dict(parsed.contexts[fact["context_ref"]]),
                "source_reference_id": source_reference["source_reference_id"],
                "raw_asset_id": raw_blob["raw_asset_id"],
                "status": "UNMAPPED_CONCEPT_REQUIRES_SEMANTIC_AUTHORITY",
                "boolean_doubt_value_asserted": False})
    units = _input_units(document)
    supplied = [row for unit in units for row in unit["blocks"]]
    _need(supplied == [[b["block_index"], b["text"]] for b in document["blocks"]],
          "GOING_CONCERN_VISIBLE_BLOCK_COVERAGE_CHANGED")
    return _seal({"record_type": "GOING_CONCERN_SOURCE_COMPONENT", "method": METHOD,
        "source_language_rules_hash": _RULES_HASH,
        "metric_id": "D04", "company_id": company_id, "cik": str(int(cik)),
        "source_filing": dict(filing), "registrant_names": names,
        "raw_blob": raw_blob, "source_reference": source_reference, "document": document,
        "navigation": proposal, "registrant_name_binding": name_binding,
        "auditor_openings": _report_openings(document, proposal, name_binding),
        "native_concept_candidates": facts, "language_candidates": _language_candidates(document, name_binding),
        "semantic_source_units": units,
        "input_coverage": {"scope": "ALL_VISIBLE_BLOCKS_OF_THIS_SAVED_DOCUMENT",
            "visible_block_count": len(document["blocks"]),
            "visible_character_count": sum(len(b["text"]) for b in document["blocks"]),
            "source_payload_bytes": sum(u["source_payload_bytes"] for u in units),
            "all_visible_blocks_supplied": True,
            "excluded_markup": ["head", "script", "style", "ix:header", "ix:hidden"],
            "native_fact_stream_inspected_separately": True,
            "semantic_coverage_complete": False,
            "provider_tokens_measured": False},
        "source_admission": "NOT_GRANTED_BY_COMPONENT_API",
        "semantic_review_required": True, "not_disclosed_confirmed": False,
        "clean_opinion_used_as_absence": False, "native_result_created": False,
        "publication_credit": False}, "component_id")


def verify_going_concern_source(*, component, **source_arguments):
    """Rebuild from bytes, including every unselected block and candidate."""
    rebuilt = inspect_going_concern_source(**source_arguments)
    _need(_json(component) == rebuilt, "GOING_CONCERN_SOURCE_REPLAY_CHANGED")
    return rebuilt


def prepare_ordinary_going_concern_source(*, repo_root: Path, company_id: str):
    """Discover and authenticate original + every current-period saved 10-K/A.

    Latest means the existing saved submissions view, not a new SEC fetch.
    Amendments are supplied in full; no claim that they are irrelevant is made.
    The caller cannot choose filings, passages, report identities or answers.
    """
    root = Path(repo_root).resolve()
    prepared = prepare_saved_annual_input(repo_root=root, company_id=company_id)
    filings = [prepared["filing"], *sorted(prepared["amendments"],
        key=lambda f: (f["filingDate"], f["accessionNumber"]))]
    proofs, source_rows = list(prepared["source_proofs"]), []
    for filing in filings:
        url = accession_document_url(cik=int(prepared["entity"]),
            accession=filing["accessionNumber"], document_name=filing["primaryDocument"])
        saved = saved_source(repo_root=root, url=url, accession=filing["accessionNumber"])
        _need(saved is not None, "GOING_CONCERN_REQUIRED_ANNUAL_SOURCE_NOT_SAVED:" + url)
        proof = saved["proof"]
        if proof not in proofs:
            proofs.append(proof)
        source_rows.append((filing, proof))
    admission = verify_saved_source_proofs(data_root=root, proofs=proofs)
    components = []
    for filing, proof in source_rows:
        blob = raw_blob_record(repo_root=root, repo_relative_path=proof["request_repo_relative_path"], media_type="text/html")
        ref = source_reference_record(raw_blob=blob, company_id=company_id,
            source_url=proof["source_url"], accession=filing["accessionNumber"],
            document_name=proof["document_name"], source_role="target_primary" if filing["form"] == "10-K" else "annual_amendment",
            request_attempt_id=proof["request_attempt_id"])
        raw = resolve_repository_file(repo_root=root, repo_relative_path=proof["request_repo_relative_path"]).read_bytes()
        components.append(inspect_going_concern_source(raw_bytes=raw, raw_blob=blob,
            source_reference=ref, company_id=company_id, cik=prepared["entity"], filing=filing))
    return _seal({"record_type": "ORDINARY_GOING_CONCERN_SOURCE_PACKET", "method": METHOD,
        "metric_id": "D04", "company_id": company_id, "prepared_annual_input": prepared,
        "source_proofs": proofs, "source_admission": admission, "components": components,
        "required_filing_accessions": [f["accessionNumber"] for f in filings],
        "required_document_ids": [c["document"]["text_document_id"] for c in components],
        "required_source_unit_ids": [u["source_unit_id"] for c in components for u in c["semantic_source_units"]],
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


def verify_ordinary_going_concern_source(*, packet, repo_root: Path, company_id: str):
    rebuilt = prepare_ordinary_going_concern_source(repo_root=repo_root, company_id=company_id)
    _need(_json(packet) == rebuilt, "ORDINARY_GOING_CONCERN_SOURCE_REPLAY_CHANGED")
    return rebuilt
