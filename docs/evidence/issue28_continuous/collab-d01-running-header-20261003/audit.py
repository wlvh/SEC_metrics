"""Map the peer's running-header defect to one exact ordinary Result."""
import hashlib
import json
from pathlib import Path
import re
from html import unescape

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
STATE = Path('/private/tmp/issue28-jpmorgan_chase-current-36-cli-20260929')
records_path, = STATE.glob('**/runs/D01/records.jsonl')
records = [json.loads(line) for line in records_path.read_text().splitlines()]
candidate = next(r for r in records if r['record_type'] == 'DETERMINISTIC_TEXT_CANDIDATE')
result = next(r for r in records if r['record_type'] == 'METRIC_RESULT' and r['metric_id'] == 'D01')
claim, = [c for c in candidate['selected'].values() if c['text'] == 'Parts I and II']
reference = next(r for r in records if r.get('source_reference_id') == claim['source_reference_id'])
blob = next(r for r in records if r['record_type'] == 'RAW_BLOB' and r['raw_asset_id'] == reference['raw_asset_id'])
data = records_path.parents[2] / 'data'
raw = (data / blob['storage_uri']).read_bytes()
assert hashlib.sha256(raw).hexdigest() == reference['raw_asset_id'][7:]
fragment = raw[claim['raw_start_byte']:claim['raw_end_byte']]
assert fragment == b'Parts I and II' and hashlib.sha256(fragment).hexdigest() == claim['raw_span_sha256']
context = raw[claim['raw_start_byte']-350:claim['raw_end_byte']+12000].decode()
assert 'page-break-after:always' in context and 'Item 1B.' in unescape(re.sub('<[^>]+>', ' ', context))
parent = json.loads((ROOT / 'docs/evidence/issue28_continuous/d04-remaining-20260922/current-390.json').read_text())
row = next(r for r in parent['rows'] if r['company_id'] == 'jpmorgan_chase' and r['metric_id'] == 'D01')
assert row['implementation_identity']['result_id'] == result['result_id']
assert row['value'] == result['value'] and result['value'].splitlines()[-1] == claim['text']
manifest = json.loads(records_path.with_name('manifest.json').read_text())
proof = {'record_type': 'ISSUE28_JPMORGAN_D01_EXACT_RUNNING_HEADER_AUDIT',
    'peer_sha': 'af29ab2f41f40a442c13a3453c97d2c476f3536b',
    'peer_defect_id': 'D01_JPMORGAN_2025_RUNNING_HEADER_PARTS_I_AND_II_TAKEN_AS_A_HEADING',
    'company_id': result['company_id'], 'period_start': result['period_start'], 'period_end': result['period_end'],
    'result_id': result['result_id'], 'run_id': manifest['run_id'],
    'archived_390_same_result_id_and_value': True, 'source_reference': reference,
    'raw_asset': blob, 'wrong_heading_claim': claim,
    'raw_heading_context': raw[claim['raw_start_byte']-200:claim['raw_end_byte']+200].decode(),
    'following_text_excerpt': re.sub(r'\s+', ' ', unescape(re.sub('<[^>]+>', ' ', context)))[:1400],
    'disposition': 'WITHHOLD_EXACT_RESULT_CURRENT_CREDIT; RETAIN_ORIGINAL_RUN_AND_SOURCE',
    'no_other_D01_withdrawal_from_metric_name': True, 'new_calls': [0,0,0]}
(HERE / 'audit.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2)+'\n')
print(json.dumps({'result_id': result['result_id'], 'exact_old_and_current_identity_match': True,
                  'source_sha256': hashlib.sha256(raw).hexdigest(), 'wrong_heading': claim['text']}))
