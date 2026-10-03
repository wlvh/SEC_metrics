import json,sys,hashlib
from pathlib import Path
sys.path[:0]=[str(Path.cwd()),str(Path.cwd()/'scripts')]
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.fiscal_year_labels import inspect_saved_fiscal_year_label,inspect_fiscal_year_labels
from vnext.canonical import sha256_file
out=Path('/tmp/sec_metrics_issue28_continuous/fiscal-label-independent-first');out.mkdir(exist_ok=False)
with original_sources_only():
 reports={c:inspect_saved_fiscal_year_label(repo_root=Path.cwd(),company_id=c) for c in ['salesforce','macys']}
 cases=[]
 for company,kind in [('salesforce','quoted_definitions'),('salesforce','exact_unicode'),('macys','foreign_company_definition')]:
  original=reports[company];prepared=original['prepared_input'];raw=Path(prepared['table_input']['source_repo_relative_path']).read_bytes()
  facts=Path(prepared['companyfacts_input']['source_repo_relative_path']).read_bytes()
  for definition in reversed(original['inspection']['source_definitions']):
   start,end=definition['raw_start_byte'],definition['raw_end_byte'];part=raw[start:end]
   if kind=='quoted_definitions':changed=b'<q>'+part+b'</q>'
   elif kind=='exact_unicode':changed=part+';'.encode()
   elif definition['kind']=='EXPLICIT_REFERENCE_YEARS':
    changed=part.replace(b"Macy's, Inc.",b'Another Corporation').replace(b'2025',b'2026',1)
   else:changed=part.replace(b"The Company's fiscal year ends",b"Another Corporation's fiscal year ends")
   if changed==part:raise RuntimeError('Mutation did not match '+kind)
   raw=raw[:start]+changed+raw[end:]
  result=inspect_fiscal_year_labels(primary_bytes=raw,companyfacts_bytes=facts,expected_primary_sha256=hashlib.sha256(raw).hexdigest(),
   expected_companyfacts_sha256=hashlib.sha256(facts).hexdigest(),expected_cik=prepared['entity'],filing=prepared['filing'])
  (out/(kind+'.html')).write_bytes(raw);(out/(kind+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2))
  row={'case':kind,'company':company,'status':result['status'],'proposed':result['new_rule_label_proposal'],
   'source_definitions':len(result['source_definitions']),'unicode_preserved':all(';' in d['text'] for d in result['source_definitions']) if kind=='exact_unicode' else None}
  cases.append(row);print(row,flush=True)
(out/'index.json').write_text(json.dumps({'source_code_sha256':sha256_file(path=Path('scripts/vnext/fiscal_year_labels.py')),'cases':cases,'calls':{'provider':0,'paid':0,'sec':0}},indent=2))
