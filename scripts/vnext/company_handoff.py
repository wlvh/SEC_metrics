"""Source-only company export and recoverable installation at a stable path."""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import shutil
from uuid import uuid4

from sec_http import parse_request_log_rows, write_immutable_bytes
from .canonical import canonical_json_bytes, content_hash, sha256_file, strict_json_file
from .normal_source_authority import ROOT, MANIFEST_PATH, _baseline_file
from .ordinary_source_authority import checkpoint_installation
from .company_source_authority import EXPORT_PATH, RECORD_TYPE, need
from .sources import resolve_repository_file

PACKAGE_FILE = 'company-source-package.json'
# These are saved processing inputs, never program rules or SEC originals.
# The paths belong to #28's EXPORT_PATHS and #47's existing read interfaces.
PROCESSING_STATE_PATHS = frozenset({
    'config/ordinary_capacity_assessment.json',
    'config/ordinary_going_concern_assessment.json',
    'config/issue47_historical_going_concern_assessment.json',
    'config/issue47_historical_ma_confirmation.json',
    'config/issue47_historical_legal_review.json',
})


def external(path):
    """Reject aliases, overlap with the program and production workspaces."""
    from git_workspace import first_symlink_in_path
    path = Path(path)
    need(path.is_absolute() and first_symlink_in_path(path=path) is None,
         'COMPANY_HANDOFF_ABSOLUTE_NONALIAS_PATH_REQUIRED')
    path = path.resolve()
    need(path != ROOT and ROOT not in path.parents and path not in ROOT.parents,
         'COMPANY_HANDOFF_PROGRAM_PATH_OVERLAP')
    need(not any((p/'outputs/active_publication.json').exists()
                 for p in (path, *path.parents)), 'COMPANY_HANDOFF_ACTIVE_ROOT_FORBIDDEN')
    return path


def binding(path):
    return {'sha256': sha256_file(path=path), 'size': path.stat().st_size}


def rule_bindings(requirement_id='issue_28_v13'):
    """One authoritative rule version, copied from the installed runtime."""
    paths = {p.relative_to(ROOT).as_posix()
             for directory in ('config', 'catalog')
             for p in (ROOT/directory).rglob('*') if p.is_file()
             and p.relative_to(ROOT).as_posix() not in {EXPORT_PATH, *PROCESSING_STATE_PATHS}}
    need(requirement_id in {'issue_28_v13', 'issue_47_v1'},
         'COMPANY_HANDOFF_RULE_REQUIREMENT_UNSUPPORTED')
    authority = strict_json_file(path=ROOT/'requirements'/requirement_id/'baseline_manifest.json')
    # Approved root-level business definitions are rule inputs too. Frozen
    # receipts and old Requirement snapshots stay in the fixed runtime.
    paths.update(p for p in authority['execution_authority']['files']
                 if '/' not in p and not p.endswith('.py'))
    need(not set(authority['execution_authority']['files']) & PROCESSING_STATE_PATHS,
         'COMPANY_HANDOFF_PROCESSING_STATE_CLASSIFIED_AS_RULE')
    return {relative: binding(ROOT/relative) for relative in sorted(paths)}


