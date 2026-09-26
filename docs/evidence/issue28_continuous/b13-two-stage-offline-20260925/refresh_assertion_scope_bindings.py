"""Rebind only the mutable Issue #28 V15 B13 assertion-scope increment."""
import hashlib
import json
from pathlib import Path

from vnext.normal_source_authority import ROOT
from vnext.requirements import load_requirement_snapshot
from vnext.requirement_profile_v1 import validate_execution_authority


HERE = Path(__file__).resolve().parent
FILES = (
    'config/issue28_continuous_calls_v1.json',
    'scripts/vnext/capacity_reference_contract.py',
    'scripts/vnext/capacity_two_stage.py',
    'scripts/vnext/native_unit_index.py',
    'scripts/vnext/native_assessment_replay.py',
    'scripts/vnext/capacity_native_assessment.py',
    'scripts/vnext/continuous_semantic_calls.py',
    'scripts/vnext/capacity_assessment_input.py',
    'scripts/vnext/capacity_run.py',
    'scripts/vnext/capacity_program_roles.py',
)


def binding(relative):
    raw = (ROOT / relative).read_bytes()
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}


def main():
    manifest_path = ROOT / 'requirements/issue_28_v14/baseline_manifest.json'
    manifest = json.loads(manifest_path.read_text())
    before = {path: {'rule': manifest['new_rule_files'].get(path),
                     'execution': manifest['execution_authority']['files'][path]}
              for path in FILES}
    before_path = HERE / 'assertion-binding-before.json'
    if not before_path.exists():
        before_path.write_text(json.dumps(before, ensure_ascii=False, indent=2) + '\n')
    decision_path = ROOT / 'requirements/issue_28_v14/decision_register.json'
    decision = json.loads(decision_path.read_text())
    decision['policy'] = json.loads(
        (ROOT / 'config/issue28_continuous_calls_v1.json').read_text())
    decision_path.write_text(json.dumps(decision, ensure_ascii=False, indent=2) + '\n')
    for relative in FILES:
        current = binding(relative)
        if relative in manifest['new_rule_files']:
            manifest['new_rule_files'][relative] = current
        manifest['execution_authority']['files'][relative] = current
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    requirement = load_requirement_snapshot(snapshot_dir=manifest_path.parent)
    validate_execution_authority(repo_root=ROOT, requirement=requirement)
    after = {'code_root': str(ROOT),
             'requirement_closure_hash': requirement['requirement_closure_hash'],
             'changed_file_bindings': {path: binding(path) for path in FILES},
             'frozen_parent_files_modified': False}
    (HERE / 'assertion-binding-after.json').write_text(
        json.dumps(after, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'requirement_closure_hash': after['requirement_closure_hash'],
                      'changed_file_count': len(FILES)}))


if __name__ == '__main__':
    main()
