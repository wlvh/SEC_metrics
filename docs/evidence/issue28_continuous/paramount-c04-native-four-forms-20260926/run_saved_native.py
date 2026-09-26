"""One no-network native C04 Run from already acquired registration filings."""
import argparse
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
from unittest.mock import patch

from vnext.c04_registration_successor import EVENT_FORMS
from vnext.canonical import sha256_bytes
from vnext.continuous_call_ledger import live_ledger
from vnext.normal_run_v3 import create_normal_run, install_normal_inputs
from vnext.normal_source_authority import ROOT
from vnext.ordinary_projection import render_ordinary_run
from vnext.requirements import load_requirement_snapshot


def counts():
    requirement = load_requirement_snapshot(
        snapshot_dir=ROOT / 'requirements/issue_28_v14')
    ledger = live_ledger(requirement=requirement)
    with ledger.locked():
        state = ledger.snapshot()
    return state['counts'], len(state['rows'])


def run(source_root, output_root, evidence_root, evidence_suffix):
    assert re.fullmatch(r'[a-z0-9-]+', evidence_suffix)
    output_root.mkdir(parents=True, exist_ok=False)
    before = counts()
    data = output_root / 'data'
    run_dir = output_root / 'run'
    with patch.object(socket.socket, 'connect',
                      side_effect=AssertionError('NETWORK_FORBIDDEN')):
        installed = install_normal_inputs(data_root=data,
            source_root=source_root,
            company_id='paramount_skydance_paramount_global',
            metric_id='C04', c04_event_forms=EVENT_FORMS)
        created = create_normal_run(data_root=data, run_dir=run_dir,
            company_id='paramount_skydance_paramount_global',
            metric_id='C04', c04_event_forms=EVENT_FORMS)
        rendered = render_ordinary_run(data_root=data, run_dir=run_dir)
    assert created['result']['value'] is None
    assert created['selection']['reason_code'] == 'C04_COMPARABLE_AUDITOR_FACTS_MISSING'
    assert len(created['selection']['event_item_claims']) == 22
    assert not created['selection']['matched_item_4_01_claim_ids']
    assert len(installed['input_binding']['c04_registration_successor']['registration_accessions']) == 2
    after = counts()
    assert before == after == ([143, 143, 49], 192)
    rows = output_root / 'public-rows'
    rows.mkdir()
    hashes = {}
    for name, raw in rendered['files'].items():
        (rows / name).write_bytes(raw)
        hashes[name] = sha256_bytes(content=raw)
    summary = {
        'status': 'PASS_RECORDED_SOURCE_NATIVE_RUN_WITHHELD_NO_FALSE_ZERO',
        'source_root': str(source_root), 'output_root': str(output_root),
        'code_root': str(ROOT), 'run_id': created['manifest']['run_id'],
        'result_id': created['result']['result_id'],
        'result_value': created['result']['value'],
        'reason_code': created['selection']['reason_code'],
        'event_count': len(installed['input_binding']['c04_registration_successor']['event_accessions']),
        'registration_event_count': 2,
        'item_claim_count': len(created['selection']['event_item_claims']),
        'item_4_01_count': 0,
        'public_row_sha256': hashes,
        'ledger_before': list(before[0]), 'ledger_after': list(after[0]),
        'ledger_rows_before_after': [before[1], after[1]],
        'new_calls': [0, 0, 0], 'production_authorized': False,
    }
    (output_root / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    cold = r'''
import json, os, socket, subprocess, sys
from pathlib import Path
base=Path(sys.argv[1]);sys.path.insert(0,str(base/'data'/'scripts'))
def forbidden(*args,**kwargs):raise AssertionError('NETWORK_OR_SUBPROCESS_FORBIDDEN')
socket.socket.connect=forbidden
subprocess.Popen=forbidden
from vnext import normal_run_v3
from vnext.ordinary_projection import render_ordinary_run
assert Path(normal_run_v3.__file__).resolve().is_relative_to(base/'data')
expected=json.loads((base/'summary.json').read_text())
result=render_ordinary_run(data_root=base/'data',run_dir=base/'run')
assert result['receipt']['result_id']==expected['result_id']
from vnext.canonical import sha256_bytes
assert {name:sha256_bytes(content=raw) for name,raw in result['files'].items()}==expected['public_row_sha256']
assert all((base/'public-rows'/name).read_bytes()==raw for name,raw in result['files'].items())
print(json.dumps({'status':'PASS_INSTALLED_C04_FOUR_FORM_COLD_READ','result_id':expected['result_id'],'new_calls':[0,0,0]}))
'''
    env = {k: value for k, value in os.environ.items()
           if k not in {'DEEPSEEK_API_KEY', 'OPENAI_API_KEY', 'SEC_CONTACT_EMAIL'}}
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    empty = output_root / 'empty-working-directory'
    empty.mkdir()
    checked = subprocess.run([sys.executable, '-c', cold, str(output_root)],
        cwd=empty, env=env, capture_output=True, text=True)
    (evidence_root / ('cold-' + evidence_suffix + '.log')).write_text(
        checked.stdout + checked.stderr)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    summary['cold_read'] = 'PASS_INSTALLED_C04_FOUR_FORM_COLD_READ'
    (evidence_root / ('summary-' + evidence_suffix + '.json')).write_text(
        json.dumps(summary, indent=2) + '\n')
    print(json.dumps({'status': summary['status'], 'cold_read': summary['cold_read'],
        'result_value': summary['result_value'], 'event_count': summary['event_count'],
        'new_calls': summary['new_calls']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--evidence-suffix', required=True)
    args = parser.parse_args()
    run(args.source_root.resolve(), args.output_root.resolve(),
        Path(__file__).resolve().parent, args.evidence_suffix)
