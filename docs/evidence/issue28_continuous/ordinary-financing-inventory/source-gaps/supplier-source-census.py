import sys,pathlib,json,re
sys.path[:0]=['.','scripts']
from vnext.normal_candidates import _prepare_b06
from vnext.normal_source_authority import verify_saved_source_proofs
from vnext.deterministic_router import parse_accession_xbrl_source
from vnext.b06_disclosure import text
from vnext.fiscal_year_labels import _DefinitionBlocks
from tests.vnext.test_normal_zero_ai_results import original_sources_only
out=pathlib.Path('/tmp/sec_metrics_issue28_continuous/supplier-classification-original-census');out.mkdir(exist_ok=False)
for company in ['southwest_airlines','pfizer']:
 with original_sources_only():p=_prepare_b06(repo_root=pathlib.Path.cwd(),company_id=company);a=verify_saved_source_proofs(data_root=pathlib.Path.cwd(),proofs=p['input_binding']['source_proofs'])
 period=p['input_binding']['prepared_annual_input']['table_input']['target_period'];parsed=parse_accession_xbrl_source(raw_bytes=p['xml']['raw_bytes']);notes=[];facts=[]
 for f in parsed.facts:
  c=parsed.contexts[f['context_ref']]
  if c['period_end']!=period['period_end'] or c['dimensions']:continue
  if re.search(r'supplierfinanc|supplychainfinanc',f['qualified_name'],re.I):facts.append({**f,'context':{**c,'dimensions':dict(c['dimensions'])}})
  if 'textblock' in f['qualified_name'].casefold() and re.search('supplier|supply chain',text(f['text']),re.I):
   t=text(f['text']);sentences=[t[max(0,m.start()-500):m.start()+2300] for m in re.finditer(r'supplier financ|supply.chain financ',t,re.I)]
   notes.append({'ordinal':f['ordinal'],'concept':f['qualified_name'],'text':t,'excerpts':sentences})
 print('COMPANY',company,'FACTS',[(f['qualified_name'],f['text']) for f in facts])
 for n in notes:
  print(n['ordinal'],n['concept']);print('\n'.join(n['excerpts']))
 (out/(company+'.json')).write_text(json.dumps({'period':period,'source_references':[p[k]['source_reference'] for k in ['primary','xml']],'source_admission':a,'native_supplier_facts':facts,'notes':notes,'calls':{'provider':0,'paid':0,'sec':0}},ensure_ascii=False,indent=2))
