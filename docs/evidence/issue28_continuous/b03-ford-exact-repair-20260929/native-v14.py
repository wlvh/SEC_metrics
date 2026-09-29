"""Exercise explicit V14 Ford B03 Run without altering the V13 default."""
import hashlib
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
WORK = Path('/private/tmp/issue28-b03-ford-v14-native-20260929')
ACQUIRED = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


originals = {'claims': ACQUIRED/'claims.jsonl',
    'source_log': ACQUIRED/'source-inputs/evidence/requests_log.csv',
    'active': ROOT/'outputs/active_publication.json'}
before = {key: digest(path) for key, path in originals.items()}
assert not WORK.exists()
with (patch.object(socket.socket, 'connect',
                   side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket, 'getaddrinfo',
                   side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen',
            side_effect=AssertionError('HTTP_FORBIDDEN'))):
    from vnext.b03_impairment_adjusted_run import (
        install_inputs, create_run, render_run)
    print('INSTALL_START', flush=True)
    install_inputs(data_root=WORK/'data', source_root=ROOT,
                   company_id='ford_motor_company')
    print('RUN_START', flush=True)
    created = create_run(data_root=WORK/'data', run_dir=WORK/'run',
                         company_id='ford_motor_company')
    print('RENDER_START', flush=True)
    rendered = render_run(data_root=WORK/'data', run_dir=WORK/'run',
                          _return_replay_context=True)
assert before == {key: digest(path) for key, path in originals.items()}
assert created['result']['result_id'] == \
       rendered['replay_context']['case']['results']['B03']['result_id']
assert rendered['row']['value'] == \
       '-0.007128858795196163766173431518'
body = {'record_type': 'ISSUE28_B03_EXACT_V14_NATIVE_PROTOTYPE',
    'result_id': created['result']['result_id'],
    'run_id': created['manifest']['run_id'],
    'requirement_id': created['manifest']['requirement_id'],
    'value': created['result']['value'],
    'row_status': rendered['row']['status'],
    'evidence_count': len(rendered['evidence']),
    'source_proof_id': rendered['replay_context']['case'][
        'input_binding']['source_relation_proof']['proof_id'],
    'original_claims_source_and_active_unchanged': True,
    'new_real_calls': [0, 0, 0],
    'formal_adoption': False}
(HERE/'native-v14.json').write_text(json.dumps(body, ensure_ascii=False,
    indent=2) + '\n')
print(json.dumps({'result_id': body['result_id'],
    'value': body['value'], 'evidence': body['evidence_count'],
    'calls': [0, 0, 0]}, sort_keys=True), flush=True)
