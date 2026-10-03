import json,tempfile
from pathlib import Path
from types import SimpleNamespace
from contextlib import nullcontext
from unittest.mock import patch,Mock
from vnext.continuous_sec_acquisition import SecAcquisitionSession
from vnext import ordinary_refresh_cycle as r
results=[]
with tempfile.TemporaryDirectory() as temp:
 root=Path(temp).resolve()
 session=object.__new__(SecAcquisitionSession)
 snapshots=iter([{'counts':[10,10,20]},{'counts':[10,10,21]}])
 session.ledger=SimpleNamespace(live=True,root=root/'ledger',locked=nullcontext,snapshot=lambda:next(snapshots))
 session.data_root=session.ledger.root/'source-inputs';session.requirement={}
 session.capture=Mock(side_effect=RuntimeError('after native claim: response publication interrupted'))
 pfizer='https://data.sec.gov/submissions/CIK0000078003.json'
 def discover(*,company_id,**kwargs):
  return {'status':'SAVED_SOURCE_DEPENDENCIES_AVAILABLE','requirements_id':'recorded-discovery-'+company_id,'limitations':[],
   'requirements':[{'source_url':pfizer,'refresh_for_new_discovery':True,'saved_status':'VERIFIED_SAVED_SOURCE'}] if company_id=='pfizer' else []}
 def update(**kwargs):
  return {'status':'UPDATES_READY','metrics':[{'metric_id':'B01','status':'NO_SOURCE_CONTENT_CHANGE','last_verified_candidate':{'year':2025,'source':'unchanged-recorded-history'}}]}
 with patch.object(r,'_check_session'),patch.object(r,'initialize_source_inputs'),patch.object(r,'_failed_urls',return_value=set()),patch.object(r,'discover_saved_source_requirements',side_effect=discover),patch.object(r,'run_company',side_effect=update) as updater:
  value=r.refresh_and_process(session=session,state_root=root/'state',company_ids=['pfizer','jpmorgan_chase'],metric_ids=['B01'],max_sec_requests=5)
 assert session.capture.call_count==1 and updater.call_count==2
 assert value['status']=='CALL_ACCOUNTING_UNRESOLVED' and value['calls']['sec'] is None
 a,b=value['companies'];assert a['source_refresh']['status']=='REFRESH_INCOMPLETE' and b['status']=='REFRESHED_UPDATES_READY'
 assert all(c['updates']['metrics'][0]['last_verified_candidate']['year']==2025 for c in value['companies'])
 results.append({'case':'capture exception with claimed slot','result':'PASS','calls_report':value['calls'],'top_status':value['status'],'capture_invocations':1,'companies_still_processed':2,'unrelated_company':b['status']})
 snapshots=iter([{'counts':[10,10,21]},{'counts':[10,10,21]}]);session.capture.reset_mock()
 with patch.object(r,'_check_session'),patch.object(r,'initialize_source_inputs'),patch.object(r,'_failed_urls',return_value={pfizer}),patch.object(r,'discover_saved_source_requirements',side_effect=discover),patch.object(r,'run_company',side_effect=update):
  value=r.refresh_and_process(session=session,state_root=root/'second-state',company_ids=['pfizer','jpmorgan_chase'],metric_ids=['B01'],max_sec_requests=5)
 assert session.capture.call_count==0
 assert value['companies'][0]['source_refresh']['failed_source_urls_not_retried']==[pfizer]
 results.append({'case':'previous failed metadata URL on next invocation','result':'PASS','capture_invocations':0,'failed_url_preserved':True})
Path('/tmp/sec_metrics_issue28_continuous/refresh-release-independent-review/refresh-probe.json').write_text(json.dumps({'cases':results,'evidence_kind':'SYNTHETIC_COORDINATOR_BOUNDARY_WITH_READ_AND_SESSION_DOUBLES','actual_new_calls':[0,0,0]},indent=2)+'\n')
print(results)
