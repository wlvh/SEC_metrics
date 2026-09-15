"""Prepare a complete ordinary version for the existing publication chain.

This adapter replays native Runs and retains a verified predecessor. It writes
no publication manifest, permission, active pointer, or migration receipt.
"""
from pathlib import Path

from git_workspace import first_symlink_in_path
from . import normal_run_v3 as normal, publication as pub, projector
from .canonical import canonical_json_bytes, content_hash, sha256_file, strict_json_file
from .ordinary_projection import render_ordinary_run
from .ratchet_release import _copy_exact_tree, _tree_files
from .run_store import _mechanically_replay_open_run
from .sources import resolve_repository_file

MANIFEST = 'ordinary_release_preparation.json'
CREDIT = 'NONE_PREPARATION_ONLY'


def _need(condition, reason):
    if not condition:
        raise ValueError(reason)


def _external(path):
    path = Path(path)
    _need(path.is_absolute() and first_symlink_in_path(path=path) is None,
          'ORDINARY_RELEASE_ABSOLUTE_UNALIASED_ROOT_REQUIRED')
    path = path.resolve()
    _need(path != normal.ROOT and path not in normal.ROOT.parents and normal.ROOT not in path.parents,
          'ORDINARY_RELEASE_CHECKOUT_FORBIDDEN')
    _need(not any((p / '.git').exists() or (p / 'outputs/active_publication.json').exists()
                  for p in (path, *path.parents)), 'ORDINARY_RELEASE_ACTIVE_OR_CHECKOUT_ANCESTOR')
    return path


def _json(value):
    return canonical_json_bytes(value=value) + b'\n'


def _csv(view, name, fields):
    return pub._csv_rows(content=view.read_bytes(relative_path=name), fieldnames=fields, label=name)


def _result_selection_basis(*, data_root, manifest, result, rendered):
    """Use only native published results or the existing complete-scope proof.

    The caller has already replayed the complete Run and rendered its rows.
    A WITHHELD label alone never establishes a public source statement.
    """
    if result['publication'] == 'PUBLISHED':
        return 'NATIVE_PUBLISHED_RESULT'
    allowed = {
        'D04': ('D04_DEFINED_SCOPE_NO_DOUBT_DISCLOSURE', 'TEXT_QUAL'),
        'B13': ('B13_DEFINED_SCOPE_NO_RELEVANT_DISCLOSURE', 'NOT_AVAILABLE_SEC'),
    }
    expected = allowed.get(result['metric_id'])
    _need(expected is not None and result['publication'] == 'WITHHELD'
          and result['reason_code'] == expected[0]
          and result.get('value_kind') == 'TEXT_V1'
          and result['value'] is None and result.get('text_payload') is None
          and result['quality'] == 'NONE' and result['applicability'] == 'APPLICABLE',
          'ORDINARY_RELEASE_RESULT_NOT_AVAILABLE')
    from .capacity_run import project_defined_absence
    case = normal.replay_case(data_root=data_root, manifest=manifest)
    company = next(row for row in projector._load_registry(repo_root=data_root)
                   if row['company_id'] == manifest['company_id'])
    statement, evidence = project_defined_absence(case=case, result=result, row={}, company=company)
    _need(statement['status'] == expected[1]
          and rendered['row']['status'] == statement['status']
          and rendered['row']['value'] == statement['value'] == ''
          and rendered['evidence'] == evidence,
          'ORDINARY_RELEASE_DEFINED_SCOPE_PROJECTION_CHANGED')
    return 'NATIVE_REVIEWED_DEFINED_SCOPE_STATEMENT'


