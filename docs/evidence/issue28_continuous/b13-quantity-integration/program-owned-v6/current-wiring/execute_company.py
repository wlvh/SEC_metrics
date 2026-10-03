"""Prepare by default. Explicit --execute requires parent-selected counts/company.

No retries, no prompt edits, no ordinary B13 LIVE pause changes. The existing
native interface owns transport/receipt/acceptance. Old failed calls stay intact.
"""
from pathlib import Path
import argparse,hashlib,json,os,sys
R=Path('/Users/lyuhongwang/Developer/SEC_metrics')
sys.path[:0]=[str(R/'scripts'),'/tmp/sec_metrics_issue28_continuous/context-tokenizers-0222']
from vnext.canonical import canonical_json_bytes,strict_json_loads
from vnext.continuous_semantic_calls import prepare_requests,build_plan,request_digest,execute_capacity_assessment
from vnext.continuous_call_wiring import validate_wiring_receipt
from vnext.native_request_construction import request_construction_session
from vnext.requirements import load_requirement_snapshot
from vnext.capacity_native_assessment import collect_native_assessments
from vnext.capacity_assessment_input import register_assessment_input
from vnext.capacity_run import install_inputs
from vnext.normal_run_v3 import create_normal_run
from vnext.ordinary_projection import render_ordinary_run
P=R/'docs/evidence/issue28_continuous/b13-quantity-integration/program-owned-v6'
EXPECTED_CLOSURE='sha256:1ef08f67e6ef52e8fc4185d65b4c124a18c8d4e2dc8814495ea431e5a0fe7e1d' # Replaced with complete current-bound identity during preparation.
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--execute',action='store_true')
parser.add_argument('--company',choices=['enphase_energy','ford_motor_company'])
parser.add_argument('--expected-counts',help='Exact current provider,paid,SEC cumulative totals supplied by parent')
parser.add_argument('--max-provider-requests',type=int)
parser.add_argument('--output-root',type=Path,required=True)
args=parser.parse_args()
assert args.output_root.is_absolute() and not args.output_root.exists(),'NEW_ABSOLUTE_OUTPUT_ROOT_REQUIRED'
if args.execute:assert args.company and args.expected_counts and args.max_provider_requests is not None,'EXPLICIT_FINITE_EXECUTION_ARGUMENTS_REQUIRED'
else:assert args.expected_counts is None and args.max_provider_requests is None,'EXECUTION_ARGUMENTS_REQUIRE_EXECUTE'
requirement=load_requirement_snapshot(snapshot_dir=R/'requirements/issue_28_v14')
assert requirement['requirement_closure_hash']==EXPECTED_CLOSURE,'CURRENT_IMPLEMENTATION_BINDING_CHANGED'
plan=json.loads((P/'company-task-request-plan.json').read_text());counts=json.loads((P/'final-request-counts.json').read_text())
selected=[c for c in plan['companies'] if args.company is None or c['company_id']==args.company]
selected.sort(key=lambda c:c['company_id']!='enphase_energy')
args.output_root.mkdir(parents=True)
def save(name,value):
 with (args.output_root/name).open('xb') as f:f.write(canonical_json_bytes(value=value))
