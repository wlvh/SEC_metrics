"""Cold-read Paramount D04 through its installed current Run package."""
import hashlib
import json
from pathlib import Path
import socket
import sys
import time
from unittest.mock import patch

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
HISTORY = Path('/private/tmp/issue28-d04-paramount-normal-77f-20260928/metrics/D04')
first = json.loads((HERE/'result.json').read_text())
identity = first['successful_attempt']
assert identity is not None
installed = HISTORY/'attempts'/identity/'data'
sys.path[:0] = [str(installed), str(installed/'scripts')]

from vnext import normal_run_v3 as normal
from vnext import ordinary_update_cycle as cycle
from vnext.canonical import sha256_file
from vnext.requirements import load_requirement_snapshot


assert normal.ROOT == installed.resolve()
started = time.monotonic()


def tree():
    return {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in HISTORY.rglob('*') if path.is_file()}


before = tree()
network_attempts = []


def no_network(*args, **kwargs):
    network_attempts.append('blocked')
    raise AssertionError('NETWORK_FORBIDDEN')


with patch.object(socket.socket, 'connect', side_effect=no_network), \
     patch.object(socket, 'getaddrinfo', side_effect=no_network), \
     patch('sec_http.urlopen', side_effect=no_network):
    configuration = cycle._read(HISTORY/'configuration.json')
    state = cycle._state(HISTORY, configuration)
    assert state['successful_attempt'] == identity
    terminal = cycle._terminal(HISTORY, identity)
    result = cycle._verify_candidate(HISTORY, terminal, configuration)['D04']
    requirement = load_requirement_snapshot(
        snapshot_dir=installed/'requirements/issue_28_v14')

after = tree()
changed = [name for name in sorted(set(before)|set(after))
           if before.get(name) != after.get(name)]
row_sha = sha256_file(path=HISTORY/'attempts'/identity/
    'rows/D04/metrics_matrix.csv')
identities_match = (result['result_id'] == first['current_result_id']
    == first['original_result_id'] and row_sha ==
    first['row_files']['metrics_matrix.csv'] and
    requirement['requirement_closure_hash'] == first['current_requirement_closure'])
complete = identities_match and not changed and not network_attempts
report = {'status': ('PASS_INDEPENDENT_INSTALLED_RUNTIME_COLD_READ' if complete
    else 'FAILED_COLD_READ_CONTRACT'),
    'company_id': first['company_id'], 'metric_id': 'D04',
    'installed_runtime_root': str(installed),
    'requirement_closure_hash': requirement['requirement_closure_hash'],
    'successful_attempt': identity,
    'result_id': result['result_id'], 'reason_code': result['reason_code'],
    'public_row_sha256': row_sha,
    'history_file_count_before_after': [len(before), len(after)],
    'changed_path_count': len(changed), 'changed_paths_first_20': changed[:20],
    'history_bytes_unchanged': not changed,
    'identities_match_original_result': identities_match,
    'network_attempts': network_attempts,
    'new_real_calls': [0, 0, 0], 'production_authorized': False,
    'seconds': round(time.monotonic()-started, 3)}
(HERE/'cold-result.json').write_text(json.dumps(report,
    ensure_ascii=False, indent=2)+'\n')
print(json.dumps({key: report[key] for key in ('status', 'result_id',
    'history_file_count_before_after', 'changed_path_count', 'seconds')},
    ensure_ascii=False), flush=True)
assert complete
