import json,sys
from pathlib import Path
ROOT=Path('/Users/lyuhongwang/Developer/SEC_metrics');sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from vnext.annual_amendment_scope import prepare_saved_amendment_scopes
from vnext.normal_annual_input_v2 import exact_json_value
from vnext.deterministic_router import parse_accession_xbrl_source
from vnext.text_results_v2 import _ReportedFactMetadata
from vnext.canonical import sha256_file
from tests.vnext.test_normal_zero_ai_results import original_sources_only
with original_sources_only():
 packet=prepare_saved_amendment_scopes(repo_root=ROOT,company_id='paramount_skydance_paramount_global')
 prepared=packet['prepared_input'];raw=(ROOT/prepared['table_input']['source_repo_relative_path']).read_bytes()
 cf=json.loads((ROOT/prepared['companyfacts_input']['source_repo_relative_path']).read_text())
 parsed=parse_accession_xbrl_source(raw_bytes=raw);meta=_ReportedFactMetadata();meta.feed(raw.decode('utf-8-sig'));meta.close()
 concepts={'AssetsCurrent','LiabilitiesCurrent','CashAndCashEquivalentsAtCarryingValue'}
 facts=[]
 for f in parsed.facts:
  name=meta.facts[f['ordinal']]['concept'];ctx=parsed.contexts[f['context_ref']]
  if name[1] in concepts and ctx['period_end']=='2025-12-31':
   facts.append({'namespace':name[0],'name':name[1],'fact':dict(f),'context':dict(ctx)})
 amounts={name:[f for f in cf['facts']['us-gaap'][name]['units']['USD'] if f['accn']==prepared['filing']['accessionNumber'] and f['end']=='2025-12-31'] for name in concepts}
 catalog=json.loads((ROOT/'catalog/deterministic_metrics.json').read_text())
 scopes=[]
 for s in packet['scopes']:
  scopes.append({k:s[k] for k in ('scope_id','classification','explanatory_note','unchanged_input_classes','original_statement_admission_requires_further_review')})
  scopes[-1]['financial_declarations']=s['details'].get('no_new_financial_statement_declarations')
  scopes[-1]['parts']=s['details'].get('parts');scopes[-1]['items']=s['details'].get('items')
 result=exact_json_value({'purpose':'READ_ONLY_SOURCE_CENSUS_NOT_METRIC_ADMISSION','source_proofs':packet['source_proofs'],
  'catalog':{m:catalog['metrics'][m] for m in ['B08','B09']},'filing':prepared['filing'],'subject_policy':prepared['subject_policy'],
  'native_current_facts':facts,'companyfacts_current':amounts,'amendment_scopes':scopes,
  'calls':{'provider':0,'paid':0,'sec':0},'production_authorized':False,
  'inspected_code_sha256':{p:sha256_file(path=ROOT/p) for p in ['scripts/vnext/normal_companyfacts_results.py','scripts/vnext/annual_amendment_scope.py']}})
p=Path('/tmp/sec_metrics_issue28_continuous/paramount-instant-scope-census.json');p.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['filing','subject_policy','native_current_facts','companyfacts_current','amendment_scopes']},ensure_ascii=False,indent=2))
