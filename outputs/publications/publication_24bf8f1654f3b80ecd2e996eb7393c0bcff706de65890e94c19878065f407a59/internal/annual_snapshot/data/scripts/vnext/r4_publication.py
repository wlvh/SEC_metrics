"""R4 release composition, immutable replay and authorized pointer operations.

The mutable publication root and the frozen qualification authority root are
different objects. R4 -> R3 -> R4 never changes the R3 snapshot against which
the fifteen qualification Runs were replayed. Recorded rehearsals use the
same primitives but an unexported, isolated-root capability, with no credit.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
import re
import subprocess

from . import publication as pub
from .canonical import atomic_write_bytes, canonical_json_bytes, content_hash, parse_utc_timestamp
from .canonical import sha256_bytes, strict_json_file, strict_json_loads
from .r4_release import ACTIVATION_PATH, RELEASE_PLAN_PATH, RELEASE_RUNTIME, REPOSITORY_ROOT
from .r4_release import R4ReleaseContext, _binding, _file, _git, _oid, _plain, _require, _self_id
from .r4_release import _portable_context_document, _read_portable_release_context, _safe_rehearsal_root
from .r4_release import validate_r4_release_context
from .records import R4_PUBLICATION_MANIFEST_TYPE, validate_record

AUTHORITY_ROOT = 'internal/r4_authority'
RELEASE_RECEIPT = 'internal/r4_release_receipt.json'
CONTEXT_DOCUMENT = 'internal/r4_context.json'
BATCH_DOCUMENT = 'internal/r4_batch.json'
COMPATIBILITY_DOCUMENT = 'internal/r4_compatibility.json'
LOCATOR_DOCUMENT = 'internal/r4_request_locator_provenance.json'
REHEARSAL_CREDIT = 'NONE_RECORDED_REHEARSAL'
_FACTORY = object()
_verification = ContextVar('r4_publication_verified_scope', default=None)
_mutation = ContextVar('r4_publication_mutation_scope', default=None)


def _json_bytes(value):
    return canonical_json_bytes(value=value) + b'\n'


def _record(body, identity):
    return {**body, identity: content_hash(value=body)}


def _files_in(root, directory):
    _require(directory.is_dir() and not directory.is_symlink(), 'R4 closure directory is unsafe')
    result = set()
    for path in directory.rglob('*'):
        _require(not path.is_symlink(), 'R4 closure cannot contain symlinks')
        if path.is_file():
            result.add(path.relative_to(root).as_posix())
        else:
            _require(path.is_dir(), 'R4 closure cannot contain special entries')
    return result


def _workspace(context):
    return context.root / RELEASE_RUNTIME / _oid(context.release_context_id)


def _authority_files(context, projection):
    """Exact transitive immutable inputs, not a copy of a mutable checkout."""
    paths = set(context._execution._session._base_files)
    paths.update(strict_json_loads(text=context._execution._historical_files.decode()))
    paths.update(context.requirement['execution_authority']['files'])
    paths.add(RELEASE_PLAN_PATH)
    paths.update({'outputs/active_publication.json', 'outputs/active_publication.json.lock'})
    paths.update(_files_in(context.root, context.root / 'outputs/publication_switch_receipts'))
    from .r4_live_authority import RUNTIME_ROOT
    namespace = RUNTIME_ROOT + '/' + _oid(context._pending['pending_plan_id'])
    paths.update(_files_in(context.root, context.root / namespace))
    for directory in projection['structural_run_dirs']:
        paths.update(_files_in(context.root, directory))
    if context.mode == 'LIVE':
        paths.add(ACTIVATION_PATH)
    # The frozen workers/scanners run from this authority's own scripts/tools.
    # Static dependencies and policy data are already in execution_authority;
    # Python package markers must also be present for standalone imports.
    paths.update(relative for relative in ('scripts/__init__.py', 'scripts/vnext/__init__.py', 'tools/__init__.py')
                 if (context.root / relative).is_file())
    return {relative: _file(context.root, relative).read_bytes() for relative in sorted(paths)}


def _ledger(context, projection):
    """Use the existing immutable-attempt and ordered-ledger verifier."""
    from sec_http import parse_request_log_rows, request_log_attempt_id, request_log_prefix_bytes
    from sec_http import validate_request_log_manifest
    log = _file(context.root, 'evidence/requests_log.csv')
    validate_request_log_manifest(log_path=log)
    text = log.read_text(encoding='utf-8')
    rows = parse_request_log_rows(text=text)
    attempts = {request_log_attempt_id(row_index=i, row=row): (i, row) for i, row in enumerate(rows)}
    _require(len(attempts) == len(rows), 'R4 request ledger has duplicate attempt identities')
    indexes = projection['record_indexes']
    sources = [indexes['sources'][key] for key in sorted(indexes['used_source_reference_ids'])]
    tier = pub.FORMAL_VALIDATION_MODE if context.mode == 'LIVE' else pub.RECORDED_VALIDATION_MODE
    verified = [pub._request_row_for_source(repo_root=context.root, source=source,
        attempt_rows=attempts, validation_tier=tier) for source in sources]
    _require(verified and all(proof['locator_class'] == 'IMMUTABLE_ATTEMPT' for _, proof in verified),
             'R4 public values require immutable SEC request attempts')
    used = sorted({(row, source['request_attempt_id']) for source, (row, _) in zip(sources, verified)})
    count = max(row for row, _ in used) + 1
    provenance = pub._request_locator_provenance(validation_tier=tier, source_proofs=[p for _, p in verified])
    binding = {'request_locator_classes': provenance['request_locator_classes'],
        'request_locator_proof_id': provenance['request_locator_proof_id'], 'request_locator_tier': tier,
        'requests_log_prefix_sha256': sha256_bytes(content=request_log_prefix_bytes(text=text, row_count=count)),
        'row_count': count, 'source_reference_ids': [s['source_reference_id'] for s in sources],
        'used_request_attempt_ids': [identity for _, identity in used]}
    return binding, provenance


def _public_files(context, projection, ledger, *, scans=None):
    """Regenerate all public bytes from native Results and actually run gates."""
    files = dict(projection['files'])
    metrics = pub._csv_rows(content=files['metrics_matrix.csv'], fieldnames=pub.METRIC_FIELDS, label='R4 matrix')
    evidence = pub._csv_rows(content=files['metric_evidence.csv'], fieldnames=pub.EVIDENCE_FIELDS, label='R4 Evidence')
    _require(len({(r['company'], r['metric_id']) for r in metrics}) == len(metrics), 'Public keys are duplicated')
    evidence_keys = {(r['company'], r['metric_id']) for r in evidence}
    _require(all(not r['value'] or (r['company'], r['metric_id']) in evidence_keys for r in metrics),
             'Numeric public Result lacks Evidence')
    proof = projection['completeness_proof']
    expected_counts = {'production_result_count': 6, 'structural_result_count': 54, 'delta_result_count': 60,
        'predecessor_result_count': 240, 'cumulative_result_count': 300,
        'structural_source_count': 0, 'structural_ai_attempt_count': 0}
    _require(all(proof[key] == value for key, value in expected_counts.items()), 'R4 public count proof differs')
    compatibility = projection['compatibility_receipt']
    _require(compatibility['status'] == 'PASS' and compatibility['strict_historical_anchor_count'] == 4
             and compatibility['approved_native_backfill_count'] == 2, 'R4 compatibility is incomplete')
    golden = [{'assertion_id': 'R4_' + key.upper(), 'description': key,
        'expected': str(value), 'actual': str(proof[key]), 'status': 'PASS',
        'evidence_path': BATCH_DOCUMENT, 'notes': 'Native registry/Spec/Run exact set; not a model accuracy claim.'}
        for key, value in sorted(expected_counts.items())]
    golden.append({'assertion_id': 'R4_STRICT_ANCHORS', 'description': 'Independent retained anchor exact value/unit/period',
        'expected': '4', 'actual': str(compatibility['strict_historical_anchor_count']), 'status': 'PASS',
        'evidence_path': COMPATIBILITY_DOCUMENT, 'notes': 'A09/A13 use approved native backfill, not invented legacy anchors.'})
    files['golden_results.csv'] = pub._csv_bytes(rows=golden, fieldnames=pub.GOLDEN_FIELDS)
    files['coverage_matrix.csv'] = pub._csv_bytes(rows=pub._expected_coverage_rows(metrics=metrics, evidence=evidence),
                                                 fieldnames=pub.COVERAGE_FIELDS)
    files['stratified_audit.csv'] = pub._csv_bytes(rows=pub._expected_stratified_rows(metrics=metrics, evidence=evidence,
        migrated_ids=set(context.release_plan['cumulative_metric_ids'])), fieldnames=pub.STRATIFIED_FIELDS)
    if scans is None:
        scans = {'semantic': pub._execute_semantic_audit(repo_root=context.root),
                 'scalability': pub._execute_scalability_audit(repo_root=context.root)}
    _require(scans['semantic']['status'] == 'PASS' and scans['semantic']['hits'] == [], 'R4 semantic audit failed')
    pub._verify_semantic_source_hashes(source_hashes=scans['semantic']['source_hashes'], repo_root=context.root)
    _require(not any(row.get('allowed') not in {'1', 'true', 'True'} for row in scans['scalability']),
             'R4 scalability audit failed')
    files['semantic_audit_receipt.json'] = _json_bytes(scans['semantic'])
    files['scalability_audit.csv'] = pub._csv_bytes(rows=scans['scalability'], fieldnames=pub.SCALABILITY_FIELDS)
    # Retained predecessor proof remains historical bytes. The R4 projection
    # and compatibility receipts explicitly own the new sixty coordinates.
    files['legacy_invariant_migration_receipt.json'] = context.predecessor.read_bytes(
        relative_path='legacy_invariant_migration_receipt.json')
    projection_receipt = projection['projection_receipt']
    projection_body = _record({'record_type': 'R4_PUBLIC_PROJECTION_MANIFEST', 'schema_version': 1,
        'artifact_requirement_generation': 'EXPLICIT_REQUIREMENT_V1',
        'projection_receipt': projection_receipt, 'batch_manifest_id': projection['batch_manifest']['batch_manifest_id'],
        'release_context_id': context.release_context_id, 'requirement_id': context.requirement['requirement_id'],
        'requirement_closure_hash': context.requirement['requirement_closure_hash'],
        'requirement_hashes': context.requirement['hashes'],
        'historical_retirement_receipt_role': 'R3_HISTORICAL_ONLY',
        'r4_compatibility_receipt_id': compatibility['compatibility_receipt_id']}, 'projection_manifest_id')
    files['projection_manifest.json'] = _json_bytes(projection_body)
    live = context.mode == 'LIVE'
    mode, result = (pub.FORMAL_VALIDATION_MODE, 'PASSED') if live else (pub.RECORDED_VALIDATION_MODE, 'PASSED_RECORDED_ONLY')
    credit = 'ELIGIBLE_PENDING_RELEASE_OWNER_AUTHORIZATION' if live else REHEARSAL_CREDIT
    validation = {
        'run_id': 'validation:' + projection_body['projection_manifest_id'], 'mode': mode, 'result': result,
        'source_commit': context.proof['source_commit'], 'started_at_utc': context.proof['validation_started_at_utc'],
        'refreshed_artifacts': sorted(pub.REQUIRED_BUNDLE_FILES - {'legacy_invariant_migration_receipt.json'}),
        'not_refreshed_artifacts': ['legacy_invariant_migration_receipt.json']}
    files['validation_run_manifest.json'] = _json_bytes(validation)
    checks = {key: 'PASS' for key in ('NATIVE_6_PLUS_54', 'CUMULATIVE_300', 'STRICT_COMPATIBILITY',
        'IMMUTABLE_REQUEST_LOCATORS', 'SEMANTIC_AUDIT', 'SCALABILITY_AUDIT', 'QUALIFICATION_AGGREGATE_REPLAY')}
    files['repair_validation_results.csv'] = pub._csv_bytes(rows=[{'check_id': key, 'severity': 'ERROR',
        'status': value, 'details': 'Recomputed against the exact R4 release context; no repair performed.'}
        for key, value in sorted(checks.items())], fieldnames=pub.REPAIR_FIELDS)
    header = ['# R4 successor publication', '',
        'Formal only after an authorized active switch.' if live else 'RECORDED REHEARSAL ONLY; no qualification/publication credit.',
        '', '- run_id: `' + validation['run_id'] + '`', '- result: `' + result + '`',
        '- Requirement: `' + context.requirement['requirement_closure_hash'] + '`',
        '- Native R4 coordinates: 6 applicable + 54 structural; cumulative vNext coordinates: 300.',
        '- Alternate-layout and stability results remain qualification evidence only.', '',
        '| Company | Metric | Value | Unit | Status |', '|---|---|---:|---|---|']
    header.extend('| ' + ' | '.join(pub._markdown_cell(value=row[key]) for key in
        ('company', 'metric_id', 'value', 'unit', 'status')) + ' |' for row in metrics)
    files['REPORT_十公司财务指标.md'] = ('\n'.join(header) + '\n').encode()
    files['README_RUN.md'] = ('# R4 immutable result reader\n\n'
        + ('LIVE release candidate; only the verified active pointer grants current publication status.\n' if live
           else 'NONE_RECORDED_REHEARSAL: synthetic transport is not live qualification or publication evidence.\n')
        + '\nUse the frozen R4 release CLI read-back and active-terminal commands. '
        + 'The exact fifteen-Run aggregate, six selected values and fifty-four native N/A terminals '
        + 'are retained in the immutable authority closure.\n').encode()
    receipt = _record({'record_type': 'R4_PUBLICATION_VALIDATION_RECEIPT', 'schema_version': 1,
        'artifact_requirement_generation': 'EXPLICIT_REQUIREMENT_V1',
        'requirement_id': context.requirement['requirement_id'],
        'requirement_closure_hash': context.requirement['requirement_closure_hash'],
        'requirement_hashes': context.requirement['hashes'],
        'status': result, 'release_context_id': context.release_context_id,
        'release_stage': 'R4', 'final_all_metric_cutover': False,
        'batch_manifest_id': projection['batch_manifest']['batch_manifest_id'],
        'projection_manifest_id': projection_body['projection_manifest_id'],
        'publication_credit': credit, 'checks': checks, 'ledger_binding': ledger,
        'artifacts': {path: {'sha256': sha256_bytes(content=data), 'size': len(data)}
                      for path, data in sorted(files.items())}}, 'validation_receipt_id')
    files['publication_validation_receipt.json'] = _json_bytes(receipt)
    _require(set(files) == pub.REQUIRED_BUNDLE_FILES, 'R4 public artifact exact set differs')
    return files, receipt, scans


@dataclass(frozen=True, init=False)
class _VerifiedBundle:
    factory: object
    manifest: bytes
    _context_bytes: bytes
    _receipt_bytes: bytes

    def __init__(self, *, factory, manifest, context_document, receipt):
        _require(factory is _FACTORY, 'R4 verification pin requires native preparation or replay')
        object.__setattr__(self, 'factory', factory)
        object.__setattr__(self, 'manifest', canonical_json_bytes(value=manifest))
        object.__setattr__(self, '_context_bytes', canonical_json_bytes(value=context_document))
        object.__setattr__(self, '_receipt_bytes', canonical_json_bytes(value=receipt))

    @property
    def context_document(self): return strict_json_loads(text=self._context_bytes.decode())
    @property
    def receipt(self): return strict_json_loads(text=self._receipt_bytes.decode())


@contextmanager
def _pinned(pin):
    _require(type(pin) is _VerifiedBundle and pin.factory is _FACTORY, 'R4 verification pin is invalid')
    token = _verification.set(pin)
    try:
        yield pin
    finally:
        _verification.reset(token)


def _release_receipt(context, projection, public_files, ledger, authority):
    return _record({'record_type': 'R4_RELEASE_RECEIPT', 'schema_version': 1,
        'artifact_requirement_generation': 'EXPLICIT_REQUIREMENT_V1',
        'release_context_id': context.release_context_id,
        'requirement_id': context.requirement['requirement_id'],
        'requirement_closure_hash': context.requirement['requirement_closure_hash'],
        'requirement_hashes': context.requirement['hashes'], 'mode': context.mode,
        'qualification_credit': context.proof['qualification_credit'],
        'publication_credit': 'LIVE' if context.mode == 'LIVE' else REHEARSAL_CREDIT,
        'predecessor_publication_id': context.predecessor.publication_id,
        'batch_manifest_id': projection['batch_manifest']['batch_manifest_id'],
        'projection_manifest_id': strict_json_loads(text=public_files['projection_manifest.json'].decode())['projection_manifest_id'],
        'compatibility_receipt_id': projection['compatibility_receipt']['compatibility_receipt_id'],
        'completeness_proof': projection['completeness_proof'], 'ledger_binding': ledger,
        'public_artifacts': {path: {'sha256': sha256_bytes(content=data), 'size': len(data)}
                             for path, data in sorted(public_files.items())},
        'authority_root': AUTHORITY_ROOT,
        'authority_files': {path: {'sha256': sha256_bytes(content=data), 'size': len(data)}
                            for path, data in sorted(authority.items())},
        'projection_workspace': _workspace(context).relative_to(context.root).as_posix(),
        'response_reuse_authorized': False, 'release_preparation_egress': [0, 0, 0]}, 'release_receipt_id')


def stage_r4_release(*, context):
    """Repository factory only; staging cannot change the active pointer/mirrors."""
    context = validate_r4_release_context(context)
    _require(not context._read_only, 'Portable read-back context cannot stage a publication')
    before = pub.publication_state_snapshot(publication_root=context.root)
    from .r4_projection import build_r4_projection
    projection = build_r4_projection(context, _workspace(context))
    ledger, provenance = _ledger(context, projection)
    public, validation, _ = _public_files(context, projection, ledger)
    authority = _authority_files(context, projection)
    document = _portable_context_document(context)
    receipt = _release_receipt(context, projection, public, ledger, authority)
    files = {**public, RELEASE_RECEIPT: _json_bytes(receipt), CONTEXT_DOCUMENT: _json_bytes(document),
        BATCH_DOCUMENT: _json_bytes(projection['batch_manifest']),
        COMPATIBILITY_DOCUMENT: _json_bytes(projection['compatibility_receipt']),
        LOCATOR_DOCUMENT: _json_bytes(provenance),
        **{AUTHORITY_ROOT + '/' + path: data for path, data in authority.items()}}
    identity = {'candidate_status': 'PUBLISHABLE', 'requirement_hashes': context.requirement['hashes'],
        'batch_manifest_id': projection['batch_manifest']['batch_manifest_id'],
        'projection_manifest_id': validation['projection_manifest_id'],
        'validation_receipt_id': validation['validation_receipt_id'], 'ledger_binding': ledger,
        'previous_publication_id': context.predecessor.publication_id,
        'artifact_requirement_generation': 'EXPLICIT_REQUIREMENT_V1',
        'requirement_id': context.requirement['requirement_id'],
        'requirement_closure_hash': context.requirement['requirement_closure_hash'],
        'projection_requirement_hashes': context.requirement['hashes'],
        'r4_release_receipt_id': receipt['release_receipt_id'], 'publication_credit': receipt['publication_credit'],
        'files': [{'path': path, 'sha256': sha256_bytes(content=data), 'size': len(data)} for path, data in sorted(files.items())]}
    manifest = validate_record(record={'record_type': R4_PUBLICATION_MANIFEST_TYPE,
        'publication_id': 'publication_' + _oid(content_hash(value=identity)), **identity})
    pub._validate_publication_metadata(**{key: identity[key] for key in ('requirement_hashes', 'batch_manifest_id',
        'projection_manifest_id', 'validation_receipt_id', 'ledger_binding', 'previous_publication_id')})
    pin = _VerifiedBundle(factory=_FACTORY, manifest=manifest, context_document=document, receipt=receipt)
    with _pinned(pin):
        pub._persist_prepared_publication_bundle(publications_dir=context.root / 'outputs/publications',
                                                files=files, manifest=manifest)
    validate_r4_release_context(context)
    _require(pub.publication_state_snapshot(publication_root=context.root) == before,
             'R4 staging changed the active pointer or public mirrors')
    return {'manifest': manifest, 'receipt': receipt, 'pin': pin}


def verify_r4_bundle(*, bundle_dir, manifest):
    """Called only after generic exact-tree/hash/self-ID validation."""
    pin = _verification.get()
    if (type(pin) is _VerifiedBundle and pin.factory is _FACTORY
            and canonical_json_bytes(value=manifest) == pin.manifest):
        return manifest
    receipt = strict_json_file(path=bundle_dir / RELEASE_RECEIPT)
    document = strict_json_file(path=bundle_dir / CONTEXT_DOCUMENT)
    _self_id(receipt, 'release_receipt_id')
    _require(receipt['authority_root'] == AUTHORITY_ROOT
             and receipt['publication_credit'] == manifest['publication_credit']
             and receipt['release_receipt_id'] == manifest['r4_release_receipt_id'], 'R4 immutable receipt differs')
    declared = {row['path']: {key: row[key] for key in ('sha256', 'size')} for row in manifest['files']}
    _require(set(receipt['public_artifacts']) == pub.REQUIRED_BUNDLE_FILES
             and all(declared.get(path) == bound for path, bound in receipt['public_artifacts'].items())
             and all(declared.get(AUTHORITY_ROOT + '/' + path) == bound
                     for path, bound in receipt['authority_files'].items()), 'R4 receipt file bindings differ')
    context = _read_portable_release_context(repo_root=bundle_dir / AUTHORITY_ROOT, document=document)
    from .r4_projection import build_r4_projection
    projection = build_r4_projection(context, _workspace(context))
    ledger, provenance = _ledger(context, projection)
    public, validation, _ = _public_files(context, projection, ledger)
    authority = _authority_files(context, projection)
    _require(_release_receipt(context, projection, public, ledger, authority) == receipt,
             'R4 portable release composition differs')
    expected_internal = {RELEASE_RECEIPT: receipt, CONTEXT_DOCUMENT: document,
        BATCH_DOCUMENT: projection['batch_manifest'], COMPATIBILITY_DOCUMENT: projection['compatibility_receipt'],
        LOCATOR_DOCUMENT: provenance}
    expected_paths = set(public) | set(expected_internal) | {AUTHORITY_ROOT + '/' + path for path in authority}
    _require({row['path'] for row in manifest['files']} == expected_paths, 'R4 portable closure exact set differs')
    for path, data in public.items():
        _require((bundle_dir / path).read_bytes() == data, 'R4 portable public bytes differ: ' + path)
    for path, value in expected_internal.items():
        _require((bundle_dir / path).read_bytes() == _json_bytes(value), 'R4 portable artifact differs: ' + path)
    requirement = context.requirement
    _require(manifest['requirement_id'] == requirement['requirement_id']
             and manifest['requirement_closure_hash'] == requirement['requirement_closure_hash']
             and manifest['requirement_hashes'] == manifest['projection_requirement_hashes'] == requirement['hashes']
             and manifest['previous_publication_id'] == context.predecessor.publication_id
             and manifest['batch_manifest_id'] == projection['batch_manifest']['batch_manifest_id']
             and manifest['projection_manifest_id'] == validation['projection_manifest_id']
             and manifest['validation_receipt_id'] == validation['validation_receipt_id']
             and manifest['ledger_binding'] == ledger and manifest['publication_credit'] == receipt['publication_credit'],
             'R4 PublicationManifest semantic authority differs')
    return manifest


def validate_r4_release(*, publication_root, publication_id):
    _require(pub.PUBLICATION_ID_PATTERN.fullmatch(publication_id) is not None, 'R4 publication ID is invalid')
    directory = publication_root / 'outputs/publications' / publication_id
    manifest = pub.verify_publication_bundle(bundle_dir=directory)
    _require(manifest['record_type'] == R4_PUBLICATION_MANIFEST_TYPE, 'Release is not an R4 successor publication')
    return _VerifiedBundle(factory=_FACTORY, manifest=manifest,
        context_document=strict_json_file(path=directory / CONTEXT_DOCUMENT),
        receipt=strict_json_file(path=directory / RELEASE_RECEIPT))


def commit_authority(*, bundle_dir, manifest):
    verify_r4_bundle(bundle_dir=bundle_dir, manifest=manifest)
    if manifest['publication_credit'] == REHEARSAL_CREDIT:
        return pub.RECORDED_COMMIT_AUTHORITY
    _require(manifest['publication_credit'] == 'LIVE', 'R4 publication credit is invalid')
    return pub.FORMAL_COMMIT_AUTHORITY


@dataclass(frozen=True, init=False)
class _SwitchAuthority:
    factory: object
    root: Path
    pin: _VerifiedBundle
    _owner_bytes: bytes
    recorded: bool

    def __init__(self, *, factory, root, pin, owner_receipt, recorded):
        _require(factory is _FACTORY, 'R4 pointer switch requires repository preflight')
        for key, value in {'factory': factory, 'root': root, 'pin': pin, 'recorded': recorded,
                           '_owner_bytes': canonical_json_bytes(value=owner_receipt)}.items():
            object.__setattr__(self, key, value)

    @property
    def owner_receipt(self): return strict_json_loads(text=self._owner_bytes.decode())


@contextmanager
def _switch_scope(authority):
    _check_switch_authority(authority)
    token = _mutation.set(authority)
    try:
        with _pinned(authority.pin):
            yield
    finally:
        _mutation.reset(token)


def _check_switch_authority(authority):
    _require(type(authority) is _SwitchAuthority and authority.factory is _FACTORY,
             'R4 publication/rollback/repair requires a private release authorization')
    pin = authority.pin
    _require(type(pin) is _VerifiedBundle and pin.factory is _FACTORY, 'Switch has no verified release closure')
    manifest = strict_json_loads(text=pin.manifest.decode())
    if authority.recorded:
        _safe_rehearsal_root(authority.root)
        _require(manifest['publication_credit'] == REHEARSAL_CREDIT and authority.owner_receipt is None,
                 'Recorded rehearsal cannot acquire LIVE publication authority')
    else:
        _require(authority.root == REPOSITORY_ROOT.resolve() and manifest['publication_credit'] == 'LIVE',
                 'LIVE switch cannot consume recorded or foreign-root authority')
        receipt = authority.owner_receipt
        _self_id(receipt, 'receipt_id')
        expected = expected_release_owner_approval(manifest=manifest,
            exact_head=receipt['exact_head'], exact_tree=receipt['exact_tree'])
        _require(all(receipt.get(key) == value for key, value in expected.items())
                 and strict_json_loads(text=receipt['approval_text']) == expected
                 and receipt['approval_text_sha256'] == sha256_bytes(content=receipt['approval_text'].encode()),
                 'Release owner approval cannot be retargeted to another publication')
        _require(_git(authority.root, 'rev-parse', 'HEAD') == receipt['exact_head']
                 and _git(authority.root, 'rev-parse', 'HEAD^{tree}') == receipt['exact_tree'],
                 'Release owner exact head/tree changed')
        from .requirement_profile import validate_execution_authority
        from .requirements import load_requirement_snapshot
        requirement = load_requirement_snapshot(snapshot_dir=authority.root / 'requirements' / manifest['requirement_id'])
        validate_execution_authority(repo_root=authority.root, requirement=requirement)
        _require(requirement['requirement_closure_hash'] == manifest['requirement_closure_hash'],
                 'Release current Requirement closure changed')
        expected_python = {path for path in requirement['execution_authority']['files']
                           if path.endswith('.py') and path.startswith(('scripts/', 'tools/'))}
        actual_python = {path for prefix in ('scripts', 'tools')
                         for path in _files_in(authority.root, authority.root / prefix) if path.endswith('.py')}
        _require(actual_python == expected_python, 'PR-C production Python exact set changed')
    # The bundle is the frozen interpretation, but current qualification inputs
    # may not drift between stage/read-back and the actual pointer transaction.
    # Only mirrors/pointer intentionally evolve across publish/rollback/restore.
    ignored = set(pub.ROOT_MIRROR_RELATIVE_PATHS.values()) | {
        'outputs/active_publication.json', 'outputs/active_publication.json.lock'}
    bindings = pin.receipt['authority_files']
    for relative, expected in bindings.items():
        if relative not in ignored:
            _require(_binding(_file(authority.root, relative)) == expected,
                     'R4 staged authority changed before switch: ' + relative)
    from .r4_live_authority import RUNTIME_ROOT
    namespace = RUNTIME_ROOT + '/' + _oid(pin.context_document['pending_plan']['pending_plan_id'])
    _require(_files_in(authority.root, authority.root / namespace)
             == {path for path in bindings if path.startswith(namespace + '/')},
             'R4 qualification exact file set changed after staging')


def _guard_edge(*, pointer_path, manifest, expected_active_id, switch_mode):
    authority = _mutation.get()
    _check_switch_authority(authority)
    _require(pointer_path == authority.root / 'outputs/active_publication.json', 'R4 pointer root substitution')
    r4 = strict_json_loads(text=authority.pin.manifest.decode())
    predecessor = r4['previous_publication_id']
    target = manifest['publication_id']
    _require((switch_mode == 'COMMIT' and target == r4['publication_id'] and expected_active_id == predecessor)
             or (switch_mode == 'ROLLBACK' and target == predecessor and expected_active_id == r4['publication_id']),
             'R4 switch does not match the authorized exact R4/R3 edge')
    if target == r4['publication_id']:
        _require(manifest == r4, 'R4 switch manifest drift')


def guard_switch(*, pointer_path, manifest, expected_active_id, switch_mode):
    _guard_edge(pointer_path=pointer_path, manifest=manifest,
                expected_active_id=expected_active_id, switch_mode=switch_mode)
    authority = _mutation.get()
    # Already under the native exclusive lock: do not reopen a shared lock.
    # A normal rollback/restore must not silently repair a corrupted mirror.
    current = authority.root / 'outputs/publications' / expected_active_id
    pub.verify_publication_bundle(bundle_dir=current)
    for relative, path in pub.ROOT_MIRROR_RELATIVE_PATHS.items():
        _require(_file(authority.root, path).read_bytes() == (current / relative).read_bytes(),
                 'R4 switch encountered active mirror drift: ' + path)


def guard_recovery(*, pointer_path, intent):
    authority = _mutation.get()
    _check_switch_authority(authority)
    target = intent['proposed_pointer']['publication_id']
    manifest = strict_json_file(path=authority.root / 'outputs/publications' / target / 'publication_manifest.json')
    previous = intent['previous_pointer']
    _guard_edge(pointer_path=pointer_path, manifest=manifest,
        expected_active_id=None if previous is None else previous['publication_id'], switch_mode=intent['switch_mode'])


def guard_mirror_repair(*, publication_root):
    authority = _mutation.get()
    _check_switch_authority(authority)
    _require(publication_root.resolve() == authority.root, 'R4 mirror repair root differs')


def _rehearsal_authority(*, publication_root, pin):
    return _SwitchAuthority(factory=_FACTORY, root=_safe_rehearsal_root(publication_root), pin=pin,
                            owner_receipt=None, recorded=True)


def expected_release_owner_approval(*, manifest, exact_head, exact_tree):
    """Future PR-C switch authorization, not provider/live qualification approval."""
    return {'decision': 'AUTHORIZE_R4_RELEASE_EXACT_HEAD', 'scope': 'R4_PUBLICATION_ROLLBACK_RESTORE_ONLY',
        'exact_head': exact_head, 'exact_tree': exact_tree, 'requirement_id': manifest['requirement_id'],
        'requirement_closure_hash': manifest['requirement_closure_hash'],
        'publication_id': manifest['publication_id'], 'r4_release_receipt_id': manifest['r4_release_receipt_id'],
        'predecessor_publication_id': manifest['previous_publication_id'],
        'allowed_operations': ['publish', 'rollback-to-R3', 'restore-R4', 'recover-mirrors'],
        'provider_paid_sec_authorized': False}


def verify_release_owner_comment(*, publication_root, pin, source_url):
    """Fresh real owner provenance is necessary for every mutating CLI process."""
    root = publication_root.resolve(strict=True)
    _require(root == REPOSITORY_ROOT.resolve(), 'R4 owner preflight requires the implementation root')
    manifest = strict_json_loads(text=pin.manifest.decode())
    _require(manifest['publication_credit'] == 'LIVE', 'Recorded Runs cannot receive real publication credit')
    document = pin.context_document
    _require(document['proof']['release_mode'] == 'LIVE' and document['activation'] is not None
             and document['owner'] is not None, 'R4 live aggregate/transition evidence is absent')
    # Recheck the merged implementation from actual Git, not portable claims.
    from .requirements import load_requirement_snapshot
    from .r4_release import _merged_implementation
    requirement = load_requirement_snapshot(snapshot_dir=root / 'requirements' / manifest['requirement_id'])
    _require(strict_json_file(path=_file(root, 'docs/evidence/' + manifest['requirement_id'] + '_transition_activation.json')) == document['activation'],
             'Current transition activation differs from the frozen release')
    merged = _merged_implementation(root, requirement, document['activation'],
        document['proof']['implementation']['commit'], document['owner'], require_clean=False)
    _require(merged == document['proof']['implementation'], 'R4 merged implementation proof drift')
    repository = requirement['baseline']['repository']['identity']
    match = re.fullmatch(r'https://github\.com/' + re.escape(repository)
        + r'/pull/([1-9][0-9]*)#issuecomment-([1-9][0-9]*)', source_url)
    _require(match is not None, 'R4 release authorization needs an exact PR owner comment URL')
    state = {'head': _git(root, 'rev-parse', 'HEAD'), 'tree': _git(root, 'rev-parse', 'HEAD^{tree}')}
    def github(path):
        response = subprocess.run(['gh', 'api', '--hostname', 'github.com', path], cwd=root,
                                  capture_output=True, text=True, check=False)
        _require(response.returncode == 0, 'R4 release owner provenance could not be read')
        return strict_json_loads(text=response.stdout)
    comment = github('repos/' + repository + '/issues/comments/' + match.group(2))
    pull = github('repos/' + repository + '/pulls/' + match.group(1))
    _require(comment.get('html_url') == source_url and str(comment.get('id')) == match.group(2)
             and comment.get('user', {}).get('login') == repository.split('/')[0]
             and comment.get('updated_at') == comment.get('created_at')
             and pull.get('head', {}).get('sha') == state['head']
             and pull.get('head', {}).get('repo', {}).get('full_name') == repository
             and pull.get('state') == 'open' and pull.get('merged') is False
             and pull.get('base', {}).get('ref') == 'main', 'R4 owner/comment/exact open PR differs')
    parse_utc_timestamp(value=comment['created_at'])
    expected = expected_release_owner_approval(manifest=manifest, exact_head=state['head'], exact_tree=state['tree'])
    _require(strict_json_loads(text=comment['body']) == expected, 'R4 owner release approval content differs')
    # A structurally valid receipt is portable evidence, not proof that the
    # corresponding owner ever posted it. The real switch checks both earlier
    # governance records against their actual immutable GitHub comments too.
    for prior in (document['activation'], document['owner']):
        prior_match = re.fullmatch(r'https://github\.com/' + re.escape(repository)
            + r'/pull/([1-9][0-9]*)#issuecomment-([1-9][0-9]*)', prior['source_url'])
        _require(prior_match is not None, 'R4 prior owner provenance URL is invalid')
        actual = github('repos/' + repository + '/issues/comments/' + prior_match.group(2))
        _require(actual.get('html_url') == prior['source_url']
                 and actual.get('user', {}).get('login') == repository.split('/')[0]
                 and actual.get('created_at') == actual.get('updated_at') == prior['approved_at_utc']
                 and actual.get('body') == prior['approval_text'], 'R4 prior owner provenance no longer matches')
        if prior is document['activation']:
            implementation_pull = github('repos/' + repository + '/pulls/' + prior_match.group(1))
            _require(implementation_pull.get('merged') is True
                     and implementation_pull.get('merge_commit_sha') == merged['commit']
                     and implementation_pull.get('head', {}).get('sha') == prior['exact_head']
                     and implementation_pull.get('base', {}).get('ref') == 'main',
                     'R4 implementation is not the actual GitHub-approved merged PR')
    receipt = _record({'record_type': 'R4_EXACT_HEAD_RELEASE_AUTHORIZATION', 'schema_version': 1,
        **expected, 'source_url': source_url, 'owner': 'github:' + comment['user']['login'],
        'approved_at_utc': comment['created_at'], 'approval_text': comment['body'],
        'approval_text_sha256': sha256_bytes(content=comment['body'].encode())}, 'receipt_id')
    authority = _SwitchAuthority(factory=_FACTORY, root=root, pin=pin, owner_receipt=receipt, recorded=False)
    _check_switch_authority(authority)
    return authority


def switch_r4_release(*, authority, operation, committed_at_utc):
    _check_switch_authority(authority)
    _require(operation in {'publish', 'rollback-to-R3', 'restore-R4', 'recover-mirrors'}, 'Unknown R4 release operation')
    manifest = strict_json_loads(text=authority.pin.manifest.decode())
    predecessor = manifest['previous_publication_id']
    root = authority.root
    with _switch_scope(authority):
        if operation == 'recover-mirrors':
            pointer = pub.recover_publication_mirrors(publication_root=root)
        elif operation == 'rollback-to-R3':
            pointer = pub.rollback_publication(publication_root=root, target_publication_id=predecessor,
                expected_active_publication_id=manifest['publication_id'], committed_at_utc=committed_at_utc)
        else:
            function = pub._commit_recorded_sandbox_publication if authority.recorded else pub._commit_publication
            pointer = function(publication_root=root, publication_id=manifest['publication_id'],
                expected_active_publication_id=predecessor, committed_at_utc=committed_at_utc)
        expected = (predecessor if operation == 'rollback-to-R3' else manifest['publication_id']
                    if operation in {'publish', 'restore-R4'} else None)
        terminal = active_terminal(publication_root=root, pin=authority.pin, expected_publication_id=expected)
    receipt = _record({'record_type': 'R4_RELEASE_SWITCH_RESULT', 'schema_version': 1, 'operation': operation,
        'pointer': pointer, 'terminal': terminal, 'owner_release_receipt_id': None if authority.recorded
        else authority.owner_receipt['receipt_id'], 'publication_credit': REHEARSAL_CREDIT if authority.recorded else 'LIVE',
        'provider_paid_sec_calls': [0, 0, 0]}, 'receipt_id')
    return receipt


def active_terminal(*, publication_root, pin=None, expected_publication_id=None):
    if pin is not None:
        with _pinned(pin):
            result = active_terminal(publication_root=publication_root, expected_publication_id=expected_publication_id)
        manifest = strict_json_loads(text=pin.manifest.decode())
        _require(result['publication_id'] in {manifest['publication_id'], manifest['previous_publication_id']},
                 'Active terminal is outside the exact R4/R3 release edge')
        return result
    view = pub.PublicationView.open(publication_root=publication_root)
    if expected_publication_id is not None:
        _require(view.publication_id == expected_publication_id, 'Active terminal differs from the requested publication')
    mirrors = {}
    for relative, path in pub.ROOT_MIRROR_RELATIVE_PATHS.items():
        data = _file(publication_root, path).read_bytes()
        _require(data == view.read_bytes(relative_path=relative), 'Active R4/R3 mirror drift: ' + path)
        mirrors[path] = {'sha256': sha256_bytes(content=data), 'size': len(data)}
    is_r4 = view.manifest['record_type'] == R4_PUBLICATION_MANIFEST_TYPE
    credit = view.manifest['publication_credit'] if is_r4 else 'HISTORICAL_R3'
    if is_r4 and credit == 'LIVE':
        from .report import validate_active_publication
        validate_active_publication(publication_view=view, publication_root=publication_root)
    return _record({'record_type': 'R4_ACTIVE_TERMINAL_READ_BACK', 'schema_version': 1, 'status': 'PASS',
        'publication_id': view.publication_id, 'previous_publication_id': view.manifest['previous_publication_id'],
        'mirror_count': len(mirrors), 'mirrors': mirrors, 'publication_credit': credit,
        'provider_paid_sec_calls': [0, 0, 0]}, 'receipt_id')
