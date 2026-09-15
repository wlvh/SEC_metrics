import sys,json,re
from pathlib import Path
ROOT=Path('/Users/lyuhongwang/Developer/SEC_metrics');sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from vnext.normal_candidates import _prepare_b06
from vnext.normal_annual_input_v2 import exact_json_value
from vnext.normal_source_authority import verify_saved_source_proofs
from vnext.deterministic_router import parse_accession_xbrl_source
from vnext.b06_disclosure import text,tables,label
from tests.vnext.test_normal_zero_ai_results import original_sources_only
out=Path('/tmp/sec_metrics_issue28_continuous/b06-embedded-note-census-v2');out.mkdir()
with original_sources_only():
 for company in ['macys','paramount_skydance_paramount_global','enphase_energy']:
  p=_prepare_b06(repo_root=ROOT,company_id=company);prepared=p['input_binding']['prepared_annual_input'];end=prepared['table_input']['target_period']['period_end']
  verify_saved_source_proofs(data_root=ROOT,proofs=p['input_binding']['source_proofs'])
  parsed=parse_accession_xbrl_source(raw_bytes=p['xml']['raw_bytes']);notes=[];facts=[]
  for f in parsed.facts:
   c=parsed.contexts[f['context_ref']]
   if c['period_end']!=end or c['dimensions'] or c['typed_dimension_count']:continue
   name=f['qualified_name']
   if re.search('debt|borrow|lease|credit|convertible',name,re.I):
    if 'textblock' in name.casefold():
     ts=tables(f['text']);notes.append({'name':name,'ordinal':f['ordinal'],'context':dict(c),'text':text(f['text']),
       'tables':[{'table_id':t['table_id'],'rows':[[cell['text'] for cell in row['cells'] if cell['is_origin']] for row in t['rows']]} for t in ts]})
    elif c['period_start']==c['period_end']:facts.append({'name':name,'value':f['text'],'unit':f['unit_ref']})
  report={'company_id':company,'prepared_input':prepared,'notes':notes,'instant_facts':facts,'source_proofs':p['input_binding']['source_proofs']}
  (out/(company+'.json')).write_text(json.dumps(exact_json_value(report),ensure_ascii=False,indent=2)+'\n')
  print(company,end,'NOTES',[(n['name'],len(n['tables'])) for n in notes],flush=True)
  print('INSTANT',facts,flush=True)
