"""Continue a saved recorded task through the real CLI; no HTTP substitution.

The RecordedSecHttpClient reads its declared original replies directly. Only
socket/DNS are blocked, and the real case factory is instrumented/then forbidden.
"""
import contextlib,csv,hashlib,io,json,socket,sys,time
from pathlib import Path
from unittest.mock import patch

program,state=map(lambda p:Path(p).resolve(),sys.argv[1:3])
sys.path[:0]=[str(program),str(program/'scripts')]
from tools.vnext_company import main
from vnext import ordinary_saved_result as saved
from vnext.company_result_view import read_company_results
args=['run','--company','marriott_international','--work-dir',str(state/'task'),
      '--output-dir',str(state/'exports'),'--call-context',str(state/'call-context.json'),
      '--metric','B01','--metric','B02','--max-sec-requests','20']
old_versions={}
old_files={}
for pointer in (state/'task/company-state/updates').glob('*/current-result.json'):
    record=json.loads(pointer.read_text());old_versions[record['metric_id']]=record['version']
    for path in (pointer.parent/'results'/record['version']).rglob('*'):
        if path.is_file():old_files[path]=hashlib.sha256(path.read_bytes()).hexdigest()
actual_factory=saved._ordinary_case
calls=[]
def counting(*a,**kw):
    calls.append(kw.get('metric_id'));return actual_factory(*a,**kw)
def run(forbid=False):
    output=io.StringIO();start=time.perf_counter()
    factory=patch.object(saved,'_ordinary_case',side_effect=AssertionError('No repeat calculation')) if forbid else patch.object(saved,'_ordinary_case',side_effect=counting)
    with factory,patch.object(socket.socket,'connect',side_effect=AssertionError('No socket')), \
         patch.object(socket,'getaddrinfo',side_effect=AssertionError('No DNS')),contextlib.redirect_stdout(output):
        code=main(args)
    result=json.loads(output.getvalue());assert code==0,result
    result['test_elapsed_seconds']=time.perf_counter()-start
    return result
first=run();repeat=run(True)
assert len(calls)==2,calls
assert {row['metric_id']:row['status'] for row in first['metrics']}=={'B01':'CANDIDATE_READY','B02':'CANDIDATE_READY'}
assert all(row['status']=='NO_SOURCE_CONTENT_CHANGE' for row in repeat['metrics'])
assert [r['result_root'] for r in first['metrics']]==[r['result_root'] for r in repeat['metrics']]
for row in first['metrics']:
    assert Path(row['result_root']).name!=old_versions[row['metric_id']]
for path,before in old_files.items():assert hashlib.sha256(path.read_bytes()).hexdigest()==before,path
with (Path(first['output_root'])/'metrics_matrix.csv').open() as source:
    rows={r['metric_id']:r for r in csv.DictReader(source)}
assert rows['B01']['value']=='26186000000' and rows['B01']['unit']=='USD'
assert rows['B02']['value']=='0.04326693227091633466135458167' and rows['B02']['unit']=='ratio'
assert all(rows[m]['fiscal_year']=='2025' for m in ('B01','B02'))
start=time.perf_counter()
with patch.object(saved,'_ordinary_case',side_effect=AssertionError('No read calculation')), \
     patch.object(socket.socket,'connect',side_effect=AssertionError('No socket')), \
     patch.object(socket,'getaddrinfo',side_effect=AssertionError('No DNS')):
    cold=read_company_results(state_root=state/'task/company-state',company_id='marriott_international')
report={'first_seconds':first['test_elapsed_seconds'],'repeat_seconds':repeat['test_elapsed_seconds'],
        'independent_read_seconds':time.perf_counter()-start,'real_factory_calls':calls,
        'old_files_unchanged':len(old_files),'repeat_statuses':[r['status'] for r in repeat['metrics']],
        'new_business_calls':{'provider':0,'paid':0,'sec':0},'source_root':first['source_root'],
        'input_role':'unchanged complete stored SEC source and recorded HTTP; no old Result used as answer',
        'current_values':{m:{k:rows[m][k] for k in ['value','unit','fiscal_year','status']} for m in ('B01','B02')}}
(state/'received-current-base-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2));print('PASS_REAL_CLI_OLD_RECORDED_TASK_CONTINUATION')
