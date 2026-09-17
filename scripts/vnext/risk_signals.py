"""Source-derived risk-factor headings, before native textual Result binding."""

import re
from typing import Mapping

from .canonical import content_hash
from .text_coverage import TextCoverageError


def risk_factor_headings(*, document: Mapping) -> dict:
    """Return verbatim emphasized items from the entire located Item 1A.

    A source heading is a disclosure, not a finding that the risk has occurred.
    A bold lead sentence is kept separately from its following paragraph. The
    native consumer must reconstruct this document from original source bytes.
    """
    if document.get("text_document_id") != content_hash(value={
            k: v for k, v in document.items() if k != "text_document_id"}):
        raise TextCoverageError("TEXT_DOCUMENT_HASH_CHANGED")
    reasons = list(document["source_reasons"])
    section = document["sections"]["ITEM_1A"]
    if section["status"] != "LOCATED":
        reasons.append("ITEM_1A_" + section["status"])
    headings = []
    normalized_names = {re.sub(r"\W", "", n).casefold()
                        for n in document["registrant_names"]}
    if section["status"] == "LOCATED":
        scope = section["candidates"][0]
        for block in document["blocks"][scope["start_block"]:scope["end_block_exclusive"]]:
            prefix = block["leading_emphasis"]
            if not prefix:
                continue
            text = prefix["text"]
            if (block["linked"]
                    or not re.search(r"[A-Za-z]", text)
                    or re.match(r"^(?:item\s*1a\b|part\s+[ivx]+$)", text, re.I)
                    or re.sub(r"\W", "", text).casefold() in normalized_names):
                continue
            # Page repeats remain inspectable. Only identical title text is
            # grouped, and every original occurrence retains its own locator.
            locator = {"block_index": block["block_index"], **{
                key: prefix[key] for key in (
                    "raw_start_byte", "raw_end_byte", "raw_span_sha256")}}
            match = next((h for h in headings if h["text"] == text), None)
            if match is None:
                headings.append({"text": text, "locators": [locator]})
            else:
                match["locators"].append(locator)
    if not headings:
        reasons.append("RISK_HEADING_STRUCTURE_NOT_IMPLEMENTED")
    result = {"record_type": "RISK_FACTOR_HEADING_PROPOSAL", "metric_id": "D01",
              "company_id": document["company_id"], "period_end": document["period_end"],
              "source_reference_id": document["source_reference_id"],
              "raw_asset_id": document["raw_asset_id"],
              "text_document_id": document["text_document_id"],
              "status": "SOURCE_HEADINGS_READY" if not reasons else "INCOMPLETE",
              "reasons": sorted(set(reasons)), "headings": headings,
              "interpretation": "VERBATIM_EMPHASIZED_ITEM_1A_DISCLOSURES",
              "risk_occurrence_asserted": False, "native_result_created": False,
              "publication_credit": False}
    return {**result, "proposal_id": content_hash(value=result)}
