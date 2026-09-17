"""Zero-provider recovery of a complete original V6 company receipt set.

There is no provider execution function, API-key read or automatic retry here.
Choose a fresh output root when an earlier native installation stopped midway.
"""
from pathlib import Path
import argparse,hashlib,json,sys
R=Path('/Users/lyuhongwang/Developer/SEC_metrics')
sys.path[:0]=[str(R/'scripts'),'/tmp/sec_metrics_issue28_continuous/context-tokenizers-0222']
from vnext.requirements import load_requirement_snapshot
from vnext.continuous_call_ledger import live_ledger
from vnext.continuous_semantic_calls import prepare_requests
from vnext.capacity_native_assessment import collect_native_assessments
from vnext.capacity_assessment_input import register_assessment_input
from vnext.capacity_run import install_inputs
from vnext.normal_run_v3 import create_normal_run
from vnext.ordinary_projection import render_ordinary_run
from vnext.native_request_construction import request_construction_session
from vnext.canonical import canonical_json_bytes
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--company',choices=['enphase_energy','ford_motor_company'],required=True)
parser.add_argument('--output-root',type=Path,required=True)
a=parser.parse_args();assert a.output_root.is_absolute() and not a.output_root.exists()
q=load_requirement_snapshot(snapshot_dir=R/'requirements/issue_28_v14')
assert q['requirement_closure_hash']=='sha256:1ef08f67e6ef52e8fc4185d65b4c124a18c8d4e2dc8814495ea431e5a0fe7e1d','CURRENT_BINDING_CHANGED'
plan=json.loads((R/'docs/evidence/issue28_continuous/b13-quantity-integration/program-owned-v6/company-task-request-plan.json').read_text())
c=next(x for x in plan['companies'] if x['company_id']==a.company)
with request_construction_session(q):
 prepared=prepare_requests(company_id=a.company,metric_id='B13',reference_context=True,program_quantity_roles=True)
 assert len(prepared)==len(c['groups'])
 for p,g in zip(prepared,c['groups']):
  assert json.loads(p.request_bytes)['request_id']==g['request_id']
  assert hashlib.sha256(p.provider_request_body_bytes).hexdigest()==g['provider_body_sha256']
 ledger=live_ledger(requirement=q)
 assert ledger.root==Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
 with ledger.locked():before=ledger.snapshot()
 complete=collect_native_assessments(prepared_requests=prepared,ledger=ledger)
 assert complete['all_source_requests_accepted'],'INCOMPLETE_OR_REJECTED_ORIGINAL_SET_NO_PROVIDER_EXECUTION'
 registered=register_assessment_input(prepared_requests=prepared,ledger=ledger)
 a.output_root.mkdir(parents=True)
 (a.output_root/'registered.json').write_bytes(canonical_json_bytes(value={'input_record_id':registered['input_record_id'],'new_calls':[0,0,0]}))
 source=json.loads(prepared[0].source_bytes)
 install_inputs(data_root=a.output_root/'data',company_id=a.company,assessment_mode='LIVE',assessment_input_id=registered['input_record_id'],
  request_context_format=source.get('request_context_format'),program_quantity_roles=True)
 created=create_normal_run(data_root=a.output_root/'data',run_dir=a.output_root/'run',company_id=a.company,metric_id='B13')
 rendered=render_ordinary_run(data_root=a.output_root/'data',run_dir=a.output_root/'run')
 for name,raw in rendered['files'].items():
  target=a.output_root/'rows'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
 with ledger.locked():after=ledger.snapshot()
 # Other authorized work may run concurrently; this script makes no claims
 # and does not attribute another caller's cumulative delta to itself.
 summary={'status':'CURRENT_V6_ORIGINAL_SUCCESSES_NATIVE_FINISH','company_id':a.company,'new_provider_executions':0,
  'counts_before':before['counts'],'counts_after':after['counts'],'input_record_id':registered['input_record_id'],
  'result':created['result'],'rendered_row':rendered['row'],'production_authorized':False}
 (a.output_root/'completed.json').write_bytes(canonical_json_bytes(value=summary));print(json.dumps({'status':summary['status'],'result_id':created['result']['result_id'],'new_provider_executions':0}),flush=True)
