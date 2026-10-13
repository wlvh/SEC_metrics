"""Formal current company CLI on a saved original; only network is disabled."""
import argparse, contextlib, csv, hashlib, io, json, runpy, socket, sys, time
from pathlib import Path
from unittest.mock import patch

parser=argparse.ArgumentParser()
parser.add_argument('--mode',choices=('first','repeat','read'),required=True)
parser.add_argument('--source-root',type=Path,required=True)
parser.add_argument('--work-root',type=Path,required=True)
parser.add_argument('--output-root',type=Path,required=True)
parser.add_argument('--reference',type=Path,required=True)
a=parser.parse_args()
program=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(program/'scripts'))
from vnext import current_risk_heading_case as cases
from vnext.canonical import strict_json_file

def hashes():
    return {str(p.relative_to(a.work_root)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in a.work_root.glob('updates/D01/results/**/*') if p.is_file()}

before=hashes();start=time.monotonic();exit_code=0;stream=io.StringIO()
if a.mode=='read':
    sys.argv=['vnext_company.py','results','--company','enphase_energy',
        '--state-root',str(a.work_root),'--output-root',str(a.output_root)]
else:
    sys.argv=['vnext_company.py','run','--company','enphase_energy',
        '--source-root',str(a.source_root),'--work-dir',str(a.work_root),
        '--output-dir',str(a.output_root),'--metric','D01']
with contextlib.ExitStack() as stack:
    stack.enter_context(patch.object(socket.socket,'connect',side_effect=AssertionError('No network')))
    stack.enter_context(patch.object(socket,'getaddrinfo',side_effect=AssertionError('No DNS')))
    if a.mode=='repeat':
        # Keep actual producer identity introspection; its first source input
        # entry now fails if the current factory is entered at all.
        stack.enter_context(patch('vnext.normal_annual_input_v2.prepare_saved_annual_input',side_effect=AssertionError('Current factory entered on unchanged repeat')))
        stack.enter_context(patch('vnext.ordinary_current_update.save_calculated_case',side_effect=AssertionError('No writer/calculation on repeat')))
    if a.mode=='read':
        stack.enter_context(patch.object(cases,'prepare_current_risk_heading_case',side_effect=AssertionError('No preparation on read')))
        stack.enter_context(patch('vnext.ordinary_current_update.run_once',side_effect=AssertionError('No update on read')))
    with contextlib.redirect_stdout(stream):
        try:runpy.run_path(str(program/'tools/vnext_company.py'),run_name='__main__')
        except SystemExit as e:exit_code=e.code or 0
elapsed=time.monotonic()-start
payload=json.loads(stream.getvalue())
report=(strict_json_file(path=a.work_root/'latest-execution.json') if a.mode!='read' else payload)
if a.mode!='read':
    actual_output=Path(report['output_root'])
    assert report['metrics'][0]['status']==('CANDIDATE_READY' if a.mode=='first' else 'NO_SOURCE_CONTENT_CHANGE'),report
else:actual_output=a.output_root
with (actual_output/'metrics_matrix.csv').open() as f:rows=list(csv.DictReader(f))
row=next(r for r in rows if r['metric_id']=='D01')
assert row['period_end']=='2025-12-31' and row['fiscal_year']=='2025' and row['unit']=='text'
# The retained reading is comparison only, first loaded after actual output.
reference=json.loads(a.reference.read_bytes())['years']['2025']['reference']
expected='\n'.join(reference['headings_read'])
assert row['value']==expected and len(reference['headings_read'])==60
with (actual_output/'metric_evidence.csv').open() as f:evidence=list(csv.DictReader(f))
assert evidence and any('0001463101-26-000013' in str(r) for r in evidence)
after=hashes()
if a.mode!='first':assert before==after and len(before) in (6,12),(before,after)
print(json.dumps({'mode':a.mode,'program_root':str(program),'source_root':str(a.source_root),
    'work_root':str(a.work_root),'output_root':str(actual_output),'exit_code':exit_code,'seconds':elapsed,
    'status':report.get('status'),'metric_status':report.get('metrics',[{}])[0].get('status'),
    'result_id':row['result_id'],'heading_count':60,'value_sha256':hashlib.sha256(row['value'].encode()).hexdigest(),
    'period_start':row['period_start'],'period_end':row['period_end'],'fiscal_year':row['fiscal_year'],
    'unit':row['unit'],'cik':row['cik'],'result_files':len(after),'result_files_unchanged':before==after,
    'new_calls':[0,0,0],'actual_reference_first_loaded_after_output':True},ensure_ascii=False,indent=2))
