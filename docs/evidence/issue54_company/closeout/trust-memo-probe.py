"""Test #47's actual scoped key with #54's external trust dependency."""
import json,os,shutil,sys,tempfile
from pathlib import Path
runtime=Path(sys.argv[1]);source=Path(sys.argv[2]);original=Path(sys.argv[3])
sys.path[:0]=[str(runtime),str(runtime/'scripts')]
from vnext import historical_derivation_memo as memo
from vnext.company_source_authority import require_company
from vnext.company_worker_guard import install_worker_guards
install_worker_guards(runtime)
with tempfile.TemporaryDirectory(dir='/workspace/work',prefix='closeout-trust-memo-') as directory:
 trust=Path(directory)/'trust';shutil.copytree(original,trust)
 for path in [trust,*trust.rglob('*')]:path.chmod(path.stat().st_mode|0o200)
 os.environ['SEC_METRICS_SOURCE_TRUST_ROOT']=str(trust)
 calls=[];report=[]
 def frozen(**kw):
  calls.append(1)
  admission=require_company(source_root=kw['repo_root'],company_id='paramount_skydance_paramount_global')
  return {'checkpoint':admission['checkpoint_id']}
 memo._install_hook()
 wrapped=memo._memo('prepare_historical_run_input',frozen,str(runtime),report)
 first=wrapped(repo_root=source);second=wrapped(repo_root=source)
 assert first==second and len(calls)==1,(calls,report)
 (trust/'scope-marker').write_text('changed trust-tree state')
 assert wrapped(repo_root=source)==first and len(calls)==2
 registered=next(trust.glob('*.json'));record=json.loads(registered.read_text());record['real_sec_credit']=not record['real_sec_credit']
 registered.write_text(json.dumps(record))
 try:wrapped(repo_root=source)
 except ValueError as error:
  refusal=str(error);assert 'NOT_IN_INSTALLED_TRUST' in refusal
 else:raise AssertionError('stale trusted answer')
 assert len(calls)==3
 print(json.dumps({'calls':len(calls),'memo':report,'changed_trust_record_refusal':refusal,'new_business_calls':[0,0,0],'scope':'Real state-key/audit/admission; input derivation is a small validation factory, not metric calculation'},indent=2))
