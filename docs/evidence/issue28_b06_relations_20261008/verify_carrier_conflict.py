"""Source-structure counterexample in memory, never acquired input credit."""
import json,re,sys
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'scripts'))
from vnext.normal_candidates import _prepare_b06
from vnext.ordinary_special_debt_scope import native,POLICY_PATH
from vnext.ordinary_reported_lease_scope import inspect_reported_lease_scope
from vnext.canonical import sha256_bytes,strict_json_file
source=Path(sys.argv[1]);p=_prepare_b06(repo_root=source,company_id='ford_motor_company')
a=p['input_binding']['prepared_annual_input']
for kind in ('primary','xml'):
 parsed,meta=native(p[kind],a)
 facts=[f for f in parsed.facts if meta.facts[f['ordinal']]['concept'][1].casefold()=='financeleaseliabilitycurrent'
        and parsed.contexts[f['context_ref']]['period_end']==a['table_input']['target_period']['period_end']
        and any('CompanyExcluding' in x for x in parsed.contexts[f['context_ref']]['dimensions'].values())]
 print(kind, [(f['context_ref'], parsed.contexts[f['context_ref']]['period_start'], parsed.contexts[f['context_ref']]['period_end']) for f in facts], file=sys.stderr)
 assert len(facts)==1
 ref=facts[0]['context_ref'];raw=p[kind]['raw_bytes']
 if kind=='primary':
  pattern=rb'(<ix:nonfraction\b(?=[^>]*name="us-gaap:FinanceLeaseLiabilityCurrent")(?=[^>]*contextref="'+ref.encode()+rb'")[^>]*>)(136)(</ix:nonfraction>)'
  value=b'1000'
 else:
  pattern=rb'(<us-gaap:FinanceLeaseLiabilityCurrent\b(?=[^>]*contextref="'+ref.encode()+rb'")[^>]*>)(136000000)(</us-gaap:FinanceLeaseLiabilityCurrent>)'
  value=b'1000000000'
 updated,n=re.subn(pattern,lambda m:m[1]+value+m[3],raw,flags=re.I)
 assert n==1
 p[kind]=deepcopy(p[kind]);p[kind]['raw_bytes']=updated
 p[kind]['source_reference']['raw_asset_id']='sha256:'+sha256_bytes(content=updated)
result=inspect_reported_lease_scope(primary=p['primary'],xml=p['xml'],annual=a,financial_institution=False,
 rules=strict_json_file(path=source/POLICY_PATH))
assert result['lease_inclusion']['status']=='UNRESOLVED'
print(json.dumps({'source_structure':'DERIVED_IN_MEMORY_TEST_ONLY','changes_per_original':1,
 'current_lease_usd':1000000000,'visible_inclusive_row_usd':226000000,
 'current_parent_usd':5550000000,'status':result['lease_inclusion']['status'],
 'addition':result['lease_inclusion']['additional_debt_amount'],'new_calls':[0,0,0]},indent=2))
