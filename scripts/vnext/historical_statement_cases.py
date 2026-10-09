"""Selected annual source roles for B01/B02/B04/B05 at the ordinary company entry.

The installed Specs, source parser, paired-measure check and Calculator own
business calculation. This adapter supplies each filing's actual period and
accession; it does not install native Runs or historical authorization trees.
"""
from datetime import date, timedelta
from pathlib import Path

from sec_urls import companyfacts_url, submissions_url
from .batch_workflow import _structured_concepts
from .calculator import calculate_metric, withheld_metric_result
from .canonical import content_hash
from .historical_annual_input import prepare_historical_annual_input
from .historical_dei import annual_period
from .historical_filing_inventory import filing_inventory, prior_filing
from .normal_annual_input import _registry_rows
from .normal_companyfacts_results import _filing_source, _SOURCE_ERRORS, NormalCompanyfactsError
from .normal_governance_input import _Sources
from .normal_run_specs import installed_ordinary_spec_documents
from .normal_source_authority import ROOT
from .normal_period_selection import resolve_period_selection
from .observations import scope_key
from .ordinary_source_authority import verify_ordinary_source_proofs
from .paired_measure_v1 import paired_measure_problem
from .sources import companyfacts_structured_facts
from .traits import repository_company_traits
from .zero_ai_r2 import _load_deterministic_catalog, _deterministic_metric_graph

METRICS = frozenset({'B01', 'B02', 'B04', 'B05'})
CURRENT_ANNUAL_METRICS = frozenset({'B04', 'B05', 'B07'})
PROCESSING_FILES = (
    'scripts/vnext/historical_statement_cases.py',
    'scripts/vnext/normal_period_selection.py',
    'scripts/vnext/normal_history_catalog.py',
    'scripts/vnext/historical_annual_input.py',
    'scripts/vnext/historical_dei.py',
    'scripts/vnext/historical_fiscal_labels.py',
    'scripts/vnext/historical_filing_inventory.py',
    'scripts/vnext/normal_companyfacts_results.py',
    'scripts/vnext/normal_annual_input.py',
    'scripts/vnext/normal_governance_input.py',
    'scripts/vnext/batch_workflow.py',
    'scripts/vnext/zero_ai_r2.py',
    'scripts/vnext/paired_measure_v1.py',
    'config/normal_period_selection_v1.json',
    'config/normal_fiscal_year_labels_v1.json',
    'catalog/deterministic_metrics.json',
)


class StatementCaseError(ValueError):
    def __init__(self, reason, category='SOURCE_INTEGRITY_ERROR'):
        super().__init__(reason)
        self.category = category


def _need(condition, reason, category='SOURCE_INTEGRITY_ERROR'):
    if not condition:
        raise StatementCaseError(reason, category)


def _registry_for_selected_period(*, registry, prepared, selection):
    """Reuse the retained history rule for a predecessor's own annual period."""
    subject = prepared['subject_policy']
    if subject['mode'] != 'CONTINUOUS_PRIMARY' or registry['entity_continuity_status'] == 'continuous':
        return registry, None
    registrant = selection.get('period_registrant') or {}
    reporting = str(int(prepared['entity']))
    _need(subject.get('cross_entity_combination_authorized') is False
          and str(int(subject['selected_cik'])) == reporting
          and registrant.get('role') == 'PREDECESSOR'
          and str(int(registrant['reporting_cik'])) == reporting
          and str(int(registrant['successor_cik'])) == str(int(registry['primary_cik'])),
          'HISTORICAL_STATEMENT_PERIOD_SUBJECT_NOT_PROVEN')
    detail = {'company_registry_status': registry['entity_continuity_status'],
              'period_subject_policy': subject['mode'], 'period_registrant_cik': reporting,
              'cross_entity_combination_authorized': False}
    return {**registry, 'primary_cik': reporting, 'entity_continuity_status': 'continuous'}, detail


def prepare_historical_statement_year_case(*, repo_root, company_id, metric_id, fiscal_year):
    """Select one issuer year and supply the existing common computation."""
    _need(metric_id in METRICS, 'HISTORICAL_STATEMENT_FAMILY_NOT_RECEIVED', 'IMPLEMENTATION_GAP')
    return _prepare_historical_statement_case(repo_root=repo_root, company_id=company_id,
        metric_id=metric_id, fiscal_year=fiscal_year)


