import csv,hashlib,io,json,os,subprocess,time
from pathlib import Path
repo=Path.cwd();python=repo/'work/issue47-venv/bin/python'
base=repo/'docs/evidence/issue47_history/company-ordinary-receiving-2026-10-07'
task=repo.parent/'SEC_metrics-issue47-ordinary-history-range-20261007'
assert not task.exists();task.mkdir()
source=repo.parent/'SEC_metrics-issue47-company-verified-source-20261006/source-inputs'
ledger=repo.parent/'SEC_metrics-issue47-sec-ledger-resume-20261006/claims.jsonl'
ledger_before=ledger.read_bytes()
common=['run','--company','marriott_international','--source-root',str(source),'--work-dir',str(task/'state'),'--output-dir',str(task/'outputs'),'--metric','B10','--metric','B11']
def invoke(label,args,forbid=False):
    code='import sys,json;from unittest.mock import patch;from tools.vnext_company import main;'
    if forbid:
        code+='\nwith patch("socket.socket.connect",side_effect=AssertionError("No business network")),patch("vnext.historical_lodging_results.prepare_historical_lodging_case",side_effect=AssertionError("Unchanged historical case must not calculate")):\n raise SystemExit(main(json.loads(sys.argv[1])))'
    else:
        code+='\nwith patch("socket.socket.connect",side_effect=AssertionError("No business network")):\n raise SystemExit(main(json.loads(sys.argv[1])))'
    start=time.monotonic();p=subprocess.run([str(python),'-c',code,json.dumps(args)],env={**os.environ,'PYTHONPATH':'scripts:.'},capture_output=True,text=True,timeout=300)
    (base/(label+'.json')).write_text(p.stdout);(base/(label+'.stderr')).write_text(p.stderr)
    result=json.loads(p.stdout);return {'label':label,'elapsed_seconds':time.monotonic()-start,'exit_code':p.returncode,'report':result}
def snapshot():
    return {str(p.relative_to(task/'state')):hashlib.sha256(p.read_bytes()).hexdigest() for p in (task/'state/updates').rglob('*') if p.is_file() and ('/results/' in str(p) or p.name=='current-result.json')}
def rows(report):
    return list(csv.DictReader(io.StringIO(Path(report['report']['output_root'],'metrics_matrix.csv').read_text(encoding='utf-8-sig'))))
first=invoke('history-range-first',common+['--period','fiscal-years','--fiscal-year-start','2024','--fiscal-year-end','2025'])
assert first['exit_code']==0,first
expected={('B10','2024'):('69.8','percent'),('B11','2024'):('128.23','USD'),('B10','2025'):('69.3','percent'),('B11','2025'):('128.8','USD')}
actual={(r['metric_id'],r['fiscal_year']):(r['value'],r['unit']) for r in rows(first)}
assert actual==expected,actual
before=snapshot()
repeat=invoke('history-range-repeat',common+['--period','fiscal-years','--fiscal-year-start','2024','--fiscal-year-end','2025'],True)
assert repeat['exit_code']==0
assert all(m['status']=='NO_SOURCE_CONTENT_CHANGE' and not m['calculation_performed'] for m in repeat['report']['metrics'])
assert snapshot()==before
read=invoke('history-range-independent-read',['results','--company','marriott_international','--state-root',str(task/'state'),'--output-root',str(task/'daily-first'),'--defects-file',str(repo/'docs/evidence/issue47_history/known_result_defects.json')])
assert read['exit_code']==0
assert snapshot()==before
current=invoke('history-range-current-mode',common+['--period','latest-complete-fy'])
assert current['exit_code']==0
assert {(r['metric_id'],r['fiscal_year']):(r['value'],r['unit']) for r in rows(current)}=={k:v for k,v in expected.items() if k[1]=='2025'}
preserved=snapshot()
missing=invoke('history-range-missing-year',common+['--period','fiscal-years','--fiscal-year-start','2025','--fiscal-year-end','2026'],True)
assert missing['exit_code']==2
assert snapshot()==preserved
missing_rows=rows(missing)
assert all(r['value']=='' and r['period_start']=='' and r['period_end']=='' for r in missing_rows if r['fiscal_year']=='2026')
assert len([r for r in missing_rows if r['fiscal_year']=='2026'])==2
read_missing=invoke('history-range-read-after-missing',['results','--company','marriott_international','--state-root',str(task/'state'),'--output-root',str(task/'daily-after-missing'),'--defects-file',str(repo/'docs/evidence/issue47_history/known_result_defects.json')])
assert snapshot()==preserved
assert ledger.read_bytes()==ledger_before
record={'public_code':'72394740c3140b72119ae4627a6ce1fd5257a29e','company_cli':'tools/vnext_company.py','source_mode':'SAVED_ONLY_NO_ONLINE_DISCOVERY','task_root':str(task),
 'actual_rows':actual and [{'metric_id':m,'fiscal_year':y,'value':v,'unit':u} for (m,y),(v,u) in actual.items()],
 'operations':[{k:v for k,v in o.items() if k!='report'}|{'status':o['report'].get('status'),'metrics':[{'metric_id':m.get('metric_id'),'fiscal_year':m.get('requested_fiscal_year'),'status':m.get('status'),'calculation_performed':m.get('calculation_performed'),'reason':m.get('reason')} for m in o['report'].get('metrics',[])]} for o in [first,repeat,read,current,missing,read_missing]],
 'repeat_case_factory_forbidden':True,'result_files_and_pointers_preserved_on_repeat_and_failure':True,'ledger_unchanged_sha256':hashlib.sha256(ledger_before).hexdigest(),
 'program_tree_copies':list((task/'state').glob('programs/**/*')),'source_tree_copies':list((task/'state').glob('source-inputs/**/*')),
 'calls':{'provider':0,'paid':0,'sec':0},'native_runs':0,'full_five_year_business_accepted':False}
(base/'history-range-validation.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({o['label']:round(o['elapsed_seconds'],6) for o in [first,repeat,read,current,missing,read_missing]}))
