"""Read-only historical adoption of native annual candidates, never execution.

Original Runs remain OPEN. A separate content-addressed receipt seals their
fully replayed bytes under a proposed, rehearsal-only adoption rule.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
import io
import json
import subprocess
import tarfile

from git_workspace import sanitized_git_environment
from .canonical import canonical_json_bytes, content_hash, sha256_bytes, sha256_file, strict_json_file
from .ratchet_release import _tree_files, _copy_exact_tree
from .sources import resolve_repository_file
from .annual_adoption_policy import policy, resolve_embedded, V1, V2

ROOT = Path(__file__).resolve().parents[2]
POLICY = 'config/annual_candidate_adoption_v1.json'
_FACTORY = object()
_active = ContextVar('annual_historical_read_only_replay', default=None)


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


def record(body, field):
    return {**body, field: content_hash(value=body)}


def check_id(value, field):
    need(value.get(field) == content_hash(value={k: v for k, v in value.items() if k != field}),
         'ANNUAL_ID_CHANGED: ' + field)


def read(root, path):
    return strict_json_file(path=resolve_repository_file(repo_root=root, repo_relative_path=path))


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT,
        env=sanitized_git_environment())


def historical_code(stage):
    """Read Git objects in memory; never execute a second checkout."""
    head = stage['reviewed_code']['exact_head']
    need(len(head) == 40 and all(c in '0123456789abcdef' for c in head), 'ANNUAL_REVIEW_HEAD_INVALID')
    need(git('merge-base', head, 'HEAD').decode().strip() == head, 'ANNUAL_REVIEW_NOT_ANCESTOR')
    paths = ['scripts', 'tools', 'catalog', 'config', 'requirements',
             'docs/evidence/issue_28_annual_runtime_policy.json',
             'docs/evidence/issue_28_annual_repair_policy.json']
    archive = git('archive', '--format=tar', head, *paths)
    blobs = {}
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        for member in tar:
            need(member.isdir() or member.isfile(), 'ANNUAL_HISTORICAL_CODE_ALIAS')
            if member.isfile():
                data = tar.extractfile(member).read()
                blobs[member.name] = {'sha256': sha256_bytes(content=data), 'size': len(data)}
    need(content_hash(value=blobs) == stage['reviewed_code']['runtime_tree'], 'ANNUAL_HISTORICAL_CODE_CHANGED')
    return blobs


def _source_proof(root, context):
    """Rebuild source, request and consumed controller identities from bytes."""
    from . import annual_runtime as runtime, annual_input
    from .requirements import load_requirement_snapshot
    from .requirement_profile import validate_execution_authority
    from .table_task_contracts import table_task_execution_plan
    from . import invocation_control as controller
    from .ai_adapter import _controller_usage
    data_root, candidate = root / 'data', root / 'candidate'
    binding = read(candidate / 'b10', 'annual_candidate_binding.json')
    stage, plan, owner = binding['stage'], binding['plan'], binding['owner_comment']
    check_id(stage, 'stage_id'); check_id(plan, 'plan_id')
    need(context['origin']['plan'] == plan and context['origin']['stage'] == stage
         and context['owner_comment'] == owner, 'ANNUAL_ORIGIN_BINDING_CHANGED')
    need(stage['publication_authorized'] is False and plan['publication_credit'] == 'NONE'
         and plan['qualification_credit'] == 'NONE' and stage['automatic_retry_count'] == 0,
         'ANNUAL_ORIGINAL_CREDIT_CHANGED')
    requirement = load_requirement_snapshot(snapshot_dir=data_root / 'requirements' / plan['requirement_id'])
    validate_execution_authority(repo_root=data_root, requirement=requirement)
    from .annual_repair_budget import validate_comment
    need(validate_comment(owner, repository=requirement['baseline']['repository']['identity'],
                          url=owner['html_url']) == stage, 'ANNUAL_ORIGINAL_OWNER_CHANGED')
    need(plan['requirement_hashes'] == requirement['hashes']
         and plan['requirement_closure_hash'] == stage['requirement_closure_hash'] == requirement['requirement_closure_hash']
         and stage['policy'] == requirement['effective_decisions']['S-ANNUAL-REPAIR']['choice'],
         'ANNUAL_ORIGINAL_REQUIREMENT_CHANGED')
    prepared = annual_input.prepare_annual_input(repo_root=data_root, company_id=context['policy']['company_id'])
    request = runtime._request(prepared, data_root, plan['task_contract_id'], code_root=data_root)
    need(prepared == plan['prepared_input'] and request == plan['request']
         and stage['reviewed_input_request'] == {'input_id': prepared['input_id'], 'request': request},
         'ANNUAL_INPUT_OR_REQUEST_CHANGED')
    need(table_task_execution_plan(repo_root=data_root, task_contract_id=plan['task_contract_id'])['run_binding']
         == plan['task_binding'], 'ANNUAL_TASK_CHANGED')
    for name, proof in plan['source_ledger'].items():
        p = resolve_repository_file(repo_root=data_root, repo_relative_path='evidence/' + name)
        need(sha256_file(path=p) == proof['sha256'] and p.stat().st_size == proof['size'], 'ANNUAL_SOURCE_LEDGER_CHANGED')
    original_workspace, original_run, original_run_id = runtime._paths(plan)
    need(str(original_workspace) == context['origin']['candidate_directory']
         and plan['data_root'] == context['origin']['data_directory'], 'ANNUAL_ORIGINAL_PATHS_CHANGED')
    need(read(candidate, 'plan.json') == plan, 'ANNUAL_PLAN_COPY_CHANGED')
    slot = {'stage_id': stage['stage_id'], 'plan_id': plan['plan_id']}
    need(read(root, 'controls/execution-slot.json') == slot
         and read(root, 'controls/repair-slot.json') == {**slot, 'ordinal': 1,
             'delegation_url': stage['policy']['repair_budget_delegation_url']}, 'ANNUAL_CONSUMED_SLOT_CHANGED')
    manifests = {name: read(candidate / name, 'manifest.json') for name in ('b01', 'b10')}
    from .sources import raw_blob_record, source_reference_record
    structured = prepared['companyfacts_input']
    raw = raw_blob_record(repo_root=data_root, repo_relative_path=structured['source_repo_relative_path'], media_type='application/json')
    source = source_reference_record(raw_blob=raw, source_role='companyfacts', **{
        k: structured[k] for k in ('company_id', 'source_url', 'accession', 'document_name', 'request_attempt_id')})
    structured_records = _records(candidate / 'b01')
    need(manifests['b01']['run_id'] == original_run_id + ':structured'
         and manifests['b01']['source_references'] == [source]
         and [r for r in structured_records if r['record_type'] == 'RAW_BLOB'] == [raw]
         and [r for r in structured_records if r['record_type'] == 'SOURCE_REFERENCE'] == [source],
         'ANNUAL_STRUCTURED_RUN_OR_SOURCE_CHANGED')
    need(manifests['b10']['run_id'] == original_run_id
         and manifests['b10']['requirement_hashes'] == requirement['hashes']
         and manifests['b10']['source_references'] == [request['source_reference']]
         and manifests['b10']['task_contract_bindings'] == [plan['task_binding']]
         and manifests['b10'].get('qualification_authorization') is None,
         'ANNUAL_ORIGINAL_RUN_CHANGED')
    need(all(m['company_id'] == context['policy']['company_id'] and m['status'] == 'OPEN'
             and m['target_period'] == prepared['table_input']['target_period'] for m in manifests.values()),
         'ANNUAL_RUN_SCOPE_OR_STATUS_CHANGED')
    logroot = candidate / 'invocation_control'
    plans = list((logroot / 'plans').glob('*.json'))
    need(len(plans) == 1, 'ANNUAL_INVOCATION_SET_INVALID')
    invocation = strict_json_file(path=plans[0])
    history = controller.prepare_historical_annual_invocation_view(repo_root=data_root, requirement_id=requirement['requirement_id'])
    controller.validate_ai_invocation_plan(plan=invocation, _historical_view=history)
    need(invocation['release_input_plan_id'] == plan['plan_id']
         and invocation['provider_request_body_sha256'] == request['provider_request_body_sha256']
         and invocation['source_identity_hash'] == request['reader_input_manifest_id']
         and invocation['selected_representation_hash'] == request['derived_asset_id'], 'ANNUAL_INVOCATION_CHANGED')
    execution_id = controller.execution_identity(ai_invocation_plan_id=invocation['ai_invocation_plan_id'],
        owner_token=stage['stage_id'], authorized_at_utc=owner['created_at'])
    execution = controller._load_execution_receipt(root=logroot,
        path=controller._execution_path(root=logroot, execution_id=execution_id), execution_id=execution_id)
    markers = controller._egress_markers_for_execution(root=logroot, execution_id=execution_id)
    need(len(list((logroot / 'executions').glob('*.json'))) == len(markers) == len(execution['attempts']) == 1
         and execution['status'] == execution['attempts'][0]['status'] == 'SUCCEEDED'
         and execution['counters'] == controller._counters_from_egress_markers(markers=markers, plan=invocation)
         and execution['counters'] == {'real_model_provider_egress_count': 1,
             'paid_model_provider_call_count': 1, 'mock_transport_invocation_count': 0}, 'ANNUAL_EXECUTION_NOT_ACCEPTED')
    attempts = [r for r in _records(candidate / 'b10') if r['record_type'] == 'AI_EXTRACTION_ATTEMPT']
    need(len(attempts) == 1 and attempts[0]['status'] == 'SUCCEEDED', 'ANNUAL_ATTEMPT_NOT_ACCEPTED')
    attempt = attempts[0]
    raw = resolve_repository_file(repo_root=candidate / 'b10', repo_relative_path=attempt['raw_response_path']).read_bytes()
    need(not runtime.prior.usage_error(raw), 'ANNUAL_USAGE_NOT_ACCEPTED')
    success = controller.load_successful_response(workspace_dir=candidate, plan=invocation, _historical_view=history)
    need(success['provider_request_id'] == attempt['provider_request_id']
         and sha256_bytes(content=success['response_body']) == attempt['assistant_output_sha256']
         and execution['attempts'][0]['usage'] == _controller_usage(raw_response_bytes=raw),
         'ANNUAL_RESPONSE_EXECUTION_CHANGED')
    return manifests, requirement, execution


def _records(directory):
    from .run_store import _read_jsonl
    return _read_jsonl(path=directory / 'records.jsonl')


class _ReadOnlyReplay:
    def __init__(self, factory, root, manifests):
        need(factory is _FACTORY, 'ANNUAL_READ_ONLY_FACTORY_REQUIRED')
        self.root = root
        self.manifests = manifests
        self.records = {name: _records(root / 'candidate' / name) for name in manifests}


def validate_historical_run_binding(*, repo_root, run_dir, manifest, records):
    """Only the native read-side qualification dispatcher may use this context."""
    context = _active.get()
    if context is None:
        return False
    need(type(context) is _ReadOnlyReplay and repo_root == context.root / 'data'
         and run_dir == context.root / 'candidate/b10'
         and manifest == context.manifests['b10'] and records == context.records['b10'],
         'ANNUAL_READ_ONLY_CONTEXT_SUBSTITUTION')
    return True


def replay_snapshot(root, context, *, policy_id=None, adoption_root=ROOT):
    """Run every native OPEN graph gate without writing a validation or Run."""
    from .run_store import _mechanically_replay_open_run
    from .run_store import load_run_bound_specs
    need(_tree_files(root=root / 'data') == context['data_files']
         and _tree_files(root=root / 'candidate') == context['candidate_files']
         and _tree_files(root=root / 'controls') == context['control_files'], 'ANNUAL_SNAPSHOT_BYTES_CHANGED')
    chosen = resolve_embedded(context['policy'])
    need(policy_id in (None, chosen['policy_id']), 'ANNUAL_ADOPTION_POLICY_MIXED')
    need(content_hash(value=context['historical_code_files'])
         == context['origin']['stage']['reviewed_code']['runtime_tree'], 'ANNUAL_HISTORICAL_CODE_MAP_CHANGED')
    for path, proof in context['data_files'].items():
        if path in context['historical_code_files']:
            need(context['historical_code_files'][path] == proof, 'ANNUAL_HISTORICAL_AUTHORITY_CHANGED')
    manifests, requirement, execution = _source_proof(root, context)
    replay = _ReadOnlyReplay(_FACTORY, root, manifests)
    token = _active.set(replay)
    try:
        runs = {}
        for name in ('b01', 'b10'):
            manifest, records, decisions = _mechanically_replay_open_run(run_dir=root / 'candidate' / name,
                repo_root=root / 'data', require_complete_results=True)
            runs[name] = {'manifest': manifest, 'records': records, 'decisions': decisions,
                         'specs': load_run_bound_specs(repo_root=root / 'data', manifest=manifest)}
    finally:
        _active.reset(token)
    selected = {}
    for metric_id, name in (('B01', 'b01'), ('B10', 'b10')):
        results = [r for r in runs[name]['records'] if r['record_type'] == 'METRIC_RESULT' and r['metric_id'] == metric_id]
        need(len(results) == 1 and results[0]['quality'] == 'EXACT' and results[0]['publication'] == 'PUBLISHED'
             and results[0]['applicability'] == 'APPLICABLE' and results[0]['value'] is not None,
             'ANNUAL_SELECTED_RESULT_NOT_COMPLETE')
        selected[metric_id] = results[0]
    receipt = record({'record_type': 'ANNUAL_CANDIDATE_ADOPTION_RECEIPT', 'schema_version': 1,
        'policy_id': context['policy']['policy_id'], 'policy_hash': content_hash(value=context['policy']),
        'status': 'PASSED_ISOLATED_ADOPTION', 'formal_publication_credit': 'NONE',
        'original_run_status': {name: m['status'] for name, m in manifests.items()},
        'snapshot_id': content_hash(value=context), 'selected_results': selected,
        'native_run_ids': {name: m['run_id'] for name, m in manifests.items()},
        'native_requirement_hashes': {name: m['requirement_hashes'] for name, m in manifests.items()},
        'preserved_unselected_results': [r['result_id'] for r in runs['b01']['records']
            if r['record_type'] == 'METRIC_RESULT' and r['metric_id'] not in selected],
        'execution_id': execution['execution_id'], 'historical_provider_paid_sec_calls': [1, 1, 0],
        'new_provider_paid_sec_calls': [0, 0, 0],
        'checks': ['ORIGINAL_EXECUTION_AND_USAGE', 'IMMUTABLE_SOURCE_AND_LEDGER', 'ORIGINAL_REQUIREMENT_AND_SPEC',
                   'COMPLETE_NATIVE_GRAPH_REPLAY', 'EVIDENCE_REVIEW_CALCULATOR', 'EXACT_SELECTED_RESULT_SET'],
        'formal_remaining_conditions': context['policy']['formal_remaining_conditions']}, 'adoption_receipt_id')
    if chosen['policy_id'] == V2:
        from .requirements import load_requirement_snapshot
        from .requirement_profile import validate_execution_authority
        exact = chosen['exact_candidate']
        need(content_hash(value=context['candidate_files']) == exact['file_set_id']
             and context['origin']['plan']['plan_id'] == exact['original_plan_id']
             and receipt['native_run_ids'] == exact['native_run_ids']
             and receipt['execution_id'] == exact['execution_id']
             and content_hash(value=selected) == exact['selected_results_id']
             and content_hash(value=context['origin']['plan']['prepared_input']['source_proofs']) == exact['source_proofs_id'],
             'ANNUAL_EXACT_ADOPTION_CANDIDATE_CHANGED')
        review = chosen['content_review']
        path = resolve_repository_file(repo_root=adoption_root, repo_relative_path=review['path'])
        need(sha256_file(path=path) == review['sha256'] and path.stat().st_size == review['size'],
             'ANNUAL_CONTENT_REVIEW_CHANGED')
        requirement = load_requirement_snapshot(snapshot_dir=adoption_root / 'requirements' / chosen['adoption_requirement_id'])
        validate_execution_authority(repo_root=adoption_root, requirement=requirement)
        need(requirement['adoption_policy'] == chosen, 'ANNUAL_ADOPTION_REQUIREMENT_POLICY_CHANGED')
        identity = {k: requirement[k] for k in ('requirement_id', 'requirement_closure_hash', 'hashes')}
        need(context['adoption_requirement'] == identity, 'ANNUAL_ADOPTION_REQUIREMENT_CHANGED')
        body = {k: v for k, v in receipt.items() if k != 'adoption_receipt_id'}
        body.update(status='VERIFIED_CANDIDATE_SPECIFIC_ADOPTION', formal_publication_credit='PENDING_EXTERNAL_AUTHORITY',
            adoption_requirement=identity, content_review=review)
        receipt = record(body, 'adoption_receipt_id')
    return receipt, runs, requirement


def prepare_snapshot(*, candidate_dir, output_root, policy_id=V1):
    """Capture source identities and a real saved approval, then replay offline."""
    from .annual_runtime import _external
    candidate_dir, output_root = _external(candidate_dir), _external(output_root)
    need(not output_root.exists(), 'ANNUAL_ADOPTION_OUTPUT_EXISTS')
    chosen_policy = policy(policy_id=policy_id)
    if policy_id == V2:
        need(content_hash(value=_tree_files(root=candidate_dir)) == chosen_policy['exact_candidate']['file_set_id'],
             'ANNUAL_EXACT_ADOPTION_CANDIDATE_CHANGED')
    binding = read(candidate_dir / 'b10', 'annual_candidate_binding.json')
    stage, plan = binding['stage'], binding['plan']
    owner = binding['owner_comment']
    need(type(owner.get('id')) is int and owner['id'] > 0, 'ANNUAL_ORIGINAL_OWNER_ID_INVALID')
    code_files = historical_code(stage)
    data_root = _external(Path(plan['data_root']))
    originals = _tree_files(root=data_root)
    for path, proof in originals.items():
        if path in code_files:
            need(code_files[path] == proof, 'ANNUAL_FROZEN_CODE_OR_RULE_CHANGED: ' + path)
    from .requirements import load_requirement_snapshot
    historical_requirement = load_requirement_snapshot(snapshot_dir=data_root / 'requirements' / plan['requirement_id'])
    repository = historical_requirement['baseline']['repository']['identity']
    # Read the original consumed approval; this creates no new permission.
    from .annual_candidate import _github
    actual = _github('repos/' + repository + '/issues/comments/' + str(owner['id']))
    need(actual == owner, 'ANNUAL_ORIGINAL_OWNER_COMMENT_CHANGED')
    need(stage['policy']['company_id'] == chosen_policy['company_id']
         and plan['requirement_id'] in chosen_policy['candidate_requirement_ids'], 'ANNUAL_UNSUPPORTED_CANDIDATE')
    _copy_exact_tree(source=data_root, destination=output_root / 'data')
    _copy_exact_tree(source=candidate_dir, destination=output_root / 'candidate')
    controls = output_root / 'controls'; controls.mkdir()
    stage_root = _external(Path(stage['stage_root']))
    for source, name in [(stage_root / 'execution-slot.json', 'execution-slot.json'),
        (stage_root.parents[1] / 'repair-slot-1.json', 'repair-slot.json')]:
        need(source.is_file() and not source.is_symlink(), 'ANNUAL_ORIGIN_CONTROL_ABSENT')
        (controls / name).write_bytes(source.read_bytes())
    context = {'schema_version': 1, 'policy': chosen_policy,
        'origin': {'candidate_directory': str(candidate_dir), 'data_directory': str(data_root),
                   'stage': stage, 'plan': plan}, 'owner_comment': owner,
        'historical_code_files': code_files,
        'data_files': _tree_files(root=output_root / 'data'),
        'candidate_files': _tree_files(root=output_root / 'candidate'),
        'control_files': _tree_files(root=controls)}
    if policy_id == V2:
        requirement = load_requirement_snapshot(snapshot_dir=ROOT / 'requirements' / chosen_policy['adoption_requirement_id'])
        context['adoption_requirement'] = {k: requirement[k] for k in ('requirement_id', 'requirement_closure_hash', 'hashes')}
    receipt, _runs, _requirement = replay_snapshot(output_root, context, policy_id=policy_id)
    (output_root / 'context.json').write_bytes(canonical_json_bytes(value=context) + b'\n')
    (output_root / 'adoption.json').write_bytes(canonical_json_bytes(value=receipt) + b'\n')
    need(_tree_files(root=candidate_dir) == context['candidate_files'] and _tree_files(root=data_root) == originals,
         'ANNUAL_ORIGINAL_CHANGED_DURING_READ')
    return receipt
