"""Bind the four omitted source headings to #28's own old Result identity."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]

from vnext.d01_emphasis_source import build_text_document_admitting_underline


def sha(value):
    return hashlib.sha256(value).hexdigest()


old_run = next(Path('/private/tmp/issue28-marriott-current-36-20260929/'
                    'state/metrics/D01/attempts').glob('*/runs/D01'))
new_state = Path('/private/tmp/issue28-d01-emphasis-marriott-20261002')
new_attempt = json.loads((new_state / 'metrics/D01/current.json').read_text())['successful_attempt']
new_run = new_state / 'metrics/D01/attempts' / new_attempt / 'runs/D01'


def records(path):
    return [json.loads(line) for line in (path / 'records.jsonl').read_text().splitlines()]


old, new = records(old_run), records(new_run)
old_candidate = next(row for row in old if row['record_type'] == 'DETERMINISTIC_TEXT_CANDIDATE')
new_candidate = next(row for row in new if row['record_type'] == 'DETERMINISTIC_TEXT_CANDIDATE')
old_result = next(row for row in old if row['record_type'] == 'METRIC_RESULT' and row['metric_id'] == 'D01')
new_result = next(row for row in new if row['record_type'] == 'METRIC_RESULT' and row['metric_id'] == 'D01')
comparison = json.loads((ROOT / 'docs/evidence/issue28_continuous/'
                         'ordinary-marriott-current-36-20260929/comparison.json').read_text())
prior = next(row for row in comparison['rows'] if row['metric_id'] == 'D01')
assert prior['historical_result_id'] == prior['current_result_id'] == old_result['result_id']
assert old_result['result_id'] != new_result['result_id']
before = {claim['text'] for claim in old_candidate['selected'].values()}
after = {claim['text'] for claim in new_candidate['selected'].values()}
assert len(before) == 34 and len(after) == 38 and not before - after
added = sorted(after - before)
assert added == ['Development and Financing Risks', 'General Risk Factors',
                 'Operational Risks',
                 'Technology, Information Protection, and Privacy Risks']
reference = next(row for row in new if row['record_type'] == 'SOURCE_REFERENCE'
                 and row['source_reference_id'] == new_candidate['source_reference_ids'][0])
blob = next(row for row in new if row['record_type'] == 'RAW_BLOB'
            and row['raw_asset_id'] == reference['raw_asset_id'])
raw = (new_run.parents[1] / 'data' / blob['storage_uri']).read_bytes()
assert 'sha256:' + sha(raw) == blob['raw_asset_id'] and len(raw) == blob['byte_length']
target = new_candidate['calculation_target']
document = build_text_document_admitting_underline(
    raw_bytes=raw, raw_blob=blob, source_reference=reference,
    expected_company_id=target['company_id'], expected_cik=target['entity'],
    expected_period_end=target['period_end'])
locators = []
for text in added:
    claim = next(claim for claim in new_candidate['selected'].values()
                 if claim['text'] == text)
    block = document['blocks'][claim['block_index']]
    assert block['leading_emphasis']['text'] == text
    assert block['leading_emphasis']['raw_span_sha256'] == claim['raw_span_sha256']
    assert sha(raw[claim['raw_start_byte']:claim['raw_end_byte']]) == claim['raw_span_sha256']
    locators.append({'text': text, 'block_index': claim['block_index'],
                     'raw_span_sha256': claim['raw_span_sha256']})
body = {'record_type': 'ISSUE28_D01_MARRIOTT_2025_OMITTED_HEADINGS',
        'status': 'CONFIRMED_EXACT_OLD_RESULT_OMITS_FOUR_SOURCE_CATEGORY_HEADINGS',
        'old_result_id': old_result['result_id'], 'old_run_id': json.loads(
            (old_run / 'manifest.json').read_text())['run_id'],
        'new_private_result_id': new_result['result_id'],
        'new_private_run_id': json.loads((new_run / 'manifest.json').read_text())['run_id'],
        'historical_390_same_old_result_id': True,
        'company_id': 'marriott_international', 'period_end': old_result['period_end'],
        'source_reference_id': reference['source_reference_id'],
        'raw_asset_id': blob['raw_asset_id'], 'added_headings': locators,
        'old_count': len(before), 'new_count': len(after),
        'peer_fixed_read': '2b4f571ef18274299145c63b4c355aa97c45d030',
        'new_real_calls': [0, 0, 0], 'old_records_preserved': True,
        'new_private_result_not_current_390_or_production_credit': True}
(HERE / 'audit-marriott.json').write_text(json.dumps(body, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'status': body['status'], 'old_result_id': old_result['result_id'],
                  'new_private_result_id': new_result['result_id'], 'new_count': len(after)}))
