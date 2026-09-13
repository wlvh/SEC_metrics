from pathlib import Path
import json,hashlib
R=Path('/Users/lyuhongwang/Developer/SEC_metrics');p=R/'requirements/issue_28_v13/baseline_manifest.json';b=json.loads(p.read_text())
for rel in ['scripts/vnext/batch_workflow.py','scripts/vnext/ordinary_remaining_cases.py','scripts/vnext/ordinary_storage_identity.py','scripts/vnext/ordinary_source_authority.py','scripts/vnext/ordinary_projection.py','scripts/vnext/normal_numeric_projection.py','scripts/vnext/continuous_sec_acquisition.py','scripts/vnext/continuous_call_ledger.py','scripts/vnext/continuous_call_policy.py']:
 raw=(R/rel).read_bytes();v={'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw)};b['execution_authority']['files'][rel]=v
 if rel in b['new_rule_files']:b['new_rule_files'][rel]=v
p.write_text(json.dumps(b,ensure_ascii=False,indent=2)+'\n')
p=Path('/tmp/sec_metrics_issue28_continuous/build_v15_continuity.py');s=p.read_text()
s=s.replace("'scripts/vnext/capacity_utilization_source.py'","'scripts/vnext/continuous_sec_acquisition.py','tools/vnext_continuous_sec.py','scripts/vnext/normal_source_requirements.py','scripts/vnext/capacity_utilization_source.py'")
s=s.replace("'offline_wiring_receipt_path':'docs/evidence/issue28_continuous/ordinary-continuity-policy/offline-wiring.json'", "'offline_wiring_receipt_path':'docs/evidence/issue28_continuous/ordinary-document-identity/provider-wiring.json','sec_wiring_receipt_path':'docs/evidence/issue28_continuous/ordinary-document-identity/sec-wiring.json'")
p.with_name('build_v15_sec.py').write_text(s)