def export_company(*, source_root, output_root, trust_root, company_id,
                   metric_ids=None, declared_frame=None):
    """Verify the full original history, export sources and install trust.

    Call this on the controlled preparation side. It never calculates metrics,
    reads AI answers, fetches SEC, or duplicates an acquisition allowance.
    Historical consumers supply their own validated declared_frame callable.
    """
    from git_workspace import first_symlink_in_path
    source = Path(source_root)
    need(source.is_absolute() and first_symlink_in_path(path=source) is None,
         'COMPANY_HANDOFF_SOURCE_ALIAS')
    source = source.resolve()
    output, trust = external(output_root), external(trust_root)
    need(not output.exists(), 'COMPANY_HANDOFF_OUTPUT_EXISTS')
    need(source != output and source not in output.parents and output not in source.parents,
         'COMPANY_HANDOFF_SOURCE_OUTPUT_OVERLAP')
    need(trust != output and trust not in output.parents and output not in trust.parents,
         'COMPANY_HANDOFF_TRUST_PACKAGE_OVERLAP')
    from .normal_source_requirements import discover_saved_source_requirements
    from .normal_run_v3 import update_metric_ids
    metrics = sorted(update_metric_ids() if metric_ids is None else metric_ids)
    need(metrics and len(metrics) == len(set(metrics))
         and set(metrics) <= set(update_metric_ids()), 'COMPANY_HANDOFF_METRIC_SCOPE_INVALID')
    # Existing installed journal, not a checkpoint nominated by the source,
    # authorizes every appended row before any company bytes are omitted.
    original, _ = checkpoint_installation(source_root=source)
    baseline = strict_json_file(path=ROOT/MANIFEST_PATH)
    if original is None:
        for relative in ('config/company_registry.csv', 'evidence/requests_log.csv',
                         'evidence/requests_log_manifest.json'):
            _baseline_file(source, relative, baseline)
    discovery = (discover_saved_source_requirements(repo_root=source, company_id=company_id)
                 if declared_frame is None else declared_frame(source, company_id))
    requirements = discovery['requirements']
    urls = {row['source_url'] for row in requirements}
    # Keep target captures outside the current window too. They belong to
    # this company's history, including failed requests and predecessor URLs.
    if original and original['record_type'] == 'ORDINARY_SEC_ACQUISITION_CHECKPOINT':
        urls.update(c['receipt']['ledger_row']['source_url']
                    for c in original['captures'] if c['receipt']['company_id'] == company_id)
    rows = parse_request_log_rows(text=(source/'evidence/requests_log.csv').read_text())
    paths = {'config/company_registry.csv', 'evidence/requests_log.csv',
             'evidence/requests_log_manifest.json'}
    for row in rows:
        if row['source_url'] in urls:
            paths.update(row[field] for field in ('repo_relative_path', 'headers_repo_relative_path')
                         if row[field] and (source/row[field]).is_file())
    # Registered event completeness also reads authenticated saved header
    # census. Resolve its company CIK roles from the registry, not substrings.
    from .traits import repository_company_ciks
    ciks = {int(cik) for cik in repository_company_ciks(repo_root=source, company_id=company_id)}
    headers = source/'evidence/accession_materials'
    if headers.is_dir():
        for directory in headers.iterdir():
            fields = directory.name.rsplit('_', 2)
            if directory.is_dir() and len(fields) == 3 and fields[1].isdigit() and int(fields[1]) in ciks:
                paths.update(p.relative_to(source).as_posix() for p in directory.glob('*.hdr.sgml'))
    # The header census can include prior/window-external documents. Carry
    # their own ledger-referenced HTTP headers and all attempts too.
    urls.update(row['source_url'] for row in rows if row['repo_relative_path'] in paths)
    for row in rows:
        if row['source_url'] in urls:
            paths.update(row[field] for field in ('repo_relative_path', 'headers_repo_relative_path')
                         if row[field] and (source/row[field]).is_file())
    files = {}
    for relative in sorted(paths):
        path = resolve_repository_file(repo_root=source, repo_relative_path=relative)
        if original is None:
            _baseline_file(source, relative, baseline)
        elif relative in baseline['files']:
            # A refreshed metadata attempt may replace a baseline working
            # locator. Its actual immutable row is authoritative instead.
            if relative in baseline['files'] and relative not in {
                    'evidence/requests_log.csv', 'evidence/requests_log_manifest.json'}:
                _baseline_file(source, relative, baseline)
        files[relative] = binding(path)
    rule_requirement_id = 'issue_28_v13' if declared_frame is None else 'issue_47_v1'
    rule_files = rule_bindings(rule_requirement_id)
    credit = ('PREEXISTING_SAVED_ACQUISITIONS_ONLY' if original is None else original['source_credit'])
    original_id = None if original is None else original['checkpoint_id']
    history = None
    if original and original['record_type'] == 'ORDINARY_SEC_ACQUISITION_CHECKPOINT':
        intent = original['captures'][0]['intent']
        history = intent.get('binding_id', intent.get('allowance_binding_id'))
        need(history is not None, 'COMPANY_HANDOFF_ORIGINAL_HISTORY_ID_MISSING')
    elif original:
        history = original['session']['record_id']
    body = {'record_type': RECORD_TYPE, 'schema_version': 1, 'company_id': company_id,
        'metric_ids': metrics, 'period_scope': discovery.get('discovery_scope', 'DECLARED_HISTORY'),
        'baseline_manifest_sha256': sha256_file(path=ROOT/MANIFEST_PATH),
        'ledger_sha256': files['evidence/requests_log.csv']['sha256'],
        'source_urls': sorted(urls), 'files': files, 'rules': rule_files,
        'rule_requirement_id': rule_requirement_id,
        'source_history_id': history, 'original_checkpoint_id': original_id,
        'original_checkpoint': original, 'source_credit': credit,
        'real_sec_credit': False if original is None else original['real_sec_credit'],
        'production_authorized': False}
    checkpoint = {**body, 'checkpoint_id': content_hash(value=body)}
    staged = output.parent/('.'+output.name+'.preparing-'+uuid4().hex)
    staged.mkdir(parents=True)
    try:
        for relative in sorted(set(files) | set(rule_files)):
            origin = source if relative in files else ROOT
            raw = resolve_repository_file(repo_root=origin, repo_relative_path=relative).read_bytes()
            target = staged/relative; target.parent.mkdir(parents=True, exist_ok=True)
            write_immutable_bytes(path=target, content=raw)
        write_immutable_bytes(path=staged/EXPORT_PATH, content=canonical_json_bytes(value=checkpoint))
        metadata = {'record_type': 'COMPANY_SOURCE_PACKAGE_V1', 'checkpoint_id': checkpoint['checkpoint_id'],
            'company_id': company_id, 'source_discovery': discovery,
            'ai_processing_state': 'NOT_INCLUDED', 'metric_execution': 'NOT_EXECUTED',
            'new_business_calls': {'provider': 0, 'paid': 0, 'sec': 0},
            'sizes_bytes': {'originals': sum(v['size'] for p, v in files.items() if p.startswith('evidence/')
                and p not in {'evidence/requests_log.csv', 'evidence/requests_log_manifest.json'}),
                'ledger_and_registry': sum(v['size'] for p, v in files.items() if not p.startswith('evidence/')
                    or p in {'evidence/requests_log.csv', 'evidence/requests_log_manifest.json'}),
                'rules': sum(v['size'] for v in rule_files.values()),
                'admission': len(canonical_json_bytes(value=checkpoint))}}
        write_immutable_bytes(path=staged/PACKAGE_FILE, content=canonical_json_bytes(value=metadata))
        # Freeze the exact copied closure before enrolling it. Concurrent
        # acquisition or a changed source between hashing and copying cannot
        # publish an unusable or partly updated package as verified.
        from .company_source_authority import _validate_admission_bytes
        _validate_admission_bytes(staged, checkpoint, baseline)
        for relative, declared in rule_files.items():
            need(binding(staged/relative) == declared,
                 'COMPANY_HANDOFF_RULE_CHANGED_DURING_EXPORT:'+relative)
        # Independent preparer-owned registration. Import/compute only read
        # this directory; a source package cannot install or replace it.
        trust.mkdir(parents=True, exist_ok=True)
        write_immutable_bytes(path=trust/(checkpoint['checkpoint_id'][7:]+'.json'),
                              content=canonical_json_bytes(value=checkpoint))
        os.rename(staged, output)
    except (OSError, ValueError):
        shutil.rmtree(staged)
        raise
    return metadata


