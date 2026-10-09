"""Historical bank performance source roles, using the existing catalog graph."""
from datetime import date, timedelta
from decimal import DecimalException
from pathlib import Path

from sec_urls import submissions_url
from .calculator import metric_is_applicable, withheld_metric_result
from .canonical import content_hash
from .historical_annual_input import prepare_historical_annual_input
from .historical_dei import annual_period
from .historical_filing_inventory import filing_inventory, prior_filing
from .normal_annual_input import _registry_rows
from .normal_companyfacts_results import _filing_source, _SOURCE_ERRORS, NormalCompanyfactsError
from .normal_governance_input import _Sources
from .normal_period_selection import resolve_period_selection
from .normal_run_specs import installed_ordinary_spec_documents
from .normal_source_authority import ROOT
from .observations import scope_key
from .ordinary_source_authority import verify_ordinary_source_proofs
from .paired_measure_v1 import paired_measure_problem
from .traits import repository_company_traits
from .zero_ai_r2 import _load_deterministic_catalog, _deterministic_metric_graph, _manual_result_trace

METRICS = frozenset({'A05', 'A06', 'A07', 'A08', 'A10'})
PROCESSING_FILES = tuple('scripts/vnext/' + n + '.py' for n in (
    'historical_bank_performance_cases', 'historical_annual_input', 'historical_dei',
    'historical_fiscal_labels', 'historical_filing_inventory', 'normal_history_catalog',
    'normal_period_selection', 'normal_annual_input', 'normal_governance_input',
    'normal_companyfacts_results', 'paired_measure_v1', 'zero_ai_r2')) + (
    'config/normal_period_selection_v1.json', 'config/normal_fiscal_year_labels_v1.json',
    'catalog/deterministic_metrics.json')


def _need(condition, reason):
    if not condition:
        raise NormalCompanyfactsError('HISTORICAL_BANK_' + reason)


