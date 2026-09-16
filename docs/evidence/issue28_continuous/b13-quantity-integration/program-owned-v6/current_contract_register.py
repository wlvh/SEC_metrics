from pathlib import Path
from unittest.mock import patch
import hashlib,json,socket,time
from vnext.continuous_semantic_calls import prepare_requests
from vnext.continuous_call_ledger import recorded_ledger
from vnext.capacity_assessment_input import register_assessment_input
from vnext.native_request_construction import request_construction_session
from vnext.requirements import load_requirement_snapshot
from vnext.normal_source_authority import ROOT
base=Path('/tmp/sec_metrics_issue28_continuous/b13-v6').resolve()
ledger=recorded_ledger(root=base/'material-enphase-format/ledger')
def files():return {str(p.relative_to(ledger.root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in ledger.root.rglob('*') if p.is_file()}
original=files();started=time.monotonic()
requirement=load_requirement_snapshot(snapshot_dir=ROOT/'requirements/issue_28_v14')
with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS_FORBIDDEN')),request_construction_session(requirement) as construction:
 prepared=prepare_requests(company_id='enphase_energy',metric_id='B13',reference_context=True,program_quantity_roles=True)
 print('prepared',len(prepared),time.monotonic()-started,flush=True)
 registered=register_assessment_input(prepared_requests=prepared,ledger=ledger)
 assert files()==original,'ORIGINAL_RECORDED_LEDGER_MUTATED'
 result={'status':'CURRENT_CONTRACT_ZERO_CALL_REREGISTRATION_PASS','input_record_id':registered['input_record_id'],
  'original_ledger_bytes_unchanged':True,'request_count':len(prepared),'new_executions':0,'new_real_calls':[0,0,0],
  'seconds':time.monotonic()-started,'requirement_closure_hash':requirement['requirement_closure_hash'],
  'evidence_type':'COMPLETE_REAL_SOURCE_RECORDED_RESPONSE_CURRENT_ACCEPTOR','new_native_run':False}
 (base/'current-contract-registration.json').write_text(json.dumps(result,indent=2)+'\n')
 print(result,flush=True)
