import sys,json,copy,socket,hashlib
from pathlib import Path
from unittest.mock import patch
out=Path('/tmp/sec_metrics_issue28_continuous/b13-role-proof-independent-review/v4');sys.dont_write_bytecode=True
import vnext
vnext.__path__.insert(0,str(out/'overlay/scripts/vnext'))
from vnext import capacity_semantic_review as api,capacity_quantity_roles as roles
from vnext.r6_semantic_source import _bytes
ledger=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/calls');results=[]
def check(name,request,response):
 try:
  c=api.validate_response(request=request,raw_response=_bytes(response));results.append({'name':name,'accepted':True,'unresolved':c['unresolved'],'findings':[{k:f[k]for k in ['kind','subject','timing']}|{'indices':[e['source_index']for e in f['resolved_evidence']]}for f in c['findings']]})
 except Exception as e:results.append({'name':name,'accepted':False,'error':type(e).__name__,'reason':str(e)})
with patch.object(socket.socket,'connect',side_effect=AssertionError('Network forbidden')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS forbidden')):
 for ordinal in [82,94]:
  slot=ledger/f'{ordinal:04d}';request=json.loads((slot/'semantic-request.json').read_text());original=json.loads((slot/'wire/assistant-output.bin').read_bytes())
  check(str(ordinal)+'-original',request,original)
  variant=copy.deepcopy(original)
  for u in variant['units']:u['calculation_limits']=[]
  check(str(ordinal)+'-limits-only-removed',request,variant)
  if ordinal==82:
   for u in variant['units']:
    for f in u['findings']:
     if f['kind']=='ACTUAL_PRODUCTION':f['kind']='SALES_OR_SHIPMENTS'
   check('82-sales-role-correct-quarter-capacity-kept',request,variant)
   from vnext.native_unit_index import restore_base_request
   base=restore_base_request(request);units=api._restore_units(base['units'],base['shared_source_dictionaries'])
   text=next(b['text']for u in units if u['kind']=='VISIBLE_TEXT'for b in u['payload']['blocks']if b['block_index']==809)
   results.append({'name':'809-independent-role-proof','proofs':roles.physical_quantity_role_proofs(text)})
  else:
   for u in variant['units']:
    for f in u['findings']:
     if f['kind']=='ACTUAL_PRODUCTION':f['kind']='OTHER_CONTEXT'
   check('94-no-quantity-role-corrected-industry-still-wrong',request,variant)
   for u in variant['units']:
    for f in u['findings']:
     if any(e['source_index']in{476,669}for e in f['evidence']):f['subject']='OTHER_ENTITY'
   check('94-no-quantity-and-industry-corrected',request,variant)
report={'scope':'SYNTHETIC_CLASSIFICATION_VARIANTS_OVER_UNMODIFIED_REAL_REQUESTS_AND_REFERENCES_NOT_NEW_PROVIDER_RESULTS','results':results,'original_slots_unchanged':True,'new_calls':[0,0,0]}
(out/'real-variants.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2))
