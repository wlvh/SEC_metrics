import json,subprocess,os,time,hashlib,csv,io
from pathlib import Path
root=Path.cwd();base=root/'docs/evidence/issue47_history/historical-income-receiving-2026-10-08';python=str(root/'work/issue47-venv/bin/python');source=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-development-evidence/source-only-b01-no-rules-20261007');parent=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence');task=parent/'historical-b03-cli-20261008'
for n in range(100):
 p=task if n==0 else task.with_name(task.name+'-'+str(n))
 if not p.exists():task=p;task.mkdir();break
args=['run','--company','marriott_international','--source-root',str(source),'--work-dir',str(task/'state'),'--output-dir',str(task/'outputs'),'--metric','B03','--period','fiscal-years','--fiscal-year-start','2024','--fiscal-year-end','2025'];operations=[]
def invoke(label,a,forbid=False):
 code='import json,sys;from unittest.mock import patch;from tools.vnext_company import main\nwith patch("socket.socket.connect",side_effect=AssertionError("No business network"))'
 if forbid:code+=',patch("vnext.historical_zero_ai_results.resolve_historical_zero_ai_metric",side_effect=AssertionError("Unchanged inputs must not calculate"))'
 code+=':\n raise SystemExit(main(json.loads(sys.argv[1])))'
 start=time.monotonic();p=subprocess.run([python,'-c',code,json.dumps(a)],capture_output=True,text=True,env={**os.environ,'PYTHONPATH':'scripts:.'},timeout=120)
 (base/(label+'.json')).write_text(p.stdout);(base/(label+'.stderr')).write_text(p.stderr);assert p.returncode==0,(label,p.returncode,p.stderr,p.stdout[:900]);d=json.loads(p.stdout);operations.append({'label':label,'seconds':time.monotonic()-start,'status':d.get('status')});return d
def protect():return {str(p.relative_to(task)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (task/'state').rglob('*') if p.is_file() and ('/results/' in str(p) or p.name in ['current-result.json','completed-check.json'])}
def rows(d):return list(csv.DictReader(io.StringIO((Path(d['output_root'])/'metrics_matrix.csv').read_text(encoding='utf-8-sig'))))
first=invoke('b03-cli-first',args);observed={(r['fiscal_year'],r['value'],r['unit']) for r in rows(first)};assert observed=={('2024','0.1653386454183266932270916335','ratio'),('2025','0.1756281982738868097456656229','ratio')}
before=protect();repeat=invoke('b03-cli-repeat',args,True);assert protect()==before;assert all(m['status']=='NO_SOURCE_CONTENT_CHANGE' and not m['calculation_performed'] for m in repeat['metrics'])
read=invoke('b03-cli-independent-read',['results','--company','marriott_international','--state-root',str(task/'state'),'--output-root',str(task/'daily')],True);assert protect()==before;assert {(r['fiscal_year'],r['value'],r['unit']) for r in rows(read)}==observed
record={'task_root':str(task),'source_root':str(source),'operations':operations,'actual_values':[{'year':y,'value':v,'unit':u} for y,v,u in sorted(observed)],'repeat_and_read_factory_forbidden':True,'protected_file_count':len(before),'protected_bytes_unchanged':True,'source_and_program_tree_copies':0,'calls':{'sec':0,'provider':0,'paid':0},'scope':'unamended continuous registrant B03 saved-source range; not full five-year business','existing_hotel_or_two_year_B01_not_recomputed':True}
(base/'b03-cli-verification.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
