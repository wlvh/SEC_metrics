"""Independent-process replay of the Marriott B03 private success and rows."""
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
from unittest.mock import patch

CODE_ROOT = Path(__file__).resolve().parents[4]
PRIVATE = Path(os.environ.get('ISSUE28_MARRIOTT_PRIVATE_ROOT',
    '/private/tmp/issue28-b03-marriott-excluded-20261001'))
STATE = PRIVATE/'normal-update'
SUFFIX = os.environ.get('ISSUE28_MARRIOTT_RECORD_SUFFIX', '')
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(CODE_ROOT/'scripts'))

from vnext.b03_contract_amortization_scope import assess_current_b03_scope
from vnext.canonical import strict_json_file
from vnext.ordinary_projection import render_ordinary_run
from vnext.ordinary_release_preparation import _result_selection_basis


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    previous = strict_json_file(path=HERE/('exercise'+SUFFIX+'.json'))
    assert previous['tested_module_sha256'] == digest(CODE_ROOT/
        'scripts/vnext/b03_contract_amortization_scope.py')
    assert previous['tested_v14_manifest_sha256'] == digest(CODE_ROOT/
        'requirements/issue_28_v14/baseline_manifest.json')
    metric_root = STATE/'marriott_international/metrics/B03'
    pointer = strict_json_file(path=metric_root/'current.json')
    assert pointer['successful_attempt'] == previous['successful_attempt']
    work = metric_root/'attempts'/pointer['successful_attempt']
    watched = [metric_root/'current.json', work/'terminal.json',
        work/'runs/B03/manifest.json', work/'runs/B03/records.jsonl',
        work/'data/evidence/requests_log.csv']
    watched.extend(sorted(path for path in (work/'rows/B03').iterdir()
                          if path.is_file()))
    before = {str(path): digest(path) for path in watched}
    with patch.object(socket.socket, 'connect',
            side_effect=AssertionError('NETWORK_FORBIDDEN')), \
         patch.object(socket, 'getaddrinfo',
            side_effect=AssertionError('DNS_FORBIDDEN')), \
         patch('sec_http.urlopen',
            side_effect=AssertionError('HTTP_FORBIDDEN')):
        rendered = render_ordinary_run(data_root=work/'data',
            run_dir=work/'runs/B03', _return_replay_context=True)
        replay = rendered['replay_context']
        manifest, records, case = (replay[key] for key in
            ('manifest', 'records', 'case'))
        result, = [row for row in records if row['record_type'] ==
            'METRIC_RESULT' and row['metric_id'] == 'B03']
        scope = assess_current_b03_scope(case=case, data_root=work/'data')
        basis = _result_selection_basis(data_root=work/'data',
            manifest=manifest, result=result, rendered=rendered)
    assert result['result_id'] == previous['result_id']
    assert result['value'] == previous['value']
    assert result['publication'] == 'PUBLISHED' and result['quality'] == 'EXACT'
    assert scope['status'] == previous['source_relation_status']
    assert not scope['blocked'] and len(scope['revenue_deduction_proofs']) == 5
    assert basis == 'NATIVE_PUBLISHED_RESULT'
    for name, raw in rendered['files'].items():
        path = work/'rows/B03'/name
        assert path.read_bytes() == raw
    after = {str(path): digest(path) for path in watched}
    assert before == after
    old_index = strict_json_file(path=CODE_ROOT/
        'docs/evidence/issue28_continuous/d04-remaining-20260922/current-390.json')
    older, = [row for row in old_index['rows'] if row['company_id'] ==
        'marriott_international' and row['metric_id'] == 'B03']
    assert older['implementation_identity']['result_id'] == result['result_id']
    assert older['implementation_identity']['run_id'] != manifest['run_id']
    body = {'record_type': 'ISSUE28_MARRIOTT_B03_CONTRACT_EXCLUSION_COLD_READ',
        'company_id': 'marriott_international',
        'result_id': result['result_id'], 'run_id': manifest['run_id'],
        'old_index_run_id': older['implementation_identity']['run_id'],
        'value': result['value'], 'source_relation_status': scope['status'],
        'revenue_deduction_proof_count': len(scope['revenue_deduction_proofs']),
        'private_release_selection_basis': basis,
        'public_row_files_byte_equal': True,
        'watched_private_files_unchanged': before == after,
        'new_real_calls': [0,0,0], 'formal_adoption': False,
        'all390_acceptance': False}
    (HERE/('cold'+SUFFIX+'.json')).write_text(json.dumps(body, ensure_ascii=False,
        indent=2, sort_keys=True)+'\n')
    print(json.dumps({'result_id': result['result_id'],
        'run_id': manifest['run_id'], 'value': result['value'],
        'private_release_basis': basis,
        'private_files_unchanged': before == after,
        'new_real_calls': [0,0,0]},sort_keys=True),flush=True)


if __name__ == '__main__':
    main()
