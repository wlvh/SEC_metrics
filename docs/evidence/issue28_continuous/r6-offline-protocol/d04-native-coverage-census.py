import json,sys
from pathlib import Path
ROOT=Path('/Users/lyuhongwang/Developer/SEC_metrics');sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from vnext.going_concern_source import prepare_ordinary_going_concern_source
from vnext.text_business_candidates import _bound_source
from vnext.normal_annual_input import _registry_rows
from vnext.normal_annual_input_v2 import exact_json_value
from tests.vnext.test_normal_zero_ai_results import original_sources_only
out=Path('/tmp/sec_metrics_issue28_continuous/d04-native-coverage-census');out.mkdir()
rows=[]
with original_sources_only():
 for company in _registry_rows(repo_root=ROOT):
  p=prepare_ordinary_going_concern_source(repo_root=ROOT,company_id=company['company_id'])
  for c in p['components']:
   raw=(ROOT/c['raw_blob']['storage_uri']).read_bytes()
   parsed,metadata,names=_bound_source(raw_bytes=raw,raw_blob=c['raw_blob'],source_reference=c['source_reference'],
     company_id=c['company_id'],cik=c['cik'],filing=c['source_filing'])
   facts=[]
   for f in parsed.facts:
    facts.append(exact_json_value({'ordinal':f['ordinal'],'concept':metadata.facts[f['ordinal']]['concept'],
      'fact':dict(f),'context':dict(parsed.contexts[f['context_ref']])}))
   raw_facts=json.dumps(facts,ensure_ascii=False,separators=(',',':')).encode()
   texts=[f['text'] for f in parsed.facts if 'nonfraction' not in f['tag'].lower()]
   visible='\n'.join(b['text'] for b in c['document']['blocks'])
   nonvisible=[t for t in texts if t and t not in visible]
   row={'company_id':company['company_id'],'accession':c['source_filing']['accessionNumber'],
     'visible_bytes':c['input_coverage']['source_payload_bytes'],'visible_units':len(c['semantic_source_units']),
     'facts':len(facts),'all_native_json_bytes':len(raw_facts),'native_candidate_count':len(c['native_concept_candidates']),
     'nonnumeric_count':len(texts),'nonnumeric_not_exactly_in_visible':len(nonvisible),
     'max_fact_text_bytes':max((len(t.encode()) for t in texts),default=0),
     'nonvisible_text_examples':[t[:400] for t in nonvisible[:3]]}
   rows.append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
(out/'summary.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
