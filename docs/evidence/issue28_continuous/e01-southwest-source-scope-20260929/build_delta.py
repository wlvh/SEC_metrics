"""Flag one existing 390 coordinate's E01 meaning as unverified."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent/'d04-remaining-20260922/current-390.json'
index = json.loads(PARENT.read_text())
audit = json.loads((HERE/'audit.json').read_text())
row, = [item for item in index['rows']
        if item['company_id'] == 'southwest_airlines' and item['metric_id'] == 'E01']
assert row['value'] == audit['result_value'] == '2'
assert row['implementation_identity']['result_id'] == audit['result_id']
assert audit['matched_claim_count'] == 2
assert audit['matched_item_codes'] == ['1.01', '1.01']
body = {'record_type': 'ISSUE28_CURRENT_390_ONE_COORDINATE_E01_DEFINITION_DELTA',
    'parent_index': str(PARENT.relative_to(HERE.parents[3])),
    'parent_index_sha256': hashlib.sha256(PARENT.read_bytes()).hexdigest(),
    'coordinate_key': 'southwest_airlines:E01',
    'historical_result_id_retained': row['implementation_identity']['result_id'],
    'historical_value_retained': row['value'],
    'historical_publication_record_retained': True,
    'current_MA_announcement_credit': 'UNVERIFIED_PENDING_ITEM_CODE_VS_CONTENT_DEFINITION',
    'basis': {'source_audit': str((HERE/'audit.json').relative_to(HERE.parents[3])),
              'matched_item_codes': ['1.01', '1.01'],
              'original_primary_bytes_verified': True,
              'first_filing': 'shareholder cooperation agreement amendment',
              'second_filing': 'debt securities offering'},
    'new_complete_coordinate_count': 0,
    'other_389_revalidated': False,
    'other_E01_coordinates_audited': False,
    'all390_acceptance': False,
    'production_authorized': False,
    'new_provider_paid_sec_calls': [0, 0, 0]}
(HERE/'delta.json').write_text(json.dumps(body, ensure_ascii=False,
    indent=2) + '\n')
print(json.dumps({'coordinate': body['coordinate_key'],
    'old_value': body['historical_value_retained'],
    'current_credit': body['current_MA_announcement_credit']}, sort_keys=True))
