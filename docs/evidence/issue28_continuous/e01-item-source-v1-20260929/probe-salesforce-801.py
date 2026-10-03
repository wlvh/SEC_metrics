"""Read one authenticated saved Salesforce 8.01 without granting E01 credit."""
import hashlib
import json
from pathlib import Path
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]

from vnext.e01_item_source import bound_801_primary_section

archive_root = ROOT/'docs/evidence/issue28_continuous/ordinary-document-identity'
index = json.loads((archive_root/'material-index.json').read_text())
member = 'live-restored-salesforce-native/runs/salesforce/E01/records.jsonl'
with tarfile.open(archive_root/'material.tar.gz', 'r:gz') as archive:
    descriptor = index['files'][member]
    content = archive.extractfile(descriptor['archive_member']).read()
assert hashlib.sha256(content).hexdigest() == descriptor['sha256']
records = [json.loads(line) for line in content.splitlines()]
claim, = [row for row in records
    if row['record_type'] == 'DETERMINISTIC_VERIFIED_CLAIM'
    and row['attributes'].get('item_code') == '8.01'
    and row['attributes'].get('accession') == '0001108524-25-000083']
reference, = [row for row in records if row['record_type'] == 'SOURCE_REFERENCE'
    and row['source_reference_id'] == claim['attributes']['primary_source_reference_id']]
path = ROOT/'evidence/accession_materials/salesforce_1108524_000110852425000083/crm-20250903.htm'
raw = path.read_bytes()
assert reference['raw_asset_id'] == 'sha256:' + hashlib.sha256(raw).hexdigest()
try:
    bound_801_primary_section(claim=claim, primary_source_reference=reference,
                              primary_document_bytes=raw)
except ValueError as error:
    reason = str(error)
else:
    raise AssertionError('Expected bounded layout refusal')
assert reason == 'E01_ITEM_SOURCE_VISIBILITY_UNPROVEN'
body = {'record_type': 'ISSUE28_E01_SALESFORCE_SAVED_801_LAYOUT_PROBE',
    'accession': reference['accession'],
    'verified_claim_id': claim['verified_claim_id'],
    'source_reference_id': reference['source_reference_id'],
    'source_path': str(path.relative_to(ROOT)),
    'raw_asset_id': reference['raw_asset_id'],
    'archive_claim_object_verified': True,
    'source_raw_bytes_verified': True,
    'opt_in_item_section_status': 'REJECTED',
    'reason': reason,
    'filing_visible_subject_manually_read': 'share_repurchase_authorization_increase',
    'metric_result_created': False,
    'new_provider_paid_sec_calls': [0, 0, 0]}
(HERE/'actual-salesforce-801.json').write_text(json.dumps(body, indent=2) + '\n')
print(json.dumps({'status': body['opt_in_item_section_status'],
    'reason': reason, 'raw_verified': True}, sort_keys=True))
