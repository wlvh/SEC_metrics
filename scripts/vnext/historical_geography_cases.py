"""Selected historical A13 through the existing source inspector and Calculator."""
from pathlib import Path

from sec_urls import submissions_url
from .calculator import (calculate_metric, calculate_observation_metric,
                         metric_is_applicable, withheld_metric_result)
from .canonical import content_hash
from .financial_results import _installed_rule, RESOLVER, _ROLES
from .financial_structured import inspect_inline_financial_claims
from .historical_annual_input import prepare_historical_annual_input
from .historical_filing_inventory import filing_inventory
from .normal_governance_input import _Sources
from .normal_period_selection import resolve_period_selection
from .normal_source_authority import ROOT
from .observations import scope_key, structured_observation
from .ordinary_source_authority import verify_ordinary_source_proofs
from .traits import repository_company_traits
from .zero_ai_r2 import _exact_filing_source_set

METRICS = frozenset({'A13'})
DEI_RELEASE = 'YEAR_QUARTER_OR_DATE'
PROCESSING_FILES = tuple('scripts/vnext/' + name + '.py' for name in (
    'historical_geography_cases', 'historical_annual_input', 'historical_dei',
    'historical_fiscal_labels', 'historical_filing_inventory', 'normal_period_selection',
    'normal_history_catalog', 'normal_annual_input', 'normal_governance_input',
    'financial_results', 'financial_structured', 'financial_candidates',
    'financial_duration', 'financial_relationships', 'composite_scope', 'constraints',
    'r4_task_contracts', 'table_task_contracts',
    'resource_limits', 'deterministic_router', 'table_grid')) + (
    'config/normal_period_selection_v1.json', 'config/normal_fiscal_year_labels_v1.json',
    'catalog/r4_normal/A13_geographic_exposure.md', 'catalog/r4_v2/A13_geographic_exposure.md',
    'catalog/table_task_contracts.json', 'config/r4_task_contracts_v2.json',
    'docs/evidence/issue_28_prb_policy_revision.json')


def prepare_historical_geography_year_case(*, repo_root, company_id, metric_id, fiscal_year):
    """Read the requested issuer year; never fetch or select today's report."""
    if metric_id not in METRICS:
        raise ValueError('HISTORICAL_GEOGRAPHY_FAMILY_NOT_RECEIVED')
    source_root = Path(repo_root)
    selected = resolve_period_selection(repo_root=source_root, company_id=company_id,
        fiscal_year=fiscal_year, rules_root=ROOT)
    prepared = prepare_historical_annual_input(repo_root=source_root, company_id=company_id,
        period_selection=selected, rules_root=ROOT)
    path, spec, _ = _installed_rule(repo_root=ROOT, metric_id=metric_id)
    period = prepared['table_input']['target_period']
    scope = dict(spec['compiled']['required_claims'])
    target = {'company_id': company_id, 'period_start': period['period_start'],
        'period_end': period['period_end'], 'scope': scope, 'scope_key': scope_key(scope=scope)}
    reader = _Sources(source_root, company_id, prepared['entity'])
    main = reader.read(submissions_url(cik=int(prepared['entity'])),
        role='sec_submissions_inventory', media_type='application/json')
    primary = reader.primary(prepared['filing'])
    inventory = filing_inventory(reader=reader, inventory=main, period_selection=selected,
        cik=prepared['entity'], accession=prepared['filing']['accessionNumber'])
    manifest = _exact_filing_source_set(company_id=company_id, source_role='target_primary',
        reference=primary['source_reference'], inventory_reference=inventory['source_reference'],
        inventory_bytes=inventory['raw_bytes'])
    traits = repository_company_traits(repo_root=ROOT, company_id=company_id)
    fact, claims, observations = None, [], []
    binding = {'record_type': 'HISTORICAL_SELECTED_GEOGRAPHY_INPUT',
        'metric_id': metric_id, 'prepared_input': prepared, 'period_selection': selected,
        'source_set_manifest': manifest, 'dei_release': DEI_RELEASE,
        'spec_closure_hash': spec['spec_closure_hash']}
    if not metric_is_applicable(applicability=spec['compiled']['applicability'], traits=traits):
        result, trace, observations = calculate_metric(compiled_spec=spec,
            target={**target, 'accession': prepared['filing']['accessionNumber'],
                    'entity': prepared['entity']},
            company_traits=traits, structured_facts=[], verified_observations=[])
    elif prepared['amendments'] or prepared['subject_policy']['mode'] != 'CONTINUOUS_PRIMARY':
        result, trace = withheld_metric_result(compiled_spec=spec, target=target,
            reason_code='HISTORICAL_GEOGRAPHY_AMENDMENT_OR_SUCCESSOR_NOT_RECEIVED')
    else:
        fact = inspect_inline_financial_claims(repo_root=ROOT,
            source_bytes=primary['raw_bytes'], source_reference=primary['source_reference'],
            source_set_manifest=manifest, expected_cik=prepared['entity'], target_period=period,
            metric_id=metric_id, inventory_source_reference=inventory['source_reference'],
            inventory_bytes=inventory['raw_bytes'], dei_release=DEI_RELEASE)
        binding['source_fact'] = fact
        if fact['outcome'] != 'STRUCTURED_PRIMARY_RESOLVED':
            result, trace = withheld_metric_result(compiled_spec=spec, target=target,
                reason_code='HISTORICAL_GEOGRAPHY_SOURCE_SEMANTICS_UNRESOLVED')
        else:
            claims = [entry['claim'] for entry in fact['selected']]
            ref = primary['source_reference']
            observation = structured_observation(metric_id=metric_id,
                semantic_role=_ROLES[metric_id], company_id=company_id,
                period_start=period['period_start'], period_end=period['period_end'],
                scope=scope, value=fact['value'], unit=spec['compiled']['canonical_unit'], quality='EXACT',
                source_binding={'raw_asset_id': ref['raw_asset_id'],
                    'source_reference_id': ref['source_reference_id'], 'accession': ref['accession'],
                    'document_name': ref['document_name'], 'source_role': ref['source_role'],
                    'entity': prepared['entity'], 'resolver': RESOLVER,
                    'source_set_manifest_id': manifest['source_set_manifest_id'],
                    'source_fact_hash': content_hash(value=fact),
                    'verified_claim_ids': [claim['verified_claim_id'] for claim in claims],
                    'measurement_time_basis': 'EXACT_ANNUAL_FILING_PERIOD',
                    'filing_period': period, 'actual_measurement_period': period})
            result, trace = calculate_observation_metric(compiled_spec=spec, target=target,
                company_traits=traits, observation=observation)
            observations = [observation]
    proofs = list({content_hash(value=p): p for p in
        [*prepared['source_proofs'], *[entry['proof'] for entry in reader.proofs.values()]]}.values())
    admission = verify_ordinary_source_proofs(data_root=source_root, proofs=proofs)
    records = list(reader.records.values())
    binding.update(claims=claims, source_proofs=proofs)
    return {'kind': 'STRUCTURED', 'primary_metric_id': metric_id, 'input_binding': binding,
        'compiled_specs': {metric_id: spec}, 'spec_paths': {metric_id: path}, 'target_period': period,
        'prepared_annual_input': prepared, 'expected_records': [*records, *claims, *observations, trace, result],
        'results': {metric_id: result}, 'traces': {metric_id: trace},
        'references': [record for record in records if record['record_type'] == 'SOURCE_REFERENCE'],
        'source_proofs': proofs, 'admission': admission,
        'selection': {'source_fact': fact} if fact is not None else None, 'rules_root': str(ROOT)}
