from pathlib import Path
import sys,json,hashlib
ROOT=Path('/Users/lyuhongwang/Developer/SEC_metrics');sys.path.insert(0,str(ROOT/'scripts'))
from vnext.requirements import load_requirement_snapshot
from vnext.canonical import content_hash,SEMANTIC_VERSIONS
from vnext.requirement_profile_v1 import resolve_decision_chains
parent=load_requirement_snapshot(snapshot_dir=ROOT/'requirements/issue_28_v13');assert parent['requirement_closure_hash']=='sha256:e1ac4b08b4b31aa5d7a411ac76b8d29c33075e82da3fe5f939009566194dc1f4'
R='issue_28_v14';G='PROFILE_DRIVEN_V15';D='S-ISSUE28-CONTINUOUS-CALLS';P='config/issue28_continuous_calls_v1.json';comment_path='docs/evidence/issue28_continuous/resume-2026-09-13/approval-comment.json'
comment=json.loads((ROOT/comment_path).read_text());approval=json.loads(comment['body'])
policy={'schema_version':1,'policy_id':'issue28_continuous_calls_v1','repository':'wlvh/SEC_metrics','requirement_id':R,
 'delegation_url':comment['html_url'],'delegation_body_sha256':hashlib.sha256(comment['body'].encode()).hexdigest(),'delegation_record_path':comment_path,
 'maximum_additional_provider_paid_sec_calls':[240,240,80],'scope':approval['scope'],'budget_root':approval['budget_root'],
 'provider':'deepseek','model':'deepseek-flash','api':'chat_completions','automatic_retry_count':0,
 'repository_monetary_budget_enforcement':'DISABLED','production_authorized':False,'long_running_schedule_authorized':False,
 'b13':approval['b13'],'offline_wiring_receipt_path':'docs/evidence/issue28_continuous/resume-2026-09-13/offline-wiring.json','real_execution_state':'REQUIRES_OFFLINE_WIRING_RECEIPT_AND_BOUND_COUNT_CONTROL',
 'rule_paths':[P,'scripts/vnext/continuous_call_policy.py','scripts/vnext/continuous_call_ledger.py','scripts/vnext/continuous_semantic_calls.py','scripts/vnext/continuous_call_wiring.py','tools/vnext_continuous_semantic.py','scripts/vnext/requirement_profile_v15.py',comment_path,
 'config/provider_model_runtime.json','requirements/issue_15_v1/decision_register.json'],
 'pending_implementation_metric_ids':['B13','D03','D04']}
