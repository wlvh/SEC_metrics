"""Selected-year E01 source preparation with honest ordinary withheld output.

Existing item/source/summary functions are reused. This consumer does not call
models, read old registered answers, or turn a development answer into accepted
content. A request without its own validated semantic response remains null.
"""
from pathlib import Path
from sec_urls import submissions_url, submissions_file_url
from .calculator import calculate_observation_metric, withheld_metric_result
from .canonical import content_hash, sha256_bytes, strict_json_file
from .deterministic_router import load_event_route_catalog, project_event_result
from .historical_annual_input import prepare_historical_annual_input
from .historical_event_cases import (check_historical_event_block, _event_amendment_checks,
                                     PROCESSING_FILES as EVENT_PROCESSING_FILES)
from .historical_event_items import (content_confirmation_candidates, successor_event_route,
                                     EventItemTextError, HEADED_NOT_LISTED)
from .historical_event_attachments import attachment_dependencies, POLICY_PATH
from .historical_e01_incorporated_input import prepare_incorporated_e01_input
from .historical_ma_confirmation import (
    confirmation_request, validate_answer, confirmed_count, CONTRACT as ITEM_CONTRACT)
from .historical_e01_incorporated_input import (
    summarize_incorporated_answer, CONTRACT as INCORPORATED_CONTRACT)
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
# This consumer actually calls the delivered event walk and amendment checks.
# Reuse their finite dependency declaration so policy changes invalidate reuse.
PROCESSING_FILES = tuple(dict.fromkeys((*EVENT_PROCESSING_FILES, *PROCESSING_FILES)))


def _display_assessment(assessment):
    """Keep daily source pointers; complete checks remain in saved evidence."""
    return {**assessment, 'annual_amendment_checks': [
        {key:check[key] for key in ('scope_id','classification',
            'fiscal_window_unchanged','unchanged_input_classes','issues')} |
        {'original': {key:check['original'][key] for key in
            ('filing','period','raw_sha256','source_reference')},
         'amendment': {key:check['amendment'][key] for key in
            ('filing','period','raw_sha256','source_reference')}}
        for check in assessment['annual_amendment_checks']]}


def prepare_historical_e01_source_context(*, repo_root, company_id, fiscal_year,
                                          period_selection=None):
    """Prepare selected-year originals and a request without a metric result.

    The company source entry can consume these same dependencies. Completeness
    covers source preparation only, never an accepted semantic response/count.
    """
    source = Path(repo_root)
    selection = (resolve_period_selection(repo_root=source,company_id=company_id,
        fiscal_year=fiscal_year,rules_root=ROOT) if period_selection is None else period_selection)
    annual = prepare_historical_annual_input(repo_root=source,company_id=company_id,
        period_selection=selection,rules_root=ROOT)
    period = annual['table_input']['target_period']
    if type(fiscal_year) is not int or period['fiscal_year'] != fiscal_year:
        raise ValueError('HISTORICAL_E01_REQUESTED_FISCAL_YEAR_CHANGED')
    frozen = load_event_route_catalog(repo_root=ROOT)['routes']['E01']
    route = successor_event_route(repo_root=ROOT,metric_id='E01',frozen_route=frozen)
    scope = {'coverage':'fiscal_year_source_set','fiscal_year':fiscal_year,
             'shared_claim_group_id':route['shared_claim_group_id']}
    target = {'company_id':company_id,'period_start':period['period_start'],
        'period_end':period['period_end'],'scope':scope,'scope_key':scope_key(scope=scope)}
    reader = _Sources(source,company_id,annual['entity'])
    reader.primary(annual['filing'])  # Bind the actual annual reporter in ordinary output.
    packet, request, incorporated, dependencies, candidates = None,None,None,[],[]
    item_source_conflict = None
    amendment_checks = []
    reason = 'E01_CONTENT_RESPONSE_NOT_AVAILABLE_FOR_REQUEST'
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
        try:
            confirmation = content_confirmation_candidates(repo_root=source,route=route,
                claims=packet['claims'],records=records,keep_text=True)
        except EventItemTextError as error:
            # The complete saved walk has found an actual header/body
            # disagreement. Preserve that completed rejection for ordinary
            # save/reuse/read; do not choose an item number or report zero.
            # Other source, parser and missing-document failures still raise.
            if not str(error).startswith(HEADED_NOT_LISTED + ':'):
                raise
            item_source_conflict = {'reason':str(error),'category':error.category,
                                    'status':'SOURCE_CONTENT_CONFLICT'}
            reason = 'E01_ITEM_METADATA_BODY_CONFLICT'
        else:
            candidates = confirmation['candidates']
        if item_source_conflict is not None:
            pass
        elif candidates:
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
        'reason_code':reason,'complete_annual_count':None,
        'candidate_item_ids':[] if request is None else [x['item_id'] for x in request['items']],
        'request_id':None if current_request is None else current_request['request_id'],
        'request_contract':None if current_request is None else current_request['contract'],
        'annual_amendment_checks':amendment_checks,
        'attachment_dependencies':dependencies,'matching_response_available':False,
        'old_answer_reused':False,'partial_count_exported':False,
        'target_model_execution_authorized':False,'new_calls':[0,0,0]}
    if item_source_conflict is not None:
        assessment['item_source_conflict'] = item_source_conflict
    complete = (packet is not None and item_source_conflict is None
                and reason != 'E01_REQUIRED_INCORPORATED_SOURCE_UNAVAILABLE')
    return {'record_type':'HISTORICAL_E01_SOURCE_CONTEXT_V1',
        'company_id':company_id,'fiscal_year':fiscal_year,'target_period':period,
        'prepared_annual_input':annual,'period_selection':selection,
        'event_packet':packet,'source_records':list(indexed.values()),
        'source_proofs':proofs,'admission':admission,
        'request':current_request,
        'predecessor_request_id':None if request is None else request['request_id'],
        'assessment':assessment,'event_route':route,'target':target,
        'source_graph_known':complete,'source_status':'READY' if complete else 'BLOCKED',
        'metric_executed':False,'metric_result_created':False,'new_calls':[0,0,0]}


