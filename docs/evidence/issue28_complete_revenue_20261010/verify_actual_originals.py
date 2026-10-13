from pathlib import Path
import json,time
from vnext.historical_annual_input import prepare_historical_annual_input
from vnext.normal_period_selection import resolve_period_selection
from vnext.normal_governance_input import _Sources
from vnext.historical_dei import annual_period
from vnext.selected_revenue_scope_v1 import selected_revenue_scope,admit_revenue_facts,verify_revenue_observations
from vnext.sources import companyfacts_structured_facts
from vnext.specs import compile_spec_file
from vnext.calculator import calculate_metric
from vnext.observations import scope_key
from vnext.traits import repository_company_traits
from vnext.xbrl_namespace_policy import YEAR_OR_DATE_RELEASE
from sec_urls import companyfacts_url
from tests.vnext.test_normal_zero_ai_results import original_sources_only
root=Path('/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs')
program=Path.cwd();start=time.monotonic()
with original_sources_only():
 select=resolve_period_selection(repo_root=root,company_id='pfizer',fiscal_year=2023,rules_root=program)
 annual=prepare_historical_annual_input(repo_root=root,company_id='pfizer',period_selection=select,rules_root=program)
 actual=annual.get('original_input',annual)
 reader=_Sources(root,'pfizer',annual['entity']); originals=reader.auditor_filing(annual['filing'])
 primary=next(s for s in originals if s['raw_blob']['media_type']=='text/html');xml=next(s for s in originals if s['raw_blob']['media_type']=='application/xml')
 fs=reader.read(companyfacts_url(cik=int(annual['entity'])),accession=annual['filing']['accessionNumber'],role='companyfacts',media_type='application/json')
 spec=compile_spec_file(path=program/'catalog/metrics/B01_revenue.md',dependency_specs={});concepts=spec['compiled']['inputs']['revenue']['structured_role']['approved_concepts']
 f=companyfacts_structured_facts(raw_bytes=fs['raw_bytes'],source_reference=fs['source_reference'],approved_concepts=concepts,allowed_ciks=[annual['entity']],include_instant=False)
 scope=selected_revenue_scope(primary=primary,xml=xml,annual=actual,approved_concepts=concepts,namespace_policy=YEAR_OR_DATE_RELEASE,annual_period_reader=annual_period)
 eligible=admit_revenue_facts(facts=f,scope=scope)
 period=annual['table_input']['target_period'];business_scope={'entity_scope':'registrant','period_basis':'source_annual_duration'}
 target={'company_id':'pfizer','entity':annual['entity'],'accession':annual['filing']['accessionNumber'],'period_start':period['period_start'],'period_end':period['period_end'],'scope':business_scope,'scope_key':scope_key(scope=business_scope)}
 old=calculate_metric(compiled_spec=spec,target=target,company_traits=repository_company_traits(repo_root=program,company_id='pfizer'),structured_facts=f,verified_observations=[])
 new=calculate_metric(compiled_spec=spec,target=target,company_traits=repository_company_traits(repo_root=program,company_id='pfizer'),structured_facts=eligible,verified_observations=[])
 verify_revenue_observations(observations=new[2],scope=scope)
 assert old[0]['value']=='50914000000',old[0]
 assert new[0]['value']=='58496000000',new[0]
 print('old',old[0]['value'],old[0]['result_id']);print('new',new[0]['value'],new[0]['result_id']);print('elapsed',time.monotonic()-start)
 outcome={'stage':'ACTUAL_ORIGINALS_AND_CALCULATOR_NOT_COMPANY_ENTRY','company':'pfizer','fiscal_year':2023,'program_git_base':'f6ef7886d6630f7675c25cd42e306c373ab05769','program_has_uncommitted_changes':True,'source_root':str(root),'annual_input':annual,'scope':scope,'original_result':old[0],'new_result':new[0],'new_trace':new[1],'new_observations':new[2],'source_proofs':[p['proof'] for p in reader.proofs.values()],'elapsed_seconds':time.monotonic()-start,'calls':{'provider':0,'paid':0,'sec':0}}
 Path('docs/evidence/issue28_complete_revenue_20261010/actual-calculator.json').write_text(json.dumps(outcome,ensure_ascii=False,indent=2)+'\n')
