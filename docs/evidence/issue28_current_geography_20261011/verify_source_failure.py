"""A required-source failure is visible, not replaced by an old current success."""
import hashlib,io,json,socket,time
from pathlib import Path
from unittest.mock import patch
from tools.vnext_company import main
from vnext import ordinary_current_update as update
from vnext.recorded_sec_http import RecordedSecHttpClient
E=Path(__file__).parent;v=json.loads((E/'source-only.json').read_text());args=v['args']
source=Path(args[args.index('--source-root')+1]);state=Path(args[args.index('--work-dir')+1])
record=Path(v['report']['metrics'][0]['result_root'])
def snapshot(root):
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}
old=snapshot(record);m=json.loads((record/'manifest.json').read_text())
primary=next(p for p in m['source_proofs'] if p['document_name']=='jpm-20251231.htm')
client=RecordedSecHttpClient(recorded_root=source,workdir=source,config_path=Path.cwd()/'config/sec_config.json',log_path=source/'evidence/requests_log.csv')
with patch.object(client,'reply',return_value=(503,b'CONTROL_MISSING_CURRENT_SOURCE',{},'isolated required source failure')):
    client._fetch_once(url=primary['source_url'],purpose='ISOLATED_A13_SOURCE_FAILURE',
                       local_path=source/'evidence/raw/failure/jpm-20251231.htm',attempt=0)
out=io.StringIO();start=time.perf_counter()
with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),patch.object(update,'create_saved_result',side_effect=AssertionError('Do not calculate failed source')),patch('sys.stdout',out):code=main(args)
report=json.loads(out.getvalue());seconds=time.perf_counter()-start
assert code==2 and report['metrics'][0]['status']=='INPUT_OR_EXECUTION_FAILED',report
assert 'LATEST_SOURCE_REQUEST_FAILED' in report['metrics'][0]['reason'] and old==snapshot(record)
before=snapshot(state);out=io.StringIO();start=time.perf_counter()
with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),patch('sys.stdout',out):
    code=main(['results','--company','jpmorgan_chase','--state-root',str(state),'--output-root',str(state.parent/'failed-read')])
reader=json.loads(out.getvalue());read_seconds=time.perf_counter()-start
assert code==0 and reader['metrics'][0]['latest_observation']=='INPUT_OR_EXECUTION_FAILED',reader
assert reader['metrics'][0]['period_end']=='2025-12-31' and before==snapshot(state)
(E/'source-failure.json').write_text(json.dumps({'report':report,'seconds':seconds,'read':reader,
    'read_seconds':read_seconds,'old_result_preserved':True,'read_state_unchanged':True,
    'source_failure':'Explicit recorded503 in isolated copied sources; no private source/ledger change',
    'new_calls':[0,0,0]},indent=2)+'\n')
print('PASS_CURRENT_A13_FAILED_SOURCE_PRESERVES_HISTORY',report['metrics'][0]['reason'])
