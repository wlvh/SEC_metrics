"""Consume existing Enphase source through explicit capacity successor through the existing company CLI."""
import csv,hashlib,json,subprocess,sys,tempfile,time
from pathlib import Path
state=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence/enphase-statements-company-jvkm2nml/state')
source=json.loads((state/'company-task.json').read_text())['source_root']
base=Path(tempfile.mkdtemp(prefix='enphase_energy-d01-company-',dir='/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence'))
refs=json.loads(Path('work/d01-capacity-consumer/existing-reference.json').read_text())['years']
def protect():
    return {str(p.relative_to(state)):hashlib.sha256(p.read_bytes()).hexdigest() for p in state.rglob('*')
            if p.is_file() and (p.name in {'company-task.json','current-result.json','completed-check.json'}
                               or 'results' in p.parts or 'shared-inputs' in p.parts)}
before=protect()
original_pointers={k:h for k,h in before.items() if 'D01/periods/FY2021/' not in k}
old_checks={str(p.relative_to(state)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (state/'updates/D01/periods/FY2021/checks').rglob('*') if p.is_file()}
args=['run','--company','enphase_energy','--period','fiscal-years','--fiscal-year-start','2021','--fiscal-year-end','2021',
      '--metric','D01','--source-root',source,'--work-dir',str(state),'--output-dir',str(base/'runs')]
def invoke(name,args,forbid=False):
    code='import sys,json\nfrom unittest.mock import patch\nfrom tools.vnext_company import main\n'
    if forbid:
        code+="""from vnext import historical_risk_heading_case as case
a=case.prepare_historical_risk_heading_year_case.__code__
def guard(frame,event,arg):
 if event=='call' and frame.f_code is a:raise AssertionError('Existing D01 source must reuse')
sys.setprofile(guard)
"""
    code+="with patch('socket.socket.connect',side_effect=AssertionError('No new network')):\n raise SystemExit(main(json.loads(sys.argv[1])))"
    start=time.monotonic();p=subprocess.run([sys.executable,'-B','-c',code,json.dumps(args)],capture_output=True,text=True)
    r={'name':name,'seconds':time.monotonic()-start,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'arguments':args}
    (base/(name+'.json')).write_text(json.dumps(r,indent=2)+'\n');print(name,p.returncode,r['seconds'],flush=True)
    assert p.returncode==0 and not p.stderr,r
    return r,json.loads(p.stdout)
first,report=invoke('only-FY2021-capacity-transition',args)
assert len(report['metrics'])==1 and all(m['metric_id']=='D01' for m in report['metrics'])
assert all((state/k).is_file() and hashlib.sha256((state/k).read_bytes()).hexdigest()==h for k,h in original_pointers.items())
assert all((state/k).is_file() and hashlib.sha256((state/k).read_bytes()).hexdigest()==h for k,h in old_checks.items())
result_root=Path(report['metrics'][0]['result_root'])
records=[json.loads(l) for l in (result_root/'records.jsonl').read_text().splitlines()]
result=next(r for r in records if r['record_type']=='METRIC_RESULT')
assert result['text_payload']['renderer']=='ORDERED_NEWLINE_128_V2' and len(result['text_payload']['items'])==68
after=protect();repeat,report=invoke('repeat-forbidden-D01-factory',args,True)
assert all(m['status']=='NO_SOURCE_CONTENT_CHANGE' and not m['calculation_performed'] for m in report['metrics'])
assert after==protect()
read,view=invoke('independent-read',['results','--company','enphase_energy','--state-root',str(state),'--output-root',str(base/'read')],True)
assert after==protect()
rows=list(csv.DictReader((base/'read/metrics_matrix.csv').open()));selected=[r for r in rows if r['metric_id']=='D01']
comparisons=[]
for row in selected:
    year=row['fiscal_year'];old=refs[year]['reference'];texts=row['value'].splitlines()
    comparisons.append({'fiscal_year':int(year),'heading_count':len(texts),'old_heading_count':len(old['headings_read']),
        'ordered_text_equal':texts==old['headings_read'],'new_not_read':[t for t in texts if t not in old['headings_read']],
        'read_not_new':[t for t in old['headings_read'] if t not in texts],
        'unit':row['unit'],'period_start':row['period_start'],'period_end':row['period_end'],'accession':row['accession'],
        'result_id':row['result_id'],'reference_result_id':old['checked_identity']['bound_from']['result_id']})
r={'code_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'first':first,'repeat':repeat,'read':read,
   'state_root':str(state),'source_root':source,'output_root':str(base),'rows':rows,'comparisons':comparisons,
   'old_files':before,'final_files':after,'all_other_results_and_pointers_preserved':True,'original_failed_checks_preserved':old_checks,'new_renderer':result['text_payload']['renderer'],'repeat_factory_calls':0,'new_calls':[0,0,0]}
Path('work/d01-capacity-consumer/actual-company.json').write_text(json.dumps(r,indent=2)+'\n')
assert len(rows)==25 and len(selected)==5
for item in comparisons:
    year=item['fiscal_year'];old=refs[str(year)]['reference']
    assert item['ordered_text_equal'],item
    assert item['unit']=='text' and item['period_end']==f'{year}-12-31' and item['period_start']==f'{year}-01-01'
    assert item['accession']==old['accession']
print('All five original references now match, only FY2021 processed; old protected',len(before),'final',len(after),flush=True)
