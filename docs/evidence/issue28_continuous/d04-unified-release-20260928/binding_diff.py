"""Bounded comparison for the exact failed D04 private release input pair."""
import hashlib
import json
from pathlib import Path

REPO = Path('/Users/lyuhongwang/Developer/SEC_metrics')
HERE = REPO / 'docs/evidence/issue28_continuous/d04-unified-release-20260928'
OLD_ROOTS = [
    Path('/private/tmp/issue28-d04-enphase-normal-b868-20260928/metrics/D04/attempts/5a5d4e4b4a39413c80013970c133a467/data'),
    Path('/private/tmp/issue28-d04-paramount-normal-77f-20260928/metrics/D04/attempts/7d63a0495d224de38e03ff0d5058f65b/data'),
]
RELATIVE = Path('requirements/issue_28_v14/baseline_manifest.json')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


old_manifests = [root / RELATIVE for root in OLD_ROOTS]
new_manifest = REPO / RELATIVE
assert all(path.is_file() for path in [*old_manifests, new_manifest])
assert sha(old_manifests[0]) == sha(old_manifests[1])
old = json.loads(old_manifests[0].read_text())
new = json.loads(new_manifest.read_text())


def changed(key):
    before = old[key].get('files', old[key])
    after = new[key].get('files', new[key])
    return [path for path in sorted(set(before) | set(after))
            if before.get(path) != after.get(path)]


result = {
    'record_type': 'ISSUE28_D04_PRIVATE_RELEASE_INSTALLED_BINDING_MISMATCH',
    'tested_head': 'a863f722324d89f4ee23bc9dd284787b6e18789d',
    'old_run_baseline_sha256': sha(old_manifests[0]),
    'second_old_run_baseline_sha256': sha(old_manifests[1]),
    'current_baseline_sha256': sha(new_manifest),
    'parent_declaration_unchanged': old['parent'] == new['parent'],
    'execution_file_bindings_changed': changed('execution_authority'),
    'rule_file_bindings_changed': changed('new_rule_files'),
    'failure_class': 'Run Requirement Snapshot is invalid',
    'failure_detail': 'Continuous successor installed snapshot differs: baseline_manifest.json',
    'old_run_before_after_tree_comparison_performed': False,
    'source_or_business_credit_granted': False,
    'production_authorized': False,
}
(HERE / 'binding-diff.json').write_text(json.dumps(result, ensure_ascii=False,
    indent=2) + '\n')
print(json.dumps(result, ensure_ascii=False), flush=True)
