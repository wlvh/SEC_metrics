"""Affected D01 originals through the existing company CLI, no source acquisition."""
import argparse,csv,hashlib,json,subprocess,sys,time
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--source-root',type=Path,required=True)
p.add_argument('--output-root',type=Path,required=True)
p.add_argument('--company',action='append',required=True)
p.add_argument('--fiscal-year',type=int,default=2021)
a=p.parse_args();base=a.output_root.resolve();base.mkdir(parents=True,exist_ok=False)
code='''import sys,json
from unittest.mock import patch
from tools.vnext_company import main
from vnext import historical_risk_heading_case as h,d01_emphasis_results as d,calculator
blocked={h.prepare_historical_risk_heading_year_case.__code__,d.create_deterministic_text_candidate.__code__,calculator.calculate_text_metric.__code__}
def guard(f,e,a):
 if e=='call' and f.f_code in blocked:raise AssertionError('NO_RECALCULATION')
if sys.argv[2]=='1':sys.setprofile(guard)
with patch('socket.socket.connect',side_effect=AssertionError('NO_NETWORK')):raise SystemExit(main(json.loads(sys.argv[1])))
'''
watch=['config/company_registry.csv','evidence/requests_log.csv','evidence/requests_log_manifest.json']
source_before={x:hashlib.sha256((a.source_root/x).read_bytes()).hexdigest() for x in watch}
cases=[]
for company in a.company:
    folder=base/company;folder.mkdir();state=folder/'state';phases={}
    def hashes():
        return {str(f.relative_to(state)):hashlib.sha256(f.read_bytes()).hexdigest()
                for f in state.rglob('*') if f.is_file()}
    args=['run','--company',company,'--period','fiscal-years',
          '--fiscal-year-start',str(a.fiscal_year),'--fiscal-year-end',str(a.fiscal_year),
          '--metric','D01','--source-root',str(a.source_root.resolve()),
          '--work-dir',str(state),'--output-dir',str(folder/'runs')]
    for name,command,forbid in [('first',args,False),('repeat',args,True),
        ('read',['results','--company',company,'--state-root',str(state),
                 '--output-root',str(folder/'read')],True)]:
        before=hashes();start=time.perf_counter()
        r=subprocess.run([sys.executable,'-B','-c',code,json.dumps(command),str(int(forbid))],
                         capture_output=True,text=True)
        record={'seconds':time.perf_counter()-start,'exit':r.returncode,
                'arguments':command,'stdout':r.stdout,'stderr':r.stderr}
        (folder/(name+'.json')).write_text(json.dumps(record,indent=2)+'\n')
        assert r.returncode==0 and not r.stderr,record
        result=json.loads(r.stdout)
        if name=='repeat':
            assert all(not m['calculation_performed'] and not m['new_candidate_created']
                       for m in result['metrics'])
            assert {x:h for x,h in before.items() if '/results/' in x}=={
                x:h for x,h in hashes().items() if '/results/' in x}
        if name=='read':assert before==hashes()
        phases[name]={k:record[k] for k in ['seconds','exit','arguments']}
    rows=list(csv.DictReader((folder/'read/metrics_matrix.csv').open()))
    assert len(rows)==1 and rows[0]['status']=='TEXT_QUAL' and rows[0]['value']
    cases.append({'company':company,'fy':a.fiscal_year,'phases':phases,'row':rows[0],
                  'heading_count':len(rows[0]['value'].splitlines()),
                  'read_state_files':len(before)})
    (base/'summary.json').write_text(json.dumps({'cases':cases,'new_calls':[0,0,0]},indent=2)+'\n')
assert source_before=={x:hashlib.sha256((a.source_root/x).read_bytes()).hexdigest() for x in watch}
