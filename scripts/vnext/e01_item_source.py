"""Opt-in, source-bound Item 8.01 body for the pending E01 successor.

This does not classify an event or change the frozen item-code route. A
header-listed 8.01 currently has only a synthesized brief; callers can use
this explicit source record to inspect its original primary section.
"""
from html.parser import HTMLParser
import re

from .canonical import content_hash, sha256_bytes
from .deterministic_router import (_reference, _require_raw_bytes,
                                   validate_verified_claim)


def _need(condition, reason):
    if not condition:
        raise ValueError('E01_ITEM_SOURCE_' + reason)


_VOID_TAGS = frozenset(('area', 'base', 'br', 'col', 'embed', 'hr', 'img',
                        'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'))
_NONDISPLAY_TAGS = frozenset(('head', 'script', 'style', 'template',
                              'noscript', 'svg', 'ix:hidden'))
_HEADING_TAGS = frozenset(('p', 'div', 'tr', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'))
_ITEM_HEADING = re.compile(r'^Item\s+(\d{1,2}\.\d{2})\s+(.+?)\.?$', re.I)


class _ItemSectionParser(HTMLParser):
    """Keep text positions and actual block boundaries, excluding hidden DOM."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.words = []
        self.blocks = []
        self.stack = []
        self.uncertain_visibility = False

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == 'style' or (tag == 'link' and
                              'stylesheet' in (attributes.get('rel') or '').lower()):
            self.uncertain_visibility = True
        style = re.sub(r'\s+', '', attributes.get('style') or '').lower()
        hidden = (bool(self.stack and self.stack[-1]['hidden'])
                  or tag in _NONDISPLAY_TAGS or 'hidden' in attributes
                  or (attributes.get('aria-hidden') or '').lower() == 'true'
                  or 'display:none' in style or 'visibility:hidden' in style
                  or 'content-visibility:hidden' in style
                  or bool(re.search(r'(?:^|;)opacity:0(?:;|$)', style)))
        emphasized = (tag in ('b', 'strong') or bool(re.search(
            r'(?:^|;)font-weight:(?:bold|[6-9]00)(?:;|$)', style)))
        if emphasized and not hidden:
            for ancestor in self.stack:
                ancestor['emphasized'] = True
        if tag not in _VOID_TAGS:
            self.stack.append({'tag': tag, 'start': len(self.words),
                               'hidden': hidden, 'emphasized': emphasized})

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in _VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        matching = next((i for i in range(len(self.stack)-1, -1, -1)
                         if self.stack[i]['tag'] == tag), None)
        if matching is None:
            return
        for element in reversed(self.stack[matching:]):
            if not element['hidden'] and element['tag'] in _HEADING_TAGS:
                self.blocks.append((element['start'], len(self.words),
                                    element['emphasized'] or
                                    element['tag'] in ('h1', 'h2', 'h3', 'h4',
                                                       'h5', 'h6'),
                                    element['tag']))
        del self.stack[matching:]

    def handle_data(self, data):
        if not self.stack or not self.stack[-1]['hidden']:
            self.words.extend(data.split())


def _visible_801_section(raw_bytes):
    """Return complete text between proven visible block headings, or stop."""
    _need(type(raw_bytes) is bytes, 'PRIMARY_BYTES_REQUIRED')
    parser = _ItemSectionParser()
    parser.feed(raw_bytes.decode('utf-8', errors='replace'))
    parser.close()
    _need(not parser.uncertain_visibility, 'VISIBILITY_UNPROVEN')
    visible = ' '.join(parser.words)
    headings = {}
    for start, end, emphasized, tag in parser.blocks:
        if start == end or not emphasized:
            continue
        block = ' '.join(parser.words[start:end]).strip()
        match = _ITEM_HEADING.fullmatch(block)
        if match is not None:
            headings.setdefault((start, end),
                                (match.group(1), match.group(2), tag))
        elif block.upper() == 'SIGNATURES':
            headings.setdefault((start, end), ('SIGNATURES', '', tag))
    starts = [(start, end, tag) for (start, end), (code, title, tag)
              in headings.items()
              if code == '8.01' and title.lower() == 'other events']
    _need(len(starts) == 1, 'ITEM_801_HEADING_MISSING_OR_AMBIGUOUS')
    start_word, heading_end, heading_tag = starts[0]
    after = sorted((begin, code, title) for (begin, _), (code, title, tag)
                   in headings.items() if begin >= heading_end
                   and tag == heading_tag)
    _need(bool(after), 'ITEM_801_SECTION_END_UNPROVEN')
    end_word, end_code, end_title = after[0]
    _need(end_code == 'SIGNATURES' or
          (end_code == '9.01' and
           end_title.lower() == 'financial statements and exhibits'),
          'ITEM_801_BOUNDARY_AMBIGUOUS')
    _need(not any(code == '9.01' for _, code, _ in after[1:]),
          'ITEM_801_BOUNDARY_AMBIGUOUS')
    _need(not any(heading_end <= begin < end_word
                  for (begin, _), (_, _, tag) in headings.items()
                  if tag != heading_tag), 'ITEM_801_BOUNDARY_AMBIGUOUS')
    _need(end_word > heading_end, 'ITEM_801_SECTION_EMPTY')
    section = ' '.join(parser.words[start_word:end_word])
    start = len(' '.join(parser.words[:start_word])) + (1 if start_word else 0)
    end = start + len(section)
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
