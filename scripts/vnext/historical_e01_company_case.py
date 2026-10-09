"""Selected-year E01 source preparation with honest ordinary withheld output.

Existing item/source/summary functions are reused. This consumer does not call
models, read old registered answers, or turn a development answer into accepted
content. A request without its own validated semantic response remains null.
"""
from pathlib import Path
from .calculator import calculate_observation_metric, withheld_metric_result
from .canonical import content_hash, strict_json_file
from .deterministic_router import load_event_route_catalog, project_event_result
from .historical_annual_input import prepare_historical_annual_input
from .historical_event_cases import check_historical_event_block, _event_amendment_checks
from .historical_event_items import content_confirmation_candidates, successor_event_route
from .historical_event_attachments import attachment_dependencies, POLICY_PATH
from .historical_e01_incorporated_input import prepare_incorporated_e01_input
from .historical_ma_confirmation import confirmation_request
from .normal_governance_input import _Sources
from .normal_history_catalog import block_last_days
from .normal_period_selection import resolve_period_selection
from .normal_source_authority import ROOT
from .observations import scope_key, structured_observation
from .ordinary_source_authority import verify_ordinary_source_proofs
from .selected_event_source_v1 import read_selected_event_sources
from .specs import compile_spec_file
from .traits import repository_company_traits

METRICS = frozenset({'E01'})
SPEC_PATH = 'catalog/r6/E01_content_confirmed_ma_v1.md'
PROCESSING_FILES = tuple('scripts/vnext/'+name+'.py' for name in (
    'historical_e01_company_case','historical_e01_incorporated_input','historical_event_attachments',
    'historical_event_items','historical_ma_confirmation','historical_annual_input','historical_dei',
    'historical_fiscal_labels','normal_period_selection','normal_history_catalog','normal_annual_input',
    'normal_governance_input','selected_event_source_v1','historical_event_cases','annual_sources',
    'deterministic_router','composite_scope','specs')) + (
    SPEC_PATH,'catalog/r6/E01_content_confirmed_ma_v1.json','catalog/event_routes.json',POLICY_PATH,
    'config/normal_period_selection_v1.json','config/normal_fiscal_year_labels_v1.json')


