"""Refresh only the unfrozen Issue #28 V14/V15 C04 development bindings.

Run after the explicit C04 implementation is final. Historical snapshots are
read as parents; this script never changes them or any recorded Run.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

from vnext.normal_source_authority import ROOT
from vnext.requirement_profile_v1 import validate_execution_authority
from vnext.requirements import load_requirement_snapshot


HERE = Path(__file__).resolve().parent
CHANGED = (
    'catalog/r5/C04_auditor_changes_v3.md',
    'config/issue28_normal_results_v2.json',
    'scripts/vnext/c04_registration_successor.py',
    'scripts/vnext/normal_run_v3.py',
)
NEW = {'catalog/r5/C04_auditor_changes_v3.md',
       'scripts/vnext/c04_registration_successor.py'}
CONTINUOUS_CHANGED = ('config/issue28_continuous_calls_v1.json',)
PARENT_FILES = ('CONTRACT.md', 'baseline_manifest.json',
                'decision_register.json', 'invariant_profile.json',
                'transfer_manifest.json')


def read(relative):
    return json.loads((ROOT / relative).read_text())


def write(relative, value):
    (ROOT / relative).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def binding(relative):
    raw = (ROOT / relative).read_bytes()
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}


def main(evidence_suffix):
    assert re.fullmatch(r'[a-z0-9-]+', evidence_suffix)
    suffix = '-' + evidence_suffix
    parent = 'requirements/issue_28_v13/'
    successor = 'requirements/issue_28_v14/'
    previous = {version: read(f'requirements/issue_28_v{version}/baseline_manifest.json')
                for version in (13, 14)}
    before = {
        'code_root': str(ROOT),
        'prior_parent_closure': previous[14]['parent']['requirement_closure_hash'],
        'changed_file_bindings': {
            str(version): {path: previous[version]['execution_authority']['files'].get(path)
                           for path in CHANGED}
            for version in (13, 14)},
    }
    (HERE / ('binding-before' + suffix + '.json')).write_text(
        json.dumps(before, indent=2) + '\n')

    policy = read('config/issue28_normal_results_v2.json')
    decision = read(parent + 'decision_register.json')
    decision['policy'] = policy
    write(parent + 'decision_register.json', decision)
    baseline = read(parent + 'baseline_manifest.json')
    for relative in CHANGED:
        file_binding = binding(relative)
        if relative in baseline['new_rule_files']:
            baseline['new_rule_files'][relative] = file_binding
        if relative in baseline['execution_authority']['files'] or relative in NEW:
            baseline['execution_authority']['files'][relative] = file_binding
    write(parent + 'baseline_manifest.json', baseline)
    ordinary = load_requirement_snapshot(snapshot_dir=ROOT / parent)
    validate_execution_authority(repo_root=ROOT, requirement=ordinary)

    continuous_policy = read('config/issue28_continuous_calls_v1.json')
    continuous_decision = read(successor + 'decision_register.json')
    continuous_decision['policy'] = continuous_policy
    write(successor + 'decision_register.json', continuous_decision)
    baseline = read(successor + 'baseline_manifest.json')
    baseline['parent']['requirement_closure_hash'] = ordinary['requirement_closure_hash']
    for name in PARENT_FILES:
        baseline['parent']['snapshot_files'][name] = binding(parent + name)
    for relative in (*CHANGED, *CONTINUOUS_CHANGED):
        file_binding = binding(relative)
        if relative in baseline['new_rule_files']:
            baseline['new_rule_files'][relative] = file_binding
        if relative in baseline['execution_authority']['files'] or relative in NEW:
            baseline['execution_authority']['files'][relative] = file_binding
    write(successor + 'baseline_manifest.json', baseline)
    transfer = read(successor + 'transfer_manifest.json')
    transfer['parent_requirement_closure_hash'] = ordinary['requirement_closure_hash']
    write(successor + 'transfer_manifest.json', transfer)
    continuous = load_requirement_snapshot(snapshot_dir=ROOT / successor)
    validate_execution_authority(repo_root=ROOT, requirement=continuous)
    after = {
        'code_root': str(ROOT),
        'ordinary_requirement_closure': ordinary['requirement_closure_hash'],
        'continuous_requirement_closure': continuous['requirement_closure_hash'],
        'ordinary_execution_authority_file_count': len(ordinary['execution_authority']['files']),
        'continuous_execution_authority_file_count': len(continuous['execution_authority']['files']),
        'changed_file_bindings': {path: binding(path)
                                  for path in (*CHANGED, *CONTINUOUS_CHANGED)},
        'frozen_parent_files_modified': False,
    }
    (HERE / ('binding-after' + suffix + '.json')).write_text(
        json.dumps(after, indent=2) + '\n')
    print(json.dumps({key: after[key] for key in ('ordinary_requirement_closure',
        'continuous_requirement_closure', 'ordinary_execution_authority_file_count',
        'continuous_execution_authority_file_count')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence-suffix', required=True)
    args = parser.parse_args()
    main(args.evidence_suffix)
