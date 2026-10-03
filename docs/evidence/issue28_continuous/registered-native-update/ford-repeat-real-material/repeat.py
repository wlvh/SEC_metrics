"""Pinned installed runtime repeats the real Ford D04 history, with sockets forbidden."""
import sys,time,json,hashlib
from pathlib import Path
base=Path('/tmp/sec_metrics_issue28_continuous/ford-repeat-6ccf');runtime=base/'runtime'
sys.path[:0]=[str(runtime),str(runtime/'scripts'),'/tmp/sec_metrics_issue28_continuous/context-tokenizers-0222']
from vnext import ordinary_update_cycle as cycle,normal_run_v3 as normal
from vnext.canonical import strict_json_file
from vnext.requirements import load_requirement_snapshot
from vnext.continuous_call_ledger import CallLedger,_FACTORY
assert normal.ROOT==runtime.resolve();fixed=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
ledger=CallLedger(factory=_FACTORY,root=fixed,binding=strict_json_file(path=fixed/'binding.json'),live=True)
with ledger.locked():before=ledger.snapshot()['counts']
events=[];local=[]
def deny(event,args):
 if event in {'socket.connect','socket.getaddrinfo'}:events.append(event);raise RuntimeError('NETWORK_FORBIDDEN')
 if event=='subprocess.Popen':
  argv=list(args[1]);assert Path(str(args[0])).name=='git' and len(argv)>1 and argv[1]in{'show','ls-files','rev-parse'},'UNAPPROVED_PROCESS'
  local.append(argv)
sys.addaudithook(deny)
start=time.monotonic();requirement=load_requirement_snapshot(snapshot_dir=runtime/'requirements/issue_28_v14')
config=strict_json_file(path=base/'history/metrics/D04/configuration.json');assert requirement['requirement_closure_hash']==config['requirement_closure_hash']=='sha256:6ccf4a6e7c54c0d499945e0e9dae8cb61f8348312c24f1c78dac2311d108bfc4'
source_identity=json.loads((base/'runtime-copy.json').read_text())['files']
assert all(hashlib.sha256((runtime/n).read_bytes()).hexdigest()==h for n,h in source_identity.items())
original={str(p.relative_to(base/'history')):hashlib.sha256(p.read_bytes()).hexdigest()for p in (base/'history').rglob('*')if p.is_file()}
(base/'history-before.json').write_text(json.dumps(original,indent=2)+'\n');print('runtime/config verified; repeat started',flush=True)
result=cycle.run_company(state_root=base/'history',source_root=fixed/'source-inputs',company_id='ford_motor_company',metric_ids=['D04'],native_assessment_ledger=ledger)
with ledger.locked():after=ledger.snapshot()['counts']
changed=[n for n,h in original.items()if hashlib.sha256((base/'history'/n).read_bytes()).hexdigest()!=h]
row=result['metrics'][0];failure=strict_json_file(path=base/'history/metrics/D04/attempts/b322a01c9d3c4dd0983547ff3a2ed8c7/terminal.json')
report={'result':result,'counts_before':before,'counts_after':after,'network_events':events,'local_readonly_processes':local,'elapsed_seconds':time.monotonic()-start,'runtime_root':str(runtime),'requirement_closure_hash':requirement['requirement_closure_hash'],'original_history_changed_paths':changed,'original_failed_attempt':failure,'new_model_sec_calls':[0,0,0],'history_is_independent_byte_copy':True}
(base/'repeat-result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':result['status'],'metric_status':row['status'],'new_candidate':row.get('new_candidate_created'),'counts_before':before,'counts_after':after,'seconds':report['elapsed_seconds'],'changed_paths':changed},indent=2),flush=True)
assert result['status']=='UPDATES_READY'and row['status']=='NO_SOURCE_CONTENT_CHANGE'and row['new_candidate_created']is False and before==after and not events
assert row['successful_attempt']=='2f7f1821cfe244cb91a2525f0a8f61af'
assert changed==['metrics/D04/current.json'],changed
