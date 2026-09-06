"""Repository-owned R4 release eligibility, separate from child Run validity.

No network or publication mutation lives here. A LIVE context requires the
merged transition, the exact owner-authorized live graph and an independent
disk replay. A recorded rehearsal context can exist only outside the actual
implementation checkout and never acquires live/publication credit.
"""

from __future__ import annotations

from pathlib import Path
from typing import Mapping
from datetime import datetime, timezone
import subprocess
import re

from .canonical import canonical_json_bytes, content_hash, sha256_bytes, strict_json_file, strict_json_loads
from .projector import _load_registry
from .publication import PublicationView, ROOT_MIRROR_RELATIVE_PATHS
from .requirement_profile import EXPLICIT_ARTIFACT_GENERATION, validate_execution_authority
from .requirement_profile import validate_transition_activation_receipt
from .requirements import load_requirement_snapshot
from .source_strategy import load_release_plan_artifact
from .sources import resolve_repository_file
from .specs import compile_spec_file
from .calculator import metric_is_applicable
from .traits import repository_company_traits

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
from .r4_label_policy import CURRENT_R4_REQUIREMENT, release_plan_id as version_release_plan_id

REQUIREMENT_ID = CURRENT_R4_REQUIREMENT
RELEASE_PLAN_ID = version_release_plan_id(REQUIREMENT_ID)
RELEASE_PLAN_PATH = 'config/release_plans/' + RELEASE_PLAN_ID + '.json'
ACTIVATION_PATH = 'docs/evidence/' + REQUIREMENT_ID + '_transition_activation.json'
RELEASE_RUNTIME = 'artifacts/vnext/qualification/r4_release'
_FACTORY = object()
_PORTABLE = object()


class R4ReleaseError(ValueError):
    """An otherwise FROZEN Run is not sufficient R4 publication authority."""


def _plain(value):
    return strict_json_loads(text=canonical_json_bytes(value=value).decode('utf-8'))


def _require(value, label):
    if not value:
        raise R4ReleaseError(label)


def _file(root, relative):
    return resolve_repository_file(repo_root=root, repo_relative_path=relative)


def _json(root, relative):
    return strict_json_file(path=_file(root, relative))


def _binding(path):
    _require(path.is_file() and not path.is_symlink(), 'Release input is not a regular file')
    data = path.read_bytes()
    return {'sha256': sha256_bytes(content=data), 'size': len(data)}


def _oid(identity):
    _require(type(identity) is str and len(identity) == 71 and identity.startswith('sha256:')
             and all(c in '0123456789abcdef' for c in identity[7:]), 'Release content ID is malformed')
    return identity[7:]


def _self_id(value, key):
    _require(type(value) is dict and key in value
             and value[key] == content_hash(value={k: v for k, v in value.items() if k != key}),
             'Release proof self identity differs: ' + key)
    _oid(value[key])


def _safe_rehearsal_root(root):
    actual = REPOSITORY_ROOT.resolve()
    root = root.resolve(strict=True)
    _require(root != actual and not root.is_relative_to(actual)
             and not actual.is_relative_to(root), 'Recorded rehearsal cannot target the implementation root')
    _require(not (root / '.git').exists() and not (root / '.git').is_symlink(),
             'Recorded rehearsal needs an independent non-Git copied workspace')
    return root


def _git(root, *args):
    from git_workspace import git_checkout_metadata_error, sanitized_git_environment
    _require(not git_checkout_metadata_error(repo_root=root), 'Release Git metadata is unsafe')
    result = subprocess.run(['git', '--no-replace-objects', *args], cwd=root,
        env=sanitized_git_environment(), capture_output=True, check=False)
    _require(result.returncode == 0, 'Release Git identity/ancestry is invalid')
    return result.stdout.decode().strip()


def _git_bytes(root, *args):
    from git_workspace import sanitized_git_environment
    result = subprocess.run(['git', '--no-replace-objects', *args], cwd=root,
        env=sanitized_git_environment(), capture_output=True, check=False)
    _require(result.returncode == 0, 'Release Git object is unavailable')
    return result.stdout


