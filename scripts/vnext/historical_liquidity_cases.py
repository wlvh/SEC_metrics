"""Selected balance-date B08/B09 cases for the common company controller."""
from pathlib import Path

from sec_urls import submissions_url
from .calculator import metric_is_applicable, withheld_metric_result
from .canonical import content_hash
from .historical_annual_input import prepare_historical_annual_input
from .historical_filing_inventory import filing_inventory
from .instant_balance_amendment import inspect_instant_balance_amendment, InstantAmendmentError
from .annual_amendment_scope import AmendmentScopeError
from .normal_annual_input import _registry_rows
from .normal_companyfacts_results import _filing_source, _SOURCE_ERRORS, NormalCompanyfactsError
from .normal_governance_input import _Sources
from .normal_period_selection import resolve_period_selection
from .normal_run_specs import installed_ordinary_spec_documents
from .normal_source_authority import ROOT
from .observations import scope_key
from .ordinary_source_authority import verify_ordinary_source_proofs
from .traits import repository_company_traits
from .zero_ai_r2 import _load_deterministic_catalog, _deterministic_metric_graph, _manual_result_trace

METRICS = frozenset({'B08', 'B09'})
PROCESSING_FILES = tuple('scripts/vnext/' + name + '.py' for name in (
    'historical_liquidity_cases', 'historical_annual_input', 'historical_dei',
    'historical_fiscal_labels', 'historical_filing_inventory', 'normal_period_selection',
    'normal_history_catalog', 'normal_governance_input', 'normal_annual_input',
    'normal_companyfacts_results', 'zero_ai_r2', 'instant_balance_amendment',
    'annual_amendment_scope', 'amendment_note_layout', 'composite_scope', 'text_results_v2')) + (
        'config/normal_period_selection_v1.json', 'config/normal_fiscal_year_labels_v1.json',
        'catalog/deterministic_metrics.json', 'config/instant_balance_amendment_v1.json',
        'config/annual_amendment_scope_v1.json', 'catalog/r6/text_results_v2_policy.json')


def _need(condition, reason):
    if not condition:
        raise ValueError('HISTORICAL_LIQUIDITY_' + reason)


