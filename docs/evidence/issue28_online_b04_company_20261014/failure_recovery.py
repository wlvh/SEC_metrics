import hashlib,io,json,socket,sys,time
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
ROOT=Path(sys.argv[1]);OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'tools'),str(ROOT)]
from vnext_company import main
from vnext.recorded_sec_http import RecordedSecHttpClient
from vnext import current_statement_metric_case
original=RecordedSecHttpClient.reply;ops=[]
first=json.loads((OUT/'first.json').read_text());m=first['metrics'][0];saved=Path(m['result_root'])
files={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in saved.rglob('*') if p.is_file()}
args=['run','--company','marriott_international','--call-context',str(OUT/'context.json'),'--metric','B04','--work-dir',str(OUT/'task'),'--output-dir',str(OUT/'output'),'--max-sec-requests','20']
for name,fail in [('source-503',True),('source-restored',False)]:
 def reply(self,*,url):
  if fail and '/submissions/CIK0001048286.json' in url:return 503,b'recorded temporary failure',{},'recorded test 503'
  return original(self,url=url)
 stream=io.StringIO();start=time.perf_counter()
 with patch.object(RecordedSecHttpClient,'reply',reply),patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),patch.object(current_statement_metric_case,'prepare_current_statement_metric_case',side_effect=AssertionError('No unchanged or failed-source calculation')),redirect_stdout(stream):code=main(args)
 report=json.loads(stream.getvalue());seconds=time.perf_counter()-start;(OUT/(name+'.json')).write_text(json.dumps(report,indent=2)+'\n');ops.append({'phase':name,'seconds':seconds,'exit_code':code,'report':report})
 assert files=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in saved.rglob('*') if p.is_file()}
 print(name,code,seconds,report['discovery'],report['metrics'],flush=True)
 if fail:
  assert report['discovery']['status']=='SOURCE_DISCOVERY_FAILED'
  metric=report['metrics'][0]
  assert metric['status']=='INPUT_OR_EXECUTION_FAILED' or metric.get('source_observation_errors')
 else:
  assert code==0 and report['discovery']['status']=='SOURCES_READY_FOR_SELECTED_METRICS'
  metric=report['metrics'][0];assert metric['status']=='NO_SOURCE_CONTENT_CHANGE' and not metric['calculation_performed'] and metric['result_id']==m['result_id']
(OUT/'failure-recovery.json').write_text(json.dumps({'operations':ops,'old_result_files_preserved':len(files),'new_real_calls':[0,0,0],'source_failure_not_cached_as_success':True},indent=2)+'\n')