def _merged_implementation(root, requirement, activation, commit, owner, *, require_clean=True):
    """Bind an actual merge parent, not an invented self-signed status flag."""
    _require(all(type(value) is str and re.fullmatch(r'[0-9a-f]{40}', value) is not None
                 for value in (commit, owner.get('exact_head'), owner.get('exact_tree'))),
             'Release Git identity/ancestry is invalid: exact commit/tree SHA required')
    validate_transition_activation_receipt(receipt=activation, requirement=requirement,
                                           exact_head=activation.get('exact_head'))
    parents = _git(root, 'show', '-s', '--format=%P', commit).split()
    _require(len(parents) == 2 and activation['exact_head'] in parents,
             'Implementation is not the exact approved transition merge')
    _git(root, 'merge-base', '--is-ancestor', commit, 'origin/main')
    _git(root, 'merge-base', '--is-ancestor', commit, owner['exact_head'])
    _git(root, 'merge-base', '--is-ancestor', owner['exact_head'], 'HEAD')
    _require(_git(root, 'rev-parse', owner['exact_head'] + '^{tree}') == owner['exact_tree'],
             'Live owner receipt tree differs from its actual commit')
    if require_clean:
        _require(not _git(root, 'status', '--porcelain=v1', '--untracked-files=all'),
                 'LIVE release requires a clean exact committed checkout')
    changed = _git(root, 'diff', '--name-only', commit, 'HEAD', '--', 'scripts', 'tools').splitlines()
    _require(not any(path.endswith('.py') for path in changed),
             'PR-C cannot modify production Python after the implementation merge')
    for relative, expected in requirement['execution_authority']['files'].items():
        raw = _git_bytes(root, 'show', commit + ':' + relative)
        _require(expected == {'sha256': sha256_bytes(content=raw), 'size': len(raw)},
                 'Merged implementation execution authority differs: ' + relative)
    for path in sorted((root / 'requirements' / requirement['requirement_id']).iterdir()):
        relative = path.relative_to(root).as_posix()
        raw = _git_bytes(root, 'show', commit + ':' + relative)
        _require(raw == path.read_bytes(), 'Merged Requirement snapshot differs')
    return {'commit': commit, 'tree': _git(root, 'rev-parse', commit + '^{tree}'),
            'approved_head': activation['exact_head']}


def _release_authority(root, requirement_id=REQUIREMENT_ID):
    requirement = load_requirement_snapshot(snapshot_dir=root / 'requirements' / requirement_id)
    validate_execution_authority(repo_root=root, requirement=requirement)
    plan = load_release_plan_artifact(repo_root=root, release_plan_id=version_release_plan_id(requirement_id))
    _require(plan['record_type'] == 'SUCCESSOR_RELEASE_PLAN' and plan['schema_version'] == 3
             and plan['artifact_requirement_generation'] == EXPLICIT_ARTIFACT_GENERATION
             and plan['requirement_id'] == requirement_id
             and plan['requirement_closure_hash'] == requirement['requirement_closure_hash']
             and plan['requirement_hashes'] == requirement['hashes']
             and plan['release_stage'] == 'R4'
             and plan['added_metric_ids'] == ['A03', 'A04', 'A09', 'A11', 'A12', 'A13']
             and plan['parent_release_plan_id'] == 'issue_15_lodging_r3',
             'R4 successor ReleasePlan identity/scope differs')
    from .r4_task_contracts import _read_catalog, resolve_r4_task_contract
    catalog, _ = _read_catalog(repo_root=root)
    tasks, specs, spec_paths = {}, {}, {}
    for declaration in catalog['tasks']:
        metric = declaration['metric_id']
        path = declaration['metric_spec_path']
        _require(path.startswith('catalog/r4_v2/'), 'R4 cannot project from the old metric catalog')
        task = resolve_r4_task_contract(repo_root=root, requirement=requirement,
            task_contract_id=declaration['task_contract_id'])
        spec = compile_spec_file(path=_file(root, path), dependency_specs={})
        _require(spec['compiled']['metric_id'] == metric
                 and task['metric_spec_closure_hashes'] == [spec['spec_closure_hash']]
                 and task['metric_spec_semantic_hashes'] == [spec['spec_semantic_hash']],
                 'R4 task/MetricSpec closure differs')
        tasks[metric], specs[metric], spec_paths[metric] = task, spec, path
    _require(sorted(specs) == plan['added_metric_ids'], 'R4 Spec exact set differs')
    registry = _load_registry(repo_root=root)
    _require(len(registry) == 10, 'R4 public registry must contain exactly ten companies')
    expected = []
    for company in registry:
        traits = repository_company_traits(repo_root=root, company_id=company['company_id'])
        for metric in sorted(specs):
            applicable = metric_is_applicable(applicability=specs[metric]['compiled']['applicability'], traits=traits)
            expected.append({'company_id': company['company_id'], 'metric_id': metric,
                'applicability': 'APPLICABLE' if applicable else 'N_A_STRUCTURAL'})
    active = [row for row in expected if row['applicability'] == 'APPLICABLE']
    _require(len(active) == 6 and len({row['company_id'] for row in active}) == 1
             and len(expected) == 60 and len(plan['cumulative_vnext_result_keys']) == 300,
             'R4 registry/Spec applicability is not exact six plus fifty-four')
    expected_cumulative = {(c['company_id'], m) for c in registry for m in plan['cumulative_metric_ids']}
    _require(expected_cumulative == {(r['company_id'], r['metric_id']) for r in plan['cumulative_vnext_result_keys']},
             'R4 cumulative public coordinates differ')
    return requirement, plan, registry, specs, tasks, spec_paths, expected


