"""Selected annual source roles for B01/B02/B04/B05 at the ordinary company entry.

The installed Specs, source parser, paired-measure check and Calculator own
business calculation. This adapter supplies each filing's actual period and
accession; it does not install native Runs or historical authorization trees.
"""
from datetime import date, timedelta
from pathlib import Path

from sec_urls import companyfacts_url, submissions_url
from .batch_workflow import _structured_concepts
from .calculator import calculate_metric, withheld_metric_result, metric_is_applicable
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
from .selected_income_source_v1 import IncomeSourceError
from .sources import companyfacts_structured_facts
from .traits import repository_company_traits
from .zero_ai_r2 import _load_deterministic_catalog, _deterministic_metric_graph, _manual_result_trace

METRICS = frozenset({'B01', 'B02', 'B04', 'B05'})
CURRENT_ANNUAL_METRICS = frozenset({'B04', 'B05', 'B07'})
# Explicit single-line source bounds have a fixed corrective implementation.
# Only the paired original-revenue consumer opts in; old Total/component
# defaults and existing saved results retain their original meaning.
PAIRED_SINGLE_REVENUE_LINE_ENABLED = True
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
    'scripts/vnext/annual_amendment_scope.py',
    'scripts/vnext/annual_amendment_scope_v2.py',
    'scripts/vnext/amendment_note_layout.py',
    'config/annual_amendment_scope_v1.json',
    'config/normal_period_selection_v1.json',
    'config/normal_fiscal_year_labels_v1.json',
    'catalog/deterministic_metrics.json',
)
INCOME_PROCESSING_FILES = (*PROCESSING_FILES,
    'scripts/vnext/selected_income_source_v1.py',
    'scripts/vnext/selected_revenue_scope_v1.py',
    'scripts/vnext/selected_reported_revenue_v2.py',
    'scripts/vnext/selected_fiscal_definition_scope_v1.py',
    'scripts/vnext/normal_annual_input_v2.py',
    'scripts/vnext/fiscal_year_labels.py',
    'scripts/vnext/composite_scope.py',
    'scripts/vnext/xbrl_namespace_policy.py',
    'scripts/vnext/ordinary_income_input.py',
    'scripts/vnext/financial_duration.py',
    'scripts/vnext/financial_structured.py',
    'scripts/vnext/text_results_v2.py',
    'scripts/vnext/governance_signals.py',
    'scripts/vnext/r5_b06_scope.py',
    'scripts/vnext/deterministic_router.py',
    'catalog/r6/text_results_v2_policy.json',
)



class StatementCaseError(ValueError):
    def __init__(self, reason, category='SOURCE_INTEGRITY_ERROR', *, revenue_scope=None):
        super().__init__(reason)
        self.category = category
        self.revenue_scope = revenue_scope


def _need(condition, reason, category='SOURCE_INTEGRITY_ERROR'):
    if not condition:
        raise StatementCaseError(reason, category)


