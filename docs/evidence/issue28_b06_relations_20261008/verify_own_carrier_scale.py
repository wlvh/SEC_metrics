"""Change one carrier fact in memory: both sources agree, inclusion conflicts."""
import json,re,sys
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'scripts'))
from vnext.normal_candidates import _prepare_b06
from vnext.ordinary_special_debt_scope import inspect_special_scope,native,POLICY_PATH
from vnext.canonical import sha256_bytes,strict_json_file
scale=sys.argv[2] if len(sys.argv)>2 else '3'
assert scale in ('3','9')
source=Path(sys.argv[1]);p=_prepare_b06(repo_root=source,company_id='ford_motor_company')
a=p['input_binding']['prepared_annual_input']
for kind in ('primary','xml'):
 parsed,meta=native(p[kind],a)
 facts=[f for f in parsed.facts if meta.facts[f['ordinal']]['concept'][1].casefold()=='otherloanspayablecurrent'
        and parsed.contexts[f['context_ref']]['period_start']==parsed.contexts[f['context_ref']]['period_end']==a['table_input']['target_period']['period_end']
        and any('CompanyExcluding' in x for x in parsed.contexts[f['context_ref']]['dimensions'].values())
        and any('NotesPayableOtherPayablesMember' in x for x in parsed.contexts[f['context_ref']]['dimensions'].values())
        and len(parsed.contexts[f['context_ref']]['dimensions']) == 2]
 print(kind, [(f['ordinal'], f['context_ref'], f['text'], dict(parsed.contexts[f['context_ref']]['dimensions'])) for f in facts], file=sys.stderr)
 assert len(facts)==1
 ref=facts[0]['context_ref'];raw=p[kind]['raw_bytes']
 if kind=='primary':
  pattern=rb'(<ix:nonfraction\b(?=[^>]*name="us-gaap:OtherLoansPayableCurrent")(?=[^>]*contextref="'+ref.encode()+rb'")[^>]*scale=")6(")'
  updated,n=re.subn(pattern,lambda m:m[1]+scale.encode()+m[2],raw,flags=re.I)
 else:
  pattern=rb'(<us-gaap:OtherLoansPayableCurrent\b(?=[^>]*contextref="'+ref.encode()+rb'")[^>]*>)(226000000)(</us-gaap:OtherLoansPayableCurrent>)'
  updated,n=re.subn(pattern,lambda m:m[1]+(b'226000' if scale=='3' else b'226000000000')+m[3],raw,flags=re.I)
 assert n==1
 p[kind]=deepcopy(p[kind]);p[kind]['raw_bytes']=updated
 p[kind]['source_reference']['raw_asset_id']='sha256:'+sha256_bytes(content=updated)
result=inspect_special_scope(primary=p['primary'],xml=p['xml'],annual=a,financial_institution=False,
 rules=strict_json_file(path=source/POLICY_PATH),reported_relations=True)
assert result['lease_inclusion']['status']=='UNRESOLVED'
print(json.dumps({'source_structure':'DERIVED_IN_MEMORY_TEST_ONLY','changes_per_original':1,
 'carrier_own_scale':int(scale),'carrier_usd':226000 if scale=='3' else 226000000000,'current_lease_usd':136000000,
 'status':result['lease_inclusion']['status'],'addition':result['lease_inclusion']['additional_debt_amount'],
 'new_calls':[0,0,0]},indent=2))
