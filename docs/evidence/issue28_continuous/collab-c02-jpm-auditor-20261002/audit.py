"""Exact #28 JPMorgan C02 auditor-retention excerpt in two old Results."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
SOURCE = next(Path('/private/tmp/issue28-jpmorgan_chase-current-36-cli-20260929').glob(
    'state/jpmorgan_chase/metrics/C02/attempts/*/runs/C02/records.jsonl'))
records = [json.loads(line) for line in SOURCE.read_bytes().splitlines()]
candidate = next(row for row in records if row['record_type'] == 'DETERMINISTIC_TEXT_CANDIDATE')
evidence = next(row for row in records if row['record_type'] == 'EVIDENCE_CHECK')
result = next(row for row in records if row['record_type'] == 'METRIC_RESULT'
              and row['metric_id'] == 'C02')
manifest = json.loads((SOURCE.parent/'manifest.json').read_text())
assert result['quality'] == 'EXACT' and result['publication'] == 'PUBLISHED'
assert evidence['status'] == 'PASS'
matches = [(role,row) for role,row in candidate['selected'].items()
           if row['block_index'] == 3367]
assert len(matches) == 1
role, claim = matches[0]
assert claim['section_id'] == 'GOVERNANCE_DISCLOSURES'
assert 'continued retention of PwC as the Firm’s independent external auditor' in claim['text']
assert 'The Board believes the Firm receives significant benefits' in claim['text']
references = {row['source_reference_id']:row for row in records
              if row['record_type'] == 'SOURCE_REFERENCE'}
blobs = {row['raw_asset_id']:row for row in records if row['record_type'] == 'RAW_BLOB'}
reference = references[claim['source_reference_id']]
blob = blobs[reference['raw_asset_id']]
path = ROOT/blob['storage_uri']
if not path.exists():
    path = SOURCE.parents[2]/'data'/blob['storage_uri']
raw = path.read_bytes()
assert len(raw) == blob['byte_length']
assert 'sha256:'+hashlib.sha256(raw).hexdigest() == blob['raw_asset_id']
span = raw[claim['raw_start_byte']:claim['raw_end_byte']]
assert hashlib.sha256(span).hexdigest() == claim['raw_span_sha256'].removeprefix('sha256:')
assert reference['company_id'] == 'jpmorgan_chase'
comparison = json.loads((ROOT/'docs/evidence/issue28_continuous/'
    'ordinary-jpmorgan-current-36-cli-20260929/comparison.json').read_text())
compared = next(row for row in comparison['rows'] if row['metric_id'] == 'C02')
assert compared['current_result_id'] == result['result_id']
archive = json.loads((ROOT/'docs/evidence/issue28_continuous/'
    'review-5207290213/current-390.json').read_text())
old = next(row for row in archive['rows'] if row['company_id'] == 'jpmorgan_chase'
           and row['metric_id'] == 'C02')
assert old['implementation_identity']['result_id'] == compared['historical_result_id']
assert old['implementation_identity']['result_id'] != result['result_id']
assert old['value'].count('continued retention of PwC as the Firm’s independent external auditor') == 1
assert old['quality'] == 'EXACT' and old['source_period']['period_end'] == result['period_end'] == '2025-12-31'
body = {'record_type':'ISSUE28_JPM_2025_C02_AUDITOR_RETENTION_SCOPE_AUDIT',
    'company_id':'jpmorgan_chase','metric_id':'C02','period_end':'2025-12-31',
    'old_private_result_id':result['result_id'],
    'old_private_run_id':manifest['run_id'],
    'old_private_selected_count':len(candidate['selected']),
    'old_private_evidence_status':evidence['status'],
    'old_archived_390_result_id':old['implementation_identity']['result_id'],
    'old_archived_390_run_id':old['implementation_identity']['run_id'],
    'old_archived_390_value_contains_excerpt':True,
    'out_of_target_source_block':{'block_index':claim['block_index'],
        'role':role,'text':claim['text'],
        'source_reference_id':reference['source_reference_id'],
        'source_accession':reference['accession'],
        'raw_asset_id':reference['raw_asset_id'],
        'raw_span_sha256':claim['raw_span_sha256']},
    'approved_target':'BOARD_COMPOSITION_FACTS_NOT_AUDITOR_RETENTION_DECISIONS',
    'old_results_and_source_preserved':True,'new_result_created':False,
    'new_real_calls':[0,0,0],
    'scope_limit':'One original governance block and two exact old #28 Results; not a full audit of all 39 selected excerpts or complete selector recall.'}
(HERE/'audit.json').write_text(json.dumps(body,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'old_private_result_id':result['result_id'],
    'old_archived_390_result_id':old['implementation_identity']['result_id'],
    'source_block_index':claim['block_index'],'new_real_calls':[0,0,0]}))