def _revenue_claims_admitted_by_original(*, reader, prepared, filing, period, claims, concepts):
    """Use the shared source-total filter, retaining original claim identities."""
    from .selected_revenue_scope_v1 import selected_revenue_scope, admit_revenue_facts
    from .selected_reported_revenue_v2 import reported_revenue_scope, admit_reported_revenue_facts
    from .xbrl_namespace_policy import YEAR_OR_DATE_RELEASE
    from .historical_fiscal_labels import resolve_selected_fiscal_year_label
    from .canonical import sha256_bytes
    originals = reader.auditor_filing(filing)
    primary = next((s for s in originals if s['raw_blob']['media_type'] == 'text/html'), None)
    xml = next((s for s in originals if s['raw_blob']['media_type'] == 'application/xml'), None)
    _need(primary is not None, 'HISTORICAL_PAIRED_REVENUE_PRIMARY_REQUIRED', 'SOURCE_UNAVAILABLE')
    facts = reader.read(companyfacts_url(cik=int(prepared['entity'])),
        accession=filing['accessionNumber'], role='companyfacts', media_type='application/json')
    label = resolve_selected_fiscal_year_label(primary_bytes=primary['raw_bytes'],
        companyfacts_bytes=facts['raw_bytes'],
        expected_primary_sha256=sha256_bytes(content=primary['raw_bytes']),
        expected_companyfacts_sha256=sha256_bytes(content=facts['raw_bytes']),
        expected_cik=prepared['entity'], filing=filing)
    source_period = annual_period(raw=primary['raw_bytes'], cik=prepared['entity'], filing=filing)
    _need(all(source_period[key] == period[key] for key in ('period_start', 'period_end')),
          'HISTORICAL_PAIRED_REVENUE_ORIGINAL_PERIOD_CHANGED')
    annual = {'company_id': prepared['company_id'], 'entity': prepared['entity'],
        'filing': filing, 'table_input': {'target_period': source_period}}
    qualified = ['us-gaap:' + c.split(':')[-1] for c in concepts]
    scope = reported_revenue_scope(primary=primary, xml=xml, annual=annual,
        approved_concepts=qualified, namespace_policy=YEAR_OR_DATE_RELEASE,
        annual_period_reader=annual_period, fiscal_label_resolution=label,
        allow_single_revenue_line=PAIRED_SINGLE_REVENUE_LINE_ENABLED)
    admit = admit_reported_revenue_facts
    if not scope['complete_scope_proven']:
        scope = selected_revenue_scope(primary=primary, xml=xml, annual=annual,
            approved_concepts=qualified, namespace_policy=YEAR_OR_DATE_RELEASE,
            annual_period_reader=annual_period)
        admit = admit_revenue_facts
    if not scope['complete_scope_proven']:
        raise StatementCaseError('HISTORICAL_PAIRED_REVENUE_COMPLETE_SCOPE_UNPROVEN',
            'IMPLEMENTATION_GAP', revenue_scope=scope)
    views = []
    for claim in claims:
        _need(claim['claim_kind'] == 'COMPANYFACTS_NUMERIC_FACT'
              and ':' not in claim['locator']['concept'],
              'HISTORICAL_PAIRED_REVENUE_CLAIM_KIND_CHANGED')
        views.append({**claim['locator'], **claim['attributes'],
            'concept': 'us-gaap:' + claim['locator']['concept'],
            'value': claim['value'], 'unit': claim['unit'],
            'verified_claim_id': claim['verified_claim_id']})
    allowed = {v['verified_claim_id'] for v in admit(facts=views, scope=scope)}
    return [claim for claim in claims if claim['verified_claim_id'] in allowed], scope


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


def prepare_historical_statement_year_case(*, repo_root, company_id, metric_id, fiscal_year,
                                           period_selection=None):
    """Select one issuer year and supply the existing common computation."""
    _need(metric_id in METRICS, 'HISTORICAL_STATEMENT_FAMILY_NOT_RECEIVED', 'IMPLEMENTATION_GAP')
    return _prepare_historical_statement_case(repo_root=repo_root, company_id=company_id,
        metric_id=metric_id, fiscal_year=fiscal_year, period_selection=period_selection)


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
    return _metadata_outcome_case(source=source, company_id=company_id, metric_id=metric_id,
        prepared=prepared, selection=selection, graph=graph, assessment=assessment,
        record_type='HISTORICAL_SUCCESSOR_COMPARABILITY_INPUT', assessment_name='successor_comparability')


def _metadata_outcome_case(*, source, company_id, metric_id, prepared, selection,
                           graph, assessment, record_type, assessment_name):
    """Common ordinary case shape for already determined metadata outcomes."""
    period = prepared['table_input']['target_period']
    documents = installed_ordinary_spec_documents()
    reader = _Sources(source, company_id, prepared['entity'])
    reader.read(submissions_url(cik=int(prepared['entity'])),
        role='sec_submissions_inventory', media_type='application/json')
    reader.primary(prepared['filing'])
    for filing in prepared['amendments']:
        reader.primary(filing)
    proofs = list({content_hash(value=p): p for p in
        [*prepared['source_proofs'], *[s['proof'] for s in reader.proofs.values()]]}.values())
    records = list(reader.records.values())
    return {'kind': 'STRUCTURED', 'primary_metric_id': metric_id,
        'input_binding': {'record_type': record_type,
            'prepared_input': prepared, 'period_selection': selection, 'metric_id': metric_id,
            'assessment': assessment},
        'compiled_specs': {metric_id: documents[metric_id]['compiled_spec']},
        'spec_paths': {metric_id: documents[metric_id]['path']}, 'target_period': period,
        'prepared_annual_input': prepared, 'expected_records': [*records, graph['trace'], graph['result']],
        'results': {metric_id: graph['result']}, 'traces': {metric_id: graph['trace']},
        'references': [r for r in records if r['record_type'] == 'SOURCE_REFERENCE'],
        'source_proofs': proofs, 'admission': verify_ordinary_source_proofs(data_root=source, proofs=proofs),
        'selection': assessment, 'input_assessments': {assessment_name: assessment},
        'rules_root': str(ROOT)}


