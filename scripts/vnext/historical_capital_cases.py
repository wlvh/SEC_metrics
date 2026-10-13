"""Selected-year capital ratios through the shared native-fact inspector."""
from pathlib import Path

from sec_urls import submissions_url
from .calculator import metric_is_applicable, calculate_observation_metric, withheld_metric_result
from .canonical import content_hash, strict_json_file
from .historical_annual_input import prepare_historical_annual_input
from .historical_dei import release_aware_pattern
from .historical_filing_inventory import filing_inventory
from .normal_accession_results import inspect_ordinary_accession_facts, NormalAccessionError, POLICY_PATH
from .normal_annual_input import _registry_rows
from .normal_governance_input import _Sources
from .normal_period_selection import resolve_period_selection
from .normal_run_specs import installed_ordinary_spec_documents
from .normal_source_authority import ROOT
from .observations import scope_key, structured_observation
from .ordinary_source_authority import verify_ordinary_source_proofs
from .traits import repository_company_traits
from .zero_ai_r2 import _load_deterministic_catalog, _exact_filing_source_set, _manual_result_trace

METRICS = frozenset({'A01', 'A02'})
PROCESSING_FILES = tuple('scripts/vnext/' + n + '.py' for n in (
    'historical_capital_cases', 'historical_annual_input', 'historical_dei',
    'historical_fiscal_labels', 'historical_filing_inventory', 'normal_period_selection',
    'normal_history_catalog', 'normal_accession_results', 'normal_annual_input',
    'normal_governance_input', 'text_results_v2', 'zero_ai_r2')) + (
    POLICY_PATH, 'config/normal_period_selection_v1.json',
    'config/normal_fiscal_year_labels_v1.json', 'catalog/r6/text_results_v2_policy.json',
    'catalog/deterministic_metrics.json')


def _need(condition, reason):
    if not condition:
        raise NormalAccessionError('HISTORICAL_CAPITAL_' + reason)


def inspect_historical_capital_source(**arguments):
    """Reuse the inspector; widen only the known historical release suffixes."""
    reasons = {'NORMAL_ACCESSION_STANDARD_NAMESPACE_CHANGED',
               'NORMAL_ACCESSION_CONCEPT_NAMESPACE_NOT_APPROVED'}
    try:
        inspection = inspect_ordinary_accession_facts(**arguments)
    except NormalAccessionError as error:
        if str(error) not in reasons:
            raise
    else:
        if not reasons.intersection(c['reason'] for c in inspection['conflicts']):
            return inspection, arguments['policy']
    policy = arguments['policy']
    policy = {**policy, **{k: release_aware_pattern(policy[k]) for k in
        ('us_gaap_namespace_pattern', 'srt_namespace_pattern', 'dei_namespace_pattern')}}
    return inspect_ordinary_accession_facts(**{**arguments, 'policy': policy}), policy


def prepare_historical_capital_year_case(*, repo_root, company_id, metric_id, fiscal_year):
    _need(metric_id in METRICS, 'FAMILY_NOT_RECEIVED')
    return _prepare_selected_native_year_case(repo_root=repo_root, company_id=company_id,
        metric_id=metric_id, fiscal_year=fiscal_year)


