"""Resolve native results through a pinned complete publication's own bindings.

Paths belong to the publication reader. Inherited coordinates follow their
declared predecessor; adopted coordinates never fall back to an older result.
"""
from .canonical import strict_json_loads
from .records import ANNUAL_PUBLICATION_MANIFEST_TYPE, validate_record


def _need(condition, reason):
    if not condition:
        raise ValueError(reason)


def _json(view, path):
    return strict_json_loads(text=view.read_bytes(relative_path=path).decode())


def _ordinary(view):
    return (view.manifest['record_type'] == ANNUAL_PUBLICATION_MANIFEST_TYPE
            and view.manifest.get('publication_credit') == 'NONE_ISOLATED_ORDINARY_VERSION')


def _predecessor(view):
    from .publication import PublicationView
    identity = view.manifest['previous_publication_id']
    prefix = ('internal/ordinary_preparation/predecessor/' if _ordinary(view)
              else 'internal/predecessor/') + identity
    raw = view.read_bytes(relative_path=prefix + '/publication_manifest.json')
    manifest = validate_record(record=strict_json_loads(text=raw.decode()))
    _need(manifest['publication_id'] == identity, 'PUBLISHED_PREDECESSOR_ID_CHANGED')
    # Every child byte is also bound by the already verified outer manifest.
    outer = {r['path']: (r['sha256'], r['size']) for r in view.manifest['files']}
    _need(all(outer.get(prefix + '/' + r['path']) == (r['sha256'], r['size'])
              for r in manifest['files']), 'PUBLISHED_PREDECESSOR_CLOSURE_CHANGED')
    return PublicationView(publication_id=identity, bundle_dir=view.bundle_dir / prefix,
                           manifest=manifest)


def authority_bytes(view, relative_path):
    """Read the coverage authority of this version, without selecting a Result."""
    from .publication import _safe_relative
    relative_path = _safe_relative(value=relative_path).as_posix()
    if _ordinary(view):
        # Selected ordinary rows do not grant a new formal migration scope.
        return authority_bytes(_predecessor(view), relative_path)
    prefix = ('internal/annual_snapshot/data/' if
              view.manifest['record_type'] == ANNUAL_PUBLICATION_MANIFEST_TYPE else
              'internal/authority/')
    return view.read_bytes(relative_path=prefix + relative_path)


