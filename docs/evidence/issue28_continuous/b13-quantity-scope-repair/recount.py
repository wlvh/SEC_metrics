"""Recount the complete current B13 envelopes after the correctness delta."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import json
import socket
from vnext.capacity_semantic_source import prepare_capacity_semantic_source
from vnext.capacity_semantic_review import requests_from_source, _restore_units
from vnext.continuous_request_context import FORMAT_VERSION, measure_request
from vnext.continuous_semantic_calls import request_body
from vnext.normal_source_authority import ROOT
from vnext.canonical import sha256_file

rows=[]
with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')), patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS_FORBIDDEN')):
    for company in ['ford_motor_company','enphase_energy']:
        source=prepare_capacity_semantic_source(repo_root=ROOT,company_id=company,request_context_format=FORMAT_VERSION)
        requests=requests_from_source(source)
        assert [u for r in requests for u in _restore_units(r['units'],r['shared_source_dictionaries'])]==source['units']
        measurements=[]
        for r in requests:
            measured=measure_request(request_body(r,SimpleNamespace(model='deepseek-flash')),require_reference=True)
            assert measured['fits']
            measurements.append({'request_id':r['request_id'],'unit_count':len(r['units']),
                'required_candidates':len(r['required_candidate_assessments']), **measured})
        rows.append({'company_id':company,'source_id':source['semantic_source_id'],
            'original_unit_count':len(source['units']),'request_count':len(requests),
            'quantity_scope_context':source['quantity_scope_context'],'complete_unit_restoration':True,
            'requests':measurements})
output={'real_calls':[0,0,0],'reason':'Correctness metadata delta; no further call optimization',
        'scope_module_sha256':sha256_file(path=ROOT/'scripts/vnext/capacity_quantity_scope.py'),
        'total_b13_requests':sum(x['request_count'] for x in rows),'companies':rows}
Path(__file__).with_name('recount.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
print([(r['company_id'],r['request_count'],max(m['context_tokens'] for m in r['requests'])) for r in rows])
