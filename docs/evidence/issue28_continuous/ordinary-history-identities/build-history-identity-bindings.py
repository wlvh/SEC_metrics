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
write(p,b)
s=(T/'build_v15_special_debt.py').read_text().replace('ordinary-special-debt-scope/provider-wiring.json','ordinary-history-identities/provider-wiring.json').replace('ordinary-special-debt-scope/sec-wiring.json','ordinary-history-identities/sec-wiring.json')
(T/'build_v15_history_identity.py').write_text(s)
