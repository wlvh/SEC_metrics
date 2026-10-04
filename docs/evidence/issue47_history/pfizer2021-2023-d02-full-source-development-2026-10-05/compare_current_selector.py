"""Compare a frozen executor reference with saved native navigation objects.

Development only: the reference never reaches apply_legal_review or a Run.
The original normal request must be separately rebuilt by the production
functions. Here we check form and measure a manual normal-pool representation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--code-root', type=Path, required=True)
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--reference', type=Path, required=True)
    p.add_argument('--normal-request', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    sys.path.insert(0, str(a.code_root / 'scripts'))
    from vnext.historical_legal_review import validate_answer
    from vnext.continuous_request_context import _load_tokenizer
    reference_bytes = (a.reference / 'executor-reference.json').read_bytes()
    digest = hashlib.sha256(reference_bytes).hexdigest()
    frozen = json.loads((a.reference / 'reference-frozen.json').read_bytes())
    assert digest == frozen['reference_sha256']
    assert frozen['independent_answer_or_current_v4_selector_read_before_freeze'] is False
    proposal = json.loads((a.input / 'incomplete-proposal.json').read_bytes())
    document = json.loads((a.input / 'document.json').read_bytes())
    metadata = json.loads((a.input / 'metadata.json').read_bytes())
    reference = json.loads(reference_bytes)
    assert reference['raw_asset_id'] == metadata['raw_asset_id'] == document['raw_asset_id']
    assert reference['request_sha256'] == metadata['request_sha256']
    question = json.loads((a.normal_request / 'request.json').read_bytes())
    rebuild = json.loads((a.normal_request / 'rebuild.json').read_bytes())
    assert hashlib.sha256((a.normal_request / 'request-body.json').read_bytes()).hexdigest() == rebuild['request_sha256']
    assert question['filing']['raw_asset_id'] == reference['raw_asset_id']
    assert question['period_end'] == reference['position'].split(':')[1]
    texts = {b['block_id']: b['text'] for b in question['blocks']}
    assert all(document['blocks'][int(i[1:])]['text'] == text for i, text in texts.items())
    scope = metadata['item8_range']
    selected = {c['block_index'] for c in proposal['D02']['candidates']}
    selected8 = selected & set(range(scope['start_block'], scope['end_block_exclusive']))
    positive = set(reference['positive_blocks'])
    pool = {int(i[1:]) for i in texts}
    must = set(question['must_decide'])
    old = reference['contract_answer']
    quotes = {e['block_id']: e['quote'] for e in old['decisions'] if e['decision'] == 'IN_SCOPE'}
    quotes.update({e['block_id']: e['quote'] for e in old['also_in_scope']})
    answer = {
        'decisions': [{'block_id': i,
                       'decision': 'IN_SCOPE' if int(i[1:]) in positive else 'OUT_OF_SCOPE',
                       'quote': quotes[i] if int(i[1:]) in positive else None}
                      for i in question['must_decide']],
        'also_in_scope': [{'block_id': 'b' + str(i), 'quote': quotes['b' + str(i)]}
                         for i in sorted(pool & positive) if 'b' + str(i) not in must],
    }
    validate_answer(request=question, raw_output=json.dumps(answer, ensure_ascii=False))
    literal = json.dumps(answer, ensure_ascii=False, separators=(',', ':')) + '\n'
    tokenizer, reason = _load_tokenizer()
    assert tokenizer is not None, reason
    tokens = len(tokenizer.encode(literal, add_special_tokens=False).ids)
    result = {
        'position': reference['position'], 'reference_sha256': digest,
        'reference_frozen_before_comparison': True,
        'normal_navigation_status': proposal['coverage_status'],
        'candidate_count_all_scopes': len(proposal['D02']['candidates']),
        'candidate_count_item8': len(selected8),
        'manual_positive_blocks': len(positive),
        'item8_false_positives': [{'block_index': i, 'text': document['blocks'][i]['text']}
                                for i in sorted(selected8 - positive)],
        'manual_positive_unselected_blocks': sorted(positive - selected8),
        'normal_pool_blocks': len(pool), 'normal_must_decide': len(must),
        'normal_pool_manual_positives': sorted(pool & positive),
        'normal_pool_positive_unselected': sorted((pool & positive) - selected8),
        'manual_positives_outside_review_pool': sorted(positive - pool),
        'normal_executor_reference_output_tokens': tokens,
        'normal_executor_reference_fits': tokens <= 4096,
        'normal_request_sha256': rebuild['request_sha256'],
        'semantic_credit': False, 'old_paid_answers_read_or_modified': False,
        'calls': [0, 0, 0], 'new_runs': 0, 'new_acceptances': 0,
    }
    a.out.mkdir(parents=True, exist_ok=False)
    (a.out / 'current-rule-comparison.json').write_text(json.dumps(result, ensure_ascii=False, indent=1) + '\n')
    (a.out / 'normal-executor-reference.json').write_text(json.dumps(answer, ensure_ascii=False, indent=1) + '\n')
    (a.out / 'normal-executor-reference-compact.json').write_text(literal)
    print(json.dumps({'candidate_count_all_scopes': result['candidate_count_all_scopes'],
                      'false_positive_indices': [e['block_index'] for e in result['item8_false_positives']],
                      'manual_positive_unselected_blocks': result['manual_positive_unselected_blocks'],
                      'normal_reference_output_tokens': tokens}))


if __name__ == '__main__':
    main()
