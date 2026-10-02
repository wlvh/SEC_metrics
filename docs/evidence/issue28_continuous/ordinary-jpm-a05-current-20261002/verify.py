"""Read the new private update, its cold pointer and the untouched old archive."""
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
STATE = Path('/private/tmp/issue28-jpm-a05-current-20261002/state/jpmorgan_chase/metrics/A05')
OLD = ROOT / 'docs/evidence/issue28_continuous/ordinary-document-identity'
OLD_RECORD = 'live-restored-jpm-native/runs/jpmorgan_chase/A05/records.jsonl'


def read(path):
    return json.loads(path.read_text())


def sha(data):
    return hashlib.sha256(data).hexdigest()


first, cold = read(HERE/'result.json'), read(HERE/'cold.json')
state = read(STATE/'current.json')
first_attempt = STATE/'attempts'/first['attempt_id']
cold_attempt = STATE/'attempts'/cold['new_attempt_id']
first_terminal = read(first_attempt/'terminal.json')
cold_terminal = read(cold_attempt/'terminal.json')
new_records = [json.loads(line) for line in
               (first_attempt/'runs/A05/records.jsonl').read_bytes().splitlines()]
new_result = next(row for row in new_records if row['record_type'] == 'METRIC_RESULT'
                  and row['metric_id'] == 'A05')
new_manifest = read(first_attempt/'runs/A05/manifest.json')
new_validation = read(first_attempt/'runs/A05/validation.json')
assert state['successful_attempt'] == first['attempt_id']
assert state['latest_attempt'] == cold['new_attempt_id']
assert first_terminal['status'] == 'CANDIDATE_READY'
assert cold_terminal['status'] == 'NO_SOURCE_CONTENT_CHANGE'
assert not (cold_attempt/'runs').exists()
assert new_result['result_id'] == first['result_id'] == cold['cold_result_id']
for name, expected in first_terminal['metrics']['A05']['files'].items():
    assert sha((first_attempt/'rows/A05'/name).read_bytes()) == expected

index = read(OLD/'material-index.json')
with tarfile.open(OLD/'material.tar.gz') as archive:
    old_bytes = archive.extractfile(
        index['files'][OLD_RECORD]['archive_member']).read()
assert sha(old_bytes) == index['files'][OLD_RECORD]['sha256']
old_result = next(row for row in (json.loads(line) for line in old_bytes.splitlines())
                  if row['record_type'] == 'METRIC_RESULT' and row['metric_id'] == 'A05')
archive_path = str((OLD/'material.tar.gz').relative_to(ROOT))
tracked_blob = subprocess.check_output(['git', 'rev-parse',
    first['tested_commit'] + ':' + archive_path], cwd=ROOT, text=True).strip()
current_blob = subprocess.check_output(['git', 'hash-object', archive_path],
                                       cwd=ROOT, text=True).strip()
assert current_blob == tracked_blob
assert old_result['result_id'] != new_result['result_id']
assert old_result['value'] == new_result['value']
body = {'record_type': 'ISSUE28_JPM_A05_PRIVATE_UPDATE_AND_COLD_VERIFICATION',
        'tested_commit': first['tested_commit'],
        'source_snapshot_id': first['source_snapshot_id'],
        'requirement_closure_hash': first['requirement_closure_hash'],
        'old_archive_git_blob_unchanged': current_blob == tracked_blob,
        'old_result_id': old_result['result_id'],
        'new_result_id': new_result['result_id'],
        'equal_value': new_result['value'],
        'new_run_id': new_manifest['run_id'],
        'new_run_validation_status': new_validation['status'],
        'first_status': first_terminal['status'],
        'cold_status': cold_terminal['status'],
        'cold_created_run': (cold_attempt/'runs').exists(),
        'rows_rechecked_against_terminal_hashes': True,
        'successful_pointer_preserved':
            state['successful_attempt'] == first['attempt_id'],
        'protected_ledger_source_log_active_unchanged':
            first['protected_source_ledger_and_active_unchanged'] and
            cold['protected_source_ledger_and_active_unchanged'],
        'new_real_calls': [0, 0, 0],
        'current_390_credit': False,
        'production_authorized': False}
(HERE/'verify.json').write_text(json.dumps(body, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({key: body[key] for key in ('old_result_id', 'new_result_id',
    'first_status', 'cold_status', 'new_run_validation_status',
    'old_archive_git_blob_unchanged')}, sort_keys=True))
