"""Read-only variants of the actual rejected 94 response; no execution credit."""
from pathlib import Path
from copy import deepcopy
import hashlib,json
from vnext.capacity_semantic_review import validate_response
from vnext.r6_semantic_source import _bytes
root=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/calls/0094')
files=['semantic-request.json','source.json','wire/assistant-output.bin','wire/journal.json','intent.json','terminal.json']
def hashes():return {p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in files}
before=hashes();request=json.loads((root/'semantic-request.json').read_text());raw=(root/'wire/assistant-output.bin').read_bytes();response=json.loads(raw)
finding=[f for u in response['units'] for f in u['findings'] if f['kind']=='ACTUAL_PRODUCTION' or any(e['source_index'] in {476,669} for e in f['evidence'])]
variants=[('ORIGINAL',response)]
removed=deepcopy(response)
for u in removed['units']:
    if any(f['kind']=='ACTUAL_PRODUCTION' for f in u['findings']):
        u['calculation_limits'].remove('TARGET_CURRENT_PRODUCTION_NOT_PRESENT_IN_THIS_UNIT')
variants.append(('SYNTHETIC_REMOVE_CONTRADICTING_LIMITS_KEEP_WRONG_LABELS',removed))
correct=deepcopy(response)
for u in correct['units']:
    for f in u['findings']:
        if f['kind']=='ACTUAL_PRODUCTION':f['kind']='OTHER_CONTEXT'
variants.append(('SYNTHETIC_QUALITATIVE_PRODUCTION_AS_OTHER_CONTEXT_KEEP_INDUSTRY_TARGET_LABEL',correct))
industry=deepcopy(correct)
for u in industry['units']:
    for f in u['findings']:
        if any(e['source_index'] in {476,669} for e in f['evidence']):f['subject']='OTHER_ENTITY'
variants.append(('SYNTHETIC_INDUSTRY_AS_OTHER_ENTITY_WITH_ORIGINAL_REFERENCES',industry))
rows=[]
for name,value in variants:
    try:
        checked=validate_response(request=request,raw_response=raw if name=='ORIGINAL' else _bytes(value))
        outcome={'accepted':True,'unresolved':checked['unresolved'],'finding_kinds':[f['kind'] for f in checked['findings']]}
    except Exception as exc:outcome={'accepted':False,'error_type':type(exc).__name__,'reason':str(exc)}
    rows.append({'variant':name,**outcome})
assert before==hashes()
report={'original_terminal_status':json.loads((root/'terminal.json').read_text())['status'],
        'original_request_id':request['request_id'],'original_target_finding':finding,'variants':rows,
        'original_files_sha256':before,'original_files_unchanged':True,'real_calls':[0,0,0],
        'changed_response_variants_are_synthetic':True,'native_Run_or_result_created':False,'usable_result_credit':False}
Path(__file__).with_name('result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(rows)
