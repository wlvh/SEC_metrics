"""Continuity-specific source binding for the shared annual snapshot/replay chain."""
from pathlib import Path
import json
from .annual_adoption import (ROOT, need, read, record, check_id, _tree_files, historical_code,
    _ReadOnlyReplay, _FACTORY, _active, verify_saved_execution, _records, git)
from .annual_adoption_policy import V3, policy, resolve_embedded
from .canonical import content_hash, sha256_file, sha256_bytes, canonical_json_bytes
from .ratchet_release import _copy_exact_tree
from . import annual_runtime as runtime


def _selected(records, metric):
    results = [r for r in records if r['record_type'] == 'METRIC_RESULT' and r['metric_id'] == metric]
    need(len(results) == 1 and results[0]['reason_code'] == 'PASS' and results[0]['quality'] == 'EXACT'
         and results[0]['publication'] == 'PUBLISHED' and results[0]['applicability'] == 'APPLICABLE'
         and results[0]['value'] is not None, 'CONTINUITY_NATIVE_RESULT_INCOMPLETE')
    return results[0]


def seed_descriptor(*, b01, b10, data_root):
    from .run_store import _mechanically_replay_open_run
    from .ratchet_release import _committed_run_origin, _validate_committed_qualification_run
    m1, r1, _ = _mechanically_replay_open_run(run_dir=b01, repo_root=data_root, require_complete_results=True)
    origin = _committed_run_origin(repo_root=ROOT, run_dir=b10)
    m10, r10, _ = _validate_committed_qualification_run(repo_root=ROOT, run_dir=b10, origin=origin)
    selected = {'B01': _selected(r1, 'B01'), 'B10': _selected(r10, 'B10')}
    chosen = policy(policy_id=V3)
    need(m1['company_id'] == m10['company_id'] == chosen['company_id']
         and m1['target_period'] == m10['target_period'], 'CONTINUITY_SEED_PERIOD_OR_SUBJECT_CHANGED')
    return {'kind': 'EXPLICIT_ISOLATED_HISTORICAL_SEED', 'b01_directory': str(b01), 'b10_directory': str(b10),
        'b01_files': _tree_files(root=b01), 'b10_files': _tree_files(root=b10), 'b10_origin': origin,
        'period': m1['target_period'], 'selected_results_id': content_hash(value=selected),
        'original_status': {'b01': m1['status'], 'b10': m10['status']}, 'historically_published': False}


def create_seed_candidate(stage, owner):
    from . import annual_input
    from .annual_continuity import _requirement, _write_once
    root = Path(stage['stage_root']); candidate = root / 'seed-candidate'; data = root / 'seed-input'
    need(not candidate.exists() and not data.exists(), 'CONTINUITY_SEED_ALREADY_CREATED')
    descriptor = stage['seed']
    prepared = annual_input.prepare_annual_input(repo_root=Path(stage['data_root']),
        company_id=stage['policy']['company_id'], fiscal_year=descriptor['period']['fiscal_year'])
    need(prepared['table_input']['target_period'] == descriptor['period'], 'CONTINUITY_SEED_SOURCE_PERIOD_CHANGED')
    runtime._copy_inputs(source_root=Path(stage['data_root']), data_root=data, prepared=prepared, requirement=_requirement())
    for name in ('b01', 'b10'):
        source = Path(descriptor[name + '_directory'])
        need(_tree_files(root=source) == descriptor[name + '_files'], 'CONTINUITY_SEED_ORIGINAL_CHANGED')
        _copy_exact_tree(source=source, destination=candidate / name)
    _write_once(candidate / 'continuity-seed.json', {'stage': stage, 'owner_comment': owner,
        'data_root': str(data), 'prepared_input': prepared, 'seed': descriptor})
    return candidate


