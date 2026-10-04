import json,os,subprocess,sys
from pathlib import Path

code=Path(sys.argv[1]);source=Path('/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-external-source-20261004/source-inputs');out=Path(sys.argv[2]);report=Path(sys.argv[3])
sys.path.insert(0,str(code/'scripts'))
from vnext.normal_history_plan import checkpoint_replayed_once
from vnext.historical_xbrl_parse import xbrl_parsed_once
from vnext.normal_period_selection import resolve_period_selection
from vnext.historical_package import install_historical_inputs

def forbid(event,args):
    if event in {'socket.__new__','socket.connect','socket.getaddrinfo','socket.sendto'}:raise AssertionError('NETWORK_FORBIDDEN')
sys.addaudithook(forbid)
with checkpoint_replayed_once(),xbrl_parsed_once():
    selection=resolve_period_selection(repo_root=source,company_id='jpmorgan_chase',report_end='2022-12-31')
    result=install_historical_inputs(data_root=out,company_id='jpmorgan_chase',metric_id='B09',period_selection=selection,source_root=source)
binding=result['binding'];bid=binding['binding_id']
cold='''import json,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from vnext.historical_package import replay_historical_inputs
from vnext.normal_history_plan import checkpoint_replayed_once
from vnext.historical_xbrl_parse import xbrl_parsed_once
def forbid(event,args):
 if event in {'socket.__new__','socket.connect','socket.getaddrinfo','socket.sendto'}:raise AssertionError('NETWORK_FORBIDDEN')
sys.addaudithook(forbid)
with checkpoint_replayed_once(),xbrl_parsed_once():
 r=replay_historical_inputs(data_root=Path(sys.argv[2]),company_id='jpmorgan_chase',metric_id='B09',binding_id=sys.argv[3])
print(json.dumps({'binding':r['binding'],'value':r['result']['value'],'quality':r['result']['quality'],'calls':r['calls']}))
'''
reads=[]
for _ in range(2):
    r=subprocess.run([sys.executable,'-c',cold,str(code/'scripts'),str(out),bid],cwd='/tmp',capture_output=True,text=True,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
    if r.returncode:raise RuntimeError(r.stderr)
    read=json.loads(r.stdout);assert read['binding']==binding
    assert read['value']==result['installed']['primary_result']['value']
    reads.append(read)
assert reads[0]==reads[1]
body={'record_type':'ISSUE47_LOCAL_PRIVATE_CLONE_INSTALL_COLD_REPLAY_PROBE','code_root':str(code),'source_root':str(source),'installed_input_root':str(out),'install_receipt':result['receipt'],'binding':binding,'two_independent_process_reads':reads,'both_reads_identical':True,'code_from_private_clone_inputs_from_installed_root':True,'network_forbidden':True,'new_runs':0,'new_acceptances':0,'calls':[0,0,0]}
report.write_text(json.dumps(body,indent=1)+'\n');print(json.dumps({'binding_id':bid,'quality':reads[0]['quality'],'value':reads[0]['value'],'cold_reads':2,'new_runs':0,'calls':[0,0,0]}))
