import sys,pathlib,json,re
sys.path[:0]=['.','scripts']
from vnext.normal_annual_input_v2 import prepare_saved_annual_input
from vnext.normal_source_authority import verify_saved_source_proofs
from vnext.table_grid import build_table_grid
from vnext.canonical import sha256_bytes
from tests.vnext.test_normal_zero_ai_results import original_sources_only
root=pathlib.Path.cwd();out=pathlib.Path('/tmp/sec_metrics_issue28_continuous/lodging-original-grid-census');out.mkdir(exist_ok=False)
with original_sources_only():p=prepare_saved_annual_input(repo_root=root,company_id='marriott_international');a=verify_saved_source_proofs(data_root=root,proofs=p['source_proofs'])
raw=(root/p['table_input']['source_repo_relative_path']).read_bytes();asset=build_table_grid(html_bytes=raw,parent_raw_asset_ids=['sha256:'+sha256_bytes(content=raw)],storage_uri='research/lodging-grid.json');print('PERIOD',p['table_input']['target_period'],'TABLES',len(asset['tables']))
for t in asset['tables']:
 cs=[c for r in t['rows'] for c in r['cells'] if c['is_origin'] and c['text']]
 if any('Comparable Systemwide Properties' in c['text'] for c in cs):
  print('TABLE',t['table_id'],t['row_count'],t['column_count'],'CAPTION',t['caption_raw_text'])
  for r in t['rows']:
   print(r['row_index'],[(c['column_index'],c['colspan'],c['rowspan'],repr(c['raw_text']),c['text']) for c in r['cells'] if c['is_origin'] and c['text']])
  (out/(t['table_id']+'.json')).write_text(json.dumps(t,ensure_ascii=False,indent=2))
(out/'index.json').write_text(json.dumps({'prepared_input':p,'source_admission':a,'asset_id':asset['derived_asset_id'],'table_count':len(asset['tables']),'calls':{'provider':0,'paid':0,'sec':0}},ensure_ascii=False,indent=2))
