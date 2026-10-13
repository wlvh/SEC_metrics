"""Existing actual current C04 success survives a later required-source failure."""
import hashlib,io,json,socket,time
from pathlib import Path
from unittest.mock import patch
from tools.vnext_company import main
from vnext import ordinary_current_update as update
from vnext.recorded_sec_http import RecordedSecHttpClient
E=Path(__file__).parent;v=json.loads((E/'source-only.json').read_text());a=v['args'];source=Path(a[a.index('--source-root')+1]);state=Path(a[a.index('--work-dir')+1]);root=Path(v['report']['metrics'][0]['result_root']);snapshot=lambda r:{str(p.relative_to(r)):hashlib.sha256(p.read_bytes()).hexdigest() for p in r.rglob('*') if p.is_file()};old=snapshot(root);client=RecordedSecHttpClient(recorded_root=source,workdir=source,config_path=Path.cwd()/'config/sec_config.json',log_path=source/'evidence/requests_log.csv');url='https://www.sec.gov/Archives/edgar/data/1048286/000104828626000007/mar-20251231.htm'
with patch.object(client,'reply',return_value=(503,b'CONTROL_REQUIRED_SOURCE_UNAVAILABLE',{},'isolated test failure')):client._fetch_once(url=url,purpose='ISOLATED_CURRENT_C04_FAILURE_CONTROL',local_path=source/'evidence/raw/failed-current/mar-20251231.htm',attempt=0)
out=io.StringIO();start=time.perf_counter()
with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),patch.object(update,'create_saved_result',side_effect=AssertionError('Do not reprocess failed selected source')),patch('sys.stdout',out):code=main(a)
value=json.loads(out.getvalue());assert code==2 and value['metrics'][0]['status']=='INPUT_OR_EXECUTION_FAILED';assert 'LATEST_SOURCE_REQUEST_FAILED' in value['metrics'][0]['reason'];assert snapshot(root)==old
before=snapshot(state);out=io.StringIO();startread=time.perf_counter()
with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),patch('sys.stdout',out):read=main(['results','--company','marriott_international','--state-root',str(state),'--output-root',str(state.parent/'failed-read')])
reader=json.loads(out.getvalue());assert read==0;assert snapshot(state)==before;assert reader['metrics'][0]['latest_observation']=='INPUT_OR_EXECUTION_FAILED';assert reader['metrics'][0]['period_end']=='2025-12-31';report={'failed_check':value,'seconds':startread-start,'read':reader,'read_seconds':time.perf_counter()-startread,'old_result_unchanged':True,'read_state_unchanged':True,'scope':'Explicit503 recorded in isolated minimalpackage; actual private source/ledger unchanged','new_calls':[0,0,0]};(E/'source-failure.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS_CURRENT_C04_FAILED_SOURCE_PRESERVES_HISTORY',value['metrics'][0]['reason'])
