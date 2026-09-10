"""Stage-bound plans using the existing publication permission and switch journal."""
from pathlib import Path
from .annual_adoption import ROOT, need, read, record, check_id, _tree_files
from .annual_adoption_policy import V3, CONTINUITY_CREDIT, policy
from .canonical import content_hash, sha256_file
from . import annual_publication as annual, annual_publication_authority as authority, publication as pub

PLAN_TYPE = 'CONTINUITY_PUBLICATION_PLAN'


def initialize(*, publication_root, approval_url):
    from .annual_continuity import verify_stage
    binding = verify_stage(approval_url=approval_url);stage=binding['stage']
    root=annual.safe_root(publication_root)
    need(str(root)==stage['publication_root'], 'CONTINUITY_PUBLICATION_ROOT_CHANGED')
    if (root/'annual_publication_workspace.json').exists():
        return marker(root)
    need(not root.exists() or not any(root.iterdir()), 'CONTINUITY_PUBLICATION_ROOT_NOT_EMPTY')
    view=pub.PublicationView.open(publication_root=ROOT)
    need(read(ROOT,'outputs/active_publication.json')==stage['initial_publication_pointer'], 'CONTINUITY_INITIAL_PUBLICATION_CHANGED')
    from .ratchet_release import _copy_exact_tree
    root.mkdir(parents=True,exist_ok=True)
    _copy_exact_tree(source=view.bundle_dir,destination=root/'outputs/publications'/view.publication_id)
    _copy_exact_tree(source=ROOT/'outputs/publication_switch_receipts',destination=root/'outputs/publication_switch_receipts')
    for name in ('active_publication.json','active_publication.json.lock'):
        (root/'outputs'/name).write_bytes((ROOT/'outputs'/name).read_bytes())
    for source,target in pub.ROOT_MIRROR_RELATIVE_PATHS.items():
        path=root/target;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(view.read_bytes(relative_path=source))
    value=record({'schema_version':2,'purpose':'ISOLATED_ANNUAL_CONTINUITY','publication_root':str(root),
        'official_root':str(ROOT),'formal_publication_authorized':False,'stage_id':stage['stage_id'],
        'stage_root':stage['stage_root'],'budget_root':stage['budget_root'],'policy_id':V3,
        'predecessor_publication_id':view.publication_id,
        'predecessor_manifest_sha256':sha256_file(path=view.bundle_dir/'publication_manifest.json')},'workspace_id')
    (root/'annual_publication_workspace.json').write_bytes(annual.json_bytes(value))
    return value


def marker(root):
    root=annual.safe_root(root);value=read(root,'annual_publication_workspace.json');check_id(value,'workspace_id')
    need(value['schema_version']==2 and value['purpose']=='ISOLATED_ANNUAL_CONTINUITY'
         and value['publication_root']==str(root) and value['official_root']==str(ROOT)
         and value['formal_publication_authorized'] is False and value['policy_id']==V3,
         'CONTINUITY_PUBLICATION_MARKER_CHANGED')
    return value


def _binding(directory, manifest, meta, adoption):
    context=read(directory,annual.SNAPSHOT+'/context.json')
    return {'publication_id':manifest['publication_id'],'manifest_sha256':sha256_file(path=directory/'publication_manifest.json'),
        'adoption_receipt_id':adoption['adoption_receipt_id'],'source_snapshot_id':adoption['snapshot_id'],
        'candidate_file_set_id':content_hash(value=context['candidate_files']),'native_run_ids':adoption['native_run_ids'],
        'original_execution_id':adoption['execution_id'],'selected_results_id':content_hash(value=adoption['selected_results']),
        'policy_id':V3,'policy_hash':content_hash(value=meta['policy']),'requirement_id':manifest['requirement_id'],
        'requirement_closure_hash':manifest['requirement_closure_hash'],'requirement_hashes':manifest['requirement_hashes']}


def plan(*, bundle_dir, approval_url):
    from .annual_continuity import verify_stage
    signed=verify_stage(approval_url=approval_url);stage=signed['stage'];root=Path(stage['publication_root']);marker(root)
    manifest=pub.verify_publication_bundle(bundle_dir=bundle_dir)
    need(manifest['publication_credit']==CONTINUITY_CREDIT, 'CONTINUITY_PUBLICATION_POLICY_REQUIRED')
    meta=read(bundle_dir,annual.META);adoption=read(bundle_dir,annual.SNAPSHOT+'/adoption.json');context=read(bundle_dir,annual.SNAPSHOT+'/context.json')
    need(context['origin']['stage']==stage and context['owner_comment']==signed['owner_comment'], 'CONTINUITY_PUBLICATION_STAGE_CHANGED')
    pointer=read(root,'outputs/active_publication.json')
    need(pointer['publication_id']==manifest['previous_publication_id'], 'CONTINUITY_PUBLICATION_PREDECESSOR_CHANGED')
    return record({'schema_version':1,'record_type':PLAN_TYPE,'stage':stage,'stage_approval_url':approval_url,
        'target_root':str(root),'environment':'ISOLATED_TEST','bundle_directory':str(bundle_dir),
        'code':authority._code(meta['implementation_head']),'binding':_binding(bundle_dir,manifest,meta,adoption),
        'predecessor':{'publication_id':pointer['publication_id'],'manifest_sha256':pointer['bundle_manifest_sha256']},
        'predecessor_pointer':pointer,'operations':stage['policy']['operations'],'new_provider_paid_sec_calls':[0,0,0],
        'kind':context['kind']},'plan_id')


