import json,sys,shutil,os,socket
from pathlib import Path
from unittest.mock import patch
ROOT=Path('/Users/lyuhongwang/Developer/SEC_metrics');sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from vnext.normal_annual_input import prepare_saved_annual_input
from vnext.canonical import sha256_file
from vnext.ordinary_source_session import recorded_source_session,compare_annual_inputs
from vnext.sources import raw_blob_record,source_reference_record,companyfacts_structured_facts
from vnext.specs import compile_spec_file
from vnext.calculator import calculate_metric
from vnext.batch_workflow import _structured_concepts
from vnext.observations import scope_key
from vnext.traits import repository_company_traits
out=Path('/tmp/sec_metrics_issue28_continuous/ordinary-source-session-material-final').resolve();out.mkdir();data=out/'data'
with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),patch('sec_http.urlopen',side_effect=AssertionError('No HTTP')),patch.dict(os.environ,{'SEC_CONTACT_EMAIL':'sec-tests@wlvh.com'}):
 original=prepare_saved_annual_input(repo_root=ROOT,company_id='marriott_international')
 paths={'config/company_registry.csv','evidence/requests_log.csv','evidence/requests_log_manifest.json'}
 for proof in original['source_proofs']:paths.update([proof['request_repo_relative_path'],proof['request_headers_repo_relative_path']])
 for relative in paths:
  target=data/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/relative,target)
 session=recorded_source_session(data_root=data,journal_root=out/'journal',company_id=original['company_id'])
 for proof in original['source_proofs']:session.record_saved_response(url=proof['source_url'],accession=proof['accession'])
 updated=session.prepare_annual_input();prepared=updated['prepared_input'];args=prepared['companyfacts_input']
 blob=raw_blob_record(repo_root=data,repo_relative_path=args['source_repo_relative_path'],media_type='application/json')
 reference=source_reference_record(raw_blob=blob,company_id=prepared['company_id'],source_url=args['source_url'],
   accession=args['accession'],document_name=args['document_name'],source_role='companyfacts',request_attempt_id=args['request_attempt_id'])
 spec=compile_spec_file(path=ROOT/'catalog/metrics/B01_revenue.md',dependency_specs={})
 facts=companyfacts_structured_facts(raw_bytes=(data/args['source_repo_relative_path']).read_bytes(),source_reference=reference,
   approved_concepts=_structured_concepts(compiled_spec=spec),allowed_ciks=[prepared['entity']],include_instant=False)
 scope={'entity_scope':'registrant','period_basis':'source_annual_duration'};period=prepared['table_input']['target_period']
 target={'company_id':prepared['company_id'],'entity':prepared['entity'],'accession':prepared['filing']['accessionNumber'],
   'period_start':period['period_start'],'period_end':period['period_end'],'scope':scope,'scope_key':scope_key(scope=scope)}
 result,trace,observations=calculate_metric(compiled_spec=spec,target=target,company_traits=repository_company_traits(repo_root=ROOT,company_id=prepared['company_id']),
   structured_facts=facts,verified_observations=[])
 assert result['value']=='26186000000'
 report={'implementation_sha256':{f:sha256_file(path=ROOT/f) for f in ['scripts/vnext/ordinary_source_session.py','scripts/sec_http.py','scripts/vnext/normal_annual_input.py','scripts/vnext/calculator.py']},'status':'RECORDED_INPUT_AND_CALCULATOR_VALIDATED','original_input':original,'updated_input':updated,
   'change':compare_annual_inputs(previous=original,current=prepared),'result':result,'trace':trace,'observations':observations,
   'source_credit':'RECORDED_TEST_ONLY','native_run_created':False,'real_sec_credit':False,'calls':{'provider':0,'paid':0,'sec':0},'production_authorized':False}
(out/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(report['status'],report['change']['status'],result['value'],len(observations))
