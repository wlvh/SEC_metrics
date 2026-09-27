"""Map one verified Southwest C04 private result onto the existing 390 index."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'scripts'))
from vnext.canonical import strict_json_file

HERE = Path(__file__).resolve().parent
PARENT = ROOT / 'docs/evidence/issue28_continuous/d04-remaining-20260922/current-390.json'
SOURCE = ROOT / 'docs/evidence/issue28_continuous/c04-southwest-prior-source-20260927'
LEDGER = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
STATE = LEDGER / 'private-c04-southwest-20260927'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def log(path):
    return json.loads(path.read_text().strip())


parent = strict_json_file(path=PARENT)
assert parent['coordinate_count'] == 390
rows = [row for row in parent['rows'] if row['company_id'] == 'southwest_airlines'
        and row['metric_id'] == 'C04']
assert len(rows) == 1
old = rows[0]
assert old['result_category'] == 'NUMERIC_RESULT' and old['value'] == '0'
capture = log(SOURCE / 'capture.log')
cold = log(SOURCE / 'cold_read_corrected.log')
assert capture['last_ordinal'] == 195 and capture['last_status'] == 'SUCCEEDED'
assert capture['cumulative_counts'] == [143, 143, 52]
receipt = strict_json_file(path=LEDGER / 'calls/0195/sec-receipt.json')
assert capture['receipt_id'] == receipt['receipt_id']
assert receipt['actual_sec_egress_count'] == 1
current = strict_json_file(path=STATE / 'current.json')
work = STATE / 'attempts' / current['successful_attempt']
terminal = strict_json_file(path=work / 'terminal.json')
manifest = strict_json_file(path=work / 'runs/C04/manifest.json')
assert terminal['status'] == 'CANDIDATE_READY'
assert terminal['metrics']['C04']['result_id'] == cold['result_id']
assert manifest['target_period'] == old['source_period']
assert cold['status'] == 'PASS_PRIVATE_NATIVE_C04_COLD_READ'
assert cold['value'] == '0' and cold['publication'] == 'PUBLISHED'
assert cold['row_bytes_verified'] and cold['network_and_subprocess_forbidden']
expected = {'record_type': 'ISSUE28_CURRENT_390_ONE_COORDINATE_DELTA',
    'parent_index': str(PARENT.relative_to(ROOT)),
    'parent_index_sha256': digest(PARENT), 'coordinate_count': 390,
    'company_id': 'southwest_airlines', 'metric_id': 'C04',
    'period': old['source_period'], 'prior_category': old['result_category'],
    'current_category': 'NUMERIC_RESULT',
    'prior_result_id': old['implementation_identity']['result_id'],
    'current_result_id': cold['result_id'], 'current_run_id': manifest['run_id'],
    'value': cold['value'], 'real_sec_ordinal_for_prior_annual': 195,
    'private_successful_attempt': current['successful_attempt'],
    'prior_failed_attempt_preserved': cold['preserved_failed_attempt'],
    'cold_read_network_and_subprocess_forbidden': True,
    'new_complete_coordinate_count': 0,
    'new_fiscal_year_transition_proven': False,
    'all390_acceptance': False, 'formal_adoption': False,
    'calls_for_source_acquisition_and_mapping': [0, 0, 1],
    'evidence_sha256': {str((SOURCE / name).relative_to(ROOT)):
        digest(SOURCE / name) for name in ('capture.log',
                                           'cold_read_corrected.log', 'README.md')}}
path = HERE / 'delta.json'
if '--write' in sys.argv:
    assert not path.exists()
    path.write_text(json.dumps(expected, ensure_ascii=False, indent=2) + '\n')
else:
    assert strict_json_file(path=path) == expected
print(json.dumps({'status': 'PASS_BOUNDED_CURRENT_390_SOUTHWEST_C04_DELTA',
    'prior_result_id': expected['prior_result_id'],
    'current_result_id': expected['current_result_id'],
    'period': expected['period'], 'new_complete_coordinate_count': 0,
    'new_fiscal_year_transition_proven': False, 'all390_acceptance': False,
    'mapping_new_calls': [0, 0, 0]}, sort_keys=True))
