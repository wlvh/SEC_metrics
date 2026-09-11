from pathlib import Path
import sys,json,copy
R=Path('/Users/lyuhongwang/Developer/SEC_metrics');sys.path.insert(0,str(R/'scripts'))
from vnext import r5_b06_structured as p
from vnext.r5_b06_measurement import measurement_inputs
from vnext.sources import raw_blob_record,source_reference_record,companyfacts_structured_facts
from vnext.specs import compile_spec_file
from vnext.batch_workflow import _registry_rows,repository_company_traits
from vnext.observations import scope_key
spec=compile_spec_file(path=R/p.SPEC_PATH,dependency_specs={});reports=[]
for company in [x for x in _registry_rows(repo_root=R) if x['company_id'] in ['lumen_technologies','southwest_airlines']]:
 s=p.discover(data_root=R,company=company);scope={'entity_scope':'consolidated'};target={'company_id':company['company_id'],'period_start':s['target_period']['period_end'],'period_end':s['target_period']['period_end'],'accession':s['filing']['accessionNumber'],'entity':s['entity'],'scope':scope,'scope_key':scope_key(scope=scope)};sources=[]
 for proof in s['sources']:
  role='accession_xbrl' if proof['document_name'].endswith('_htm.xml') else 'companyfacts' if '/companyfacts/' in proof['source_url'] else None
  if not role:continue
  blob=raw_blob_record(repo_root=R,repo_relative_path=proof['request_repo_relative_path'],media_type='application/xml' if role=='accession_xbrl' else 'application/json');ref=source_reference_record(raw_blob=blob,company_id=company['company_id'],source_url=proof['source_url'],accession=proof['accession'],document_name=proof['document_name'],source_role=role,request_attempt_id=proof['request_attempt_id']);sources.append((role,ref,(R/proof['request_repo_relative_path']).read_bytes()))
 _,xref,xraw=next(x for x in sources if x[0]=='accession_xbrl');_,cfref,cfraw=next(x for x in sources if x[0]=='companyfacts')
 try:m=measurement_inputs(raw=xraw,source=xref,spec=spec,target=target,filed=s['filing']['filingDate'],data_root=R)
 except Exception as e:reports.append({'company':company['company_id'],'error':str(e)});continue
 facts=companyfacts_structured_facts(raw_bytes=cfraw,source_reference=cfref,approved_concepts=p.concepts(spec),allowed_ciks=[s['entity']],include_instant=True);traits=repository_company_traits(repo_root=R,company_id=company['company_id']);r,t,o,a=p.resolve_primary(spec=spec,target=target,traits=traits,facts=facts,measurement=m)
 result={'company':company['company_id'],'real_fact_result':r,'measurement':m,'selection':a}
 if company['company_id']=='lumen_technologies':
  changed=copy.deepcopy(facts)
  for f in changed:
   if f['concept']=='us-gaap:DebtAndCapitalLeaseObligations' and f['accession']==target['accession'] and f['period_end']==target['period_end']:f['value']='18000000000'
  br,bt,bo,ba=p.resolve_primary(spec=spec,target=target,traits=traits,facts=changed,measurement=m)
  result['function_level_conflicting_CF_carrying_case']={'injection':'test-only altered parsed CompanyFacts carrying amount to 18bn; raw files unchanged; same exact real XML measurement; no native acceptance claimed','result':br,'reasons':ba['reasons'],'debt':ba['debt']}
 reports.append(result)
O=Path(__file__).parent;(O/'measurement-code-check.json').write_text(json.dumps(reports,indent=2));print(json.dumps([{'company':r['company'],'error':r.get('error'),'result':r.get('real_fact_result',{}).get('quality'),'counterexample':r.get('function_level_conflicting_CF_carrying_case',{})} for r in reports],indent=2))