def _statement_amendment_checks(reader, prepared):
    """Consume the shared original-statement proof for this selected filing."""
    if not prepared['amendments']:
        return []
    from .annual_amendment_scope_v2 import inspect_annual_amendment_scope
    original_source = reader.primary(prepared['filing'])
    original = {'raw':original_source['raw_bytes'], 'blob':original_source['raw_blob'],
        'reference':original_source['source_reference'], 'filing':prepared['filing']}
    checks = []
    for filing in prepared['amendments']:
        amended = reader.primary(filing)
        checked = inspect_annual_amendment_scope(original=original,
            amendment={'raw':amended['raw_bytes'], 'blob':amended['raw_blob'],
                'reference':amended['source_reference'], 'filing':filing},
            company_id=prepared['company_id'], cik=prepared['entity'],
            note_layout='inline-paragraphs-v2')
        _need(checked['fiscal_window_unchanged'] and not checked['issues']
              and 'ORIGINAL_STATEMENT_VALUES' in checked['unchanged_input_classes']
              and checked['original_statement_admission_requires_further_review'] is False,
              'HISTORICAL_STATEMENT_AMENDMENT_ORIGINAL_VALUES_NOT_PROVEN',
              'AMENDMENT_INPUT_NOT_CLEARED')
        checks.append(checked)
    return checks


