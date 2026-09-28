"""Replay the new Enphase D04 update from its installed runtime in a new process."""
import hashlib
import json
from pathlib import Path
import socket
import sys
import time
from unittest.mock import patch

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
STATE = Path('/private/tmp/issue28-d04-enphase-normal-b868-20260928')
history = STATE/'metrics/D04'
pointer = json.loads((history/'current.json').read_text())
identity = pointer['successful_attempt']
assert identity is not None
installed = history/'attempts'/identity/'data'
sys.path[:0] = [str(installed), str(installed/'scripts')]

from vnext import normal_run_v3 as normal
from vnext import ordinary_update_cycle as cycle
from vnext.canonical import sha256_file
from vnext.requirements import load_requirement_snapshot


assert normal.ROOT == installed.resolve()
started = time.monotonic()
before = {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
          for path in history.rglob('*') if path.is_file()}
network_attempts = []


def no_network(*args, **kwargs):
    network_attempts.append('blocked')
    raise AssertionError('NETWORK_FORBIDDEN')


with patch.object(socket.socket, 'connect', side_effect=no_network), \
     patch.object(socket, 'getaddrinfo', side_effect=no_network), \
     patch('sec_http.urlopen', side_effect=no_network):
    configuration = cycle._read(history/'configuration.json')
    checked_state = cycle._state(history, configuration)
    assert checked_state['successful_attempt'] == identity
    terminal = cycle._terminal(history, identity)
    result = cycle._verify_candidate(history, terminal, configuration)['D04']
    requirement = load_requirement_snapshot(
        snapshot_dir=installed/'requirements/issue_28_v14')

after = {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
         for path in history.rglob('*') if path.is_file()}
first = json.loads((HERE/'result.json').read_text())
changed = [path for path in sorted(set(before)|set(after))
           if before.get(path) != after.get(path)]
identities_match = (first['result_id'] == result['result_id']
    and first['current_requirement_closure'] == requirement['requirement_closure_hash']
    and first['row_files']['metrics_matrix.csv'] == sha256_file(
        path=history/'attempts'/identity/'rows/D04/metrics_matrix.csv'))
complete = identities_match and not changed and not network_attempts
report = {'status': ('PASS_INDEPENDENT_INSTALLED_RUNTIME_COLD_READ' if complete
                     else 'FAILED_COLD_READ_CONTRACT'),
          'installed_runtime_root': str(installed),
          'requirement_closure_hash': requirement['requirement_closure_hash'],
          'company_id': 'enphase_energy', 'metric_id': 'D04',
          'successful_attempt': identity,
          'result_id': result['result_id'],
          'reason_code': result['reason_code'],
          'public_row_sha256': sha256_file(
              path=history/'attempts'/identity/'rows/D04/metrics_matrix.csv'),
          'history_file_count_before_after': [len(before), len(after)],
          'history_bytes_unchanged': not changed,
          'changed_path_count': len(changed),
          'changed_paths_first_20': changed[:20],
          'identities_match_original_result': identities_match,
          'network_attempts': network_attempts,
          'new_real_calls': [0, 0, 0],
          'production_authorized': False,
          'seconds': round(time.monotonic()-started, 3)}
(HERE/'cold-result.json').write_text(json.dumps(report, ensure_ascii=False,
                                             indent=2)+'\n')
print(json.dumps({key: report[key] for key in ('status', 'result_id',
    'reason_code', 'history_file_count_before_after',
    'history_bytes_unchanged', 'changed_path_count',
    'seconds')}, ensure_ascii=False), flush=True)
assert complete
