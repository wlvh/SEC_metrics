"""Verify exact #28 JPMorgan D02 page furniture in two current Result IDs."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
COMPANY = 'jpmorgan_chase'
SOURCE = next(Path('/private/tmp/issue28-jpmorgan_chase-current-36-cli-20260929').glob(
    'state/jpmorgan_chase/metrics/D02/attempts/*/runs/D02/records.jsonl'))
records = [json.loads(line) for line in SOURCE.read_bytes().splitlines()]
candidate = next(row for row in records if row['record_type'] == 'DETERMINISTIC_TEXT_CANDIDATE')
evidence = next(row for row in records if row['record_type'] == 'EVIDENCE_CHECK')
private = next(row for row in records if row['record_type'] == 'METRIC_RESULT'
               and row['metric_id'] == 'D02')
manifest = json.loads((SOURCE.parent/'manifest.json').read_text())
assert evidence['status'] == 'PASS'
assert private['publication'] == 'PUBLISHED' and private['quality'] == 'EXACT'
expected = {10174:'JPMorgan Chase & Co./2025 Form 10-K',
            10184:'JPMorgan Chase & Co./2025 Form 10-K',
            10186:'Notes to consolidated financial statements',
            10195:'JPMorgan Chase & Co./2025 Form 10-K'}
references = {row['source_reference_id']:row for row in records
              if row['record_type'] == 'SOURCE_REFERENCE'}
blobs = {row['raw_asset_id']:row for row in records if row['record_type'] == 'RAW_BLOB'}
found = {}
for role, claim in candidate['selected'].items():
    if claim['block_index'] not in expected:
        continue
    index = claim['block_index']
    assert index not in found and claim['section_id'] == 'NOTE_30'
    assert claim['text'].strip() == expected[index]
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
    found[index] = {'role':role,'block_index':index,'text':claim['text'],
        'section_id':claim['section_id'],
        'source_reference_id':reference['source_reference_id'],
        'source_accession':reference['accession'],
        'raw_asset_id':reference['raw_asset_id'],
        'raw_span_sha256':claim['raw_span_sha256']}
assert set(found) == set(expected)
comparison = json.loads((ROOT/'docs/evidence/issue28_continuous/'
    'ordinary-jpmorgan-current-36-cli-20260929/comparison.json').read_text())
compared = next(row for row in comparison['rows'] if row['metric_id'] == 'D02')
assert compared['current_result_id'] == private['result_id']
archive = json.loads((ROOT/'docs/evidence/issue28_continuous/'
    'review-5207290213/current-390.json').read_text())
old = next(row for row in archive['rows'] if row['company_id'] == COMPANY
           and row['metric_id'] == 'D02')
archived_id = old['implementation_identity']['result_id']
assert compared['historical_result_id'] == archived_id != private['result_id']
assert old['value'].count(expected[10174]) == 3
assert old['value'].count(expected[10186]) == 1
assert private['period_end'] == old['source_period']['period_end'] == '2025-12-31'
body = {'record_type':'ISSUE28_CURRENT_JPM_D02_TWO_RESULT_PAGE_FURNITURE_AUDIT',
    'company_id':COMPANY,'metric_id':'D02','period_end':private['period_end'],
    'private_result_id':private['result_id'],'private_run_id':manifest['run_id'],
    'private_candidate_count':len(candidate['selected']),
    'private_evidence_status':evidence['status'],
    'private_selected_non_disclosures':[found[index] for index in sorted(found)],
    'archived_390_result_id':archived_id,
    'archived_390_run_id':old['implementation_identity']['run_id'],
    'archived_390_value_footer_occurrences':3,
    'archived_390_value_running_head_occurrences':1,
    'old_390_and_private_result_ids_distinct':True,
    'peer_lead_commit':'e76e2953d96005f2fde60e46118a9fbd495c5dfe',
    'peer_defect_register_blob':'80335204c5c19ef721eec4a6c0e934d754a3a836',
    'peer_result_credit_copied':False,
    'old_runs_results_and_source_preserved':True,
    'new_result_created':False,'new_real_calls':[0,0,0],
    'scope_limit':'Four exact furniture excerpts and two named #28 Result IDs; not a full assessment of all 34 selected excerpts or a replacement D02 result.'}
(HERE/'audit.json').write_text(json.dumps(body,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'private_result_id':private['result_id'],
                  'archived_390_result_id':archived_id,
                  'verified_furniture_blocks':sorted(found),
                  'new_real_calls':[0,0,0]}))
