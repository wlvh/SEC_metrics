"""Independent bounded B13 quantity/qualification probe; no admission credit."""
from pathlib import Path
from types import SimpleNamespace
import ast
import hashlib
import json
from tests.vnext.test_capacity_utilization_source import quantity_source
from vnext.capacity_utilization_source import calculate_source_comparable_pair
from vnext.capacity_semantic_review import requests_from_source, validate_response
from vnext.capacity_native_assessment import build_acceptance
from vnext.r6_semantic_source import _bytes
from vnext.canonical import content_hash

HERE=Path(__file__).resolve().parent
P='For fiscal year 2025, we produced 80 widgets worldwide.'
C='For fiscal year 2025, our available annual production capacity was 100 widgets worldwide.'
CASES={
    'actual_plain': '<p>'+P+'</p><p>'+C+'</p>',
    'hypothetical_heading_after_two_blocks': '<h2>Hypothetical example:</h2><p>The following example shows the calculation.</p><p>All figures in this example are assumed.</p><p>'+P+'</p><p>'+C+'</p>',
    'same_block_post_qualifier': '<p>'+P+' '+C+' These quantities are hypothetical examples, not actual production or available capacity.</p>',
}
NAMES={
 'scripts/vnext/capacity_utilization_source.py': ['_quantity_context_qualified','explicit_annual_quantity_statements','calculate_source_comparable_pair','validate_explicit_quantity_classifications','calculate_comparable_pair'],
 'scripts/vnext/capacity_semantic_review.py': ['validate_response','_tax_credit_without_capacity'],
 'scripts/vnext/capacity_text_results.py': ['_prepare'],
 'scripts/vnext/capacity_run.py': ['prepare_case','validate_run_authority','project_defined_absence'],
}
original={}
for name,names in NAMES.items():
    src=Path(name).read_text()
    original[name]={n.name:ast.get_source_segment(src,n) for n in ast.parse(src).body if isinstance(n,ast.FunctionDef) and n.name in names}
rows=[]
for name, html in CASES.items():
    source,raw=quantity_source(html)
    row={'case':name,'source_html':html,'source_id':source['semantic_source_id']}
    try:
        checked=calculate_source_comparable_pair(source=source,raw_bytes_by_id=raw)
        row['quantity_result']={'value':checked['result']['value'],'source_assignments_independently_verified':checked['source_assignments_independently_verified'],'native_result_created':checked['native_result_created']}
    except ValueError as exc:row['quantity_result']={'error':str(exc)}
    request=requests_from_source(source)[0]
    observed=[]
    for label in ['CURRENT_QUANTITIES','OTHER_CONTEXT','CONDITIONAL_OR_BOILERPLATE']:
        findings=[]
        for block in source['units'][0]['payload']['blocks']:
            for statement,kind in [(P,'ACTUAL_PRODUCTION'),(C,'AVAILABLE_CAPACITY')]:
                if statement in block['text']:
                    findings.append({'kind':kind if label=='CURRENT_QUANTITIES' else label,'subject':'TARGET_REGISTRANT','timing':'CONDITIONAL' if label=='CONDITIONAL_OR_BOILERPLATE' else 'CURRENT_REPORT', 'reason':'Synthetic label probe, not model interpretation.', 'evidence':[{'kind':'VISIBLE_BLOCK','source_index':block['block_index']}]})
        response={'request_id':request['request_id'],'units':[{'unit_id':source['units'][0]['unit_id'],'reviewed':True,'findings':findings,'unresolved':[],'calculation_limits':[]}]}
        result={'label':label}
        try:
            v=validate_response(request=request,raw_response=_bytes(response));result['validation']={'accepted':True,'unresolved':v['unresolved']}
        except ValueError as exc:result['validation']={'accepted':False,'reason':str(exc)}
        prepared=SimpleNamespace(request_bytes=_bytes(request),source_bytes=_bytes(source))
        plan={k:content_hash(value=k) for k in ('selected_representation_hash','ai_invocation_plan_id','source_identity_hash','task_contract_hash')}
        try:result['native_acceptance']=build_acceptance(prepared=prepared,plan=plan,response_body=_bytes(response))['evidence_status']
        except ValueError as exc:result['native_acceptance_error']=str(exc)
        observed.append(result)
    row['labels']=observed;rows.append(row)
record={p:{n:{'text':s,'sha256':hashlib.sha256(s.encode()).hexdigest()} for n,s in fs.items()} for p,fs in original.items()}
(HERE/'reviewed-functions.json').write_text(json.dumps(record,indent=2)+'\n')
for path, fs in original.items():
    src=Path(path).read_text();after={n.name:ast.get_source_segment(src,n) for n in ast.parse(src).body if isinstance(n,ast.FunctionDef) and n.name in fs}
    assert after==fs,'function changed during probe: '+path
print(json.dumps({'cases':rows,'real_calls':[0,0,0],'full_Run_executed':False,'source_and_admission':'SYNTHETIC_FACTORY_NO_REAL_CREDIT'},ensure_ascii=False,indent=2))