def validate_plan(value):
    from .annual_continuity import validate_stage
    check_id(value,'plan_id');stage=value['stage'];requirement=validate_stage(stage)
    root=annual.safe_root(Path(value['target_root']));mark=marker(root)
    need(value['record_type']==PLAN_TYPE and value['schema_version']==1 and value['environment']=='ISOLATED_TEST'
         and str(root)==stage['publication_root'] and mark['stage_id']==stage['stage_id']
         and value['stage_approval_url'].startswith('https://github.com/'+stage['repository']+'/')
         and value['operations']==stage['policy']['operations'] and value['new_provider_paid_sec_calls']==[0,0,0],
         'CONTINUITY_PUBLICATION_SCOPE_CHANGED')
    directory=annual.safe_root(Path(value['bundle_directory']));manifest=pub.verify_publication_bundle(bundle_dir=directory)
    need(manifest['publication_credit']==CONTINUITY_CREDIT, 'CONTINUITY_PUBLICATION_CREDIT_CHANGED')
    meta=read(directory,annual.META);adoption=read(directory,annual.SNAPSHOT+'/adoption.json');context=read(directory,annual.SNAPSHOT+'/context.json')
    need(context['origin']['stage']==stage and context['kind']==value['kind']
         and value['binding']==_binding(directory,manifest,meta,adoption)
         and value['code']==authority._code(meta['implementation_head'])
         and value['code']['test_tree']==stage['reviewed_code']['test_tree'], 'CONTINUITY_PUBLICATION_BINDING_CHANGED')
    authority._same_implementation(value['code'],authority.git('rev-parse','HEAD').decode().strip())
    pointer=value['predecessor_pointer'];previous=value['predecessor']
    need(pointer['publication_id']==manifest['previous_publication_id']==previous['publication_id']
         and pointer['bundle_manifest_sha256']==previous['manifest_sha256']==meta['predecessor_manifest_sha256'],
         'CONTINUITY_PUBLICATION_EDGE_CHANGED')
    if value['kind']=='NORMAL_EXECUTION':
        need(context['origin']['plan']['predecessor_pointer']==pointer, 'CONTINUITY_INPUT_PREDECESSOR_CHANGED')
    else:
        need(value['kind']=='HISTORICAL_SEED' and pointer==stage['initial_publication_pointer'], 'CONTINUITY_SEED_PREDECESSOR_CHANGED')
    return root,manifest,requirement


def verify_authorization(*, plan, activation_url, owner_url, allow_expired_recovery=False):
    from .annual_continuity import verify_stage, validate_owner
    need(activation_url==owner_url==plan['stage_approval_url'], 'CONTINUITY_SINGLE_STAGE_APPROVAL_REQUIRED')
    signed=verify_stage(approval_url=owner_url,execution=not allow_expired_recovery)
    need(signed['stage']==plan['stage'], 'CONTINUITY_PUBLICATION_APPROVAL_CHANGED')
    root,manifest,requirement=validate_plan(plan)
    activation=record({'record_type':'ISOLATED_CONTINUITY_STAGE_ACTIVATION','stage_id':signed['stage']['stage_id'],
        'requirement_id':requirement['requirement_id'],'requirement_closure_hash':requirement['requirement_closure_hash'],
        'owner_comment':signed['owner_comment'],'production_authorized':False},'activation_id')
    return authority.PublicationPermission(factory=authority._FACTORY,binding={'plan':plan,'activation':activation,
        'owner':signed['owner_comment'],'pull':None,'manifest':manifest})


def live_guard(binding, operation, action):
    if binding['plan'].get('record_type')!=PLAN_TYPE:
        return
    from .annual_continuity import validate_stage
    stage=binding['plan']['stage']
    if operation=='recover':
        # An expired grant may finish only an already reserved in-window edge.
        from .canonical import parse_utc_timestamp
        need(parse_utc_timestamp(value=stage['created_at_utc']) <= parse_utc_timestamp(value=action['committed_at_utc'])
             <= parse_utc_timestamp(value=stage['expires_at_utc']), 'CONTINUITY_RECOVERY_OUTSIDE_ORIGINAL_WINDOW')
        validate_stage(stage)
    else:
        validate_stage(stage,execution=True)