def dump(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(value if isinstance(value,str) else json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def bind(relative):
 raw=(ROOT/relative).read_bytes();return {'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw)}
dump(ROOT/P,policy)
dest=ROOT/'requirements'/R;dest.mkdir(exist_ok=True)
raw_decisions=json.loads((ROOT/'requirements/issue_15_v1/decision_register.json').read_text())['decisions']
d36,chains=resolve_decision_chains(decisions=[x for x in raw_decisions if x['decision_id']=='D-36']);d36=d36['D-36']
def decision(identity,choice):
 old=parent['effective_decisions'].get(identity)
 return {'decision_id':identity,'status':'APPROVED','choice':choice,'approved_by':'user:conversation:2026-09-13',
 'approved_at_utc':comment['created_at'],'evidence':comment['html_url'],
 'supersedes_decision_id':content_hash(value=old) if old else None}
transport=dict(parent['effective_decisions']['S-PROVIDER-TRANSPORT']['choice']);transport.update(model='deepseek-flash',filing_egress_policy='PUBLIC_SEC_FILING_CONTENT_ONLY')
retry=dict(parent['effective_decisions']['S-TRANSPORT-RETRY']['choice'])
new={'S-PROVIDER-TRANSPORT':decision('S-PROVIDER-TRANSPORT',transport),'S-TRANSPORT-RETRY':decision('S-TRANSPORT-RETRY',retry),
 'D-36':decision('D-36',d36['choice']),D:decision(D,{'kind':'CONTINUOUS_CALL_ALLOWANCE','maximum_additional_provider_paid_sec_calls':[240,240,80],'automatic_retry_count':0,'response_reuse':'NOT_AUTHORIZED','budget_root':policy['budget_root']})}
register={'status':'USER_APPROVED_LIMITED_CALLS_AND_B13','delegation_url':comment['html_url'],'policy':policy,'successor_decisions':new,
 'field_resolutions':{'S-R5-B06-B13-MEANING':{'b13_economic_meaning':{'status':'APPROVED','choice':approval['b13'],'evidence':comment['html_url']}}}}
paths=set(parent['execution_authority']['files'])|set(policy['rule_paths'])|{'scripts/vnext/requirement_profile.py'}
execution={'files':{p:bind(p) for p in sorted(paths)},'semantic_runtime_versions_hash':content_hash(value=SEMANTIC_VERSIONS)}
validator='scripts/vnext/requirement_profile_v15.py'
baseline={'schema_version':1,'record_type':'REQUIREMENT_BASELINE_MANIFEST','requirement_id':R,'requirement_generation':G,'artifact_requirement_generation':'EXPLICIT_REQUIREMENT_V1','contract_revision':'continuous-calls-and-b13-v1',
 'parent':{'requirement_id':'issue_28_v13','requirement_closure_hash':parent['requirement_closure_hash'],'snapshot_files':{p.name:bind(str(p.relative_to(ROOT))) for p in sorted((ROOT/'requirements/issue_28_v13').iterdir())}},
 'repository':{'identity':'wlvh/SEC_metrics'},'validator':{'path':validator,**bind(validator),'dependencies':['scripts/vnext/continuous_call_policy.py','scripts/vnext/requirement_profile_v1.py','scripts/vnext/canonical.py']},
 'new_rule_files':{p:bind(p) for p in policy['rule_paths']},'execution_authority':execution}
dump(dest/'CONTRACT.md', '# Continuous calls and B13 successor\n\nThe final user resume approval binds ten companies and39metrics, limited provider240/paid240/SEC80, official configured deepseek-flash Chat Completions, WB-3 and SecHttpClient. Counts persist across directories/branches/processes/stages; zero automatic retry, no unchanged-request redraw, no old closed quota reuse. HTTP402, UNKNOWN and authenticity failures stop affected calls and retain counts; unknown usage is not zero. Existing per-request resource and context limits remain unchanged. D-36 monetary enforcement remains disabled; account arrangements are external and only existing usage/cost observations are retained.\n\nOnly the B13 economic-meaning field is resolved: Ford/Enphase, comparable same-subject/period/product-or-facility production divided by available capacity; capacity alone and unapproved substitutes cannot produce a ratio. Qualitative and established-absence outcomes remain source-bound; unimplemented logic is not nondisclosure. New B13 Spec and rule implementation must preserve the old Spec/Run/failure bytes.\n\nThis successor owns its policy/configuration and factory identity. It does not use legacy Issue15 effective invocation defaults or closed v8 stage authority. Registered approval plus bound policy and a real offline authority-to-factory-to-request-to-WB3 wiring receipt precede any actual call. No Ready, merge, formal adoption, deployment, active switch or long-term production permission. Core semantics, native integration,390acceptance, update/publication/retirement and module-specific independent review remain required.\n')
dump(dest/'decision_register.json',register)
dump(dest/'invariant_profile.json',{'delegation_provenance_exact':True,'historical_rules_unchanged':True,'automatic_retry_count':0,'repository_monetary_enforcement':'DISABLED','aggregate_counts_cross_all_execution_locations':True,'unknown_usage_is_zero':False,'new_factory_and_execution_binding_required':True,'offline_wiring_before_first_call':True,'b13_field_resolved_only':True,'production_authorized':False})
dump(dest/'transfer_manifest.json',{'parent_requirement_id':'issue_28_v13','parent_requirement_closure_hash':parent['requirement_closure_hash'],'disposition':'CARRY_HISTORY_AND_NON_SUPERSEDED_OBLIGATIONS','superseded_fields':{'ordinary_development_external_call_budget':D,'S-R5-B06-B13-MEANING':['b13_economic_meaning']},'all_other_business_and_production_authority':'UNCHANGED','old_closed_call_allowances':'HISTORICAL_ONLY_NO_CREDIT'})
dump(dest/'baseline_manifest.json',baseline)
r=load_requirement_snapshot(snapshot_dir=dest);print(r['requirement_id'],r['requirement_closure_hash'],len(execution['files']))
