"""Isolated process preparation only: no production/source-file modifications."""
from pathlib import Path
from unittest.mock import patch
import hashlib,json,sys
root=Path(__file__).resolve().parents[5]
sys.path.insert(0,str(root));sys.path.insert(0,str(root/'scripts'))
import sec_pipeline as legacy
from vnext import publication
inventory_path=root/'requirements/issue_15_v1/legacy_semantic_producer_inventory.json'
inventory=json.loads(inventory_path.read_text())
semantic=[r for r in inventory['producers'] if r['kind']=='SEMANTIC_PRODUCER']
metrics=set(json.loads((root/'config/source_strategy_registry.json').read_text())['metrics'])
assert len(metrics)==39
names=[r['producer_id'].split('::')[1] for r in semantic]
assert all(r['producer_id'].startswith('scripts/sec_pipeline.py::') for r in semantic)
assert all(callable(getattr(legacy,name)) for name in names)
assert set(m for r in semantic for m in r['covered_metric_ids'])==metrics
pointer=root/'outputs/active_publication.json';before=pointer.read_bytes()
view=publication.PublicationView.open(publication_root=root)
history_before={p:hashlib.sha256(view.read_bytes(relative_path=p)).hexdigest() for p in ('metrics_matrix.csv','metric_evidence.csv')}
old_check=legacy.check_legacy_production_paths_retired()
replacements={name:legacy.retired_legacy_entrypoint(producer=name) for name in names}
blocked=[];writes=[]
# This scope is an offline rehearsal of the existing guard/tombstone mechanism.
# It is not an activation condition and adds no persistence or production grant.
with patch.multiple(legacy,**replacements),patch.object(legacy,'MIGRATED_VNEXT_METRIC_IDS',frozenset(metrics)):
 for name in names:
  try:getattr(legacy,name)()
  except legacy.LegacyPathStillActiveError:blocked.append(name)
  else:raise AssertionError('semantic entry stayed active:'+name)
 for metric in sorted(metrics):
  for operation,call in [('upsert_metric',lambda:legacy.upsert_metric(rows=[],new_row={'metric_id':metric})),('append_evidence',lambda:legacy.append_evidence(rows=[{'metric_id':metric}]))]:
   try:call()
   except legacy.LegacyPathStillActiveError:writes.append({'operation':operation,'metric_id':metric})
   else:raise AssertionError('legacy write not rejected:'+operation+metric)
 current=publication.PublicationView.open(publication_root=root)
 history_after={p:hashlib.sha256(current.read_bytes(relative_path=p)).hexdigest() for p in history_before}
 assert history_after==history_before and pointer.read_bytes()==before
assert pointer.read_bytes()==before
report={'record_type':'LEGACY_EXIT_PREPARATION_ONLY','production_exit_activated':False,
 'scope':'One disposable Python process; original inventory and existing tombstone/metric-write guards, no source edits or active switch',
 'inventory_sha256':hashlib.sha256(inventory_path.read_bytes()).hexdigest(),
 'pipeline_sha256':hashlib.sha256((root/'scripts/sec_pipeline.py').read_bytes()).hexdigest(),
 'semantic_producer_count':len(semantic),'shared_inventory_rows_retained':len(inventory['producers'])-len(semantic),
 'target_metric_ids':sorted(metrics),'original_existing_retirement_check':old_check,
 'prepared_blocked_symbols':blocked,'write_boundary_cases':writes,
 'historical_publication':view.publication_id,'historical_rows_bytes_unchanged':True,
 'source_producer_inventory':semantic,'calls':[0,0,0],
 'remaining':['Full current390 native successor coverage','Independent whole production graph validation with old semantics unavailable','Actual successor publication-bound retirement declaration','Separate production authorization and corresponding deployed entry switch'],
 'not_proven':'This isolated export/write-boundary check is not a complete transitive call-graph proof or formal retirement receipt.'}
Path(__file__).with_name('result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('source_producer_inventory','prepared_blocked_symbols','write_boundary_cases')},ensure_ascii=False,indent=2))
