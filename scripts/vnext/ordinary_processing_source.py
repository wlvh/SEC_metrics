"""Build a current-rule processing copy from an authenticated old source root.

The acquisition ledger and its source bytes remain untouched. This is a
private, content-addressed input copy for ordinary Runs, not another SEC
ledger, a new source authority, or a publication root.
"""
import os
import json
from pathlib import Path
from uuid import uuid4

from sec_http import write_immutable_bytes

from .canonical import content_hash, sha256_file, strict_json_file
from .continuous_sec_acquisition import (initialize_source_inputs,
                                         _clone_or_copy_source)
from .normal_annual_input_v2 import POLICY_PATH as FISCAL_POLICY_PATH
from .normal_run_v3 import _external, _policy
from .normal_source_authority import ROOT, MANIFEST_PATH
from .ordinary_source_authority import EXPORT_PATH, checkpoint_installation
from .requirement_profile import validate_execution_authority
from .sources import resolve_repository_file


RECORD = 'ISSUE28_CURRENT_PROCESSING_SOURCE_SNAPSHOT_V1'
META = 'ordinary-processing-source-snapshot.json'


def _need(ok, reason):
    if not ok:
        raise ValueError(reason)


def _identity(*, source_root, requirement, checkpoint):
    ledger = sha256_file(path=resolve_repository_file(
        repo_root=source_root, repo_relative_path='evidence/requests_log.csv'))
    body = {'record_type': RECORD, 'source_ledger_sha256': ledger,
        'source_checkpoint_id': None if checkpoint is None else checkpoint['checkpoint_id'],
        'requirement_id': requirement['requirement_id'],
        'requirement_closure_hash': requirement['requirement_closure_hash'],
        'source_baseline_manifest_sha256': sha256_file(path=ROOT/MANIFEST_PATH)}
    return {**body, 'snapshot_id': content_hash(value=body)}


def _check_copy(*, root, identity, checkpoint, requirement):
    _need(root.is_dir() and strict_json_file(path=resolve_repository_file(
              repo_root=root, repo_relative_path=META)) == identity,
          'ORDINARY_PROCESSING_SNAPSHOT_ID_CHANGED')
    _need(strict_json_file(path=resolve_repository_file(repo_root=root,
              repo_relative_path='source-baseline.json')) == {
                  'baseline_manifest_sha256': sha256_file(path=ROOT/MANIFEST_PATH)},
          'ORDINARY_PROCESSING_SNAPSHOT_BASELINE_CHANGED')
    _need(sha256_file(path=root/'evidence/requests_log.csv') ==
          identity['source_ledger_sha256'],
          'ORDINARY_PROCESSING_SNAPSHOT_LEDGER_CHANGED')
    selected, _ = checkpoint_installation(source_root=root)
    _need((None if selected is None else selected['checkpoint_id']) ==
          identity['source_checkpoint_id'],
          'ORDINARY_PROCESSING_SNAPSHOT_SOURCE_CHECKPOINT_CHANGED')
    _policy(root)
    parent = requirement['parent_snapshot']
    presentation = set(parent['policy']['presentation_paths'])
    for relative, binding in parent['execution_authority']['files'].items():
        if relative in presentation or not relative.startswith(('config/', 'catalog/')):
            continue
        path = resolve_repository_file(repo_root=root,
                                       repo_relative_path=relative)
        _need({'sha256': sha256_file(path=path), 'size': path.stat().st_size}
              == binding,
              'ORDINARY_PROCESSING_SNAPSHOT_RULE_CHANGED:' + relative)
    _need(sha256_file(path=resolve_repository_file(repo_root=root,
          repo_relative_path=FISCAL_POLICY_PATH)) ==
          sha256_file(path=ROOT/FISCAL_POLICY_PATH),
          'ORDINARY_PROCESSING_SNAPSHOT_FISCAL_RULE_CHANGED')
    return root


