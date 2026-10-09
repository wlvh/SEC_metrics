"""Replace external HTTP only; use real CLI/discovery/store/calculation/CSV."""
import contextlib,csv,io,json,socket,sys,time
from pathlib import Path
from unittest.mock import patch

program=Path(sys.argv[1]).resolve();origin=Path(sys.argv[2]).resolve();state=Path(sys.argv[3]).resolve()
sys.path[:0]=[str(program),str(program/'scripts')]
from sec_http import parse_request_log_rows
from vnext.continuous_call_ledger import recorded_ledger
from vnext.canonical import content_hash
from tools.vnext_company import main

rows=parse_request_log_rows(text=(origin/'evidence/requests_log.csv').read_text())
by_url={r['source_url']:r for r in rows if r['status_code']=='200' and not r['error'] and (origin/r['repo_relative_path']).is_file()}
state.mkdir(parents=True,exist_ok=True)
ledger=recorded_ledger(root=state/'recorded-ledger',limits=(0,0,40))
with ledger.locked():ledger.snapshot()
context={'company_id':'marriott_international','metric_ids':['B01','B02'],
    'recorded_http_root':str(origin),'ledger_root':str(ledger.root),'maximum_counts':[0,0,40],
    'execution_mode':'RECORDED_TEST_ONLY','purpose':'remaining_development_feasibility',
    'requirement_id':'ordinary-company-capture-v1','requirement_closure_hash':content_hash(value={'recorded':True})}
path=state/'call-context.json';path.write_text(json.dumps(context))
calls=[]
class Response(io.BytesIO):
    status=200;headers={'Content-Type':'application/octet-stream'}

def http(*,request,timeout):
    url=request.full_url;calls.append(url)
    if url not in by_url:raise AssertionError('ORIGINAL_HTTP_REPLY_MISSING:'+url)
    row=by_url[url];raw=(origin/row['repo_relative_path']).read_bytes()
    assert len(raw)==int(row['content_length'])
    import hashlib
    assert hashlib.sha256(raw).hexdigest()==row['content_sha256']
    return Response(raw)

def adapted_http(url):
    from types import SimpleNamespace
    response=http(request=SimpleNamespace(full_url=url),timeout=60)
    return response.status,response.getvalue(),response.headers,''

