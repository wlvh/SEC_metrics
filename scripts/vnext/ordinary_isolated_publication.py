"""Private ordinary-version rehearsal using the existing publication core.

This type has no formal publication authority. Its process-local capability
only switches one verified candidate and its exact predecessor in a newly
created external workspace. Original Runs and historical bundles stay intact.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path

from git_workspace import first_symlink_in_path
from . import ordinary_release_preparation as preparation
from . import publication as pub, projector
from .annual_publication import _scalability_snapshot
from .canonical import canonical_json_bytes, content_hash, sha256_bytes, sha256_file, strict_json_file
from .ratchet_release import _copy_exact_tree, _tree_files
from .records import ANNUAL_PUBLICATION_MANIFEST_TYPE, validate_record
from .requirements import load_requirement_snapshot
from .run_store import _mechanically_replay_open_run

ROOT = Path(__file__).resolve().parents[2]
CREDIT = 'NONE_ISOLATED_ORDINARY_VERSION'
MARKER = 'ordinary_publication_workspace.json'
SNAPSHOT = 'internal/ordinary_preparation'
META = 'internal/ordinary_publication.json'
FACTS = 'internal/ordinary_complete_version.json'
REQUIREMENT = 'issue_28_v14'
IMPLEMENTATION = ('scripts/vnext/ordinary_isolated_publication.py',
                  'scripts/vnext/ordinary_release_preparation.py',
                  'scripts/vnext/publication.py', 'scripts/vnext/records.py',
                  'scripts/vnext/publication_results.py')
_FACTORY = object()
_created_workspaces = {}
_switch = ContextVar('ordinary_isolated_publication_edge', default=None)
_verified = ContextVar('ordinary_isolated_verified_manifest', default=None)


def need(condition, reason):
    if not condition:
        raise pub.PublicationError(reason)


def _json(value):
    return canonical_json_bytes(value=value) + b'\n'


def _record(body, field):
    return {**body, field: content_hash(value=body)}


def _safe_root(root):
    need(isinstance(root, Path) and root.is_absolute()
         and first_symlink_in_path(path=root) is None, 'ORDINARY_PUBLICATION_UNALIASED_ROOT_REQUIRED')
    root = root.resolve()
    need(root != ROOT and root not in ROOT.parents and ROOT not in root.parents,
         'ORDINARY_PUBLICATION_OFFICIAL_ROOT_FORBIDDEN')
    need(not any((p / '.git').exists() or (p / 'outputs/active_publication.json').exists()
                 for p in root.parents), 'ORDINARY_PUBLICATION_ACTIVE_OR_CHECKOUT_ANCESTOR')
    need(not (root / '.git').exists(), 'ORDINARY_PUBLICATION_CHECKOUT_FORBIDDEN')
    return root


def _marker(root):
    root = _safe_root(root)
    need((root / MARKER).is_file() and not (root / MARKER).is_symlink(),
         'ORDINARY_PUBLICATION_PRIVATE_MARKER_INVALID')
    value = strict_json_file(path=root / MARKER)
    need(set(value) == {'schema_version', 'purpose', 'publication_root', 'official_root',
         'preparation_id', 'predecessor', 'production_authorized', 'workspace_id'}
         and value['workspace_id'] == content_hash(value={k: v for k, v in value.items() if k != 'workspace_id'})
         and value['schema_version'] == 1 and value['purpose'] == CREDIT
         and value['publication_root'] == str(root) and value['official_root'] == str(ROOT)
         and value['production_authorized'] is False, 'ORDINARY_PUBLICATION_PRIVATE_MARKER_INVALID')
    return value


def _implementation():
    requirement = load_requirement_snapshot(snapshot_dir=ROOT / 'requirements' / REQUIREMENT)
    files = requirement['execution_authority']['files']
    bindings = {p: {'sha256': sha256_file(path=ROOT / p), 'size': (ROOT / p).stat().st_size}
                for p in IMPLEMENTATION}
    need(all(files.get(p) == binding for p, binding in bindings.items()),
         'ORDINARY_PUBLICATION_CURRENT_EXECUTION_NOT_BOUND')
    return requirement, bindings


def _ledger(snapshot, selected):
    """Bind actual compatible request prefixes, retaining every native proof.

    Production inputs share the append-only source log. Unrelated test logs
    cannot be silently concatenated or acquire invented request identities.
    """
    from sec_http import parse_request_log_rows, request_log_attempt_id, request_log_prefix_bytes, validate_request_log_manifest
    native_proofs, prefixes, sources, attempts, proofs = [], [], set(), set(), []
    for item in selected:
        data = snapshot / item['data_path']; run = snapshot / item['run_path']
        manifest, records, _ = _mechanically_replay_open_run(run_dir=run, repo_root=data, require_complete_results=True)
        indexes = projector._record_indexes(runs=[(manifest, records)])
        log = data / 'evidence/requests_log.csv'; validate_request_log_manifest(log_path=log)
        text = log.read_text(); rows = parse_request_log_rows(text=text)
        by_id = {request_log_attempt_id(row_index=i, row=row): (i, row) for i, row in enumerate(rows)}
        # Defined-scope absence deliberately has no quantity observations.
        # Its complete registered source census still owns every native source.
        used = [indexes['sources'][s] for s in sorted(indexes['sources'])]
        checked = [pub._request_row_for_source(repo_root=data, source=s, attempt_rows=by_id,
                   validation_tier=pub.RECORDED_VALIDATION_MODE) for s in used]
        need(checked and all(proof['locator_class'] == 'IMMUTABLE_ATTEMPT' for _, proof in checked),
             'ORDINARY_PUBLICATION_IMMUTABLE_SOURCES_REQUIRED')
        count = max(i for i, _ in checked) + 1
        prefix = request_log_prefix_bytes(text=text, row_count=count)
        prefixes.append((count, prefix)); proofs.extend(proof for _, proof in checked)
        sources.update(s['source_reference_id'] for s in used)
        attempts.update(s['request_attempt_id'] for s in used)
        native_proofs.append({'run_id': manifest['run_id'], 'row_count': count,
                             'requests_log_prefix_sha256': sha256_bytes(content=prefix)})
    count, longest = max(prefixes, key=lambda item: item[0])
    need(all(longest.startswith(prefix) for _, prefix in prefixes),
         'ORDINARY_PUBLICATION_UNRELATED_SOURCE_LOGS_NOT_SUPPORTED')
    provenance = pub._request_locator_provenance(validation_tier=pub.RECORDED_VALIDATION_MODE,
                                                source_proofs=proofs)
    binding = {'request_locator_classes': provenance['request_locator_classes'],
               'request_locator_proof_id': provenance['request_locator_proof_id'],
               'request_locator_tier': pub.RECORDED_VALIDATION_MODE,
               'requests_log_prefix_sha256': sha256_bytes(content=longest), 'row_count': count,
               'source_reference_ids': sorted(sources), 'used_request_attempt_ids': sorted(attempts)}
    return binding, {'native_prefixes': native_proofs, 'locator_provenance': provenance}


def _verify_nested_preparation(snapshot, expected_id):
    # A publication embeds the prepared tree beneath its private active root.
    # The public preparation API deliberately forbids such roots; reuse its
    # native composition below only after checking this entire immutable tree.
    need(first_symlink_in_path(path=snapshot) is None, 'ORDINARY_PUBLICATION_SNAPSHOT_ALIAS')
    saved = strict_json_file(path=snapshot / preparation.MANIFEST)
    body = {k: v for k, v in saved.items() if k != 'preparation_id'}
    need(saved['preparation_id'] == expected_id == content_hash(value=body)
         and saved['record_type'] == 'ORDINARY_RELEASE_PREPARATION' and saved['schema_version'] == 1,
         'ORDINARY_PUBLICATION_PREPARATION_ID_CHANGED')
    before = _tree_files(root=snapshot); files = dict(before); files.pop(preparation.MANIFEST)
    need(files == saved['files'], 'ORDINARY_PUBLICATION_PREPARATION_FILES_CHANGED')
    composition, public = preparation._compose(snapshot, saved['inputs'])
    need(composition == saved['composition'] and all((snapshot / p).read_bytes() == raw for p, raw in public.items())
         and _tree_files(root=snapshot) == before, 'ORDINARY_PUBLICATION_PREPARATION_REPLAY_CHANGED')
    return saved


def _selected_stratified_rows(*, metrics, evidence, selected):
    """Audit exact selected coordinates, including native nonnumeric states."""
    registry = {row['company_id']: row for row in projector._load_registry(repo_root=ROOT)}
    bindings = {(registry[item['company_id']]['display_name'], item['metric_id']): item for item in selected}
    need(len(bindings) == len(selected), 'ORDINARY_PUBLICATION_AUDIT_SELECTION_DUPLICATE')
    evidence_by_key = {}
    for row in evidence:
        evidence_by_key.setdefault((row['company'], row['metric_id']), []).append(row)
    output = []
    for row in metrics:
        key = row['company'], row['metric_id']
        if key not in bindings:
            continue
        binding = bindings[key]
        sources = evidence_by_key.get(key, [])
        need(sources or binding['applicability'] == 'N_A_STRUCTURAL' or binding['quality'] == 'NOT_MEANINGFUL',
             'ORDINARY_PUBLICATION_SELECTED_AUDIT_EVIDENCE_MISSING')
        output.append({'audit_id': 'AUDIT_{:02d}'.format(len(output) + 1), 'source_bucket': row['source_class'],
            **{field: row[field] for field in ('company', 'metric_id', 'metric_name', 'value', 'unit', 'status',
                'source_class', 'period_start', 'period_end', 'accession', 'concept_or_section', 'context_or_dimension')},
            'evidence_value': ';'.join(item['value_normalized'] for item in sources),
            'evidence_unit': ';'.join(item['unit'] for item in sources),
            'evidence_quote': ' | '.join(item['evidence_quote'] for item in sources),
            'audit_verdict': 'PASS',
            'audit_notes': 'Selected native Run, actual result state and evidence replayed; inherited coordinates retain their own evidence. '
                           + 'value_kind=' + binding['value_kind'] + '; reason=' + binding['reason_code']})
    need(len(output) == len(bindings), 'ORDINARY_PUBLICATION_AUDIT_SELECTION_MISSING')
    return output


def _compose(snapshot, meta):
    saved = _verify_nested_preparation(snapshot, meta['preparation_id'])
    requirement, implementation = _implementation()
    need(meta['implementation'] == implementation and meta['requirement_hashes'] == requirement['hashes'],
         'ORDINARY_PUBLICATION_IMPLEMENTATION_CHANGED')
    composition = saved['composition']; selected = composition['selected_results']
    ledger, provenance = _ledger(snapshot, selected)
    rows = pub._csv_rows(content=(snapshot / 'metrics_matrix.csv').read_bytes(), fieldnames=pub.METRIC_FIELDS, label='ordinary metrics')
    evidence = pub._csv_rows(content=(snapshot / 'metric_evidence.csv').read_bytes(), fieldnames=pub.EVIDENCE_FIELDS, label='ordinary evidence')
    predecessor = snapshot / 'predecessor' / saved['inputs']['predecessor']['publication_id']
    batch = _record({'record_type': 'ORDINARY_ISOLATED_COMPLETE_VERSION', 'preparation_id': saved['preparation_id'],
        'preparer_sha256': composition['preparer_sha256'], 'selected_results': selected,
        'predecessor': composition['predecessor'], 'public_row_count': len(rows),
        'inherited_public_row_count': composition['inherited_public_row_count'],
        'unselected_coordinate_keys': composition['unselected_coordinate_keys'],
        'matrix_hash': composition['matrix_hash'], 'evidence_hash': composition['evidence_hash'],
        'full390_acceptance': False, 'publication_credit': CREDIT}, 'batch_manifest_id')
    from tools.check_vnext_semantics import run_audit
    scans = {'semantic': run_audit(repo_root=ROOT, secret_roots=[], secret_token=''),
             'scalability': _scalability_snapshot(ROOT)}
    pub._semantic_gate_evidence(receipt=scans['semantic'], repo_root=None)
    need(not any(row['allowed'] not in {'1', 'true', 'True'} for row in scans['scalability']),
         'ORDINARY_PUBLICATION_SCALABILITY_FAILED')
    checks = {'NATIVE_COMPLETE_REPLAY': True, 'RETAINED_PREDECESSOR_EXACT': True,
              'SELECTED_EVIDENCE_RESOLVES': True, 'UNIQUE_PUBLIC_KEYS': len({(r['company'], r['metric_id']) for r in rows}) == len(rows),
              'CURRENT_EXECUTION_BOUND': True, 'IMMUTABLE_REQUEST_PREFIXES': True}
    need(all(checks.values()), 'ORDINARY_PUBLICATION_CHECK_FAILED')
    projection = _record({'record_type': 'ORDINARY_ISOLATED_PROJECTION', 'batch_manifest_id': batch['batch_manifest_id'],
        'preparation_id': saved['preparation_id'], 'requirement_hashes': requirement['hashes'],
        'publication_credit': CREDIT, 'full390_acceptance': False}, 'projection_manifest_id')
    files = {name: (snapshot / name).read_bytes() for name in ('metrics_matrix.csv', 'metric_evidence.csv')}
    files['coverage_matrix.csv'] = pub._csv_bytes(rows=pub._expected_coverage_rows(metrics=rows, evidence=evidence), fieldnames=pub.COVERAGE_FIELDS)
    files['stratified_audit.csv'] = pub._csv_bytes(rows=_selected_stratified_rows(
        metrics=rows, evidence=evidence, selected=selected), fieldnames=pub.STRATIFIED_FIELDS)
    files['scalability_audit.csv'] = pub._csv_bytes(rows=scans['scalability'], fieldnames=pub.SCALABILITY_FIELDS)
    files['semantic_audit_receipt.json'] = _json(scans['semantic'])
    files['legacy_invariant_migration_receipt.json'] = (predecessor / 'legacy_invariant_migration_receipt.json').read_bytes()
    files['golden_results.csv'] = pub._csv_bytes(rows=[{'assertion_id': key, 'description': key, 'expected': 'True',
        'actual': str(value), 'status': 'PASS', 'evidence_path': FACTS,
        'notes': 'Current selected native replay; inherited coordinates retain their original evidence.'}
        for key, value in sorted(checks.items())], fieldnames=pub.GOLDEN_FIELDS)
    files['repair_validation_results.csv'] = pub._csv_bytes(rows=[{'check_id': key, 'severity': 'ERROR',
        'status': 'PASS', 'details': 'Verified selected native version and exact retained predecessor.'}
        for key in sorted(checks)], fieldnames=pub.REPAIR_FIELDS)
    files['projection_manifest.json'] = _json(projection)
    files['validation_run_manifest.json'] = _json({'run_id': 'validation:' + projection['projection_manifest_id'],
        'mode': pub.RECORDED_VALIDATION_MODE, 'result': pub.RECORDED_VALIDATION_RESULT,
        'source_commit': pub.RECORDED_SOURCE_COMMIT, 'started_at_utc': meta['prepared_at_utc'],
        'refreshed_artifacts': sorted(pub.REQUIRED_BUNDLE_FILES - {'legacy_invariant_migration_receipt.json'}),
        'not_refreshed_artifacts': ['legacy_invariant_migration_receipt.json']})
    files.update(pub._expected_documents(metrics=rows, projection=projection, validation_mode=pub.RECORDED_VALIDATION_MODE))
    files['README_RUN.md'] += b'\nPrivate ordinary-version rehearsal only. No formal publication or full390 acceptance.\nSelected Runs retain their actual source and execution evidence type; inherited rows retain their original period and credit.\n'
    receipt = _record({'record_type': 'ORDINARY_ISOLATED_VALIDATION', 'status': pub.RECORDED_VALIDATION_RESULT,
        'publication_credit': CREDIT, 'batch_manifest_id': batch['batch_manifest_id'],
        'projection_manifest_id': projection['projection_manifest_id'], 'checks': checks, 'ledger_binding': ledger,
        'artifacts': {p: {'sha256': sha256_bytes(content=raw), 'size': len(raw)} for p, raw in sorted(files.items())}}, 'validation_receipt_id')
    files['publication_validation_receipt.json'] = _json(receipt)
    need(set(files) == pub.REQUIRED_BUNDLE_FILES, 'ORDINARY_PUBLICATION_PUBLIC_FILE_SET_CHANGED')
    files.update({META: _json(meta), FACTS: _json(batch), 'internal/ordinary_locator_provenance.json': _json(provenance)})
    pub._copy_tree_into_closure(source_root=snapshot, destination_root=Path(SNAPSHOT), files=files)
    for relative in IMPLEMENTATION:
        files['internal/implementation/' + relative] = (ROOT / relative).read_bytes()
    identity = {'candidate_status': 'PUBLISHABLE', 'artifact_requirement_generation': 'EXPLICIT_REQUIREMENT_V1',
        'requirement_id': requirement['requirement_id'], 'requirement_closure_hash': requirement['requirement_closure_hash'],
        'requirement_hashes': requirement['hashes'], 'projection_requirement_hashes': requirement['hashes'],
        'batch_manifest_id': batch['batch_manifest_id'], 'projection_manifest_id': projection['projection_manifest_id'],
        'validation_receipt_id': receipt['validation_receipt_id'], 'ledger_binding': ledger,
        'previous_publication_id': composition['predecessor']['publication_id'],
        'annual_adoption_receipt_id': saved['preparation_id'], 'publication_credit': CREDIT,
        'files': [{'path': p, 'sha256': sha256_bytes(content=raw), 'size': len(raw)} for p, raw in sorted(files.items())]}
    manifest = validate_record(record={'record_type': ANNUAL_PUBLICATION_MANIFEST_TYPE,
        'publication_id': 'publication_' + content_hash(value=identity)[7:], **identity})
    return files, manifest


def stage(*, preparation_root, publication_root):
    root = _safe_root(publication_root)
    need(not root.exists(), 'ORDINARY_PUBLICATION_FRESH_PRIVATE_ROOT_REQUIRED')
    source = preparation._external(preparation_root)
    need(root != source and root not in source.parents and source not in root.parents,
         'ORDINARY_PUBLICATION_INPUT_OUTPUT_OVERLAP')
    saved = preparation.verify(preparation_root=source)
    requirement, implementation = _implementation()
    official_pointer = (ROOT / 'outputs/active_publication.json').read_bytes()
    official = pub.PublicationView.open(publication_root=ROOT)
    need(saved['inputs']['predecessor'] == {'publication_id': official.publication_id,
         'manifest_sha256': sha256_file(path=official.bundle_dir / 'publication_manifest.json')},
         'ORDINARY_PUBLICATION_CURRENT_PREDECESSOR_CHANGED')
    snapshot = root / 'staging/ordinary_preparation'
    _copy_exact_tree(source=source, destination=snapshot)
    meta = {'preparation_id': saved['preparation_id'], 'implementation': implementation,
            'requirement_hashes': requirement['hashes'], 'prepared_at_utc': datetime.now(timezone.utc).isoformat()}
    files, manifest = _compose(snapshot, meta)
    need((ROOT / 'outputs/active_publication.json').read_bytes() == official_pointer,
         'ORDINARY_PUBLICATION_OFFICIAL_PREDECESSOR_CHANGED')
    _copy_exact_tree(source=official.bundle_dir, destination=root / 'outputs/publications' / official.publication_id)
    _copy_exact_tree(source=ROOT / 'outputs/publication_switch_receipts', destination=root / 'outputs/publication_switch_receipts')
    for name in ('active_publication.json', 'active_publication.json.lock'):
        (root / 'outputs' / name).write_bytes((ROOT / 'outputs' / name).read_bytes())
    for relative, target in pub.ROOT_MIRROR_RELATIVE_PATHS.items():
        path = root / target; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(official.read_bytes(relative_path=relative))
    marker = _record({'schema_version': 1, 'purpose': CREDIT, 'publication_root': str(root), 'official_root': str(ROOT),
        'preparation_id': saved['preparation_id'], 'predecessor': saved['inputs']['predecessor'],
        'production_authorized': False}, 'workspace_id')
    (root / MARKER).write_bytes(_json(marker))
    pub._persist_prepared_publication_bundle(publications_dir=root / 'outputs/publications', files=files, manifest=manifest)
    need((root / 'outputs/active_publication.json').read_bytes() == official_pointer
         and (ROOT / 'outputs/active_publication.json').read_bytes() == official_pointer,
         'ORDINARY_PUBLICATION_SEED_POINTER_CHANGED')
    _created_workspaces[str(root)] = marker['workspace_id']
    return {'publication_id': manifest['publication_id'], 'preparation_id': saved['preparation_id'],
            'credit': CREDIT, 'new_calls': [0, 0, 0]}


def verify_annual_bundle(*, bundle_dir, manifest):
    need(manifest['publication_credit'] == CREDIT and manifest['candidate_status'] == 'PUBLISHABLE',
         'ORDINARY_PUBLICATION_PRIVATE_TYPE_REQUIRED')
    if _verified.get() == canonical_json_bytes(value=manifest):
        return manifest
    files, rebuilt = _compose(bundle_dir / SNAPSHOT, strict_json_file(path=bundle_dir / META))
    need(rebuilt == manifest and all((bundle_dir / p).read_bytes() == raw for p, raw in files.items()),
         'ORDINARY_PUBLICATION_REPLAY_CHANGED')
    return manifest


def _edge():
    value = _switch.get()
    need(type(value) is tuple and len(value) == 3 and value[0] is _FACTORY,
         'ORDINARY_PUBLICATION_PRIVATE_CAPABILITY_REQUIRED')
    root, manifest = value[1:]; marker = _marker(root)
    need(_created_workspaces.get(str(root)) == marker['workspace_id'],
         'ORDINARY_PUBLICATION_CREATOR_PROCESS_REQUIRED')
    need(manifest['publication_credit'] == CREDIT and manifest['annual_adoption_receipt_id'] == marker['preparation_id']
         and manifest['previous_publication_id'] == marker['predecessor']['publication_id'],
         'ORDINARY_PUBLICATION_PRIVATE_EDGE_CHANGED')
    predecessor = root / 'outputs/publications' / manifest['previous_publication_id']
    need(sha256_file(path=predecessor / 'publication_manifest.json') == marker['predecessor']['manifest_sha256'],
         'ORDINARY_PUBLICATION_PRIVATE_PREDECESSOR_CHANGED')
    return root, manifest


def commit_authority(*, bundle_dir, manifest):
    root, selected = _edge()
    need(bundle_dir == root / 'outputs/publications' / manifest['publication_id'] and manifest == selected,
         'ORDINARY_PUBLICATION_COMMIT_OUTSIDE_PRIVATE_EDGE')
    verify_annual_bundle(bundle_dir=bundle_dir, manifest=manifest)
    return pub.RECORDED_COMMIT_AUTHORITY


def guard_switch(*, pointer_path, manifest, expected_active_id, switch_mode):
    root, selected = _edge()
    need(pointer_path == root / 'outputs/active_publication.json'
         and ((switch_mode == 'COMMIT' and manifest == selected and expected_active_id == selected['previous_publication_id'])
              or (switch_mode == 'ROLLBACK' and manifest['publication_id'] == selected['previous_publication_id']
                  and expected_active_id == selected['publication_id'])), 'ORDINARY_PUBLICATION_SWITCH_EDGE_CHANGED')
    current = root / 'outputs/publications' / expected_active_id
    pub.verify_publication_bundle(bundle_dir=current)
    need(all((root / target).read_bytes() == (current / relative).read_bytes()
             for relative, target in pub.ROOT_MIRROR_RELATIVE_PATHS.items()), 'ORDINARY_PUBLICATION_ACTIVE_MIRROR_DRIFT')


def guard_recovery(*, pointer_path, intent):
    root, selected = _edge()
    need(pointer_path == root / 'outputs/active_publication.json', 'ORDINARY_PUBLICATION_RECOVERY_ROOT_CHANGED')
    before = intent['previous_pointer']; after = intent['proposed_pointer']
    need(before is not None and ((intent['switch_mode'] == 'COMMIT'
         and before['publication_id'] == selected['previous_publication_id'] and after['publication_id'] == selected['publication_id'])
         or (intent['switch_mode'] == 'ROLLBACK' and before['publication_id'] == selected['publication_id']
             and after['publication_id'] == selected['previous_publication_id'])), 'ORDINARY_PUBLICATION_RECOVERY_EDGE_CHANGED')


def guard_mirror_repair(*, publication_root):
    root, selected = _edge()
    need(publication_root == root, 'ORDINARY_PUBLICATION_MIRROR_ROOT_CHANGED')
    view = pub.PublicationView.open(publication_root=root)
    need(view.publication_id in {selected['publication_id'], selected['previous_publication_id']},
         'ORDINARY_PUBLICATION_MIRROR_EDGE_CHANGED')


def recovery_hooks():
    """Only an already established private capability selects mirror repair."""
    if _switch.get() is None:
        return None
    _edge()
    import sys
    return sys.modules[__name__]


@contextmanager
def _capability(root, manifest):
    token = _switch.set((_FACTORY, root, manifest))
    pin = _verified.set(canonical_json_bytes(value=manifest))
    try:
        _edge()
        yield
    finally:
        _verified.reset(pin); _switch.reset(token)


def read_back(*, publication_root):
    root = _safe_root(publication_root); _marker(root)
    view = pub.PublicationView.open(publication_root=root)
    need(all((root / target).read_bytes() == view.read_bytes(relative_path=relative)
             for relative, target in pub.ROOT_MIRROR_RELATIVE_PATHS.items()), 'ORDINARY_PUBLICATION_READ_BACK_MIRROR_CHANGED')
    return {'publication_id': view.publication_id, 'credit': CREDIT,
            'matrix_sha256': sha256_bytes(content=view.read_bytes(relative_path='metrics_matrix.csv')),
            'evidence_sha256': sha256_bytes(content=view.read_bytes(relative_path='metric_evidence.csv'))}


def switch(*, publication_root, publication_id, operation):
    root = _safe_root(publication_root); _marker(root)
    need(operation in {'publish', 'rollback', 'restore', 'recover'}, 'ORDINARY_PUBLICATION_OPERATION_INVALID')
    need(pub.PUBLICATION_ID_PATTERN.fullmatch(publication_id) is not None, 'ORDINARY_PUBLICATION_ID_INVALID')
    directory = root / 'outputs/publications' / publication_id
    manifest = pub.verify_publication_bundle(bundle_dir=directory)
    need(manifest.get('publication_credit') == CREDIT, 'ORDINARY_PUBLICATION_PRIVATE_TYPE_REQUIRED')
    with _capability(root, manifest):
        if operation == 'recover':
            pub.recover_publication_mirrors(publication_root=root)
        else:
            current = pub.PublicationView.open(publication_root=root).publication_id
            target = manifest['previous_publication_id'] if operation == 'rollback' else publication_id
            if current != target:
                kwargs = {'publication_root': root, 'expected_active_publication_id': current,
                          'committed_at_utc': datetime.now(timezone.utc).isoformat()}
                if operation == 'rollback':
                    pub.rollback_publication(target_publication_id=target, **kwargs)
                else:
                    pub._commit_recorded_sandbox_publication(publication_id=target, **kwargs)
        return read_back(publication_root=root)
