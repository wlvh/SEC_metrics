"""Exact candidate publication permission over the existing switch journal.

Plans and templates are inert. Only fresh GitHub provenance verification creates
the private permission used by deployment, switch and same-intent recovery.
"""
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
import json
import os
import re

from . import annual_candidate, publication as pub
from .annual_adoption import ROOT, need, read, record, check_id, git
from .annual_adoption_policy import V2, PENDING_CREDIT, policy, resolve_embedded
from .canonical import canonical_json_bytes, content_hash, sha256_file, sha256_bytes, strict_json_loads, parse_utc_timestamp
from .requirement_profile import validate_transition_activation_receipt, validate_execution_authority
from .requirements import load_requirement_snapshot

_FACTORY = object()
_context = ContextVar('annual_publication_authorization', default=None)
IMPLEMENTATION_PATHS = ('scripts', 'tools', 'config', 'catalog', 'requirements')


def _code(head):
    need(type(head) is str and re.fullmatch('[0-9a-f]{40}', head), 'ANNUAL_APPROVED_HEAD_INVALID')
    need(git('merge-base', head, 'HEAD').decode().strip() == head, 'ANNUAL_APPROVED_HEAD_NOT_ANCESTOR')
    return {'exact_head': head,
        'implementation_tree': content_hash(value=git('ls-tree', '-r', head, *IMPLEMENTATION_PATHS).decode()),
        'test_tree': content_hash(value=git('ls-tree', '-r', head, 'tests').decode())}


def _same_implementation(code, head):
    other = _code(head)
    need(all(other[k] == code[k] for k in ('implementation_tree', 'test_tree')), 'ANNUAL_APPROVED_IMPLEMENTATION_CHANGED')


def _target(root):
    from .annual_publication import safe_root, _marker
    need(type(root) is Path or isinstance(root, Path), 'ANNUAL_TARGET_ROOT_REQUIRED')
    need(root.is_absolute(), 'ANNUAL_TARGET_ROOT_REQUIRED')
    for path in (root, *root.parents):
        need(not path.is_symlink(), 'ANNUAL_TARGET_ALIAS')
    if root == ROOT:
        return root, 'PRODUCTION'
    root = safe_root(root)
    _marker(root)
    return root, 'ISOLATED_TEST'


def _bundle(directory):
    from . import annual_publication as annual
    directory = annual.safe_root(directory)
    manifest = pub.verify_publication_bundle(bundle_dir=directory)
    need(manifest['publication_credit'] == PENDING_CREDIT, 'ANNUAL_V1_HAS_NO_PRODUCTION_CREDIT')
    meta = read(directory, annual.META)
    chosen = resolve_embedded(meta['policy'])
    need(chosen['policy_id'] == V2, 'ANNUAL_FORMAL_POLICY_REQUIRED')
    adoption = read(directory, annual.SNAPSHOT + '/adoption.json')
    return manifest, meta, adoption


def _binding(directory, manifest, meta, adoption):
    return {'publication_id': manifest['publication_id'],
        'manifest_sha256': sha256_file(path=directory / 'publication_manifest.json'),
        'adoption_receipt_id': adoption['adoption_receipt_id'], 'source_snapshot_id': adoption['snapshot_id'],
        'candidate_file_set_id': meta['policy']['exact_candidate']['file_set_id'],
        'native_run_ids': adoption['native_run_ids'], 'original_execution_id': adoption['execution_id'],
        'selected_results_id': content_hash(value=adoption['selected_results']),
        'policy_id': meta['policy']['policy_id'], 'policy_hash': content_hash(value=meta['policy']),
        'requirement_id': manifest['requirement_id'], 'requirement_closure_hash': manifest['requirement_closure_hash'],
        'requirement_hashes': manifest['requirement_hashes']}


