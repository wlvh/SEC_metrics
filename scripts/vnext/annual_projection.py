"""Project selected native annual Results into the complete retained version."""
import csv
import io
from .annual_adoption import need, record, read
from .canonical import content_hash, sha256_bytes
from . import projector, publication as pub


def rows(content, fields, label):
    return pub._csv_rows(content=content, fieldnames=fields, label=label)


def build_projection(*, snapshot_root, context, adoption, runs, predecessor):
    data = snapshot_root / 'data'
    registry = {r['company_id']: r for r in projector._load_registry(repo_root=data)}
    company = registry[context['policy']['company_id']]
    index = read(data, 'config/issue_15_release_plan.json')
    plan_row = next(r for r in index['release_plan_paths'] if r['release_plan_content_id'] == index['active_release_plan_content_id'])
    plan = read(data, plan_row['path'])
    need(plan['release_stage'] == 'R3', 'ANNUAL_PREDECESSOR_SCOPE_UNSUPPORTED')
    from .annual_adoption_policy import V3
    prior_authority = (predecessor.authority_bytes(relative_path='config/issue_15_release_plan.json')
        if context['policy']['policy_id'] == V3 else
        predecessor.read_bytes(relative_path='internal/authority/config/issue_15_release_plan.json'))
    need(prior_authority == (data / 'config/issue_15_release_plan.json').read_bytes(), 'ANNUAL_CUMULATIVE_PLAN_CHANGED')
    old_metrics = rows(predecessor.read_bytes(relative_path='metrics_matrix.csv'), pub.METRIC_FIELDS, 'Predecessor metrics')
    old_evidence = rows(predecessor.read_bytes(relative_path='metric_evidence.csv'), pub.EVIDENCE_FIELDS, 'Predecessor evidence')
    key = lambda row: (row['company'], row['metric_id'])
    old_by_key = {key(r): r for r in old_metrics}
    need(len(old_by_key) == len(old_metrics), 'ANNUAL_PREDECESSOR_DUPLICATE')
    keys = {(company['display_name'], metric) for metric in context['policy']['metric_ids']}
    need(keys.issubset(old_by_key), 'ANNUAL_ADOPTION_CANNOT_ADD_COVERAGE')
    native_indexes = projector._record_indexes(runs=[(r['manifest'], r['records']) for r in runs.values()])
    replacements, evidence_replacements, bindings = {}, {}, []
    for metric_id, name in (('B01', 'b01'), ('B10', 'b10')):
        result = adoption['selected_results'][metric_id]
        native = runs[name]
        spec = native['specs'][metric_id]
        # Empty presentation baseline: no historical value/period/answer input.
        baseline = {field: '' for field in pub.METRIC_FIELDS}
        row, evidence, _ = projector._project_result(result=result,
            trace=native_indexes['traces'][result['trace_id']], company=company, spec=spec,
            baseline_row=baseline, indexes=native_indexes,
            fiscal_year=str(native['manifest']['target_period']['fiscal_year']), metric_fields=pub.METRIC_FIELDS)
        need((row['period_start'], row['period_end']) == (result['period_start'], result['period_end']), 'ANNUAL_PROJECTED_PERIOD_CHANGED')
        old = old_by_key[key(row)]
        historical_seed = context['policy']['policy_id'] == V3 and context.get('kind') == 'HISTORICAL_SEED'
        need(historical_seed or row['period_end'] >= old['period_end'], 'ANNUAL_PERIOD_REGRESSION_FORBIDDEN')
        replacements[key(row)], evidence_replacements[key(row)] = row, evidence
        bindings.append({'company_id': result['company_id'], 'metric_id': metric_id,
            'origin': 'ADOPTED_NATIVE_CANDIDATE', 'run_id': native['manifest']['run_id'],
            'run_status': native['manifest']['status'], 'result_id': result['result_id'],
            'requirement_hashes': native['manifest']['requirement_hashes'],
            'row_hash': content_hash(value=row), 'evidence_hash': content_hash(value=evidence),
            'snapshot_run_path': 'candidate/' + name,
            'source_reference_ids': sorted({r['source_reference_id'] for r in native['records'] if r['record_type'] == 'SOURCE_REFERENCE'})})
    metrics = projector.project_metric_rows(legacy_rows=old_metrics, migrated_keys=keys,
        replacement_rows=replacements, fieldnames=pub.METRIC_FIELDS)
    evidence = projector.project_evidence_rows(legacy_rows=old_evidence, migrated_keys=keys,
        replacement_rows=evidence_replacements, fieldnames=pub.EVIDENCE_FIELDS)
    unchanged_metrics = [r for r in old_metrics if key(r) not in keys]
    unchanged_evidence = [r for r in old_evidence if key(r) not in keys]
    need([r for r in metrics if key(r) not in keys] == unchanged_metrics
         and [r for r in evidence if key(r) not in keys] == unchanged_evidence
         and {key(r) for r in metrics} == set(old_by_key) and len(metrics) == len(old_metrics),
         'ANNUAL_INHERITED_ROWS_CHANGED')
    cumulative_keys = [(r['company_id'], r['metric_id']) for r in plan['cumulative_vnext_result_keys']]
    need(len(set(cumulative_keys)) == len(cumulative_keys), 'ANNUAL_CUMULATIVE_DUPLICATE')
    expected = {(c, m) for c in registry for m in plan['cumulative_metric_ids']}
    need(set(cumulative_keys) == expected
         and all((registry[c]['display_name'], m) in old_by_key for c, m in expected), 'ANNUAL_CUMULATIVE_COVERAGE_MISSING')
    selected = {(r['company_id'], r['metric_id']): r for r in bindings}
    complete = []
    for c, m in sorted(expected):
        if (c, m) in selected:
            complete.append(selected[(c, m)])
        else:
            public_key = registry[c]['display_name'], m
            old = old_by_key[public_key]
            complete.append({'company_id': c, 'metric_id': m, 'origin': 'PINNED_PREDECESSOR',
                'publication_id': predecessor.publication_id, 'period_start': old['period_start'],
                'period_end': old['period_end'], 'row_hash': content_hash(value=old),
                'evidence_hash': content_hash(value=[r for r in old_evidence if key(r) == public_key])})
    batch = record({'record_type': 'ANNUAL_COMPLETE_VERSION_BINDINGS', 'schema_version': 1,
        'adoption_receipt_id': adoption['adoption_receipt_id'], 'previous_publication_id': predecessor.publication_id,
        'cumulative_metric_ids': plan['cumulative_metric_ids'], 'cumulative_result_bindings': complete,
        'selected_result_count': len(selected), 'inherited_result_count': len(complete) - len(selected),
        'public_row_count': len(metrics), 'unchanged_public_row_count': len(unchanged_metrics),
        'unchanged_rows_hash': content_hash(value=unchanged_metrics),
        'unchanged_evidence_hash': content_hash(value=unchanged_evidence),
        'historical_release_plan_content_id': plan['release_plan_content_id'],
        'unselected_native_records': 'PRESERVED_IN_ORIGINAL_RUN_SNAPSHOT_NOT_PUBLISHED_AS_NEW'}, 'batch_manifest_id')
    proof = record({'record_type': 'ANNUAL_PROJECTION_RECEIPT', 'status': 'PASS',
        'batch_manifest_id': batch['batch_manifest_id'], 'adoption_receipt_id': adoption['adoption_receipt_id'],
        'selected_results': bindings, 'complete_public_key_set_hash': content_hash(value=sorted(old_by_key)),
        'unchanged_metric_rows_exact': True, 'unchanged_evidence_rows_exact': True,
        'periods_not_relabelled': True, 'cumulative_result_count': len(complete)}, 'projection_receipt_id')
    return {'metrics': metrics, 'evidence': evidence, 'batch': batch, 'proof': proof,
        'files': {'metrics_matrix.csv': pub._csv_bytes(rows=metrics, fieldnames=pub.METRIC_FIELDS),
                  'metric_evidence.csv': pub._csv_bytes(rows=evidence, fieldnames=pub.EVIDENCE_FIELDS)},
        'indexes': native_indexes, 'migrated_ids': set(plan['cumulative_metric_ids'])}
