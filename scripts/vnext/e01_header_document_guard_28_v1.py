"""Pinned source-heading guard for the explicit #28 E01 input successor.

The heading algorithm is #47's 0097c911 addition, consuming #28's immutable
488a6173 item reader. #28 regressions also exclude hidden headings and apply
the existing cross-reference words without a case distinction. This neither
classifies M&A nor makes absence claims.
"""
from .deterministic_router import _visible_text
from .e01_item_text_28_v1 import (
    _REFERENCE_BEFORE, _hidden_in_span, _linked_in_span, _text_nodes, item_headings)


PEER_PATCH_SHA = '0097c911df0e3e62fc681b7bfda2385edfc9bfcc'
POLICY = 'STOP_ON_A_CANDIDATE_HEADED_IN_THE_DOCUMENT_BUT_NOT_LISTED_IN_ITS_HEADER'


def headed_item_codes(*, raw_bytes):
    """The document's visible headings, excluding linked contents entries."""
    text = _visible_text(raw_bytes=raw_bytes)
    nodes = _text_nodes(raw_bytes=raw_bytes, text=text)
    return {code for start, end, code in item_headings(text)
            if not _linked_in_span(nodes=nodes, start=start, end=end)
            and _hidden_in_span(nodes=nodes, start=start, end=end) is None
            and not _REFERENCE_BEFORE.search(text[max(0, start - 40):start].lower())}


def check_document_header_items(*, raw_bytes, listed_item_codes,
                                candidate_item_codes, accession):
    headed = headed_item_codes(raw_bytes=raw_bytes)
    unlisted = sorted((headed & set(candidate_item_codes)) - set(listed_item_codes))
    if unlisted:
        raise ValueError('ORDINARY_E01_ITEM_HEADED_BUT_NOT_LISTED:'
                         + accession + ':' + ','.join(unlisted))
    return sorted(headed)
