import sys,pathlib,json,re
sys.path[:0]=['.','scripts']
from vnext.normal_candidates import _prepare_b06
from vnext.normal_source_authority import verify_saved_source_proofs
from vnext.deterministic_router import parse_accession_xbrl_source
from vnext.b06_disclosure import text
from vnext.fiscal_year_labels import _DefinitionBlocks
from tests.vnext.test_normal_zero_ai_results import original_sources_only
root=pathlib.Path.cwd();out=pathlib.Path('/tmp/sec_metrics_issue28_continuous/pfizer-finance-lease-census');out.mkdir(exist_ok=False)
with original_sources_only():p=_prepare_b06(repo_root=root,company_id='pfizer');a=verify_saved_source_proofs(data_root=root,proofs=p['input_binding']['source_proofs'])
rows={}
for kind in ['primary','xml']:
 raw=p[kind]['raw_bytes'];parsed=parse_accession_xbrl_source(raw_bytes=raw);facts=[]
 for f in parsed.facts:
  if re.search(r'financelease|capitallease|financinglease',f['qualified_name'],re.I):
   c=parsed.contexts[f['context_ref']];facts.append({**f,'context':{**c,'dimensions':dict(c['dimensions'])}})
 rows[kind]=facts;print(kind,'FINANCE_LEASE_FACTS',len(facts))
 for f in facts:print(f['qualified_name'],f['text'],f['context'])
s=p['primary']['raw_bytes'].decode('utf-8-sig');parser=_DefinitionBlocks(s);parser.feed(s);parser.close();parser._flush()
clauses=[{'index':i,**b} for i,b in enumerate(parser.blocks) if re.search(r'financ(?:e|ing) leases?|capital leases?',b['text'],re.I)]
print('FULL_PRIMARY_MATCHING_BLOCKS',len(clauses))
for b in clauses:print(b['index'],b['text'][:2200])
(out/'index.json').write_text(json.dumps({'source_references':[p[k]['source_reference'] for k in ['primary','xml']],'source_admission':a,'native_fact_census':rows,'matching_primary_blocks':clauses,'limitation':'No missing value is inferred as zero; this is a bounded source census, not a complete B06.','calls':{'provider':0,'paid':0,'sec':0}},ensure_ascii=False,indent=2))
