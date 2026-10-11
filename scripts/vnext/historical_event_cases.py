"""Selected historical disclosure counts through the existing event route.

This adapter owns the selected issuer year. Source collection, item matching,
calculation and ordinary persistence keep their existing implementations. E01's
content confirmation and the successor multi-CIK source API remain explicit
separate dependencies; neither is replaced by a partial count here.
"""
from pathlib import Path
from sec_urls import submissions_url, accession_document_url
from .annual_sources import AnnualUpdateError
from .batch_workflow import BatchWorkflowError
from .calculator import calculate_observation_metric, withheld_metric_result
from .canonical import content_hash, strict_json_file, strict_json_loads
from .historical_annual_input import prepare_historical_annual_input
from .normal_history_catalog import HistoryCatalogError, block_last_days, history_block_coherence
from .selected_event_source_v1 import read_selected_event_sources, SelectedEventSourceError
from .annual_amendment_scope import AmendmentScopeError
from .annual_amendment_scope_v2 import inspect_annual_amendment_scope
from .public_projection import event_target_period
from .normal_governance_input import _Sources, NormalGovernanceInputError, _history_index
from .normal_period_selection import resolve_period_selection
from .normal_run_specs import installed_ordinary_spec_documents
from .normal_source_authority import ROOT
from .normal_zero_ai_results import NormalZeroAiError
from .observations import scope_key, structured_observation
from .ordinary_source_authority import verify_ordinary_source_proofs
from .deterministic_router import load_event_route_catalog, project_event_result
from .sources import SourceError
from .traits import repository_company_traits, repository_company_ciks

METRICS = frozenset({'C01', 'E02', 'E03', 'E04', 'E05'})
PROCESSING_FILES = tuple('scripts/vnext/' + name + '.py' for name in (
    'historical_event_cases', 'selected_event_source_v1', 'normal_zero_ai_results',
    'normal_history_catalog', 'normal_period_selection', 'historical_annual_input',
    'historical_dei', 'historical_fiscal_labels', 'normal_governance_input',
    'normal_annual_input', 'deterministic_router', 'public_projection',
    'annual_amendment_scope', 'annual_amendment_scope_v2', 'amendment_note_layout',
    'composite_scope', 'text_results_v2', 'zero_ai_r2')) + (
    'config/normal_period_selection_v1.json', 'config/normal_fiscal_year_labels_v1.json',
    'config/annual_amendment_scope_v1.json', 'catalog/event_routes.json',
    'catalog/r6/text_results_v2_policy.json', 'catalog/zero_ai_public_projection.json')


class EventAmendmentError(ValueError):
    category = 'AMENDMENT_INPUT_NOT_CLEARED'


def selected_event_window(prepared, *, rules_root=ROOT):
    """Keep the issuer annual container and approved event measurement distinct."""
    mode = prepared['subject_policy']['mode']
    if mode not in {'CONTINUOUS_PRIMARY', 'SUCCESSOR_REGISTRANT_ONLY'}:
        raise NormalZeroAiError('HISTORICAL_EVENT_SUBJECT_NOT_RECEIVED')
    pinned = prepared['table_input']['target_period']
    union = mode == 'SUCCESSOR_REGISTRANT_ONLY'
    if not union:
        return dict(pinned), False
    catalog = strict_json_file(path=Path(rules_root)/'catalog/zero_ai_public_projection.json')
    return event_target_period(target_period=pinned,
        continuity_status='successor_predecessor', catalog=catalog), True


def check_historical_event_block(*, shard, body, rows, shards, period, last_day):
    """Use the public walk's effective end and the complete selected body.

    The consumer supplies block_last_days itself to the public interface; that
    interface computes the bound from the actual inventory it just read and
    passes the same bound used for selection. No second metadata read or
    independent source cache is needed.
    """
    return history_block_coherence(shard=shard, body=body, rows=rows,
                                   last_day=last_day)


def _event_amendment_checks(reader, prepared):
    if not prepared['amendments']:
        return []
    original = reader.primary(prepared['filing'])
    original = {'raw': original['raw_bytes'], 'blob': original['raw_blob'],
                'reference': original['source_reference'], 'filing': prepared['filing']}
    checks = []
    for filing in prepared['amendments']:
        amended = reader.primary(filing)
        scope = inspect_annual_amendment_scope(original=original,
            amendment={'raw': amended['raw_bytes'], 'blob': amended['raw_blob'],
                       'reference': amended['source_reference'], 'filing': filing},
            company_id=prepared['company_id'], cik=prepared['entity'],
            note_layout='inline-paragraphs-v2')
        if not scope['fiscal_window_unchanged'] or 'FISCAL_EVENT_WINDOW' not in scope['unchanged_input_classes']:
            raise EventAmendmentError('HISTORICAL_EVENT_AMENDMENT_WINDOW_NOT_CLEARED')
        checks.append(scope)
    return checks