def plan_publication(*, bundle_dir, target_root, pull_number):
    """Prepare a fully bound inert plan; no approval or production writes."""
    need(not git('status', '--porcelain', '--untracked-files=all').strip(), 'ANNUAL_PLAN_CLEAN_CODE_REQUIRED')
    need(type(pull_number) is int and pull_number > 0, 'ANNUAL_PUBLICATION_PR_REQUIRED')
    root, environment = _target(target_root)
    manifest, meta, adoption = _bundle(bundle_dir)
    code = _code(meta['implementation_head'])
    _same_implementation(code, git('rev-parse', 'HEAD').decode().strip())
    view = pub.PublicationView.open(publication_root=root)
    baseline = meta['policy']['baseline_publication']
    need(view.publication_id == baseline['publication_id'] == manifest['previous_publication_id']
         and sha256_file(path=view.bundle_dir / 'publication_manifest.json') == baseline['manifest_sha256'],
         'ANNUAL_PLAN_PREDECESSOR_CHANGED')
    requirement = load_requirement_snapshot(snapshot_dir=ROOT / 'requirements' / manifest['requirement_id'])
    from .annual_publication import utc
    return record({'schema_version': 1, 'record_type': 'ANNUAL_PUBLICATION_PLAN', 'planned_at_utc': utc(),
        'repository': requirement['baseline']['repository']['identity'], 'pull_number': pull_number,
        'target_root': str(root), 'environment': environment, 'bundle_directory': str(bundle_dir),
        'code': code, 'binding': _binding(bundle_dir, manifest, meta, adoption),
        'predecessor': baseline, 'predecessor_pointer': read(root, 'outputs/active_publication.json'),
        'operations': meta['policy']['operations'], 'new_provider_paid_sec_calls': [0, 0, 0],
        'merge_rule': 'APPROVED_CONTENT_UNCHANGED_THROUGH_THIS_PR_MERGE',
        'approval_status': 'NOT_ISSUED'}, 'plan_id')


def validate_plan(plan):
    from . import annual_publication as annual
    need(type(plan) is dict and set(plan) == {'schema_version', 'record_type', 'repository', 'pull_number',
        'target_root', 'environment', 'bundle_directory', 'code', 'binding', 'predecessor', 'predecessor_pointer',
        'operations', 'new_provider_paid_sec_calls', 'merge_rule', 'approval_status', 'plan_id', 'planned_at_utc'}, 'ANNUAL_PUBLICATION_PLAN_FIELDS')
    check_id(plan, 'plan_id')
    parse_utc_timestamp(value=plan['planned_at_utc'])
    root, environment = _target(Path(plan['target_root']))
    need(environment == plan['environment'] and plan['new_provider_paid_sec_calls'] == [0, 0, 0]
         and plan['schema_version'] == 1 and plan['record_type'] == 'ANNUAL_PUBLICATION_PLAN'
         and plan['approval_status'] == 'NOT_ISSUED'
         and plan['merge_rule'] == 'APPROVED_CONTENT_UNCHANGED_THROUGH_THIS_PR_MERGE', 'ANNUAL_PLAN_SCOPE_CHANGED')
    directory = Path(plan['bundle_directory'])
    manifest, meta, adoption = _bundle(directory)
    need(plan['binding'] == _binding(directory, manifest, meta, adoption), 'ANNUAL_PLAN_CANDIDATE_OR_PACKAGE_CHANGED')
    need(plan['code'] == _code(meta['implementation_head']), 'ANNUAL_PLAN_CODE_CHANGED')
    _same_implementation(plan['code'], git('rev-parse', 'HEAD').decode().strip())
    # Code and its tests stay clean. Production pointer/mirrors are runtime
    # data; each operation separately validates their complete expected bytes.
    need(not git('status', '--porcelain', '--untracked-files=all', '--', *IMPLEMENTATION_PATHS, 'tests').strip(),
         'ANNUAL_PUBLICATION_CLEAN_CODE_REQUIRED')
    chosen = meta['policy']
    need(plan['operations'] == chosen['operations'] and plan['predecessor'] == chosen['baseline_publication']
         and manifest['previous_publication_id'] == plan['predecessor']['publication_id'], 'ANNUAL_PLAN_EDGE_CHANGED')
    pointer = plan['predecessor_pointer']
    predecessor_manifest = read(directory / 'internal/predecessor' / plan['predecessor']['publication_id'], 'publication_manifest.json')
    need(set(pointer) == {'publication_id', 'bundle_manifest_sha256', 'previous_publication_id', 'committed_at_utc'}
         and pointer['publication_id'] == plan['predecessor']['publication_id']
         and pointer['bundle_manifest_sha256'] == plan['predecessor']['manifest_sha256']
         and pointer['previous_publication_id'] == predecessor_manifest['previous_publication_id'], 'ANNUAL_PLAN_POINTER_CHANGED')
    parse_utc_timestamp(value=pointer['committed_at_utc'])
    requirement = load_requirement_snapshot(snapshot_dir=ROOT / 'requirements' / manifest['requirement_id'])
    validate_execution_authority(repo_root=ROOT, requirement=requirement)
    need(plan['repository'] == requirement['baseline']['repository']['identity']
         and type(plan['pull_number']) is int and plan['pull_number'] > 0
         and requirement['requirement_closure_hash'] == plan['binding']['requirement_closure_hash']
         and requirement['hashes'] == plan['binding']['requirement_hashes'], 'ANNUAL_PLAN_REQUIREMENT_CHANGED')
    return root, manifest, requirement