def _prepare_historical_statement_case(*, repo_root, company_id, metric_id, fiscal_year,
                                       withhold_known_source_errors=False, period_selection=None):
    """Shared selected-filing case; catalog and Calculator retain computation."""
    source = Path(repo_root)
    selection = (resolve_period_selection(repo_root=source, company_id=company_id,
                                          fiscal_year=fiscal_year, rules_root=ROOT)
                 if period_selection is None else period_selection)
    prepared = prepare_historical_annual_input(repo_root=source, company_id=company_id,
                                               period_selection=selection, rules_root=ROOT)
    # Explicit selection saves the preceding fiscal-year search only. Annual
    # preparation re-derives its source selection, and the requested label is
    # still checked even when the selection was originally made by report end.
    if period_selection is not None:
        _need(type(fiscal_year) is int and prepared['table_input']['target_period']['fiscal_year'] == fiscal_year,
              'HISTORICAL_STATEMENT_REQUESTED_FISCAL_YEAR_CHANGED')
    if prepared['subject_policy']['mode'] == 'SUCCESSOR_REGISTRANT_ONLY' and metric_id != 'B01':
        return _successor_comparability_case(source=source, company_id=company_id,
            metric_id=metric_id, prepared=prepared, selection=selection)
    _need(prepared['subject_policy']['mode'] == 'CONTINUOUS_PRIMARY'
          and (not prepared['amendments'] or metric_id in METRICS),
          'HISTORICAL_STATEMENT_AMENDMENT_OR_SUCCESSOR_NOT_RECEIVED', 'IMPLEMENTATION_GAP')
    reader = _Sources(source, company_id, prepared['entity']) if prepared['amendments'] else None
    amendment_checks = _statement_amendment_checks(reader, prepared)
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
    if not metric_is_applicable(applicability=spec['compiled']['applicability'], traits=traits):
        scope = {'coverage': 'deterministic_source_set', 'fiscal_year': fiscal_year}
        result, trace = _manual_result_trace(metric_id=metric_id, company_id=company_id,
            period_start=period['period_start'], period_end=period['period_end'], scope=scope,
            spec_closure_hash=spec['spec_closure_hash'], applicability='N_A_STRUCTURAL',
            quality='NONE', reason_code='TRAIT_NOT_APPLICABLE', input_observation_ids=[],
            steps=[{'event':'N_A_STRUCTURAL'}], accession=prepared['filing']['accessionNumber'],
            entity=prepared['entity'], unit=None)
        return _metadata_outcome_case(source=source, company_id=company_id, metric_id=metric_id,
            prepared=prepared, selection=selection, graph={'result':result,'trace':trace},
            assessment={'category':'APPROVED_STRUCTURAL_APPLICABILITY',
                'applicability_rule':spec['compiled']['applicability'], 'traits':traits,
                'statement_values_used':False, 'source_extraction_failure':False},
            record_type='HISTORICAL_STRUCTURAL_APPLICABILITY_INPUT', assessment_name='structural_applicability')
    if reader is None:
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
    paired_revenue_scopes = {}
    if metric_id == 'B02' and not prior_error:
        try:
            for role in ('current', 'prior'):
                by_role[role], paired_revenue_scopes[role] = _revenue_claims_admitted_by_original(
                    reader=reader, prepared=prepared, filing=filings[role], period=periods[role],
                    claims=by_role[role], concepts=concepts)
        except (*_SOURCE_ERRORS, NormalCompanyfactsError, StatementCaseError, IncomeSourceError) as error:
            unresolved_scope = getattr(error, 'revenue_scope', None)
            if unresolved_scope is not None:
                paired_revenue_scopes[role] = unresolved_scope
            prior_error = {'category': getattr(error, 'category', 'SOURCE_OR_IMPLEMENTATION_UNRESOLVED'),
                'reason': str(error), 'error_type': type(error).__name__,
                'unresolved_revenue_role': role,
                'paired_revenue_scopes': paired_revenue_scopes}
            assessment = prior_error
    if metric_id == 'B01':
        from .selected_revenue_scope_v1 import (
            selected_revenue_scope, admit_revenue_facts, verify_revenue_observations, STATEMENT_CONCEPTS)
        from .selected_reported_revenue_v2 import (reported_revenue_scope,
            admit_reported_revenue_facts, verify_reported_revenue_observations)
        from .selected_income_source_v1 import visible_income_periods
        from .selected_income_source_v1 import native_income_reports
        from .deterministic_router import parse_accession_xbrl_source
        from .xbrl_namespace_policy import YEAR_OR_DATE_RELEASE
        from .ordinary_income_input import verify_income_observations
        originals = reader.auditor_filing(prepared['filing'])
        by_kind = {kind: [original for original in originals
                   if original['raw_blob']['media_type'] == media]
                   for kind, media in [('primary', 'text/html'), ('xml', 'application/xml')]}
        _need(all(len(originals) == 1 for originals in by_kind.values()),
              'HISTORICAL_INCOME_ORIGINAL_SOURCE_SET_AMBIGUOUS')
        # Native source identity uses the literal DEI label, while the company
        # result uses the separately resolved issuer fiscal label and dates.
        source_annual = prepared.get('original_input', prepared)
        _need(all(source_annual['table_input']['target_period'][key] == period[key]
                  for key in ('period_start', 'period_end')),
              'HISTORICAL_INCOME_ORIGINAL_PERIOD_CHANGED')
        reported_scope = reported_revenue_scope(primary=by_kind['primary'][0],
            xml=by_kind['xml'][0], annual=source_annual, approved_concepts=concepts,
            namespace_policy=YEAR_OR_DATE_RELEASE, annual_period_reader=annual_period,
            fiscal_label_resolution=prepared.get('fiscal_year_label_resolution'))
        if reported_scope['complete_scope_proven']:
            revenue_scope = reported_scope
            admit_facts = admit_reported_revenue_facts
            check_observations = verify_reported_revenue_observations
            reports = {'primary':reported_scope['original_reports'],
                       'xml':native_income_reports(by_kind['xml'][0],source_annual,
                           sorted(set(concepts)|set(STATEMENT_CONCEPTS)),
                           namespace_policy=YEAR_OR_DATE_RELEASE,annual_period_reader=annual_period)}
        else:
            revenue_scope = selected_revenue_scope(primary=by_kind['primary'][0],
                xml=by_kind['xml'][0], annual=source_annual, approved_concepts=concepts,
                namespace_policy=YEAR_OR_DATE_RELEASE, annual_period_reader=annual_period)
            admit_facts = admit_revenue_facts
            check_observations = verify_revenue_observations
            reports = revenue_scope['original_reports']
        # Preserve the existing visible check for a native short-period fact;
        # the scope helper does not grant that fact an annual interpretation.
        short = [row for row in reports['primary']
                 if row['period_start'] != period['period_start']]
        if short:
            raw = by_kind['primary'][0]['raw_bytes']
            visible = visible_income_periods(raw, parse_accession_xbrl_source(raw_bytes=raw), short)
            for row in short:
                row['visible_period_check'] = visible[row['ordinal']]
        facts_source = reader.read(companyfacts_url(cik=int(prepared['entity'])),
            accession=prepared['filing']['accessionNumber'], role='companyfacts', media_type='application/json')
        facts = companyfacts_structured_facts(raw_bytes=facts_source['raw_bytes'],
            source_reference=facts_source['source_reference'], approved_concepts=concepts,
            allowed_ciks=[prepared['entity']], include_instant=False)
        result, trace, observations = calculate_metric(compiled_spec=spec,
            target={**target, 'entity': prepared['entity'], 'accession': prepared['filing']['accessionNumber']},
            company_traits=traits, structured_facts=admit_facts(facts=facts, scope=revenue_scope),
            verified_observations=[])
        check_observations(observations=observations, scope=revenue_scope)
        assessment = {'selected_revenue_scope': revenue_scope}
        # Bind the CompanyFacts observation to this selected filing's originals.
        # The public reader does no current-year selection or amendment admission.
        if result['publication'] == 'PUBLISHED' and observations:
            checks = verify_income_observations({'annual_input': prepared,
                'statement_period': period, 'original_reports': reports}, observations)
            assessment['income_observation_checks'] = checks
        selected_claims = claims
    elif prior_error:
        result, trace = withheld_metric_result(compiled_spec=spec, target=target,
            reason_code=('HISTORICAL_PAIRED_REVENUE_SCOPE_UNRESOLVED'
                         if 'unresolved_revenue_role' in prior_error
                         else 'HISTORICAL_PRIOR_INPUT_UNRESOLVED'))
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
            if metric_id == 'B02':
                _need(len(graph['claims']) == 2 and all(
                    len([claim for claim in graph['claims']
                         if claim['attributes']['accession'] == filings[role]['accessionNumber']
                         and claim['verified_claim_id'] in
                         {source_claim['verified_claim_id'] for source_claim in by_role[role]}]) == 1
                    for role in ('current', 'prior')),
                    'HISTORICAL_PAIRED_REVENUE_SELECTED_OPERAND_CHANGED')
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
    if amendment_checks:
        assessment = {**(assessment or {}), 'statement_amendment_checks': [
            {key:check[key] for key in ('scope_id','classification','fiscal_window_unchanged',
                'unchanged_input_classes','issues','policy_hash')}
            for check in amendment_checks]}
    if paired_revenue_scopes:
        assessment = {**(assessment or {}), 'paired_revenue_scopes': paired_revenue_scopes}
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
        'assessment': assessment,
        **({'statement_amendment_checks':amendment_checks} if amendment_checks else {})}
    display_assessment = assessment
    if assessment and 'selected_revenue_scope' in assessment:
        revenue_scope = assessment['selected_revenue_scope']
        display_assessment = {**assessment, 'selected_revenue_scope': {
            key: revenue_scope[key] for key in ('scope_id', 'status', 'complete_scope_proven')}}
        if 'income_observation_checks' in assessment:
            display_assessment['income_observation_checks'] = [
                {'observation_id': check['observation_id'],
                 'source_roles': sorted(check['original_reports'])}
                for check in assessment['income_observation_checks']]
    if assessment and 'paired_revenue_scopes' in assessment:
        display_assessment = {**(display_assessment or {}), 'paired_revenue_scopes': {
            role: {key: source_scope[key] for key in ('scope_id', 'status', 'complete_scope_proven')}
            for role, source_scope in assessment['paired_revenue_scopes'].items()}}
    return {'kind': 'STRUCTURED', 'primary_metric_id': metric_id, 'input_binding': binding,
        'compiled_specs': {metric_id: spec}, 'spec_paths': {metric_id: documents[metric_id]['path']},
        'target_period': period, 'prepared_annual_input': prepared, 'expected_records': records,
        'results': {metric_id: result}, 'traces': {metric_id: trace},
        'references': [r for r in source_records if r['record_type'] == 'SOURCE_REFERENCE'],
        'source_proofs': proofs, 'admission': admission, 'selection': display_assessment, 'rules_root': str(ROOT),
        **({'input_assessments': {'historical_statement': assessment}} if assessment else {})}
