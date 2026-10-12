"""Fresh public B02 FY2021 only, forbidden repeat and independent saved read."""
import argparse,contextlib,csv,hashlib,io,json,socket,subprocess,sys,time
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from tools.vnext_company import main
from vnext import ordinary_saved_result


def invoke(args):
    start=time.monotonic()
    with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),contextlib.redirect_stdout(io.StringIO()) as out:
        code=main(args)
    return code,json.loads(out.getvalue()),time.monotonic()-start


def tree(root,results_only=False):
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob('*') if p.is_file() and (not results_only or '/results/' in p.relative_to(root).as_posix())}


def verify(source,work,resume=False):
    if not resume:
        work.mkdir(parents=True,exist_ok=False)
    ledger=(source/'evidence/requests_log.csv').read_bytes()
    args=['run','--company','enphase_energy','--metric','B02','--source-root',str(source),
        '--work-dir',str(work/'task'),'--output-dir',str(work/'first'),'--period','fiscal-years',
        '--fiscal-year-start','2021','--fiscal-year-end','2021']
    if resume:
        saved=json.loads((work/'first-execution.json').read_text())
        code,first,elapsed=saved['code'],saved['result'],saved['elapsed_seconds']
    else:
        code,first,elapsed=invoke(args)
        (work/'first-execution.json').write_text(json.dumps({'code':code,'elapsed_seconds':elapsed,'result':first},indent=2)+'\n')
    assert code==0,first
    before=tree(work/'task',True)
    repeated=list(args);repeated[repeated.index('--output-dir')+1]=str(work/'repeat')
    with patch.object(ordinary_saved_result,'_ordinary_case',side_effect=AssertionError('Repeat cannot calculate')):
        code,repeat,repeat_seconds=invoke(repeated)
    assert code==0 and tree(work/'task',True)==before,repeat
    after_repeat=tree(work/'task')
    read_root=work/('read-resume' if resume else 'read')
    start=time.monotonic()
    child=subprocess.run([sys.executable,str(ROOT/'tools/vnext_company.py'),'results',
        '--company','enphase_energy','--state-root',str(work/'task'),'--output-root',str(read_root)],
        capture_output=True,text=True,check=True)
    read_seconds=time.monotonic()-start;read=json.loads(child.stdout)
    with (read_root/'metrics_matrix.csv').open(newline='') as stream:rows=list(csv.DictReader(stream))
    row=next(r for r in rows if r['metric_id']=='B02')
    expected=(Decimal('1382049000')-Decimal('774425000'))/Decimal('774425000')
    assert Decimal(row['value'])==expected,row
    assert row['fiscal_year']=='2021' and row['period_start']=='2021-01-01' and row['period_end']=='2021-12-31',row
    assert tree(work/'task')==after_repeat
    assert (source/'evidence/requests_log.csv').read_bytes()==ledger
    record=Path(row['record_root']);native_records=[json.loads(line) for line in (record/'records.jsonl').read_text().splitlines() if line.strip()]
    result={'program_root':str(ROOT),'source_root':str(source),'work_root':str(work),
        'first':{'elapsed_seconds':elapsed,'status':first['status']},
        'repeat':{'elapsed_seconds':repeat_seconds,'status':repeat['status'],'calculation_forbidden':True,'result_bytes_and_dirs_unchanged':True},
        'independent_read':{'elapsed_seconds':read_seconds,'row':row},
        'records_count':len(native_records),'own_current_revenue':'1382049000','own_prior_revenue':'774425000',
        'new_business_calls':{'provider':0,'paid':0,'sec':0},
        'limits':['Only FY2021 B02 newly processed; other completed years reused without replay.',
                  'Ordinary candidate, not production adoption or five-year independent business acceptance.']}
    (work/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);p.add_argument('--work-root',type=Path,required=True);p.add_argument('--resume',action='store_true');a=p.parse_args()
    print(json.dumps(verify(a.source_root.resolve(),a.work_root.resolve(),a.resume),ensure_ascii=False,indent=2))
