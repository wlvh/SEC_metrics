"""Full source-only company path; old prototypes are not edited or used as answers."""
import contextlib,csv,io,json,socket,subprocess,sys,tempfile,time
from pathlib import Path
from decimal import Decimal
from unittest.mock import patch
from tools.vnext_company import main
from vnext.canonical import sha256_file

source=Path(sys.argv[1]).resolve()
evidence=Path(__file__).resolve().parent
base=Path(tempfile.mkdtemp(prefix='issue28-lumen-complete-source-'))
state,outputs,reader=(base/p for p in ('state','outputs','reader'))
args=['run','--company','lumen_technologies','--period','fiscal-years',
      '--fiscal-year-start','2022','--fiscal-year-end','2022','--metric','B02',
      '--source-root',str(source),'--work-dir',str(state),'--output-dir',str(outputs)]
def snapshot(root):
    return {str(p.relative_to(root)):sha256_file(path=p) for p in root.rglob('*') if p.is_file()}
source_metadata={p:sha256_file(path=source/p) for p in ('config/company_registry.csv',
    'evidence/requests_log.csv','evidence/requests_log_manifest.json')}
stream=io.StringIO()
with patch.object(socket.socket,'connect',side_effect=AssertionError('No HTTP/provider')):
    started=time.monotonic()
    with contextlib.redirect_stdout(stream):first_exit=main(args)
    first_seconds=time.monotonic()-started
    result_files={p:h for p,h in snapshot(state).items() if '/results/' in '/'+p}
    started=time.monotonic()
    with (patch('vnext.ordinary_current_update.save_calculated_case',side_effect=AssertionError('No repeat write/calculate')),
         patch('vnext.company_fiscal_range.discover_fiscal_range',side_effect=AssertionError('No repeat fiscal discovery')),
         patch('vnext.calculator.calculate_metric',side_effect=AssertionError('No repeat graph')),
         patch('vnext.calculator.calculate_observation_metric',side_effect=AssertionError('No repeat observation')),
         contextlib.redirect_stdout(stream)):repeat_exit=main(args)
    repeat_seconds=time.monotonic()-started
assert result_files=={p:h for p,h in snapshot(state).items() if '/results/' in '/'+p}
assert source_metadata=={p:sha256_file(path=source/p) for p in source_metadata}
before_read=snapshot(state);started=time.monotonic()
read=subprocess.run([sys.executable,'tools/vnext_company.py','results','--company','lumen_technologies',
    '--state-root',str(state),'--output-root',str(reader)],capture_output=True,text=True)
read_seconds=time.monotonic()-started
assert read.returncode==0 and before_read==snapshot(state),read.stderr
rows=list(csv.DictReader((reader/'metrics_matrix.csv').open()));by_metric={r['metric_id']:r for r in rows}
assert len(rows)==1,rows
assert Decimal(by_metric['B02']['value'])==(Decimal('17478')-Decimal('19687'))/Decimal('19687'),rows
assert by_metric['B02']['unit']=='ratio'
assert all(r['cik']=='18926' and r['period_start']=='2022-01-01' and r['period_end']=='2022-12-31'
    and r['local_metric_status']=='NO_SOURCE_CONTENT_CHANGE' for r in rows)
assert first_exit==repeat_exit==0,stream.getvalue()
citations=list(csv.DictReader((reader/'metric_evidence.csv').open()));assert citations
scopes={}
for p in state.rglob('input-assessments.json'):
    s=json.loads(p.read_text());details=s.get('assessments',{}).get('historical_statement',{})
    for role,scope in details.get('paired_revenue_scopes',{}).items():
        scopes[role]={'status':scope['status'],'complete_scope_proven':scope['complete_scope_proven'],
            'scope_id':scope['scope_id'],'filing':scope['annual_input']['filing'],
            'totals':[{'value':x['total']['value'],'concept':x['total']['concept'],
                'context_ref':x['total']['context_ref'],'unit':x['total']['unit'],
                'native_source':x['total']['source_reference'],
                'page_boundary':x['statement_scope'].get('statement_page_boundary'),
                'excluded_context_blocks':len(x['statement_scope'].get('preceding_page_context',[]))}
                for x in scope.get('reported_totals',[])]}
assert set(scopes)=={'current','prior'} and all(s['complete_scope_proven'] for s in scopes.values())
record={'code_root':str(Path.cwd()),'tested_mode':'uncommitted c2f main merge+source/test changes',
    'source_root':str(source),'state_root':str(state),'args':args,
    'first_seconds':first_seconds,'repeat_seconds':repeat_seconds,'read_seconds':read_seconds,
    'first_exit':first_exit,'repeat_exit':repeat_exit,'read_exit':read.returncode,
    'rows':[{k:v for k,v in r.items() if k!='context_or_dimension'} for r in rows],
    'paired_scopes':scopes,'citations':citations,'protected_result_files':result_files,
    'all_state_read_unchanged':True,'source_metadata_unchanged':True,'stdout':stream.getvalue(),
    'calls':{'sec':0,'provider':0,'paid':0}}
(evidence/'actual-company.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:record[k] for k in ('first_seconds','repeat_seconds','read_seconds','first_exit','repeat_exit','read_exit')},indent=2))