def native_result(view, company_id, metric_id, *, _visited=()):
    """Return source/Run bytes for one exact selected or inherited coordinate."""
    _need(view.publication_id not in _visited and len(_visited) < 32,
          'PUBLISHED_RESULT_ANCESTRY_INVALID')
    chain = (*_visited, view.publication_id)
    if _ordinary(view):
        batch = _json(view, 'internal/ordinary_complete_version.json')
        found = [r for r in batch['selected_results']
                 if (r['company_id'], r['metric_id']) == (company_id, metric_id)]
        _need(len(found) <= 1, 'PUBLISHED_RESULT_BINDING_NOT_UNIQUE')
        if not found:
            _need({'company_id': company_id, 'metric_id': metric_id} in batch['unselected_coordinate_keys'],
                  'PUBLISHED_RESULT_BINDING_NOT_UNIQUE')
            result = native_result(_predecessor(view), company_id, metric_id, _visited=chain)
            return {**result, 'requested_publication_id': chain[0],
                    'inheritance_chain': list(chain) + result['inheritance_chain'][len(chain):]}
        binding = found[0]
        _need(binding['origin'] == 'VERIFIED_ORDINARY_RUN', 'PUBLISHED_RESULT_ORIGIN_UNKNOWN')
        paths = [('internal/ordinary_preparation/' + binding['run_path'], binding)]
    elif view.manifest['record_type'] == ANNUAL_PUBLICATION_MANIFEST_TYPE:
        batch = _json(view, 'internal/annual_complete_version.json')
        found = [r for r in batch['cumulative_result_bindings']
                 if (r['company_id'], r['metric_id']) == (company_id, metric_id)]
        _need(len(found) == 1, 'PUBLISHED_RESULT_BINDING_NOT_UNIQUE')
        binding = found[0]
        if binding['origin'] == 'PINNED_PREDECESSOR':
            _need(binding['publication_id'] == view.manifest['previous_publication_id'],
                  'PUBLISHED_RESULT_PREDECESSOR_CHANGED')
            result = native_result(_predecessor(view), company_id, metric_id, _visited=chain)
            return {**result, 'requested_publication_id': chain[0],
                    'inheritance_chain': list(chain) + result['inheritance_chain'][len(chain):]}
        _need(binding['origin'] == 'ADOPTED_NATIVE_CANDIDATE', 'PUBLISHED_RESULT_ORIGIN_UNKNOWN')
        paths = [('internal/annual_snapshot/' + binding['snapshot_run_path'], binding)]
    else:
        batch = _json(view, 'internal/batch/batch_manifest.json')
        paths = [('internal/batch/' + r['run_path'], r) for r in batch['runs']
                 if r['company_id'] == company_id]
    matches = []
    for prefix, binding in paths:
        records_raw = view.read_bytes(relative_path=prefix + '/records.jsonl')
        records = [validate_record(record=strict_json_loads(text=line))
                   for line in records_raw.decode().splitlines() if line.strip()]
        results = [r for r in records if r['record_type'] == 'METRIC_RESULT'
                   and (r['company_id'], r['metric_id']) == (company_id, metric_id)]
        if not results:
            continue
        _need(len(results) == 1, 'PUBLISHED_NATIVE_RESULT_NOT_UNIQUE')
        result = results[0]
        manifest_raw = view.read_bytes(relative_path=prefix + '/manifest.json')
        manifest = validate_record(record=strict_json_loads(text=manifest_raw.decode()))
        expected = [binding['result_id']] if 'result_id' in binding else binding['result_ids']
        _need(result['result_id'] in expected and manifest['run_id'] == binding['run_id']
              and manifest['company_id'] == company_id, 'PUBLISHED_NATIVE_RUN_BINDING_CHANGED')
        trace = [r for r in records if r['record_type'] == 'EXECUTION_TRACE'
                 and r['trace_id'] == result['trace_id']]
        _need(len(trace) == 1, 'PUBLISHED_NATIVE_TRACE_MISSING')
        observations = [r for r in records if r['record_type'] == 'VERIFIED_OBSERVATION'
                        and r['observation_id'] in trace[0]['input_observation_ids']]
        source_ids = {r['source_binding']['source_reference_id'] for r in observations}
        if _ordinary(view) and binding.get('selection_basis') == 'NATIVE_REVIEWED_DEFINED_SCOPE_STATEMENT':
            # The bundle's native verifier has already proved the complete
            # source census and effective Review; absence has no observations.
            reasons = {'D04': 'D04_DEFINED_SCOPE_NO_DOUBT_DISCLOSURE',
                       'B13': 'B13_DEFINED_SCOPE_NO_RELEVANT_DISCLOSURE'}
            _need(result['metric_id'] in reasons and result['reason_code'] == reasons[result['metric_id']]
                  and result['publication'] == 'WITHHELD' and result.get('value_kind') == 'TEXT_V1'
                  and result['value'] is None and result.get('text_payload') is None
                  and result['quality'] == 'NONE' and result['applicability'] == 'APPLICABLE',
                  'PUBLISHED_DEFINED_SCOPE_RESULT_CHANGED')
            source_ids = {r['source_reference_id'] for r in manifest['source_references']}
        if view.manifest.get('publication_credit') == 'NONE_ISOLATED_STRUCTURED_MIGRATION' and not source_ids:
            # A blocked candidate has no accepted Observation; return its
            # actual bound sources for review without inventing acceptance.
            source_ids = {r['source_reference_id'] for r in manifest['source_references']}
        sources = [r for r in records if r['record_type'] == 'SOURCE_REFERENCE'
                   and r['source_reference_id'] in source_ids]
        _need(sources and len(sources) == len(source_ids), 'PUBLISHED_NATIVE_SOURCE_MISSING')
        matches.append({'requested_publication_id': chain[0], 'owner_publication_id': view.publication_id,
                        'inheritance_chain': list(chain), 'run_path': prefix, 'result': result,
                        'sources': sources, 'manifest_raw': manifest_raw, 'records_raw': records_raw,
                        'reviews_raw': view.read_bytes(relative_path=prefix + '/review_decisions.jsonl')})
    _need(bool(matches), 'PUBLISHED_NATIVE_CONTENT_NOT_EMBEDDED')
    _need(len(matches) == 1, 'PUBLISHED_NATIVE_COORDINATE_NOT_UNIQUE')
    return matches[0]