def prepare_historical_current_annual_year_case(*, repo_root, company_id, metric_id, fiscal_year):
    """Use the same case core for received current-annual income metrics."""
    _need(metric_id in CURRENT_ANNUAL_METRICS, 'HISTORICAL_CURRENT_ANNUAL_FAMILY_NOT_RECEIVED',
          'IMPLEMENTATION_GAP')
    route = _load_deterministic_catalog(repo_root=ROOT)['metrics'][metric_id]
    _need(route['adapter_id'] == 'companyfacts' and route['result_period_role'] == 'current_annual'
          and all(c['accession_role'] == 'current' and c['period_role'] == 'current_annual'
                  for branch in route['branches'] for c in branch['components']),
          'HISTORICAL_CURRENT_ANNUAL_SOURCE_ROLE_CHANGED', 'IMPLEMENTATION_GAP')
    return _prepare_historical_statement_case(repo_root=repo_root, company_id=company_id,
        metric_id=metric_id, fiscal_year=fiscal_year, withhold_known_source_errors=True)


def _successor_comparability_case(*, source, company_id, metric_id, prepared, selection):
    """Consume the approved metadata-only guard, without statement claims."""
    route = _load_deterministic_catalog(repo_root=ROOT)['metrics'][metric_id]
    _need(route['adapter_id'] == 'companyfacts' and route['continuity_policy'] == 'REQUIRE_CONTINUOUS'
          and route['result_period_role'] == 'current_annual',
          'HISTORICAL_SUCCESSOR_COMPARABILITY_ROUTE_NOT_RECEIVED', 'IMPLEMENTATION_GAP')
    registry = next(r for r in _registry_rows(repo_root=source) if r['company_id'] == company_id)
    expected = next(r for r in _registry_rows(repo_root=ROOT) if r['company_id'] == company_id)
    subject = prepared['subject_policy']
    _need(subject['mode'] == 'SUCCESSOR_REGISTRANT_ONLY'
          and registry == expected and registry['entity_continuity_status'] != 'continuous'
          and subject['cross_entity_combination_authorized'] is False
          and str(int(subject['selected_cik'])) == str(int(prepared['entity']))
          == str(int(registry['primary_cik'])), 'HISTORICAL_SUCCESSOR_SUBJECT_NOT_PROVEN')
    period = prepared['table_input']['target_period']
    documents = installed_ordinary_spec_documents()
    reader = _Sources(source, company_id, prepared['entity'])
    reader.read(submissions_url(cik=int(prepared['entity'])),
        role='sec_submissions_inventory', media_type='application/json')
    reader.primary(prepared['filing'])
    for filing in prepared['amendments']:
        reader.primary(filing)
    context = {'repo_root': ROOT, 'deterministic_catalog': _load_deterministic_catalog(repo_root=ROOT),
        'role_context': {(company_id, 'companyfacts'): {'sources': [], 'claims_by_accession_role': {}}},
        'target_periods': {company_id: {'current': period, 'prior': None}},
        'targets': {company_id: period}, 'registry': {company_id: registry},
        'filings_by_company': {company_id: {'current': {'accession': prepared['filing']['accessionNumber']}}}}
    graph = _deterministic_metric_graph(context=context, company_id=company_id, metric_id=metric_id)
    result = graph['result']
    _need(result['value'] is None and result['quality'] == 'NOT_MEANINGFUL'
          and result['reason_code'] == 'ENTITY_CONTINUITY_NOT_COMPARABLE'
          and not graph['claims'] and graph['observation'] is None,
          'HISTORICAL_SUCCESSOR_COMPARABILITY_GUARD_CHANGED')
    assessment = {'category': 'APPROVED_COMPARABILITY_LIMIT',
        'reason': 'ENTITY_CONTINUITY_NOT_COMPARABLE', 'subject_policy': subject,
        'statement_values_used': False, 'annual_statement_scope_admitted': False,
        'amendment_scope_not_admitted': bool(prepared['amendments'])}
    proofs = list({content_hash(value=p): p for p in
        [*prepared['source_proofs'], *[s['proof'] for s in reader.proofs.values()]]}.values())
    records = list(reader.records.values())
    return {'kind': 'STRUCTURED', 'primary_metric_id': metric_id,
        'input_binding': {'record_type': 'HISTORICAL_SUCCESSOR_COMPARABILITY_INPUT',
            'prepared_input': prepared, 'period_selection': selection, 'metric_id': metric_id,
            'assessment': assessment},
        'compiled_specs': {metric_id: documents[metric_id]['compiled_spec']},
        'spec_paths': {metric_id: documents[metric_id]['path']}, 'target_period': period,
        'prepared_annual_input': prepared, 'expected_records': [*records, graph['trace'], result],
        'results': {metric_id: result}, 'traces': {metric_id: graph['trace']},
        'references': [r for r in records if r['record_type'] == 'SOURCE_REFERENCE'],
        'source_proofs': proofs, 'admission': verify_ordinary_source_proofs(data_root=source, proofs=proofs),
        'selection': assessment, 'input_assessments': {'successor_comparability': assessment},
        'rules_root': str(ROOT)}


