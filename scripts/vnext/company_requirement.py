"""Fixed successor runtime for company source admission; business rules inherit."""
from pathlib import Path

from .canonical import content_hash, sha256_file, strict_json_file
from .requirement_profile_v1 import PROFILE_SNAPSHOT_FILES, RequirementProfileError
from .sources import resolve_repository_file

PARENTS = {'issue_54_v1': 'issue_28_v13', 'issue_54_history_v1': 'issue_47_v1'}
PROFILE_REQUIREMENT_GENERATION = 'COMPANY_SEPARATION_V1'


def load_profile_requirement_snapshot(*, snapshot_dir, parent_loader):
    """Verify the installed successor and retain every parent obligation."""
    def need(ok, reason):
        if not ok:
            raise RequirementProfileError(reason)
    installed = Path(__file__).resolve().parents[2]
    root = snapshot_dir.parent.parent
    requirement_id = snapshot_dir.name
    need(requirement_id in PARENTS, 'Company successor identity unsupported')
    parent_id = PARENTS[requirement_id]
    need(snapshot_dir.name == requirement_id
         and {p.name for p in snapshot_dir.iterdir()} == PROFILE_SNAPSHOT_FILES,
         'Company successor snapshot directory differs')
    for name in PROFILE_SNAPSHOT_FILES:
        relative = 'requirements/'+requirement_id+'/'+name
        need(resolve_repository_file(repo_root=root, repo_relative_path=relative).read_bytes()
             == resolve_repository_file(repo_root=installed, repo_relative_path=relative).read_bytes(),
             'Company successor installed snapshot differs:'+name)
    baseline = strict_json_file(path=snapshot_dir/'baseline_manifest.json')
    need(baseline['requirement_id'] == requirement_id
         and baseline['requirement_generation'] == PROFILE_REQUIREMENT_GENERATION
         and baseline['production_authorized'] is False,
         'Company successor identity or authority differs')
    # The parent was fully loaded and validated before installation changed
    # the four dispatch files. Reconstruct its frozen authority instead of
    # executing an old engine against the successor's different code tree.
    frozen = baseline['parent']['loaded_snapshot']
    parent_path = resolve_repository_file(repo_root=root, repo_relative_path=frozen['path'])
    need({'sha256': sha256_file(path=parent_path), 'size': parent_path.stat().st_size}
         == {k: frozen[k] for k in ('sha256', 'size')}, 'Company frozen parent differs')
    parent = strict_json_file(path=parent_path)
    need(parent['requirement_id'] == parent_id
         and content_hash(value=parent['hashes']) == parent['requirement_closure_hash'],
         'Company frozen parent identity differs')
    need(baseline['parent']['requirement_id'] == parent_id
         and baseline['parent']['requirement_closure_hash'] == parent['requirement_closure_hash'],
         'Company successor parent differs')
    for name, binding in baseline['parent']['snapshot_files'].items():
        path = root/'requirements'/parent_id/name
        need({'sha256': sha256_file(path=path), 'size': path.stat().st_size} == binding,
             'Company successor parent bytes differ:'+name)
    validator = baseline['validator']
    need(validator['path'] == 'scripts/vnext/company_requirement.py'
         and sha256_file(path=root/validator['path']) == validator['sha256']
         and sha256_file(path=installed/validator['path']) == validator['sha256'],
         'Company successor validator differs')
    decisions = strict_json_file(path=snapshot_dir/'decision_register.json')
    need(decisions == {'status': 'USER_DELEGATED_DEVELOPMENT_ONLY',
                      'delegation_url': 'https://github.com/wlvh/SEC_metrics/issues/54',
                      'new_business_calls': [0, 0, 0], 'production_authorized': False},
         'Company successor development boundary differs')
    transfer = strict_json_file(path=snapshot_dir/'transfer_manifest.json')
    need(transfer == {'parent_requirement_id': parent_id,
                     'parent_requirement_closure_hash': parent['requirement_closure_hash'],
                     'disposition': 'CARRY_ALL_PARENT_OBLIGATIONS_WITHOUT_ACTIVATION',
                     'pending_decision_ids': parent['pending_decision_ids']},
         'Company successor transfer differs')
    hashes = {key: sha256_file(path=snapshot_dir/name) for key, name in (
        ('baseline_sha256', 'baseline_manifest.json'), ('contract_sha256', 'CONTRACT.md'),
        ('decision_register_sha256', 'decision_register.json'),
        ('invariant_profile_sha256', 'invariant_profile.json'),
        ('transfer_manifest_sha256', 'transfer_manifest.json'))}
    hashes.update(parent_requirement_closure_hash=parent['requirement_closure_hash'],
                  validator_sha256=validator['sha256'])
    return {**parent, 'baseline': baseline, 'requirement_id': requirement_id,
        'requirement_generation': PROFILE_REQUIREMENT_GENERATION,
        'requirement_closure_hash': content_hash(value=hashes), 'hashes': hashes,
        'execution_authority': baseline['execution_authority'],
        'parent_snapshot': parent, 'parent_requirement_id': parent_id,
        'parent_requirement_closure_hash': parent['requirement_closure_hash'],
        'activation_state': 'NOT_ACTIVATED', 'transfer': transfer,
        'issue_contract_revision': 'company-separation-v1',
        'evaluated_invariants': strict_json_file(path=snapshot_dir/'invariant_profile.json')}