def _verified_r3_plan(view):
    """R3 is a generic portable publication, not the R2 zero-AI wrapper."""
    from .publication import INTERNAL_AUTHORITY_ROOT, INTERNAL_CLOSURE_MANIFEST
    closure = strict_json_loads(text=view.read_bytes(relative_path=INTERNAL_CLOSURE_MANIFEST).decode())
    _require(closure['authority_root'] == INTERNAL_AUTHORITY_ROOT, 'R3 portable authority root differs')
    relative = INTERNAL_AUTHORITY_ROOT + '/config/release_plans/issue_15_lodging_r3.json'
    plan = strict_json_loads(text=view.read_bytes(relative_path=relative).decode())
    _require(plan['record_type'] == 'ISSUE_15_RELEASE_PLAN'
             and plan['release_plan_id'] == 'issue_15_lodging_r3', 'R3 predecessor plan subtype differs')
    return plan


def _credit(plan, summary, replay, mode):
    """Early exact aggregate gates before source work, Runs or staging writes."""
    _self_id(plan, 'pending_plan_id')
    _self_id(summary, 'summary_id')
    _self_id(replay, 'replay_id')
    live = mode == 'LIVE'
    expected_mode = 'LIVE' if live else 'RECORDED_TEST'
    _require(mode in {'LIVE', 'RECORDED_REHEARSAL'}, 'Unknown R4 release mode')
    _require(plan['record_type'] == ('R4_PENDING_LIVE_PLAN' if live else 'R4_RECORDED_TEST_PLAN')
             and plan['execution_mode'] == summary['execution_mode'] == replay['execution_mode'] == expected_mode,
             'Recorded execution cannot acquire LIVE publication credit')
    _require(len(plan['entries']) == 12 and len({e['entry_id'] for e in plan['entries']}) == 12
             and summary['pending_plan_id'] == replay['pending_plan_id'] == plan['pending_plan_id']
             and replay['summary_id'] == summary['summary_id']
             and summary['status'] == ('PASSED_PENDING_INDEPENDENT_REPLAY' if live else 'PASSED_RECORDED_ONLY')
             and summary['qualification_credit'] == ('PENDING_INDEPENDENT_REPLAY' if live else 'NONE_RECORDED_TEST')
             and replay['status'] == 'PASSED'
             and replay['qualification_credit'] == ('EXACT_PLAN_LIVE_QUALIFICATION_ONLY' if live else 'NONE_RECORDED_TEST')
             and replay['replayed_run_count'] == 15 and replay['scoped_run_count'] == 12
             and replay['structured_run_count'] == 3 and replay['verified_fixture_count'] == 16
             and len(summary['terminal_ids']) == len(set(summary['terminal_ids'])) == 12
             and len(summary['structured_terminal_ids']) == len(set(summary['structured_terminal_ids'])) == 3
             and summary['counters'] == {'real_model_provider_egress_count': 12 if live else 0,
                 'paid_model_provider_call_count': 12 if live else 0,
                 'mock_transport_invocation_count': 0 if live else 12}
             and summary['sec_calls'] == 0 and replay['provider_paid_sec_calls'] == [0, 0, 0]
             and plan['response_reuse_authorized'] is False and summary['response_reuse_authorized'] is False
             and summary['publication_credit'] == replay['publication_credit'] == 'NONE',
             'R4 release needs the complete independently replayed exact twelve-call aggregate')


