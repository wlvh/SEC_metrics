"""No-network, mixed V4/V5 B13 recording; test data have no business credit."""
from dataclasses import replace
from pathlib import Path
import hashlib
import json
import os
import socket
import subprocess
import sys
from unittest.mock import patch

from vnext.canonical import canonical_json_bytes, strict_json_loads
from vnext.capacity_reference_contract import upgrade_request
from vnext.capacity_two_stage import interpretation_request, scan_request, saved_scan_stage
from vnext.capacity_assessment_input import register_assessment_input
from vnext.capacity_run import install_inputs
from vnext.continuous_call_ledger import recorded_ledger
from vnext.continuous_call_policy import configured_transport_policy
from vnext.continuous_semantic_calls import (
    _json, _source_json, execute_capacity_assessment,
    execute_capacity_interpretation, execute_capacity_scan,
    prepare_requests, request_body)
from vnext.normal_run_v3 import create_normal_run
from vnext.ordinary_projection import render_ordinary_run
from vnext.normal_source_authority import ROOT


def wire(content):
    if not isinstance(content, str):
        content = json.dumps(content, ensure_ascii=False)
    return canonical_json_bytes(value={
        'id': 'b13-two-stage-recorded-only', 'model': 'deepseek-flash',
        'choices': [{'message': {'role': 'assistant', 'content': content},
                     'finish_reason': 'stop'}],
        'usage': {'prompt_tokens': 100, 'completion_tokens': 20,
                  'total_tokens': 120}})


def selected(base, request, policy):
    return replace(base, request_bytes=_source_json(request),
        provider_request_body_bytes=request_body(request, policy),
        output_schema_bytes=_json(request['response_protocol']))


