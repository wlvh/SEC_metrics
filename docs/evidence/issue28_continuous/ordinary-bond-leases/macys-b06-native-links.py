import sys,json,re
from pathlib import Path
r=Path('/Users/lyuhongwang/Developer/SEC_metrics');sys.path[:0]=[str(r),str(r/'scripts')]
from vnext.normal_candidates import _prepare_b06
from vnext.deterministic_router import parse_accession_xbrl_source
from vnext.financial_structured import _InlineTableIndex,_fact_cells
from vnext.b06_disclosure import label
from vnext.fiscal_year_labels import _DefinitionBlocks
from vnext.normal_annual_input_v2 import exact_json_value
from tests.vnext.test_normal_zero_ai_results import original_sources_only
with original_sources_only():
 p=_prepare_b06(repo_root=r,company_id='macys');prepared=p['input_binding']['prepared_annual_input'];end=prepared['filing']['reportDate'];out={}
 for kind in ['xml','primary']:
  raw=p[kind]['raw_bytes'];parsed=parse_accession_xbrl_source(raw_bytes=raw);facts=[]
  for f in parsed.facts:
   c=parsed.contexts[f['context_ref']]
   if c['period_end']==end and any('ThirtyThree' in str(v) for v in c['dimensions'].values()):
    facts.append({'fact':dict(f),'context':{**c,'dimensions':dict(c['dimensions'])}})
  if kind=='primary':
   index=_InlineTableIndex(raw);index.feed(raw.decode());index.close();cells=_fact_cells(index,parsed,{i['fact']['ordinal'] for i in facts if i['fact']['unit_ref']})
   for i in facts:
    f=i['fact'];i['raw_start_byte']=index.fact_positions[f['ordinal']]
    if f['ordinal'] in cells:
     t,c=cells[f['ordinal']];i['table_cell']={'table_id':t['table_id'],'grid_sha256':t['grid_sha256'],'row_label':label(t['rows'][c['origin_row_index']]),'cell':c}
   b=_DefinitionBlocks(raw.decode());b.feed(raw.decode());b.close();b._flush();out['paragraphs']=[dict(x) for x in b.blocks if '2033' in x['text'] and ('500' in x['text'] or '7.375' in x['text'] or '7.875' in x['text'])]
  out[kind]={'source_reference':p[kind]['source_reference'],'facts':facts}
 out['input_binding']=p['input_binding'];out=exact_json_value(out)
 Path('/tmp/sec_metrics_issue28_continuous/macys-b06-native-links.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
 for kind in ['xml','primary']:
  print(kind)
  for i in out[kind]['facts']:print(i['fact']['qualified_name'],i['fact']['text'],i['context']['period_start'],i.get('table_cell',{}).get('row_label'))
 print('PARAGRAPHS',out['paragraphs'])