class R4ReleaseContext:
    """Private immutable-source interpretation plus its exact eligibility graph."""
    __slots__ = ('_factory', '_root', '_execution', '_requirement', '_plan', '_registry', '_specs',
        '_tasks', '_spec_paths', '_expected', '_production', '_period', '_predecessor', '_proof_bytes',
        '_input_pins', '_pending', '_summary', '_replay', '_mode', '_read_only', '_activation', '_owner')

    def __init__(self, *, factory, root, execution, authority, pending, summary, replay,
                 mode, production, period, predecessor, proof, pins, read_only, activation, owner):
        _require(factory is _FACTORY, 'Release context requires the repository factory')
        self._factory, self._root, self._execution = factory, root, execution
        (self._requirement, self._plan, self._registry, self._specs,
         self._tasks, self._spec_paths, self._expected) = authority
        self._production, self._period, self._predecessor = production, period, predecessor
        self._pending, self._summary, self._replay, self._mode = pending, summary, replay, mode
        self._proof_bytes, self._input_pins = canonical_json_bytes(value=proof), pins
        self._read_only, self._activation, self._owner = read_only, activation, owner

    @property
    def root(self): return self._root
    @property
    def requirement(self): return _plain(self._requirement)
    @property
    def release_plan(self): return _plain(self._plan)
    @property
    def registry(self): return _plain(self._registry)
    @property
    def specs(self): return _plain(self._specs)
    @property
    def expected_keys(self): return _plain(self._expected)
    @property
    def target_period(self): return _plain(self._period)
    @property
    def predecessor(self): return self._predecessor
    @property
    def mode(self): return self._mode
    @property
    def proof(self): return strict_json_loads(text=self._proof_bytes.decode())
    @property
    def release_context_id(self): return self.proof['release_context_id']
    @property
    def production_runs(self):
        return [{**_plain({k: v for k, v in row.items() if k != 'run_dir'}),
                 'run_dir': row['run_dir']} for row in self._production]

    def _check(self):
        _require(self._factory is _FACTORY, 'Release context factory differs')
        if self._mode == 'RECORDED_REHEARSAL' and not self._read_only:
            _safe_rehearsal_root(self._root)
        self._execution._check()
        for relative, expected in self._input_pins.items():
            _require(_binding(_file(self._root, relative)) == expected, 'Release input drift: ' + relative)
        selected = [{key: row[key] for key in ('company_id', 'metric_id', 'fixture_id', 'run_path')}
                    for row in sorted(self._production, key=lambda row: (row['company_id'], row['metric_id']))]
        _require(selected == self.proof['production_selection'], 'Release production selection changed')
        from .r4_live_qualification import _structured_terminals, _validated_terminal, _execution_summary
        structured = _structured_terminals(context=self._execution, plan=self._pending)
        terminals = [_validated_terminal(context=self._execution, plan=self._pending,
            entry=entry, require_success=True) for entry in self._pending['entries']]
        _require(_execution_summary(context=self._execution, plan=self._pending,
            terminals=terminals, structured=structured) == self._summary,
            'Aggregate changed after independent qualification replay')
        _credit(self._pending, self._summary, self._replay, self._mode)


def validate_r4_release_context(context):
    _require(type(context) is R4ReleaseContext and context._factory is _FACTORY,
             'Caller mapping is not an R4 release capability')
    context._check()
    return context


