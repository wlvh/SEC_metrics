"""Append mutable V15 bindings for the bounded V6 review repair."""
import hashlib
import json
from pathlib import Path

from vnext.normal_source_authority import ROOT
from vnext.requirement_profile_v1 import validate_execution_authority
from vnext.requirements import load_requirement_snapshot


HERE = Path(__file__).resolve().parent
FILES = ('scripts/vnext/capacity_two_stage.py',
         'config/issue28_continuous_calls_v1.json')


def binding(relative):
    raw = (ROOT / relative).read_bytes()
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}


def main():
    manifest_path = ROOT / 'requirements/issue_28_v14/baseline_manifest.json'
    decision_path = ROOT / 'requirements/issue_28_v14/decision_register.json'
    manifest = json.loads(manifest_path.read_text())
    before = {'previous_requirement_closure':
              'sha256:5917d8f0687be9dafe05bf4544260a5b674725ae660753bd2bdb7a7e3af134c2',
              'changed_file_bindings': {path: {
                  'new_rule': manifest['new_rule_files'].get(path),
                  'execution': manifest['execution_authority']['files'][path]}
                  for path in FILES}}
    (HERE/'assertion-binding-before-repair.json').write_text(
        json.dumps(before, ensure_ascii=False, indent=2) + '\n')
    decision = json.loads(decision_path.read_text())
    decision['policy'] = json.loads(
        (ROOT/'config/issue28_continuous_calls_v1.json').read_text())
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
    (HERE/'assertion-binding-after-repair.json').write_text(
        json.dumps(after, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'requirement_closure_hash':
        requirement['requirement_closure_hash'], 'changed_file_count': len(FILES)}))


if __name__ == '__main__':
    main()
