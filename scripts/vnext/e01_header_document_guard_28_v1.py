"""Pinned source-heading guard for the explicit #28 E01 input successor.

The heading algorithm is #47's 0097c911 addition, consuming #28's immutable
488a6173 item reader. #28 regressions also exclude hidden headings and apply
the existing cross-reference words without a case distinction. This neither
classifies M&A nor makes absence claims.
"""
import re

from .deterministic_router import _visible_text
from .e01_item_text_28_v1 import (
    _HEADING, _NONDISPLAY, _REFERENCE_BEFORE, _Visibility, _hidden_by_style,
    _hidden_in_span, _linked_in_span, _need)


PEER_PATCH_SHA = '0097c911df0e3e62fc681b7bfda2385edfc9bfcc'
POLICY = 'STOP_ON_A_CANDIDATE_HEADED_IN_THE_DOCUMENT_BUT_NOT_LISTED_IN_ITS_HEADER'


class _HeadingContext(_Visibility):
    """Add block boundaries to the existing text/visibility/link reader."""
    _BOUNDARIES = frozenset(('body', 'p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                            'li', 'tr', 'td', 'th', 'blockquote', 'pre', 'address',
                            'section', 'article', 'hr'))

    def __init__(self):
        super().__init__()
        self.block_number = 0
        self.node_blocks = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        visible = not (self.stack and self.stack[-1] is not None)
        visible = visible and not (
            tag in _NONDISPLAY or 'hidden' in attributes
            or (attributes.get('aria-hidden') or '').lower() == 'true'
            or _hidden_by_style(re.sub(r'\s+', '', attributes.get('style') or '').lower()))
        if tag in self._BOUNDARIES and visible:
            self.block_number += 1
        super().handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        visible = next((self.stack[i] is None
                        for i in range(len(self.tags) - 1, -1, -1)
                        if self.tags[i] == tag), False)
        super().handle_endtag(tag)
        if tag in self._BOUNDARIES and visible:
            self.block_number += 1

    def handle_data(self, data):
        before = len(self.nodes)
        super().handle_data(data)
        if len(self.nodes) != before:
            self.node_blocks.append(self.block_number)


def headed_item_codes(*, raw_bytes):
    """The document's visible headings, excluding linked contents entries."""
    text = _visible_text(raw_bytes=raw_bytes)
    reader = _HeadingContext()
    reader.feed(raw_bytes.decode('utf-8', errors='replace'))
    reader.close()
    _need(' '.join(node for node, _, _ in reader.nodes) == text,
          'EVENT_ITEM_TEXT_VIEW_NOT_REBUILT')
    nodes, groups, offset = [], [], 0
    for (node, hidden, linked), group in zip(reader.nodes, reader.node_blocks):
        nodes.append((offset, offset + len(node), hidden, linked))
        groups.append(group)
        offset += len(node) + 1
    found = set()
    for match in _HEADING.finditer(text):
        start, end = match.start(), match.end()
        if (_linked_in_span(nodes=nodes, start=start, end=end)
                or _hidden_in_span(nodes=nodes, start=start, end=end) is not None):
            continue
        own_group = next(group for (begin, finish, _, _), group in zip(nodes, groups)
                         if begin <= start < finish)
        context = ' '.join(text[begin:min(finish, start)]
                           for (begin, finish, hidden, _), group in zip(nodes, groups)
                           if group == own_group and hidden is None
                           and begin < start)[-40:]
        if not _REFERENCE_BEFORE.search(context.lower()):
            found.add(match.group(1))
    return found


def check_document_header_items(*, raw_bytes, listed_item_codes,
                                candidate_item_codes, accession):
    headed = headed_item_codes(raw_bytes=raw_bytes)
    unlisted = sorted((headed & set(candidate_item_codes)) - set(listed_item_codes))
    if unlisted:
        raise ValueError('ORDINARY_E01_ITEM_HEADED_BUT_NOT_LISTED:'
                         + accession + ':' + ','.join(unlisted))
    return sorted(headed)
