"""Bounded six-event instrumentation; no source or execution byte changes."""
import contextlib,functools,importlib,json,os,platform,socket,sys,time
from pathlib import Path
from unittest.mock import patch
runtime=Path(sys.argv[1]);state=Path(sys.argv[2]);kind=sys.argv[3]
sys.path[:0]=[str(runtime),str(runtime/'scripts')]
os.environ['SEC_METRICS_SOURCE_TRUST_ROOT']='/workspace/work/closeout-paramount-trust'
os.environ['PYTHONDONTWRITEBYTECODE']='1'
from vnext.company_worker_guard import install_worker_guards
from vnext.company_source_authority import require_company
company='paramount_skydance_paramount_global';metrics=['C01','E01','E02','E03','E04','E05']
modules={n:importlib.import_module('vnext.'+n) for n in ['company_compute','company_historical_compute','historical_run','historical_results','historical_projection','historical_run_receipts','normal_period_selection','normal_run_v3','company_source_authority','canonical']}
items=[('normal_period_selection','resolve_period_selection','select'),('historical_results','prepare_historical_run_input','prepare'),('historical_run','install_historical_run_inputs','install'),('normal_run_v3','_install_case_inputs','copy_install'),('historical_run','create_historical_run','create'),('historical_projection','render_historical_run','render'),('historical_run_receipts','read_run_receipt','receipt'),('company_source_authority','_validate_admission_bytes','source_validate')]
counts={};stack=[]
for mod,name,label in items:
 original=getattr(modules[mod],name)
 def make(original,label):
  @functools.wraps(original)
  def measured(*args,**kw):
   start=time.monotonic();stack.append({'label':label,'children':0})
   try:return original(*args,**kw)
   finally:
    frame=stack.pop();delta=time.monotonic()-start
    if stack:stack[-1]['children']+=delta
    c=counts.setdefault(label,{'count':0,'inclusive_seconds':0,'exclusive_seconds':0});c['count']+=1;c['inclusive_seconds']+=delta;c['exclusive_seconds']+=delta-frame['children']
    if label in {'install','create','render','receipt'}:print(json.dumps({'phase':label,'metric':kw.get('metric_id') or Path(kw.get('run_dir','unknown')).name,'seconds':delta,'counts':counts}),flush=True)
  return measured
 replacement=make(original,label)
 for module in list(sys.modules.values()):
  if getattr(module,'__name__','').startswith('vnext.'):
   for key,value in list(vars(module).items()):
    if value is original:setattr(module,key,replacement)
old_write=modules['normal_run_v3']._write
@functools.wraps(old_write)
def counted_write(path,content):
 c=counts.setdefault('copy_bytes',{'calls':0,'bytes_requested':0,'new_files':0,'new_bytes':0})
 c['calls']+=1;c['bytes_requested']+=len(content)
 if not Path(path).exists():c['new_files']+=1;c['new_bytes']+=len(content)
 return old_write(path,content)
modules['normal_run_v3']._write=counted_write
old_hash=modules['canonical'].sha256_file
@functools.wraps(old_hash)
def counted_hash(*args,**kw):
 p=Path(kw['path']);c=counts.setdefault('hash_bytes',{'count':0,'bytes':0})
 c['count']+=1;c['bytes']+=p.stat().st_size
 return old_hash(*args,**kw)
for module in list(sys.modules.values()):
 if getattr(module,'__name__','').startswith('vnext.'):
  for key,value in list(vars(module).items()):
   if value is old_hash:setattr(module,key,counted_hash)
start=time.monotonic();print(json.dumps({'kind':kind,'pid':os.getpid(),'uid':os.getuid(),'platform':platform.platform(),'runtime':str(runtime),'source':str(state/'source'),'metrics':metrics,'start':time.time()}),flush=True)
install_worker_guards(runtime)
with patch.object(socket.socket,'connect',side_effect=ValueError('NO_NETWORK')),patch.object(socket,'getaddrinfo',side_effect=ValueError('NO_DNS')):
 if kind=='company':
  result=modules['company_compute'].compute_company(state_root=state,company_id=company,metric_ids=metrics,report_end='2025-12-31')
 else:
  from vnext.historical_run_replay import run_checks_replay_once
  from vnext.historical_derivation_memo import derived_once_per_state
  from vnext.historical_xbrl_parse import xbrl_parsed_once
  with run_checks_replay_once(),derived_once_per_state(),xbrl_parsed_once():
   result=modules['company_historical_compute'].compute_historical(root=state,source=state/'source',company_id=company,metric_ids=metrics,report_end='2025-12-31')
print(json.dumps({'phase':'complete','seconds':time.monotonic()-start,'counts':counts,'result':result}),flush=True)
