"""Independent no-network replay of the private Salesforce FY2026 C04 Run."""
import json
from pathlib import Path
import socket
import subprocess
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'scripts'))
from vnext import c04_update_cycle as c04
from vnext.canonical import strict_json_file
from vnext.normal_run_v3 import BINDING_DIRECTORY, PREFIX

LEDGER = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
STATE = LEDGER / 'private-c04-salesforce-fy2026-20260927'
state = strict_json_file(path=STATE / 'current.json')
configuration = c04.cycle._read(STATE / 'configuration.json')
terminal = c04.cycle._terminal(STATE, state['successful_attempt'])
work = STATE / 'attempts' / state['successful_attempt']
manifest = strict_json_file(path=work / 'runs/C04/manifest.json')
assert manifest['run_id'].startswith(PREFIX)
key = manifest['run_id'][len(PREFIX):]
binding = strict_json_file(path=work / 'data' / BINDING_DIRECTORY /
                           (key + '.json'))
input_binding = binding['input_binding']['c04_registration_successor']
alias, = input_binding['verified_annual_document_aliases']
label = input_binding['fiscal_year_label_binding']
assert alias['saved_document_name'] == '0002.body'
assert alias['sec_url_document_name'] == 'crm-20250131.htm'
assert alias['source_reference_id'] == (
    'sha256:5dba75f58e0215431818b4822462606124c54301fd82c5a6be8f5feb1e9b5c43')
assert label['selected_fiscal_year'] == 2026
assert label['original_dei_fiscal_year'] == 2025
assert label['basis'] == 'EXPLICIT_SOURCE_ISSUER_DEFINITION'
assert label['metadata_conflict_retained']
assert manifest['target_period'] == {'fiscal_year': 2026,
    'period_start': '2025-02-01', 'period_end': '2026-01-31'}
with patch.object(socket.socket, 'connect',
                  side_effect=AssertionError('NETWORK_FORBIDDEN')), \
     patch.object(socket, 'getaddrinfo',
                  side_effect=AssertionError('DNS_FORBIDDEN')), \
     patch('sec_http.urlopen',
           side_effect=AssertionError('HTTP_FORBIDDEN')), \
     patch.object(subprocess, 'Popen',
                  side_effect=AssertionError('SUBPROCESS_FORBIDDEN')):
    result = c04._verify_candidate(STATE, terminal, configuration)['C04']
assert result['publication'] == 'PUBLISHED' and result['value'] == '0'
assert result['result_id'] == terminal['metrics']['C04']['result_id']
print(json.dumps({'status': 'PASS_PRIVATE_SALESFORCE_FY2026_NATIVE_COLD_READ',
    'company_id': 'salesforce', 'metric_id': 'C04',
    'target_period': manifest['target_period'],
    'result_id': result['result_id'], 'run_id': manifest['run_id'],
    'publication': result['publication'], 'value': result['value'],
    'original_alias_reference_id': alias['source_reference_id'],
    'saved_document_name': alias['saved_document_name'],
    'actual_sec_url_document_name': alias['sec_url_document_name'],
    'issuer_label_2026_and_dei_2025_both_retained': True,
    'public_row_bytes_verified': True,
    'network_and_subprocess_forbidden': True,
    'new_calls': [0, 0, 0], 'production_authorized': False},
    sort_keys=True))
