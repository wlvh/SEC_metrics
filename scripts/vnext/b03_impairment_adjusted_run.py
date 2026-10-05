"""Explicit B03 native route for an exact, original-proven impairment split.

The historic B03 Spec/Run and normal_run_v3 defaults are untouched. This route
must prove the original cash-flow and segment relation before using the new
derived-role Spec; a pair of Company Facts numbers alone is insufficient.
"""
from pathlib import Path

from . import normal_run_v3 as normal
from .b03_exact_impairment_relation import prove_exact_impairment_relation
from .batch_workflow import _structured_concepts
from .calculator import calculate_metric
from .canonical import sha256_bytes, sha256_file
from .requirements import load_requirement_snapshot
from .sources import companyfacts_structured_facts, resolve_repository_file
from .specs import compile_spec_file
from .traits import repository_company_traits


SPEC_PATH = 'catalog/r6/B03_impairment_excluded_v1.md'
ROUTE = 'B03_EXACT_IMPAIRMENT_EXCLUSION_V1'


def _need(condition, reason):
    if not condition:
        raise ValueError(reason)


def prepare_case(*, data_root, company_id):
    """Rebuild source proof, Spec graph, observation arithmetic and binding."""
    root = Path(data_root)
    base = normal.prepare_case(data_root=root, company_id=company_id,
                               metric_id='B03')
    proof = prove_exact_impairment_relation(case=base, data_root=root)
    _need(SPEC_PATH in normal._policy(normal.ROOT)['metric_spec_paths']['B03'],
          'B03_ADJUSTED_SPEC_ROUTE_NOT_ENABLED')
    path = root/SPEC_PATH if (root/SPEC_PATH).is_file() else normal.ROOT/SPEC_PATH
    _need(sha256_file(path=path) == sha256_file(path=normal.ROOT/SPEC_PATH),
          'B03_ADJUSTED_SPEC_BYTES_CHANGED')
    spec = compile_spec_file(path=path,
        dependency_specs={'B01': base['compiled_specs']['B01']})
    old_da = [row for row in base['observations']
        if row['semantic_role'] == 'depreciation_and_amortization']
    _need(len(old_da) == 1, 'B03_ADJUSTED_OLD_SELECTION_NOT_UNIQUE')
    binding = old_da[0]['source_binding']
    sources = [row for row in base['source_proofs']
        if row['content_sha256'] == binding['raw_asset_id'][7:]
        and row['source_url'].endswith('/CIK' + str(int(binding['entity'])).zfill(10) + '.json')]
    references = [row for row in base['references']
        if row['source_reference_id'] == binding['source_reference_id']]
    _need(len(sources) == len(references) == 1,
          'B03_ADJUSTED_COMPANYFACTS_SOURCE_NOT_UNIQUE')
    raw = resolve_repository_file(repo_root=root,
        repo_relative_path=sources[0]['request_repo_relative_path']).read_bytes()
    _need(sha256_bytes(content=raw) == sources[0]['content_sha256'],
          'B03_ADJUSTED_COMPANYFACTS_BYTES_CHANGED')
    concepts = sorted(set(_structured_concepts(
        compiled_spec=base['compiled_specs']['B01'])) |
        set(_structured_concepts(compiled_spec=spec)))
    facts = companyfacts_structured_facts(raw_bytes=raw,
        source_reference=references[0], approved_concepts=concepts,
        allowed_ciks=[binding['entity']], include_instant=False)
    dependency = [row for row in base['expected_records']
        if row['record_type'] == 'VERIFIED_OBSERVATION'
        and row['metric_id'] == 'B01']
    result, trace, observations = calculate_metric(compiled_spec=spec,
        target=base['traces']['B03']['calculation_target'],
        company_traits=repository_company_traits(repo_root=root,
            company_id=company_id), structured_facts=facts,
        verified_observations=dependency)
    arithmetic = [step for step in trace['steps']
        if step['event'] == 'DERIVED_BRANCH_SELECTED'
        and step['role'] == 'depreciation_and_amortization']
    _need(len(arithmetic) == 1
          and arithmetic[0]['component_values'] == {
              'reported_da_including_impairment': proof['selected_total_usd'],
              'impairment_related_depreciation':
                  proof['exact_impairment_depreciation_usd']}
          and arithmetic[0]['value'] == proof['arithmetically_remaining_da_usd'],
          'B03_ADJUSTED_CALCULATION_NOT_SOURCE_PROVEN')
    retained = [row for row in base['expected_records']
        if not (row.get('metric_id') == 'B03' and row['record_type'] in {
            'VERIFIED_OBSERVATION', 'EXECUTION_TRACE', 'METRIC_RESULT'})]
    input_binding = {'record_type': 'B03_EXACT_IMPAIRMENT_RUN_INPUT_V1',
        'route': ROUTE, 'base_input_id': base['input_binding']['input_id'],
        'old_result_id_retained_without_current_credit':
            base['results']['B03']['result_id'],
        'source_relation_proof': proof,
        'spec_path': SPEC_PATH,
        'spec_closure_hash': spec['spec_closure_hash'],
        'production_authorized': False}
    selected = {'source_relation_proof_id': proof['proof_id'],
        'selected_fact_ids': [row['source_binding']['fact_id']
            for row in observations if row['metric_id'] == 'B03'],
        'reason_code': result['reason_code']}
    return {**base, 'input_binding': input_binding,
        'spec_paths': {**base['spec_paths'], 'B03': SPEC_PATH},
        'compiled_specs': {**base['compiled_specs'], 'B03': spec},
        'observations': observations,
        'results': {**base['results'], 'B03': result},
        'traces': {**base['traces'], 'B03': trace},
        'expected_records': [*retained, *observations, trace, result],
        'selection': selected}


def install_inputs(*, data_root, source_root, company_id):
    """Install exact source/runtime bytes, then rebuild before any Run."""
    data, source = normal._external(Path(data_root)), Path(source_root).resolve()
    _need(data != source and data not in source.parents
          and source not in data.parents,
          'B03_ADJUSTED_SOURCE_AND_OUTPUT_OVERLAP')
    requirement = load_requirement_snapshot(
        snapshot_dir=normal.ROOT/'requirements'/normal.REQUIREMENT_ID)
    case = prepare_case(data_root=source, company_id=company_id)
    normal._install_case_inputs(data_root=data, source_root=source,
        company_id=company_id, case=case, requirement=requirement)
    rebuilt = prepare_case(data_root=data, company_id=company_id)
    _need(normal._binding(rebuilt, requirement) ==
          normal._binding(case, requirement),
          'B03_ADJUSTED_INSTALLED_INPUT_CHANGED')
    return rebuilt


def create_run(*, data_root, run_dir, company_id):
    """Use the existing native Run writer, never a direct result rewrite."""
    data = normal._external(Path(data_root))
    case = prepare_case(data_root=data, company_id=company_id)
    from .ordinary_source_authority import require_installed_checkpoint
    require_installed_checkpoint(data_root=data, admission=case['admission'])
    requirement = load_requirement_snapshot(
        snapshot_dir=data/'requirements'/normal.REQUIREMENT_ID)
    return normal._create_case_run(data_root=data, run_dir=run_dir,
        company_id=company_id, metric_id='B03', case=case,
        requirement=requirement)
