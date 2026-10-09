"""Selected historical disclosure counts through the existing event route.

This adapter owns the selected issuer year. Source collection, item matching,
calculation and ordinary persistence keep their existing implementations. E01's
content confirmation and the successor multi-CIK source API remain explicit
separate dependencies; neither is replaced by a partial count here.
"""
from pathlib import Path
from sec_urls import submissions_url
from .annual_sources import AnnualUpdateError
from .batch_workflow import BatchWorkflowError
from .calculator import calculate_observation_metric, withheld_metric_result
from .canonical import content_hash
from .historical_annual_input import prepare_historical_annual_input
from .historical_event_walk import event_sources
from .normal_history_catalog import HistoryCatalogError
from .historical_amendment_admission import AmendmentAdmissionError
from .normal_governance_input import _Sources, NormalGovernanceInputError
from .normal_period_selection import resolve_period_selection
from .normal_run_specs import installed_ordinary_spec_documents
from .normal_source_authority import ROOT
from .normal_zero_ai_results import NormalZeroAiError
from .observations import scope_key, structured_observation
from .ordinary_source_authority import verify_ordinary_source_proofs
from .deterministic_router import load_event_route_catalog, project_event_result
from .sources import SourceError
from .traits import repository_company_traits

METRICS = frozenset({'C01', 'E02', 'E03', 'E04', 'E05'})
PROCESSING_FILES = tuple('scripts/vnext/' + name + '.py' for name in (
    'historical_event_cases', 'historical_event_walk', 'normal_zero_ai_results',
    'normal_history_catalog', 'normal_period_selection', 'historical_annual_input',
    'historical_dei', 'historical_fiscal_labels', 'normal_governance_input',
    'normal_annual_input', 'deterministic_router', 'public_projection',
    'historical_amendment_admission', 'historical_amendment_note',
    'annual_amendment_scope', 'zero_ai_r2')) + (
    'config/normal_period_selection_v1.json', 'config/normal_fiscal_year_labels_v1.json',
    'config/annual_amendment_scope_v1.json', 'catalog/event_routes.json',
    'catalog/zero_ai_public_projection.json')


def prepare_historical_event_year_case(*, repo_root, company_id, metric_id, fiscal_year):
    if metric_id not in METRICS:
        raise NormalZeroAiError('HISTORICAL_EVENT_CONTENT_FAMILY_NOT_RECEIVED')
    source = Path(repo_root)
    selected = resolve_period_selection(repo_root=source, company_id=company_id,
                                        fiscal_year=fiscal_year, rules_root=ROOT)
    prepared = prepare_historical_annual_input(repo_root=source, company_id=company_id,
                                             period_selection=selected, rules_root=ROOT)
    if prepared['subject_policy']['mode'] != 'CONTINUOUS_PRIMARY':
        raise NormalZeroAiError('HISTORICAL_REGISTERED_EVENT_SOURCE_API_NOT_RECEIVED')
    period = prepared['table_input']['target_period']
    documents = installed_ordinary_spec_documents(); spec = documents[metric_id]['compiled_spec']
    catalog = load_event_route_catalog(repo_root=ROOT)
    if catalog['routes'][metric_id]['keyword_item_rules'] or 'confirmation' in catalog['routes'][metric_id]:
        raise NormalZeroAiError('HISTORICAL_EVENT_CONTENT_ROUTE_NOT_RECEIVED')
    reader = _Sources(source, company_id, prepared['entity'])
    inventory = reader.read(submissions_url(cik=int(prepared['entity'])),
                            role='sec_submissions_inventory', media_type='application/json')
    scope = {'coverage': 'fiscal_year_source_set', 'fiscal_year': fiscal_year,
             'shared_claim_group_id': catalog['routes'][metric_id]['shared_claim_group_id']}
    target = {'company_id': company_id, 'period_start': period['period_start'],
              'period_end': period['period_end'], 'scope': scope, 'scope_key': scope_key(scope=scope)}
    claims, source_sets, filings, observations, selection = [], [], [], [], None
    try:
        if prepared['amendments']:
            from .historical_amendment_admission import amendment_admission
            amendment_admission(repo_root=source, company_id=company_id, metric_ids=[metric_id],
                prepared=prepared, event_metric_ids=METRICS)
        claims, source_sets, filings = event_sources(repo_root=source, reader=reader,
                                                     prepared=prepared, inventory=inventory)
        graph = project_event_result(metric_id=metric_id, claims=claims,
            source_set_manifest=source_sets[-1], inventory_source_reference=inventory['source_reference'],
            target_period=period, catalog=catalog)
        original = graph['observation']
        binding = {**original['source_binding'],
                   'source_role': inventory['source_reference']['source_role'],
                   'source_set_role': source_sets[-1]['source_role']}
        observation = structured_observation(metric_id=metric_id,
            semantic_role=original['semantic_role'], company_id=company_id,
            period_start=period['period_start'], period_end=period['period_end'],
            scope=original['scope'], value=original['value'], unit=original['unit'],
            quality=original['quality'], source_binding=binding)
        result, trace = calculate_observation_metric(compiled_spec=spec, target=target,
            company_traits=repository_company_traits(repo_root=ROOT, company_id=company_id),
            observation=observation)
        observations = [observation]
        selection = {'reason_code': result['reason_code'],
            'matched_verified_claim_ids': graph['matched_verified_claim_ids'],
            'source_event_accessions': sorted({f['accessionNumber'] for f in filings})}
    except (NormalZeroAiError, NormalGovernanceInputError, AnnualUpdateError,
            BatchWorkflowError, SourceError, AmendmentAdmissionError, HistoryCatalogError) as error:
        result, trace = withheld_metric_result(compiled_spec=spec, target=target,
                                               reason_code='HISTORICAL_EVENT_SOURCE_UNRESOLVED')
        selection = {'reason_code': result['reason_code'], 'reason': str(error),
                     'category': ('AMENDMENT_INPUT_NOT_CLEARED' if isinstance(error, AmendmentAdmissionError)
                                  else getattr(error, 'category', 'SOURCE_INTEGRITY_ERROR'))}
    records = list(reader.records.values())
    proofs = list({content_hash(value=p): p for p in [*prepared['source_proofs'],
        *[entry['proof'] for entry in reader.proofs.values()]]}.values())
    admission = verify_ordinary_source_proofs(data_root=source, proofs=proofs)
    binding = {'record_type': 'HISTORICAL_EVENT_SOURCE_INPUT', 'prepared_input': prepared,
        'period_selection': selected, 'metric_id': metric_id, 'event_window': period,
        'source_set_manifests': source_sets, 'claims': claims, 'filings': filings, 'selection': selection,
        'source_proofs': proofs, 'source_admission': admission,
        'financial_cross_entity_combination_authorized': False}
    return {'kind': 'STRUCTURED', 'primary_metric_id': metric_id, 'input_binding': binding,
        'compiled_specs': {metric_id: spec}, 'spec_paths': {metric_id: documents[metric_id]['path']},
        'target_period': period, 'prepared_annual_input': prepared,
        'expected_records': [*records, *claims, *observations, trace, result],
        'results': {metric_id: result}, 'traces': {metric_id: trace},
        'references': [r for r in records if r['record_type'] == 'SOURCE_REFERENCE'],
        'source_proofs': proofs, 'admission': admission, 'selection': selection,
        'rules_root': str(ROOT),
        **({'input_assessments': {'historical_event': selection}}
           if result['publication'] == 'WITHHELD' else {})}
