"""Selected NIM/nonaccrual/AUM periods reuse their existing source inspectors and Calculator."""
from pathlib import Path
from sec_urls import submissions_url
from .calculator import calculate_metric, calculate_observation_metric, metric_is_applicable, withheld_metric_result
from .canonical import content_hash
from .financial_results import _installed_rule, _actual_period, RESOLVER, _ROLES
from .historical_bank_scope_wording import inspect_historical_bank_scope
from .historical_annual_input import prepare_historical_annual_input
from .historical_filing_inventory import filing_inventory
from .normal_governance_input import _Sources
from .normal_period_selection import resolve_period_selection
from .normal_source_authority import ROOT
from .observations import scope_key, structured_observation
from .ordinary_source_authority import verify_ordinary_source_proofs
from .traits import repository_company_traits
from .zero_ai_r2 import _exact_filing_source_set

METRICS = frozenset({'A04', 'A09', 'A11'})
DEI_RELEASE = 'YEAR_QUARTER_OR_DATE'
PROCESSING_FILES = tuple('scripts/vnext/' + name + '.py' for name in (
    'historical_bank_scope_cases', 'historical_bank_scope_wording', 'historical_annual_input', 'historical_dei',
    'historical_fiscal_labels', 'historical_filing_inventory', 'normal_period_selection',
    'normal_history_catalog', 'normal_annual_input', 'normal_governance_input',
    'financial_results', 'financial_candidates', 'financial_balance_scope',
    'financial_structured', 'financial_duration', 'financial_relationships', 'composite_scope', 'constraints',
    'r4_task_contracts', 'table_task_contracts', 'resource_limits', 'table_grid',
    'zero_ai_r2', 'deterministic_router', 'ordinary_source_authority', 'traits', 'specs')) + (
    'config/normal_period_selection_v1.json', 'config/normal_fiscal_year_labels_v1.json',
    'catalog/r4_normal/A04_net_interest_margin.md', 'catalog/r4_normal/A09_nonperforming_loan_ratio.md',
    'catalog/r4_normal/A11_assets_under_management.md',
    'catalog/r4_v2/A03_liquidity_coverage_ratio.md', 'catalog/r4_v2/A12_trading_exposure.md',
    'catalog/r4_v2/A04_net_interest_margin.md', 'catalog/r4_v2/A09_nonperforming_loan_ratio.md',
    'catalog/r4_v2/A11_assets_under_management.md', 'catalog/r4_v2/A13_geographic_exposure.md',
    'catalog/table_task_contracts.json', 'config/r4_task_contracts_v2.json',
    'docs/evidence/issue_28_prb_policy_revision.json')


def measurement(*, metric_id, annual, component):
    if metric_id not in METRICS:
        raise ValueError('HISTORICAL_BANK_SCOPE_FAMILY_NOT_RECEIVED')
    passed = (component['outcome'] in {'STRUCTURED_PRIMARY_RESOLVED', 'HTML_FALLBACK_SOURCE_SEMANTIC_FACT'}
              if metric_id == 'A09' else component['semantic_status'] == 'SINGLE_SOURCE_SEMANTIC_FACT')
    value = (component['relations'][0]['rate_check']['disclosed_ratio'] if metric_id == 'A04'
             else component['value']) if passed else None
    actual, basis = _actual_period(metric_id=metric_id, annual=annual,
        fact=component, applicable=True, passed=passed)
    return passed, value, actual, basis


