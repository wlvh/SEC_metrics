"""Bind original D04 real result to current update, cold read and repeat."""
import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
ORIGINAL = ROOT/'docs/evidence/issue28_continuous/batch33-authorization/d04-enphase-real'
STATE = Path('/private/tmp/issue28-d04-enphase-normal-b868-20260928/metrics/D04')


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


original = read(ORIGINAL/'finish-summary.json')
original_cold = read(ORIGINAL/'cold-summary.json')
first = read(HERE/'result.json')
cold = read(HERE/'cold-result.json')
repeat = read(HERE/'repeat-result.json')
attempt = STATE/'attempts'/first['successful_attempt']
manifest = read(attempt/'runs/D04/manifest.json')
with (attempt/'rows/D04/metrics_matrix.csv').open(newline='') as stream:
    rows = list(csv.DictReader(stream))
assert len(rows) == 1
row = rows[0]

assert original['status'] == 'COMPLETE_NATIVE_OPEN_AND_PUBLIC_ROWS'
assert original_cold['status'] == 'PASS_PERSISTED_COMPLETE_CANDIDATE_AND_COLD_READ'
assert original['original_call_ordinals'] == [173, 174, 175, 176, 177, 178]
assert original['result_id'] == original_cold['result_id'] == first['result_id'] \
    == cold['result_id'] == repeat['result_id']
assert original['run_id'] == original_cold['run_id']
assert manifest['run_id'] != original['run_id']
assert manifest['requirement_closure_hash'] == first['current_requirement_closure'] \
    == cold['requirement_closure_hash']
assert first['status'] == 'CANDIDATE_READY' and first['update_status'] == 'UPDATES_READY'
assert first['result_publication'] == 'WITHHELD'
assert first['reason_code'] == cold['reason_code'] \
    == 'D04_DEFINED_SCOPE_NO_DOUBT_DISCLOSURE'
assert row['company'] == 'Enphase Energy' and row['metric_id'] == 'D04'
assert row['status'] == 'TEXT_QUAL' and row['value'] == ''
assert (row['fiscal_year'], row['period_start'], row['period_end']) == \
    ('2025', '2025-01-01', '2025-12-31')
assert sha(attempt/'rows/D04/metrics_matrix.csv') == \
    first['row_files']['metrics_matrix.csv'] == cold['public_row_sha256']
assert cold['status'] == 'PASS_INDEPENDENT_INSTALLED_RUNTIME_COLD_READ'
assert cold['identities_match_original_result'] and cold['history_bytes_unchanged']
assert repeat['status'] == 'NO_SOURCE_CONTENT_CHANGE'
assert repeat['successful_attempt_after_repeat'] == first['successful_attempt']
assert repeat['new_candidate_created'] is False
assert repeat['original_success_package_unchanged']
assert first['ledger_counts_before'] == first['ledger_counts_after'] == [143, 143, 52]
assert repeat['ledger_counts_before_after'] == [[143, 143, 52], [143, 143, 52]]
assert all(item['new_real_calls'] == [0, 0, 0]
           for item in (first, cold, repeat))

report = {
    'record_type': 'ISSUE28_ENPHASE_D04_CURRENT_NORMAL_UPDATE_RECONCILIATION',
    'status': 'PASS_ORIGINAL_REAL_RESULT_REUSED_BY_CURRENT_NORMAL_UPDATE',
    'company_id': 'enphase_energy', 'metric_id': 'D04',
    'original_call_ordinals': original['original_call_ordinals'],
    'original_run_id': original['run_id'],
    'current_run_id': manifest['run_id'],
    'result_id': first['result_id'],
    'current_requirement_closure': first['current_requirement_closure'],
    'public_row_sha256': cold['public_row_sha256'],
    'public_row_status': row['status'], 'fiscal_year': row['fiscal_year'],
    'current_update_status': first['status'],
    'repeat_status': repeat['status'],
    'cold_status': cold['status'],
    'original_finish_summary_sha256': sha(ORIGINAL/'finish-summary.json'),
    'original_cold_summary_sha256': sha(ORIGINAL/'cold-summary.json'),
    'new_complete_company_results': 0,
    'new_real_calls': [0, 0, 0],
    'all390_acceptance': False, 'production_authorized': False,
}
(HERE/'reconciliation.json').write_text(json.dumps(report,
    ensure_ascii=False, indent=2)+'\n')
print(json.dumps({key: report[key] for key in ('status', 'original_run_id',
    'current_run_id', 'result_id', 'repeat_status', 'cold_status',
    'new_real_calls')}, ensure_ascii=False))
