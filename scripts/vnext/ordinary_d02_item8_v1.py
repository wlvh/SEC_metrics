"""Opt-in #28 D02 Item 8 category-mention selection.

The immutable rule is adapted from #47 commit 104876d6; its historical route
was first wired at 36c64ab6. The ordinary path owns this versioned copy and
does not import the provider branch's mutable source path. The original D02
selection and old installed Runs keep their original bytes.
"""
from .canonical import content_hash
from .d02_item8_category_28_v1 import TERMS_HASH, left_out_as_category_mention
from .text_business_candidates import _LEGAL


POLICY = 'D02_ITEM8_CATEGORY_MENTION_28_V1'


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
