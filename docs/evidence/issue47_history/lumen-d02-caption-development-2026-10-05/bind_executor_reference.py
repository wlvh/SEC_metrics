"""Bind manual Item 8 decisions after source reading; never a blind response.

The explicit positive set below is the executor's reading. The code checks
source bytes, exact text correspondence and the unchanged answer contract.
It is not a production keyword classifier and is not imported by a reader.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--code-root', type=Path, required=True)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--equivalence-map', type=Path, required=True)
    parser.add_argument('--proxy-document', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.code_root / 'scripts'))
    from vnext.historical_legal_review import validate_answer
    request = json.loads((args.input / 'request.json').read_text())
    document = json.loads((args.input / 'document.json').read_text())
    proxy = json.loads(args.proxy_document.read_text())
    mapping = json.loads(args.equivalence_map.read_text())
    texts = {b['block_id']: b['text'] for b in request['blocks']}
    assert len(texts) == 1782
    assert len(request['must_decide']) == 60
    assert [int(name[1:]) for name in texts] == list(range(900, 2682))
    assert len(mapping['blocks']) == len(texts)
    unmatched = []
    for entry in mapping['blocks']:
        index = entry['annual_block_index']
        assert document['blocks'][index]['text'] == texts['b' + str(index)]
        matches = entry['exact_text_matches_in_previously_fully_read_proxy']
        if matches:
            assert all(proxy['blocks'][i]['text'] == texts['b' + str(index)] for i in matches)
        else:
            unmatched.append(index)
    assert unmatched == mapping['unmatched_blocks']
    assert len(unmatched) == 330
    # Manual decisions: recognition policy and every disclosure/heading/
    # continuation of the actual Note18 proceedings. Finance, commitments,
    # pension settlement and ordinary tax-accounting language are not included.
    in_scope = {1154, 2528, 2529, 2530, 2531, 2533, 2534, 2535, 2536, 2537,
                2538, 2539, 2540, 2541, 2542, 2545, 2546, 2547, 2548, 2549,
                2550, 2551, 2553, 2557, 2558, 2559, 2560, 2561, 2562, 2563}
    also = [2543, 2552, 2554, 2556]

    def quote(index):
        # New executor source-reference quote, never cut from an old answer.
        # The manual IN/OUT judgment precedes this mechanical byte binding.
        text = texts['b' + str(index)]
        if len(text) <= 160:
            return text
        return text[:160].rsplit(' ', 1)[0]

    answer = {'decisions': [
        {'block_id': name,
         'decision': 'IN_SCOPE' if int(name[1:]) in in_scope else 'OUT_OF_SCOPE',
         'quote': quote(int(name[1:])) if int(name[1:]) in in_scope else None}
        for name in request['must_decide']],
        'also_in_scope': [{'block_id': 'b' + str(i), 'quote': quote(i)} for i in also]}
    assert in_scope <= {int(name[1:]) for name in request['must_decide']}
    assert not set(also) & {int(name[1:]) for name in request['must_decide']}
    validate_answer(request=request, raw_output=json.dumps(answer, ensure_ascii=False))
    findings = [
        {'blocks': [1154, 2529, 2530, 2531],
         'judgment': 'Actual litigation/non-income-tax loss recognition and recovery '
                     'policy, 103/141 million accrued comparison, and putative-class '
                     'explanation are in scope. These are not a case-count or total '
                     'liability assertion.'},
        {'blocks': list(range(2533, 2564)),
         'judgment': 'Read the complete principal/other-proceedings passages, '
                     'excluding page numbers 2544/2555. Actual shareholder, '
                     'billing/derivative, outage, Missouri tax, Peruvian/Brazilian '
                     'tax and qui tam matters retain their stated disposition. '
                     'Tax-related court matters are not ordinary tax positions. '
                     'All four nonmandatory positive blocks are explicit here.'},
        {'blocks': [975, 1908, 1990, 2008, 2040, 2072, 2218, 2626],
         'judgment': 'Pension/accounting settlements and asset-retirement liabilities '
                     'do not disclose the legal matters in the definition.'},
        {'blocks': [910, 913, 915, 1032, 1148, 1153, 1182, 1183, 1203, 1206,
                    1317, 1322, 1640, 1836, 1841, 2080, 2081, 2351, 2365,
                    2455, 2461, 2505],
         'judgment': 'Auditor report, a balance-sheet caption, cost policies, '
                     'generic estimates, receivable losses, intangibles, financing '
                     'covenants, investment trades, derivative settlements and '
                     'ordinary unrecognized-tax-benefit accounting are outside '
                     'the disclosure definition. b1153 is the general estimate '
                     'context; b1154 is the actual recognition policy.'},
        {'blocks': list(range(2564, 2579)),
         'judgment': 'Right-of-way and purchase commitments disclose contractual '
                     'purchases without a legal claim. They must not enter merely '
                     'because Note18 contains litigation elsewhere.'},
        {'blocks': [537, 2533, 2558],
         'judgment': 'The Item3 quoted titles still differ from actual Note18 '
                     'captions. This reference judges direct Item8 disclosures; '
                     'it does not resolve the native incorporation boundary, '
                     'supply caption aliases or make its gate pass.'},
    ]
    reference = {
        'record_type': 'ISSUE47_LUMEN_FY2021_FULL_ITEM8_EXECUTOR_DEVELOPMENT_REFERENCE',
        'position': 'lumen_technologies:2021-12-31:D02',
        'request_sha256': hashlib.sha256((args.input / 'request-body.json').read_bytes()).hexdigest(),
        'request_id': request['request_id'], 'raw_asset_id': document['raw_asset_id'],
        'source_reading': {
            'item8_blocks': 1782,
            'previously_read_exact_text_blocks_bound': 1452,
            'unmatched_original_blocks_read_directly': 330,
            'all_60_mandatory_blocks_read_directly': True,
            'full_note18_blocks_2528_to_2578_read_directly': True,
            'equivalence_map_sha256': hashlib.sha256(args.equivalence_map.read_bytes()).hexdigest(),
            'source_images_or_full_grid_equivalence_claimed': False,
            'method': 'Exact text matches to previously fully read, explicitly '
                      'unupdated FY2021 proxy appendix; all unmatched original '
                      'Item8 blocks, mandatory blocks and full Note18 read directly. '
                      'This reuses executor reading, not an independent context.'},
        'contract_answer': answer, 'manual_findings': findings,
        'contract_structure_and_quotes': 'PASS',
        'positive_blocks': sorted(in_scope | set(also)),
        'unresolved': [
            'Native quoted-caption boundary remains unresolved and the normal '
            'entrypoint still refuses. This expanded Item8 question is not its runtime pool.',
            'No independent exact-input method answer, target-model generation, '
            'normal installation or cold-read Result exists for this request.',
            'Complete tables/images and formal D02 source/selection ownership '
            'remain separately unproved; no complete metric acceptance.'],
        'normal_entrypoint_changed': False, 'independent_model_answer': False,
        'old_answers_modified': False, 'runtime_wired': False,
        'new_runs': 0, 'new_acceptances': 0, 'calls': [0, 0, 0],
    }
    args.out.write_text(json.dumps(reference, ensure_ascii=False, indent=1) + '\n')
    print(json.dumps({'mandatory': 60, 'positive': len(in_scope) + len(also),
                      'additional': len(also), 'contract_structure': 'PASS',
                      'independent_model_answer': False, 'calls': [0, 0, 0]}))


if __name__ == '__main__':
    main()