def run():
    root = Path(os.environ['B13_TWO_STAGE_NATIVE_ROOT']).resolve()
    assert not root.exists(), 'IMMUTABLE_RECORDING_ROOT_ALREADY_EXISTS'
    root.mkdir(parents=True)
    old = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/calls/0190')
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN')), \
         patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS_FORBIDDEN')), \
         patch('sec_http.urlopen', side_effect=AssertionError('SEC_FORBIDDEN')):
        bases = prepare_requests(company_id='enphase_energy', metric_id='B13',
            reference_context=True, program_quantity_roles=True)
        assert len(bases) == 6
        assert bases[0].source_bytes == (old/'source.json').read_bytes()
        policy = configured_transport_policy(requirement=bases[0].requirement, repo_root=ROOT)
        ledger = recorded_ledger(root=root/'ledger')
        chosen = []
        for index, base in enumerate(bases):
            original = strict_json_loads(text=base.request_bytes.decode('utf-8'))
            prior = upgrade_request(original, compact=True, role_labels=True,
                                    relevance_scope=True)
            if index == 0:
                prepared = selected(base, prior, policy)
                assert prepared.request_bytes == (old/'semantic-request.json').read_bytes()
                saved_output = (old/'wire/assistant-output.bin').read_bytes().decode('utf-8')
                path, outcome = execute_capacity_assessment(prepared=prepared,
                    ledger=ledger, recorded_wire=wire(saved_output))
                assert outcome['terminal']['status'] == 'SUCCEEDED', (path, outcome)
            elif index == 1:
                scan = scan_request(prior)
                scan_prepared = selected(base, scan, policy)
                scan_value = {'units_reviewed': list(range(len(prior['units']))),
                              'candidate_refs': ['B2382'], 'unresolved_refs': []}
                assert 'destination of shipments' in prior['units'][1]['payload']['blocks']['2382'][-1]
                scan_path, outcome = execute_capacity_scan(prepared=scan_prepared,
                    ledger=ledger, recorded_wire=wire(scan_value))
                assert outcome['terminal']['status'] == 'SUCCEEDED', (scan_path, outcome)
                draft = interpretation_request(request=prior,
                    scan_result=outcome['response_check'],
                    scan_raw_response=(scan_path/'wire/assistant-output.bin').read_bytes())
                stage = saved_scan_stage(prepared=selected(base, draft, policy),
                                        scan_path=scan_path)
                request = interpretation_request(request=prior,
                    scan_result=stage['scan_result'],
                    scan_raw_response=stage['scan_raw_response'],
                    scan_execution_proof=stage['stage_proof'])
                prepared = selected(base, request, policy)
                codes = request['response_protocol']['classification_codebooks']
                response = {'units': [
                    {'unit_index': n, 'reviewed': True, 'unresolved': [],
                     'calculation_limits': []} for n in range(len(request['units']))],
                    'findings': [['sales_or_shipments',
                        codes['subject'].index('TARGET_REGISTRANT'),
                        codes['timing'].index('CURRENT_REPORT'), ['B2382'],
                        'Shipment destination is sales context, not factory output.']]}
                path, outcome = execute_capacity_interpretation(prepared=prepared,
                    ledger=ledger, recorded_wire=wire(response))
                assert outcome['terminal']['status'] == 'SUCCEEDED', (path, outcome)
            else:
                assert not prior['required_candidate_assessments']
                prepared = selected(base, prior, policy)
                response = {'units': [
                    {'unit_index': n, 'reviewed': True, 'unresolved': [],
                     'calculation_limits': []} for n in range(len(prior['units']))],
                    'findings': []}
                path, outcome = execute_capacity_assessment(prepared=prepared,
                    ledger=ledger, recorded_wire=wire(response))
                assert outcome['terminal']['status'] == 'SUCCEEDED', (path, outcome)
            chosen.append(prepared)
            print('recorded_group', index, path.name, flush=True)
        registered = register_assessment_input(prepared_requests=chosen, ledger=ledger)
        assert registered['mode'] == 'RECORDED_TEST_ONLY'
        assert len(registered['scan_stages']) == 1
        data, run_dir = root/'data', root/'run'
        install_inputs(data_root=data, company_id='enphase_energy',
            assessment_mode='RECORDED_TEST_ONLY',
            assessment_input_id=registered['input_record_id'],
            request_context_format=strict_json_loads(text=chosen[0].source_bytes.decode()).get('request_context_format'),
            program_quantity_roles=True)
        created = create_normal_run(data_root=data, run_dir=run_dir,
                                    company_id='enphase_energy', metric_id='B13')
        rendered = render_ordinary_run(data_root=data, run_dir=run_dir)
        for name, raw in rendered['files'].items():
            target = root/'rows'/name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        with ledger.locked():
            recorded_counts = ledger.snapshot()['counts']
        assert recorded_counts == [7, 7, 0]
        summary = {
            'status': 'RECORDED_MIXED_V4_V5_NATIVE_CHAIN_PASS',
            'company_id': 'enphase_energy',
            'source_id': strict_json_loads(text=chosen[0].source_bytes.decode())['semantic_source_id'],
            'recorded_call_counts': recorded_counts,
            'request_variants': registered['assessment']['native_request_variants'],
            'scan_stage_count': len(registered['scan_stages']),
            'run_id': created['manifest']['run_id'],
            'result_id': created['result']['result_id'],
            'result_kind': created['result']['value_kind'],
            'public_rows_sha256': {name: hashlib.sha256(raw).hexdigest()
                                   for name, raw in rendered['files'].items()},
            'real_calls': [0, 0, 0], 'business_result_proven': False,
            'production_authorized': False}
        (root/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
        print('recorded_run', summary['run_id'], flush=True)

    code = '''import sys,json
from pathlib import Path
base=Path(sys.argv[1]);sys.path.insert(0,str(base/'data'));sys.path.insert(0,str(base/'data/scripts'))
blocked=[]
def audit(event,args):
 if event.startswith('socket.') or event in {'subprocess.Popen','os.system'}:
  blocked.append(event);raise RuntimeError('NETWORK_OR_PROCESS_FORBIDDEN:'+event)
sys.addaudithook(audit)
from vnext.ordinary_projection import render_ordinary_run
from vnext import run_store
assert Path(run_store.__file__).resolve().is_relative_to(base/'data')
expected=json.loads((base/'summary.json').read_text())
rendered=render_ordinary_run(data_root=base/'data',run_dir=base/'run')
assert rendered['receipt']['result_id']==expected['result_id']
assert rendered['receipt']['semantic_assessment_mode']=='RECORDED_TEST_ONLY'
for name,raw in rendered['files'].items():assert (base/'rows'/name).read_bytes()==raw
assert not blocked
print(json.dumps({'status':'PASS_INSTALLED_RUNTIME_COLD_READ','run_id':expected['run_id'],
 'result_id':expected['result_id'],'public_rows_identical':True,'new_calls':[0,0,0]}))
'''
    env = {k: value for k, value in os.environ.items()
           if k not in {'DEEPSEEK_API_KEY', 'OPENAI_API_KEY', 'SEC_CONTACT_EMAIL'}}
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    empty = root/'empty-working-directory'
    empty.mkdir()
    result = subprocess.run([sys.executable, '-c', code, str(root)],
        cwd=empty, env=env, capture_output=True, text=True)
    (root/'cold.log').write_text(result.stdout+result.stderr)
    assert result.returncode == 0, result.stdout+result.stderr
    print(result.stdout.strip())
    print(json.dumps(summary))


if __name__ == '__main__':
    run()
