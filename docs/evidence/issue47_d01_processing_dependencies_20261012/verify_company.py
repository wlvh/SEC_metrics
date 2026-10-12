"""One real D01 task plus an explicitly in-memory processing-change control."""
import argparse,csv,hashlib,json,subprocess,sys,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);p.add_argument('--state-root',type=Path,required=True);p.add_argument('--output-root',type=Path,required=True);a=p.parse_args()
source=a.source_root.resolve();state=a.state_root.resolve();out=a.output_root.resolve();out.mkdir(exist_ok=False,parents=True)
def hashes(root):return {str(f.relative_to(root)):hashlib.sha256(f.read_bytes()).hexdigest() for f in root.rglob('*') if f.is_file()}
before=hashes(state);old={n:h for n,h in before.items() if '/results/' in n or '/checks/' in n}
(out/'before-state.json').write_text(json.dumps(before,indent=2)+'\n')
args=['run','--company','enphase_energy','--period','fiscal-years','--fiscal-year-start','2021','--fiscal-year-end','2021','--metric','D01','--source-root',str(source),'--work-dir',str(state),'--output-dir',str(out/'runs')]
def invoke(name,argv,mode):
 code="""import json,sys
from pathlib import Path
from unittest.mock import patch
from tools.vnext_company import main
from vnext import historical_risk_heading_case as c,d01_emphasis_results as d,calculator,ordinary_current_update as u,scope_contract
factory=c.prepare_historical_risk_heading_year_case.__code__
codes={factory,d.create_deterministic_text_candidate.__code__,calculator.calculate_metric.__code__,calculator.calculate_observation_metric.__code__}
scope={v.__code__ for v in vars(scope_contract).values() if callable(v) and hasattr(v,'__code__') and v.__module__==scope_contract.__name__}
entered=False;calls=0;mode=sys.argv[2]
def prof(frame,event,arg):
 global entered,calls
 if event!='call':return
 if frame.f_code==factory:entered=True;calls+=1
 if mode=='forbid' and frame.f_code in codes:raise AssertionError('UNCHANGED_INPUT_MUST_NOT_RECALCULATE')
 if mode=='memory-change' and entered and frame.f_code in scope:raise AssertionError('CONSTRUCTED_CONTROL_D01_USED_SCOPE_FILE_CHANGED')
actual=u.sha256_file
def changed(*,path):
 return 'constructed-used-scope-digest' if Path(path)==u.ROOT/'scripts/vnext/scope_contract.py' else actual(path=path)
sys.setprofile(prof)
with patch('socket.socket.connect',side_effect=AssertionError('NO_NETWORK')):
 if mode=='memory-change':
  with patch.object(u,'sha256_file',side_effect=changed):result=main(json.loads(sys.argv[1]))
 else:result=main(json.loads(sys.argv[1]))
sys.setprofile(None)
print('FACTORY_CALLS='+str(calls),file=sys.stderr)
raise SystemExit(result)
"""
 start=time.perf_counter();proc=subprocess.run([sys.executable,'-B','-c',code,json.dumps(argv),mode],capture_output=True,text=True)
 record={'seconds':time.perf_counter()-start,'exit':proc.returncode,'arguments':argv,'control':mode,'stdout':proc.stdout,'stderr':proc.stderr}
 (out/(name+'.json')).write_text(json.dumps(record,indent=2)+'\n');print(name,round(record['seconds'],3),proc.returncode,flush=True)
 assert proc.returncode in (0,2),record
 return json.loads(proc.stdout),record
first,fr=invoke('configuration-migration',args,'observe');assert first['metrics'][0]['calculation_performed'],first
assert all(hashes(state).get(n)==h for n,h in old.items())
repeat,rr=invoke('unchanged-repeat',args,'forbid');assert not repeat['metrics'][0]['calculation_performed'];assert 'FACTORY_CALLS=0' in rr['stderr']
result_hashes={n:h for n,h in hashes(state).items() if '/results/' in n}
fault,ar=invoke('memory-only-changed-dependency',args,'memory-change')
assert fault['metrics'][0]['status']=='INPUT_OR_EXECUTION_FAILED' and fault['metrics'][0]['reason']=='CONSTRUCTED_CONTROL_D01_USED_SCOPE_FILE_CHANGED',fault
assert 'FACTORY_CALLS=1' in ar['stderr'];assert all(hashes(state).get(n)==h for n,h in result_hashes.items())
restored,sr=invoke('unchanged-after-control',args,'forbid');assert not restored['metrics'][0]['calculation_performed'];assert 'FACTORY_CALLS=0' in sr['stderr']
before_read=hashes(state)
read,dr=invoke('independent-read',['results','--company','enphase_energy','--state-root',str(state),'--output-root',str(out/'read')],'forbid');assert before_read==hashes(state)
rows=list(csv.DictReader((out/'read/metrics_matrix.csv').open(encoding='utf-8-sig')));assert len(rows)==1;row=rows[0]
assert len(row['value'].splitlines())==68 and row['unit']=='text' and row['status']=='TEXT_QUAL'
assert hashlib.sha256(row['value'].encode()).hexdigest()=='8b66471154344b88f8a7e94a0184d90f284e65850c089f0abcbfe8f49909a483'
assert row['result_id']=='sha256:e3dd15bbe689462ab075d5f24ac0d88f03b9037f9cb86f747e40e568ede99b0c'
(out/'summary.json').write_text(json.dumps({'code_head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'phases':{n:{k:r[k] for k in ['seconds','exit','control']} for n,r in [('migration',fr),('repeat',rr),('memory_change',ar),('after_control',sr),('read',dr)]},'old_saved_files_unchanged':len(old),'result_files_protected_in_control':len(result_hashes),'read_state_files_unchanged':len(before_read),'heading_count':68,'value_sha256':hashlib.sha256(row['value'].encode()).hexdigest(),'result_id':row['result_id'],'new_calls':[0,0,0]},indent=2)+'\n')