def _source_proof(root, context):
    from . import annual_continuity as continuity
    from .annual_continuity_sources import select_saved_input
    stage, owner = context['origin']['stage'], context['owner_comment']
    chosen = resolve_embedded(context['policy']); need(chosen['policy_id'] == V3, 'CONTINUITY_POLICY_REQUIRED')
    check_id(stage, 'stage_id'); continuity.validate_owner(stage, owner)
    need(stage['policy'] == chosen and stage['production_publication_authorized'] is False,
         'CONTINUITY_ORIGINAL_SCOPE_CHANGED')
    code = historical_code(stage)
    need(code == context['historical_code_files'], 'CONTINUITY_HISTORICAL_IMPLEMENTATION_CHANGED')
    for path, proof in context['data_files'].items():
        if path in code:need(code[path] == proof, 'CONTINUITY_SNAPSHOT_AUTHORITY_CHANGED')
    data, candidate = root / 'data', root / 'candidate'
    requirement = continuity._requirement(data)
    need(stage['requirement_closure_hash'] == requirement['requirement_closure_hash']
         and stage['requirement_id'] == requirement['requirement_id'], 'CONTINUITY_SNAPSHOT_REQUIREMENT_CHANGED')
    need(read(root, 'controls/registration.json') == stage['budget_registration'], 'CONTINUITY_REGISTRATION_CHANGED')
    if context['kind'] == 'HISTORICAL_SEED':
        seed = read(candidate, 'continuity-seed.json')
        need(seed['stage'] == stage and seed['owner_comment'] == owner and seed['seed'] == stage['seed'],
             'CONTINUITY_SEED_DESCRIPTOR_CHANGED')
        from . import annual_input
        prepared = annual_input.prepare_annual_input(repo_root=data, company_id=chosen['company_id'],
            fiscal_year=stage['seed']['period']['fiscal_year'])
        need(prepared == seed['prepared_input'], 'CONTINUITY_SEED_INPUT_CHANGED')
        for name in ('b01', 'b10'):
            need(_tree_files(root=candidate / name) == stage['seed'][name + '_files'], 'CONTINUITY_SEED_RUN_CHANGED')
        origin = stage['seed']['b10_origin']; relative = origin['run_path']
        paths = git('ls-tree', '-r', '--name-only', origin['commit'], '--', relative).decode().splitlines()
        committed = {p[len(relative)+1:]: {'sha256': sha256_bytes(content=git('show', origin['commit'] + ':' + p)),
            'size': len(git('show', origin['commit'] + ':' + p))} for p in paths}
        need(committed == stage['seed']['b10_files'], 'CONTINUITY_SEED_NOT_ORIGINAL_COMMITTED_RUN')
        return requirement, None
    need(context['kind'] == 'NORMAL_EXECUTION', 'CONTINUITY_SNAPSHOT_KIND_INVALID')
    plan = context['origin']['plan'];check_id(plan, 'plan_id')
    binding = read(candidate / 'b10', 'annual_candidate_binding.json')
    need(binding == {'stage': stage, 'plan': plan, 'owner_comment': owner}
         and read(candidate, 'plan.json') == plan, 'CONTINUITY_SNAPSHOT_PLAN_CHANGED')
    visibility = plan['selection']['visibility']
    prepared, selection = select_saved_input(data, None if visibility is None else visibility['visibility'])
    need(plan == continuity._plan(stage, prepared, selection, data, plan['predecessor_pointer'], plan['ordinal'], authority_root=data),
         'CONTINUITY_SNAPSHOT_REQUEST_CHANGED')
    slot = read(root, 'controls/provider-slot.json');check_id(slot, 'slot_id')
    need(slot['plan_id'] == plan['plan_id'] and slot['stage_id'] == stage['stage_id']
         and slot['ordinal'] == plan['ordinal'] and slot['input_id'] == prepared['input_id']
         and slot['registration_id'] == stage['budget_registration']['registration_id'],
         'CONTINUITY_SNAPSHOT_SLOT_CHANGED')
    workspace, _, run_id = runtime._paths(plan)
    need(str(workspace) == context['origin']['candidate_directory'], 'CONTINUITY_SNAPSHOT_ORIGINAL_PATH_CHANGED')
    m1, m10 = (read(candidate / name, 'manifest.json') for name in ('b01', 'b10'))
    from .sources import raw_blob_record, source_reference_record
    structured = prepared['companyfacts_input']
    raw = raw_blob_record(repo_root=data, repo_relative_path=structured['source_repo_relative_path'], media_type='application/json')
    source = source_reference_record(raw_blob=raw, source_role='companyfacts', **{
        k: structured[k] for k in ('company_id','source_url','accession','document_name','request_attempt_id')})
    need(m1['run_id'] == run_id + ':structured' and m10['run_id'] == run_id
         and m1['target_period'] == m10['target_period'] == prepared['table_input']['target_period']
         and m10['source_references'] == [plan['request']['source_reference']]
         and m1['source_references'] == [source]
         and [r for r in _records(candidate / 'b01') if r['record_type'] == 'RAW_BLOB'] == [raw]
         and m10['requirement_id'] == requirement['requirement_id']
         and m10['requirement_hashes'] == requirement['hashes']
         and m10['requirement_closure_hash'] == requirement['requirement_closure_hash']
         and m10['task_contract_bindings'] == [plan['task_binding']]
         and m10.get('qualification_authorization') is None
         and m1['status'] == m10['status'] == 'OPEN'
         and m1['company_id'] == m10['company_id'] == chosen['company_id'], 'CONTINUITY_NATIVE_RUN_CHANGED')
    execution = verify_saved_execution(candidate=candidate, data_root=data, plan=plan,
        stage=stage, owner=owner, requirement=requirement, request=plan['request'])
    return requirement, execution


