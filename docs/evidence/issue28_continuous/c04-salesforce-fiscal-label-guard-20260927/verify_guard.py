"""Read-only guard against relabeling the current Salesforce C04 period."""
import hashlib
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'scripts'))
from vnext.normal_annual_input import prepare_saved_annual_input
from vnext.ordinary_source_authority import verify_ordinary_source_proofs

SOURCE = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/source-inputs')
FISCAL = ROOT / 'docs/evidence/issue28_continuous/successor-source-components/fiscal-label/salesforce.json'
INDEX = ROOT / 'docs/evidence/issue28_continuous/d04-remaining-20260922/current-390.json'

fiscal = json.loads(FISCAL.read_text())['inspection']
assert fiscal['status'] == 'SOURCE_LABEL_CONFLICT'
assert fiscal['dei_fiscal_year'] == 2025
assert fiscal['companyfacts_fiscal_year_values'] == [2025]
assert fiscal['source_defined_fiscal_year'] == 2026
assert fiscal['actual_period'] == {'period_start': '2025-02-01',
                                   'period_end': '2026-01-31'}
assert any(2026 in row['current_period_labels'] for row in
           fiscal['source_definitions'])
rows = [row for row in json.loads(INDEX.read_text())['rows']
        if row['company_id'] == 'salesforce' and row['metric_id'] == 'C04']
assert len(rows) == 1
prior = rows[0]
assert prior['source_period']['fiscal_year'] == 2026
assert prior['source_period']['period_start'] == '2025-02-01'
assert prior['source_period']['period_end'] == '2026-01-31'
with patch.object(socket.socket, 'connect',
                  side_effect=AssertionError('NETWORK_FORBIDDEN')), \
     patch.object(socket, 'getaddrinfo',
                  side_effect=AssertionError('DNS_FORBIDDEN')):
    prepared = prepare_saved_annual_input(repo_root=SOURCE,
                                          company_id='salesforce')
    admission = verify_ordinary_source_proofs(data_root=SOURCE,
                                               proofs=prepared['source_proofs'])
target = prepared['table_input']['target_period']
assert target == {'fiscal_year': 2025,
                  'period_start': '2025-02-01', 'period_end': '2026-01-31'}
primary, = [proof for proof in prepared['source_proofs']
            if proof['source_url'].endswith('/crm-20260131.htm')]
raw = (SOURCE / primary['request_repo_relative_path']).read_bytes()
assert hashlib.sha256(raw).hexdigest() == fiscal['primary_sha256']
print(json.dumps({'status': 'PASS_REAL_SOURCE_FISCAL_LABEL_CONFLICT_GUARD',
    'company_id': 'salesforce', 'metric_id': 'C04',
    'same_actual_period': fiscal['actual_period'],
    'current_ordinary_input_fiscal_year': target['fiscal_year'],
    'issuer_defined_fiscal_year': fiscal['source_defined_fiscal_year'],
    'prior_390_fiscal_year': prior['source_period']['fiscal_year'],
    'prior_390_result_id': prior['implementation_identity']['result_id'],
    'primary_source_sha256': fiscal['primary_sha256'],
    'source_admission_status': admission.get('source_credit'),
    'new_c04_result_or_run_created': False,
    'existing_result_rewritten': False,
    'network_forbidden': True, 'new_calls': [0, 0, 0],
    'business_precedence_decision_required': True,
    'production_authorized': False}, sort_keys=True))
