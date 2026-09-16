"""Zero-call reuse of complete native receipts against current source content.

Original source/request/response bytes stay original. A separate current-source
proof may establish that only acquisition provenance changed. This is not a
semantic normalization API and cannot purchase a replacement execution.
"""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

from .canonical import content_hash, sha256_file, strict_json_file, strict_json_loads
from .capacity_utilization_source import need
from .normal_source_authority import ROOT

_META = {'semantic_source_id','original_source_packet_id','inherited_complete_source_id',
         'original_complete_source_id','source_proofs','source_admission','prepared_annual_input',
         'module_sha256','capacity_module_sha256'}


def _annual_content(value):
    value=deepcopy(value)
    value.pop('input_id',None);value.pop('source_proofs',None)
    if isinstance(value.get('original_input'),dict):
        value['original_input'].pop('input_id',None)
        value['original_input'].pop('source_proofs',None)
    return value


def source_equivalence(*,current,original):
    """Require complete identical substantive input, never changed source data."""
    from .continuous_semantic_calls import source_requests
    for source in (current,original):
        need(source['metric_id'] in {'B13','D04'} and source['source_serialization_complete'] is True
             and source['semantic_source_id']==content_hash(value={k:v for k,v in source.items() if k!='semantic_source_id'}),
             'UPDATE_NATIVE_COMPLETE_SOURCE_REQUIRED')
    need(set(current)==set(original) and current['record_type']==original['record_type']
         and 'HISTORICAL' not in current['record_type'], 'UPDATE_NATIVE_SOURCE_TYPE_CHANGED')
    need(all(current[k]==original[k] for k in current if k not in _META),
         'UPDATE_NATIVE_SUBSTANTIVE_SOURCE_CHANGED')
    need(_annual_content(current['prepared_annual_input'])==_annual_content(original['prepared_annual_input']),
         'UPDATE_NATIVE_ANNUAL_SELECTION_CHANGED')
    def bodies(source):
        return sorted((p['source_url'],p['accession'],p['document_name'],p['content_sha256']) for p in source['source_proofs'])
    need(bodies(current)==bodies(original),'UPDATE_NATIVE_SOURCE_BODY_SET_CHANGED')
    def requests(source):
        return [{k:v for k,v in r.items() if k not in {'source_id','request_id'}} for r in source_requests(source)]
    current_requests=requests(current)
    need(current_requests==requests(original),'UPDATE_NATIVE_SUBSTANTIVE_REQUEST_CHANGED')
    body={'record_type':'CURRENT_NATIVE_SOURCE_EQUIVALENCE','current_source_id':current['semantic_source_id'],
        'original_source_id':original['semantic_source_id'],'source_body_set_hash':content_hash(value=bodies(current)),
        'substantive_request_set_hash':content_hash(value=current_requests),
        'original_provider_bytes_rewritten':False,'new_provider_execution':False,'new_acquisition_credit':False}
    return {**body,'equivalence_id':content_hash(value=body)}


def _ledger(requirement,mode,provided):
    from .continuous_call_ledger import CallLedger,_FACTORY
    fixed=Path(requirement['policy']['budget_root'])
    if provided is not None:
        need(type(provided) is CallLedger and provided._factory is _FACTORY
             and provided.live==(mode=='LIVE') and (not provided.live or provided.root==fixed),
             'UPDATE_NATIVE_LEDGER_FACTORY_OR_MODE_CHANGED')
        return provided
    need(mode=='LIVE','UPDATE_RECORDED_NATIVE_LEDGER_REQUIRED')
    # Local read validation of an existing grant, never a new execution grant.
    from .continuous_call_policy import load_delegation
    approved=load_delegation(requirement=requirement,online=False)
    policy=requirement['policy']
    body={'record_type':'CONTINUOUS_CALL_ALLOWANCE','delegation_url':approved['html_url'],
        'delegation_body_sha256':policy['delegation_body_sha256'],'root':str(fixed),
        'limits':policy['maximum_additional_provider_paid_sec_calls'],
        'purposes':policy['scope']['purposes'],'execution_mode':'LIVE'}
    binding={**body,'binding_id':content_hash(value=body)}
    need((fixed/'binding.json').is_file() and strict_json_file(path=fixed/'binding.json')==binding,
         'UPDATE_NATIVE_EXISTING_LEDGER_REQUIRED')
    return CallLedger(factory=_FACTORY,root=fixed,binding=binding,live=True)


def prepare_registered_update(*,source_root,company_id,metric_id,options,ledger=None,allow_incomplete=False):
    """Re-register exact original successes under current runtime, with no calls."""
    from .continuous_call_policy import REQUIREMENT_ID
    from .requirements import load_requirement_snapshot
    requirement=load_requirement_snapshot(snapshot_dir=ROOT/'requirements'/REQUIREMENT_ID)
    from .native_request_construction import request_construction_session
    with request_construction_session(requirement):
        return _prepare_registered_update(source_root=source_root,company_id=company_id,metric_id=metric_id,
            options=options,ledger=ledger,allow_incomplete=allow_incomplete,requirement=requirement)


