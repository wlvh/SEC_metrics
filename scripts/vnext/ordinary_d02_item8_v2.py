"""Opt-in #28 D02 Item 8 category-mention selection, version 2.

The rule and terms are adapted from #47 commit 147957c4 into a dedicated
ordinary path. The old version 1 policy and installed Runs keep their bytes.
"""
from .canonical import content_hash
from .d02_item8_category_28_v2 import TERMS_HASH, left_out_as_category_mention
from .text_business_candidates import _LEGAL


POLICY = 'D02_ITEM8_CATEGORY_MENTION_28_V2'


def select(*, proposal):
    """Remove only bound Item 8 list mentions, retaining original coverage."""
    if (proposal.get('record_type') != 'LEGAL_REGULATORY_SOURCE_CANDIDATES'
            or proposal.get('proposal_id') != content_hash(value={
                k: v for k, v in proposal.items() if k != 'proposal_id'})):
        raise ValueError('ORDINARY_D02_ORIGINAL_PROPOSAL_CHANGED')
    kept, removed = [], []
    for excerpt in proposal['D02']['candidates']:
        if (excerpt['section_id'] == 'ITEM_8'
                and left_out_as_category_mention(text=excerpt['text'], keyword=_LEGAL)):
            removed.append({'block_index': excerpt['block_index'],
                            'section_id': excerpt['section_id'],
                            'source_reference_id': excerpt['source_reference_id'],
                            'raw_span_sha256': excerpt['raw_span_sha256']})
        else:
            kept.append(excerpt)
    if not removed:
        return proposal
    # D03 uses the same authenticated source scan but does not inherit this
    # D02-only exclusion. All checked ranges and raw-source references remain.
    body = {k: v for k, v in proposal.items() if k != 'proposal_id'}
    body['D02'] = {**proposal['D02'],
                   'finding_status': ('SOURCE_EXCERPTS_FOUND' if kept
                                      else 'NO_SUPPORTED_SOURCE_LANGUAGE'),
                   'candidates': kept}
    body['item_8_category_mentions_left_out'] = {
        'policy': POLICY, 'terms_hash': TERMS_HASH, 'blocks': removed}
    return {**body, 'proposal_id': content_hash(value=body)}
