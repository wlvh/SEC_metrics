from pathlib import Path
import json,hashlib
R=Path('/Users/lyuhongwang/Developer/SEC_metrics');T=Path('/tmp/sec_metrics_issue28_continuous')
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def bind(rel):raw=(R/rel).read_bytes();return {'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw)}
p=R/'config/issue28_normal_results_v2.json';policy=json.loads(p.read_text())
for rel in ['config/b06_special_scope_v1.json','scripts/vnext/ordinary_special_debt_scope.py']:
 if rel not in policy['rule_paths']:policy['rule_paths'].append(rel)
policy['rule_paths'].sort();write(p,policy)
write(R/'requirements/issue_28_v13/decision_register.json',{'status':'USER_DELEGATED_DEVELOPMENT_ONLY','policy':policy})
p=R/'requirements/issue_28_v13/baseline_manifest.json';b=json.loads(p.read_text());b['new_rule_files']={rel:bind(rel) for rel in policy['rule_paths']}
for rel in [*policy['rule_paths'],'scripts/vnext/normal_run_v3.py']:
 b['execution_authority']['files'][rel]=bind(rel)
b['execution_authority']['files']['scripts/vnext/ordinary_storage_identity.py']=bind('scripts/vnext/ordinary_storage_identity.py')
if 'scripts/vnext/normal_source_requirements.py' in b['execution_authority']['files']:
 b['execution_authority']['files']['scripts/vnext/normal_source_requirements.py']=bind('scripts/vnext/normal_source_requirements.py')
for rel in ['scripts/vnext/normal_zero_ai_results.py','scripts/vnext/normal_run_v3.py','scripts/vnext/run_store.py']:
 b['execution_authority']['files'][rel]=bind(rel)
 if rel in b['new_rule_files']:b['new_rule_files'][rel]=bind(rel)
write(p,b)
s=(T/'build_v15_registered_events.py').read_text().replace('ordinary-registered-events/provider-wiring.json','ordinary-registered-event-runs/provider-wiring.json').replace('ordinary-registered-events/sec-wiring.json','ordinary-registered-event-runs/sec-wiring.json')
(T/'build_v15_registered_event_runs.py').write_text(s)