def replay_snapshot(root, context, *, adoption_root=ROOT):
    from .run_store import _mechanically_replay_open_run, load_run_bound_specs
    from .ratchet_release import load_portable_qualification_run
    for name in ('data', 'candidate', 'controls'):
        field = {'data': 'data_files', 'candidate': 'candidate_files', 'controls': 'control_files'}[name]
        need(_tree_files(root=root / name) == context[field], 'CONTINUITY_SNAPSHOT_FILES_CHANGED')
    requirement, execution = _source_proof(root, context)
    manifests = {name: read(root / 'candidate' / name, 'manifest.json') for name in ('b01', 'b10')}
    replay = _ReadOnlyReplay(_FACTORY, root, manifests);token = _active.set(replay)
    try:
        runs = {}
        for name in ('b01', 'b10'):
            directory = root / 'candidate' / name
            if context['kind'] == 'HISTORICAL_SEED' and name == 'b10':
                manifest, records, decisions = load_portable_qualification_run(run_dir=directory, repo_root=root / 'data')
            else:
                manifest, records, decisions = _mechanically_replay_open_run(run_dir=directory,
                    repo_root=root / 'data', require_complete_results=True)
            runs[name] = {'manifest': manifest, 'records': records, 'decisions': decisions,
                'specs': load_run_bound_specs(repo_root=root / 'data', manifest=manifest)}
    finally:
        _active.reset(token)
    selected = {metric: _selected(runs[name]['records'], metric) for metric, name in (('B01','b01'),('B10','b10'))}
    need(runs['b01']['manifest']['target_period'] == runs['b10']['manifest']['target_period'], 'CONTINUITY_COMPLETE_PERIOD_CHANGED')
    if context['kind'] == 'HISTORICAL_SEED':
        need(content_hash(value=selected) == context['origin']['stage']['seed']['selected_results_id'], 'CONTINUITY_SEED_SELECTION_CHANGED')
    identity = {k: requirement[k] for k in ('requirement_id', 'requirement_closure_hash', 'hashes')}
    need(context['adoption_requirement'] == identity, 'CONTINUITY_ADOPTION_REQUIREMENT_CHANGED')
    receipt = record({'record_type':'ANNUAL_CANDIDATE_ADOPTION_RECEIPT','schema_version':1,
        'policy_id':V3,'policy_hash':content_hash(value=context['policy']),
        'status':'VERIFIED_ISOLATED_CONTINUITY_ADOPTION','formal_publication_credit':'NONE',
        'kind':context['kind'],'original_run_status':{n:m['status'] for n,m in manifests.items()},
        'snapshot_id':content_hash(value=context),'selected_results':selected,
        'native_run_ids':{n:m['run_id'] for n,m in manifests.items()},
        'native_requirement_hashes':{n:m['requirement_hashes'] for n,m in manifests.items()},
        'preserved_unselected_results':[r['result_id'] for r in runs['b01']['records'] if r['record_type']=='METRIC_RESULT' and r['metric_id'] not in selected],
        'execution_id':None if execution is None else execution['execution_id'],
        'historical_provider_paid_sec_calls':[1,1,0], 'new_provider_paid_sec_calls':[0,0,0],
        'adoption_requirement':identity,'checks':['IMMUTABLE_SEC_SOURCE_AND_PERIOD','ORIGINAL_EXECUTION_AND_USAGE',
            'NATIVE_EVIDENCE_SYSTEM_REVIEW_CALCULATOR','EXACT_COMPLETE_SELECTED_SET','STAGE_AND_PREDECESSOR_BOUND'],
        'formal_remaining_conditions':context['policy']['formal_remaining_conditions']},'adoption_receipt_id')
    return receipt,runs,requirement