def _prepare_registered_update(*,source_root,company_id,metric_id,options,ledger,allow_incomplete,requirement):
    from .continuous_semantic_calls import (prepare_requests,source_requests,request_body,_json,
                                           configured_transport_policy,select_native_request_variants)
    from .capacity_native_assessment import collect_native_assessments
    from .capacity_assessment_input import register_assessment_input
    ledger=_ledger(requirement,options['assessment_mode'],ledger)
    current_prepared=prepare_requests(company_id=company_id,metric_id=metric_id,native=metric_id=='D04',
        reference_context=True,complete_response_contract=options['complete_response_contract'],
        source_root=source_root,source_ledger=ledger,program_quantity_roles=options.get('program_quantity_roles',False))
    template=current_prepared[0];current=strict_json_loads(text=template.source_bytes.decode())
    candidates={}
    with ledger.locked():
        snapshot=ledger.snapshot()
        for row in snapshot['rows']:
            if row['channel']!='PROVIDER' or row['status']!='SUCCEEDED':continue
            path=ledger.root/'calls'/('%04d'%row['ordinal'])
            if not (path/'source.json').is_file():continue
            original=strict_json_file(path=path/'source.json')
            if original.get('company_id')==company_id and original.get('metric_id')==metric_id:
                candidates.setdefault(original['semantic_source_id'],original)
    complete=[]
    for original in candidates.values():
        try:equivalence=source_equivalence(current=current,original=original)
        except ValueError:continue
        policy=configured_transport_policy(requirement=requirement,repo_root=ROOT)
        prepared=[replace(template,source_bytes=_json(original),request_bytes=_json(request),
            provider_request_body_bytes=request_body(request,policy),output_schema_bytes=_json(request['response_protocol']),
            replay_only=True,current_source_bytes=template.source_bytes,
            current_source_ledger_sha256=sha256_file(path=Path(source_root)/'evidence/requests_log.csv'))
            for request in source_requests(original)]
        selected,variants=select_native_request_variants(prepared_requests=prepared,ledger=ledger)
        assessment=collect_native_assessments(prepared_requests=selected,ledger=ledger)
        if assessment['all_source_requests_accepted'] and not assessment['failed_requests']:
            complete.append((selected,original,equivalence))
    if not complete and allow_incomplete:
        return {'status':'CURRENT_NATIVE_SET_INCOMPLETE','prepared_requests':current_prepared,
                'current_source':current,'requirement':requirement}
    need(len(complete)==1,'UPDATE_NATIVE_COMPLETE_ORIGINAL_SET_MISSING_OR_AMBIGUOUS')
    prepared,original,equivalence=complete[0]
    registered=register_assessment_input(prepared_requests=prepared,ledger=ledger,include_source_snapshot=True)
    need(registered['source_snapshot']==original,'UPDATE_NATIVE_ORIGINAL_SOURCE_SNAPSHOT_CHANGED')
    return {'source':original,'registered_input':registered,'current_source':current,
            'equivalence':equivalence,'requirement':requirement}


# Current B13 real content validation remains paused. This new entry point has
# no option to clear that pause; a reviewed implementation change is required.
_LIVE_UPDATE_METRICS = frozenset({'D04'})