def expected_activation_approval(plan):
    return {'decision': 'APPROVE_REQUIREMENT_TRANSITION' if plan['environment'] == 'PRODUCTION'
            else 'TEST_ONLY_APPROVE_REQUIREMENT_TRANSITION', 'exact_head': plan['code']['exact_head'],
        'requirement_id': plan['binding']['requirement_id'], 'requirement_closure_hash': plan['binding']['requirement_closure_hash'],
        'scope': 'TRANSITION_ONLY', 'provider_paid_sec_authorized': False}


def expected_owner_approval(plan):
    """Same explicit decision/plan shape as annual_candidate, no model grant."""
    return {'decision': 'AUTHORIZE_CANDIDATE_SPECIFIC_PUBLICATION' if plan['environment'] == 'PRODUCTION'
            else 'TEST_ONLY_AUTHORIZE_ISOLATED_PUBLICATION',
        'plan_id': plan['plan_id'], 'requirement_id': plan['binding']['requirement_id'],
        'requirement_closure_hash': plan['binding']['requirement_closure_hash'],
        'policy_id': plan['binding']['policy_id'], 'policy_hash': plan['binding']['policy_hash'],
        'exact_head': plan['code']['exact_head'], 'environment': plan['environment'],
        'new_provider_paid_sec_calls': [0, 0, 0]}


def _comment(plan, url, expected):
    repository = plan['repository']
    match = re.fullmatch(r'https://github\.com/' + re.escape(repository) + r'/pull/([1-9][0-9]*)#issuecomment-([1-9][0-9]*)', url)
    need(match is not None and int(match[1]) == plan['pull_number'], 'ANNUAL_APPROVAL_LOCATION_INVALID')
    value = annual_candidate._github('repos/' + repository + '/issues/comments/' + match[2])
    need(type(value) is dict and value.get('html_url') == url and str(value.get('id')) == match[2]
         and value.get('issue_url') == 'https://api.github.com/repos/' + repository + '/issues/' + match[1]
         and value.get('user', {}).get('login') == repository.split('/')[0]
         and value.get('created_at') == value.get('updated_at'), 'ANNUAL_APPROVAL_PROVENANCE_INVALID')
    parse_utc_timestamp(value=value['created_at'])
    need(parse_utc_timestamp(value=value['created_at']) >= parse_utc_timestamp(value=plan['planned_at_utc']).replace(microsecond=0),
         'ANNUAL_APPROVAL_PREDATES_PLAN')
    need(strict_json_loads(text=value['body']) == expected, 'ANNUAL_PUBLICATION_APPROVAL_MISMATCH')
    return {**{k: value[k] for k in ('id', 'html_url', 'issue_url', 'body', 'created_at', 'updated_at')},
            'user': {'login': value['user']['login']}}


