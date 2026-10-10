"""One real previously blocked D01 consumer; no source/model acquisition."""
import argparse,csv,hashlib,json,subprocess,sys,tempfile,time
from pathlib import Path
parser=argparse.ArgumentParser()
parser.add_argument('--state-root',type=Path,required=True)
parser.add_argument('--output-parent',type=Path,required=True)
parser.add_argument('--reference',type=Path,default=Path(__file__).resolve().parents[1]/'selected-subject/existing-reference.json')
options=parser.parse_args()
state=options.state_root.resolve()
source=json.loads((state/'company-task.json').read_text())['source_root']
base=Path(tempfile.mkdtemp(prefix='d01-paramount-amendment-',dir=options.output_parent))
root=base
ref=json.loads(options.reference.read_text())['reference']
def hashes():
 return {str(p.relative_to(state)):hashlib.sha256(p.read_bytes()).hexdigest() for p in state.rglob('*') if p.is_file()}
source_before={k:hashlib.sha256((Path(source)/k).read_bytes()).hexdigest() for k in ('evidence/requests_log.csv','evidence/requests_log_manifest.json','config/company_registry.csv')}
before=hashes();(root/'before-state.json').write_text(json.dumps({'state_root':str(state),'files':before},indent=2)+'\n')
args=['run','--company','paramount_skydance_paramount_global','--period','fiscal-years','--fiscal-year-start','2025','--fiscal-year-end','2025','--metric','D01','--source-root',source,'--work-dir',str(state),'--output-dir',str(base/'runs')]
def invoke(name,args,forbid=False):
 code='import sys,json\nfrom unittest.mock import patch\nfrom tools.vnext_company import main\n'
 if forbid:
  code+='from vnext import historical_risk_heading_case as case\na=case.prepare_historical_risk_heading_year_case.__code__\ndef guard(frame,event,arg):\n if event=="call" and frame.f_code is a:raise AssertionError("Stable D01 must reuse")\nsys.setprofile(guard)\n'
 code+='with patch("socket.socket.connect",side_effect=AssertionError("No network")):\n raise SystemExit(main(json.loads(sys.argv[1])))'
 start=time.monotonic();p=subprocess.run([sys.executable,'-B','-c',code,json.dumps(args)],capture_output=True,text=True)
 result={'name':name,'seconds':time.monotonic()-start,'exit_code':p.returncode,'arguments':args,'stdout':p.stdout,'stderr':p.stderr}
 (base/(name+'.json')).write_text(json.dumps(result,indent=2)+'\n');print(name,p.returncode,result['seconds'],flush=True)
 assert p.returncode==0 and not p.stderr,result
 return result,json.loads(p.stdout)
first,run=invoke('process-one-previous-amendment-gap',args)
assert len(run['metrics'])==1 and run['metrics'][0]['metric_id']=='D01'
# The original failure checks and immutable task stay; ordinary latest pointers legitimately transition.
kept={k:h for k,h in before.items() if '/checks/' in k or k=='company-task.json'}
assert all((state/k).is_file() and hashlib.sha256((state/k).read_bytes()).hexdigest()==h for k,h in kept.items())
after=hashes();repeat,run=invoke('repeat-forbidden-factory',args,True)
assert run['metrics'][0]['status']=='NO_SOURCE_CONTENT_CHANGE' and not run['metrics'][0]['calculation_performed']
# New check history may append; results, shared inputs and successful result pointer must remain.
protected={k:h for k,h in after.items() if '/results/' in k or '/shared-inputs/' in k or k.endswith('current-result.json') or k.endswith('completed-check.json') or k=='company-task.json'}
assert all(hashes().get(k)==h for k,h in protected.items())
read,view=invoke('independent-read',['results','--company','paramount_skydance_paramount_global','--state-root',str(state),'--output-root',str(base/'read')],True)
assert all(hashes().get(k)==h for k,h in protected.items())
rows=list(csv.DictReader((base/'read/metrics_matrix.csv').open()));row=next(r for r in rows if r['metric_id']=='D01')
assert row['value'].splitlines()==ref['headings_read'] and len(ref['headings_read'])==38
assert row['unit']=='text' and row['period_start']=='2025-01-01' and row['period_end']=='2025-12-31'
assert row['accession']==ref['accession'] and row['cik']=='2041610'
assert all(hashlib.sha256((Path(source)/k).read_bytes()).hexdigest()==h for k,h in source_before.items())
result_root=Path(run['metrics'][0].get('result_root') or run['metrics'][0]['record_root'])
assessment=json.loads((result_root/'input-assessments.json').read_text())
scopes=assessment['assessments']['risk_heading_amendment_checks']
assert len(scopes)==1 and scopes[0]['decision']=='INPUT_PROPERTY_PROVEN' and not scopes[0]['issues']
assert 'D01' in scopes[0]['source_scope']['not_covered_metric_ids']
assert scopes[0]['original']['raw_sha256']=='4cf3d42c0ba1129dadd58d9c1ffdc4f35e2a81cec7bab3763e2a3bbecfea135d'
assert scopes[0]['amendment']['raw_sha256']=='10fcfbc33813d251dcaf024cf7ac96adc2a4971d7cc1424eed25affb470ff7d0'
records=[json.loads(l) for l in (result_root/'records.jsonl').read_text().splitlines()]
refs=[r for r in records if r['record_type']=='SOURCE_REFERENCE']
assert {r['accession'] for r in refs}=={'0002041610-26-000011','0001140361-26-016758'}
evidence=next(r for r in records if r['record_type']=='EVIDENCE_CHECK');assert evidence['status']=='PASS'
maximum=max(len(v) for r in rows for v in r.values())
assert maximum<131072
receipt={'code_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'first':first,'repeat':repeat,'read':read,'state_root':str(state),'output_root':str(base),'row':row,'heading_count':38,'ordered_reference_equal':True,'old_reference_result_id':ref['checked_identity']['bound_from']['result_id'],'old_files':before,'original_failure_checks_preserved':kept,'protected_result_files':protected,'amendment_scope_summary':{k:scopes[0][k] for k in ['scope_id','classification','decision','input_class','issues']},'saved_source_references':refs,'evidence':evidence,'maximum_daily_csv_field_characters':maximum,'new_calls':[0,0,0],'repeat_factory_calls':0}
(root/'actual-company.json').write_text(json.dumps(receipt,indent=2)+'\n')
print('38 original headings match; one explicit amendment assessment and both sources kept; old failure retained',flush=True)