def ensure_native_update(*,source_root,company_id,metric_id,ledger,max_provider_requests,
                         recorded_wire_factory=None):
    """Complete only previously unattempted native requests, with a finite cap.

    Reuses whole-source equivalents and exact-current successes. Reusing a
    semantic group across different source packets remains unsupported; do not
    buy a redraw or change its output contract to work around that limitation.
    """
    from .normal_run_v3 import current_registered_update_options
    from .continuous_semantic_calls import (select_native_request_variants,configured_transport_policy,
        request_digest,execute_capacity_assessment,execute_d04_assessment)
    from .native_unit_index import upgrade_request
    need(type(max_provider_requests) is int and 0<=max_provider_requests<=240,
         'UPDATE_NATIVE_FINITE_PROVIDER_LIMIT_REQUIRED')
    need(metric_id in {'B13','D04'},'UPDATE_NATIVE_METRIC_UNSUPPORTED')
    need(not ledger.live or recorded_wire_factory is None,'UPDATE_RECORDED_WIRE_CANNOT_RUN_LIVE')
    options=current_registered_update_options(metric_id,assessment_mode='LIVE' if ledger.live else 'RECORDED_TEST_ONLY')
    selected=prepare_registered_update(source_root=source_root,company_id=company_id,metric_id=metric_id,
        options=options,ledger=ledger,allow_incomplete=True)
    base={'company_id':company_id,'metric_id':metric_id,'executions':[],
          'attempted_executions':0,'counts':[0,0,0],'call_accounting':'KNOWN','stop_provider':False,
          'new_complete_metric_credit':False,'production_authorized':False}
    attributed_ordinals={}
    def attribute(ordinal,counts):
        if ordinal in attributed_ordinals:
            need(attributed_ordinals[ordinal]==counts,'UPDATE_NATIVE_ORDINAL_COUNTS_CHANGED')
            return
        attributed_ordinals[ordinal]=list(counts)
        base['counts']=[a+b for a,b in zip(base['counts'],counts)]
    if 'registered_input' in selected:
        return {**base,'status':'REGISTERED_INPUT_REUSED','input_record_id':selected['registered_input']['input_record_id']}
    originals=selected['prepared_requests']
    prepared,variants=select_native_request_variants(prepared_requests=originals,ledger=ledger)
    pending=[(p,b) for p,b,v in zip(prepared,originals,variants) if v['original_ordinal'] is None]
    if ledger.live and metric_id not in _LIVE_UPDATE_METRICS:
        return {**base,'status':'LIVE_NATIVE_EXECUTION_PAUSED','pending_request_count':len(pending)}
    with ledger.locked():snapshot=ledger.snapshot()
    policy=configured_transport_policy(requirement=originals[0].requirement,repo_root=ROOT)
    for _,original in pending:
        request=strict_json_loads(text=original.request_bytes.decode())
        # Check both versions before choosing indexed output. An old failed
        # BASE request is not an automatic license to try INDEXED next time.
        if any(('PROVIDER',request_digest(r,policy)) in snapshot['requests']
               for r in (request,upgrade_request(request))):
            return {**base,'status':'PRIOR_ATTEMPT_OR_CHANGED_SOURCE_GROUP_REUSE_UNSUPPORTED',
                    'pending_request_count':len(pending),'blocked_request_id':request['request_id']}
    if 'PROVIDER' in snapshot['stopped_channels']:
        return {**base,'status':'PROVIDER_CHANNEL_STOPPED','stop_provider':True,'pending_request_count':len(pending)}
    if not max_provider_requests:
        return {**base,'status':'PROVIDER_LIMIT_DEFERRED','pending_request_count':len(pending)}
    execute=execute_capacity_assessment if metric_id=='B13' else execute_d04_assessment
    for prepared,_ in pending[:max_provider_requests]:
        base['attempted_executions']+=1
        before=None
        try:
            with ledger.locked():before=ledger.snapshot()
            wire=None if ledger.live else (recorded_wire_factory(prepared) if recorded_wire_factory else None)
            path,outcome=execute(prepared=prepared,ledger=ledger,recorded_wire=wire)
            terminal=outcome['terminal']
            base['executions'].append({'call_path':str(path),'terminal':terminal})
            ordinal=int(path.name)
            need(path==ledger.root/'calls'/('%04d'%ordinal),'UPDATE_NATIVE_EXECUTION_PATH_CHANGED')
            attribute(ordinal,terminal['counts'])
            if terminal['status']!='SUCCEEDED' or terminal['stop_reason']:
                with ledger.locked():after=ledger.snapshot()
                return {**base,'status':'NATIVE_REQUEST_FAILED','stop_provider':'PROVIDER' in after['stopped_channels']}
        except Exception as error:
            # A raised executor may already own an immutable claim. Attribute
            # only this request's new ordinal; do not count concurrent work.
            try:
                with ledger.locked():after=ledger.snapshot()
                digest=request_digest(strict_json_loads(text=prepared.request_bytes.decode()),policy)
                observed=[]
                for row in after['rows'][len(before['rows']):]:
                    path=ledger.root/'calls'/('%04d'%row['ordinal'])
                    intent=strict_json_file(path=path/'intent.json')
                    if row['channel']=='PROVIDER' and intent['request_digest']==digest:observed.append(row)
                need(len(observed)<=1,'UPDATE_NATIVE_ATTEMPT_ATTRIBUTION_AMBIGUOUS')
                for row in observed:attribute(row['ordinal'],row['counts'])
                base['stop_provider']='PROVIDER' in after['stopped_channels']
            except Exception:
                base.update(call_accounting='UNKNOWN',stop_provider=True)
            return {**base,'status':'NATIVE_EXECUTION_ERROR','error_type':type(error).__name__,'reason':str(error)}
    if len(pending)>max_provider_requests:
        return {**base,'status':'PROVIDER_LIMIT_DEFERRED','pending_request_count':len(pending)-max_provider_requests}
    # Registration and the subsequent ordinary Run each retain their full
    # current checks. A content error is not converted to a disclosure limit.
    try:
        registered=prepare_registered_update(source_root=source_root,company_id=company_id,metric_id=metric_id,
            options=options,ledger=ledger)
    except Exception as error:
        return {**base,'status':'NATIVE_REGISTRATION_FAILED','error_type':type(error).__name__,'reason':str(error)}
    return {**base,'status':'NATIVE_INPUT_REGISTERED','input_record_id':registered['registered_input']['input_record_id']}
