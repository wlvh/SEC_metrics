from pathlib import Path
import json,hashlib
R=Path('/Users/lyuhongwang/Developer/SEC_metrics');P=R/'requirements/issue_28_v13/baseline_manifest.json';d=json.loads(P.read_text())
relative='scripts/vnext/normal_companyfacts_results.py';raw=(R/relative).read_bytes();binding={'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw)}
assert relative in d['new_rule_files'] and relative in d['execution_authority']['files']
d['new_rule_files'][relative]=binding;d['execution_authority']['files'][relative]=binding
P.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
p=Path('/tmp/sec_metrics_issue28_continuous/build_v15_after_runtime_binding_repair.py');s=p.read_text().replace('runtime-binding-repair-780d9ba/offline-wiring.json','ordinary-continuity-policy/offline-wiring.json');p.with_name('build_v15_continuity.py').write_text(s)
