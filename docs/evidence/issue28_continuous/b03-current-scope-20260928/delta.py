"""One affected coordinate against the existing #28 390 index; no new ledger."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PARENT = ROOT/'docs/evidence/issue28_continuous/d04-remaining-20260922/current-390.json'
index = json.loads(PARENT.read_text())
audit = json.loads((HERE/'audit.json').read_text())
selected = [row for row in index['rows'] if
    row['company_id'] == 'salesforce' and row['metric_id'] == 'B03']
scope = [row for row in audit['rows'] if row['company_id'] == 'salesforce']
assert index['coordinate_count'] == 390 and len(selected) == len(scope) == 1
assert selected[0]['implementation_identity']['result_id'] == \
       scope[0]['historical_native_result_id']
assert scope[0]['scope_check']['status'] == \
       'NARROW_SELECTED_AND_COMPETING_SCOPE'
body = {'record_type': 'ISSUE28_CURRENT_390_ONE_COORDINATE_SCOPE_DELTA',
    'parent_index': str(PARENT.relative_to(ROOT)),
    'coordinate_key': 'salesforce:B03',
    'historical_result_id_retained': selected[0]['implementation_identity']['result_id'],
    'historical_value_retained': selected[0]['value'],
    'historical_publication_record_retained': True,
    'current_business_credit': 'REVOKED_PENDING_DEPRECIATION_SCOPE_RESOLUTION',
    'source_scope': scope[0]['scope_check'],
    'new_complete_coordinate_count': 0,
    'other_389_revalidated': False,
    'all390_acceptance': False,
    'production_authorized': False,
    'new_provider_paid_sec_calls': [0, 0, 0]}
(HERE/'delta.json').write_text(json.dumps(body, ensure_ascii=False,
                                         indent=2) + '\n')
print(json.dumps({'coordinate':body['coordinate_key'],
    'current_business_credit':body['current_business_credit'],
    'parent_coordinate_count':index['coordinate_count']}, sort_keys=True))