def verify_processing_source(*, acquisition_root, processing_root, requirement):
    """Bind a completed copy to the current original source ledger."""
    source = _external(Path(acquisition_root))
    copy = _external(Path(processing_root))
    _need(source != copy and source not in copy.parents
          and copy not in source.parents,
          'ORDINARY_PROCESSING_SOURCE_OUTPUT_OVERLAP')
    validate_execution_authority(repo_root=ROOT, requirement=requirement)
    checkpoint, _ = checkpoint_installation(source_root=source)
    identity = _identity(source_root=source,
                         requirement=requirement, checkpoint=checkpoint)
    _need(copy.name == identity['snapshot_id'][7:],
          'ORDINARY_PROCESSING_SNAPSHOT_PATH_CHANGED')
    _check_copy(root=copy, identity=identity, checkpoint=checkpoint,
                requirement=requirement)
    return identity


def current_processing_source(*, acquisition_root, output_parent, requirement):
    """Copy the verified source ledger into a current-rule private input root.

    Caller must hold the acquisition ledger lock when freshness matters.
    A later caller still checks its original ledger identity before granting
    an update-current result; this copy alone gives no execution credit.
    """
    source = _external(Path(acquisition_root))
    parent = _external(Path(output_parent))
    _need(parent != source and parent not in source.parents
          and source not in parent.parents,
          'ORDINARY_PROCESSING_SOURCE_OUTPUT_OVERLAP')
    validate_execution_authority(repo_root=ROOT, requirement=requirement)
    checkpoint, paths = checkpoint_installation(source_root=source)
    identity = _identity(source_root=source,
                         requirement=requirement, checkpoint=checkpoint)
    key = identity['snapshot_id'][7:]
    parent.mkdir(parents=True, exist_ok=True)
    destination = parent/key
    if destination.exists():
        return {'data_root': _check_copy(root=_external(destination),
            identity=identity, checkpoint=checkpoint,
            requirement=requirement),
            'snapshot_id': identity['snapshot_id'], 'reused': True,
            'new_calls': [0, 0, 0]}
    temporary = parent/('.' + key + '.building-' + uuid4().hex)
    initialize_source_inputs(root=temporary, requirement=requirement,
                             clone_baseline=True)
    for relative in ('evidence/requests_log.csv',
                     'evidence/requests_log_manifest.json', *sorted(paths)):
        raw = resolve_repository_file(repo_root=source,
            repo_relative_path=relative).read_bytes()
        target = temporary/relative
        if target.exists():
            if target.read_bytes() == raw:
                continue
            _need(relative in {'evidence/requests_log.csv',
                               'evidence/requests_log_manifest.json'},
                  'ORDINARY_PROCESSING_BASELINE_SOURCE_CONFLICT:' + relative)
            target.write_bytes(raw)
        else:
            _clone_or_copy_source(source=resolve_repository_file(
                repo_root=source, repo_relative_path=relative), target=target)
    if checkpoint is not None:
        write_immutable_bytes(path=temporary/EXPORT_PATH,
            content=json.dumps(checkpoint, ensure_ascii=False,
                sort_keys=True, separators=(',', ':')).encode('utf-8') + b'\n')
    _need(sha256_file(path=source/'evidence/requests_log.csv') ==
          identity['source_ledger_sha256'],
          'ORDINARY_PROCESSING_SOURCE_CHANGED_DURING_COPY')
    write_immutable_bytes(path=temporary/META,
        content=json.dumps(identity, ensure_ascii=False,
            sort_keys=True, separators=(',', ':')).encode('utf-8') + b'\n')
    _check_copy(root=temporary, identity=identity, checkpoint=checkpoint,
                requirement=requirement)
    _need(not destination.exists(), 'ORDINARY_PROCESSING_CONCURRENT_SNAPSHOT_CREATED')
    os.rename(temporary, destination)
    return {'data_root': destination, 'snapshot_id': identity['snapshot_id'],
            'reused': False, 'new_calls': [0, 0, 0]}
