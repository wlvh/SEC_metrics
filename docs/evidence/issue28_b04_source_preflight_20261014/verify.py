import hashlib,io,json,socket,sys,time
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
ROOT=Path(sys.argv[1]);OUT=Path(__file__).resolve().parent;sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'tools'),str(ROOT)]
from vnext_company import main
from vnext.continuous_call_ledger import CallLedger
from sec_http import SecHttpClient
SOURCE=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/source-inputs')
protected=[SOURCE/'config/company_registry.csv',SOURCE/'evidence/requests_log.csv',SOURCE/'evidence/requests_log_manifest.json']
def hashes(paths):return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
before=hashes(protected);results=[]
with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),patch.object(CallLedger,'claim',side_effect=AssertionError('No calls')),patch.object(SecHttpClient,'fetch',side_effect=AssertionError('No SEC fetch')),patch('vnext.calculator.calculate_metric',side_effect=AssertionError('No computation')):
 for company,end in [('marriott_international','2025-12-31'),('jpmorgan_chase','2025-12-31'),('salesforce','2026-01-31')]:
  stream=io.StringIO();start=time.perf_counter()
  with redirect_stdout(stream):code=main(['sources','--company',company,'--source-root',str(SOURCE),'--report-end',end,'--metric','B04'])
  seconds=time.perf_counter()-start;report=json.loads(stream.getvalue());(OUT/(company+'.json')).write_text(json.dumps(report,indent=2)+'\n')
  assert code==0 and report['status']=='SAVED_SOURCE_BYTES_AVAILABLE',report
  assert not report['metric_executed'] and not report['fetch_authorized'] and not report['metric_acceptance_proven']
  assert not any('instance' in role or 'accession_index' in role or 'prior' in role for r in report['requirements'] for role in r['roles'])
  paths=[SOURCE/r['request_repo_relative_path'] for r in report['requirements'] if r.get('request_repo_relative_path')]
  results.append({'company_id':company,'report_end':end,'seconds':seconds,'exit_code':code,'requirement_count':len(report['requirements']),'status':report['status'],'raw_original_period':report['original_annual_period'],'requirements_id':report['requirements_id'],'source_files_hashes':hashes(paths),'calls':report['calls']});print(company,seconds,len(report['requirements']),report['original_annual_period'],flush=True)
assert before==hashes(protected)
(OUT/'summary.json').write_text(json.dumps({'code_root':str(ROOT),'code_state':'named uncommitted B04 preflight changes','rows':results,'source_log_and_registry_preserved':True,'new_calls':[0,0,0],'no_result_or_acceptance':True},indent=2)+'\n')
