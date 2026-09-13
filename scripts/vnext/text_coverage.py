"""Read complete local text ranges without turning a search miss into a fact.

This adapter binds ranges to existing RawBlob/SourceReference records.  It
locates numbered annual-report sections in the source itself, excludes linked
contents entries and retains repeated page headings inside the section.  A
complete local scan is deliberately not a legal/risk conclusion, a complete
filing-set certificate, or permission to create a published MetricResult.
"""

from __future__ import annotations

import html
import re
from datetime import date
from html.parser import HTMLParser
from typing import Mapping, Sequence

from .canonical import content_hash, sha256_bytes
from .deterministic_router import parse_accession_xbrl_source
from .records import validate_record
from .resource_limits import RESOURCE_LIMITS
from .sources import validate_public_sec_filing_identity


TEXT_TRANSFORM_VERSION = "1"
_BLOCKS = {"p", "div", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6", "br"}
_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
_HIDDEN = {"script", "style", "head", "ix:header", "ix:hidden"}
_TITLES = {
    "1": r"business", "1A": r"risk factors", "1B": r"unresolved staff comments",
    "1C": r"cybersecurity", "2": r"properties", "3": r"legal proceedings",
    "4": r"mine safety disclosures", "5": r"market for", "6": r"(?:reserved|selected)",
    "7": r"management[’']?s discussion", "7A": r"quantitative and qualitative",
    "8": r"(?:consolidated )?financial statements", "9": r"changes in and disagreements",
    "9A": r"controls and procedures", "9B": r"other information",
    "9C": r"disclosure regarding", "10": r"directors", "11": r"executive compensation",
    "12": r"security ownership", "13": r"certain relationships", "14": r"principal accountant",
    "15": r"exhibits", "16": r"form 10-k summary",
}
# Some reports omit inapplicable 1B/4 entirely. A later, explicitly named
# section still supplies a source boundary; no missing section text is invented.
_SUCCESSOR = {"1A": {"1B", "1C", "2"}, "3": {"4", "5"}, "8": {"9", "9A"}}
_ITEM = re.compile(r"^item\s*(\d{1,2}[ABC]?)\s*[.：:]?\s*(.*?)\s*$", re.I)
_MONTHS = {name: index + 1 for index, name in enumerate(("january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"))}


class TextCoverageError(ValueError):
    """Reject unbound or unsupported source inputs before any semantic use."""


def _need(condition, reason):
    if not condition:
        raise TextCoverageError(reason)


def _period_text(value):
    value = " ".join(str(value).split())
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        match = re.fullmatch(r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})", value)
        _need(match is not None and match.group(1).lower() in _MONTHS,
              "TEXT_DOCUMENT_PERIOD_LEXICAL_UNSUPPORTED")
        try:
            return date(int(match.group(3)), _MONTHS[match.group(1).lower()], int(match.group(2))).isoformat()
        except ValueError as error:
            raise TextCoverageError("TEXT_DOCUMENT_PERIOD_INVALID") from error


