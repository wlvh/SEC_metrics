from pathlib import Path
import json,shutil,tempfile,time,importlib,os
from unittest.mock import patch
from vnext import ordinary_current_update as update
from vnext.canonical import sha256_file
from vnext.ordinary_saved_result import read_saved_result
j=json.load(open('/private/tmp/issue28-peer-na-operation.json'));old=Path(j['state_root'])/'updates/B01/periods/FY2021';c=json.loads((old/'completed-check.json').read_text());saved=read_saved_result(output_root=old/'results'/c['version']);source=Path(saved['manifest']['source_root'])
# Copy just one ordinary state's metadata and result, not the source/runtime.
base=Path(tempfile.mkdtemp(prefix='issue28-proof-batch-update-'));state=base/'state';dst=state/'periods/FY2021';dst.mkdir(parents=True)
for p in old.glob('*.json'):shutil.copyfile(p,dst/p.name)
shutil.copytree(old/'results'/c['version'],dst/'results'/c['version'])
original_files={str(p.relative_to(dst)):sha256_file(path=p) for p in (dst/'results').rglob('*') if p.is_file()}
factory_module=importlib.import_module(c['configuration']['case_producer']['module']);factory=getattr(factory_module,c['configuration']['case_producer']['name'])
processing=tuple(c['configuration'].get('declared_processing_files',{}))
with patch.object(factory_module,'resolve_period_selection',side_effect=AssertionError('No source preparation')),patch.object(update,'save_calculated_case',side_effect=AssertionError('No calculation or new result')):
 start=time.perf_counter();r=update.run_once(state_root=state,source_root=source,company_id='jpmorgan_chase',metric_id='B01',fiscal_year=2021,case_factory=factory,processing_files=processing);elapsed=time.perf_counter()-start
 print('actual_status',r['status'],'reason',r.get('reason'),'elapsed',elapsed)
 assert r['status']=='NO_SOURCE_CONTENT_CHANGE',r
 after={str(p.relative_to(dst)):sha256_file(path=p) for p in (dst/'results').rglob('*') if p.is_file()};assert original_files==after
out={'base_main':'f6ef7886d6630f7675c25cd42e306c373ab05769','program_root':str(Path.cwd()),'product_changes_uncommitted':True,'source_root':str(source),'isolated_state_root':str(state),'peer_state_read_only':str(old),'elapsed_seconds':elapsed,'report':r,'old_result_files':original_files,'unchanged_result_files':True,'original_completion_config_retained':json.loads((dst/'completed-check.json').read_text())==c,'new_calls':[0,0,0]}
Path(os.environ.get('ISSUE28_PROOF_BENCH_OUTPUT','docs/evidence/issue28_source_proof_batch_20261010/actual-update.json')).write_text(json.dumps(out,indent=2)+'\n')
