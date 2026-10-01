"""Bounded check of the known C02 selection errors in two saved private Runs."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = {
    'paramount': {'positive': (100, 110, 117), 'negative': (168,)},
    'salesforce': {'positive': (919, 933), 'negative': (4300,)},
}
rows = []
for short, expected in CASES.items():
    receipt = json.loads((HERE / ('peer4d-' + short + '-update.json')).read_text())
    state = Path(receipt['state_root'])
    paths = list((state / 'metrics/C02/attempts').glob('*/runs/C02/records.jsonl'))
    assert len(paths) == 1
    records_path = paths[0]
    records = [json.loads(line) for line in records_path.read_text().splitlines()]
    candidate = next(row for row in records if row['record_type'] == 'DETERMINISTIC_TEXT_CANDIDATE')
    evidence = next(row for row in records if row['record_type'] == 'EVIDENCE_CHECK')
    result = next(row for row in records if row['record_type'] == 'METRIC_RESULT'
                  and row['metric_id'] == 'C02')
    source_refs = {row['source_reference_id']: row for row in records
                   if row['record_type'] == 'SOURCE_REFERENCE'}
    raw_blobs = {row['raw_asset_id']: row for row in records
                 if row['record_type'] == 'RAW_BLOB'}
    checks = [check for check in evidence['checks']
              if check['check'].startswith('TEXT_EXACT_EXCERPT:')]
    selected = {index for check in checks for index in check['selected_source_blocks']}
    context = {index for check in checks for index in check['context_source_blocks']}
    positives = []
    for index in expected['positive']:
        matching = [check for check in checks if index in check['selected_source_blocks']]
        assert len(matching) == 1
        check = matching[0]
        role = check['check'].removeprefix('TEXT_EXACT_EXCERPT:')
        claim = candidate['selected'][role]
        reference = source_refs[claim['source_reference_id']]
        blob = raw_blobs[reference['raw_asset_id']]
        raw = (records_path.parents[2] / 'data' / blob['storage_uri']).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == blob['raw_asset_id'].removeprefix('sha256:')
        span = raw[claim['raw_start_byte']:claim['raw_end_byte']]
        assert hashlib.sha256(span).hexdigest() == claim['raw_span_sha256'].removeprefix('sha256:')
        assert claim['text'] in result['value']
        positives.append({'original_block_index': index, 'group_role': role,
                          'group_raw_span_sha256': claim['raw_span_sha256'],
                          'text_excerpt': claim['text'][:190],
                          'source_reference_id': reference['source_reference_id']})
    assert all(index not in selected and index not in context for index in expected['negative'])
    assert result['result_id'] == receipt['result_id']
    rows.append({'company_id': receipt['company_id'], 'period_end': receipt['period_end'],
                 'run_id': receipt['run_id'], 'result_id': receipt['result_id'],
                 'positive_source_checks': positives,
                 'negative_original_block_indices_absent': list(expected['negative']),
                 'original_selected_block_count': len(selected),
                 'context_block_count': len(context),
                 'business_content_acceptance': False, 'current_390_credit': False})
body = {'record_type': 'ISSUE28_C02_PEER4D_KNOWN_SOURCE_DELTA_CHECK',
        'fixed_peer_sha': '4d0b2b9d4718e36ec84ed87588863f98ba5e4bb9',
        'code_head_before_commit': '137ecb24e15ab8f6e7da9beed58ff5c448cb70aa',
        'worktree_contains_uncommitted_peer_reader': True,
        'rows': rows, 'new_real_calls': [0, 0, 0],
        'scope_limit': 'Only listed source blocks and saved Result spans are checked; not all content, '
                       'business acceptance, old Result release or a production Run.'}
(HERE / 'peer4d-known-source-check.json').write_text(
    json.dumps(body, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'status': 'PASS_KNOWN_SOURCE_DELTA',
                  'companies': len(rows), 'new_real_calls': [0, 0, 0]}, sort_keys=True))