def prepare_historical_e01_year_case(*, repo_root, company_id, metric_id, fiscal_year):
    if metric_id != 'E01':
        raise ValueError('HISTORICAL_E01_FAMILY_NOT_RECEIVED')
    context = prepare_historical_e01_source_context(repo_root=repo_root,
        company_id=company_id,fiscal_year=fiscal_year)
    return finish_historical_e01_case(context=context)


def historical_e01_response_factory(*, response_reader):
    """Adapt the public saved-response reader to the existing year factory.

    response_reader(request=...) returns a verified original response read;
    it never acquires a source or makes a model call. The public controller
    receives its files separately as ordinary processing inputs.
    """
    if not callable(response_reader):
        raise ValueError('E01_SAVED_RESPONSE_READER_REQUIRED')

    def prepare(*, repo_root, company_id, metric_id, fiscal_year):
        if metric_id != 'E01':
            raise ValueError('HISTORICAL_E01_FAMILY_NOT_RECEIVED')
        context = prepare_historical_e01_source_context(repo_root=repo_root,
            company_id=company_id, fiscal_year=fiscal_year)
        reply = None
        if (context['source_graph_known'] and context['request'] is not None
                and context['assessment']['reason_code'] == 'E01_CONTENT_RESPONSE_NOT_AVAILABLE_FOR_REQUEST'):
            reply = response_reader(request=context['request'])
        return finish_historical_e01_case(context=context, reviewed_response=reply)

    return prepare