with request_construction_session(requirement):
 prepared_sets=[];preflight=[]
 for c in selected:
  prepared=prepare_requests(company_id=c['company_id'],metric_id='B13',reference_context=True,program_quantity_roles=True)
  measured=next(x for x in counts['companies'] if x['company_id']==c['company_id'])
  assert len(prepared)==len(c['groups'])==measured['request_count']
  for p,g,m in zip(prepared,c['groups'],measured['measurements']):
   r=json.loads(p.request_bytes);policy,invocation=build_plan(p)
   assert r['request_id']==g['request_id'],'PLANNED_REQUEST_ID_CHANGED'
   assert hashlib.sha256(p.provider_request_body_bytes).hexdigest()==g['provider_body_sha256']==m['request_sha256'],'PLANNED_PROVIDER_BODY_CHANGED'
   assert invocation['observability']['estimated_context_tokens']==m['context_tokens']<=200000
   assert len(p.provider_request_body_bytes)<=8388608
  validate_wiring_receipt(requirement=prepared[0].requirement)
  prepared_sets.append((c,prepared));preflight.append({'company_id':c['company_id'],'request_count':len(prepared),'all_original_request_ids_and_bodies_verified':True,'source_unit_count':len(json.loads(prepared[0].source_bytes)['units'])})
 save('preflight.json',{'status':'CURRENT_V6_FULL_COMPANY_PREPARATION_PASS','closure':requirement['requirement_closure_hash'],'companies':preflight,'calls':[0,0,0],'execution_requested':args.execute})
 print(json.dumps({'event':'PREFLIGHT_PASS','companies':preflight,'execution_requested':args.execute}),flush=True)
 if not args.execute:sys.exit(0)
 from vnext.continuous_call_ledger import live_ledger
 ledger=live_ledger(requirement=requirement)
 assert ledger.root==Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
 expected=[int(x) for x in args.expected_counts.split(',')];assert len(expected)==3
 c,prepared=prepared_sets[0]
 with ledger.locked():snapshot=ledger.snapshot()
 assert snapshot['counts']==expected and not snapshot['stopped_channels'],'FIXED_LEDGER_STATE_CHANGED_OR_STOPPED'
 # Reuse only original successful receipts that still pass full current checks.
 # Any original failed/unknown matching request is a stop, never a redraw.
 pending=[]
 for p in prepared:
  policy,_=build_plan(p);digest=request_digest(json.loads(p.request_bytes),policy)
  if ('PROVIDER',digest) not in snapshot['requests']:pending.append(p)
  else:
   matches=[r for r in snapshot['rows'] if json.loads((ledger.root/'calls'/('%04d'%r['ordinal'])/'intent.json').read_bytes())['request_digest']==digest]
   assert len(matches)==1 and matches[0]['status']=='SUCCEEDED','MATCHING_PRIOR_FAILURE_NO_RETRY'
 partial=collect_native_assessments(prepared_requests=prepared,ledger=ledger)
 assert len(partial['completed'])==len(prepared)-len(pending),'PRIOR_SUCCESS_CURRENT_ACCEPTOR_REJECTED'
 assert len(pending)<=args.max_provider_requests<=len(prepared),'FINITE_COMPANY_REQUEST_CAP_EXCEEDED'
 assert snapshot['counts'][0]+len(pending)<=240 and snapshot['counts'][1]+len(pending)<=240 and snapshot['counts'][2]<=80
 # Read the existing local credential only after all nonsecret preflight checks.
 # Never print its contents or put it in any report.
 if pending:
  secret=Path('/Users/lyuhongwang/.local/state/sec_metrics/private-credentials/deepseek-20260914.key').read_text().strip();assert secret
  os.environ['DEEPSEEK_API_KEY']=secret
 observations=[]
 for p in pending:
  r=json.loads(p.request_bytes)
  print(json.dumps({'event':'EXECUTE_ONE_CURRENT_NATIVE_REQUEST','company_id':c['company_id'],'request_id':r['request_id']}),flush=True)
  path,result=execute_capacity_assessment(prepared=p,ledger=ledger)
  wire=json.loads((path/'wire/journal.json').read_bytes())
  row={'ordinal':int(path.name),'request_id':r['request_id'],'terminal_status':result['terminal']['status'],'stop_reason':result['terminal']['stop_reason'],
   'usage':wire['usage'],'wire_error':wire['error_class'],'native_candidate_evidence_created':result.get('native_candidate_evidence_created',False),
   'response_check_error':result.get('response_check_error'),'complete_company_result':False}
  observations.append(row);save('request-%04d.json'%int(path.name),row);print(json.dumps(row),flush=True)
  if result['terminal']['status']!='SUCCEEDED':
   with ledger.locked():after=ledger.snapshot()
   save('stopped.json',{'status':'NATIVE_REQUEST_FAILED_NO_RETRY','observations':observations,'counts':after['counts'],'company_id':c['company_id'],'coordinate_complete':False})
   sys.exit(2)
 complete=collect_native_assessments(prepared_requests=prepared,ledger=ledger)
 assert complete['all_source_requests_accepted'],'COMPLETE_SOURCE_SET_REQUIRED'
 registered=register_assessment_input(prepared_requests=prepared,ledger=ledger)
 source=json.loads(prepared[0].source_bytes)
 install_inputs(data_root=args.output_root/'data',company_id=c['company_id'],assessment_mode='LIVE',assessment_input_id=registered['input_record_id'],
  request_context_format=source.get('request_context_format'),program_quantity_roles=True)
 created=create_normal_run(data_root=args.output_root/'data',run_dir=args.output_root/'run',company_id=c['company_id'],metric_id='B13')
 rendered=render_ordinary_run(data_root=args.output_root/'data',run_dir=args.output_root/'run')
 for name,raw in rendered['files'].items():
  target=args.output_root/'rows'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
 with ledger.locked():after=ledger.snapshot()
 save('completed.json',{'status':'COMPLETE_CURRENT_V6_NATIVE_COMPANY_RUN','company_id':c['company_id'],'request_count':len(prepared),'new_provider_executions':len(observations),
  'input_record_id':registered['input_record_id'],'result':created['result'],'rendered_row':rendered['row'],'counts_after':after['counts'],'ordinary_update_replay_still_required':True,'production_authorized':False})
 print(json.dumps({'event':'COMPLETE_NATIVE_COMPANY_RUN','company_id':c['company_id'],'counts_after':after['counts'],'result_id':created['result']['result_id']}),flush=True)
