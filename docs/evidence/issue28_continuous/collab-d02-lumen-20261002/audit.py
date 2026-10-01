"""Bound one peer-reported D02 defect to #28's own exact Result and source."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
STATE = Path('/private/tmp/issue28-lumen_technologies-current-36-cli-20260929/state/lumen_technologies')
RECORDS = (STATE / 'metrics/D02/attempts/44cca0bca8ab47418e2f2857405ea108/'
           'runs/D02/records.jsonl')
MANIFEST = RECORDS.parent / 'manifest.json'
EXPECTED_TEXT = ('In the normal course of our business, we incur costs to hire and retain '
                 'external legal counsel to advise us on finance, regulatory, litigation, '
                 'and other matters. Subject to certain exceptions, we expense these costs '
                 'as the related services are received.')

def sha(data):
    return hashlib.sha256(data).hexdigest()


ledger = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/claims.jsonl')
source_log = ROOT / 'evidence/requests_log.csv'
before = {'ledger': sha(ledger.read_bytes()), 'source_log': sha(source_log.read_bytes())}
rows = [json.loads(line) for line in RECORDS.read_text().splitlines()]
candidate = next(row for row in rows if row['record_type'] == 'DETERMINISTIC_TEXT_CANDIDATE')
evidence = next(row for row in rows if row['record_type'] == 'EVIDENCE_CHECK')
result = next(row for row in rows if row['record_type'] == 'METRIC_RESULT'
              and row['metric_id'] == 'D02')
manifest = json.loads(MANIFEST.read_text())
matched = [(role, claim) for role, claim in candidate['selected'].items()
           if claim['text'] == EXPECTED_TEXT]
assert len(matched) == 1
role, claim = matched[0]
assert claim['block_index'] == 1670 and EXPECTED_TEXT in result['value']
assert evidence['status'] == 'PASS'
check = next(check for check in evidence['checks']
             if check['check'] == 'TEXT_EXACT_EXCERPT:' + role)
assert check['status'] == 'PASS'
reference = next(row for row in rows if row['record_type'] == 'SOURCE_REFERENCE'
                 and row['source_reference_id'] == claim['source_reference_id'])
blob = next(row for row in rows if row['record_type'] == 'RAW_BLOB'
            and row['raw_asset_id'] == reference['raw_asset_id'])
raw_path = RECORDS.parents[2] / 'data' / blob['storage_uri']
raw = raw_path.read_bytes()
assert sha(raw) == reference['raw_asset_id'].removeprefix('sha256:')
assert len(raw) == blob['byte_length']
assert sha(raw[claim['raw_start_byte']:claim['raw_end_byte']]) == claim['raw_span_sha256'].removeprefix('sha256:')
comparison = json.loads((ROOT / 'docs/evidence/issue28_continuous/'
                         'ordinary-lumen-current-36-cli-20260929/comparison.json').read_text())
same = next(row for row in comparison['rows'] if row['metric_id'] == 'D02')
assert same['historical_result_id'] == same['current_result_id'] == result['result_id']
spec = (ROOT / 'catalog/r6/D02_legal_disclosures_v1.md').read_text()
assert '# Litigation source disclosures' in spec
after = {'ledger': sha(ledger.read_bytes()), 'source_log': sha(source_log.read_bytes())}
assert before == after
body = {
    'record_type': 'ISSUE28_D02_LUMEN_2025_EXACT_RESULT_DEFECT_AUDIT',
    'status': 'CONFIRMED_OUT_OF_SCOPE_LEGAL_COUNSEL_COST_POLICY_IN_D02_RESULT',
    'company_id': 'lumen_technologies', 'metric_id': 'D02',
    'period_start': result['period_start'], 'period_end': result['period_end'],
    'result_id': result['result_id'], 'run_id': manifest['run_id'],
    'private_result_quality': result['quality'],
    'historical_index_same_result_id': True,
    'candidate_selected_count': len(candidate['selected']),
    'source_block': 1670, 'source_section_id': claim['section_id'],
    'candidate_role': role,
    'source_reference_id': reference['source_reference_id'],
    'source_accession': reference['accession'],
    'source_url': reference['source_url'],
    'source_raw_asset_id': reference['raw_asset_id'],
    'source_byte_length': len(raw),
    'source_raw_span_sha256': claim['raw_span_sha256'],
    'selected_text_sha256': sha(claim['text'].encode('utf-8')),
    'selected_text': claim['text'],
    'reason': 'This is an accounting policy for external legal counsel costs in several advisory areas, not a proceeding, claim, litigation event or accrued litigation amount.',
    'peer_lead': {'fixed_commit': '1f3f446c1d3eb299b95c03ec967a4a5224523353',
                  'defect_id': 'D02_LUMEN_2025_KEYWORD_PROXY_ADMITS_LEGAL_FEE_POLICY',
                  'not_peer_acceptance_credit': True},
    'old_run_and_result_preserved': True, 'new_real_calls': [0, 0, 0],
    'original_ledger_and_source_log_unchanged': True,
    'scope_limit': 'One exact Result and one confirmed wrong excerpt; not a full D02 content audit or a finding about every company.'
}
(HERE / 'audit.json').write_text(json.dumps(body, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({key: body[key] for key in ('status', 'company_id', 'period_end',
                                           'result_id', 'source_block', 'new_real_calls')},
                 sort_keys=True))