def finish_historical_e01_case(*, context, reviewed_response=None):
    """Finish one selected fiscal window from an exact saved-response read.

    The public reader owns HTTP/terminal/request-file verification. This
    consumer owns the existing item contract, complete-window rule and numeric
    derivation. A valid response shape does not establish semantic correctness.
    No provider, ledger, source acquisition or result writing occurs here.
    """
    company_id = context['company_id']
    period = context['target_period']
    annual = context['prepared_annual_input']
    selection = context['period_selection']
    packet, route, target = context['event_packet'], context['event_route'], context['target']
    reason = context['assessment']['reason_code']
    spec = compile_spec_file(path=ROOT/SPEC_PATH,dependency_specs={})
    observations = []
    response_summary = None
    if (reviewed_response is not None and context['source_graph_known']
            and reason == 'E01_CONTENT_RESPONSE_NOT_AVAILABLE_FOR_REQUEST'):
        request = context['request']
        if (request['request_id'] != content_hash(value={
                k:v for k,v in request.items() if k != 'request_id'})
                or request['company_id'] != company_id
                or str(request['target_cik']) != str(annual['entity'])
                or request['window'] != {k:period[k] for k in ('period_start', 'period_end')}):
            raise ValueError('E01_SAVED_CURRENT_SOURCE_REQUEST_CHANGED')
        if (reviewed_response.get('request_id') != request['request_id']
                or reviewed_response.get('request') != request):
            raise ValueError('E01_SAVED_RESPONSE_REQUEST_CHANGED')
        if reviewed_response.get('original_execution_mode') != 'LIVE':
            raise ValueError('E01_SAVED_LIVE_RESPONSE_REQUIRED')
        usage = reviewed_response.get('usage') or {}
        if (reviewed_response.get('usage_known') is not True
                or any(type(usage.get(k)) is not int or usage[k] < 0
                       for k in ('input_tokens', 'output_tokens'))):
            raise ValueError('E01_SAVED_RESPONSE_USAGE_UNKNOWN')
        raw = reviewed_response['raw_output']
        if type(raw) is not bytes:
            raise ValueError('E01_SAVED_RESPONSE_OUTPUT_BYTES_REQUIRED')
        if request['contract'] == ITEM_CONTRACT:
            decisions = validate_answer(request=request, raw_output=raw)
            count, unresolved_reason, item_ids = confirmed_count(request=request, decisions=decisions)
            response_summary = {'request_id': request['request_id'], 'decisions': decisions,
                'proposed_count': count, 'reason': unresolved_reason,
                'unresolved_item_ids': item_ids if unresolved_reason else [],
                'confirmed_item_ids': [] if unresolved_reason else item_ids}
        elif request['contract'] == INCORPORATED_CONTRACT:
            response_summary = summarize_incorporated_answer(request=request, raw_output=raw)
            # This is still a development contract. Reading its answer does
            # not promote a successor input into the adopted item-only rule.
            response_summary = {**response_summary,
                'reason': response_summary['reason'] or 'E01_INCORPORATED_DEVELOPMENT_RESULT_NOT_ADOPTED'}
        else:
            raise ValueError('E01_SAVED_RESPONSE_CONTRACT_NOT_SUPPORTED')
        response_summary = {**response_summary,
            'raw_output_sha256': sha256_bytes(content=raw), 'usage': dict(usage),
            'original_execution_id': reviewed_response['original_execution_id'],
            'original_terminal_id': reviewed_response['original_terminal_id'],
            'semantic_correctness_verified': False, 'new_calls': [0, 0, 0]}
        reason = response_summary['reason'] or 'PASS'
    if reason == 'PASS' and response_summary is not None:
        reference = packet['inventory_source_reference']
        source_binding = {'source_reference_id': reference['source_reference_id'],
            'accession': reference['accession'], 'document_name': reference['document_name'],
            'raw_asset_id': reference['raw_asset_id'], 'source_role': reference['source_role'],
            'source_set_role': packet['source_set_manifests'][-1]['source_role'],
            'derivation': 'MODEL_ITEM_DECISIONS_DERIVED_COUNT',
            'request_id': response_summary['request_id'],
            'response_sha256': response_summary['raw_output_sha256'],
            'original_execution_id': response_summary['original_execution_id'],
            'original_terminal_id': response_summary['original_terminal_id'],
            'confirmed_item_ids': response_summary['confirmed_item_ids'],
            'item_decisions': response_summary['decisions'],
            'complete_candidate_count': len(context['request']['items']),
            'semantic_correctness_verified': False}
        observation = structured_observation(metric_id='E01', semantic_role='event_count',
            company_id=company_id, period_start=period['period_start'], period_end=period['period_end'],
            scope=target['scope'], value=str(response_summary['proposed_count']), unit='count',
            quality='EXACT', source_binding=source_binding)
        result, trace = calculate_observation_metric(compiled_spec=spec, target=target,
            company_traits=repository_company_traits(repo_root=ROOT, company_id=company_id),
            observation=observation)
        observations = [observation]
    elif reason == 'PASS':
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
    source_records = context['source_records']
    proofs, admission = context['source_proofs'], context['admission']
    current_request = context['request']
    assessment = {**context['assessment'], 'reason_code': reason,
        'complete_annual_count': (str(response_summary['proposed_count'])
            if reason == 'PASS' and response_summary is not None else '0' if reason == 'PASS' else None)}
    if response_summary is not None:
        assessment.update(matching_response_available=True, partial_count_exported=False,
            semantic_correctness_verified=False, saved_response=response_summary)
    display_assessment = _display_assessment(assessment)
    binding={'record_type':'HISTORICAL_E01_COMPANY_SOURCE_INPUT','prepared_input':annual,
        'period_selection':selection,'source_proofs':proofs,'request':current_request,
        'predecessor_request_id':context['predecessor_request_id'],
        'filings':[] if packet is None else packet['filings'],'assessment':assessment}
    return {'kind':'STRUCTURED','primary_metric_id':'E01','compiled_specs':{'E01':spec},
        'spec_paths':{'E01':SPEC_PATH},'target_period':period,'prepared_annual_input':annual,
        'input_binding':binding,'expected_records':[*source_records,
            *([] if packet is None else packet['claims']), *observations,trace,result],
        'results':{'E01':result},'traces':{'E01':trace},'observations':observations,
        'references':[r for r in source_records if r['record_type']=='SOURCE_REFERENCE'],
        'source_proofs':proofs,'admission':admission,'rules_root':str(ROOT),
        'input_assessments':{'e01_content':assessment,'e01_request':current_request},
        'selection':{'e01_content':display_assessment}}


