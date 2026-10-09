"""Read-only version comparison for the existing Salesforce/C04 coordinate."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
index = json.loads((ROOT /
    'docs/evidence/issue28_continuous/d04-remaining-20260922/current-390.json').read_text())
rows = [row for row in index['rows'] if row['company_id'] == 'salesforce'
        and row['metric_id'] == 'C04']
assert index['coordinate_count'] == 390 and len(rows) == 1
old = rows[0]
cold = json.loads((HERE / 'cold_read_salesforce.log').read_text().strip())
assert old['source_period'] == cold['target_period']
assert old['source_period']['fiscal_year'] == 2026
assert old['result_category'] == 'NUMERIC_RESULT' and old['value'] == '0'
assert cold['publication'] == 'PUBLISHED' and cold['value'] == '0'
assert old['implementation_identity']['result_id'] != cold['result_id']
assert old['formal_adoption_or_active_credit'] is False
print(json.dumps({'status': 'PASS_EXISTING_390_SALESFORCE_C04_VERSION_DELTA',
    'company_id': 'salesforce', 'metric_id': 'C04',
    'period': cold['target_period'],
    'old_result_id': old['implementation_identity']['result_id'],
    'new_private_result_id': cold['result_id'],
    'new_private_run_id': cold['run_id'],
    'numeric_value_unchanged': True,
    'new_complete_coordinate_count': 0,
    'full390_acceptance': False,
    'new_calls_for_mapping': [0, 0, 0],
    'formal_adoption': False}, sort_keys=True))
