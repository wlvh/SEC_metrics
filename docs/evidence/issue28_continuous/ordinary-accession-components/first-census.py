import json,sys
from pathlib import Path
sys.path[:0]=[str(Path.cwd()),str(Path.cwd()/'scripts')]
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.normal_annual_input import prepare_saved_annual_input
from vnext.normal_source_authority import verify_saved_source_proofs
from vnext.deterministic_router import parse_accession_xbrl_source
from vnext.governance_signals import _source_value
from vnext.text_results_v2 import _ReportedFactMetadata,_verified_context
from vnext.canonical import canonical_json_bytes,sha256_bytes
out=Path('/tmp/sec_metrics_issue28_continuous/ordinary-accession-census');out.mkdir(exist_ok=False)
catalog=json.loads(Path('catalog/deterministic_metrics.json').read_text())
with original_sources_only():
 for company,metrics in [('jpmorgan_chase',['A01','A02']),('salesforce',['B12'])]:
  p=prepare_saved_annual_input(repo_root=Path.cwd(),company_id=company)
  verify_saved_source_proofs(data_root=Path.cwd(),proofs=p['source_proofs'])
  raw=Path(p['table_input']['source_repo_relative_path']).read_bytes()
  parsed=parse_accession_xbrl_source(raw_bytes=raw);meta=_ReportedFactMetadata();meta.feed(raw.decode());meta.close()
  rows=[]
  for metric in metrics:
   names={c for b in catalog['metrics'][metric]['branches'] for item in b['components'] for c in item['approved_concepts']}
   for f in parsed.facts:
    m=meta.facts[f['ordinal']]
    if m['concept'][1].casefold() not in {n.casefold() for n in names}:continue
    context=parsed.contexts[f['context_ref']]
    value,proof,error=None,None,None
    try:value=_source_value(f,m);proof=_verified_context(native=context,metadata=meta)
    except Exception as e:error=str(e)
    row={'metric_id':metric,'fact':dict(f),'concept_qname':m['concept'],'context':dict(context),'unit_definition':meta.units.get(f['unit_ref']),
         'value':value,'context_proof':proof,'error':error,'fact_tag_namespace':m['namespaces'].get(m['tag'].split(':')[0])}
    rows.append(row)
  data={'company_id':company,'primary_sha256':sha256_bytes(content=raw),'prepared_input':p,'facts':rows}
  (out/(company+'.json')).write_bytes(canonical_json_bytes(value=data))
  print(company,len(rows),flush=True)
  for r in rows:
   if r['context']['period_end']==p['filing']['reportDate']:
    print(r['metric_id'],r['concept_qname'],r['value'],r['unit_definition'],dict(r['context']['dimensions']),r['error'],flush=True)