def run(name, *, forbid_calculation=False):
    start=time.monotonic();out=io.StringIO()
    with contextlib.ExitStack() as stack:
        if forbid_calculation:stack.enter_context(patch('vnext.ordinary_saved_result._ordinary_case',side_effect=AssertionError('REPEAT_MUST_NOT_CALCULATE')))
        stack.enter_context(patch('vnext.recorded_sec_http.RecordedSecHttpClient.reply',side_effect=lambda **kw: adapted_http(kw['url'])))
        stack.enter_context(patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')))
        stack.enter_context(patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS_FORBIDDEN')))
        stack.enter_context(contextlib.redirect_stdout(out))
        code=main(['run','--company','marriott_international','--work-dir',str(state/'task'),
            '--output-dir',str(state/'exports'),'--call-context',str(path),
            '--metric','B01','--metric','B02','--max-sec-requests','20'])
    result=json.loads(out.getvalue());result['cli_return_code']=code;result['elapsed_seconds']=time.monotonic()-start
    (state/(name+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2))
    with (Path(result['output_root'])/'metrics_matrix.csv').open() as f:matrix=list(csv.DictReader(f))
    print(name,round(result['elapsed_seconds'],3),result['status'],result['discovery'],[(r['metric_id'],r['value'],r['status']) for r in matrix],flush=True)
    return result
first=run('first');repeat=run('repeat',forbid_calculation=True)
assert first['status']==repeat['status']=='FLOW_COMPLETED'
assert all(m['status']=='NO_SOURCE_CONTENT_CHANGE' for m in repeat['metrics'])
assert [m['result_root'] for m in first['metrics']]==[m['result_root'] for m in repeat['metrics']]
print('HTTP boundary calls',len(calls),calls,flush=True)
print('RESULT_IDS',[(r.get('metric_id'),r.get('saved_result_id')) for r in repeat['metrics']],flush=True)
# A related source-byte change must reach the actual calculation. This is a
# deliberate test mutation of a saved CompanyFacts body, not a reported result.
original_http=http
mutated=[]
def changed_http(*,request,timeout):
    response=original_http(request=request,timeout=timeout)
    if '/companyfacts/' not in request.full_url:return response
    facts=json.loads(response.getvalue())
    for concept in facts['facts']['us-gaap'].values():
        for units in concept.get('units',{}).values():
            for row in units:
                if row.get('accn')=='0001048286-26-000007' and row.get('end')=='2025-12-31' and row.get('val')==26186000000:
                    row['val']=26187000000;mutated.append(row)
    assert mutated
    return Response(json.dumps(facts).encode())
http=changed_http
changed=run('changed-test-input')
assert all(m['status']=='CANDIDATE_READY' for m in changed['metrics'])
assert [m['result_root'] for m in changed['metrics']]!=[m['result_root'] for m in first['metrics']]
http=original_http
# A failed metadata fetch must not call the old input current-success. The old
# result still has its original period, as history, and no failed check is cached.
def failed_http(*,request,timeout):
    if '/companyfacts/' in request.full_url:
        r=Response(b'recorded fixture failure');r.status=503;return r
    return original_http(request=request,timeout=timeout)
http=failed_http
failed=run('failed-refresh')
assert failed['status']=='FLOW_COMPLETED_WITH_LIMITATIONS'
assert all(m['status']=='INPUT_OR_EXECUTION_FAILED' for m in failed['metrics'])
with (Path(failed['output_root'])/'metrics_matrix.csv').open() as stream: failed_rows=list(csv.DictReader(stream))
assert all(m['source_observation_status']=='FAILED_CURRENT_CHECK' and m['period_role']=='PREVIOUS_RESULT' for m in failed_rows)
http=original_http
recovered=run('recovered-refresh')
assert recovered['status']=='FLOW_COMPLETED'
# Restore HTTP adapter for independent read: no networking and no calculation.
from tools.vnext_company import main as read_main
out=io.StringIO();started=time.monotonic()
with patch('sec_http.urlopen',side_effect=AssertionError('READ_MUST_NOT_FETCH')),patch('vnext.ordinary_saved_result._ordinary_case',side_effect=AssertionError('READ_MUST_NOT_CALCULATE')),contextlib.redirect_stdout(out):
    code=read_main(['results','--state-root',str(state/'task/company-state'),'--company','marriott_international'])
view=json.loads(out.getvalue());assert code in (0,2)
(state/'read.json').write_text(json.dumps(view,ensure_ascii=False,indent=2))
print('independent-read',time.monotonic()-started,[(r['metric_id'],r.get('source_observation_status'),r.get('period_role')) for r in view['metrics']],flush=True)

# Independent next task; no old successful results can mask this local failure.
original_state=state
state=original_state/'prior-file-failure';state.mkdir()
local_ledger=recorded_ledger(root=state/'recorded-ledger',limits=(0,0,40))
with local_ledger.locked():local_ledger.snapshot()
local_context={**context,'ledger_root':str(local_ledger.root)}
path=state/'call-context.json';path.write_text(json.dumps(local_context))
def prior_failure_http(*,request,timeout):
    if request.full_url.endswith('/mar-20241231.htm'):
        r=Response(b'recorded missing prior primary');r.status=404;return r
    return original_http(request=request,timeout=timeout)
http=prior_failure_http
partial=run('prior-source-failed')
assert partial['status']=='FLOW_COMPLETED_WITH_LIMITATIONS'
assert {m['metric_id']:m['status'] for m in partial['metrics']}=={'B01':'CANDIDATE_READY','B02':'CANDIDATE_WITHHELD'}
assert partial['metrics'][1]['result_reason_code']=='NORMAL_COMPANYFACTS_ROUTE_UNRESOLVED'
assert partial['metrics'][1]['source_observation_errors'][0]['status_code']=='404'
print('PASS_REAL_HTTP_BOUNDARY_PROGRAM_CHAIN',flush=True)
