"""Read seven existing recorded stages with current code; do not re-execute them."""
from dataclasses import replace
from pathlib import Path
import hashlib
import json
import os
import socket
import subprocess
import sys
from unittest.mock import patch

from vnext.canonical import strict_json_loads, strict_json_file
from vnext.capacity_assessment_input import register_assessment_input
from vnext.capacity_run import install_inputs
from vnext.continuous_call_ledger import recorded_ledger
from vnext.continuous_call_policy import configured_transport_policy
from vnext.continuous_semantic_calls import (
    _json, _source_json, prepare_requests, request_body)
from vnext.normal_run_v3 import create_normal_run
from vnext.ordinary_projection import render_ordinary_run
from vnext.normal_source_authority import ROOT


def run():
    previous = Path('/tmp/sec_metrics_issue28_b13_two_stage_recorded_20260925_1')
    root = Path(os.environ['B13_TWO_STAGE_REPLAY_ROOT']).resolve()
    assert previous.joinpath('summary.json').is_file(), 'ORIGINAL_RECORDING_INCOMPLETE'
    assert not root.exists(), 'IMMUTABLE_REPLAY_ROOT_ALREADY_EXISTS'
    root.mkdir(parents=True)
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN')), \
         patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS_FORBIDDEN')), \
         patch('sec_http.urlopen', side_effect=AssertionError('SEC_FORBIDDEN')):
        bases = prepare_requests(company_id='enphase_energy', metric_id='B13',
            reference_context=True, program_quantity_roles=True)
        assert len(bases) == 6
        policy = configured_transport_policy(requirement=bases[0].requirement, repo_root=ROOT)
        ledger = recorded_ledger(root=previous/'ledger')
        chosen = []
        for index, ordinal in enumerate((1, 3, 4, 5, 6, 7)):
            saved = previous/'ledger/calls'/('%04d' % ordinal)
            request = strict_json_file(path=saved/'semantic-request.json')
            prepared = replace(bases[index], request_bytes=_source_json(request),
                provider_request_body_bytes=request_body(request, policy),
                output_schema_bytes=_json(request['response_protocol']))
            assert prepared.source_bytes == (saved/'source.json').read_bytes()
            assert prepared.request_bytes == (saved/'semantic-request.json').read_bytes()
            chosen.append(prepared)
        registered = register_assessment_input(prepared_requests=chosen, ledger=ledger)
        assert registered['mode'] == 'RECORDED_TEST_ONLY'
        assert len(registered['scan_stages']) == 1
        with ledger.locked():
            counts = ledger.snapshot()['counts']
        assert counts == [7, 7, 0]
        data, run_dir = root/'data', root/'run'
        source = strict_json_loads(text=chosen[0].source_bytes.decode())
        install_inputs(data_root=data, company_id='enphase_energy',
            assessment_mode='RECORDED_TEST_ONLY',
            assessment_input_id=registered['input_record_id'],
            request_context_format=source.get('request_context_format'),
            program_quantity_roles=True)
        created = create_normal_run(data_root=data, run_dir=run_dir,
                                    company_id='enphase_energy', metric_id='B13')
        rendered = render_ordinary_run(data_root=data, run_dir=run_dir)
        for name, raw in rendered['files'].items():
            target = root/'rows'/name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        summary = {
            'status': 'RECORDED_MIXED_V4_V5_FINAL_BINDING_REPLAY_PASS',
            'company_id': 'enphase_energy',
            'source_id': source['semantic_source_id'],
            'requirement_closure_hash': bases[0].requirement['requirement_closure_hash'],
            'original_recorded_counts': counts,
            'new_recorded_calls': 0,
            'request_variants': registered['assessment']['native_request_variants'],
            'scan_stage_count': len(registered['scan_stages']),
            'run_id': created['manifest']['run_id'],
            'result_id': created['result']['result_id'],
            'public_rows_sha256': {name: hashlib.sha256(raw).hexdigest()
                                   for name, raw in rendered['files'].items()},
            'real_calls': [0, 0, 0], 'business_result_proven': False,
            'production_authorized': False}
        (root/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
        print('replayed_run', summary['run_id'], flush=True)
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