def prepare_historical_e01_year_case(*, repo_root, company_id, metric_id, fiscal_year):
    if metric_id != 'E01':
        raise ValueError('HISTORICAL_E01_FAMILY_NOT_RECEIVED')
    source = Path(repo_root)
    selection = resolve_period_selection(repo_root=source,company_id=company_id,
        fiscal_year=fiscal_year,rules_root=ROOT)
    annual = prepare_historical_annual_input(repo_root=source,company_id=company_id,
        period_selection=selection,rules_root=ROOT)
    period = annual['table_input']['target_period']
    spec = compile_spec_file(path=ROOT/SPEC_PATH,dependency_specs={})
    frozen = load_event_route_catalog(repo_root=ROOT)['routes']['E01']
    route = successor_event_route(repo_root=ROOT,metric_id='E01',frozen_route=frozen)
    scope = {'coverage':'fiscal_year_source_set','fiscal_year':fiscal_year,
             'shared_claim_group_id':route['shared_claim_group_id']}
    target = {'company_id':company_id,'period_start':period['period_start'],
        'period_end':period['period_end'],'scope':scope,'scope_key':scope_key(scope=scope)}
    reader = _Sources(source,company_id,annual['entity'])
    reader.primary(annual['filing'])  # Bind the actual annual reporter in ordinary output.
    packet, request, incorporated, dependencies, candidates = None,None,None,[],[]
    amendment_checks = []
    reason = 'E01_CONTENT_RESPONSE_NOT_AVAILABLE_FOR_REQUEST'
    observations = []
    if annual['subject_policy']['mode'] != 'CONTINUOUS_PRIMARY':
        reason = 'E01_SUCCESSOR_EVENT_WINDOW_NOT_RECEIVED'
    else:
        # Reuse the already delivered source-impact checks. A compensation-only
        # amendment is not a reason to discard the fiscal event inputs.
        amendment_checks = _event_amendment_checks(reader, annual)
        packet = read_selected_event_sources(data_root=source,rules_root=ROOT,
            prepared=annual,period=period,registered_union=False,
            history_validator=check_historical_event_block,history_last_days=block_last_days)
        records = {r.get('raw_asset_id') if r['record_type']=='RAW_BLOB' else r['source_reference_id']:r
                   for r in packet['source_records']}
        confirmation = content_confirmation_candidates(repo_root=source,route=route,
            claims=packet['claims'],records=records,keep_text=True)
        candidates = confirmation['candidates']
        if candidates:
            request = confirmation_request(route=route,company_id=company_id,
                target_cik=annual['entity'],window=period,candidates=candidates)
            policy = strict_json_file(path=ROOT/POLICY_PATH)
            declared = [d for d in policy['items'] if d['company_id']==company_id
                        and d['report_end']==period['period_end']]
            if declared:
                requirements = [{'source_url':d['parent_url'],'accession':d['accession'],
                    'dependency_class':'FISCAL_EVENT_FILING','primary_cik':annual['entity'],
                    'registrant_cik':d['parent_url'].split('/data/',1)[1].split('/',1)[0]} for d in declared]
                dependencies = attachment_dependencies(repo_root=source,company_id=company_id,
                    requirements=requirements,report_ends=[period['period_end']])
                if any(d['saved_status']!='VERIFIED_SAVED_SOURCE' for d in dependencies):
                    reason = 'E01_REQUIRED_INCORPORATED_SOURCE_UNAVAILABLE'
                else:
                    predecessor_proofs = list({content_hash(value=p):p for p in
                        [*annual['source_proofs'], *[x['proof'] for x in reader.proofs.values()],
                         *packet['source_proofs']]}.values())
                    incorporated = prepare_incorporated_e01_input(data_root=source,
                        predecessor_source={'company_id':company_id,'request':request,
                                            'source_proofs':predecessor_proofs})
        else:
            # Zero is justified only after the complete source/item walk has
            # found no candidate, using the existing event Calculator route.
            reason = 'PASS'
    if reason == 'PASS':
        sets = packet['source_set_manifests']
        catalog = {'routes': {'E01': route}}
        graph = project_event_result(metric_id='E01',claims=packet['claims'],
            source_set_manifest=sets[-1],inventory_source_reference=packet['inventory_source_reference'],
            target_period=period,catalog=catalog)
        original = graph['observation']
        binding = {**original['source_binding'],
            'source_role':packet['inventory_source_reference']['source_role'],
            'source_set_role':sets[-1]['source_role']}
        observation = structured_observation(metric_id='E01',semantic_role=original['semantic_role'],
            company_id=company_id,period_start=period['period_start'],period_end=period['period_end'],
            scope=original['scope'],value=original['value'],unit=original['unit'],
            quality=original['quality'],source_binding=binding)
        result,trace = calculate_observation_metric(compiled_spec=spec,target=target,
            company_traits=repository_company_traits(repo_root=ROOT,company_id=company_id),observation=observation)
        observations = [observation]
    else:
        result,trace = withheld_metric_result(compiled_spec=spec,target=target,reason_code=reason)
    source_records = list(reader.records.values()) + ([] if packet is None else packet['source_records'])
    source_records += [] if incorporated is None else incorporated['added_source_records']
    indexed = {}
    for record in source_records:
        key = record.get('raw_asset_id') if record['record_type']=='RAW_BLOB' else record['source_reference_id']
        previous=indexed.get(key)
        if previous is not None and previous!=record:
            if record['record_type']!='RAW_BLOB' or {k:v for k,v in previous.items() if k!='storage_uri'}!={k:v for k,v in record.items() if k!='storage_uri'}:
                raise ValueError('E01_SOURCE_RECORD_IDENTITY_CONFLICT')
            continue
        indexed[key]=record
    proofs = list(annual['source_proofs'])+[x['proof'] for x in reader.proofs.values()]
    proofs += [] if packet is None else packet['source_proofs']
    proofs += [] if incorporated is None else incorporated['source_proofs']
    proofs = list({content_hash(value=p):p for p in proofs}.values())
    admission = verify_ordinary_source_proofs(data_root=source,proofs=proofs)
    current_request = incorporated if incorporated is not None else request
    assessment = {'status':'NO_CANDIDATE_ITEM' if reason=='PASS' else 'WITHHELD',
        'reason_code':reason,'complete_annual_count':'0' if reason=='PASS' else None,
        'candidate_item_ids':[] if request is None else [x['item_id'] for x in request['items']],
        'request_id':None if current_request is None else current_request['request_id'],
        'request_contract':None if current_request is None else current_request['contract'],
        'annual_amendment_checks':amendment_checks,
        'attachment_dependencies':dependencies,'matching_response_available':False,
        'old_answer_reused':False,'partial_count_exported':False,
        'target_model_execution_authorized':False,'new_calls':[0,0,0]}
    binding={'record_type':'HISTORICAL_E01_COMPANY_SOURCE_INPUT','prepared_input':annual,
        'period_selection':selection,'source_proofs':proofs,'request':current_request,
        'predecessor_request_id':None if request is None else request['request_id'],
        'filings':[] if packet is None else packet['filings'],'assessment':assessment}
    return {'kind':'STRUCTURED','primary_metric_id':'E01','compiled_specs':{'E01':spec},
        'spec_paths':{'E01':SPEC_PATH},'target_period':period,'prepared_annual_input':annual,
        'input_binding':binding,'expected_records':[*indexed.values(),
            *([] if packet is None else packet['claims']), *observations,trace,result],
        'results':{'E01':result},'traces':{'E01':trace},
        'references':[r for r in indexed.values() if r['record_type']=='SOURCE_REFERENCE'],
        'source_proofs':proofs,'admission':admission,'rules_root':str(ROOT),
        'input_assessments':{'e01_content':assessment,'e01_request':current_request},
        'selection':{'e01_content':assessment}}
