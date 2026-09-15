"""Read-only variants of the actual rejected 82 response; no execution credit."""
from pathlib import Path
from copy import deepcopy
import hashlib,json
from vnext.capacity_semantic_review import validate_response
from vnext.r6_semantic_source import _bytes
root=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/calls/0082')
files=['semantic-request.json','source.json','wire/assistant-output.bin','wire/journal.json','intent.json','terminal.json']
def hashes():return {p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in files}
before=hashes();request=json.loads((root/'semantic-request.json').read_text());raw=(root/'wire/assistant-output.bin').read_bytes();response=json.loads(raw)
unit=next(u for u in response['units'] if u['unit_index']==2)
finding=next(f for f in unit['findings'] if any(e['source_index']==883 for e in f['evidence']))
variants=[('ORIGINAL',response)]
removed=deepcopy(response);next(u for u in removed['units'] if u['unit_index']==2)['calculation_limits'].remove('TARGET_CURRENT_PRODUCTION_NOT_PRESENT_IN_THIS_UNIT')
variants.append(('SYNTHETIC_REMOVE_CONTRADICTING_LIMIT_KEEP_WRONG_PRODUCTION_LABEL',removed))
correct=deepcopy(response)
next(f for f in next(u for u in correct['units'] if u['unit_index']==2)['findings'] if any(e['source_index']==883 for e in f['evidence']))['kind']='OTHER_CONTEXT'
variants.append(('SYNTHETIC_OTHER_CONTEXT_ORIGINAL_REFERENCES_AND_LIMITS',correct))
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