def _prepare_historical_statement_case(*, repo_root, company_id, metric_id, fiscal_year,
                                       withhold_known_source_errors=False):
    """Shared selected-filing case; catalog and Calculator retain computation."""
    source = Path(repo_root)
    selection = resolve_period_selection(repo_root=source, company_id=company_id,
                                         fiscal_year=fiscal_year, rules_root=ROOT)
    prepared = prepare_historical_annual_input(repo_root=source, company_id=company_id,
                                               period_selection=selection, rules_root=ROOT)
    if prepared['subject_policy']['mode'] == 'SUCCESSOR_REGISTRANT_ONLY' and metric_id != 'B01':
        return _successor_comparability_case(source=source, company_id=company_id,
            metric_id=metric_id, prepared=prepared, selection=selection)
    _need(not prepared['amendments'] and prepared['subject_policy']['mode'] == 'CONTINUOUS_PRIMARY',
          'HISTORICAL_STATEMENT_AMENDMENT_OR_SUCCESSOR_NOT_RECEIVED', 'IMPLEMENTATION_GAP')
    period = prepared['table_input']['target_period']
    documents = installed_ordinary_spec_documents()
    spec = documents[metric_id]['compiled_spec']
    _need(not spec['compiled']['dependencies'], 'HISTORICAL_STATEMENT_DEPENDENCY_NOT_RECEIVED')
    registry = next(r for r in _registry_rows(repo_root=source) if r['company_id'] == company_id)
    expected = next(r for r in _registry_rows(repo_root=ROOT) if r['company_id'] == company_id)
    _need(registry == expected, 'HISTORICAL_STATEMENT_SOURCE_SUBJECT_CHANGED')
    period_registry, period_continuity = _registry_for_selected_period(
        registry=registry, prepared=prepared, selection=selection)
    traits = repository_company_traits(repo_root=ROOT, company_id=company_id)
    reader = _Sources(source, company_id, prepared['entity'])
    main = reader.read(submissions_url(cik=int(prepared['entity'])),
                       role='sec_submissions_inventory', media_type='application/json')
    reader.primary(prepared['filing'])
    current_inventory = filing_inventory(reader=reader, inventory=main,
        period_selection=selection, cik=prepared['entity'], accession=prepared['filing']['accessionNumber'])
    catalog = _load_deterministic_catalog(repo_root=ROOT)
    concepts = (_structured_concepts(compiled_spec=spec) if metric_id == 'B01' else
        sorted({c for b in catalog['metrics'][metric_id]['branches']
                for component in b['components'] for c in component['approved_concepts']}))
    current, claims = _filing_source(reader, prepared, prepared['filing'], current_inventory, concepts)
    sources = [{**current, 'accession_role': 'current'}]
    by_role = {'current': claims}
    periods = {'current': period, 'prior': None}
    filings = {'current': prepared['filing'], 'prior': None}
    prior_error = None
    if metric_id == 'B02':
        try:
            prior, listed_in = prior_filing(reader, main, prepared)
            _need(selection['prior_filing'] is not None
                  and prior['accessionNumber'] == selection['prior_filing']['accessionNumber'],
                  'HISTORICAL_STATEMENT_PRIOR_DIFFERS_FROM_SELECTION')
            primary = reader.primary(prior, required=False)
            originals = [primary] if primary else reader.auditor_filing(prior)
            actual = [annual_period(raw=s['raw_bytes'], cik=prepared['entity'], filing=prior)
                      for s in originals]
            _need(actual and all(p == actual[0] for p in actual),
                  'HISTORICAL_STATEMENT_PRIOR_NATIVE_PERIOD_CONFLICT')
            _need(date.fromisoformat(actual[0]['period_end']) + timedelta(days=1)
                  == date.fromisoformat(period['period_start']),
                  'HISTORICAL_STATEMENT_PRIOR_NOT_ADJACENT')
            prior_source, by_role['prior'] = _filing_source(reader, prepared, prior, listed_in, concepts)
            sources.append({**prior_source, 'accession_role': 'prior'})
            periods['prior'], filings['prior'] = actual[0], prior
        except (*_SOURCE_ERRORS, NormalCompanyfactsError, StatementCaseError) as error:
            prior_error = {'reason': str(error), 'error_type': type(error).__name__,
                'category': ('IMPLEMENTATION_GAP' if str(error) ==
                    'NORMAL_COMPANYFACTS_PRIOR_AMENDMENT_REPLAY_NOT_IMPLEMENTED'
                    else getattr(error, 'category', 'SOURCE_OR_IMPLEMENTATION_UNRESOLVED'))}
    scope = ({'entity_scope': 'registrant', 'period_basis': 'source_annual_duration'}
             if metric_id == 'B01' else {'coverage': 'deterministic_source_set', 'fiscal_year': fiscal_year})
    target = {'company_id': company_id, 'period_start': period['period_start'],
              'period_end': period['period_end'], 'scope': scope, 'scope_key': scope_key(scope=scope)}
    assessment = prior_error
    if metric_id == 'B01':
        facts_source = reader.read(companyfacts_url(cik=int(prepared['entity'])),
            accession=prepared['filing']['accessionNumber'], role='companyfacts', media_type='application/json')
        facts = companyfacts_structured_facts(raw_bytes=facts_source['raw_bytes'],
            source_reference=facts_source['source_reference'], approved_concepts=concepts,
            allowed_ciks=[prepared['entity']], include_instant=False)
        result, trace, observations = calculate_metric(compiled_spec=spec,
            target={**target, 'entity': prepared['entity'], 'accession': prepared['filing']['accessionNumber']},
            company_traits=traits, structured_facts=facts, verified_observations=[])
        selected_claims = claims
    elif prior_error:
        result, trace = withheld_metric_result(compiled_spec=spec, target=target,
                                               reason_code='HISTORICAL_PRIOR_INPUT_UNRESOLVED')
        observations, selected_claims = [], []
    else:
        context = {'repo_root': ROOT, 'deterministic_catalog': catalog,
            'role_context': {(company_id, 'companyfacts'): {'sources': sources,
                            'claims_by_accession_role': by_role}},
            'target_periods': {company_id: periods}, 'targets': {company_id: period},
            'registry': {company_id: period_registry}, 'filings_by_company': {company_id:
                {role: {'accession': filing['accessionNumber']} if filing else None
                 for role, filing in filings.items()}}}
        try:
            graph = _deterministic_metric_graph(context=context, company_id=company_id, metric_id=metric_id)
        except (*_SOURCE_ERRORS, NormalCompanyfactsError) as error:
            if not withhold_known_source_errors:
                raise
            assessment = {'category': 'SOURCE_OR_IMPLEMENTATION_UNRESOLVED',
                'reason': str(error), 'error_type': type(error).__name__,
                'catalog_branches': catalog['metrics'][metric_id]['branches'],
                'does_not_establish_missing_filing_disclosure': True}
            result, trace = withheld_metric_result(compiled_spec=spec, target=target,
                reason_code='HISTORICAL_CURRENT_ANNUAL_INPUT_UNRESOLVED')
            observations, selected_claims = [], []
        else:
            problem, bridged = paired_measure_problem(route=catalog['metrics'][metric_id],
                claims=graph['claims'], current_claims=by_role['current'],
                accessions={role: (filing or {}).get('accessionNumber') for role, filing in filings.items()})
            if problem:
                assessment = {'category': 'MEASURE_NOT_COMPARABLE', **problem}
                result, trace = withheld_metric_result(compiled_spec=spec, target=target,
                    reason_code='HISTORICAL_PAIRED_MEASURE_NOT_COMPARABLE')
                observations, selected_claims = [], []
            else:
                result, trace = graph['result'], graph['trace']
                observations = [graph['observation']] if graph['observation'] else []
                selected_claims = graph['claims']
                assessment = {'paired_measure_bridge': bridged} if bridged else None
    if period_continuity is not None:
        assessment = {**(assessment or {}), 'period_continuity': period_continuity}
    proofs = list({content_hash(value=p): p for p in
        [*prepared['source_proofs'], *[s['proof'] for s in reader.proofs.values()]]}.values())
    admission = verify_ordinary_source_proofs(data_root=source, proofs=proofs)
    source_records = list(reader.records.values())
    records = [*source_records, *selected_claims, *observations, trace, result]
    binding = {'record_type': 'HISTORICAL_STATEMENT_SOURCE_INPUT', 'prepared_input': prepared,
        'period_selection': selection, 'metric_id': metric_id, 'filings': filings,
        'actual_periods': periods, 'source_sets': [s['manifest'] for s in sources],
        'claims_by_accession_role': by_role,
        'spec_closure_hash': spec['spec_closure_hash'], 'source_proofs': proofs,
        'assessment': assessment}
    return {'kind': 'STRUCTURED', 'primary_metric_id': metric_id, 'input_binding': binding,
        'compiled_specs': {metric_id: spec}, 'spec_paths': {metric_id: documents[metric_id]['path']},
        'target_period': period, 'prepared_annual_input': prepared, 'expected_records': records,
        'results': {metric_id: result}, 'traces': {metric_id: trace},
        'references': [r for r in source_records if r['record_type'] == 'SOURCE_REFERENCE'],
        'source_proofs': proofs, 'admission': admission, 'selection': assessment, 'rules_root': str(ROOT),
        **({'input_assessments': {'historical_statement': assessment}} if assessment else {})}
