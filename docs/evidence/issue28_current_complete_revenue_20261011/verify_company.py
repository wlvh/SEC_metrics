import contextlib,csv,io,json,socket,subprocess,sys,time
from decimal import Decimal
from pathlib import Path
import tempfile
from unittest.mock import patch
from tools.vnext_company import main
from vnext.canonical import sha256_file
base=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(tempfile.mkdtemp(prefix='issue28-current-revenue-final-'))
evidence=Path('docs/evidence/issue28_current_complete_revenue_20261011')
def snap(root):return {str(p.relative_to(root)):sha256_file(path=p) for p in root.rglob('*') if p.is_file()}
def read(company,state,target):
 code='import runpy,socket,sys; socket.socket.connect=lambda *a,**k: (_ for _ in ()).throw(AssertionError("No network")); sys.argv='+repr(['tools/vnext_company.py','results','--company',company,'--state-root',str(state),'--output-root',str(target)])+'; runpy.run_path("tools/vnext_company.py",run_name="__main__")'
 before=snap(state);start=time.monotonic();r=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True)
 elapsed=time.monotonic()-start
 assert r.returncode==0,(r.stdout,r.stderr)
 assert before==snap(state),'independent results mutated state'
 return list(csv.DictReader((target/'metrics_matrix.csv').open())),elapsed
records=[]
for company in ('lumen_technologies','macys'):
 source=Path(sys.argv[2]).resolve() if len(sys.argv)>2 else Path('/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs')
 state=base/('fixed-'+company);out=base/('outputs-'+company)
 metrics=['B01','B02','B03'] if company=='lumen_technologies' else ['B01','B02']
 args=['run','--company',company,'--source-root',str(source),'--work-dir',str(state),'--output-dir',str(out)]
 for metric in metrics:args.extend(['--metric',metric])
 stream=io.StringIO();start=time.monotonic()
 with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),contextlib.redirect_stdout(stream):
  first_code=main(args)
 first_rows=list(csv.DictReader(next(out.rglob('metrics_matrix.csv')).open()))
 first={'args':args,'code':first_code,'seconds':time.monotonic()-start,'rows':first_rows,'stdout':stream.getvalue()}
 assert first_code==0,stream.getvalue()
 source=Path(first['args'][first['args'].index('--source-root')+1])
 source_before={p:sha256_file(path=source/p) for p in ('config/company_registry.csv','evidence/requests_log.csv','evidence/requests_log_manifest.json')}
 before=snap(state);results_before={p:h for p,h in before.items() if '/results/' in '/'+p}
 stream=io.StringIO();start=time.monotonic()
 with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')), \
      patch('vnext.ordinary_current_update.save_calculated_case',side_effect=AssertionError('No repeat save/calculate')), \
      patch('vnext.normal_zero_ai_results.calculate_metric',side_effect=AssertionError('No repeat Calculator')), \
      patch('vnext.zero_ai_r2._deterministic_metric_graph',side_effect=AssertionError('No repeat paired graph')), \
      patch('vnext.normal_run_inputs.prepare_ordinary_zero_ai_run_input',side_effect=AssertionError('No repeat prepare')), \
      contextlib.redirect_stdout(stream):code=main(first['args'])
 repeat=time.monotonic()-start;assert code==0,stream.getvalue()
 assert results_before=={p:h for p,h in snap(state).items() if '/results/' in '/'+p}
 rows,reading=read(company,state,base/('read-fixed-'+company));by={r['metric_id']:r for r in rows}
 if company=='lumen_technologies':
  assert Decimal(by['B01']['value'])==Decimal('12402000000')
  assert Decimal(by['B02']['value'])==(Decimal('12402')-Decimal('13108'))/Decimal('13108')
  assert Decimal(by['B03']['value'])==(Decimal('-812')+Decimal('2749'))/Decimal('12402')
  assert all(r['cik']=='18926' and r['period_start']=='2025-01-01' and r['period_end']=='2025-12-31' for r in rows)
 else:
  assert Decimal(by['B02']['value'])==(Decimal('22621')-Decimal('23006'))/Decimal('23006')
  assert by['B01']['result_id']=='sha256:923318dfcf74a09a6f198d2cb13475ff5396793d4f79b7b119d562fd3fc9ee6e'
  assert all(r['period_start']=='2025-02-02' and r['period_end']=='2026-01-31' and r['fiscal_year']=='2025' for r in rows)
 assert all(r['status']=='OK' and r['local_metric_status']=='NO_SOURCE_CONTENT_CHANGE' for r in rows)
 assert list(csv.DictReader((base/('read-fixed-'+company)/'metric_evidence.csv').open()))
 old_state=Path('/private/tmp/issue28-current-revenue-20261011')/('baseline-'+company);bad,old_seconds=read(company,old_state,base/('read-old-'+company))
 for r in bad:
  if company=='macys' and r['metric_id']=='B01':assert r['status']=='OK'
  else:assert r['status']=='WITHHELD_KNOWN_DEFECT' and not r['value'],r
 scopes=[]
 for p in state.rglob('input-assessments.json'):
  s=json.loads(p.read_text());a=s['assessments'];scopes.append({'path':str(p),'assessments':a})
 assert source_before=={p:sha256_file(path=source/p) for p in source_before}
 item={'company':company,'first':first,'repeat_exit':code,'repeat_seconds':repeat,'independent_read_seconds':reading,
       'rows':rows,'old_wrong_read':bad,'old_read_seconds':old_seconds,'result_files_before':results_before,
       'repeat_result_files_unchanged':True,'independent_read_all_state_unchanged':True,
       'source_metadata_unchanged':True,'scopes':scopes,'calls':{'sec':0,'provider':0,'paid':0}}
 records.append(item)
 print(json.dumps({'company':company,'first_seconds':first['seconds'],'repeat_seconds':repeat,'read_seconds':reading,'protected_result_files':len(results_before),'old_wrong_read_hidden':True}),flush=True)
for item in records:
 for row in item['rows']+item['old_wrong_read']+item['first']['rows']:
  if 'context_or_dimension' in row:row['context_or_dimension_sha256']=__import__('hashlib').sha256(row.pop('context_or_dimension').encode()).hexdigest()
 for assessment in item['scopes']:
  for key,value in assessment['assessments'].items():
   scopes=value.values() if key=='paired_revenue_scopes' else [value] if key=='revenue_scope' else []
   for scope in scopes:
    original=scope['annual_input'];scope['annual_input']={k:original[k] for k in ('company_id','entity','filing','table_input')}
    scope.pop('original_reports',None)
    for proof in scope.get('reported_totals',[]):
     context=proof['statement_scope']
     if 'preceding_page_context' in context:context['preceding_page_context_count']=len(context.pop('preceding_page_context'))
    label=scope.get('fiscal_label_resolution')
    if label:scope['fiscal_label_resolution']={k:label[k] for k in ('record_type','original_dei_fiscal_year','selected_fiscal_year')}
(evidence/'company-verification.json').write_text(json.dumps({'code_root':str(Path.cwd()),'source_root':str(source),'tested_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'has_uncommitted_changes':True,'records':records},ensure_ascii=False,indent=2)+'\n')
