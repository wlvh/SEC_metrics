"""Ordinary annual adoption through the existing complete publication primitives.

Only isolated rehearsal is implemented. Native Runs, full predecessor bytes,
Projector output and independent validation records remain separate identities.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
import json
import io
import tarfile
import shutil
from datetime import datetime, timezone

from . import publication as pub
from .annual_adoption import ROOT, POLICY, need, read, record, check_id, git, policy
from .annual_adoption import prepare_snapshot, replay_snapshot
from .annual_projection import build_projection
from .canonical import canonical_json_bytes, content_hash, sha256_bytes, sha256_file, strict_json_file
from .ratchet_release import _tree_files, _copy_exact_tree
from .records import ANNUAL_PUBLICATION_MANIFEST_TYPE, validate_record

CREDIT = 'NONE_ISOLATED_ADOPTION_REHEARSAL'
SNAPSHOT = 'internal/annual_snapshot'
META = 'internal/annual_release.json'
BATCH = 'internal/annual_complete_version.json'
PROOF = 'internal/annual_projection.json'
_FACTORY = object()
_pin = ContextVar('annual_verified_publication', default=None)
_switch = ContextVar('annual_isolated_publication_edge', default=None)


def json_bytes(value):
    return canonical_json_bytes(value=value) + b'\n'


def utc():
    return datetime.now(timezone.utc).isoformat()


def safe_root(root):
    need(isinstance(root, Path) and root.is_absolute(), 'ANNUAL_ABSOLUTE_ROOT_REQUIRED')
    for path in (root, *root.parents):
        need(not path.is_symlink() and not (path / '.git').exists(), 'ANNUAL_ROOT_ALIAS_OR_CHECKOUT')
    result = root.resolve()
    need(result != ROOT and result not in ROOT.parents and ROOT not in result.parents, 'ANNUAL_OFFICIAL_ROOT_FORBIDDEN')
    if (result / 'outputs/active_publication.json').exists():
        need((result / 'annual_publication_workspace.json').is_file(), 'ANNUAL_UNOWNED_ACTIVE_ROOT_FORBIDDEN')
    return result


def _marker(root):
    root = safe_root(root)
    marker = read(root, 'annual_publication_workspace.json')
    check_id(marker, 'workspace_id')
    need(marker['purpose'] == 'ISOLATED_ANNUAL_PUBLICATION_REHEARSAL'
         and marker['publication_root'] == str(root)
         and marker['official_root'] == str(ROOT)
         and marker['formal_publication_authorized'] is False
         and marker['predecessor_publication_id'] == policy()['baseline_publication']['publication_id']
         and marker['predecessor_manifest_sha256'] == policy()['baseline_publication']['manifest_sha256'],
         'ANNUAL_REHEARSAL_ROOT_INVALID')
    return marker


def initialize(*, publication_root):
    root = safe_root(publication_root)
    if (root / 'annual_publication_workspace.json').exists():
        return _marker(root)
    need(not root.exists() or not any(root.iterdir()), 'ANNUAL_REHEARSAL_ROOT_NOT_EMPTY')
    view = pub.PublicationView.open(publication_root=ROOT)
    root.mkdir(parents=True, exist_ok=True)
    _copy_exact_tree(source=view.bundle_dir, destination=root / 'outputs/publications' / view.publication_id)
    receipts = ROOT / 'outputs/publication_switch_receipts'
    _copy_exact_tree(source=receipts, destination=root / 'outputs/publication_switch_receipts')
    for name in ('active_publication.json', 'active_publication.json.lock'):
        (root / 'outputs' / name).write_bytes((ROOT / 'outputs' / name).read_bytes())
    for relative, target in pub.ROOT_MIRROR_RELATIVE_PATHS.items():
        path = root / target; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(view.read_bytes(relative_path=relative))
    marker = record({'schema_version': 1, 'purpose': 'ISOLATED_ANNUAL_PUBLICATION_REHEARSAL',
        'publication_root': str(root), 'official_root': str(ROOT),
        'predecessor_publication_id': view.publication_id,
        'predecessor_manifest_sha256': sha256_file(path=view.bundle_dir / 'publication_manifest.json'),
        'formal_publication_authorized': False}, 'workspace_id')
    (root / 'annual_publication_workspace.json').write_bytes(json_bytes(marker))
    need(pub.PublicationView.open(publication_root=root).publication_id == view.publication_id,
         'ANNUAL_REHEARSAL_SEED_CHANGED')
    return marker


def _ledger(snapshot, indexes):
    from sec_http import parse_request_log_rows, request_log_attempt_id, request_log_prefix_bytes, validate_request_log_manifest
    data = snapshot / 'data'
    path = data / 'evidence/requests_log.csv'; validate_request_log_manifest(log_path=path)
    text = path.read_text(); rows = parse_request_log_rows(text=text)
    attempts = {request_log_attempt_id(row_index=i, row=row): (i, row) for i, row in enumerate(rows)}
    sources = [indexes['sources'][key] for key in sorted(indexes['used_source_reference_ids'])]
    verified = [pub._request_row_for_source(repo_root=data, source=source, attempt_rows=attempts,
        validation_tier=pub.RECORDED_VALIDATION_MODE) for source in sources]
    need(verified and all(proof['locator_class'] == 'IMMUTABLE_ATTEMPT' for _, proof in verified), 'ANNUAL_IMMUTABLE_SOURCE_REQUIRED')
    used = sorted({(row, source['request_attempt_id']) for source, (row, _) in zip(sources, verified)})
    count = max(row for row, _ in used) + 1
    provenance = pub._request_locator_provenance(validation_tier=pub.RECORDED_VALIDATION_MODE,
        source_proofs=[p for _, p in verified])
    binding = {'request_locator_classes': provenance['request_locator_classes'],
        'request_locator_proof_id': provenance['request_locator_proof_id'], 'request_locator_tier': pub.RECORDED_VALIDATION_MODE,
        'requests_log_prefix_sha256': sha256_bytes(content=request_log_prefix_bytes(text=text, row_count=count)),
        'row_count': count, 'source_reference_ids': [s['source_reference_id'] for s in sources],
        'used_request_attempt_ids': [identity for _, identity in used]}
    return binding, provenance


def _scalability_snapshot(runtime_root):
    """Reuse trusted matchers while leaving the frozen pipeline byte-identical."""
    from sec_pipeline import load_company_registry_from_path, literal_value_matches_identity
    from sec_pipeline import python_literal_values, audit_python_literal
    registry = load_company_registry_from_path(path=runtime_root / 'config/company_registry.csv')
    identities = []
    for company in registry:
        candidates = [(str(company['company']), 'company_name'), (str(company['primary_cik']), 'cik')]
        if company['ticker']:
            candidates.append((str(company['ticker']), 'ticker'))
        candidates.extend((str(role['cik']), 'cik') for role in company['roles'])
        for candidate in candidates:
            if candidate not in identities:
                identities.append(candidate)
    rows = []
    for prefix in ('scripts', 'tools'):
        for path in sorted((runtime_root / prefix).rglob('*.py')):
            relative = path.relative_to(runtime_root)
            for line, literal in python_literal_values(path=path):
                for forbidden, kind in identities:
                    if literal_value_matches_identity(literal_value=literal, forbidden_literal=forbidden, literal_type=kind):
                        rows.append({'file': relative.as_posix(), 'line': str(line), 'literal': forbidden,
                            'type': kind, 'allowed': '0', 'reason': 'identity literal appears in production Python',
                            'replacement_plan': 'Move identity to config or fixtures and branch on profile, SEC metadata, dimensions, or registry rules.'})
                # The native helper owns the accession/date matching rules.
                # Its current-registry company matches are replaced above by
                # the snapshot registry, preserving historical interpretation.
                rows.extend(row for row in audit_python_literal(file_path=ROOT / relative,
                    line_number=line, literal_value=literal) if row['type'] in {'accession', 'fixed_fiscal_date'})
    return rows


def _implementation_files(head):
    need(type(head) is str and len(head) == 40 and all(c in '0123456789abcdef' for c in head), 'ANNUAL_IMPLEMENTATION_HEAD_INVALID')
    need(git('merge-base', head, 'HEAD').decode().strip() == head, 'ANNUAL_IMPLEMENTATION_NOT_ANCESTOR')
    paths = git('ls-tree', '-r', '--name-only', head, 'scripts', 'tools', 'config', 'catalog', 'requirements').decode().splitlines()
    foundation = json.loads(git('show', head + ':requirements/issue_15_v1/foundation_verification_receipt.json'))
    paths = sorted(set(paths) | {r['path'] for r in foundation['receipt_bindings']})
    files = {}
    with tarfile.open(fileobj=io.BytesIO(git('archive', '--format=tar', head, *paths))) as archive:
        for member in archive:
            need(member.isdir() or member.isfile(), 'ANNUAL_IMPLEMENTATION_ALIAS')
            if member.isfile():
                data = archive.extractfile(member).read()
                files[member.name] = {'sha256': sha256_bytes(content=data), 'size': len(data)}
    return files


def _public_files(projection, adoption, requirement, ledger, meta, runtime_root, predecessor):
    metrics, evidence = projection['metrics'], projection['evidence']
    batch = projection['batch']
    checks = {'COMPLETE_CUMULATIVE_KEYS': batch['selected_result_count'] + batch['inherited_result_count'] == len(batch['cumulative_result_bindings']),
        'EXACT_SELECTED_ADOPTION': batch['selected_result_count'] == len(adoption['selected_results']),
        'UNCHANGED_ROWS_AND_PERIODS': projection['proof']['periods_not_relabelled'],
        'UNIQUE_PUBLIC_KEYS': len({(r['company'], r['metric_id']) for r in metrics}) == len(metrics),
        'NATIVE_GRAPH_AND_SOURCE_REPLAY': adoption['status'] == 'PASSED_ISOLATED_ADOPTION',
        'NUMERIC_ROWS_HAVE_EVIDENCE': all(not r['value'] or (r['company'], r['metric_id']) in {
            (e['company'], e['metric_id']) for e in evidence} for r in metrics)}
    need(all(checks.values()), 'ANNUAL_COMPLETE_PUBLICATION_CHECK_FAILED')
    scans = meta['scans']
    from tools.check_vnext_semantics import run_audit
    need(run_audit(repo_root=runtime_root, secret_roots=[], secret_token='') == scans['semantic'],
         'ANNUAL_SEMANTIC_REPLAY_CHANGED')
    pub._semantic_gate_evidence(receipt=scans['semantic'], repo_root=None)
    need(_scalability_snapshot(runtime_root) == scans['scalability'], 'ANNUAL_SCALABILITY_REPLAY_CHANGED')
    need(not any(row['allowed'] not in {'1', 'true', 'True'} for row in scans['scalability']), 'ANNUAL_SCALABILITY_FAILED')
    files = dict(projection['files'])
    files['coverage_matrix.csv'] = pub._csv_bytes(rows=pub._expected_coverage_rows(metrics=metrics, evidence=evidence), fieldnames=pub.COVERAGE_FIELDS)
    files['stratified_audit.csv'] = pub._csv_bytes(rows=pub._expected_stratified_rows(metrics=metrics, evidence=evidence,
        migrated_ids=projection['migrated_ids']), fieldnames=pub.STRATIFIED_FIELDS)
    files['scalability_audit.csv'] = pub._csv_bytes(rows=scans['scalability'], fieldnames=pub.SCALABILITY_FIELDS)
    files['semantic_audit_receipt.json'] = json_bytes(scans['semantic'])
    files['legacy_invariant_migration_receipt.json'] = predecessor.read_bytes(relative_path='legacy_invariant_migration_receipt.json')
    files['golden_results.csv'] = pub._csv_bytes(rows=[{'assertion_id': 'ANNUAL_' + key,
        'description': key, 'expected': 'True', 'actual': str(value), 'status': 'PASS',
        'evidence_path': BATCH, 'notes': 'Recomputed native adoption and exact predecessor comparison; no old producer.'}
        for key, value in sorted(checks.items())], fieldnames=pub.GOLDEN_FIELDS)
    files['repair_validation_results.csv'] = pub._csv_bytes(rows=[{'check_id': key, 'severity': 'ERROR',
        'status': 'PASS', 'details': 'Mechanically recomputed; original Run/evidence unchanged.'} for key in sorted(checks)], fieldnames=pub.REPAIR_FIELDS)
    projection_manifest = record({'record_type': 'ANNUAL_PUBLIC_PROJECTION_MANIFEST', 'schema_version': 1,
        'batch_manifest_id': batch['batch_manifest_id'], 'adoption_receipt_id': adoption['adoption_receipt_id'],
        'projection_receipt_id': projection['proof']['projection_receipt_id'],
        'requirement_id': requirement['requirement_id'], 'requirement_hashes': requirement['hashes'],
        'requirement_closure_hash': requirement['requirement_closure_hash'], 'publication_credit': CREDIT,
        'native_requirement_identities': adoption['native_requirement_hashes']}, 'projection_manifest_id')
    files['projection_manifest.json'] = json_bytes(projection_manifest)
    files['validation_run_manifest.json'] = json_bytes({'run_id': 'validation:' + projection_manifest['projection_manifest_id'],
        'mode': pub.RECORDED_VALIDATION_MODE, 'result': pub.RECORDED_VALIDATION_RESULT,
        'source_commit': meta['implementation_head'], 'started_at_utc': meta['prepared_at_utc'],
        'refreshed_artifacts': sorted(pub.REQUIRED_BUNDLE_FILES - {'legacy_invariant_migration_receipt.json'}),
        'not_refreshed_artifacts': ['legacy_invariant_migration_receipt.json']})
    files.update(pub._expected_documents(metrics=metrics, projection=projection_manifest, validation_mode=pub.RECORDED_VALIDATION_MODE))
    files['README_RUN.md'] += ('\nAnnual adoption rehearsal: use PublicationView.open(publication_root=<isolated-root>).\n'
        'Original Runs remain OPEN; new immutable adoption is not formal qualification.\n'
        'Read internal/annual_complete_version.json for every selected/inherited coordinate and source period.\n').encode()
    receipt = record({'record_type': 'ANNUAL_PUBLICATION_VALIDATION_RECEIPT', 'schema_version': 1,
        'status': pub.RECORDED_VALIDATION_RESULT, 'publication_credit': CREDIT,
        'adoption_receipt_id': adoption['adoption_receipt_id'], 'batch_manifest_id': batch['batch_manifest_id'],
        'projection_manifest_id': projection_manifest['projection_manifest_id'], 'checks': checks,
        'ledger_binding': ledger, 'artifacts': {p: {'sha256': sha256_bytes(content=b), 'size': len(b)} for p, b in sorted(files.items())},
        'formal_remaining_conditions': policy()['formal_remaining_conditions']}, 'validation_receipt_id')
    files['publication_validation_receipt.json'] = json_bytes(receipt)
    need(set(files) == pub.REQUIRED_BUNDLE_FILES, 'ANNUAL_FULL_PUBLIC_FILE_SET_INVALID')
    return files, projection_manifest, receipt


class _Verified:
    def __init__(self, factory, manifest):
        need(factory is _FACTORY, 'ANNUAL_VERIFIED_FACTORY_REQUIRED')
        self.manifest = canonical_json_bytes(value=manifest)


@contextmanager
def _verified(pin):
    need(type(pin) is _Verified, 'ANNUAL_VERIFIED_PIN_REQUIRED')
    token = _pin.set(pin)
    try:
        yield
    finally:
        _pin.reset(token)


def _compose(snapshot, context, predecessor_dir, meta, runtime_root):
    baseline = policy()['baseline_publication']
    need(predecessor_dir.name == baseline['publication_id']
         and sha256_file(path=predecessor_dir / 'publication_manifest.json') == baseline['manifest_sha256'],
         'ANNUAL_TRUSTED_PREDECESSOR_CHANGED')
    predecessor_manifest = pub.verify_publication_bundle(bundle_dir=predecessor_dir)
    need(predecessor_manifest['publication_id'] == meta['predecessor_publication_id']
         and sha256_file(path=predecessor_dir / 'publication_manifest.json') == meta['predecessor_manifest_sha256'],
         'ANNUAL_PREDECESSOR_CHANGED')
    predecessor = pub.PublicationView(publication_id=predecessor_manifest['publication_id'],
        bundle_dir=predecessor_dir, manifest=predecessor_manifest)
    adoption, runs, requirement = replay_snapshot(snapshot, context)
    need(read(snapshot, 'adoption.json') == adoption, 'ANNUAL_ADOPTION_RECEIPT_CHANGED')
    projection = build_projection(snapshot_root=snapshot, context=context, adoption=adoption, runs=runs, predecessor=predecessor)
    ledger, provenance = _ledger(snapshot, projection['indexes'])
    public, projection_manifest, validation = _public_files(projection, adoption, requirement, ledger, meta, runtime_root, predecessor)
    return public, projection, adoption, requirement, ledger, provenance, projection_manifest, validation


def prepare(*, candidate_dir, publication_root):
    need(not git('status', '--porcelain', '--untracked-files=all').strip(), 'ANNUAL_PUBLICATION_CLEAN_CODE_REQUIRED')
    implementation_head = git('rev-parse', 'HEAD').decode().strip()
    marker = initialize(publication_root=publication_root)
    root = safe_root(publication_root)
    candidate_dir = safe_root(candidate_dir)
    candidate_hash = content_hash(value=_tree_files(root=candidate_dir))
    implementation_tree = content_hash(value=git('ls-tree', '-r', 'HEAD', 'scripts', 'tools', 'config', 'catalog', 'requirements').decode())
    key = content_hash(value={'candidate_files': candidate_hash, 'predecessor': marker['predecessor_publication_id'],
        'policy': policy(), 'implementation_tree': implementation_tree})[7:]
    workspace = root / 'annual_preparation' / key
    completed = workspace / 'prepared.json'
    if completed.exists():
        saved = read(workspace, 'prepared.json')
        pub.verify_publication_bundle(bundle_dir=root / 'outputs/publications' / saved['publication_id'])
        return {**saved, 'status': 'REUSED_PREPARED_PUBLICATION', 'new_provider_paid_sec_calls': [0, 0, 0]}
    snapshot = workspace / 'snapshot'
    prepare_snapshot(candidate_dir=candidate_dir, output_root=snapshot)
    context = read(snapshot, 'context.json')
    runtime = workspace / 'runtime'; runtime.mkdir()
    source_paths = sorted(_implementation_files(implementation_head))
    for relative in source_paths:
        source = ROOT / relative
        need(source.is_file() and not source.is_symlink(), 'ANNUAL_RUNTIME_SOURCE_UNSAFE')
        target = runtime / relative; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(source.read_bytes())
    scans = {'semantic': pub._execute_semantic_audit(repo_root=ROOT), 'scalability': pub._execute_scalability_audit(repo_root=ROOT)}
    meta = {'schema_version': 1, 'implementation_head': implementation_head,
        'implementation_tree': implementation_tree,
        'prepared_at_utc': utc(), 'policy': policy(), 'scans': scans,
        'predecessor_publication_id': marker['predecessor_publication_id'],
        'predecessor_manifest_sha256': marker['predecessor_manifest_sha256'],
        'runtime_files': _tree_files(root=runtime)}
    need(meta['runtime_files'] == _implementation_files(implementation_head), 'ANNUAL_PREPARE_CODE_BYTES_CHANGED')
    predecessor = root / 'outputs/publications' / marker['predecessor_publication_id']
    public, projection, adoption, requirement, ledger, provenance, projection_manifest, validation = _compose(snapshot, context, predecessor, meta, runtime)
    files = {**public, META: json_bytes(meta), BATCH: json_bytes(projection['batch']), PROOF: json_bytes(projection['proof']),
             'internal/annual_locator_provenance.json': json_bytes(provenance)}
    for source, prefix in [(snapshot, SNAPSHOT), (runtime, 'internal/annual_runtime'),
                            (predecessor, 'internal/predecessor/' + predecessor.name)]:
        pub._copy_tree_into_closure(source_root=source, destination_root=Path(prefix), files=files)
    body = {'candidate_status': 'PUBLISHABLE', 'artifact_requirement_generation': 'EXPLICIT_REQUIREMENT_V1',
        'requirement_id': requirement['requirement_id'], 'requirement_closure_hash': requirement['requirement_closure_hash'],
        'requirement_hashes': requirement['hashes'], 'projection_requirement_hashes': requirement['hashes'],
        'batch_manifest_id': projection['batch']['batch_manifest_id'], 'projection_manifest_id': projection_manifest['projection_manifest_id'],
        'validation_receipt_id': validation['validation_receipt_id'], 'ledger_binding': ledger,
        'previous_publication_id': marker['predecessor_publication_id'],
        'annual_adoption_receipt_id': adoption['adoption_receipt_id'], 'publication_credit': CREDIT,
        'files': [{'path': p, 'sha256': sha256_bytes(content=b), 'size': len(b)} for p, b in sorted(files.items())]}
    manifest = validate_record(record={'record_type': ANNUAL_PUBLICATION_MANIFEST_TYPE,
        'publication_id': 'publication_' + content_hash(value=body)[7:], **body})
    need(not git('status', '--porcelain', '--untracked-files=all').strip()
         and git('rev-parse', 'HEAD').decode().strip() == implementation_head, 'ANNUAL_CODE_CHANGED_DURING_PREPARE')
    pin = _Verified(_FACTORY, manifest)
    with _verified(pin):
        pub._persist_prepared_publication_bundle(publications_dir=root / 'outputs/publications', files=files, manifest=manifest)
    result = {'status': 'PREPARED_ISOLATED_COMPLETE_PUBLICATION', 'publication_id': manifest['publication_id'],
        'previous_publication_id': manifest['previous_publication_id'], 'adoption_receipt_id': adoption['adoption_receipt_id'],
        'cumulative_result_count': len(projection['batch']['cumulative_result_bindings']),
        'public_row_count': projection['batch']['public_row_count'], 'selected_result_count': projection['batch']['selected_result_count'],
        'publication_credit': CREDIT, 'new_provider_paid_sec_calls': [0, 0, 0]}
    completed.write_bytes(json_bytes(result))
    return result


def verify_annual_bundle(*, bundle_dir, manifest):
    pin = _pin.get()
    if type(pin) is _Verified and pin.manifest == canonical_json_bytes(value=manifest):
        return manifest
    need(manifest['record_type'] == ANNUAL_PUBLICATION_MANIFEST_TYPE and manifest['publication_credit'] == CREDIT,
         'ANNUAL_FORMAL_CREDIT_FORBIDDEN')
    meta = read(bundle_dir, META)
    need(meta['policy'] == policy() and _tree_files(root=bundle_dir / 'internal/annual_runtime') == meta['runtime_files']
         and meta['runtime_files'] == _implementation_files(meta['implementation_head'])
         and meta['implementation_tree'] == content_hash(value=git('ls-tree', '-r', meta['implementation_head'],
             'scripts', 'tools', 'config', 'catalog', 'requirements').decode()),
         'ANNUAL_RELEASE_RUNTIME_CHANGED')
    snapshot = bundle_dir / SNAPSHOT; context = read(snapshot, 'context.json')
    predecessor = bundle_dir / 'internal/predecessor' / manifest['previous_publication_id']
    values = _compose(snapshot, context, predecessor, meta, bundle_dir / 'internal/annual_runtime')
    public, projection, adoption, requirement, ledger, provenance, projected, validation = values
    expected = {**public, META: json_bytes(meta), BATCH: json_bytes(projection['batch']), PROOF: json_bytes(projection['proof']),
                'internal/annual_locator_provenance.json': json_bytes(provenance)}
    for source, prefix in [(snapshot, SNAPSHOT), (bundle_dir / 'internal/annual_runtime', 'internal/annual_runtime'),
                           (predecessor, 'internal/predecessor/' + predecessor.name)]:
        pub._copy_tree_into_closure(source_root=source, destination_root=Path(prefix), files=expected)
    need(set(expected) == {r['path'] for r in manifest['files']}, 'ANNUAL_COMPLETE_CLOSURE_CHANGED')
    for path, data in expected.items():
        need((bundle_dir / path).read_bytes() == data, 'ANNUAL_REPLAYED_PUBLIC_BYTES_CHANGED: ' + path)
    need(manifest['annual_adoption_receipt_id'] == adoption['adoption_receipt_id']
         and manifest['batch_manifest_id'] == projection['batch']['batch_manifest_id']
         and manifest['projection_manifest_id'] == projected['projection_manifest_id']
         and manifest['validation_receipt_id'] == validation['validation_receipt_id']
         and manifest['ledger_binding'] == ledger and manifest['requirement_hashes'] == requirement['hashes']
         and manifest['requirement_id'] == requirement['requirement_id']
         and manifest['requirement_closure_hash'] == requirement['requirement_closure_hash']
         and manifest['projection_requirement_hashes'] == requirement['hashes'], 'ANNUAL_RELEASE_IDENTITY_CHANGED')
    return manifest


def commit_authority(*, bundle_dir, manifest):
    verify_annual_bundle(bundle_dir=bundle_dir, manifest=manifest)
    return pub.RECORDED_COMMIT_AUTHORITY


def _edge():
    edge = _switch.get()
    need(type(edge) is tuple and len(edge) == 3 and edge[0] is _FACTORY, 'ANNUAL_ISOLATED_SWITCH_CAPABILITY_REQUIRED')
    root, manifest = edge[1:]
    marker = _marker(root)
    need(manifest['publication_credit'] == CREDIT and manifest['previous_publication_id'] == marker['predecessor_publication_id'],
         'ANNUAL_SWITCH_EDGE_CHANGED')
    return root, manifest


def _guard_edge(*, pointer_path, manifest, expected_active_id, switch_mode):
    root, annual = _edge()
    need(pointer_path == root / 'outputs/active_publication.json', 'ANNUAL_SWITCH_ROOT_CHANGED')
    need((switch_mode == 'COMMIT' and manifest == annual and expected_active_id == annual['previous_publication_id'])
         or (switch_mode == 'ROLLBACK' and manifest['publication_id'] == annual['previous_publication_id']
             and expected_active_id == annual['publication_id']), 'ANNUAL_SWITCH_EDGE_CHANGED')
    return root


def guard_switch(*, pointer_path, manifest, expected_active_id, switch_mode):
    root = _guard_edge(pointer_path=pointer_path, manifest=manifest,
        expected_active_id=expected_active_id, switch_mode=switch_mode)
    current = root / 'outputs/publications' / expected_active_id
    pub.verify_publication_bundle(bundle_dir=current)
    for relative, target in pub.ROOT_MIRROR_RELATIVE_PATHS.items():
        need((root / target).read_bytes() == (current / relative).read_bytes(), 'ANNUAL_SWITCH_ACTIVE_MIRROR_DRIFT')


def guard_recovery(*, pointer_path, intent):
    root, _ = _edge()
    target = intent['proposed_pointer']['publication_id']
    _guard_edge(pointer_path=pointer_path, manifest=read(root / 'outputs/publications' / target, 'publication_manifest.json'),
        expected_active_id=None if intent['previous_pointer'] is None else intent['previous_pointer']['publication_id'],
        switch_mode=intent['switch_mode'])


def guard_mirror_repair(*, publication_root):
    root, _ = _edge()
    need(publication_root == root, 'ANNUAL_REPAIR_ROOT_CHANGED')


def switch(*, publication_root, publication_id, operation):
    root = safe_root(publication_root); _marker(root)
    need(operation in {'publish', 'rollback', 'restore', 'recover'}, 'ANNUAL_SWITCH_OPERATION_INVALID')
    need(pub.PUBLICATION_ID_PATTERN.fullmatch(publication_id) is not None, 'ANNUAL_PUBLICATION_ID_INVALID')
    directory = root / 'outputs/publications' / publication_id
    manifest = pub.verify_publication_bundle(bundle_dir=directory)
    need(manifest['record_type'] == ANNUAL_PUBLICATION_MANIFEST_TYPE, 'ANNUAL_SWITCH_REQUIRES_ADOPTION')
    pin = _Verified(_FACTORY, manifest)
    token = _switch.set((_FACTORY, root, manifest))
    try:
        with _verified(pin):
            if operation == 'recover':
                pub.recover_publication_mirrors(publication_root=root)
            else:
                current = pub.PublicationView.open(publication_root=root).publication_id
                target = manifest['previous_publication_id'] if operation == 'rollback' else publication_id
                if current == target:
                    return {'status': 'ALREADY_ACTIVE_NO_SWITCH', 'publication_id': current, 'new_provider_paid_sec_calls': [0, 0, 0]}
                if operation == 'rollback':
                    pub.rollback_publication(publication_root=root, target_publication_id=target,
                        expected_active_publication_id=publication_id, committed_at_utc=utc())
                else:
                    pub._commit_recorded_sandbox_publication(publication_root=root, publication_id=publication_id,
                        expected_active_publication_id=manifest['previous_publication_id'], committed_at_utc=utc())
            return read_version(publication_root=root)
    finally:
        _switch.reset(token)


def read_version(*, publication_root):
    root = safe_root(publication_root); _marker(root)
    view = pub.PublicationView.open(publication_root=root)
    for relative, target in pub.ROOT_MIRROR_RELATIVE_PATHS.items():
        need((root / target).read_bytes() == view.read_bytes(relative_path=relative), 'ANNUAL_PUBLIC_MIRROR_CHANGED')
    metrics = pub._csv_rows(content=view.read_bytes(relative_path='metrics_matrix.csv'), fieldnames=pub.METRIC_FIELDS, label='Active version')
    evidence = pub._csv_rows(content=view.read_bytes(relative_path='metric_evidence.csv'), fieldnames=pub.EVIDENCE_FIELDS, label='Active evidence')
    company = policy()['company_id']
    import csv
    registry = list(csv.DictReader((ROOT / 'config/company_registry.csv').read_text().splitlines()))
    display = next(r['display_name'] for r in registry if r['company_id'] == company)
    selected = [r for r in metrics if r['company'] == display and r['metric_id'] in policy()['metric_ids']]
    source_locations = []
    if view.manifest['record_type'] == ANNUAL_PUBLICATION_MANIFEST_TYPE:
        batch = json.loads(view.read_bytes(relative_path=BATCH))
        for binding in batch['cumulative_result_bindings']:
            if binding['origin'] != 'ADOPTED_NATIVE_CANDIDATE':
                continue
            records = [json.loads(line) for line in view.read_bytes(relative_path=SNAPSHOT + '/' + binding['snapshot_run_path'] + '/records.jsonl').decode().splitlines() if line]
            raw = {r['raw_asset_id']: r for r in records if r['record_type'] == 'RAW_BLOB'}
            for source in (r for r in records if r['record_type'] == 'SOURCE_REFERENCE'):
                blob = raw[source['raw_asset_id']]
                relative = SNAPSHOT + '/data/' + blob['storage_uri']
                content = view.read_bytes(relative_path=relative)
                need(sha256_bytes(content=content) == blob['raw_asset_id'].split(':')[1], 'ANNUAL_READ_SOURCE_BYTES_CHANGED')
                source_locations.append({'metric_id': binding['metric_id'], 'source_reference': source,
                    'original_storage_uri': blob['storage_uri'], 'bundle_relative_path': relative,
                    'sha256': sha256_bytes(content=content), 'size': len(content), 'verified_via': 'PublicationView.read_bytes'})
    return {'status': 'READABLE_COMPLETE_ISOLATED_VERSION', 'publication_id': view.publication_id,
        'previous_publication_id': view.manifest['previous_publication_id'], 'public_row_count': len(metrics),
        'selected_rows': selected, 'verified_source_locations': source_locations, 'selected_evidence': [r for r in evidence if r['company'] == display and r['metric_id'] in policy()['metric_ids']],
        'publication_credit': view.manifest.get('publication_credit', 'HISTORICAL_PREDECESSOR_COPY'),
        'new_provider_paid_sec_calls': [0, 0, 0]}