def prepare_historical_bank_year_case(*, repo_root, company_id, metric_id, fiscal_year):
    _need(metric_id in METRICS, 'FAMILY_NOT_RECEIVED')
    source_root = Path(repo_root)
    selection = resolve_period_selection(repo_root=source_root, company_id=company_id,
        fiscal_year=fiscal_year, rules_root=ROOT)
    prepared = prepare_historical_annual_input(repo_root=source_root, company_id=company_id,
        period_selection=selection, rules_root=ROOT)
    registry = next(r for r in _registry_rows(repo_root=source_root) if r['company_id'] == company_id)
    expected = next(r for r in _registry_rows(repo_root=ROOT) if r['company_id'] == company_id)
    _need(registry == expected, 'SOURCE_SUBJECT_CHANGED')
    annual = prepared['table_input']['target_period']
    documents = installed_ordinary_spec_documents()
    spec = documents[metric_id]['compiled_spec']
    catalog = _load_deterministic_catalog(repo_root=ROOT)
    route = catalog['metrics'][metric_id]
    period = {**annual, **({'period_start': annual['period_end']}
                          if route['result_period_role'] == 'current_instant' else {})}
    scope = {'coverage': 'deterministic_source_set', 'fiscal_year': fiscal_year}
    target = {'company_id': company_id, 'period_start': period['period_start'],
        'period_end': period['period_end'], 'scope': scope, 'scope_key': scope_key(scope=scope)}
    reader = _Sources(source_root, company_id, prepared['entity'])
    main = reader.read(submissions_url(cik=int(prepared['entity'])),
        role='sec_submissions_inventory', media_type='application/json')
    reader.primary(prepared['filing'])
    inventory = filing_inventory(reader=reader, inventory=main, period_selection=selection,
        cik=prepared['entity'], accession=prepared['filing']['accessionNumber'])
    traits = repository_company_traits(repo_root=ROOT, company_id=company_id)
    sources, source_sets, by_role, claims, observations = [], [], {}, [], []
    periods = {'current': annual, 'prior': None}
    filings = {'current': prepared['filing'], 'prior': None}
    assessment = None
    if not metric_is_applicable(applicability=route['applicability'], traits=traits):
        result, trace = _manual_result_trace(metric_id=metric_id, company_id=company_id,
            period_start=period['period_start'], period_end=period['period_end'], scope=scope,
            spec_closure_hash=spec['spec_closure_hash'], applicability='N_A_STRUCTURAL', quality='NONE',
            reason_code='TRAIT_NOT_APPLICABLE', input_observation_ids=[],
            steps=[{'event': 'N_A_STRUCTURAL'}], accession=prepared['filing']['accessionNumber'],
            entity=prepared['entity'], unit=None)
    else:
        try:
            _need(not prepared['amendments'] and prepared['subject_policy']['mode'] == 'CONTINUOUS_PRIMARY',
                  'AMENDMENT_OR_SUCCESSOR_NOT_RECEIVED')
            concepts = sorted({c for b in route['branches'] for part in b['components']
                               for c in part['approved_concepts']})
            current, by_role['current'] = _filing_source(reader, prepared, prepared['filing'], inventory, concepts)
            sources.append({**current, 'accession_role': 'current'})
            needs_prior = any(c['accession_role'] == 'prior' for b in route['branches'] for c in b['components'])
            if needs_prior:
                prior, listed_in = prior_filing(reader, main, prepared)
                _need(selection['prior_filing'] is not None and
                      prior['accessionNumber'] == selection['prior_filing']['accessionNumber'], 'PRIOR_SELECTION_DIFFERS')
                primary = reader.primary(prior, required=False)
                originals = [primary] if primary else reader.auditor_filing(prior)
                actual = [annual_period(raw=s['raw_bytes'], cik=prepared['entity'], filing=prior) for s in originals]
                _need(actual and all(p == actual[0] for p in actual), 'PRIOR_NATIVE_PERIOD_CONFLICT')
                _need(date.fromisoformat(actual[0]['period_end']) + timedelta(days=1)
                      == date.fromisoformat(annual['period_start']), 'PRIOR_NOT_ADJACENT')
                previous, by_role['prior'] = _filing_source(reader, prepared, prior, listed_in, concepts)
                sources.append({**previous, 'accession_role': 'prior'})
                periods['prior'], filings['prior'] = actual[0], prior
            context = {'repo_root': ROOT, 'deterministic_catalog': catalog,
                'role_context': {(company_id, 'companyfacts'): {'sources': sources, 'claims_by_accession_role': by_role}},
                'target_periods': {company_id: periods}, 'targets': {company_id: annual},
                'registry': {company_id: registry}, 'filings_by_company': {company_id:
                    {role: {'accession': f['accessionNumber']} if f else None for role, f in filings.items()}}}
            graph = _deterministic_metric_graph(context=context, company_id=company_id, metric_id=metric_id)
            if needs_prior:
                problem, bridge = paired_measure_problem(route=route, claims=graph['claims'],
                    current_claims=by_role['current'], accessions={role: (f or {}).get('accessionNumber') for role, f in filings.items()})
                if problem is not None:
                    assessment = {'category': 'MEASURE_NOT_COMPARABLE', **problem}
                    raise NormalCompanyfactsError('HISTORICAL_BANK_PAIRED_MEASURE_NOT_COMPARABLE')
                assessment = {'paired_measure_bridge': bridge} if bridge else None
            result, trace, claims = graph['result'], graph['trace'], graph['claims']
            observations = [graph['observation']] if graph['observation'] else []
        except (*_SOURCE_ERRORS, NormalCompanyfactsError, DecimalException) as error:
            assessment = {**(assessment or {'category': 'SOURCE_OR_IMPLEMENTATION_UNRESOLVED'}),
                'reason': str(error), 'error_type': type(error).__name__}
            result, trace = withheld_metric_result(compiled_spec=spec, target=target,
                reason_code='HISTORICAL_BANK_INPUT_UNRESOLVED')
    source_sets = [s['manifest'] for s in sources]
    proofs = list({content_hash(value=p): p for p in
        [*prepared['source_proofs'], *[s['proof'] for s in reader.proofs.values()]]}.values())
    admission = verify_ordinary_source_proofs(data_root=source_root, proofs=proofs)
    records = list(reader.records.values())
    binding = {'record_type': 'HISTORICAL_BANK_SOURCE_INPUT', 'prepared_input': prepared,
        'period_selection': selection, 'metric_id': metric_id, 'actual_periods': periods,
        'filings': filings, 'source_sets': source_sets, 'claims_by_accession_role': by_role,
        'assessment': assessment, 'spec_closure_hash': spec['spec_closure_hash'], 'source_proofs': proofs}
    return {'kind': 'STRUCTURED', 'primary_metric_id': metric_id, 'input_binding': binding,
        'compiled_specs': {metric_id: spec}, 'spec_paths': {metric_id: documents[metric_id]['path']},
        'target_period': period, 'prepared_annual_input': prepared,
        'expected_records': [*records, *claims, *observations, trace, result],
        'results': {metric_id: result}, 'traces': {metric_id: trace},
        'references': [r for r in records if r['record_type'] == 'SOURCE_REFERENCE'],
        'source_proofs': proofs, 'admission': admission, 'selection': assessment, 'rules_root': str(ROOT),
        **({'input_assessments': {'bank_source': assessment}} if assessment else {})}
