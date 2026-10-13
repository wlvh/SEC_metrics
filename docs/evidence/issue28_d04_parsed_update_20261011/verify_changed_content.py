"""Reuse the completed actual task to prove a business change cannot be cached."""
import csv,hashlib,io,json,socket,time
from pathlib import Path
from unittest.mock import patch
from tools.vnext_company import main
from vnext import ordinary_current_update as update
from vnext.continuous_call_ledger import CallLedger
from vnext.recorded_sec_http import RecordedSecHttpClient
E=Path(__file__).parent;v=json.loads((E/'actual-company.json').read_text());ROOT=Path.cwd();SOURCE=Path(v['source_root']);STATE=Path(v['state']);base=STATE.parent
first=v['operations'][0]['report']['metrics'][0];result_root=Path(first['result_root']);snap=lambda root:{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()};before=snap(result_root)
client=RecordedSecHttpClient(recorded_root=SOURCE,workdir=SOURCE,config_path=ROOT/'config/sec_config.json',log_path=SOURCE/'evidence/requests_log.csv')
url='https://www.sec.gov/Archives/edgar/data/1048286/000104828626000007/mar-20251231.htm';original=(SOURCE/'evidence/raw/r2-live2/mar-20251231.htm').read_bytes();changed=original.replace(b'</body>',b'<p>Substantial doubt exists about our ability to continue as a going concern.</p></body>');assert changed!=original
with patch.object(client,'reply',return_value=(200,changed,{},'')):
 client._fetch_once(url=url,purpose='ISOLATED_R2_BUSINESS_CHANGE_CONTROL',local_path=SOURCE/'evidence/raw/r2-changed/mar-20251231.htm',attempt=0)
args=['run','--company','marriott_international','--source-root',str(SOURCE),'--metric','D04','--work-dir',str(STATE),'--output-dir',str(base/'changed-output')];out=io.StringIO();start=time.perf_counter()
with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),patch.object(CallLedger,'claim',side_effect=AssertionError('No real claims')),patch.object(update,'create_saved_result',side_effect=ValueError('CONTROL_CHANGED_TASK_REQUIRES_FULL_PROCESSING')) as full,patch('sys.stdout',out):code=main(args)
result=json.loads(out.getvalue());assert code==2 and full.call_count==1;assert result['metrics'][0]['status']=='INPUT_OR_EXECUTION_FAILED';assert result['metrics'][0]['reason']=='CONTROL_CHANGED_TASK_REQUIRES_FULL_PROCESSING';assert before==snap(result_root)
(E/'changed-content-result.json').write_text(json.dumps({'seconds':time.perf_counter()-start,'exit_code':code,'report':result,'complete_processor_entered':True,'original_result_unchanged':True,'scope':'Explicit test disclosure added to isolated original, not real new financial input; full processor stopped by control after correct changed-task dispatch, no model/candidate credited','new_calls':[0,0,0]},indent=2)+'\n');print('PASS_CHANGED_DISCLOSURE_NOT_REUSED',full.call_count,flush=True)
