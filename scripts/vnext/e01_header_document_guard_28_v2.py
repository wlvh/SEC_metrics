"""Explicit source-header guard using the same pinned reader as V3 input."""
from .e01_item_text_28_v2 import headed_item_codes

PEER_PATCH_SHA = '9caada4ed62d02321d32fbb8249407b992de7154'
POLICY = 'STOP_ON_A_CANDIDATE_HEADED_IN_THE_DOCUMENT_BUT_NOT_LISTED_IN_ITS_HEADER'


def check_document_header_items(*, raw_bytes, listed_item_codes,
                                candidate_item_codes, accession):
    headed = headed_item_codes(raw_bytes=raw_bytes)
    unlisted = sorted((headed & set(candidate_item_codes)) - set(listed_item_codes))
    if unlisted:
        raise ValueError('ORDINARY_E01_ITEM_HEADED_BUT_NOT_LISTED:'
                         + accession + ':' + ','.join(unlisted))
    return sorted(headed)
