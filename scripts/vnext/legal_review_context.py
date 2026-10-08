"""Successor D02 context preparation and source-responsibility postprocessing.

V1 stays unchanged. The model decides scope from full supplied context; this
module checks quotes and partitions original block identities. It does not
prove that the caller's source responsibilities cover the complete metric.
"""
from .canonical import content_hash
from .legal_review_contract import (
    CONTRACT as V1_CONTRACT, _need, block_id,
    review_request, validate_answer, reviewed_blocks)

CONTRACT = 'D02_ITEM_8_CONTEXT_REVIEW_V2'
# The generic instruction already tested on saved Pfizer and Marriott inputs.
SCOPE_CLARIFICATION = '''
For the definition above, separate the legal matter itself or its loss/exposure policy from another accounting measurement that merely names legal or tax contingencies. A general acquisition-date contingent-liability recognition or fair-value framework is not itself a disclosure of an actual legal matter. A tax-asset or tax-benefit amount arising from legal reserves remains a tax measurement unless its text discloses the legal matter or its loss policy. Ordinary uncertain-tax-position estimates, tax-benefit reconciliations, statute expirations, routine audit closings and the word settlement do not by themselves establish a qualifying legal proceeding or governmental investigation; language saying a process can involve legal proceedings describes possibility, not that such a proceeding exists. Do count affirmed actual appeals, investigations, proceedings and related loss policies if the text supports them, including tax matters: do not include or exclude the whole tax category. Read legal/product-liability insurance, recovery, coverage and self-insurance disclosures in context; a policy addressing those exposures may count even without repeating lawsuit vocabulary. A heading counts when it introduces or continues the qualifying disclosure, rather than admitting all unrelated table rows in a mixed note. Apply the same actual-matter distinction to ordinary commercial revenue adjustments/true-ups. Preserve negations, conditions, time and subject in judging scope. All original response fields, complete must_decide coverage and exact 20–300 character quote requirements remain unchanged.'''


def review_context_request(*, company_id, target_cik, period_end, document,
                           context_pool, responsibility_pool, keyword_admitted):
    """Supply full context and preserve the existing route's block ownership."""
    _need(list(responsibility_pool) == sorted(set(responsibility_pool))
          and set(responsibility_pool) <= set(context_pool),
          'D02_CONTEXT_RESPONSIBILITY_OUTSIDE_CONTEXT')
    request = review_request(company_id=company_id, target_cik=target_cik,
        period_end=period_end, document=document, pool=context_pool,
        keyword_admitted=keyword_admitted)
    body = {k:v for k,v in request.items() if k != 'request_id'}
    body.update(contract=CONTRACT,
        responsibility_block_ids=[block_id(i) for i in responsibility_pool],
        system_prompt=request['system_prompt']+SCOPE_CLARIFICATION)
    return {**body, 'request_id':content_hash(value=body)}


def validate_context_answer(*, request, raw_output):
    """Explicit successor adapter for the same V1 decision/quote checks."""
    _need(request.get('contract') == CONTRACT, 'D02_CONTEXT_REQUEST_CONTRACT_CHANGED')
    blocks = [b['block_id'] for b in request['blocks']]
    owned = request.get('responsibility_block_ids')
    _need(type(owned) is list and len(owned) == len(set(owned))
          and set(owned) <= set(blocks), 'D02_CONTEXT_RESPONSIBILITY_OUTSIDE_CONTEXT')
    # V1 itself continues to refuse the successor contract. This adapter only
    # selects its mechanical checks, without changing saved responses.
    return validate_answer(request={**request, 'contract':V1_CONTRACT}, raw_output=raw_output)


def responsible_reviewed_blocks(*, request, raw_output):
    """Partition source identities for deduplication; no new semantic vote."""
    decisions, added = validate_context_answer(request=request, raw_output=raw_output)
    counted, reason, unsettled = reviewed_blocks(request=request, decisions=decisions, added=added)
    owned = set(request['responsibility_block_ids'])
    return {'in_scope':counted,
        'owned_in_scope':None if counted is None else [b for b in counted if b in owned],
        'other_responsibility_in_scope':None if counted is None else [b for b in counted if b not in owned],
        'reason':reason, 'unsettled':unsettled,
        'source_responsibility_completeness_proven':False}
