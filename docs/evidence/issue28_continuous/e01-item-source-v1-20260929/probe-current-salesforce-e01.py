"""Read current #28 Salesforce E01 inputs without fetching or reclassifying."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
ACQUIRED = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]

from vnext.continuous_call_policy import REQUIREMENT_ID
from vnext.normal_run_v3 import prepare_case
from vnext.ordinary_processing_source import verify_processing_source
from vnext.requirements import load_requirement_snapshot
from vnext.sources import resolve_repository_file


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


originals = {'claims': ACQUIRED/'claims.jsonl',
    'source_log': ACQUIRED/'source-inputs/evidence/requests_log.csv',
    'active': ROOT/'outputs/active_publication.json'}
before = {key: digest(path) for key, path in originals.items()}
processing = json.loads((ROOT/'docs/evidence/issue28_continuous/'
    'b03-ford-exact-repair-20260929/processing.json').read_text())
source = Path(processing['processing_root'])
requirement = load_requirement_snapshot(
    snapshot_dir=ROOT/'requirements'/REQUIREMENT_ID)
verified = verify_processing_source(
    acquisition_root=ACQUIRED/'source-inputs',
    processing_root=source, requirement=requirement)
assert verified['snapshot_id'] == processing['source_snapshot_id']
case = prepare_case(data_root=source, company_id='salesforce', metric_id='E01')
assert case['admission']['source_credit'] == 'VERIFIED_SEC_ACQUISITION'
component = case['input_binding']['component']
claims = component['claims']
selected_ids = component['selection']['matched_verified_claim_ids']
selected, = [claim for claim in claims
             if claim['verified_claim_id'] in selected_ids]
eight, = [claim for claim in claims if claim['attributes'].get('item_code') == '8.01'
          and claim['attributes'].get('accession') == '0001108524-25-000083']
assert selected['attributes']['item_code'] == '1.01'
assert selected['attributes']['accession'] == '0001193125-25-145772'
assert eight['verified_claim_id'] not in selected_ids
assert eight['attributes']['brief'] == '8-K item 8.01 parsed from hdr.sgml'
refs = {row['source_reference_id']: row for row in case['references']}
header = refs[eight['attributes']['hdr_source_reference_id']]
primary = refs[eight['attributes']['primary_source_reference_id']]
blobs = {row['raw_asset_id']: row for row in case['source_records']
         if row['record_type'] == 'RAW_BLOB'}
for ref in (header, primary):
    blob = blobs[ref['raw_asset_id']]
    raw = resolve_repository_file(repo_root=source,
        repo_relative_path=blob['storage_uri']).read_bytes()
    assert 'sha256:' + hashlib.sha256(raw).hexdigest() == ref['raw_asset_id']
assert case['results']['E01']['value'] == '1'
assert case['results']['E01']['publication'] == 'PUBLISHED'
after = {key: digest(path) for key, path in originals.items()}
assert before == after
body = {'record_type': 'ISSUE28_SALESFORCE_E01_CURRENT_CUMULATIVE_SOURCE_PROBE',
    'source_snapshot_id': verified['snapshot_id'],
    'requirement_closure_hash': requirement['requirement_closure_hash'],
    'source_credit': case['admission']['source_credit'],
    'claim_count': len(claims),
    'matched_claim_id': selected['verified_claim_id'],
    'matched_claim_item_code': selected['attributes']['item_code'],
    'matched_claim_accession': selected['attributes']['accession'],
    'item_801_claim_id': eight['verified_claim_id'],
    'item_801_brief_source': eight['attributes']['brief_source'],
    'item_801_counted': False,
    'item_801_header_source_reference_id': header['source_reference_id'],
    'item_801_header_raw_asset_id': header['raw_asset_id'],
    'item_801_primary_source_reference_id': primary['source_reference_id'],
    'item_801_primary_raw_asset_id': primary['raw_asset_id'],
    'current_existing_e01_result_id': case['results']['E01']['result_id'],
    'current_existing_e01_value_under_item_rule': '1',
    'ma_content_meaning_approved': False,
    'new_result_or_run_created': False,
    'original_claims_source_and_active_unchanged': True,
    'new_real_calls': [0, 0, 0]}
(HERE/'current-cumulative-salesforce-e01.json').write_text(
    json.dumps(body, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'source_credit': body['source_credit'],
    'claims': len(claims), 'matched_item': body['matched_claim_item_code'],
    'item_801_counted': False, 'calls': [0, 0, 0]},
    sort_keys=True), flush=True)
