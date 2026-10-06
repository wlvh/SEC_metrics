import json,os,pathlib,socket,sys,time
from unittest.mock import patch
program=pathlib.Path(sys.argv[1]);root=pathlib.Path(sys.argv[2]);fixture=pathlib.Path(sys.argv[3]);sys.path[:0]=[str(program),str(program/'scripts')]
os.environ['SEC_METRICS_ACQUISITION_TRUST_ROOT']=str(root/'trust/acquisition')
os.environ['SEC_METRICS_SOURCE_TRUST_ROOT']=str(root/'trust/company')
from vnext.company_local_acquisition import local_session,acquire_only
from sec_http import parse_request_log_rows
from vnext.company_handoff import export_company,install_company
from vnext.company_compute import compute_company
from vnext.company_result_export import export_results
from vnext.company_worker_guard import install_worker_guards
rows=parse_request_log_rows(text=(fixture/'evidence/requests_log.csv').read_text())
by_url={r['source_url']:r for r in rows if r['status_code']=='200' and not r['error']}
session=local_session(root=root/'acquisition',company_id='marriott_international',allowance=120,response=b'{}')
original=session.capture
missing=[]
def recorded(**kw):
 url=kw['url'];row=by_url.get(url)
 if row is None:
  missing.append(url);session.response=b'not in recorded fixture';session.response_status=404
 else:
  path=fixture/row['repo_relative_path'];session.response=path.read_bytes();session.response_status=200
 return original(**kw)
session.capture=recorded
start=time.monotonic()
with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS_FORBIDDEN')):
 result=acquire_only(session=session,company_id='marriott_international',max_requests=120)
 pathlib.Path(str(root)+'.acquire.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
 print(json.dumps({'stage':'acquire','status':result['status'],'seconds':round(time.monotonic()-start,3),'captures':len(result['captures']),'missing':missing}),flush=True)
 package=export_company(source_root=session.data_root,output_root=root/'handoff',trust_root=root/'trust/company',company_id='marriott_international',metric_ids=['B01','D01'])
 install_company(package_root=root/'handoff',state_root=root/'state',company_id='marriott_international')
# Calculation cannot read the fixture/preparer or access SEC.
os.environ['COMPANY_DENY_READ_ROOTS']=os.pathsep.join(map(str,[fixture,session.data_root,root/'trust/acquisition']))
install_worker_guards(program)
computed=compute_company(state_root=root/'state',company_id='marriott_international',metric_ids=['B01','D01'])
exported=export_results(state_root=root/'state',output_root=root/'export',company_id='marriott_international',runtime_roots=[program])
print(json.dumps({'stage':'compute/export','metrics':[{k:r.get(k) for k in ['metric_id','status','reason']} for r in computed['metrics']],'export_status':exported['status'],'seconds':round(time.monotonic()-start,3),'calls':[0,0,0],'recorded_only':True}),flush=True)
