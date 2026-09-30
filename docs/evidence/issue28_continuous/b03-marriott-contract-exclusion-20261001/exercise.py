"""One private Marriott B03 normal update under the approved exclusion."""
from contextlib import redirect_stdout
import hashlib
from io import StringIO
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch

CODE_ROOT = Path(__file__).resolve().parents[4]
LEDGER_ROOT = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
PRIVATE = Path('/private/tmp/issue28-b03-marriott-excluded-20261001')
PROCESSING_PARENT = PRIVATE/'sources'
STATE_ROOT = PRIVATE/'normal-update'
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(CODE_ROOT/'scripts'), str(CODE_ROOT/'tools')]

from vnext.b03_contract_amortization_scope import assess_current_b03_scope
from vnext.canonical import strict_json_file
from vnext.continuous_call_policy import REQUIREMENT_ID
from vnext.normal_run_v3 import prepare_case
from vnext.ordinary_processing_source import current_processing_source
from vnext.requirements import load_requirement_snapshot
import vnext_normal_update


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    assert not PRIVATE.exists()
    source_root = LEDGER_ROOT/'source-inputs'
    protected = {'claims': LEDGER_ROOT/'claims.jsonl',
        'source_log': source_root/'evidence/requests_log.csv',
        'active': CODE_ROOT/'outputs/active_publication.json'}
    before = {key: digest(path) for key, path in protected.items()}
    requirement = load_requirement_snapshot(
        snapshot_dir=CODE_ROOT/'requirements'/REQUIREMENT_ID)
    with patch.object(socket.socket, 'connect',
            side_effect=AssertionError('NETWORK_FORBIDDEN')), \
         patch.object(socket, 'getaddrinfo',
            side_effect=AssertionError('DNS_FORBIDDEN')), \
         patch('sec_http.urlopen',
            side_effect=AssertionError('HTTP_FORBIDDEN')):
        processing = current_processing_source(
            acquisition_root=source_root, output_parent=PROCESSING_PARENT,
            requirement=requirement)
        case = prepare_case(data_root=processing['data_root'],
            company_id='marriott_international', metric_id='B03')
        relation = assess_current_b03_scope(
            case=case, data_root=processing['data_root'])
        assert relation['status'] == 'COMPOSED_DA_CONTRACT_REVENUE_DEDUCTION_EXCLUDED'
        assert not relation['blocked'] and len(relation['revenue_deduction_proofs']) == 5
        capture = StringIO()
        with redirect_stdout(capture):
            rc = vnext_normal_update.main(['--process',
                '--company', 'marriott_international', '--metric', 'B03',
                '--data-root', str(processing['data_root']),
                '--state-root', str(STATE_ROOT)])
    report = json.loads(capture.getvalue())
    company, = report['companies']
    metric, = company['metrics']
    assert rc == 0 and company['status'] == 'UPDATES_READY'
    assert metric['metric_id'] == 'B03' and metric['status'] == 'CANDIDATE_READY'
    result = metric['last_verified_candidate']['results']['B03']
    assert result['publication'] == 'PUBLISHED' and result['quality'] == 'EXACT'
    assert result['value'] == '0.1756281982738868097456656229'
    assert result['result_id'] == ('sha256:3043aa63cbf7616f9866fb93b8f69200'
                                   'a2246a33dfec8f1d09502a34af39a72a')
    pointer = strict_json_file(path=STATE_ROOT/
        'marriott_international/metrics/B03/current.json')
    assert pointer['successful_attempt'] == metric['attempt_id']
    terminal = strict_json_file(path=STATE_ROOT/
        'marriott_international/metrics/B03/attempts'/metric['attempt_id']/
        'terminal.json')
    assert terminal['status'] == 'CANDIDATE_READY'
    after = {key: digest(path) for key, path in protected.items()}
    assert before == after and report['calls'] == {'provider':0,'paid':0,'sec':0}
    body = {'record_type': 'ISSUE28_MARRIOTT_B03_CONTRACT_REVENUE_EXCLUSION_PRIVATE_UPDATE',
        'base_git_head_with_uncommitted_difference': '430097dd212bfe097caaa5d1d4b5b3f5dcc7a14e',
        'tested_module_sha256': digest(CODE_ROOT/
            'scripts/vnext/b03_contract_amortization_scope.py'),
        'tested_v14_manifest_sha256': digest(CODE_ROOT/
            'requirements/issue_28_v14/baseline_manifest.json'),
        'processing_snapshot_id': processing['snapshot_id'],
        'company_id': 'marriott_international',
        'fiscal_year': 2025,
        'source_relation_status': relation['status'],
        'selected_components': relation['selected_components'],
        'excluded_revenue_deduction_facts': relation['excluded_facts'],
        'revenue_deduction_proofs': relation['revenue_deduction_proofs'],
        'normal_cli_return_code': rc, 'company_status': company['status'],
        'b03_status': metric['status'], 'result_id': result['result_id'],
        'run_id': metric['last_verified_candidate']['results']['B03'].get('run_id'),
        'value': result['value'], 'quality': result['quality'],
        'attempt_id': metric['attempt_id'],
        'successful_attempt': pointer['successful_attempt'],
        'original_protected_hashes_unchanged': before == after,
        'new_real_calls': [0,0,0], 'formal_adoption': False,
        'all390_acceptance': False}
    (HERE/'exercise.json').write_text(json.dumps(body, ensure_ascii=False,
        indent=2, sort_keys=True)+'\n')
    print(json.dumps({'status': metric['status'], 'result_id': result['result_id'],
        'value': result['value'], 'source_relation': relation['status'],
        'originals_unchanged': before == after,
        'new_real_calls': [0,0,0]},sort_keys=True),flush=True)


if __name__ == '__main__':
    main()
