"""Read actual owned saved sources through the factory; no claims, plans or calls."""
import argparse,hashlib,json,socket,sys,time
from pathlib import Path
from unittest.mock import patch
p=argparse.ArgumentParser();p.add_argument('--ledger-root',type=Path,required=True)
p.add_argument('--program-root',type=Path,default=Path(__file__).resolve().parents[3])
p.add_argument('--company',required=True);p.add_argument('--output',type=Path,required=True)
a=p.parse_args();assert not a.output.exists();root=a.ledger_root.resolve();start=time.monotonic()
ROOT=a.program_root.resolve();sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from vnext.continuous_call_ledger import CallLedger,_FACTORY
from vnext.continuous_semantic_calls import prepare_d03_replay_only_requests
from vnext.canonical import strict_json_file,strict_json_loads
tracked={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir() if p.is_file() and p.suffix in {'.json','.jsonl'}}
with (patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),
      patch.object(CallLedger,'claim',side_effect=AssertionError('No claim'))):
    ledger=CallLedger(factory=_FACTORY,root=root,binding=strict_json_file(path=root/'binding.json'),live=True)
    try:
        prepared=prepare_d03_replay_only_requests(company_id=a.company,source_root=root/'source-inputs',source_ledger=ledger)
        rows=[]
        for item in prepared:
            source=strict_json_loads(text=item.source_bytes.decode());request=strict_json_loads(text=item.request_bytes.decode())
            assert item.replay_only and source.get('external_replay_only') is True and request.get('external_replay_only') is True
            rows.append({'request_id':request['request_id'],'source_id':source['semantic_source_id'],
                'anchor_successor':'source_fact_review_contract' in request,'unit_ids':[u['unit_id'] for u in request['units']]})
        result={'status':'PREPARED_REPLAY_ONLY','groups':rows,'source_unit_ids':source['required_unit_ids']}
    except Exception as error:
        result={'status':'PREPARATION_FAILED','error_type':type(error).__name__,'reason':str(error)}
assert tracked=={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in tracked},'Original ledger metadata changed'
result.update(company_id=a.company,code_root=str(ROOT),source_root=str(root/'source-inputs'),
    elapsed_seconds=time.monotonic()-start,original_metadata_sha256=tracked,new_calls=[0,0,0],native_result_created=False)
a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in {'groups','source_unit_ids','original_metadata_sha256'}},indent=2))
if result['status']=='PREPARATION_FAILED':raise SystemExit(2)