@contextmanager
def locked_company(state_root):
    """Serialize import and compute on a stable directory inode."""
    root = external(state_root)
    root.mkdir(parents=True, exist_ok=True)
    fd = os.open(root, os.O_RDONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield root
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _atomic_json(path, value):
    temporary = path.with_name('.'+path.name+'.'+uuid4().hex)
    with temporary.open('xb') as stream:
        stream.write(canonical_json_bytes(value=value)); stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path)
    _sync_directory(path.parent)


def _sync_directory(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def check_package(*, package_root, company_id):
    from .company_source_authority import require_company
    package = external(package_root)
    admission = require_company(source_root=package, company_id=company_id)
    need(admission['rules'] == rule_bindings(admission.get('rule_requirement_id', 'issue_28_v13')),
         'COMPANY_HANDOFF_RULE_VERSION_CHANGED')
    metadata = strict_json_file(path=package/PACKAGE_FILE)
    need(metadata['checkpoint_id'] == admission['checkpoint_id']
         and metadata['company_id'] == company_id, 'COMPANY_HANDOFF_PACKAGE_ID_CHANGED')
    expected = set(admission['files']) | set(admission['rules']) | {EXPORT_PATH, PACKAGE_FILE}
    actual = set()
    for path in package.rglob('*'):
        need(not path.is_symlink(), 'COMPANY_HANDOFF_MEMBER_ALIAS')
        if path.is_file():
            actual.add(path.relative_to(package).as_posix())
        else:
            need(path.is_dir(), 'COMPANY_HANDOFF_SPECIAL_MEMBER')
    need(actual == expected, 'COMPANY_HANDOFF_MEMBER_SET_CHANGED')
    for relative, declared in admission['rules'].items():
        need(binding(package/relative) == declared, 'COMPANY_HANDOFF_RULE_COPY_CHANGED:'+relative)
    return admission


def recover_import(root):
    """Restore the last committed source after interruption during replacement."""
    pointer = root/'current_source.json'
    if not pointer.exists():
        # An interrupted first import has no committed source to expose.
        # Authenticate the intent and immutable version before quarantining
        # its uncommitted copy; an arbitrary preexisting directory is refused.
        if (root/'source').exists():
            need((root/'import_intent.json').is_file(), 'COMPANY_HANDOFF_UNOWNED_SOURCE_ROOT')
            intent = strict_json_file(path=root/'import_intent.json')
            version = root/'versions'/intent['checkpoint_id'][7:]
            admission = check_package(package_root=version, company_id=intent['company_id'])
            installed = check_package(package_root=root/'source', company_id=intent['company_id'])
            need(installed['checkpoint_id'] == admission['checkpoint_id'] == intent['checkpoint_id'],
                 'COMPANY_HANDOFF_UNOWNED_SOURCE_ROOT')
            os.rename(root/'source', root/('.interrupted-source-'+uuid4().hex))
            _sync_directory(root)
        return None
    current = strict_json_file(path=pointer)
    immutable = root/'versions'/current['checkpoint_id'][7:]
    need(immutable.is_dir(), 'COMPANY_HANDOFF_COMMITTED_VERSION_MISSING')
    check_package(package_root=immutable, company_id=current['company_id'])
    source = root/'source'
    same = (source/EXPORT_PATH).is_file() and strict_json_file(path=source/EXPORT_PATH)['checkpoint_id'] == current['checkpoint_id']
    if same:
        check_package(package_root=source, company_id=current['company_id'])
        return current
    staged = root/('.recovery-'+uuid4().hex)
    shutil.copytree(immutable, staged)
    if source.exists():
        os.rename(source, root/('.interrupted-source-'+uuid4().hex))
    os.rename(staged, source)
    _sync_directory(root)
    check_package(package_root=source, company_id=current['company_id'])
    return current


def install_company(*, package_root, state_root, company_id, fault=None):
    """Validate before installing; keep immutable versions and the stable root."""
    package = external(package_root)
    with locked_company(state_root) as root:
        committed_before = ((root/'current_source.json').read_bytes()
                            if (root/'current_source.json').is_file() else None)
        attempt = {'company_id': company_id, 'package_root': str(package),
                   'status': 'IN_PROGRESS'}
        _atomic_json(root/'latest_import.json', attempt)
        try:
            result = _install_locked(package, root, company_id, fault)
        except Exception as error:
            committed_after = ((root/'current_source.json').read_bytes()
                               if (root/'current_source.json').is_file() else None)
            _atomic_json(root/'latest_import.json', {**attempt, 'status': 'FAILED',
                         'error': str(error),
                         'committed_source_unchanged': committed_before == committed_after})
            raise
        _atomic_json(root/'latest_import.json', {**attempt, **result})
        return result


def _install_locked(package, root, company_id, fault):
    previous = recover_import(root)
    incoming = check_package(package_root=package, company_id=company_id)
    if previous:
        need(previous['company_id'] == company_id, 'COMPANY_HANDOFF_STATE_WRONG_COMPANY')
        old = strict_json_file(path=root/'source'/EXPORT_PATH)
        raw = (package/'evidence/requests_log.csv').read_bytes()
        need(raw.startswith((root/'source/evidence/requests_log.csv').read_bytes()),
             'COMPANY_HANDOFF_SOURCE_HISTORY_NOT_PREFIX')
        need(old['source_history_id'] is None or incoming['source_history_id'] == old['source_history_id'],
             'COMPANY_HANDOFF_UNRELATED_SOURCE_HISTORY')
        need(old['rules'] == incoming['rules'], 'COMPANY_HANDOFF_RULE_HISTORY_CHANGED')
        if old['checkpoint_id'] == incoming['checkpoint_id']:
            return {'status': 'ALREADY_INSTALLED', **previous}
    version = root/'versions'/incoming['checkpoint_id'][7:]
    if version.exists():
        check_package(package_root=version, company_id=company_id)
    else:
        staging = root/('.version-'+uuid4().hex)
        shutil.copytree(package, staging)
        check_package(package_root=staging, company_id=company_id)
        version.parent.mkdir(exist_ok=True)
        os.rename(staging, version)
    staged = root/('.source-'+uuid4().hex)
    shutil.copytree(version, staged)
    check_package(package_root=staged, company_id=company_id)
    current = {'company_id': company_id, 'checkpoint_id': incoming['checkpoint_id'],
               'source_root': str(root/'source')}
    _atomic_json(root/'import_intent.json', current)
    if fault:
        fault('before_source_replace')
    if (root/'source').exists():
        os.rename(root/'source', root/('.previous-source-'+uuid4().hex))
    if fault:
        fault('after_old_source_move')
    os.rename(staged, root/'source')
    _sync_directory(root)
    if fault:
        fault('after_new_source_move')
    _atomic_json(root/'current_source.json', current)
    return {'status': 'INSTALLED', **current}
