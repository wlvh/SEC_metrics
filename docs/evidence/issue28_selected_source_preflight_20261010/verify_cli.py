"""Actual public readonly CLI over saved sources; no financial/HTTP substitutes."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

parser=argparse.ArgumentParser();parser.add_argument('--program',type=Path,required=True)
parser.add_argument('--source',type=Path,required=True);parser.add_argument('--company',required=True)
parser.add_argument('--report-end',required=True);parser.add_argument('--record',type=Path,required=True)
args=parser.parse_args();program=args.program.resolve();source=args.source.resolve()
sys.path[:0]=[str(program),str(program/'scripts')]
from vnext.selected_source_requirements import discover_selected_annual_requirements
plan=discover_selected_annual_requirements(repo_root=source,company_id=args.company,
    report_end=args.report_end,metric_ids=['B01','B02'])
paths={'config/company_registry.csv','evidence/requests_log.csv','evidence/requests_log_manifest.json'}
for item in plan['requirements']:
    proof=item.get('proof')
    if proof:paths.update(proof[k] for k in ('request_repo_relative_path','request_headers_repo_relative_path'))
def state():return {p:hashlib.sha256((source/p).read_bytes()).hexdigest() for p in sorted(paths)}
before=state()
prelude="""import sys,socket,urllib.request,runpy
sys.path[:0]=[sys.argv.pop(1),sys.argv.pop(1)]
def forbidden(*args,**kwargs):raise AssertionError('No request/calculation/full annual preparation in source preflight')
socket.socket.connect=forbidden
urllib.request.urlopen=forbidden
import sec_http
sec_http.SecHttpClient.fetch=forbidden
from vnext import calculator,historical_annual_input,normal_annual_input_v2
calculator.calculate_metric=forbidden
historical_annual_input.prepare_historical_annual_input=forbidden
normal_annual_input_v2.prepare_saved_annual_input=forbidden
entry=sys.argv.pop(1);sys.argv[0]=entry
runpy.run_path(entry,run_name='__main__')
"""
command=[sys.executable,'-B','-c',prelude,str(program),str(program/'scripts'),str(program/'tools/vnext_company.py'),
    'sources','--company',args.company,'--source-root',str(source),'--report-end',args.report_end,
    '--metric','B01','--metric','B02']
runs=[]
for _ in range(2):
    start=time.monotonic();result=subprocess.run(command,cwd=program,capture_output=True,text=True)
    elapsed=time.monotonic()-start
    if result.stderr:raise AssertionError(result.stderr)
    value=json.loads(result.stdout)
    assert result.returncode==(0 if value['status']=='SAVED_SOURCE_BYTES_AVAILABLE' else 2)
    assert value['calls']=={'provider':0,'paid':0,'sec':0}
    assert not value['metric_executed'] and not value['metric_acceptance_proven']
    assert before==state()
    runs.append({'exit_code':result.returncode,'wall_seconds':elapsed,'report':value})
assert runs[0]['report']['requirements_id']==runs[1]['report']['requirements_id']
record={'program_root':str(program),'source_root':str(source),'company_id':args.company,
    'report_end':args.report_end,'guarded_http_calculator_full_preparation':True,
    'protected_source_files':before,'all_protected_source_files_unchanged':True,'runs':runs,
    'not_financial_calculation_or_business_acceptance':True}
args.record.write_text(json.dumps(record,indent=2)+'\n')
print(args.company,[(r['exit_code'],round(r['wall_seconds'],6),r['report']['unique_known_get_count'],r['report']['original_annual_period']) for r in runs])
