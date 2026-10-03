from pathlib import Path
from unittest.mock import patch
import hashlib,json,socket,time
from vnext.requirements import load_requirement_snapshot
from vnext.normal_source_authority import ROOT
from vnext.native_request_construction import request_construction_session
from vnext.continuous_call_ledger import recorded_ledger
from vnext.continuous_semantic_calls import prepare_requests,select_native_request_variants
from vnext.capacity_assessment_input import register_assessment_input,load_registered_input
from vnext.canonical import content_hash
evidence=Path(__file__).resolve().parent;root=Path('/tmp/sec_metrics_recovery110_wiring_20260922_v2/ledger');ledger=recorded_ledger(root=root)
def files():return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
before=files();req=load_requirement_snapshot(snapshot_dir=ROOT/'requirements/issue_28_v14');start=time.monotonic()
with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS_FORBIDDEN')),request_construction_session(req):
 originals=prepare_requests(company_id='enphase_energy',metric_id='B13',reference_context=True,program_quantity_roles=True)
 prepared,selection=select_native_request_variants(prepared_requests=originals,ledger=ledger,source_references=True)
 assert len(prepared)==6 and [r['original_ordinal'] for r in selection]==list(range(2,8))
 registered=register_assessment_input(prepared_requests=prepared,ledger=ledger)
 assert not registered['assessment']['failed_requests'] and len(registered['assessment']['recovered_http402_failures'])==1
 loaded=load_registered_input(data_root=ROOT,source=json.loads(prepared[0].source_bytes),requirement=req,mode='RECORDED_TEST_ONLY',input_record_id=registered['input_record_id'],check_export=False)
 assert loaded==registered and before==files()
 result={'status':'PASS_CURRENT_REGISTRATION_REPLAY_NO_NEW_EXECUTIONS','requirement_closure_hash':req['requirement_closure_hash'],'execution_authority_hash':content_hash(value=req['execution_authority']),'original_recorded_ledgers_unchanged':True,'registration_reader':'PASS','history_retained':'ORIGINAL_HTTP402_FAILURE_AND_APPROVED_NEW_SUCCESS','original_ordinals':[r['original_ordinal'] for r in selection],'new_calls':[0,0,0],'new_recorded_executions':0,'seconds':round(time.monotonic()-start,3)}
 (evidence/'current-registration.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
