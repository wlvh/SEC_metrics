import sys,json,io,contextlib,socket
from pathlib import Path
from unittest.mock import patch
program=Path(sys.argv[1]).resolve();state=Path(sys.argv[2]).resolve();origin=Path('/Users/lyuhongwang/Developer/SEC_metrics')
sys.path[:0]=[str(program),str(program/'scripts')]
from tools.vnext_company import main
from sec_http import parse_request_log_rows
from vnext.continuous_call_ledger import CallLedger,_FACTORY
# Reuse a legal isolated recorded store from the passed original chain, not
# its Result or old computation. Only metadata gets new HTTP responses.
ctx=json.loads((state/'call-context.json').read_text());ctx['recorded_http_root']=str(origin);ctx['source_root']=str(state/'task/sources')
newctx=state/'shared-context.json';newctx.write_text(json.dumps(ctx))
rows=parse_request_log_rows(text=(origin/'evidence/requests_log.csv').read_text());byurl={r['source_url']:r for r in rows if r['status_code']=='200' and not r['error'] and (origin/r['repo_relative_path']).is_file()}
class Response(io.BytesIO):
 status=200;headers={'Content-Type':'application/json'}
requested=[]
def transport(*,request,timeout):
 url=request.full_url;requested.append(url)
 assert '/submissions/' in url or '/companyfacts/' in url,'Immutable source must be reused, not fetched'
 return Response((origin/byurl[url]['repo_relative_path']).read_bytes())
out=io.StringIO()
with patch('vnext.recorded_sec_http.RecordedSecHttpClient.reply',side_effect=lambda **kw: (200,transport(request=type('Request',(),{'full_url':kw['url']})(),timeout=60).getvalue(),{},'')),patch.object(socket.socket,'connect',side_effect=AssertionError('NO_NETWORK')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('NO_DNS')),contextlib.redirect_stdout(out):
 code=main(['run','--company','marriott_international','--work-dir',str(state/'new-company-task'),'--output-dir',str(state/'new-exports'),'--call-context',str(newctx),'--metric','B01','--metric','B02','--max-sec-requests','20'])
x=json.loads(out.getvalue());assert code==0 and x['status']=='FLOW_COMPLETED'
assert len(requested)==2
print(json.dumps({'code':code,'status':x['status'],'simulated_sec_claims':x['simulated_sec_claims'],'existing_source_root':ctx['source_root'],'requests':requested,'record_root':x['record_root'],'source_rows_kept':len(parse_request_log_rows(text=(Path(ctx['source_root'])/'evidence/requests_log.csv').read_text()))},indent=2))
