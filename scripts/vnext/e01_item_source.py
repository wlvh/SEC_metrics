"""Opt-in, source-bound Item 8.01 body for the pending E01 successor.

This does not classify an event or change the frozen item-code route. A
header-listed 8.01 currently has only a synthesized brief; callers can use
this explicit source record to inspect its original primary section.
"""
import re

from .canonical import content_hash, sha256_bytes
from .deterministic_router import (_reference, _require_raw_bytes,
                                   _visible_text, validate_verified_claim)


def _need(condition, reason):
    if not condition:
        raise ValueError('E01_ITEM_SOURCE_' + reason)


def _visible_801_section(raw_bytes):
    """Return a full normalized visible section, or stop on uncertain bounds."""
    _need(type(raw_bytes) is bytes, 'PRIMARY_BYTES_REQUIRED')
    visible = _visible_text(raw_bytes=raw_bytes)
    mentions = list(re.finditer(r'\bItem\s+8\.01\b', visible, re.I))
    headings = list(re.finditer(r'\bItem\s+8\.01\s+Other Events\b',
                                visible, re.I))
    _need(len(mentions) == len(headings) == 1,
          'ITEM_801_HEADING_MISSING_OR_AMBIGUOUS')
    start = headings[0].start()
    after = visible[headings[0].end():]
    next_901 = re.search(r'\bItem\s+9\.01\s+Financial Statements and Exhibits\b',
                         after, re.I)
    boundaries = ([headings[0].end()+next_901.start()]
                  if next_901 is not None else [])
    signatures = re.search(r'\bSIGNATURES\b', after)
    if signatures is not None:
        boundaries.append(headings[0].end()+signatures.start())
    _need(bool(boundaries), 'ITEM_801_SECTION_END_UNPROVEN')
    end = min(boundaries)
    _need(re.search(r'\bItem\s+\d{1,2}\.\d{2}\b',
                    visible[headings[0].end():end], re.I) is None,
          'ITEM_801_BOUNDARY_AMBIGUOUS')
    section = visible[start:end].strip()
    payload = visible[headings[0].end():end].strip().lstrip('.:-–— ').strip()
    _need(bool(payload) and end > start, 'ITEM_801_SECTION_EMPTY')
    return {'section_text': section, 'start_char': start, 'end_char': end,
            'visible_text_sha256': sha256_bytes(content=visible.encode('utf-8'))}


def bound_801_primary_section(*, claim, primary_source_reference,
                              primary_document_bytes):
    """Bind one old header claim to its complete original-body visible text.

    The old claim and source identity are preserved. This is input to a future
    E01 content review, not an E01 match or a native Result.
    """
    selected = validate_verified_claim(claim=claim)
    reference = _reference(value=primary_source_reference)
    _need(selected['claim_kind'] == 'DETERMINISTIC_8K_ITEM_BRIEF'
          and selected['attributes']['item_code'] == '8.01',
          'ITEM_801_VERIFIED_CLAIM_REQUIRED')
    _need(selected['attributes']['primary_source_reference_id'] ==
          reference['source_reference_id']
          and selected['company_id'] == reference['company_id']
          and selected['attributes']['accession'] == reference['accession']
          and reference['source_role'] == 'fy_8k_primary',
          'PRIMARY_REFERENCE_CHANGED')
    _require_raw_bytes(source_reference=reference,
                       raw_bytes=primary_document_bytes)
    section = _visible_801_section(primary_document_bytes)
    body = {'record_type': 'E01_VERIFIED_PRIMARY_ITEM_801_SECTION_V1',
        'item_code': '8.01',
        'verified_claim_id': selected['verified_claim_id'],
        'primary_source_reference_id': reference['source_reference_id'],
        'primary_raw_asset_id': reference['raw_asset_id'],
        'company_id': reference['company_id'],
        'accession': reference['accession'],
        'section_text': section['section_text'],
        'section_text_sha256': sha256_bytes(
            content=section['section_text'].encode('utf-8')),
        'visible_text_sha256': section['visible_text_sha256'],
        'start_char': section['start_char'],
        'end_char': section['end_char'],
        'source_acquisition_credit': False,
        'metric_result_created': False,
        'production_authorized': False}
    return {**body, 'section_id': content_hash(value=body)}


def verify_bound_801_primary_section(*, section, claim,
                                     primary_source_reference,
                                     primary_document_bytes):
    """Rebuild a saved section from its authenticated original before reuse."""
    rebuilt = bound_801_primary_section(
        claim=claim, primary_source_reference=primary_source_reference,
        primary_document_bytes=primary_document_bytes)
    _need(type(section) is dict and section == rebuilt, 'SECTION_CHANGED')
    return rebuilt
