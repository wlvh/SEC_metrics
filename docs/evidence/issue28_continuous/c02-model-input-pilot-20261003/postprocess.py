"""Mechanical source quotation preview; no semantic or native acceptance.

Reuse the existing complete-block grouping. Model facts and unresolved entries
remain unchanged; shared citation blocks are one source view, not duplicate
facts. This development script is not in production execution authority.
"""
import hashlib
import json
from pathlib import Path

from vnext.c02_grouped_source import grouped_governance_source
from vnext.canonical import content_hash
from vnext.text_business_candidates import governance_source_document, _excerpt
from prepare_input import DEFAULT, SOURCE_SHA

KINDS = {'board_size', 'board_membership', 'board_independence',
         'board_leadership', 'committee_structure', 'committee_membership',
         'committee_independence', 'member_qualification', 'membership_change'}


def preview(*, response, document, raw):
    if type(response) is not dict or set(response) != {'facts', 'unresolved'}:
        raise ValueError('DEVELOPMENT_RESPONSE_SHAPE')
    if type(response['facts']) is not list or not 0 < len(response['facts']) <= 64:
        raise ValueError('DEVELOPMENT_FACT_BOUND')
    if type(response['unresolved']) is not list:
        raise ValueError('DEVELOPMENT_UNRESOLVED_SHAPE')
    selected, seen = set(), set()
    for entries, fields in [(response['facts'], {'kind', 'statement', 'source_blocks', 'stated_time'}),
                            (response['unresolved'], {'source_blocks', 'reason'})]:
        for item in entries:
            if type(item) is not dict or set(item) != fields:
                raise ValueError('DEVELOPMENT_ENTRY_SHAPE')
            ids = item['source_blocks']
            if (type(ids) is not list or not ids or len(ids) != len(set(ids))
                    or any(type(i) is not int or not 0 <= i < len(document['blocks']) for i in ids)):
                raise ValueError('DEVELOPMENT_REFERENCE_INVALID')
            if any(type(item[k]) is not str or not item[k].strip() for k in fields - {'source_blocks'}):
                raise ValueError('DEVELOPMENT_FIELD_INVALID')
            if 'kind' in item:
                if item['kind'] not in KINDS:
                    raise ValueError('DEVELOPMENT_KIND_INVALID')
                identity = (item['kind'], item['statement'], tuple(sorted(ids)), item['stated_time'])
                if identity in seen:
                    raise ValueError('DEVELOPMENT_EXACT_DUPLICATE_FACT')
                seen.add(identity)
                selected.update(ids)
    proposal = {'document_id': document['text_document_id'],
        'source_reference_id': document['source_reference_id'],
        'kind': 'DEVELOPMENT_SOURCE_QUOTATIONS',
        'candidates': [_excerpt(document, document['blocks'][i],
                       'GOVERNANCE_DISCLOSURES', ['MODEL_DEVELOPMENT_CITATION'])
                       for i in sorted(selected)]}
    proposal['proposal_id'] = content_hash(value=proposal)
    coverage = {'document_id': document['text_document_id'],
                'source_reference_id': document['source_reference_id'],
                'scope': 'COMPLETE_SOURCE_INPUT_NOT_SEMANTIC_ABSENCE'}
    coverage['coverage_hash'] = content_hash(value=coverage)
    _, grouped, scope = grouped_governance_source(document=document,
        proposal=proposal, coverage=coverage, raw_bytes=raw)
    chars = sum(len(x['text']) for x in grouped['candidates'])
    if len(grouped['candidates']) > 64 or chars > 64000:
        raise ValueError('DEVELOPMENT_QUOTATION_BOUND_NO_TRUNCATION')
    return {'status': 'DEVELOPMENT_QUOTATION_PREVIEW_ONLY',
        'facts_and_unresolved_unchanged': response,
        'unique_cited_blocks': len(selected), 'quote_groups': grouped['candidates'],
        'quote_characters': chars, 'source_partition': scope,
        'native_result_created': False, 'semantic_acceptance': False,
        'target_model_verified': False, 'new_business_calls': [0, 0, 0]}


def original(input_dir, *, attempt=DEFAULT, company_id='enphase_energy', cik='1463101',
             expected_source_sha=SOURCE_SHA):
    meta = json.loads((input_dir / 'metadata.json').read_text())
    raw = (attempt / 'data' / meta['raw_blob']['storage_uri']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == meta['source_sha256'] == expected_source_sha
    doc = governance_source_document(raw_bytes=raw, raw_blob=meta['raw_blob'],
        source_reference=meta['source_reference'], company_id=company_id,
        cik=cik, filing=meta['filing'])
    expected = '\n'.join('[B{}]\n{}\n'.format(i, b['text']) for i, b in enumerate(doc['blocks']))
    assert (input_dir / 'source.txt').read_text() == expected
    assert hashlib.sha256(expected.encode()).hexdigest() == meta['input_sha256']
    return raw, doc


if __name__ == '__main__':
    root = Path(__file__).parent
    raw, doc = original(Path('/private/tmp/issue28-c02-blind-source-pilot2-20261003'))
    response = json.loads((root / 'independent-input-76da71e/response-v2.log').read_text())
    result = preview(response=response, document=doc, raw=raw)
    (root / 'quotation-preview.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'fact_count': len(response['facts']),
                     'unresolved': len(response['unresolved']),
                     'quote_groups': len(result['quote_groups']),
                     'unique_cited_blocks': result['unique_cited_blocks'],
                     'quote_characters': result['quote_characters']}))