def prepare_historical_bank_scope_year_case(*, repo_root, company_id, metric_id, fiscal_year):
    if metric_id not in METRICS:
        raise ValueError('HISTORICAL_BANK_SCOPE_FAMILY_NOT_RECEIVED')
    source_root = Path(repo_root)
    selection = resolve_period_selection(repo_root=source_root, company_id=company_id,
        fiscal_year=fiscal_year, rules_root=ROOT)
    prepared = prepare_historical_annual_input(repo_root=source_root, company_id=company_id,
        period_selection=selection, rules_root=ROOT)
    path, spec, _ = _installed_rule(repo_root=ROOT, metric_id=metric_id)
    annual = prepared['table_input']['target_period']
    traits = repository_company_traits(repo_root=ROOT, company_id=company_id)
    applicable = metric_is_applicable(applicability=spec['compiled']['applicability'], traits=traits)
    reader = _Sources(source_root, company_id, prepared['entity'])
    main = reader.read(submissions_url(cik=int(prepared['entity'])),
        role='sec_submissions_inventory', media_type='application/json')
    primary = reader.primary(prepared['filing'])
    inventory = filing_inventory(reader=reader, inventory=main, period_selection=selection,
        cik=prepared['entity'], accession=prepared['filing']['accessionNumber'])
    manifest = _exact_filing_source_set(company_id=company_id, source_role='target_primary',
        reference=primary['source_reference'], inventory_reference=inventory['source_reference'],
        inventory_bytes=inventory['raw_bytes'])
    component, passed, value, actual, basis = None, False, None, dict(annual), 'STRUCTURAL_NO_MEASUREMENT'
    reason = 'TRAIT_NOT_APPLICABLE'
    if applicable:
        reason = 'HISTORICAL_BANK_SCOPE_AMENDMENT_OR_SUCCESSOR_NOT_RECEIVED'
        if not prepared['amendments'] and prepared['subject_policy']['mode'] == 'CONTINUOUS_PRIMARY':
            arguments = {'repo_root': ROOT, 'source_bytes': primary['raw_bytes'],
                'expected_cik': prepared['entity'], 'target_period': annual, 'dei_release': DEI_RELEASE}
            if metric_id == 'A09':
                arguments.update(source_reference=primary['source_reference'], source_set_manifest=manifest,
                    inventory_source_reference=inventory['source_reference'], inventory_bytes=inventory['raw_bytes'])
            else:
                arguments['expected_source_sha256'] = primary['source_reference']['raw_asset_id'][7:]
            component = inspect_historical_bank_scope(metric_id=metric_id, **arguments)
            passed, value, actual, basis = measurement(metric_id=metric_id, annual=annual, component=component)
            reason = 'PASS' if passed else 'HISTORICAL_BANK_SCOPE_SOURCE_SEMANTICS_UNRESOLVED'
    scope = dict(spec['compiled']['required_claims'])
    target = {'company_id': company_id, 'period_start': actual['period_start'],
        'period_end': actual['period_end'], 'scope': scope, 'scope_key': scope_key(scope=scope)}
    observations = []
    if not applicable:
        result, trace, observations = calculate_metric(compiled_spec=spec,
            target={**target, 'entity': prepared['entity'], 'accession': prepared['filing']['accessionNumber']},
            company_traits=traits, structured_facts=[], verified_observations=[])
    elif not passed:
        result, trace = withheld_metric_result(compiled_spec=spec, target=target, reason_code=reason)
    else:
        ref = primary['source_reference']
        observation = structured_observation(metric_id=metric_id, semantic_role=_ROLES[metric_id],
            company_id=company_id, period_start=actual['period_start'], period_end=actual['period_end'],
            scope=scope, value=value, unit=spec['compiled']['canonical_unit'], quality='EXACT',
            source_binding={'raw_asset_id': ref['raw_asset_id'], 'source_reference_id': ref['source_reference_id'],
                'accession': ref['accession'], 'document_name': ref['document_name'], 'source_role': ref['source_role'],
                'entity': prepared['entity'], 'resolver': RESOLVER, 'source_fact_hash': content_hash(value=component),
                'source_set_manifest_id': manifest['source_set_manifest_id'], 'measurement_time_basis': basis,
                'filing_period': annual, 'actual_measurement_period': actual})
        result, trace = calculate_observation_metric(compiled_spec=spec, target=target,
            company_traits=traits, observation=observation)
        observations = [observation]
    proofs = list({content_hash(value=p): p for p in
        [*prepared['source_proofs'], *[entry['proof'] for entry in reader.proofs.values()]]}.values())
    admission = verify_ordinary_source_proofs(data_root=source_root, proofs=proofs)
    records = list(reader.records.values())
    binding = {'record_type': 'HISTORICAL_SELECTED_BANK_SCOPE_INPUT', 'prepared_input': prepared,
        'period_selection': selection, 'source_set_manifest': manifest, 'source_fact': component,
        'source_proofs': proofs, 'metric_id': metric_id, 'dei_release': DEI_RELEASE,
        'measurement_time_basis': basis, 'spec_closure_hash': spec['spec_closure_hash']}
    return {'kind': 'STRUCTURED', 'primary_metric_id': metric_id, 'input_binding': binding,
        'compiled_specs': {metric_id: spec}, 'spec_paths': {metric_id: path}, 'target_period': actual,
        'prepared_annual_input': prepared, 'expected_records': [*records, *observations, trace, result],
        'results': {metric_id: result}, 'traces': {metric_id: trace},
        'references': [record for record in records if record['record_type'] == 'SOURCE_REFERENCE'],
        'source_proofs': proofs, 'admission': admission, 'selection': {'source_fact': component},
        'rules_root': str(ROOT)}