def _pull(plan, *, require_merge):
    pull = annual_candidate._github('repos/' + plan['repository'] + '/pulls/' + str(plan['pull_number']))
    need(pull.get('number') == plan['pull_number'] and pull.get('base', {}).get('ref') == 'main'
         and pull.get('base', {}).get('repo', {}).get('full_name') == plan['repository']
         and pull.get('head', {}).get('repo', {}).get('full_name') == plan['repository'], 'ANNUAL_RELEASE_PR_CHANGED')
    head = pull.get('head', {}).get('sha')
    _same_implementation(plan['code'], head)
    need(git('merge-base', plan['code']['exact_head'], head).decode().strip() == plan['code']['exact_head'], 'ANNUAL_REVIEWED_PR_ANCESTRY_CHANGED')
    if require_merge:
        merge = pull.get('merge_commit_sha')
        need(pull.get('merged') is True and pull.get('state') == 'closed' and type(merge) is str,
             'ANNUAL_REVIEWED_PR_MERGE_REQUIRED')
        parents = git('show', '-s', '--format=%P', merge).decode().split()
        need(len(parents) == 2 and parents[1] == head
             and git('merge-base', merge, 'HEAD').decode().strip() == merge, 'ANNUAL_EXACT_PR_MERGE_RELATION_REQUIRED')
        _same_implementation(plan['code'], merge)
    return {'number': pull['number'], 'repository': plan['repository'], 'base': 'main',
            'head': head, 'merge_commit_sha': pull.get('merge_commit_sha'), 'merged': pull.get('merged')}


def activate_requirement(*, plan, activation_url):
    """Verify real external activation; return a separate immutable receipt."""
    _, _, requirement = validate_plan(plan)
    _pull(plan, require_merge=False)
    comment = _comment(plan, activation_url, expected_activation_approval(plan))
    body = {'record_type': 'REQUIREMENT_TRANSITION_ACTIVATION', 'schema_version': 1,
        'requirement_id': requirement['requirement_id'], 'requirement_closure_hash': requirement['requirement_closure_hash'],
        'exact_head': plan['code']['exact_head'], 'authorization_scope': 'TRANSITION_ONLY',
        'provider_paid_sec_authorized': False, 'approval_kind': 'EXACT_HEAD_TRANSITION_APPROVAL',
        'owner': 'github:' + comment['user']['login'], 'approved_at_utc': comment['created_at'],
        'source_url': comment['html_url'], 'approval_text': comment['body'],
        'approval_text_sha256': sha256_bytes(content=comment['body'].encode())}
    receipt = record(body, 'receipt_id')
    if plan['environment'] == 'PRODUCTION':
        validate_transition_activation_receipt(receipt=receipt, requirement=requirement, exact_head=plan['code']['exact_head'])
    else:
        # A separately typed isolated receipt keeps the actual TEST_ONLY body.
        # Never rewrite it into the legacy production activation shape.
        body.update(record_type='ISOLATED_REQUIREMENT_TRANSITION_REHEARSAL',
            approval_kind='TEST_ONLY_TRANSITION_APPROVAL', authorization_scope='ISOLATED_TEST_ONLY',
            plan_id=plan['plan_id'])
        receipt = record(body, 'receipt_id')
    return receipt


@dataclass(frozen=True, init=False)
class PublicationPermission:
    _factory: object
    _bytes: bytes

    def __init__(self, *, factory, binding):
        need(factory is _FACTORY, 'ANNUAL_VERIFIED_GITHUB_PERMISSION_REQUIRED')
        object.__setattr__(self, '_factory', factory)
        object.__setattr__(self, '_bytes', canonical_json_bytes(value=binding))


def verify_authorization(*, plan, activation_url, owner_url):
    """The only permission factory: local JSON, templates and old grants cannot enter."""
    root, manifest, _ = validate_plan(plan)
    need(activation_url != owner_url, 'ANNUAL_DISTINCT_PUBLICATION_DECISION_REQUIRED')
    activation = activate_requirement(plan=plan, activation_url=activation_url)
    pull = _pull(plan, require_merge=plan['environment'] == 'PRODUCTION')
    owner = _comment(plan, owner_url, expected_owner_approval(plan))
    return PublicationPermission(factory=_FACTORY, binding={'plan': plan, 'activation': activation,
        'owner': owner, 'pull': pull, 'manifest': manifest})