def _prepare_selected_native_year_case(*, repo_root, company_id, metric_id, fiscal_year):
    # Only the existing native policy's A01/A02/B12 routes are received here.
    _need(metric_id in METRICS | {'B12'}, 'NATIVE_FAMILY_NOT_RECEIVED')
    prefix = 'HISTORICAL_RPO_' if metric_id == 'B12' else 'HISTORICAL_CAPITAL_'
    def need(condition, reason):
        if not condition:
            raise NormalAccessionError(prefix + reason)
    source_root = Path(repo_root)
    selected = resolve_period_selection(repo_root=source_root, company_id=company_id,
        fiscal_year=fiscal_year, rules_root=ROOT)
    prepared = prepare_historical_annual_input(repo_root=source_root, company_id=company_id,
        period_selection=selected, rules_root=ROOT)
    registry = next(r for r in _registry_rows(repo_root=source_root) if r['company_id'] == company_id)
    expected = next(r for r in _registry_rows(repo_root=ROOT) if r['company_id'] == company_id)
    need(registry == expected, 'SOURCE_SUBJECT_CHANGED')
    annual = prepared['table_input']['target_period']
    period = {**annual, 'period_start': annual['period_end']}
    documents = installed_ordinary_spec_documents()
    spec = documents[metric_id]['compiled_spec']
    policy = strict_json_file(path=ROOT/POLICY_PATH)
    route = _load_deterministic_catalog(repo_root=ROOT)['metrics'][metric_id]
    item = policy['metrics'][metric_id]
    reader = _Sources(source_root, company_id, prepared['entity'])
    main = reader.read(submissions_url(cik=int(prepared['entity'])),
        role='sec_submissions_inventory', media_type='application/json')
    source = reader.primary(prepared['filing'])
    inventory = filing_inventory(reader=reader, inventory=main, period_selection=selected,
        cik=prepared['entity'], accession=prepared['filing']['accessionNumber'])
    manifest = _exact_filing_source_set(company_id=company_id, source_role='target_accession_instance',
        reference=source['source_reference'], inventory_reference=inventory['source_reference'],
        inventory_bytes=inventory['raw_bytes'])
    traits = repository_company_traits(repo_root=ROOT, company_id=company_id)
    scope = {'coverage': 'deterministic_source_set', 'fiscal_year': fiscal_year}
    target = {'company_id': company_id, 'period_start': period['period_start'],
        'period_end': period['period_end'], 'scope': scope, 'scope_key': scope_key(scope=scope)}
    inspection, claims, observations = None, [], []
    if not metric_is_applicable(applicability=route['applicability'], traits=traits):
        result, trace = _manual_result_trace(metric_id=metric_id, company_id=company_id,
            period_start=period['period_start'], period_end=period['period_end'], scope=scope,
            spec_closure_hash=spec['spec_closure_hash'], applicability='N_A_STRUCTURAL', quality='NONE',
            reason_code='TRAIT_NOT_APPLICABLE', input_observation_ids=[],
            steps=[{'event': 'N_A_STRUCTURAL'}], accession=prepared['filing']['accessionNumber'],
            entity=prepared['entity'], unit=None)
    else:
        try:
            need(not prepared['amendments'] and prepared['subject_policy']['mode'] == 'CONTINUOUS_PRIMARY',
                  'AMENDMENT_OR_SUCCESSOR_NOT_RECEIVED')
            inspection, used = inspect_historical_capital_source(raw_bytes=source['raw_bytes'],
                source_reference=source['source_reference'], source_set_manifest=manifest,
                expected_cik=prepared['entity'], period_end=period['period_end'], route=route,
                metric_id=metric_id, policy=policy)
            need(inspection['status'] == 'SOURCE_SCOPE_PROVEN', 'SOURCE_SCOPE_UNRESOLVED')
            claims = sorted(inspection['selected_claims'], key=lambda c: c['verified_claim_id'])
            ref = source['source_reference']
            observation = structured_observation(metric_id=metric_id, semantic_role='deterministic_value',
                company_id=company_id, period_start=period['period_start'], period_end=period['period_end'],
                scope=scope, value=claims[0]['value'], unit=item['canonical_unit'], quality='EXACT',
                source_binding={'raw_asset_id': ref['raw_asset_id'], 'source_reference_id': ref['source_reference_id'],
                    'accession': ref['accession'], 'document_name': ref['document_name'], 'source_role': ref['source_role'],
                    'source_set_manifest_id': manifest['source_set_manifest_id'],
                    'verified_claim_ids': [c['verified_claim_id'] for c in claims],
                    'ordinary_policy_hash': content_hash(value=used), 'source_measure': item['measure']})
            result, trace = calculate_observation_metric(compiled_spec=spec, target=target,
                company_traits=traits, observation=observation)
            observations = [observation]
        except NormalAccessionError as error:
            inspection = {**(inspection or {}), 'status': 'UNRESOLVED', 'reason': str(error)}
            result, trace = withheld_metric_result(compiled_spec=spec, target=target,
                reason_code=prefix + 'SOURCE_UNRESOLVED')
    proofs = list({content_hash(value=p): p for p in
        [*prepared['source_proofs'], *[s['proof'] for s in reader.proofs.values()]]}.values())
    admission = verify_ordinary_source_proofs(data_root=source_root, proofs=proofs)
    records = list(reader.records.values())
    binding = {'record_type': 'HISTORICAL_CAPITAL_SOURCE_INPUT', 'prepared_input': prepared,
        'period_selection': selected, 'source_set': manifest, 'metric_id': metric_id,
        'inspection': inspection, 'source_proofs': proofs, 'spec_closure_hash': spec['spec_closure_hash']}
    return {'kind': 'STRUCTURED', 'primary_metric_id': metric_id, 'input_binding': binding,
        'compiled_specs': {metric_id: spec}, 'spec_paths': {metric_id: documents[metric_id]['path']},
        'target_period': period, 'prepared_annual_input': prepared,
        'expected_records': [*records, *claims, *observations, trace, result],
        'results': {metric_id: result}, 'traces': {metric_id: trace},
        'references': [r for r in records if r['record_type'] == 'SOURCE_REFERENCE'],
        'source_proofs': proofs, 'admission': admission, 'selection': inspection, 'rules_root': str(ROOT),
        **({'input_assessments': {'capital_source': inspection}} if inspection else {})}