class _Blocks(HTMLParser):
    """Keep visible block text and exact UTF-8 source ranges in document order."""

    def __init__(self, text):
        super().__init__(convert_charrefs=False)
        self.text = text
        self.lines = [0] + [m.end() for m in re.finditer("\n", text)]
        self.stack = []
        self.blocks = []
        self.parts = []
        self.structural_errors = []
        self.html_count = self.body_count = self.html_closed = self.body_closed = 0
        self.node_count = 0

    def _offset(self):
        line, column = self.getpos()
        return self.lines[line - 1] + column

    def _flush(self):
        if self.parts:
            value = " ".join("".join(p[2] for p in self.parts).split())
            if value:
                prefix = []
                for part in self.parts:
                    if not part[2].strip() and not prefix:
                        continue
                    if not part[4] and part[2].strip():
                        break
                    prefix.append(part)
                prefix_text = " ".join("".join(p[2] for p in prefix).split())
                self.blocks.append({"text": value, "start": self.parts[0][0],
                                    "end": self.parts[-1][1],
                                    "linked": any(p[3] for p in self.parts),
                                    "emphasized": all(p[4] for p in self.parts
                                                      if p[2].strip()),
                                    "leading_emphasis": ({"text": prefix_text,
                                                          "start": prefix[0][0],
                                                          "end": prefix[-1][1]}
                                                         if prefix_text else None)})
            self.parts = []

    def handle_starttag(self, tag, attrs):
        self.node_count += 1
        _need(self.node_count <= 1000000, "TEXT_NODE_LIMIT")
        _need(len(self.stack) <= 512, "TEXT_NESTING_LIMIT")
        attrs = dict(attrs)
        hidden = (tag in _HIDDEN or "hidden" in attrs or
                  re.search(r"(?:display\s*:\s*none|visibility\s*:\s*hidden)",
                            attrs.get("style", ""), re.I) is not None)
        if tag in _BLOCKS:
            self._flush()
        if tag == "html": self.html_count += 1
        if tag == "body": self.body_count += 1
        emphasized = self.stack[-1][3] if self.stack else False
        if tag in {"b", "strong", "h1", "h2", "h3", "h4", "h5", "h6"}:
            emphasized = True
        weight = re.search(r"(?:^|;)\s*font-weight\s*:\s*([^;]+)",
                           attrs.get("style", ""), re.I)
        if weight:
            token = weight[1].strip().casefold()
            if token in {"bold", "bolder"} or token.isdigit() and int(token) >= 600:
                emphasized = True
            elif token == "normal" or token.isdigit() and int(token) < 600:
                emphasized = False
        if tag not in _VOID:
            self.stack.append((tag, hidden, tag == "a" and bool(attrs.get("href")),
                               emphasized))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in _VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag in _BLOCKS or tag in {"body", "html"}:
            self._flush()
        if tag == "html": self.html_closed += 1
        if tag == "body": self.body_closed += 1
        if tag in _VOID:
            return
        matches = [i for i, entry in enumerate(self.stack) if entry[0] == tag]
        if matches:
            index = matches[-1]
            # HTML permits optional p/li/table closures. Losing an enclosing
            # hidden/root element is not an optional-close repair.
            if any(x[0] in {"body", "html"} or x[1] for x in self.stack[index + 1:]):
                self.structural_errors.append("TEXT_UNCLOSED_STRUCTURAL_ELEMENT")
            del self.stack[index:]
        elif tag in {"body", "html"} | _HIDDEN:
            self.structural_errors.append("TEXT_UNMATCHED_STRUCTURAL_ELEMENT")

    def _part(self, raw):
        if any(row[1] for row in self.stack) or not any(row[0] == "body" for row in self.stack):
            return
        start = self._offset()
        _need(self.text[start:start + len(raw)] == raw, "TEXT_SOURCE_OFFSET_MISMATCH")
        self.parts.append((start, start + len(raw), html.unescape(raw),
                           any(row[2] for row in self.stack),
                           self.stack[-1][3] if self.stack else False))

    def handle_data(self, data):
        self._part(data)

    def handle_entityref(self, name):
        _need(len(name) <= RESOURCE_LIMITS.max_entity_reference_chars, "TEXT_ENTITY_LIMIT")
        raw = "&" + name
        if self.text[self._offset() + len(raw):self._offset() + len(raw) + 1] == ";": raw += ";"
        self._part(raw)

    def handle_charref(self, name):
        _need(len(name) <= RESOURCE_LIMITS.max_entity_reference_chars, "TEXT_ENTITY_LIMIT")
        raw = "&#" + name
        if self.text[self._offset() + len(raw):self._offset() + len(raw) + 1] == ";": raw += ";"
        self._part(raw)


def _heading(blocks, index):
    block = blocks[index]
    if block["linked"]:
        return None
    match = _ITEM.fullmatch(block["text"])
    if match is None:
        return None
    item, title = match.group(1).upper(), match.group(2)
    end_index = index
    if not title and index + 1 < len(blocks) and not blocks[index + 1]["linked"]:
        end_index += 1
        title = blocks[end_index]["text"]
    if item not in _TITLES or len(title) > 180 or not re.match(_TITLES[item], title, re.I):
        return None
    if re.search(r"\bcontinued\b", title, re.I):
        return None
    # Contents lists often separate item, title and page into three cells.
    if end_index + 1 < len(blocks) and re.fullmatch(r"\d+(?:[-–]\d+)?", blocks[end_index + 1]["text"]):
        return None
    if re.search(r"\s\d+(?:[-–]\d+)?\s*$", title):
        return None
    return {"item": item, "block_index": index, "heading_end_index": end_index}


def _byte_offsets(text, positions):
    """Convert only needed character boundaries, in one forward pass."""
    offsets, last, size = {}, 0, 0
    for position in sorted(set(positions)):
        size += len(text[last:position].encode("utf-8"))
        offsets[position] = size
        last = position
    return offsets