def prepare_historical_event_year_case(*, repo_root, company_id, metric_id, fiscal_year):
    if metric_id not in METRICS:
        raise NormalZeroAiError('HISTORICAL_EVENT_CONTENT_FAMILY_NOT_RECEIVED')
    source = Path(repo_root)
    selected = resolve_period_selection(repo_root=source, company_id=company_id,
                                        fiscal_year=fiscal_year, rules_root=ROOT)
    prepared = prepare_historical_annual_input(repo_root=source, company_id=company_id,
                                             period_selection=selected, rules_root=ROOT)
    period, registered_union = selected_event_window(prepared)
    documents = installed_ordinary_spec_documents(); spec = documents[metric_id]['compiled_spec']
    catalog = load_event_route_catalog(repo_root=ROOT)
    if catalog['routes'][metric_id]['keyword_item_rules'] or 'confirmation' in catalog['routes'][metric_id]:
        raise NormalZeroAiError('HISTORICAL_EVENT_CONTENT_ROUTE_NOT_RECEIVED')
    reader = _Sources(source, company_id, prepared['entity'])
    scope = {'coverage': 'fiscal_year_source_set', 'fiscal_year': fiscal_year,
             'shared_claim_group_id': catalog['routes'][metric_id]['shared_claim_group_id']}
    target = {'company_id': company_id, 'period_start': period['period_start'],
              'period_end': period['period_end'], 'scope': scope, 'scope_key': scope_key(scope=scope)}
    claims, source_sets, filings, observations, selection = [], [], [], [], None
    packet, amendment_checks = None, []
    try:
        # The event inventory and source sets prove this route's reporter.
        # Annual files are read here only when amendment impact requires them.
        amendment_checks = _event_amendment_checks(reader, prepared)
        packet = read_selected_event_sources(data_root=source, rules_root=ROOT,
            prepared=prepared, period=period, registered_union=registered_union,
            history_validator=check_historical_event_block, history_last_days=block_last_days)
        claims, source_sets, filings = packet['claims'], packet['source_set_manifests'], packet['filings']
        for record in packet['source_records']:
            key = (record['raw_asset_id'] if record['record_type'] == 'RAW_BLOB'
                   else record['source_reference_id'])
            existing = reader.records.get(key)
            if existing is not None and existing != record:
                if (record['record_type'] != 'RAW_BLOB' or
                        {k:v for k,v in existing.items() if k != 'storage_uri'} !=
                        {k:v for k,v in record.items() if k != 'storage_uri'}):
                    raise NormalZeroAiError('HISTORICAL_EVENT_SOURCE_RECORD_CONFLICT', 'SOURCE_INTEGRITY_ERROR')
                continue
            reader.records[key] = record
        reader.proofs.update({p['source_reference_id']:p for p in packet['source_bindings']})
        inventory_reference = packet['inventory_source_reference']
        graph = project_event_result(metric_id=metric_id, claims=claims,
            source_set_manifest=source_sets[-1], inventory_source_reference=inventory_reference,
            target_period=period, catalog=catalog)
        original = graph['observation']
        binding = {**original['source_binding'],
                   'source_role': inventory_reference['source_role'],
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
            BatchWorkflowError, SourceError, EventAmendmentError, AmendmentScopeError,
            SelectedEventSourceError, HistoryCatalogError) as error:
        result, trace = withheld_metric_result(compiled_spec=spec, target=target,
                                               reason_code='HISTORICAL_EVENT_SOURCE_UNRESOLVED')
        selection = {'reason_code': result['reason_code'], 'reason': str(error),
                     'category': ('AMENDMENT_INPUT_NOT_CLEARED' if isinstance(error, (EventAmendmentError, AmendmentScopeError))
                                  else getattr(error, 'category', 'SOURCE_INTEGRITY_ERROR'))}
    records = list(reader.records.values())
    proofs = list({content_hash(value=p): p for p in [*prepared['source_proofs'],
        *[entry['proof'] for entry in reader.proofs.values()]]}.values())
    admission = verify_ordinary_source_proofs(data_root=source, proofs=proofs)
    binding = {'record_type': 'HISTORICAL_EVENT_SOURCE_INPUT', 'prepared_input': prepared,
        'period_selection': selected, 'metric_id': metric_id, 'event_window': period,
        'source_set_manifests': source_sets, 'claims': claims, 'filings': filings, 'selection': selection,
        'source_proofs': proofs, 'source_admission': admission,
        'financial_cross_entity_combination_authorized': False,
        'registered_event_scope': None if packet is None else packet['registered_event_scope'],
        'amendment_checks': amendment_checks}
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