def collect_historical_e01_requirements(plan, *, prepared, period_selection=None):
    """Attach the existing selected E01 sources to the shared read-only plan.

    ``prepared`` is the body returned by ``prepare_historical_annual_input``:
    company_id/entity/filing/subject_policy/table_input, not a latest-current
    wrapper. Its identity is checked against the source-derived context.
    Missing original-source exceptions retain their original URL and category
    for the public planner; they never become an empty event collection.
    """
    period = prepared['table_input']['target_period']
    company_id = plan.company['company_id']
    if prepared['company_id'] != company_id:
        raise ValueError('HISTORICAL_E01_SOURCE_PLAN_COMPANY_CHANGED')
    context = prepare_historical_e01_source_context(repo_root=plan.root,
        company_id=company_id, fiscal_year=period['fiscal_year'],
        period_selection=period_selection)
    actual = context['prepared_annual_input']
    if (actual['entity'] != prepared['entity'] or actual['filing'] != prepared['filing']
            or context['target_period'] != period
            or actual['subject_policy'] != prepared['subject_policy']):
        raise ValueError('HISTORICAL_E01_SOURCE_PLAN_SELECTION_CHANGED')

    records = context['source_records']
    blobs = {r['raw_asset_id']:r for r in records if r['record_type']=='RAW_BLOB'}
    references = {r['source_url']:r for r in records if r['record_type']=='SOURCE_REFERENCE'}
    annual_json = {}
    facts_url = actual.get('companyfacts_input',{}).get('source_url')
    if facts_url:
        annual_json[facts_url] = 'application/json'
    selected = context['period_selection']
    catalogs = [(actual['entity'],selected.get('loaded_inventories',[]))]
    registrant = selected.get('period_registrant')
    if registrant:
        catalogs.append((plan.company['primary_cik'],
                         registrant['primary_catalog']['loaded_inventories']))
    for cik,names in catalogs:
        if names:
            annual_json[submissions_url(cik=int(cik))] = 'application/json'
            annual_json.update((submissions_file_url(file_name=name),'application/json')
                               for name in names[1:])
    urls = []
    for item in context['source_proofs']:
        proof = item.get('proof', item)
        url = proof['source_url']
        reference = references.get(url)
        # Annual preparation also binds companyfacts/submissions JSON. Other
        # proofs are the selected original or recorded event sources above.
        media = blobs[reference['raw_asset_id']]['media_type'] if reference else annual_json.get(url)
        if media is None:
            raise ValueError('HISTORICAL_E01_SOURCE_MEDIA_TYPE_UNDECLARED:'+url)
        role = reference['source_role'] if reference else 'historical_e01_annual_dependency'
        plan.require(url, role=role, media_type=media, accession=proof['accession'])
        if url not in urls:
            urls.append(url)
    for dependency in context['assessment']['attachment_dependencies']:
        url = dependency['source_url']
        plan.require(url, role='incorporated_EX99', media_type=dependency['media_type'],
                     accession=dependency['accession'])
        if url not in urls:
            urls.append(url)
    errors = [{'phase':'E01_SAVED_SOURCE_RECHECK',
        'source_url':url,'reason':plan.requests[url].get('reason',plan.requests[url]['saved_status']),
        'category':'SOURCE_UNAVAILABLE'} for url in urls
        if plan.requests[url]['saved_status']!='VERIFIED_SAVED_SOURCE']
    if not context['source_graph_known']:
        errors.append({'phase':'E01_SELECTED_SOURCE_SCOPE',
            'reason':context['assessment']['reason_code'],
            'category':'SOURCE_SCOPE_NOT_COMPLETE'})
    complete = context['source_graph_known'] and not errors
    return {'metric_id':'E01','requirements':[plan.requests[url] for url in urls],
        'errors':errors,'source_graph_known':complete,'event_window':period,
        'request_id':context['assessment']['request_id'],
        'request_contract':context['assessment']['request_contract'],
        'matching_response_available':False,'complete_annual_count':None,
        'metric_executed':False,'new_calls':[0,0,0]}