def _compose(root, inputs):
    _need(type(inputs) is dict and set(inputs) == {'predecessor', 'native_count'}
          and type(inputs['predecessor']) is dict
          and set(inputs['predecessor']) == {'publication_id', 'manifest_sha256'}, 'ORDINARY_RELEASE_INPUT_BINDING_FIELDS')
    identity = inputs['predecessor']['publication_id']
    _need(type(identity) is str and identity.startswith('publication_') and len(identity) == 76
          and all(c in '0123456789abcdef' for c in identity[12:]), 'ORDINARY_RELEASE_PREDECESSOR_ID_INVALID')
    predecessor = root / 'predecessor' / inputs['predecessor']['publication_id']
    _need(sha256_file(path=predecessor / 'publication_manifest.json') == inputs['predecessor']['manifest_sha256'],
          'ORDINARY_RELEASE_PREDECESSOR_CHANGED')
    manifest = pub.verify_publication_bundle(bundle_dir=predecessor)
    _need(manifest['publication_id'] == predecessor.name, 'ORDINARY_RELEASE_PREDECESSOR_ID_CHANGED')
    view = pub.PublicationView(publication_id=manifest['publication_id'], bundle_dir=predecessor, manifest=manifest)
    old_rows = _csv(view, 'metrics_matrix.csv', pub.METRIC_FIELDS)
    old_evidence = _csv(view, 'metric_evidence.csv', pub.EVIDENCE_FIELDS)
    key = lambda row: (row['company'], row['metric_id'])
    old_by_key = {key(row): row for row in old_rows}
    _need(len(old_by_key) == len(old_rows), 'ORDINARY_RELEASE_PREDECESSOR_DUPLICATE')
    registry = {r['company_id']: r for r in projector._load_registry(repo_root=normal.ROOT)}
    strategy = strict_json_file(path=normal.ROOT / 'config/source_strategy_registry.json')
    expected = {(c, m) for c in registry for m in strategy['metrics']}
    replacements, evidence_replacements, bindings, selected = {}, {}, [], set()
    _need(type(inputs['native_count']) is int and 0 < inputs['native_count'] <= len(expected),
          'ORDINARY_RELEASE_NATIVE_COUNT_INVALID')
    for ordinal in range(inputs['native_count']):
        prefix = 'native/{:03d}'.format(ordinal)
        data, run = root / prefix / 'data', root / prefix / 'run'
        native, records, _ = _mechanically_replay_open_run(run_dir=run, repo_root=data, require_complete_results=True)
        rendered = render_ordinary_run(data_root=data, run_dir=run)
        _need(native['run_id'].startswith(normal.PREFIX), 'ORDINARY_RELEASE_NATIVE_ID_INVALID')
        binding_key = native['run_id'][len(normal.PREFIX):]
        native_input = strict_json_file(path=resolve_repository_file(repo_root=data,
            repo_relative_path=normal.BINDING_DIRECTORY + '/' + binding_key + '.json'))
        _need(content_hash(value=native_input)[7:] == binding_key, 'ORDINARY_RELEASE_NATIVE_INPUT_CHANGED')
        metric = rendered['receipt']['primary_metric_id']
        coordinate = native['company_id'], metric
        _need(coordinate in expected and coordinate not in selected, 'ORDINARY_RELEASE_COORDINATE_INVALID_OR_DUPLICATE')
        selected.add(coordinate)
        results = [r for r in records if r['record_type'] == 'METRIC_RESULT' and r['metric_id'] == metric]
        _need(len(results) == 1, 'ORDINARY_RELEASE_RESULT_NOT_AVAILABLE')
        result = results[0]
        selection_basis = _result_selection_basis(data_root=data, manifest=native, result=result, rendered=rendered)
        row = rendered['row']; row_key = key(row)
        _need(row_key == (registry[coordinate[0]]['display_name'], metric), 'ORDINARY_RELEASE_PUBLIC_IDENTITY_CHANGED')
        _need(row_key not in old_by_key or row['period_end'] >= old_by_key[row_key]['period_end'],
              'ORDINARY_RELEASE_PERIOD_REGRESSION')
        sources = []
        for evidence in rendered['evidence']:
            _need(key(evidence) == row_key, 'ORDINARY_RELEASE_EVIDENCE_COORDINATE_CHANGED')
            source = resolve_repository_file(repo_root=data, repo_relative_path=evidence['repo_relative_path'])
            _need(sha256_file(path=source) == evidence['content_sha256'], 'ORDINARY_RELEASE_EVIDENCE_SOURCE_CHANGED')
            sources.append({'evidence_hash': content_hash(value=evidence),
                            'package_path': prefix + '/data/' + evidence['repo_relative_path'],
                            'sha256': evidence['content_sha256']})
        replacements[row_key] = row
        evidence_replacements[row_key] = rendered['evidence']
        bindings.append({'company_id': coordinate[0], 'metric_id': metric, 'origin': 'VERIFIED_ORDINARY_RUN',
            'data_path': prefix + '/data', 'run_path': prefix + '/run',
            'run_id': native['run_id'], 'run_status': native['status'], 'result_id': result['result_id'],
            'value_kind': result.get('value_kind', 'NUMERIC'), 'quality': result['quality'],
            'applicability': result['applicability'], 'reason_code': result['reason_code'],
            'target_period': native['target_period'], 'requirement_id': native['requirement_id'],
            'requirement_hashes': native['requirement_hashes'], 'requirement_closure_hash': native['requirement_closure_hash'],
            'render_receipt': rendered['receipt'], 'source_locations': sources})
        bindings[-1]['source_admission'] = native_input['source_admission']
        if result['publication'] != 'PUBLISHED':
            bindings[-1]['result_publication'] = result['publication']
            bindings[-1]['selection_basis'] = selection_basis
    keys = set(replacements)
    rows = projector.project_metric_rows(legacy_rows=old_rows, migrated_keys=keys,
        replacement_rows=replacements, fieldnames=pub.METRIC_FIELDS)
    evidence = projector.project_evidence_rows(legacy_rows=old_evidence, migrated_keys=keys,
        replacement_rows=evidence_replacements, fieldnames=pub.EVIDENCE_FIELDS)
    _need([r for r in rows if key(r) not in keys] == [r for r in old_rows if key(r) not in keys]
          and [r for r in evidence if key(r) not in keys] == [r for r in old_evidence if key(r) not in keys],
          'ORDINARY_RELEASE_INHERITED_ROWS_CHANGED')
    report = {'record_type': 'ORDINARY_COMPLETE_VERSION_PREPARATION', 'schema_version': 1,
        'publication_credit': CREDIT, 'production_authorized': False, 'switch_available': False,
        'full390_acceptance': False, 'predecessor': inputs['predecessor'], 'selected_results': bindings,
        'public_row_count': len(rows), 'inherited_public_row_count': len(old_rows) - len(keys.intersection(old_by_key)),
        'unselected_coordinate_keys': [{'company_id': c, 'metric_id': m} for c, m in sorted(expected - selected)],
        'inherited_evidence_owner': 'predecessor/' + manifest['publication_id'],
        'scope_authority_hashes': {p: sha256_file(path=normal.ROOT / p) for p in
            ('config/company_registry.csv', 'config/source_strategy_registry.json')},
        'preparer_sha256': sha256_file(path=Path(__file__)),
        'matrix_hash': content_hash(value=rows), 'evidence_hash': content_hash(value=evidence),
        'calls': {'provider': 0, 'paid': 0, 'sec': 0}}
    return report, {'metrics_matrix.csv': pub._csv_bytes(rows=rows, fieldnames=pub.METRIC_FIELDS),
                    'metric_evidence.csv': pub._csv_bytes(rows=evidence, fieldnames=pub.EVIDENCE_FIELDS)}


