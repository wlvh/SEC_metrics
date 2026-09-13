import pathlib,sys,json,shutil,traceback
sys.path[:0]=['.','scripts']
from vnext.run_store import _mechanically_replay_open_run
from vnext.canonical import content_hash
from tests.vnext.test_normal_zero_ai_results import original_sources_only
base=pathlib.Path('/tmp/sec_metrics_issue28_continuous/v14-southwest-amendment-repair')
data=base/'data/southwest_airlines';run=base/'runs/southwest_airlines/B03'
out=pathlib.Path('/tmp/sec_metrics_issue28_continuous/v14-amendment-source-binding-probe');out.mkdir(exist_ok=False)
with original_sources_only():m,records,reviews=_mechanically_replay_open_run(run_dir=run,repo_root=data,require_complete_results=True)
print('BASELINE_SOURCE_BOUND_B03_PASS',m['run_id'])
key=m['run_id'].rsplit(':',1)[-1];binding=json.loads((data/'ordinary_integrated_bindings'/(key+'.json')).read_text());packet=binding['input_binding']['component']['input_binding']['amendment_input'];accession=packet['scopes'][0]['amendment']['filing']['accessionNumber']
changed=out/'without-amendment-source';shutil.copytree(run,changed)
references=m['source_references'];m={**m,'source_references':[r for r in references if r['accession']!=accession]};assert len(m['source_references'])<len(references)
(changed/'manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2))
try:
 with original_sources_only():_mechanically_replay_open_run(run_dir=changed,repo_root=data,require_complete_results=True)
 raise AssertionError('Native B03 accepted without its required amendment source')
except ValueError as error:
 print('REJECTED_WITHOUT_AMENDMENT_SOURCE',type(error).__name__,str(error));(out/'rejection.log').write_text(traceback.format_exc())
 (out/'index.json').write_text(json.dumps({'baseline_run_id':m['run_id'],'removed_accession':accession,'expected':'REJECT','actual_error':str(error),'error_type':type(error).__name__,'calls':{'provider':0,'paid':0,'sec':0},'data_root_changed':False},indent=2))