def prepare_historical_liquidity_year_case(*, repo_root, company_id, metric_id, fiscal_year):
    """Keep the issuer FY label and calculate its actual end-date balance."""
    _need(metric_id in METRICS, 'FAMILY_NOT_RECEIVED')
    source = Path(repo_root)
    selected = resolve_period_selection(repo_root=source, company_id=company_id,
        fiscal_year=fiscal_year, rules_root=ROOT)
    prepared = prepare_historical_annual_input(repo_root=source, company_id=company_id,
        period_selection=selected, rules_root=ROOT)
    subject = prepared['subject_policy']
    _need(subject['mode'] in {'CONTINUOUS_PRIMARY', 'SUCCESSOR_REGISTRANT_ONLY'}
          and str(int(subject['selected_cik'])) == str(int(prepared['entity']))
          and subject['cross_entity_combination_authorized'] is False,
          'SUBJECT_SCOPE_NOT_RECEIVED')
    annual = prepared['table_input']['target_period']
    period = {**annual, 'period_start': annual['period_end']}
    documents = installed_ordinary_spec_documents()
    spec = documents[metric_id]['compiled_spec']
    _need(not spec['compiled']['dependencies'], 'DEPENDENCY_NOT_RECEIVED')
    registry = next(r for r in _registry_rows(repo_root=source) if r['company_id'] == company_id)
    expected = next(r for r in _registry_rows(repo_root=ROOT) if r['company_id'] == company_id)
    _need(registry == expected, 'SOURCE_SUBJECT_CHANGED')
    reader = _Sources(source, company_id, prepared['entity'])
    main = reader.read(submissions_url(cik=int(prepared['entity'])),
        role='sec_submissions_inventory', media_type='application/json')
    primary = reader.primary(prepared['filing'])
    inventory = filing_inventory(reader=reader, inventory=main, period_selection=selected,
        cik=prepared['entity'], accession=prepared['filing']['accessionNumber'])
    catalog = _load_deterministic_catalog(repo_root=ROOT)
    route = catalog['metrics'][metric_id]
    _need(route['source_role'] == 'companyfacts' and route['result_period_role'] == 'current_instant'
          and route['continuity_policy'] == 'ALLOW'
          and all(c['accession_role'] == 'current' and c['period_role'] == 'current_instant'
                  for b in route['branches'] for c in b['components']),
          'SOURCE_OR_PERIOD_ROLE_CHANGED')
    scope = {'coverage': 'deterministic_source_set', 'fiscal_year': fiscal_year}
    source_sets, by_role, claims, observations = [], {'current': []}, [], []
    assessment = None
    amendment_checks = []
    if not metric_is_applicable(applicability=route['applicability'],
                                traits=repository_company_traits(repo_root=ROOT, company_id=company_id)):
        result, trace = _manual_result_trace(metric_id=metric_id, company_id=company_id,
            period_start=period['period_start'], period_end=period['period_end'], scope=scope,
            spec_closure_hash=spec['spec_closure_hash'], applicability='N_A_STRUCTURAL',
            quality='NONE', reason_code='TRAIT_NOT_APPLICABLE', input_observation_ids=[],
            steps=[{'event': 'N_A_STRUCTURAL'}], accession=prepared['filing']['accessionNumber'],
            entity=prepared['entity'], unit=None)
    else:
        original = {'raw': primary['raw_bytes'], 'blob': primary['raw_blob'],
                    'reference': primary['source_reference'], 'filing': prepared['filing']}
        for filing in prepared['amendments']:
            amended = reader.primary(filing)
            amendment = {'raw': amended['raw_bytes'], 'blob': amended['raw_blob'],
                         'reference': amended['source_reference'], 'filing': filing}
            try:
                check = inspect_instant_balance_amendment(original=original,
                    amendment=amendment, company_id=company_id, cik=prepared['entity'],
                    note_layout='inline-paragraphs-v2')
            except (AmendmentScopeError, InstantAmendmentError) as error:
                check = {'decision': 'WITHHELD', 'metric_ids': [metric_id],
                    'original_accession': prepared['filing']['accessionNumber'],
                    'amendment_accession': filing['accessionNumber'],
                    'issues': [{'reason': str(error), 'error_type': type(error).__name__}],
                    'source_scope_unresolved': True, 'annual_continuity_proven': False}
            amendment_checks.append(check)
        blocked = [c for c in amendment_checks
                   if c['decision'] != 'INPUT_PROPERTY_PROVEN' or metric_id not in c['metric_ids']]
        if blocked:
            assessment = {'category': 'AMENDMENT_INPUT_UNRESOLVED', 'checks': amendment_checks,
                          'annual_continuity_proven': False}
        concepts = sorted({c for b in route['branches'] for component in b['components']
                           for c in component['approved_concepts']})
        current, by_role['current'] = _filing_source(reader, prepared, prepared['filing'], inventory, concepts)
        source_sets = [current['manifest']]
        context = {'repo_root': ROOT, 'deterministic_catalog': catalog,
            'role_context': {(company_id, 'companyfacts'): {'sources': [{**current, 'accession_role': 'current'}],
                'claims_by_accession_role': by_role}},
            'target_periods': {company_id: {'current': annual, 'prior': None}},
            'targets': {company_id: annual}, 'registry': {company_id: registry},
            'filings_by_company': {company_id: {'current': {'accession': prepared['filing']['accessionNumber']}}}}
        try:
            if blocked:
                raise NormalCompanyfactsError('HISTORICAL_LIQUIDITY_AMENDMENT_INPUT_UNRESOLVED')
            graph = _deterministic_metric_graph(context=context, company_id=company_id, metric_id=metric_id)
            result, trace, claims = graph['result'], graph['trace'], graph['claims']
            observations = [graph['observation']] if graph['observation'] else []
        except (*_SOURCE_ERRORS, NormalCompanyfactsError) as error:
            assessment = {**(assessment or {'category': 'SOURCE_OR_IMPLEMENTATION_UNRESOLVED'}),
                          'reason': str(error), 'error_type': type(error).__name__}
            result, trace = withheld_metric_result(compiled_spec=spec, target={
                'company_id': company_id, 'period_start': period['period_start'],
                'period_end': period['period_end'], 'scope': scope, 'scope_key': scope_key(scope=scope)},
                reason_code='HISTORICAL_LIQUIDITY_ROUTE_UNRESOLVED')
    _need(all(result[k] == period[k] for k in ('period_start', 'period_end')),
          'RESULT_BALANCE_DATE_CHANGED')
    proofs = list({content_hash(value=p): p for p in
        [*prepared['source_proofs'], *[s['proof'] for s in reader.proofs.values()]]}.values())
    admission = verify_ordinary_source_proofs(data_root=source, proofs=proofs)
    records = list(reader.records.values())
    binding = {'record_type': 'HISTORICAL_LIQUIDITY_SOURCE_INPUT', 'prepared_input': prepared,
        'period_selection': selected, 'metric_id': metric_id, 'annual_container': annual,
        'balance_period': period, 'source_sets': source_sets, 'claims_by_accession_role': by_role,
        'spec_closure_hash': spec['spec_closure_hash'], 'source_proofs': proofs,
        'assessment': assessment, 'amendment_checks': amendment_checks,
        'subject_scope': 'SELECTED_CIK_CURRENT_INSTANT_ONLY', 'annual_continuity_proven': False}
    assessments = {'historical_liquidity': assessment} if assessment else {}
    if amendment_checks or subject['mode'] != 'CONTINUOUS_PRIMARY':
        assessments['historical_liquidity_scope'] = {
            'selected_cik': prepared['entity'], 'subject_policy': subject,
            'subject_scope': 'SELECTED_CIK_CURRENT_INSTANT_ONLY',
            'amendment_checks': amendment_checks, 'annual_continuity_proven': False,
            'cross_entity_combination_authorized': False}
    return {'kind': 'STRUCTURED', 'primary_metric_id': metric_id, 'input_binding': binding,
        'compiled_specs': {metric_id: spec}, 'spec_paths': {metric_id: documents[metric_id]['path']},
        'target_period': period, 'prepared_annual_input': prepared,
        'expected_records': [*records, *claims, *observations, trace, result],
        'results': {metric_id: result}, 'traces': {metric_id: trace},
        'references': [r for r in records if r['record_type'] == 'SOURCE_REFERENCE'],
        'source_proofs': proofs, 'admission': admission, 'selection': assessment, 'rules_root': str(ROOT),
        **({'input_assessments': assessments} if assessments else {})}