def build_text_document(*, raw_bytes: bytes, raw_blob: Mapping,
                        source_reference: Mapping, expected_company_id: str,
                        expected_cik: str, expected_period_end: str) -> dict:
    """Derive annual HTML blocks and closed item boundaries from exact bytes.

    The existing acquisition/Run layer still owns ledger authenticity and the
    complete amendment/source set. A 10-K/A remains explicitly incomplete for
    whole-report coverage, even when its HTML is well formed.
    """
    _need(type(raw_bytes) is bytes and 0 < len(raw_bytes) <= RESOURCE_LIMITS.max_html_bytes,
          "TEXT_SOURCE_SIZE_LIMIT")
    blob, ref = validate_record(record=dict(raw_blob)), validate_record(record=dict(source_reference))
    _need(blob["record_type"] == "RAW_BLOB" and ref["record_type"] == "SOURCE_REFERENCE",
          "TEXT_SOURCE_RECORD_TYPE")
    _need(blob["raw_asset_id"] == ref["raw_asset_id"] == "sha256:" + sha256_bytes(content=raw_bytes)
          and blob["byte_length"] == len(raw_bytes), "TEXT_SOURCE_BYTES_CHANGED")
    _need(ref["company_id"] == expected_company_id, "TEXT_COMPANY_MISMATCH")
    validate_public_sec_filing_identity(raw_blob=blob, source_url=ref["source_url"],
        accession=ref["accession"], document_name=ref["document_name"],
        source_role="target_primary", allowed_ciks=[expected_cik])
    try:
        text = raw_bytes.decode("utf-8-sig", errors="strict")
    except UnicodeError as error:
        raise TextCoverageError("TEXT_ENCODING_UNSUPPORTED") from error
    # The locator always addresses original UTF-8 bytes, including any BOM.
    bom_size = 3 if raw_bytes.startswith(b"\xef\xbb\xbf") else 0
    parsed = parse_accession_xbrl_source(raw_bytes=raw_bytes)
    # The native parser preserves fact values/contexts; the shared attribute
    # adapter resolves namespace declarations, including local rebindings.
    # A custom concept with a DEI-like local name is not identity authority.
    from .governance_signals import _FactAttributes
    metadata = _FactAttributes()
    metadata.feed(text)
    metadata.close()
    _need(metadata.ordinal == len(parsed.facts), "TEXT_IDENTITY_ATTRIBUTE_STREAM_CHANGED")
    identities, periods, forms, names = set(), set(), set(), set()
    for fact in parsed.facts:
        namespace, name = metadata.facts[fact["ordinal"]]["concept"]
        if not re.fullmatch(r"https?://xbrl\.sec\.gov/dei/\d{4}", namespace):
            continue
        name = name.casefold()
        context = parsed.contexts.get(fact["context_ref"], {})
        if name == "entitycentralindexkey" and str(fact["text"]).isdigit():
            identities.add(str(int(fact["text"])))
        if name == "documentperiodenddate":
            periods.add(context.get("period_end"))
            periods.add(_period_text(fact["text"]))
            if str(context.get("entity_identifier", "")).isdigit():
                identities.add(str(int(context["entity_identifier"])))
        if name == "documenttype": forms.add(str(fact["text"]).upper())
        if name == "entityregistrantname": names.add(str(fact["text"]).strip())
    _need(identities == {str(int(expected_cik))}, "TEXT_DOCUMENT_ENTITY_MISMATCH_OR_MISSING")
    _need(periods == {expected_period_end}, "TEXT_DOCUMENT_PERIOD_MISMATCH_OR_MISSING")
    _need(len(forms) == 1 and forms <= {"10-K", "10-K/A"}, "TEXT_DOCUMENT_FORM_UNSUPPORTED")
    parser = _Blocks(text)
    parser.feed(text)
    parser.close()
    parser._flush()
    reasons = list(parser.structural_errors)
    if (parser.html_count, parser.body_count, parser.html_closed, parser.body_closed) != (1, 1, 1, 1):
        reasons.append("TEXT_FRAGMENT_OR_TRUNCATED_DOCUMENT")
    if any(row[0] in {"body", "html"} or row[1] for row in parser.stack):
        reasons.append("TEXT_UNCLOSED_STRUCTURAL_ELEMENT")
    if forms == {"10-K/A"}:
        reasons.append("TEXT_AMENDMENT_SOURCE_SET_REQUIRED")
    blocks = parser.blocks
    positions = [position for b in blocks for position in (b["start"], b["end"])]
    positions += [position for b in blocks if b["leading_emphasis"]
                  for position in (b["leading_emphasis"]["start"],
                                   b["leading_emphasis"]["end"])]
    offsets = _byte_offsets(text, positions)
    for index, block in enumerate(blocks):
        block["block_index"] = index
        block["raw_start_byte"] = offsets[block.pop("start")] + bom_size
        block["raw_end_byte"] = offsets[block.pop("end")] + bom_size
        block["raw_span_sha256"] = sha256_bytes(content=raw_bytes[block["raw_start_byte"]:block["raw_end_byte"]])
        prefix = block["leading_emphasis"]
        if prefix:
            prefix["raw_start_byte"] = offsets[prefix.pop("start")] + bom_size
            prefix["raw_end_byte"] = offsets[prefix.pop("end")] + bom_size
            prefix["raw_span_sha256"] = sha256_bytes(content=raw_bytes[
                prefix["raw_start_byte"]:prefix["raw_end_byte"]])
    headings = [h for i in range(len(blocks)) if (h := _heading(blocks, i)) is not None]
    sections = {}
    for item, next_items in _SUCCESSOR.items():
        candidates = []
        for i, heading in enumerate(headings):
            if heading["item"] != item:
                continue
            following = next((h for h in headings[i + 1:] if h["item"] != item), None)
            if following is None or following["item"] not in next_items:
                continue
            start = heading["heading_end_index"] + 1
            end = following["block_index"]
            if start >= end:
                continue
            candidates.append({"section_id": "ITEM_" + item, "start_block": start,
                               "end_block_exclusive": end, "heading": heading,
                               "closing_heading": following})
        sections["ITEM_" + item] = {"status": "LOCATED" if len(candidates) == 1 else "AMBIGUOUS" if candidates else "MISSING",
                                   "candidates": candidates}
    doc = {"record_type": "LOCAL_TEXT_DOCUMENT", "transform_version": TEXT_TRANSFORM_VERSION,
           "source_reference_id": ref["source_reference_id"], "source_reference": ref,
           "raw_asset_id": blob["raw_asset_id"], "byte_length": len(raw_bytes),
           "company_id": expected_company_id, "cik": str(int(expected_cik)),
           "registrant_names": sorted(names),
           "period_end": expected_period_end, "form": next(iter(forms)),
           "source_state": "INCOMPLETE" if reasons else "COMPLETE_LOCAL_DOCUMENT",
           "source_reasons": sorted(set(reasons)), "blocks": blocks, "sections": sections,
           "semantic_disclosure_verified": False, "publication_credit": False}
    doc["text_document_id"] = content_hash(value=doc)
    return doc


