"""Finish the ten saved real Paramount D04 groups without another provider call."""
import json
import socket
import time
from pathlib import Path
from unittest.mock import patch

from vnext.capacity_assessment_input import register_assessment_input
from vnext.capacity_run import install_inputs
from vnext.continuous_call_ledger import live_ledger
from vnext.continuous_semantic_calls import prepare_requests, select_native_request_variants
from vnext.native_request_construction import request_construction_session
from vnext.normal_run_v3 import create_normal_run
from vnext.normal_source_authority import ROOT
from vnext.ordinary_projection import render_ordinary_run
from vnext.requirements import load_requirement_snapshot


evidence = Path(__file__).resolve().parent
base = Path('/tmp/sec_metrics_issue28_d04_paramount_real_20260924')
assert not base.exists(), 'D04_PARAMOUNT_CURRENT_MATERIAL_ALREADY_EXISTS'
started = time.monotonic()
requirement = load_requirement_snapshot(snapshot_dir=ROOT/'requirements/issue_28_v14')
ledger = live_ledger(requirement=requirement)
with ledger.locked():
    before = ledger.snapshot()
assert before['counts'] == [139, 139, 49] and len(before['rows']) == 188
assert before['stopped_channels'] == []
with patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN')), \
     patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS_FORBIDDEN')), \
     patch('sec_http.urlopen', side_effect=AssertionError('SEC_FORBIDDEN')), \
     patch('vnext.continuous_semantic_calls.execute_d04_assessment',
           side_effect=AssertionError('NEW_PROVIDER_CALL_FORBIDDEN')), \
     request_construction_session(requirement):
    prepared = prepare_requests(company_id='paramount_skydance_paramount_global', metric_id='D04', native=True,
                                reference_context=True, complete_response_contract=True)
    selected, variants = select_native_request_variants(prepared_requests=prepared,
                                                         ledger=ledger)
    ordinals = [row['original_ordinal'] for row in variants]
    assert len(selected) == 10 and ordinals == [179, 180, 181, 182, 183, 184, 185, 186, 187, 188]
    registered = register_assessment_input(prepared_requests=selected, ledger=ledger)
    source = json.loads(selected[0].source_bytes)
    data, run = base/'data', base/'run'
    install_inputs(data_root=data, company_id='paramount_skydance_paramount_global', metric_id='D04',
                   assessment_mode='LIVE',
                   assessment_input_id=registered['input_record_id'],
                   request_context_format=source['request_context_format'],
                   complete_response_contract=True)
    created = create_normal_run(data_root=data, run_dir=run,
                                company_id='paramount_skydance_paramount_global', metric_id='D04')
    rendered = render_ordinary_run(data_root=data, run_dir=run)
    for name, raw in rendered['files'].items():
        path = base/'rows'/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
with ledger.locked():
    after = ledger.snapshot()
assert after['counts'] == before['counts'] and len(after['rows']) == 188
result = created['result']
body = {'record_type':'ISSUE28_D04_PARAMOUNT_COMPLETE_REAL_NATIVE_CANDIDATE',
        'status':'COMPLETE_NATIVE_OPEN_AND_PUBLIC_ROWS',
        'company_id':'paramount_skydance_paramount_global', 'metric_id':'D04',
        'requirement_closure_hash':requirement['requirement_closure_hash'],
        'source_id':source['semantic_source_id'],
        'original_call_ordinals':ordinals,
        'recovered_failed_ordinals':[113],
        'assessment_input_id':registered['input_record_id'],
        'run_id':created['manifest']['run_id'],
        'result_id':result['result_id'], 'value_kind':result['value_kind'],
        'value':result['value'], 'quality':result['quality'],
        'applicability':result['applicability'],
        'reason_code':result['reason_code'],
        'public_files':sorted(rendered['files']),
        'material_root':str(base),
        'new_calls_from_local_finish':[0,0,0],
        'ledger_counts':after['counts'],
        'seconds':round(time.monotonic()-started,3),
        'production_authorized':False}
(base/'summary.json').write_text(json.dumps(body,ensure_ascii=False,indent=2)+'\n')
(evidence/'finish-summary.json').write_text(json.dumps(body,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(body,ensure_ascii=False))
