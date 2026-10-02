"""Install a deterministic, separately bound company computing runtime.

Original #28 files/snapshots stay untouched. The small dispatch changes below
are applied only to a fresh runtime tree and included in its own Requirement.
This supports a read-only program image and a separate persistent trust volume.
"""
import difflib
from pathlib import Path
import shutil
import subprocess

from .canonical import canonical_json_bytes, content_hash, strict_json_file
from .company_handoff import binding, external, PROCESSING_STATE_PATHS
from .company_source_authority import need
from .normal_source_authority import ROOT

SUCCESSOR_MODULES = ('company_source_authority', 'company_handoff',
                     'company_requirement', 'company_runtime_install', 'company_compute',
                     'company_result_export', 'company_historical_compute',
                     'company_result_view', 'company_result_read',
                     'company_processing', 'company_processing_read', 'company_worker_guard')


def _replace(path, old, new, count=1):
    text = path.read_text()
    need(text.count(old) == count, 'COMPANY_RUNTIME_UPSTREAM_SEAM_CHANGED:'+str(path))
    path.write_text(text.replace(old, new))


def install_runtime(*, output_root, kind='baseline'):
    """Install fixed source/rules and a new identity; do not re-sign old Runs."""
    output = external(output_root)
    need(not output.exists(), 'COMPANY_RUNTIME_OUTPUT_EXISTS')
    need(kind in {'baseline', 'ordinary', 'native', 'historical'}, 'COMPANY_RUNTIME_KIND_INVALID')
    parent_id = {'historical': 'issue_47_v1', 'native': 'issue_28_v14'}.get(kind, 'issue_28_v13')
    requirement_id = {'historical': 'issue_54_v3', 'native': 'issue_54_v2'}.get(kind, 'issue_54_v1')
    from .annual_runtime import _authority_files
    from .annual_continuity_sources import frozen_foundation_receipts
    from .requirements import load_requirement_snapshot
    from .requirement_profile_v1 import PROFILE_SNAPSHOT_FILES
    if kind == 'historical':
        # Register its lazy loader in this installation process only. Validate
        # the original unpatched tree before applying #47's supplied patch.
        from .requirement_profile import PROFILE_ENGINES
        PROFILE_ENGINES['PROFILE_DRIVEN_V16'] = '.requirement_profile_v16'
    parent = load_requirement_snapshot(snapshot_dir=ROOT/'requirements'/parent_id)
    from .requirement_profile_v1 import validate_execution_authority
    validate_execution_authority(repo_root=ROOT, requirement=parent)
    paths = set(_authority_files(parent))
    need(not paths & PROCESSING_STATE_PATHS,
         'COMPANY_RUNTIME_PROCESSING_STATE_CLASSIFIED_AS_RULE')
    cursor = parent
    while cursor:
        paths.update(cursor.get('execution_authority', {}).get('files', {}))
        paths.update(cursor.get('baseline', {}).get('new_rule_files', {}))
        cursor = cursor.get('parent_snapshot')
    for directory in ('scripts', 'tools', 'requirements', 'catalog', 'config'):
        paths.update(p.relative_to(ROOT).as_posix() for p in (ROOT/directory).rglob('*')
                     if p.is_file() and '__pycache__' not in p.parts)
    # Some native consumers read the approved business definition at the
    # repository root. It is a rule input, not a home-directory dependency.
    for manifest_path in (ROOT/'requirements').glob('*/baseline_manifest.json'):
        raw_manifest = strict_json_file(path=manifest_path)
        declared = set(raw_manifest.get('execution_authority', {}).get('files', {}))
        declared.update(raw_manifest.get('new_rule_files', {}))
        paths.update(p for p in declared if not p.endswith('.py') and (ROOT/p).is_file())
    paths.difference_update(PROCESSING_STATE_PATHS)
    index = strict_json_file(path=ROOT/'docs/evidence/issue28_continuous/frozen-parent-v10-index.json')
    paths.update('docs/evidence/issue28_continuous/frozen-parent-v10/'+p for p in index['files'])
    receipts = frozen_foundation_receipts()
    for relative in sorted(paths):
        target = output/relative; target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(receipts[relative]['bytes'] if relative in receipts else (ROOT/relative).read_bytes())
    need(not (output/'evidence').exists(), 'COMPANY_RUNTIME_WOULD_INSTALL_SEC_ORIGINALS')
    if kind == 'baseline':
        # Baseline source proofs and installation already work without core
        # changes. Keep that route available instead of forcing a successor.
        _commit_runtime(output, 'Install unchanged ordinary baseline runtime')
        return {'status': 'RUNTIME_INSTALLED', 'runtime_root': str(output),
                'requirement_id': parent_id, 'dispatch_files': [],
                'sec_originals_installed': False, 'new_business_calls': [0, 0, 0],
                'production_authorized': False}
    upstream_modified = ()
    if kind == 'historical':
        patches = list((ROOT/'docs/evidence/issue47_history').glob(
            'native-run-*/0001-register-issue47-v1.patch'))
        need(len(patches) == 1, 'COMPANY_RUNTIME_HISTORY_REGISTRATION_PATCH_AMBIGUOUS')
        upstream = patches[0]
        patch_text = upstream.read_text()
        subprocess.run(['git', 'apply', str(upstream)], cwd=output, check=True, capture_output=True)
        upstream_modified = tuple(line.split(' b/', 1)[1] for line in patch_text.splitlines()
                                  if line.startswith('diff --git '))
        (output/'company-history-upstream-registration.patch').write_text(patch_text)
    run_module = 'historical_run' if kind == 'historical' else 'normal_run_v3'
    modified = ('scripts/vnext/requirement_profile.py', 'scripts/vnext/run_store.py',
                'scripts/vnext/'+run_module+'.py', 'scripts/vnext/ordinary_source_authority.py',
                'scripts/vnext/records.py')
    originals = {p: (output/p).read_text() for p in modified}
    _replace(output/modified[0], 'PROFILE_ENGINES = {',
             'PROFILE_ENGINES = {\n    "COMPANY_SEPARATION_V1": ".company_requirement",')
    # This fixed tree computes new company Runs. Old Runs keep their own
    # installed ordinary runtime and Requirement; no mixed-generation tree.
    old_id = '"'+parent_id+'"'
    count = (output/modified[1]).read_text().count(old_id)
    need(count > 0, 'COMPANY_RUNTIME_UPSTREAM_RUN_DISPATCH_MISSING')
    _replace(output/modified[1], old_id, '"'+requirement_id+'"', count=count)
    _replace(output/modified[2], 'REQUIREMENT_ID = "'+('issue_28_v13' if kind == 'native' else parent_id)+'"',
             'REQUIREMENT_ID = "'+requirement_id+'"')
    # The manifest's coordinate validator independently owns fiscal labels.
    # Register the new runtime there as well, including non-calendar years.
    record_id = '"issue_28_v13"' if kind == 'native' else old_id
    record_count = (output/modified[4]).read_text().count(record_id)
    need(record_count > 0, 'COMPANY_RUNTIME_UPSTREAM_COORDINATE_DISPATCH_MISSING')
    _replace(output/modified[4], record_id, '"'+requirement_id+'"', count=record_count)
    if kind == 'native':
        native_literal = "'issue_28_v14'"
        native_count = (output/modified[2]).read_text().count(native_literal)
        need(native_count > 0, 'COMPANY_RUNTIME_UPSTREAM_NATIVE_REPLAY_MISSING')
        _replace(output/modified[2], native_literal, "'"+requirement_id+"'", count=native_count)
        _replace(output/modified[1], '"issue_28_v12", "issue_28_v13"}',
                 '"issue_28_v12", "issue_28_v13", "'+requirement_id+'"}')
        capacity = 'scripts/vnext/capacity_run.py'
        originals[capacity] = (output/capacity).read_text()
        _replace(output/capacity, 'from .continuous_call_policy import REQUIREMENT_ID',
                 'REQUIREMENT_ID = "'+requirement_id+'"')
        controller = 'scripts/vnext/ordinary_update_cycle.py'
        originals[controller] = (output/controller).read_text()
        _replace(output/controller, 'from .continuous_call_policy import REQUIREMENT_ID',
                 'from .capacity_run import REQUIREMENT_ID', count=2)
        modified = (*modified, capacity, controller)
    _replace(output/modified[3], 'def _validate_checkpoint(data_root,checkpoint,baseline):\n',
             'def _validate_checkpoint(data_root,checkpoint,baseline):\n'
             '    if checkpoint.get("record_type") == "COMPANY_SOURCE_ADMISSION_V1":\n'
             '        from .company_source_authority import validate_checkpoint\n'
             '        return validate_checkpoint(data_root,checkpoint,baseline)\n')
    _replace(output/modified[3], 'def _trusted_checkpoint(data_root):\n',
             'def _trusted_checkpoint(data_root):\n'
             '    exported = data_root/EXPORT_PATH\n'
             '    if exported.is_file() and strict_json_file(path=exported).get("record_type") == "COMPANY_SOURCE_ADMISSION_V1":\n'
             '        from .company_source_authority import trusted_checkpoint\n'
             '        return trusted_checkpoint(data_root)\n')
    _replace(output/modified[3], "acquired=checkpoint.get('record_type')=='ORDINARY_SEC_ACQUISITION_CHECKPOINT'",
             "acquired=(checkpoint.get('record_type')=='ORDINARY_SEC_ACQUISITION_CHECKPOINT'\n"
             "              or checkpoint.get('record_type')=='COMPANY_SOURCE_ADMISSION_V1'\n"
             "              and (checkpoint.get('original_checkpoint') or {}).get('record_type')=='ORDINARY_SEC_ACQUISITION_CHECKPOINT')")
    _replace(output/modified[3], '_,_,admitted=_validate_checkpoint(source_root,checkpoint,baseline);paths=set()',
             '_,_,admitted=_validate_checkpoint(source_root,checkpoint,baseline);paths=set()\n'
             '    if checkpoint.get("record_type") == "COMPANY_SOURCE_ADMISSION_V1":\n'
             '        return checkpoint,set(checkpoint["files"])')
    patch = ''.join(''.join(difflib.unified_diff(originals[p].splitlines(True),
        (output/p).read_text().splitlines(True), fromfile='a/'+p, tofile='b/'+p)) for p in modified)
    (output/'company-runtime-dispatch.patch').write_text(patch)
    snapshot = output/'requirements'/requirement_id; snapshot.mkdir()
    authority = {**parent['execution_authority'], 'files': dict(parent['execution_authority']['files'])}
    for relative in (*modified, *upstream_modified, 'tools/vnext_company.py',
                     *('scripts/vnext/'+m+'.py' for m in SUCCESSOR_MODULES)):
        authority['files'][relative] = binding(output/relative)
    frozen_parent = 'docs/evidence/issue54_runtime/frozen-parent-requirement.json'
    (output/frozen_parent).parent.mkdir(parents=True, exist_ok=True)
    (output/frozen_parent).write_bytes(canonical_json_bytes(value=parent))
    authority['files'][frozen_parent] = binding(output/frozen_parent)
    baseline = {'record_type': 'REQUIREMENT_BASELINE_MANIFEST', 'schema_version': 1,
        'requirement_id': requirement_id, 'requirement_generation': 'COMPANY_SEPARATION_V1',
        'artifact_requirement_generation': 'EXPLICIT_REQUIREMENT_V1',
        'production_authorized': False, 'new_rule_files': {},
        'parent': {'requirement_id': parent_id,
            'requirement_closure_hash': parent['requirement_closure_hash'],
            'loaded_snapshot': {'path': frozen_parent, **binding(output/frozen_parent)},
            'snapshot_files': {name: binding(ROOT/'requirements'/parent_id/name)
                               for name in sorted(PROFILE_SNAPSHOT_FILES)}},
        'validator': {'path': 'scripts/vnext/company_requirement.py',
                      **binding(output/'scripts/vnext/company_requirement.py'),
                      'dependencies': ['scripts/vnext/requirement_profile_v1.py', 'scripts/vnext/canonical.py']},
        'execution_authority': authority}
    files = {'baseline_manifest.json': baseline,
        'decision_register.json': {'status': 'USER_DELEGATED_DEVELOPMENT_ONLY',
            'delegation_url': 'https://github.com/wlvh/SEC_metrics/issues/54',
            'new_business_calls': [0, 0, 0], 'production_authorized': False},
        'transfer_manifest.json': {'parent_requirement_id': parent_id,
            'parent_requirement_closure_hash': parent['requirement_closure_hash'],
            'disposition': 'CARRY_ALL_PARENT_OBLIGATIONS_WITHOUT_ACTIVATION',
            'pending_decision_ids': parent['pending_decision_ids']},
        'invariant_profile.json': {**parent['evaluated_invariants'],
            'company_scope_admission': True, 'separate_installed_trust': True}}
    for name, value in files.items():
        (snapshot/name).write_bytes(canonical_json_bytes(value=value))
    (snapshot/'CONTRACT.md').write_text('# Company separation runtime v1\n\n'
        'Inherit '+parent_id+' business semantics and all parent obligations.\n'
        'Verify complete source histories on the preparation side; computing consumes only the company admission.\n'
        'Independent installed trust owns admission. Original ledgers, old Runs and closed budgets are unchanged.\n'
        'No new SEC/provider/paid calls, activation, publication or deployment authority.\n')
    # Existing installation reads committed historical receipts and a tracked
    # rule inventory. The runtime Git directory is immutable during compute.
    _commit_runtime(output, 'Install fixed company computation runtime v1')
    return {'status': 'RUNTIME_INSTALLED', 'runtime_root': str(output),
        'requirement_id': requirement_id, 'dispatch_files': list(modified),
        'authority_hash': content_hash(value=authority), 'sec_originals_installed': False,
        'new_business_calls': [0, 0, 0], 'production_authorized': False}


def _commit_runtime(output, message):
    subprocess.run(['git', 'init', '-q', str(output)], check=True, capture_output=True)
    subprocess.run(['git', 'add', '.'], cwd=output, check=True, capture_output=True)
    subprocess.run(['git', '-c', 'user.name=Codex', '-c', 'user.email=codex@openai.com',
                    'commit', '-qm', message],
                   cwd=output, check=True, capture_output=True)