def inspect_text_scope(*, document: Mapping, required_sections: Sequence[str],
                       terms: Sequence[str]) -> dict:
    """Return exact search hits separately from completeness and interpretation.

    Terms are literal, case-insensitive word-bounded search clues. A miss in
    complete ranges means only that these terms were not found there. It must
    never be rendered as NOT_DISCLOSED_CONFIRMED or as absence of business risk.
    """
    _need(document.get("text_document_id") == content_hash(value={k: v for k, v in document.items() if k != "text_document_id"}),
          "TEXT_DOCUMENT_HASH_CHANGED")
    _need(bool(required_sections) and len(set(required_sections)) == len(required_sections)
          and all(s in document["sections"] for s in required_sections), "TEXT_REQUIRED_SECTION_INVALID")
    _need(bool(terms) and len(set(terms)) == len(terms) and all(isinstance(t, str) and t.strip() == t and t for t in terms),
          "TEXT_SEARCH_TERMS_INVALID")
    reasons = list(document["source_reasons"])
    ranges = []
    for section_id in required_sections:
        section = document["sections"][section_id]
        if section["status"] != "LOCATED":
            reasons.append(section_id + "_" + section["status"])
        else:
            ranges.append(section["candidates"][0])
    hits = []
    for scope in ranges:
        for block in document["blocks"][scope["start_block"]:scope["end_block_exclusive"]]:
            matched = [t for t in terms if re.search(r"(?<!\w)" + re.escape(t) + r"(?!\w)", block["text"], re.I)]
            if matched:
                hits.append({"section_id": scope["section_id"], "matched_terms": matched,
                             "text": block["text"], "source_reference_id": document["source_reference_id"],
                             "raw_asset_id": document["raw_asset_id"],
                             **{k: block[k] for k in ("block_index", "raw_start_byte", "raw_end_byte", "raw_span_sha256")}})
    result = {"record_type": "LOCAL_TEXT_SCOPE_SCAN", "text_document_id": document["text_document_id"],
              "required_sections": list(required_sections), "terms": list(terms),
              "coverage_status": "INCOMPLETE" if reasons else "COMPLETE_LOCAL_SECTION_SCAN",
              "coverage_reasons": sorted(set(reasons)), "checked_ranges": ranges,
              "finding_status": "FOUND" if hits else "NOT_FOUND_IN_CHECKED_RANGES",
              "findings": hits, "semantic_disclosure_verified": False,
              "not_disclosed_confirmed": False, "publication_credit": False}
    result["text_scan_id"] = content_hash(value=result)
    return result


def verify_text_document(*, document: Mapping, raw_bytes: bytes, raw_blob: Mapping,
                         source_reference: Mapping, expected_company_id: str,
                         expected_cik: str, expected_period_end: str) -> dict:
    """Replay source bytes, so a self-consistent modified range is insufficient."""
    rebuilt = build_text_document(raw_bytes=raw_bytes, raw_blob=raw_blob,
        source_reference=source_reference, expected_company_id=expected_company_id,
        expected_cik=expected_cik, expected_period_end=expected_period_end)
    _need(rebuilt == document, "TEXT_DOCUMENT_REPLAY_MISMATCH")
    return rebuilt
