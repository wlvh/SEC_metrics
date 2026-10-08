"""Affected company CLI check using an existing source-only saved package."""
import csv, hashlib, io, json, os, subprocess, time
from pathlib import Path
repo=Path.cwd();python=repo/'work/issue47-venv/bin/python'
base=repo/'docs/evidence/issue47_history/company-ordinary-receiving-2026-10-07'
source=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-development-evidence/source-only-b01-no-rules-20261007')
parent=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence');parent.mkdir(parents=True,exist_ok=True)
task=parent/'history-rule-root-20261007'
for suffix in range(100):
 candidate=task if suffix==0 else parent/(task.name+'-'+str(suffix))
 if not candidate.exists():task=candidate;task.mkdir();break
else:raise RuntimeError('No unused local task path')
assert not (source/'catalog').exists() and not (source/'scripts').exists()
assert {p.name for p in (source/'config').iterdir()}=={'company_registry.csv'}
def digest_tree(root):return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
source_before=digest_tree(source)
ledger=Path('/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-sec-ledger-resume-20261006/claims.jsonl');ledger_before=ledger.read_bytes()
common=['run','--company','marriott_international','--source-root',str(source),'--work-dir',str(task/'state'),'--output-dir',str(task/'outputs'),'--metric','B10','--metric','B11']
def invoke(label,args,forbid=False):
 code='import sys,json;from unittest.mock import patch;from tools.vnext_company import main;'
 if forbid:
  code+='\nwith patch("socket.socket.connect",side_effect=AssertionError("No business network")),patch("vnext.historical_lodging_results.prepare_historical_lodging_case",side_effect=AssertionError("Unchanged history must not calculate")):\n raise SystemExit(main(json.loads(sys.argv[1])))'
 else:
  code+='\nwith patch("socket.socket.connect",side_effect=AssertionError("No business network")):\n raise SystemExit(main(json.loads(sys.argv[1])))'
 start=time.monotonic();p=subprocess.run([str(python),'-c',code,json.dumps(args)],env={**os.environ,'PYTHONPATH':'scripts:.'},capture_output=True,text=True,timeout=300)
 (base/(label+'.json')).write_text(p.stdout);(base/(label+'.stderr')).write_text(p.stderr)
 if p.returncode:raise AssertionError((label,p.returncode,p.stderr,p.stdout[:200]))
 return {'label':label,'elapsed_seconds':time.monotonic()-start,'exit_code':p.returncode,'report':json.loads(p.stdout)}
def protected():
 return {str(p.relative_to(task/'state/updates')):hashlib.sha256(p.read_bytes()).hexdigest() for p in (task/'state/updates').rglob('*') if p.is_file() and ('/results/' in str(p) or p.name=='current-result.json')}
def rows(op):return list(csv.DictReader(io.StringIO(Path(op['report']['output_root'],'metrics_matrix.csv').read_text(encoding='utf-8-sig'))))
args=common+['--period','fiscal-years','--fiscal-year-start','2024','--fiscal-year-end','2025']
first=invoke('history-rule-root-final-first',args)
expected={('B10','2024'):('69.8','percent'),('B11','2024'):('128.23','USD'),('B10','2025'):('69.3','percent'),('B11','2025'):('128.8','USD')}
assert {(r['metric_id'],r['fiscal_year']):(r['value'],r['unit']) for r in rows(first)}==expected
assert all((r['period_start'],r['period_end'])==(r['fiscal_year']+'-01-01',r['fiscal_year']+'-12-31') for r in rows(first))
before=protected()
repeat=invoke('history-rule-root-final-repeat',args,True)
assert all(m['status']=='NO_SOURCE_CONTENT_CHANGE' and not m['calculation_performed'] for m in repeat['report']['metrics'])
assert protected()==before
read=invoke('history-rule-root-final-read',['results','--company','marriott_international','--state-root',str(task/'state'),'--output-root',str(task/'daily')])
assert {(r['metric_id'],r['fiscal_year']):(r['value'],r['unit']) for r in rows(read)}==expected
assert protected()==before
current=invoke('history-rule-root-final-current',common+['--period','latest-complete-fy'])
assert {(r['metric_id'],r['fiscal_year']):(r['value'],r['unit']) for r in rows(current)}=={k:v for k,v in expected.items() if k[1]=='2025'}
assert digest_tree(source)==source_before and ledger.read_bytes()==ledger_before
record={'record_type':'HISTORICAL_COMPANY_SOURCE_RULE_ROOT_RECEIVING','source_root':str(source),'rules_root':str(repo),'task_root':str(task),'source_contents':'Originals/headers/request log and company_registry only; no catalog, calculation config, code or answers. Existing package read without copying.','source_file_count':len(source_before),'source_files_unchanged':True,'shared_public_updater_store_reader':True,'actual_rows':[dict(metric_id=m,fiscal_year=y,value=v,unit=u) for (m,y),(v,u) in expected.items()],'operations':[{k:v for k,v in op.items() if k!='report'}|{'status':op['report'].get('status')} for op in [first,repeat,read,current]],'repeat_factory_forbidden':True,'result_and_pointer_bytes_unchanged_on_repeat_and_read':True,'ordinary_check_intents_and_terminals_may_append':True,'protected_result_file_count':len(before),'program_or_source_tree_copies':0,'calls':{'provider':0,'paid':0,'sec':0},'ledger_unchanged_sha256':hashlib.sha256(ledger_before).hexdigest(),'old_runs_rewritten':False,'automatic_historical_source_acquisition':False,'full_five_year_business_accepted':False}
(base/'history-rule-root-validation.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({op['label']:round(op['elapsed_seconds'],6) for op in [first,repeat,read,current]}))