def prepare_snapshot(*, candidate_dir, output_root):
    from .annual_candidate import _github
    from .annual_continuity import _requirement, validate_owner
    candidate_dir, output_root = runtime._external(candidate_dir), runtime._external(output_root)
    need(not output_root.exists(), 'CONTINUITY_SNAPSHOT_EXISTS')
    seed = candidate_dir / 'continuity-seed.json'
    binding = read(candidate_dir, seed.name) if seed.exists() else read(candidate_dir / 'b10', 'annual_candidate_binding.json')
    stage, owner = binding['stage'], binding['owner_comment'];validate_owner(stage, owner)
    actual = _github('repos/' + stage['repository'] + '/issues/comments/' + str(owner['id']))
    actual = {**{k: actual[k] for k in ('id','html_url','issue_url','body','created_at','updated_at')}, 'user':{'login':actual['user']['login']}}
    need(actual == owner, 'CONTINUITY_SAVED_OWNER_CHANGED')
    data = Path(binding['data_root'] if seed.exists() else binding['plan']['data_root'])
    requirement = _requirement(); code = historical_code(stage)
    _copy_exact_tree(source=data, destination=output_root / 'data')
    _copy_exact_tree(source=candidate_dir, destination=output_root / 'candidate')
    controls=output_root/'controls';controls.mkdir()
    registration=Path(stage['budget_root'])/'registration.json';(controls/'registration.json').write_bytes(registration.read_bytes())
    if not seed.exists():
        slot=Path(stage['budget_root'])/('provider-'+str(binding['plan']['ordinal'])+'.json')
        (controls/'provider-slot.json').write_bytes(slot.read_bytes())
    context={'schema_version':1,'kind':'HISTORICAL_SEED' if seed.exists() else 'NORMAL_EXECUTION','policy':policy(policy_id=V3),
        'origin':{'candidate_directory':str(candidate_dir),'data_directory':str(data),'stage':stage,
                  'plan':None if seed.exists() else binding['plan']},'owner_comment':owner,'historical_code_files':code,
        'data_files':_tree_files(root=output_root/'data'),'candidate_files':_tree_files(root=output_root/'candidate'),
        'control_files':_tree_files(root=controls),'adoption_requirement':{k:requirement[k] for k in ('requirement_id','requirement_closure_hash','hashes')}}
    receipt,_,_=replay_snapshot(output_root,context)
    for name,value in [('context.json',context),('adoption.json',receipt)]:
        (output_root/name).write_bytes(canonical_json_bytes(value=value)+b'\n')
    need(_tree_files(root=candidate_dir)==context['candidate_files'] and _tree_files(root=data)==context['data_files'],
         'CONTINUITY_ORIGINAL_CHANGED_DURING_SNAPSHOT')
    return receipt
