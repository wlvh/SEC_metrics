"""Rebind mutable V15 after disabling V6 native acceptance."""
import hashlib
import json
from pathlib import Path

from vnext.normal_source_authority import ROOT
from vnext.requirement_profile_v1 import validate_execution_authority
from vnext.requirements import load_requirement_snapshot


HERE = Path(__file__).resolve().parent
FILES = ('scripts/vnext/capacity_two_stage.py',
         'scripts/vnext/continuous_semantic_calls.py',
         'scripts/vnext/native_assessment_replay.py',
         'config/issue28_continuous_calls_v1.json')


def binding(relative):
    raw = (ROOT/relative).read_bytes()
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}


def main():
    base_path = ROOT/'requirements/issue_28_v14/baseline_manifest.json'
    decision_path = ROOT/'requirements/issue_28_v14/decision_register.json'
    baseline = json.loads(base_path.read_text())
    before = {'preceding_closure':
              'sha256:805130a44789ce57fe7d8f5149918c06612b21de2b06229edabcade9e0c7f9ff',
              'file_bindings': {path: baseline['execution_authority']['files'][path]
                                for path in FILES}}
    (HERE/'v6-suspension-binding-before.json').write_text(
        json.dumps(before, ensure_ascii=False, indent=2)+'\n')
    decision = json.loads(decision_path.read_text())
    decision['policy'] = json.loads((ROOT/FILES[-1]).read_text())
    decision_path.write_text(json.dumps(decision, ensure_ascii=False, indent=2)+'\n')
    for relative in FILES:
        current = binding(relative)
        if relative in baseline['new_rule_files']:
            baseline['new_rule_files'][relative] = current
        baseline['execution_authority']['files'][relative] = current
    base_path.write_text(json.dumps(baseline, ensure_ascii=False, indent=2)+'\n')
    requirement = load_requirement_snapshot(snapshot_dir=base_path.parent)
    validate_execution_authority(repo_root=ROOT, requirement=requirement)
    after = {'code_root': str(ROOT),
             'requirement_closure_hash': requirement['requirement_closure_hash'],
             'changed_file_bindings': {path: binding(path) for path in FILES},
             'frozen_parent_files_modified': False}
    (HERE/'v6-suspension-binding-after.json').write_text(
        json.dumps(after, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'requirement_closure_hash':after['requirement_closure_hash'],
                      'changed_file_count':len(FILES)}))


if __name__ == '__main__':
    main()
