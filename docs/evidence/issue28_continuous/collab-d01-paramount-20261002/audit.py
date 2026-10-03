"""Check one peer-reported Paramount D01 truncation against #28's own Run."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
ATTEMPTS = Path('/private/tmp/issue28-paramount_skydance_paramount_global-current-36-cli-20260929/'
                'state/paramount_skydance_paramount_global/metrics/D01/attempts')

def sha(data):
    return hashlib.sha256(data).hexdigest()


candidates = list(ATTEMPTS.glob('*/runs/D01/records.jsonl'))
assert len(candidates) == 1
records_path = candidates[0]
ledger = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/claims.jsonl')
source_log = ROOT / 'evidence/requests_log.csv'
before = (sha(ledger.read_bytes()), sha(source_log.read_bytes()))
records = [json.loads(line) for line in records_path.read_text().splitlines()]
candidate = next(row for row in records if row['record_type'] == 'DETERMINISTIC_TEXT_CANDIDATE')
evidence = next(row for row in records if row['record_type'] == 'EVIDENCE_CHECK')
result = next(row for row in records if row['record_type'] == 'METRIC_RESULT'
              and row['metric_id'] == 'D01')
manifest = json.loads((records_path.parent / 'manifest.json').read_text())
matched = [(role, claim) for role, claim in candidate['selected'].items()
           if claim['block_index'] == 292]
assert len(matched) == 1
role, claim = matched[0]
assert claim['text'] == 'Failures to comply with or changes in U'
assert claim['extent'] == 'LEADING_EMPHASIS' and claim['section_id'] == 'ITEM_1A'
assert claim['text'] in result['value']
assert evidence['status'] == 'PASS'
check = next(x for x in evidence['checks'] if x['check'] == 'TEXT_EXACT_EXCERPT:' + role)
assert check['status'] == 'PASS'
reference = next(x for x in records if x['record_type'] == 'SOURCE_REFERENCE'
                 and x['source_reference_id'] == claim['source_reference_id'])
blob = next(x for x in records if x['record_type'] == 'RAW_BLOB'
            and x['raw_asset_id'] == reference['raw_asset_id'])
raw = (records_path.parents[2] / 'data' / blob['storage_uri']).read_bytes()
assert sha(raw) == blob['raw_asset_id'].removeprefix('sha256:')
assert len(raw) == blob['byte_length']
assert sha(raw[claim['raw_start_byte']:claim['raw_end_byte']]) == claim['raw_span_sha256'].removeprefix('sha256:')
from vnext.text_coverage import build_text_document
document = build_text_document(raw_bytes=raw, raw_blob=blob, source_reference=reference,
                               expected_company_id='paramount_skydance_paramount_global',
                               expected_cik='2041610', expected_period_end='2025-12-31')
original = document['blocks'][292]
assert original['text'].startswith('Failures to comply with or changes in U.S. or foreign laws or regulations')
assert original['leading_emphasis']['text'] == claim['text']
comparison = json.loads((ROOT / 'docs/evidence/issue28_continuous/'
                         'ordinary-paramount-current-36-cli-20260929/comparison.json').read_text())
prior = next(row for row in comparison['rows'] if row['metric_id'] == 'D01')
assert prior['historical_result_id'] == prior['current_result_id'] == result['result_id']
assert '# Risk factor headings' in (ROOT / 'catalog/r6/D01_risk_factor_headings.md').read_text()
assert before == (sha(ledger.read_bytes()), sha(source_log.read_bytes()))
body = {
    'record_type': 'ISSUE28_D01_PARAMOUNT_2025_EXACT_HEADING_TRUNCATION',
    'status': 'CONFIRMED_SELECTED_HEADING_TRUNCATED_AT_UNBOLDED_PERIOD_IN_US',
    'company_id': 'paramount_skydance_paramount_global', 'metric_id': 'D01',
    'period_end': result['period_end'], 'result_id': result['result_id'],
    'run_id': manifest['run_id'], 'quality': result['quality'],
    'historical_index_same_result_id': True,
    'candidate_selected_count': len(candidate['selected']),
    'source_block': 292, 'source_section': claim['section_id'],
    'source_reference_id': reference['source_reference_id'],
    'source_accession': reference['accession'],
    'source_raw_asset_id': blob['raw_asset_id'],
    'selected_span_sha256': claim['raw_span_sha256'],
    'delivered_heading': claim['text'],
    'full_original_block_text': original['text'],
    'full_original_block_raw_span_sha256': original['raw_span_sha256'],
    'original_parser_leading_emphasis': original['leading_emphasis']['text'],
    'peer_lead': {'fixed_commit': '1f3f446c1d3eb299b95c03ec967a4a5224523353',
                  'defect_id': 'D01_PARAMOUNT_2025_HEADING_TRUNCATED_AT_AN_UNBOLDED_PERIOD',
                  'peer_result_credit_not_copied': True},
    'old_run_result_source_preserved': True,
    'new_real_calls': [0, 0, 0],
    'original_ledger_and_source_log_unchanged': True,
    'scope_limit': 'One exact current D01 Result and original heading; not all other D01 headings or a repaired Result.'
}
(HERE / 'audit.json').write_text(json.dumps(body, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({key: body[key] for key in ('status', 'result_id', 'source_block',
                                           'delivered_heading', 'new_real_calls')}, sort_keys=True))
