"""Refresh only current unfrozen V13/V14 bindings for the pinned D01 running-header receiver."""
import hashlib
import json
from pathlib import Path

from vnext.normal_source_authority import ROOT
from vnext.requirement_profile_v1 import validate_execution_authority
from vnext.requirements import load_requirement_snapshot


HERE = Path(__file__).resolve().parent
PARENT = Path('requirements/issue_28_v13')
SUCCESSOR = Path('requirements/issue_28_v14')
CHANGED = ('scripts/vnext/d01_emphasis_results.py', 'scripts/vnext/normal_run_v3.py', 'scripts/vnext/ordinary_remaining_cases.py', 'scripts/vnext/ordinary_update_cycle.py', 'tools/vnext_normal_update.py', 'config/issue28_normal_results_v2.json', 'scripts/vnext/d01_running_header_28_v1.py', 'scripts/vnext/d01_emphasis_results_v3.py', 'scripts/vnext/ordinary_d01_header_update_v3.py')
NEW_FILES = ('scripts/vnext/d01_running_header_28_v1.py', 'scripts/vnext/d01_emphasis_results_v3.py', 'scripts/vnext/ordinary_d01_header_update_v3.py')
PARENT_FILES = ('CONTRACT.md', 'baseline_manifest.json',
                'decision_register.json', 'invariant_profile.json',
                'transfer_manifest.json')


def read(path):
    return json.loads((ROOT / path).read_text())


def write(path, value):
    (ROOT / path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def binding(path):
    raw = (ROOT / path).read_bytes()
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}


def main():
    before = {'code_root': str(ROOT), 'bindings': {},
              'parent_closure': read(SUCCESSOR/'baseline_manifest.json')
                  ['parent']['requirement_closure_hash']}
    for version in (PARENT, SUCCESSOR):
        manifest = read(version/'baseline_manifest.json')
        before['bindings'][str(version)] = {
            path: {'new_rule_files': manifest['new_rule_files'].get(path),
                   'execution_authority': manifest['execution_authority']['files'].get(path)}
            for path in CHANGED}
    (HERE/'binding-before.json').write_text(json.dumps(before, indent=2) + '\n')

    parent = read(PARENT/'baseline_manifest.json')
    for path in CHANGED:
        if path in parent['new_rule_files'] or path in NEW_FILES:
            parent['new_rule_files'][path] = binding(path)
        parent['execution_authority']['files'][path] = binding(path)
    write(PARENT/'baseline_manifest.json', parent)
    decision = read(PARENT/'decision_register.json')
    decision['policy'] = read('config/issue28_normal_results_v2.json')
    write(PARENT/'decision_register.json', decision)
    ordinary = load_requirement_snapshot(snapshot_dir=ROOT/PARENT)
    validate_execution_authority(repo_root=ROOT, requirement=ordinary)

    successor = read(SUCCESSOR/'baseline_manifest.json')
    successor['parent']['requirement_closure_hash'] = ordinary['requirement_closure_hash']
    for name in PARENT_FILES:
        successor['parent']['snapshot_files'][name] = binding(PARENT/name)
    continuous_rules = set(read('config/issue28_continuous_calls_v1.json')['rule_paths'])
    for path in NEW_FILES:
        if path not in continuous_rules:
            successor['new_rule_files'].pop(path, None)
    for path in CHANGED:
        if path in successor['new_rule_files']:
            successor['new_rule_files'][path] = binding(path)
        successor['execution_authority']['files'][path] = binding(path)
    write(SUCCESSOR/'baseline_manifest.json', successor)
    transfer = read(SUCCESSOR/'transfer_manifest.json')
    transfer['parent_requirement_closure_hash'] = ordinary['requirement_closure_hash']
    write(SUCCESSOR/'transfer_manifest.json', transfer)
    continuous = load_requirement_snapshot(snapshot_dir=ROOT/SUCCESSOR)
    validate_execution_authority(repo_root=ROOT, requirement=continuous)
    after = {'code_root': str(ROOT),
             'ordinary_requirement_closure': ordinary['requirement_closure_hash'],
             'continuous_requirement_closure': continuous['requirement_closure_hash'],
             'bindings': {path: binding(path) for path in CHANGED},
             'historical_frozen_snapshots_changed': False}
    (HERE/'binding-after.json').write_text(json.dumps(after, indent=2) + '\n')
    print(json.dumps(after, sort_keys=True))


if __name__ == '__main__':
    main()