def _permission(permission):
    need(type(permission) is PublicationPermission and permission._factory is _FACTORY, 'ANNUAL_VERIFIED_GITHUB_PERMISSION_REQUIRED')
    return strict_json_loads(text=permission._bytes.decode())


def has_context():
    return _context.get() is not None


def _current():
    value = _context.get()
    need(type(value) is tuple and len(value) == 3, 'ANNUAL_PRODUCTION_SWITCH_PERMISSION_REQUIRED')
    permission, operation, action = value
    binding = _permission(permission)
    return binding, operation, action


def switch_binding():
    binding, _, action = _current()
    return {'plan_id': binding['plan']['plan_id'], 'action_id': action['action_id'],
            'permission_id': content_hash(value=binding)}


def commit_authority(*, bundle_dir, manifest):
    binding, _, _ = _current()
    need(manifest == binding['manifest'] and sha256_file(path=bundle_dir / 'publication_manifest.json')
         == binding['plan']['binding']['manifest_sha256'], 'ANNUAL_AUTHORIZED_PACKAGE_CHANGED')
    return pub.FORMAL_COMMIT_AUTHORITY


def _edge(binding, action, pointer_path, manifest, expected_active_id, switch_mode):
    plan = binding['plan']
    need(pointer_path == Path(plan['target_root']) / 'outputs/active_publication.json', 'ANNUAL_AUTHORIZED_ROOT_CHANGED')
    need(manifest['publication_id'] == action['target_publication_id']
         and expected_active_id == action['previous_pointer']['publication_id']
         and switch_mode == action['switch_mode'], 'ANNUAL_AUTHORIZED_SWITCH_EDGE_CHANGED')
    expected_hash = plan['predecessor']['manifest_sha256'] if switch_mode == 'ROLLBACK' else plan['binding']['manifest_sha256']
    need(sha256_file(path=pointer_path.parent / 'publications' / manifest['publication_id'] / 'publication_manifest.json') == expected_hash,
         'ANNUAL_AUTHORIZED_TARGET_MANIFEST_CHANGED')


def guard_switch(*, pointer_path, manifest, expected_active_id, switch_mode):
    binding, _, action = _current()
    _edge(binding, action, pointer_path, manifest, expected_active_id, switch_mode)
    need(read(pointer_path.parent, pointer_path.name) == action['previous_pointer'], 'ANNUAL_AUTHORIZED_ACTIVE_CHANGED')
    directory = pointer_path.parent / 'publications' / expected_active_id
    pub.verify_publication_bundle(bundle_dir=directory)
    for source, target in pub.ROOT_MIRROR_RELATIVE_PATHS.items():
        need((pointer_path.parent.parent / target).read_bytes() == (directory / source).read_bytes(), 'ANNUAL_ACTIVE_MIRROR_CHANGED')


def guard_recovery(*, pointer_path, intent):
    binding, operation, action = _current()
    need(operation == 'recover', 'ANNUAL_EXPLICIT_RECOVERY_REQUIRED')
    target = intent['proposed_pointer']['publication_id']
    manifest = read(pointer_path.parent / 'publications' / target, 'publication_manifest.json')
    _edge(binding, action, pointer_path, manifest, intent['previous_pointer']['publication_id'], intent['switch_mode'])
    need(intent['previous_pointer'] == action['previous_pointer']
         and intent['proposed_pointer']['committed_at_utc'] == action['committed_at_utc']
         and intent.get('annual_authority') == switch_binding(), 'ANNUAL_RECOVERY_DIFFERENT_TRANSACTION')


def guard_mirror_repair(*, publication_root):
    binding, operation, _ = _current()
    need(operation == 'recover' and str(publication_root) == binding['plan']['target_root'], 'ANNUAL_MIRROR_REPAIR_NOT_AUTHORIZED')


def _action_path(root, plan, operation):
    return root / 'outputs/annual_publication_actions' / (plan['plan_id'][7:] + '-' + operation + '.json')


