"""Two real formal routes on an explicitly combined, isolated program tree."""
import csv,hashlib,io,json,socket,subprocess,sys,tempfile,time
from pathlib import Path
from unittest.mock import patch
E=Path(__file__).parent;ROOT=Path(sys.argv[1]).resolve()
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from tools.vnext_company import main
from vnext import ordinary_current_update as update
SOURCE=Path(json.loads((E/'actual-company.json').read_text())['source_root'])
def snapshot(root):
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}
rows=[]
for company,metric,value in [('jpmorgan_chase','A13','42758000000'),('marriott_international','C04','0')]:
    base=Path(tempfile.mkdtemp(prefix='issue28-union-'+metric+'-'))
    args=['run','--company',company,'--source-root',str(SOURCE),'--metric',metric,
          '--work-dir',str(base/'state'),'--output-dir',str(base/'out')]
    out=io.StringIO();start=time.perf_counter()
    with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),patch('sys.stdout',out):code=main(args)
    first=json.loads(out.getvalue());first_seconds=time.perf_counter()-start
    assert code==0 and first['metrics'][0]['status']=='CANDIDATE_READY',first
    record=Path(first['metrics'][0]['result_root']);record_before=snapshot(record)
    out=io.StringIO();start=time.perf_counter()
    with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),patch.object(update,'create_saved_result',side_effect=AssertionError('No repeated union calculation')),patch.object(update,'save_calculated_case',side_effect=AssertionError('No repeated union write')),patch('sys.stdout',out):code=main(args)
    repeat=json.loads(out.getvalue());repeat_seconds=time.perf_counter()-start
    assert code==0 and repeat['metrics'][0]['status']=='NO_SOURCE_CONTENT_CHANGE'
    assert repeat['metrics'][0]['result_id']==first['metrics'][0]['result_id']
    assert record_before==snapshot(record)
    command='import runpy,socket,sys;socket.socket.connect=lambda *a,**k: (_ for _ in ()).throw(AssertionError("No network"));sys.argv='+repr(['tools/vnext_company.py','results','--company',company,'--state-root',str(base/'state'),'--output-root',str(base/'read')])+';runpy.run_path("tools/vnext_company.py",run_name="__main__")'
    state_before=snapshot(base/'state');start=time.perf_counter();read=subprocess.run([sys.executable,'-c',command],cwd=ROOT,capture_output=True,text=True);read_seconds=time.perf_counter()-start
    assert read.returncode==0,read.stderr
    row=list(csv.DictReader((base/'read/metrics_matrix.csv').open()))[0]
    assert row['value']==value and row['fiscal_year']=='2025',row
    assert row['period_start']=='2025-01-01' and row['period_end']=='2025-12-31',row
    assert snapshot(base/'state')==state_before
    rows.append({'company':company,'metric':metric,'value':row['value'],'unit':row['unit'],
        'result_id':first['metrics'][0]['result_id'],'record_root':first['metrics'][0]['result_root'],
        'first_seconds':first_seconds,'repeat_seconds':repeat_seconds,'read_seconds':read_seconds})
    print(company,metric,value,round(first_seconds,3),round(repeat_seconds,3),round(read_seconds,3),flush=True)
tree=subprocess.check_output(['git','write-tree'],cwd=ROOT,text=True).strip()
(E/'union-company.json').write_text(json.dumps({'program_root':str(ROOT),'source_root':str(SOURCE),
    'combined_index_tree':tree,'rows':rows,'new_calls':[0,0,0],
    'scope':'Explicit isolated175+174 union, not execution of either published head or author merge'},indent=2)+'\n')
print('PASS_REAL_A13_C04_UNION',tree,flush=True)