def _construct(*, root, pending, replay, mode, activation=None, implementation=None, owner=None,
               portable=None, recorded_proof=None):
    from .r4_live_authority import RUNTIME_ROOT, prepare_r4_execution_context, validate_r4_live_authorization_receipt
    from .r4_live_qualification import replay_r4_qualification
    root = root.resolve(strict=True)
    read_only = portable is _PORTABLE
    _require(portable is None or read_only, 'Invalid portable release context')
    if mode == 'RECORDED_REHEARSAL' and not read_only: _safe_rehearsal_root(root)
    started = (recorded_proof['validation_started_at_utc'] if read_only
               else datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'))
    from .canonical import parse_utc_timestamp
    parse_utc_timestamp(value=started)
    source_commit = (recorded_proof['source_commit'] if read_only else
                     _git(root, 'rev-parse', 'HEAD') if mode == 'LIVE' else 'RECORDED_VNEXT_NO_SOURCE_COMMIT')
    authority = _release_authority(root, pending['requirement_id'])
    requirement, release, registry, specs, tasks, spec_paths, expected = authority
    _require(pending['requirement_id'] == requirement['requirement_id']
             and pending['requirement_closure_hash'] == requirement['requirement_closure_hash']
             and pending['requirement_hashes'] == requirement['hashes'], 'R4 pending plan Requirement differs')
    namespace = RUNTIME_ROOT + '/' + _oid(pending['pending_plan_id'])
    summary = _json(root, namespace + '/execution_summary.json')
    _credit(pending, summary, replay, mode)
    implementation_proof = None
    if mode == 'LIVE':
        if not read_only:
            _require(root == REPOSITORY_ROOT.resolve(), 'LIVE release requires the implementation repository')
        _require(activation is not None and owner is not None and implementation is not None,
                 'Live release requires transition, merged implementation and owner live receipts')
        validate_r4_live_authorization_receipt(receipt=owner, plan=pending, requirement=requirement,
            exact_head=owner['exact_head'], exact_tree=owner['exact_tree'])
        if read_only:
            validate_transition_activation_receipt(receipt=activation, requirement=requirement,
                exact_head=activation.get('exact_head'))
            implementation_proof = recorded_proof['implementation']
            _require(implementation_proof['commit'] == implementation
                     and implementation_proof['approved_head'] == activation['exact_head'],
                     'Portable merged implementation/activation differs')
        else:
            implementation_proof = _merged_implementation(root, requirement, activation, implementation, owner)
            _git(root, 'merge-base', '--is-ancestor', implementation, pending['implementation_head'])
            _git(root, 'merge-base', '--is-ancestor', pending['implementation_head'], owner['exact_head'])
            _require(_git(root, 'rev-parse', pending['implementation_head'] + '^{tree}')
                     == pending['implementation_tree'], 'Pending implementation tree differs')
    execution = prepare_r4_execution_context(repo_root=root, requirement_id=requirement['requirement_id'])
    computed = replay_r4_qualification(repo_root=root, plan=pending, context=execution)
    _require(computed == replay, 'Release aggregate receipt differs from independent native disk replay')
    # The fresh execution context already opened and fully verified R3/R2/R1.
    # Pin that exact manifest; never repeat portable R3 replay for each layer.
    execution._check()
    parent_binding = execution._historical_proof['chain'][0]['manifest']
    parent_path = _file(root, parent_binding['path'])
    _require(_binding(parent_path) == {k: parent_binding[k] for k in ('sha256', 'size')},
             'Already verified R3 manifest bytes changed')
    parent_manifest = strict_json_file(path=parent_path)
    predecessor = PublicationView(publication_id=parent_manifest['publication_id'],
        bundle_dir=parent_path.parent, manifest=parent_manifest)
    _require(predecessor.publication_id == requirement['effective_decisions']['S-PUBLICATION-PREDECESSOR']['choice']['required_predecessor']
             and predecessor.publication_id == summary['active_publication_id'] == replay['active_publication_id'],
             'R4 release predecessor is not exact active R3')
    predecessor_plan = _verified_r3_plan(predecessor)
    _require(predecessor_plan['release_plan_content_id'] == release['parent_release_plan_content_id']
             and predecessor_plan['release_plan_id'] == release['parent_release_plan_id'],
             'R4 release parent plan differs from immutable R3')
    definitions = {row['fixture_id']: row for row in execution._session._authority['fixtures']}
    scoped = {entry['fixture_id']: entry for entry in pending['entries'] if entry['fixture_execution_ordinal'] == 1}
    production = []
    release_path = 'config/release_plans/' + release['release_plan_id'] + '.json'
    activation_path = 'docs/evidence/' + requirement['requirement_id'] + '_transition_activation.json'
    pins = {release_path: _binding(_file(root, release_path)),
            namespace + '/execution_summary.json': _binding(_file(root, namespace + '/execution_summary.json'))}
    if mode == 'LIVE':
        pins[activation_path] = _binding(_file(root, activation_path))
    from .live_scoped_reader import build_scoped_invocation_acceptance_context
    from .r4_structured_run import prepare_r4_structured_run_context
    from .run_store import load_frozen_run
    # Every scoped terminal must refer to this one owner receipt; child FROZEN
    # state cannot substitute a different authorization for the aggregate.
    for entry in pending['entries']:
        run_path = namespace + '/entries/' + _oid(entry['entry_id']) + '/run'
        manifest = _json(root, run_path + '/manifest.json')
        bound = manifest['r4_execution_binding']['artifact_files']['authorization_binding']
        path = _file(root, run_path + '/' + bound['path'])
        _require(_binding(path) == {k: bound[k] for k in ('sha256', 'size')},
                 'Native Run authorization binding bytes differ')
        authorization = strict_json_file(path=path)
        _require(authorization['owner_receipt'] == owner
                 and authorization['owner_receipt_id'] == (None if owner is None else owner['receipt_id']),
                 'Aggregate scoped terminal owner authority differs')
    for fixture in definitions.values():
        if fixture['fixture_class'] != 'POSITIVE_PRODUCTION': continue
        if fixture['artifact_kind'] == 'SCOPED_EXTRACTION':
            entry = scoped.get(fixture['fixture_id'])
            _require(entry is not None, 'Production scoped fixture is absent from the base ordinals')
            relative = namespace + '/entries/' + _oid(entry['entry_id']) + '/run'
            native = build_scoped_invocation_acceptance_context(
                request=execution._requests[fixture['fixture_id']], execution_context=execution)
        elif fixture['artifact_kind'] == 'STRUCTURED_PRIMARY':
            relative = namespace + '/structured/' + fixture['fixture_id'] + '/run'
            native = prepare_r4_structured_run_context(repo_root=root, fixture_id=fixture['fixture_id'],
                plan=pending, execution_context=execution)
        else:
            raise R4ReleaseError('Production fixture has an unknown native artifact kind')
        manifest, records, decisions = load_frozen_run(run_dir=root / relative, repo_root=root, r4_replay_context=native)
        results = [r for r in records if r['record_type'] == 'METRIC_RESULT']
        _require(len(results) == 1 and results[0]['metric_id'] == fixture['metric_id']
                 and results[0]['spec_closure_hash'] == specs[fixture['metric_id']]['spec_closure_hash']
                 and results[0]['applicability'] == 'APPLICABLE' and results[0]['publication'] == 'PUBLISHED',
                 'Production Result differs from the successor MetricSpec')
        production.append({'company_id': manifest['company_id'], 'metric_id': fixture['metric_id'],
            'fixture_id': fixture['fixture_id'], 'run_dir': root / relative,
            'run_path': relative, 'manifest': manifest, 'records': records, 'decisions': decisions})
        pins[relative + '/manifest.json'] = _binding(root / relative / 'manifest.json')
    public = {(row['company_id'], row['metric_id']) for row in expected if row['applicability'] == 'APPLICABLE'}
    _require(len(production) == len(public) == 6
             and {(r['company_id'], r['metric_id']) for r in production} == public,
             'Public production selection is missing/duplicated or contains a fixture issuer')
    periods = {canonical_json_bytes(value=row['manifest']['target_period']) for row in production}
    _require(len(periods) == 1, 'Public production Run periods differ')
    period = strict_json_loads(text=next(iter(periods)).decode())
    body = {'record_type': 'R4_RELEASE_CONTEXT', 'schema_version': 1,
        'artifact_requirement_generation': EXPLICIT_ARTIFACT_GENERATION,
        'requirement_id': requirement['requirement_id'], 'requirement_closure_hash': requirement['requirement_closure_hash'],
        'requirement_hashes': requirement['hashes'], 'release_mode': mode,
        'validation_started_at_utc': started, 'source_commit': source_commit,
        'release_plan_id': release['release_plan_id'], 'release_plan_content_id': release['release_plan_content_id'],
        'pending_plan_id': pending['pending_plan_id'], 'summary_id': summary['summary_id'], 'replay_id': replay['replay_id'],
        'transition_activation_receipt_id': None if activation is None else activation['receipt_id'],
        'owner_live_receipt_id': None if owner is None else owner['receipt_id'],
        'implementation': implementation_proof, 'predecessor_publication_id': predecessor.publication_id,
        'expected_result_keys': expected, 'target_period': period,
        'spec_bindings': {metric: {'path': spec_paths[metric], **_binding(_file(root, spec_paths[metric])),
            'spec_closure_hash': specs[metric]['spec_closure_hash'], 'task_contract_hash': tasks[metric]['catalog_task_contract_hash']}
            for metric in sorted(specs)},
        'registry_binding': _binding(_file(root, 'config/company_registry.csv')),
        'production_selection': [{k: r[k] for k in ('company_id', 'metric_id', 'fixture_id', 'run_path')}
            for r in sorted(production, key=lambda r: (r['company_id'], r['metric_id']))],
        'scoped_terminal_ids': summary['terminal_ids'], 'structured_terminal_ids': summary['structured_terminal_ids'],
        'qualification_credit': 'EXACT_PLAN_LIVE_QUALIFICATION_ONLY' if mode == 'LIVE' else 'NONE_RECORDED_REHEARSAL',
        'publication_credit': 'ELIGIBLE_PENDING_RELEASE_OWNER_AUTHORIZATION' if mode == 'LIVE' else 'NONE_RECORDED_REHEARSAL',
        'response_reuse_authorized': False}
    proof = {**body, 'release_context_id': content_hash(value=body)}
    if read_only:
        _require(proof == recorded_proof, 'Portable release context rederivation differs')
    context = R4ReleaseContext(factory=_FACTORY, root=root, execution=execution, authority=authority,
        pending=pending, summary=summary, replay=replay, mode=mode, production=production,
        period=period, predecessor=predecessor, proof=proof, pins=pins, read_only=read_only,
        activation=activation, owner=owner)
    return validate_r4_release_context(context)


def prepare_r4_release_context(*, repo_root: Path, plan_id: str, replay_id: str, implementation_commit: str):
    """LIVE staging factory: no caller-selected Requirement, plan or policy map."""
    from .r4_live_authority import RUNTIME_ROOT
    root = repo_root.resolve(strict=True)
    plan = _json(root, RUNTIME_ROOT + '/plans/' + _oid(plan_id) + '.json')
    activation = _json(root, 'docs/evidence/' + plan['requirement_id'] + '_transition_activation.json')
    replay = _json(root, RUNTIME_ROOT + '/replays/' + _oid(replay_id) + '.json')
    _require(plan['pending_plan_id'] == plan_id and replay['replay_id'] == replay_id, 'Plan/replay file identity differs')
    first = plan['entries'][0]
    run_path = RUNTIME_ROOT + '/' + _oid(plan_id) + '/entries/' + _oid(first['entry_id']) + '/run'
    manifest = _json(root, run_path + '/manifest.json')
    bound = manifest['r4_execution_binding']['artifact_files']['authorization_binding']
    binding = _json(root, run_path + '/' + bound['path'])
    owner = _json(root, RUNTIME_ROOT + '/authorizations/' + _oid(binding['owner_receipt_id']) + '.json')
    return _construct(root=root, pending=plan, replay=replay, mode='LIVE',
                      activation=activation, implementation=implementation_commit, owner=owner)


def _prepare_recorded_release_context(*, repo_root: Path, plan: Mapping, replay: Mapping):
    """Explicit no-credit test entrypoint; never exposed as a CLI mode."""
    return _construct(root=_safe_rehearsal_root(repo_root), pending=_plain(plan),
                      replay=_plain(replay), mode='RECORDED_REHEARSAL')


def _read_portable_release_context(*, repo_root, document):
    """Read-only closure interpretation: never a staging/switch capability.

    Publication identity and the exact file census bind this captured graph.
    A real switch independently checks current Git and freshly read owner
    evidence; a portable snapshot is not an authentication oracle.
    """
    _require(set(document) == {'proof', 'pending_plan', 'replay', 'activation', 'owner'},
             'Portable release context exact fields differ')
    proof = document['proof']
    _self_id(proof, 'release_context_id')
    implementation = proof['implementation']
    return _construct(root=repo_root, pending=document['pending_plan'], replay=document['replay'],
        mode=proof['release_mode'], activation=document['activation'], owner=document['owner'],
        implementation=None if implementation is None else implementation['commit'],
        portable=_PORTABLE, recorded_proof=proof)


def _portable_context_document(context):
    validate_r4_release_context(context)
    return _plain({'proof': context.proof, 'pending_plan': context._pending, 'replay': context._replay,
                   'activation': context._activation, 'owner': context._owner})