def _write_once(path, value):
    need(not path.is_symlink() and not path.parent.is_symlink(), 'ANNUAL_ACTION_PATH_UNSAFE')
    path.parent.mkdir(exist_ok=True)
    descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(canonical_json_bytes(value=value)); stream.flush(); os.fsync(stream.fileno())


def _save_permission(root, binding):
    identity = content_hash(value=binding)
    path = root / 'outputs/annual_publication_authorizations' / (identity[7:] + '.json')
    if path.exists():
        need(read(path.parent, path.name) == binding, 'ANNUAL_SAVED_PERMISSION_CHANGED')
    else:
        _write_once(path, binding)


def _action(root, plan, operation):
    path = _action_path(root, plan, operation)
    value = read(path.parent, path.name); check_id(value, 'action_id')
    target = plan['predecessor']['publication_id'] if operation == 'rollback' else plan['binding']['publication_id']
    previous = plan['binding']['publication_id'] if operation == 'rollback' else plan['predecessor']['publication_id']
    need(set(value) == {'action_id', 'plan_id', 'operation', 'previous_pointer', 'target_publication_id', 'switch_mode', 'committed_at_utc'}
         and value['plan_id'] == plan['plan_id'] and value['operation'] == operation
         and value['target_publication_id'] == target and value['previous_pointer']['publication_id'] == previous
         and value['switch_mode'] == ('ROLLBACK' if operation == 'rollback' else 'COMMIT'), 'ANNUAL_SAVED_ACTION_CHANGED')
    parse_utc_timestamp(value=value['committed_at_utc'])
    return value


def _complete(root, binding, action, pointer):
    plan = binding['plan']
    receipt = pub._switch_receipt_for_pointer(pointer_path=root / 'outputs/active_publication.json', pointer=pointer)
    need(receipt.get('annual_authority') == {'plan_id': plan['plan_id'], 'action_id': action['action_id'],
        'permission_id': content_hash(value=binding)} and pointer['committed_at_utc'] == action['committed_at_utc']
        and pointer['publication_id'] == action['target_publication_id']
        and pointer['previous_publication_id'] == action['previous_pointer']['publication_id'],
        'ANNUAL_COMPLETION_NOT_THIS_AUTHORIZED_SWITCH')
    return receipt


def deploy(*, permission):
    """Copy only a fully verified approved immutable package; never change active."""
    from .annual_publication import _verified, _Verified, _FACTORY as verified_factory
    binding = _permission(permission); plan = binding['plan']
    root, manifest, _ = validate_plan(plan)
    need(manifest == binding['manifest'], 'ANNUAL_AUTHORIZED_PACKAGE_CHANGED')
    need(read(root, 'outputs/active_publication.json') == plan['predecessor_pointer'], 'ANNUAL_DEPLOY_PREDECESSOR_CHANGED')
    _save_permission(root, binding)
    target = root / 'outputs/publications' / manifest['publication_id']
    if target.exists():
        need(pub.verify_publication_bundle(bundle_dir=target) == manifest, 'ANNUAL_DEPLOYED_PACKAGE_CHANGED')
        return {'status': 'ALREADY_DEPLOYED', 'publication_id': manifest['publication_id']}
    source = Path(plan['bundle_directory'])
    files = {entry['path']: (source / entry['path']).read_bytes() for entry in manifest['files']}
    with _verified(_Verified(verified_factory, manifest)):
        pub._persist_prepared_publication_bundle(publications_dir=target.parent, files=files, manifest=manifest)
    return {'status': 'DEPLOYED_INACTIVE', 'publication_id': manifest['publication_id']}