def prepare(*, native_runs, output_root):
    """Snapshot selected native inputs and compose a reusable complete version."""
    root = _external(output_root)
    _need(not root.exists(), 'ORDINARY_RELEASE_OUTPUT_EXISTS')
    _need(type(native_runs) is list and native_runs, 'ORDINARY_RELEASE_SELECTION_REQUIRED')
    selected = []
    for item in native_runs:
        _need(type(item) is dict and set(item) == {'data_root', 'run_dir'}, 'ORDINARY_RELEASE_INPUT_FIELDS')
        data, run = _external(item['data_root']), _external(item['run_dir'])
        _need(all(root != p and root not in p.parents and p not in root.parents for p in (data, run)),
              'ORDINARY_RELEASE_INPUT_OUTPUT_OVERLAP')
        selected.append((data, run))
    view = pub.PublicationView.open(publication_root=normal.ROOT)
    inputs = {'predecessor': {'publication_id': view.publication_id,
              'manifest_sha256': sha256_file(path=view.bundle_dir / 'publication_manifest.json')},
              'native_count': len(selected)}
    _copy_exact_tree(source=view.bundle_dir, destination=root / 'predecessor' / view.publication_id)
    for ordinal, (data, run) in enumerate(selected):
        prefix = root / 'native' / '{:03d}'.format(ordinal)
        _copy_exact_tree(source=data, destination=prefix / 'data')
        _copy_exact_tree(source=run, destination=prefix / 'run')
    composition, files = _compose(root, inputs)
    for name, raw in files.items():
        normal._write(root / name, raw)
    body = {'record_type': 'ORDINARY_RELEASE_PREPARATION', 'schema_version': 1,
            'inputs': inputs, 'composition': composition, 'files': _tree_files(root=root)}
    record = {**body, 'preparation_id': content_hash(value=body)}
    normal._write(root / MANIFEST, _json(record))
    return record


def verify(*, preparation_root, expected_preparation_id=None):
    """Rebuild the selected native version; a self-signed CSV is insufficient."""
    root = _external(preparation_root)
    saved = strict_json_file(path=root / MANIFEST)
    body = {k: v for k, v in saved.items() if k != 'preparation_id'}
    _need(saved['preparation_id'] == content_hash(value=body)
          and (expected_preparation_id is None or saved['preparation_id'] == expected_preparation_id),
          'ORDINARY_RELEASE_PREPARATION_ID_CHANGED')
    _need(saved['record_type'] == 'ORDINARY_RELEASE_PREPARATION' and saved['schema_version'] == 1,
          'ORDINARY_RELEASE_PREPARATION_TYPE_CHANGED')
    actual = _tree_files(root=root); actual.pop(MANIFEST)
    _need(actual == saved['files'], 'ORDINARY_RELEASE_PACKAGE_FILES_CHANGED')
    composition, files = _compose(root, saved['inputs'])
    _need(saved['composition'] == composition, 'ORDINARY_RELEASE_NATIVE_COMPOSITION_CHANGED')
    _need(all((root / name).read_bytes() == raw for name, raw in files.items()), 'ORDINARY_RELEASE_PUBLIC_ROWS_CHANGED')
    _need(_tree_files(root=root) == {**actual, MANIFEST: {'sha256': sha256_file(path=root / MANIFEST),
          'size': (root / MANIFEST).stat().st_size}}, 'ORDINARY_RELEASE_PACKAGE_CHANGED_DURING_REPLAY')
    return saved
