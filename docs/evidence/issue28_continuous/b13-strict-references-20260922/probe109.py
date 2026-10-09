from pathlib import Path
import hashlib,json,time
from vnext.canonical import canonical_json_bytes
from vnext.native_unit_index import restore_response as restore_indexed
from vnext.capacity_reference_contract import upgrade_request,restore_response
from vnext.capacity_semantic_review import validate_response
root=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/calls/0109')
out=Path(__file__).resolve().parent
paths=[root/'semantic-request.json',root/'source.json',root/'wire/assistant-output.bin',root/'terminal.json']
original={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
request=json.loads(paths[0].read_bytes()); source=json.loads(paths[1].read_bytes());raw=paths[2].read_bytes()
started=time.monotonic()
try: validate_response(request=request,raw_response=raw,source=source)
except ValueError as exc:
 assert str(exc)=='B13_REFERENCE_OUTSIDE_SUPPLIED_SOURCE',str(exc)
else:raise AssertionError('Original failure incorrectly accepted')
base,normalized,_=(restore_indexed(request=request,raw_response=raw) if "indexed_unit_contract" in request else (request,raw,None))
old=json.loads(normalized)
flat={'units':[{'unit_index':i,**{k:v for k,v in row.items() if k not in {'unit_id','findings'}}} for i,row in enumerate(old['units'])],
      'findings':[finding for row in old['units'] for finding in row['findings']]}
new=upgrade_request(base)
restored,normalized,seen=restore_response(request=new,raw_response=canonical_json_bytes(value=flat))
checked=validate_response(request=restored,raw_response=normalized,source=source)
assert seen==flat and new['system_prompt']==base['system_prompt']
assert original=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
result={'status':'PASS_SYNTHETIC_CONTRACT_DIAGNOSTIC_ONLY','original109':'FAILED_TERMINAL_UNCHANGED','original_hashes':original,
 'new_contract':new['source_reference_contract']['version'],'findings':len(checked['findings']),
 'units':len(flat['units']),'prompt_unchanged':True,'source_unchanged':new['units']==base['units'],
 'new_calls':[0,0,0],'real_acceptance':False,'seconds':round(time.monotonic()-started,3)}
(out/'probe109.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