def execute(*, permission, operation):
    """One publish, one rollback, one restore; recover belongs to its existing action."""
    from . import annual_publication as annual
    binding = _permission(permission); plan = binding['plan']
    root, manifest, _ = validate_plan(plan)
    need(manifest == binding['manifest'] and operation in {'publish', 'rollback', 'restore', 'recover'}, 'ANNUAL_OPERATION_NOT_AUTHORIZED')
    directory = root / 'outputs/publications' / manifest['publication_id']
    need(pub.verify_publication_bundle(bundle_dir=directory) == manifest, 'ANNUAL_DEPLOYED_PACKAGE_REQUIRED')
    if operation == 'recover':
        intent = pub._load_switch_intent(pointer_path=root / 'outputs/active_publication.json')
        actions = []
        for name in ('publish', 'rollback', 'restore'):
            path = _action_path(root, plan, name)
            if path.exists():
                action = _action(root, plan, name)
                if intent and action['committed_at_utc'] == intent['proposed_pointer']['committed_at_utc']:
                    actions.append(action)
        if intent is None:
            view = pub.PublicationView.open(publication_root=root)
            pointer = read(root, 'outputs/active_publication.json')
            for name in ('publish', 'rollback', 'restore'):
                if _action_path(root, plan, name).exists():
                    action = _action(root, plan, name)
                    if view.publication_id == action['target_publication_id'] and pointer['committed_at_utc'] == action['committed_at_utc']:
                        _complete(root, binding, action, pointer)
                        return {'status': 'RECOVERED_SAME_COMMITTED_SWITCH_RECORD', 'publication_id': view.publication_id}
            return {'status': 'NO_PENDING_AUTHORIZED_SWITCH', 'publication_id': view.publication_id}
        need(len(actions) == 1, 'ANNUAL_RECOVERY_NOT_THIS_AUTHORIZED_SWITCH')
        action = actions[0]
    else:
        need(pub._load_switch_intent(pointer_path=root / 'outputs/active_publication.json') is None, 'ANNUAL_RECOVERY_REQUIRED')
        path = _action_path(root, plan, operation)
        if path.exists():
            prior = _action(root, plan, operation)
            return {'status': 'AUTHORIZED_OPERATION_ALREADY_RESERVED', 'action_id': prior['action_id'],
                    'publication_id': pub.PublicationView.open(publication_root=root).publication_id}
        previous = plan['predecessor_pointer']
        if operation != 'publish':
            previous_name = 'publish' if operation == 'rollback' else 'rollback'
            need(_action_path(root, plan, previous_name).exists(), 'ANNUAL_PRIOR_AUTHORIZED_OPERATION_NOT_COMPLETED')
            prior_action = _action(root, plan, previous_name)
            previous = read(root, 'outputs/active_publication.json')
            _complete(root, binding, prior_action, previous)
        need(read(root, 'outputs/active_publication.json') == previous, 'ANNUAL_EXPECTED_ACTIVE_CHANGED')
        target = manifest['previous_publication_id'] if operation == 'rollback' else manifest['publication_id']
        action = record({'plan_id': plan['plan_id'], 'operation': operation,
            'previous_pointer': previous, 'target_publication_id': target,
            'switch_mode': 'ROLLBACK' if operation == 'rollback' else 'COMMIT',
            'committed_at_utc': annual.utc()}, 'action_id')
        _save_permission(root, binding)
        _write_once(path, action)
    token = _context.set((permission, operation, action))
    try:
        if operation != 'recover':
            pub._fault_injection_checkpoint(fault_point='ANNUAL_ACTION_RESERVED_BEFORE_NATIVE_SWITCH')
        with annual._verified(annual._Verified(annual._FACTORY, manifest)):
            if operation == 'recover':
                pub.recover_publication_mirrors(publication_root=root)
            elif operation == 'rollback':
                pub.rollback_publication(publication_root=root, target_publication_id=action['target_publication_id'],
                    expected_active_publication_id=action['previous_pointer']['publication_id'], committed_at_utc=action['committed_at_utc'])
            else:
                pub._commit_publication(publication_root=root, publication_id=manifest['publication_id'],
                    expected_active_publication_id=action['previous_pointer']['publication_id'], committed_at_utc=action['committed_at_utc'])
            view = pub.PublicationView.open(publication_root=root)
            pointer = read(root, 'outputs/active_publication.json')
            if view.publication_id == action['target_publication_id']:
                _complete(root, binding, action, pointer)
            return {'status': 'AUTHORIZED_' + operation.upper() + '_COMPLETED', 'publication_id': view.publication_id,
                'environment': plan['environment'], 'action_id': action['action_id'], 'new_provider_paid_sec_calls': [0, 0, 0]}
    finally:
        _context.reset(token)
