"""Read-only comparison of actual old finance metadata with current dependencies."""
import hashlib,importlib,inspect,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path[:0]=[str(ROOT/'scripts'),str(ROOT)]
from vnext import ordinary_current_update as update,ordinary_update_compatibility as compat
state=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence/bank-scope-company-aw1qyxi9/state')
source=Path('/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs')
assert state.exists() and source.exists()
records=[]
for path in sorted(state.glob('updates/*/periods/FY2021/completed-check.json')):
 before=path.read_bytes();old=json.loads(before)['configuration'];metric=old['metric_id']
 if metric not in compat.FINANCE_METRICS:continue
 started=time.monotonic();new=update._configuration(source,'jpmorgan_chase',metric)
 new['requested_fiscal_year']=2021
 extra={};missing=[]
 for relative in old.get('declared_processing_files',{}):
  file=ROOT/relative
  if file.is_file():extra[relative]=hashlib.sha256(file.read_bytes()).hexdigest()
  else:missing.append(relative)
 if extra:new['declared_processing_files']=extra
 producer=old['case_producer'];module=importlib.import_module(producer['module'])
 fn=getattr(module,producer['name']);file=Path(inspect.getsourcefile(fn))
 new['case_producer']={'module':fn.__module__,'name':fn.__qualname__,'sha256':hashlib.sha256(file.read_bytes()).hexdigest()}
 differences={}
 for k in old.keys()|new.keys():
  if old.get(k)==new.get(k):continue
  if isinstance(old.get(k),dict) and isinstance(new.get(k),dict):
   a,b=old[k],new[k];differences[k]=[p for p in sorted(a.keys()|b.keys()) if a.get(p)!=b.get(p)]
  else:differences[k]='changed-or-new-field'
 unchanged=before==path.read_bytes()
 records.append({'metric_id':metric,'requested_fiscal_year':2021,'seconds':time.monotonic()-started,
  'compatible':compat.compatible_configuration(old,new),'same_processing':update._same_processing_configuration(old,new),
  'differences':differences,'missing_declared_dependencies':missing,'original_pointer_unchanged':unchanged,
  'original_pointer_sha256':hashlib.sha256(before).hexdigest(),'case_producer_called':False})
 assert unchanged
 print(metric,'compatible',records[-1]['compatible'],'changed fields',list(differences),flush=True)
assert len(records)==6
(Path(__file__).parent/'old-configurations.json').write_text(json.dumps({'code_root':str(ROOT),'old_state_root':str(state),
 'source_root':str(source),'comparison_only':True,'old_state_files_written':False,'new_calls':[0,0,0],
 'records':records},ensure_ascii=False,indent=2)+'\n')
