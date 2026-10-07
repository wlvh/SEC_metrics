import csv,hashlib,io,json,os,subprocess,time
from pathlib import Path
repo=Path.cwd();base=repo/'docs/evidence/issue47_history/simplification-closeout-2026-10-08'
python='/Users/lyuhongwang/.codex/worktrees/issue47-history-continue/SEC_metrics/work/issue47-venv/bin/python'
source=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-development-evidence/source-only-b01-no-rules-20261007')
parent=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence');task=parent/'history-company-production-20261008'
for n in range(100):
 p=task if n==0 else task.with_name(task.name+'-'+str(n))
 if not p.exists():task=p;task.mkdir();break
args=['run','--company','marriott_international','--source-root',str(source),'--work-dir',str(task/'state'),'--output-dir',str(task/'outputs'),'--metric','B10','--metric','B11','--period','fiscal-years','--fiscal-year-start','2024','--fiscal-year-end','2025']
expected={('B10','2024'):'69.8',('B11','2024'):'128.23',('B10','2025'):'69.3',('B11','2025'):'128.8'}
def protected(root):
 return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file() and ('/results/' in str(p) or p.name in ['current-result.json','completed-check.json'])}
def invoke(label,a,forbid=False):
 code='import json,sys;from unittest.mock import patch;from tools.vnext_company import main\n'
 code+='with patch("socket.socket.connect", side_effect=AssertionError("No business network"))'
 if forbid:code+=', patch("vnext.historical_lodging_results.prepare_historical_lodging_case", side_effect=AssertionError("Factory must not calculate"))'
 code+=':\n raise SystemExit(main(json.loads(sys.argv[1])))'
 start=time.monotonic();r=subprocess.run([python,'-c',code,json.dumps(a)],capture_output=True,text=True,env={**os.environ,'PYTHONPATH':'scripts:.'},timeout=120)
 (base/(label+'.json')).write_text(r.stdout);(base/(label+'.stderr')).write_text(r.stderr)
 assert r.returncode==0,(label,r.stderr,r.stdout[:600]);d=json.loads(r.stdout)
 rows=list(csv.DictReader(io.StringIO((Path(d['output_root'])/'metrics_matrix.csv').read_text(encoding='utf-8-sig'))))
 assert {(x['metric_id'],x['fiscal_year']):x['value'] for x in rows}==expected
 return {'operation':label,'seconds':time.monotonic()-start,'status':d.get('status')},d
first,report=invoke('production-cli-first',args);before=protected(task/'state')
repeat,r=invoke('production-cli-repeat',args,True);assert protected(task/'state')==before
assert all(x['status']=='NO_SOURCE_CONTENT_CHANGE' and not x['calculation_performed'] for x in r['metrics'])
read,_=invoke('production-cli-independent-read',['results','--company','marriott_international','--state-root',str(task/'state'),'--output-root',str(task/'daily')],True);assert protected(task/'state')==before
old=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence/history-rule-root-20261007-1/state');oldbytes=protected(old)
oldread,_=invoke('retained-task-independent-read',['results','--company','marriott_international','--state-root',str(old),'--output-root',str(task/'retained-task-daily')],True);assert protected(old)==oldbytes
record={'task_root':str(task),'operations':[first,repeat,read,oldread],'factory_forbidden_on_repeat_and_reads':True,'result_and_pointer_files_unchanged':len(before),'old_task_protected_files':len(oldbytes),'production_case_factory_used':True,'business_outcomes_not_mocked':True,'calls':{'sec':0,'provider':0,'paid':0},'tree_copies':0}
(base/'production-cli.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
