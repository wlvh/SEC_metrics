"""Bound D03/D04 feasibility requests through the existing provider opener/WB-3.

Saved source authenticity is replayed, never relabelled as new acquisition.
These executions retain original wire and a terminal but deliberately confer
no native Evidence, qualification, publication or semantic acceptance credit.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import json
import io
import tarfile
import uuid

from .canonical import canonical_json_bytes, content_hash, sha256_bytes, strict_json_loads, strict_json_file, sha256_file
from .continuous_call_policy import REQUIREMENT_ID, configured_transport_policy, load_delegation, need
from .normal_source_authority import ROOT, verify_saved_source_proofs
from .provider_runtime import load_provider_runtime_authority
from .requirements import load_requirement_snapshot
from . import invocation_control as control

_FACTORY = object()
_FEASIBILITY = 'FEASIBILITY_ONLY_NO_NATIVE_EVIDENCE'
REVIEW_POLICY_PATH = 'catalog/r6/semantic_review_v3.json'
SEMANTIC_RULE_PATHS = (
    'scripts/vnext/r6_semantic_source.py','scripts/vnext/r6_semantic_review.py',
    'scripts/vnext/going_concern_source.py','scripts/vnext/regulatory_investigation_candidates.py',
    'scripts/vnext/r6_regulatory_semantics.py','catalog/r6/semantic_source_v1.json',
    'catalog/r6/semantic_review_v1.json','catalog/r6/semantic_review_v2.json',REVIEW_POLICY_PATH,
    'scripts/vnext/r6_semantic_scope.py',
    'catalog/r6/going_concern_source_rules_v1.json',
    'catalog/r6/regulatory_investigation_candidates_v1.json',
    'catalog/r6/regulatory_semantic_review_v1.json','catalog/r6/regulatory_semantic_review_v2.json',
    'catalog/r6/regulatory_semantic_review_v3.json','catalog/r6/regulatory_semantic_review_v4.json',
    'catalog/r6/regulatory_semantic_review_v5.json',
    'catalog/r6/regulatory_semantic_review_v6.json',
    'scripts/vnext/r6_semantic_verification.py',
    'catalog/r6/regulatory_semantic_verification_v1.json','catalog/r6/regulatory_semantic_verification_v2.json',
    'scripts/vnext/r6_historical_controls.py','config/r6_historical_control_sources_v1.json',
    'scripts/vnext/regulatory_statement_facts.py',
    'scripts/vnext/capacity_semantic_source.py', 'scripts/vnext/capacity_semantic_review.py',
    'catalog/r5/capacity_semantic_review_v1.json', 'catalog/r5/capacity_semantic_review_v2.json',
    'catalog/r5/capacity_semantic_review_v3.json',
    'catalog/r5/capacity_semantic_review_v4.json',
    'catalog/r5/capacity_semantic_review_v5.json',
    'scripts/vnext/d04_native_assessment.py', 'catalog/r6/semantic_review_v4.json',
    'catalog/r6/D04_going_concern_assessment_v1.md',
    'scripts/vnext/capacity_native_assessment.py',
    'scripts/vnext/continuous_request_context.py',
    'config/tokenizers/deepseek_v41/tokenizer.json.gz',
    'requirements-continuous-context.txt')


def validate_semantic_rule_bindings(requirement):
    """Imported source/interpretation modules belong to the call's version."""
    for relative in SEMANTIC_RULE_PATHS:
        raw=(ROOT/relative).read_bytes()
        need(requirement['execution_authority']['files'].get(relative)==
             {'sha256':sha256_bytes(content=raw),'size':len(raw)},
             'CONTINUOUS_SEMANTIC_RULE_NOT_BOUND:'+relative)


def now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')


def _json(value):
    return canonical_json_bytes(value=value)


def request_body(request, policy):
    payload = {k:v for k,v in request.items() if k not in
        {'system_prompt','provider_request_sent','provider_tokens_measured','production_authorized'}}
    return _json({'model':policy.model,'messages':[
        {'role':'system','content':request['system_prompt']},
        {'role':'user','content':json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':'))}],
        'response_format':{'type':'json_object'},'temperature':0,'max_tokens':4096,
        'stream':False,'thinking':{'type':'disabled'}})


def request_digest(request, policy):
    """New code/provenance IDs alone do not authorize another extraction."""
    body = {'model':policy.model,'system_prompt':request['system_prompt'],
        'target_cik':request['target_cik'],'target_period':request['target_period'],
        'fiscal_label_context':request['fiscal_label_context'],
        'filing':request['document_context']['filing'],
        'units':[{'kind':u['kind'],'payload':u['payload']} for u in request['units']],
        'response_protocol':request['response_protocol'],
        'category_definitions':request['category_definitions'],
        'required_candidate_assessments':request['required_candidate_assessments'],
        # Semantic input IDs do not grant a redraw. Actual decoding settings
        # belong to the request, including the repaired thinking-mode setting.
        'provider_parameters':{k:v for k,v in strict_json_loads(
            text=request_body(request,policy).decode()).items() if k not in {'messages'}}}
    if request['record_type']=='D03_SEMANTIC_VERIFICATION_REQUEST':
        body['verification']={'proposals':request['proposals'],
            'prior_assistant_output_sha256':request['prior_assistant_output_sha256']}
    if request.get('source_statement_facts'):
        body['source_statement_facts'] = request['source_statement_facts']
    if 'shared_source_dictionaries' in request:
        body['shared_source_dictionaries'] = request['shared_source_dictionaries']
    if request.get('metric_id') == 'B13':
        body['native_capacity_role_assessments'] = request['native_capacity_role_assessments']
    return sha256_bytes(content=_json(body))


def source_requests(source):
    """Keep every existing source unit, with one unit per smaller request."""
    if source['record_type']=='D03_PROVIDER_PROPOSAL_VERIFICATION_SOURCE':
        from .r6_semantic_verification import requests_from_source
        return requests_from_source(source)
    if source['record_type'] in {'D04_NATIVE_COMPLETE_SEMANTIC_SOURCE', 'D04_NATIVE_HISTORICAL_CONTROL_SOURCE'}:
        from .d04_native_assessment import requests_from_source
        return requests_from_source(source)
    if source['metric_id'] == 'B13':
        from .capacity_semantic_review import requests_from_source
        return requests_from_source(source)
    if source['metric_id']=='D03':
        from .r6_regulatory_semantics import requests_from_source
        return requests_from_source(source)
    need(source['metric_id']=='D04','CONTINUOUS_SEMANTIC_METRIC_REQUIRED')
    from .r6_semantic_review import requests_from_source
    from .r6_semantic_review import POLICY as reference_policy, _source_items
    review_policy = strict_json_file(path=ROOT/REVIEW_POLICY_PATH)
    # Reuse the original exact-reference validator with unchanged categories
    # and bounds. Only the model's instructions and explicit per-unit todo grow.
    for key in ('kinds','subjects','timings','current_target_kinds','max_response_bytes',
                'max_findings_per_unit','max_reason_characters','max_quote_characters'):
        need(review_policy[key] == reference_policy[key], 'CONTINUOUS_RESPONSE_PROTOCOL_CHANGED')
    original = requests_from_source(source); requests = []
    for group in original:
        for unit in group['units']:
            body = {k:v for k,v in group.items() if k != 'request_id'}
            body['units'] = [unit]
            body['system_prompt'] = review_policy['system_prompt']
            body['policy_sha256'] = sha256_file(path=ROOT/REVIEW_POLICY_PATH)
            body['category_definitions'] = review_policy['category_definitions']
            kind,items = _source_items(unit)
            context = body['document_context']
            required = (context['language_candidate_block_indices'] if kind=='VISIBLE_BLOCK' else
                        context['native_candidate_ordinals'] if kind=='NATIVE_FACT' else [])
            body['required_candidate_assessments'] = [
                {'unit_id':unit['unit_id'],'kind':kind,'source_index':index}
                for index in required if index in items]
            if source['record_type']=='D04_HISTORICAL_PRIMARY_CONTROL_SOURCE':
                body['historical_control']=source['control']
                body['control_source_scope']=source['control_scope']
                body['system_prompt'] += (' This is a real historical filing control. Interpret CURRENT_REPORT relative '
                    'to this supplied original report, not the present day. Its scope is the complete selected primary HTML, '
                    'with SEC header identity; companion XBRL is not supplied. Do not infer whole-filing absence, current '
                    'company status, or production acceptance from this control.')
            requests.append({**body,'request_id':content_hash(value=body)})
    need([u['unit_id'] for r in requests for u in r['units']] == source['required_unit_ids'],
         'CONTINUOUS_SOURCE_UNIT_COVERAGE_CHANGED')
    return requests


@dataclass(frozen=True)
class SemanticRequest:
    _factory: object
    source_bytes: bytes
    request_bytes: bytes
    provider_request_body_bytes: bytes
    output_schema_bytes: bytes
    requirement: object
    authority: object
    data_root: Path = ROOT

    def validate(self, policy):
        need(self._factory is _FACTORY, 'CONTINUOUS_SOURCE_FACTORY_REQUIRED')
        self.authority._check()
        source = strict_json_loads(text=self.source_bytes.decode())
        request = strict_json_loads(text=self.request_bytes.decode())
        need(source['semantic_source_id'] == content_hash(value={k:v for k,v in source.items() if k!='semantic_source_id'}),
             'CONTINUOUS_SOURCE_CHANGED')
        allowed_control_root=Path(self.requirement['policy']['budget_root'])/'source-inputs'
        need(self.data_root in {ROOT,allowed_control_root}
             and not any(p.is_symlink() for p in [self.data_root,*self.data_root.parents]),
             'CONTINUOUS_SOURCE_ROOT_NOT_ALLOWED')
        if self.data_root==ROOT:
            verify_saved_source_proofs(data_root=ROOT,proofs=source['source_proofs'])
        else:
            from .ordinary_source_authority import verify_ordinary_source_proofs
            need(source['record_type'] in {'D04_HISTORICAL_PRIMARY_CONTROL_SOURCE', 'D04_NATIVE_HISTORICAL_CONTROL_SOURCE'}
                 and source['normal_update_input'] is False,
                 'CONTINUOUS_CONTROL_SOURCE_SCOPE_REQUIRED')
            verify_ordinary_source_proofs(data_root=self.data_root,proofs=source['source_proofs'])
        need(request in source_requests(source), 'CONTINUOUS_REQUEST_NOT_IN_SOURCE')
        need(configured_transport_policy(requirement=self.requirement,repo_root=ROOT) == policy
             and request_body(request,policy) == self.provider_request_body_bytes
             and _json(request['response_protocol']) == self.output_schema_bytes,
             'CONTINUOUS_PROVIDER_PAYLOAD_CHANGED')
        return request


def prepare_requests(*, company_id, metric_id='D04', prior_call_ordinal=None,control_id=None, native=False,
                     reference_context=False):
    from .r6_semantic_source import prepare_d04_semantic_source
    from .requirement_profile import validate_execution_authority
    requirement = load_requirement_snapshot(snapshot_dir=ROOT/'requirements'/REQUIREMENT_ID)
    validate_execution_authority(repo_root=ROOT,requirement=requirement)
    validate_semantic_rule_bindings(requirement)
    load_delegation(requirement=requirement)
    policy = configured_transport_policy(requirement=requirement,repo_root=ROOT)
    authority = control.prepare_successor_invocation_authority(repo_root=ROOT,requirement_id=REQUIREMENT_ID)
    need(metric_id in {'B13','D03','D04'},'CONTINUOUS_SEMANTIC_METRIC_REQUIRED')
    need(not native or (metric_id == 'D04' and prior_call_ordinal is None),
         'D04_NATIVE_REQUIRES_CURRENT_COMPLETE_SOURCE')
    need(not reference_context or (prior_call_ordinal is None and (native or metric_id in {'B13', 'D03'})),
         'CONTINUOUS_REFERENCE_GROUPING_UNSUPPORTED')
    from .continuous_request_context import FORMAT_VERSION
    context_format = FORMAT_VERSION if reference_context else None
    data_root=ROOT
    if control_id is not None:
        need(metric_id=='D04' and prior_call_ordinal is None,'CONTINUOUS_HISTORICAL_CONTROL_REQUIRES_D04')
        from .r6_historical_controls import prepare_control_source
        data_root=Path(requirement['policy']['budget_root'])/'source-inputs'
        source=prepare_control_source(repo_root=data_root,company_id=company_id,control_id=control_id)
        if native:
            from .d04_native_assessment import native_source
            source = native_source(source, historical_control=True, request_context_format=context_format)
    elif prior_call_ordinal is not None:
        need(metric_id=='D03','CONTINUOUS_VERIFICATION_REQUIRES_D03')
        from .r6_semantic_verification import prepare_verification_source
        source=prepare_verification_source(company_id=company_id,prior_call_ordinal=prior_call_ordinal)
    elif metric_id=='D03':
        from .r6_regulatory_semantics import prepare_regulatory_semantic_source
        source = prepare_regulatory_semantic_source(repo_root=ROOT,company_id=company_id,request_context_format=context_format)
    elif metric_id == 'B13':
        from .capacity_semantic_source import prepare_capacity_semantic_source
        source = prepare_capacity_semantic_source(repo_root=ROOT,company_id=company_id,request_context_format=context_format)
    else:
        source = prepare_d04_semantic_source(repo_root=ROOT,company_id=company_id)
        if native:
            from .d04_native_assessment import native_source
            source = native_source(source, request_context_format=context_format)
    if data_root==ROOT:verify_saved_source_proofs(data_root=ROOT,proofs=source['source_proofs'])
    else:
        from .ordinary_source_authority import verify_ordinary_source_proofs
        verify_ordinary_source_proofs(data_root=data_root,proofs=source['source_proofs'])
    raw = _json(source)
    return [SemanticRequest(_FACTORY,raw,_json(request),request_body(request,policy),
        _json(request['response_protocol']),requirement,authority,data_root) for request in source_requests(source)]


def transport_payload(*, request, policy):
    """Called by the existing DeepSeek transport immediately before sending."""
    need(type(request) is SemanticRequest, 'CONTINUOUS_REQUEST_TYPE_REQUIRED')
    request.validate(policy)
    return request.request_bytes,request.provider_request_body_bytes,request.output_schema_bytes


def usage_observation(raw):
    """Unknown token/cost observations stay null, including HTTP errors."""
    usage = {}
    if raw:
        try:
            value = strict_json_loads(text=raw.decode())
            if type(value) is dict and type(value.get('usage')) is dict: usage = value['usage']
        except (ValueError,UnicodeError): pass
    def count(key):
        value = usage.get(key)
        return value if type(value) is int and value>=0 else None
    return {'input_tokens':count('prompt_tokens'),'output_tokens':count('completion_tokens'),
        'cache_hit_input_tokens':count('prompt_cache_hit_tokens'),
        'cache_miss_input_tokens':count('prompt_cache_miss_tokens'),
        'actual_cost':None}


def usage_error(raw, *, expected_prompt_tokens=None, enforce_total_context=False):
    observed = usage_observation(raw)
    if observed['input_tokens'] is None or observed['output_tokens'] is None:return 'USAGE_UNKNOWN'
    usage = strict_json_loads(text=raw.decode())['usage']
    total = usage.get('total_tokens')
    if type(total) is not int or total != observed['input_tokens']+observed['output_tokens']:
        return 'USAGE_UNKNOWN'
    hit,miss = observed['cache_hit_input_tokens'],observed['cache_miss_input_tokens']
    for key,value in [('prompt_cache_hit_tokens',hit),('prompt_cache_miss_tokens',miss)]:
        if key in usage and value is None:return 'USAGE_UNKNOWN'
    if hit is not None and miss is not None and hit+miss!=observed['input_tokens']:return 'USAGE_UNKNOWN'
    if observed['input_tokens'] > 200000 or (enforce_total_context and total > 200000):
        return 'CONTEXT_LIMIT'
    if expected_prompt_tokens is not None and observed['input_tokens'] != expected_prompt_tokens:
        return 'CONTEXT_REFERENCE_MISMATCH'
    return ''


def build_plan(prepared):
    requirement = prepared.requirement
    policy = configured_transport_policy(requirement=requirement,repo_root=ROOT)
    request = prepared.validate(policy)
    metric_id = request.get('metric_id','D04')
    runtime = load_provider_runtime_authority(repo_root=ROOT,provider=policy.provider,model=policy.model,api=policy.api)
    from .continuous_request_context import measure_request
    context = measure_request(prepared.provider_request_body_bytes,
        provider=policy.provider, model=policy.model, api=policy.api)
    plan = control.build_successor_ai_invocation_plan(repo_root=ROOT,requirement_id=REQUIREMENT_ID,
        authority=prepared.authority,
        release_input_plan_id=content_hash(value={'purpose':metric_id+('_SOURCE_ASSESSMENT' if metric_id == 'B13'
            or request.get('native_evidence_requested') is True else '_FEASIBILITY'),'source':request['source_id']}),
        source_identity_hash=request['source_id'],selected_representation_hash=request['request_id'],
        task_contract_hash=content_hash(value={'metric':metric_id,'prompt':request['system_prompt']}),
        output_schema_hash=content_hash(value=request['response_protocol']),serialization_version='continuous-'+metric_id.lower()+'-chat-v1',
        provider=policy.provider,model=policy.model,api=policy.api,request_body=prepared.provider_request_body_bytes,
        maximum_payload_bytes=policy.maximum_payload_bytes,maximum_context_tokens=200000,
        estimated_context_tokens=context['context_tokens'],
        context_authority_hash=content_hash(value={'provider_runtime':runtime['context_authority_hash'],
            'bounded_chat_context':context['context_authority_hash']}),estimator_id=context['estimator_id'],
        estimator_version=context['estimator_version'],estimator_method=context['estimator_method'],
        billing_class=runtime['billing_class'],paid_call_observation_source=runtime['paid_call_observation_source'],
        pricing_snapshot_hash=content_hash(value={'provider':policy.provider,'model':policy.model,
            'status':'NON_BLOCKING_PRICE_UNAVAILABLE'}),estimated_cost=None)
    need(plan['observability']['estimated_context_tokens']<=200000
         and len(prepared.provider_request_body_bytes)<=policy.maximum_payload_bytes,
         'CONTINUOUS_REQUEST_RESOURCE_LIMIT')
    return policy,plan


def preserve_execution_rules(prepared, path):
    """Retain the exact rules/configuration used before later draft changes."""
    from .sources import resolve_repository_file
    prepared.authority._check()
    files = strict_json_loads(text=prepared.authority._files.decode())
    with (path/'execution-rules.tar.gz').open('xb') as output:
        with tarfile.open(fileobj=output,mode='w:gz') as archive:
            for relative,binding in sorted(files.items()):
                raw = resolve_repository_file(repo_root=ROOT,repo_relative_path=relative).read_bytes()
                need({'sha256':sha256_bytes(content=raw),'size':len(raw)}==binding,
                     'CONTINUOUS_EXECUTION_RULE_CHANGED:' + relative)
                member=tarfile.TarInfo(relative);member.size=len(raw);member.mode=0o600
                archive.addfile(member,io.BytesIO(raw))
        output.flush()
        import os
        os.fsync(output.fileno())
    control._exclusive_write_json(path=path/'execution-rules.json',value={
        'requirement_id':prepared.requirement['requirement_id'],
        'requirement_closure_hash':prepared.requirement['requirement_closure_hash'],'files':files})


class SourceAuthenticityFailure(ValueError):
    pass


class _Transport:
    def __init__(self, *, prepared, policy, ledger, path, intent, recorded_wire, owner_token,
                 native_assessment=False):
        self.prepared,self.policy,self.ledger = prepared,policy,ledger
        self.path,self.intent,self.recorded_wire = path,intent,recorded_wire
        self.wire = None
        self.owner_token = owner_token
        self.native_assessment = native_assessment

    @property
    def transport_kind(self):
        return 'REAL_MODEL_PROVIDER' if self.ledger.live else 'MOCK'

    def send(self, *, request_body, plan, execution_id, attempt_ordinal):
        from . import ai_adapter as adapter
        from .sources import resolve_repository_file
        import os
        need(attempt_ordinal==1 and request_body==self.prepared.provider_request_body_bytes
             and plan['ai_invocation_plan_id']==self.intent['plan_id'], 'CONTINUOUS_EXECUTION_REQUEST_CHANGED')
        need(control._SUCCESSOR_AUTHORITY.get() is self.prepared.authority and self.ledger._locked,
             'CONTINUOUS_WB3_OWNER_CONTEXT_REQUIRED')
        root = self.path/'invocation_control'
        reservation = control._validate_active_reservation_for_plan(
            reservation=strict_json_loads(text=resolve_repository_file(repo_root=root,
                repo_relative_path='reservations/'+plan['provider_request_identity'].split(':')[1]+'.json').read_text()),
            plan=plan)
        markers = control._egress_markers_for_execution(root=root,execution_id=execution_id)
        need(reservation['owner_process_id']==os.getpid()
             and reservation['owner_token_hash']==content_hash(value=self.owner_token)
             and reservation['execution_id']==execution_id
             and len(markers)==1 and markers[0]['ai_invocation_plan_id']==plan['ai_invocation_plan_id']
             and markers[0]['transport_kind']==self.transport_kind, 'CONTINUOUS_WB3_RESERVATION_OWNER_REQUIRED')
        def source_check():
            try:self.prepared.validate(self.policy)
            except ValueError as error:raise SourceAuthenticityFailure(str(error)) from error
        raw = None; output = None; request_id = ''; error_class = ''; error_detail = ''; status_code = 200
        try:
            if self.ledger.live:
                need(self.recorded_wire is None and self.ledger._locked, 'CONTINUOUS_LIVE_LEDGER_REQUIRED')
                source_check()
                load_delegation(requirement=self.prepared.requirement,online=True)
                result = adapter._build_repository_transport(policy=self.policy).complete(
                    prepared_request=self.prepared,
                    egress_capability=adapter._RESERVATION_OWNER_EGRESS_CAPABILITY,
                    before_socket_open=source_check)
                raw,output,request_id = result.raw_response_bytes,result.response_bytes,result.provider_request_id
                mismatch = adapter.transport_observation_mismatch(policy=self.policy,
                    observation=result.observation,request_bytes=request_body)
                need(mismatch is None, 'CONTINUOUS_TRANSPORT_OBSERVATION_CHANGED')
            else:
                need(type(self.recorded_wire) is bytes, 'CONTINUOUS_RECORDED_WIRE_REQUIRED')
                raw = self.recorded_wire
                request_id,model,text = adapter._deepseek_chat_output_text(raw_response_bytes=raw)
                need(model==self.policy.model,'CONTINUOUS_RECORDED_MODEL_CHANGED')
                output = text.encode()
        except adapter.TransportAttemptError as error:
            raw,output,request_id = error.raw_response_bytes,error.assistant_output_bytes,error.provider_request_id
            error_class = error.error_class; status_code = adapter._controller_status_code(error_class=error_class)
            error_detail = str(error)
        except SourceAuthenticityFailure as error:
            error_class = 'SOURCE_AUTHENTICITY_FAILED'; status_code = 0
            error_detail = str(error)
        usage = usage_observation(raw)
        if not error_class:
            # The plan counted the exact outgoing body before opening a socket.
            # Compare genuine service observations without treating synthetic
            # recorded usage as evidence for the reference tokenizer.
            reference_input = None
            if self.ledger.live and plan['observability']['estimator_method'] == 'PINNED_REFERENCE_CHAT_FORMAT':
                from .continuous_request_context import OUTPUT_RESERVE
                reference_input = plan['observability']['estimated_context_tokens'] - OUTPUT_RESERVE
            error_class = usage_error(raw, expected_prompt_tokens=reference_input,
                                      enforce_total_context=self.ledger.live)
        for name,data in [('raw-response.bin',raw),('assistant-output.bin',output)]:
            if data is not None: control._exclusive_write_bytes(path=self.path/'wire'/name,content=data)
        body = {'record_type':'CONTINUOUS_ORIGINAL_WIRE','execution_id':execution_id,
            'intent_id':self.intent['intent_id'],'ai_invocation_plan_id':plan['ai_invocation_plan_id'],
            'request_sha256':sha256_bytes(content=request_body),'provider_request_id':request_id,
            'status_code':status_code,'error_class':error_class,'error_detail':error_detail,
            'usage':usage,'observed_at_utc':now(),
            'raw_response_sha256':None if raw is None else sha256_bytes(content=raw),
            'assistant_output_sha256':None if output is None else sha256_bytes(content=output),
            'mode':'LIVE' if self.ledger.live else 'RECORDED_TEST_ONLY'}
        self.wire = {**body,'wire_id':content_hash(value=body)}
        control._exclusive_write_json(path=self.path/'wire/journal.json',value=self.wire)
        if error_class in {'UNKNOWN_REMOTE_OUTCOME','TIMEOUT'}:
            raise control.UnknownRemoteOutcomeError(error_class)
        return {'status_code':status_code,'error_class':error_class or ('' if self.native_assessment else _FEASIBILITY),
            'response_body':output if output is not None else raw or b'',
            'provider_request_id':request_id,'usage':usage}


def execute_feasibility(*, prepared, ledger, recorded_wire=None):
    """A response is a feasibility observation, never a native result."""
    need(strict_json_loads(text=prepared.request_bytes.decode()).get('metric_id') != 'B13',
         'B13_REQUIRES_NATIVE_ASSESSMENT_ENTRY')
    need(not strict_json_loads(text=prepared.request_bytes.decode()).get('native_evidence_requested'),
         'D04_NATIVE_REQUEST_REQUIRES_NATIVE_ENTRY')
    return _execute_semantic(prepared=prepared, ledger=ledger, recorded_wire=recorded_wire,
                             native_assessment=False)


def execute_capacity_assessment(*, prepared, ledger, recorded_wire=None):
    """Accept new B13 source proposals through full native Candidate/Evidence."""
    need(strict_json_loads(text=prepared.request_bytes.decode()).get('metric_id') == 'B13',
         'B13_NATIVE_ASSESSMENT_REQUIRED')
    return _execute_semantic(prepared=prepared, ledger=ledger, recorded_wire=recorded_wire,
                             native_assessment=True)


def execute_d04_assessment(*, prepared, ledger, recorded_wire=None):
    """Fresh current-source D04 Evidence; historical diagnostics are not inputs."""
    need(strict_json_loads(text=prepared.request_bytes.decode())['record_type'] == 'D04_NATIVE_INTERPRETATION_REQUEST',
         'D04_FRESH_NATIVE_REQUEST_REQUIRED')
    return _execute_semantic(prepared=prepared, ledger=ledger, recorded_wire=recorded_wire,
                             native_assessment=True)


def _execute_semantic(*, prepared, ledger, recorded_wire, native_assessment):
    from .r6_semantic_scope import validate_response
    request_fields=strict_json_loads(text=prepared.request_bytes.decode())
    need(not native_assessment or request_fields.get('metric_id') == 'B13'
         or request_fields['record_type'] == 'D04_NATIVE_INTERPRETATION_REQUEST',
         'NATIVE_DIAGNOSTIC_UPGRADE_FORBIDDEN')
    if request_fields['record_type']=='D03_SEMANTIC_VERIFICATION_REQUEST':
        from .r6_semantic_verification import validate_response
    elif request_fields.get('metric_id')=='D03':
        from .r6_regulatory_semantics import validate_response
    elif request_fields.get('metric_id') == 'B13':
        from .capacity_semantic_review import validate_response
    elif request_fields['record_type'] == 'D04_NATIVE_INTERPRETATION_REQUEST':
        from .d04_native_assessment import validate_response
    policy,plan = build_plan(prepared)
    def response_validator(**kwargs):
        if native_assessment:
            try:
                validate_response(request=request_fields, raw_response=kwargs['response_body'])
            except (ValueError, KeyError, TypeError) as error:
                raise control.SchemaViolationError(str(error)) from error

    def evidence_validator(**kwargs):
        if native_assessment:
            if request_fields.get('metric_id') == 'B13':
                from .capacity_native_assessment import build_acceptance
            else:
                from .d04_native_assessment import build_acceptance
            try:
                return build_acceptance(prepared=prepared, plan=plan, response_body=kwargs['response_body'])
            except (ValueError, KeyError, TypeError) as error:
                raise control.EvidenceFailureError(str(error)) from error
    if ledger.live:
        need(recorded_wire is None, 'CONTINUOUS_RECORDED_BYTES_CANNOT_RUN_LIVE')
        need(ledger.root == Path(prepared.requirement['policy']['budget_root'])
             and ledger.binding['delegation_url'] == prepared.requirement['policy']['delegation_url']
             and ledger.binding['delegation_body_sha256'] == prepared.requirement['policy']['delegation_body_sha256']
             and ledger.binding['limits'] == [240,240,80], 'CONTINUOUS_LIVE_ALLOWANCE_CHANGED')
        from .ai_adapter import api_key_environment_name
        import os
        need(bool(os.environ.get(api_key_environment_name(policy=policy),'').strip()),
             'DEEPSEEK_API_KEY_REQUIRED')
        # This flag is installed only after the actual offline bridge and count
        # tests have been saved and bound to this implementation.
        from .continuous_call_wiring import validate_wiring_receipt
        validate_wiring_receipt(requirement=prepared.requirement)
    with ledger.locked():
        path,intent = ledger.claim(channel='PROVIDER',request_digest=request_digest(
            strict_json_loads(text=prepared.request_bytes.decode()),policy),
            requirement=prepared.requirement,plan_id=plan['ai_invocation_plan_id'],purpose='remaining_development_feasibility')
        control._exclusive_write_bytes(path=path/'source.json',content=prepared.source_bytes)
        control._exclusive_write_bytes(path=path/'semantic-request.json',content=prepared.request_bytes)
        preserve_execution_rules(prepared,path)
        owner = str(uuid.uuid4()); when = now()
        transport = _Transport(prepared=prepared,policy=policy,ledger=ledger,path=path,intent=intent,
            recorded_wire=recorded_wire,owner_token=owner,native_assessment=native_assessment)
        execution = control.execute_successor_invocation(repo_root=ROOT,authority=prepared.authority,
            workspace_dir=path,plan=plan,request_body=prepared.provider_request_body_bytes,
            execution_id=control.execution_identity(ai_invocation_plan_id=plan['ai_invocation_plan_id'],owner_token=owner,authorized_at_utc=when),
            owner_token=owner,authorized_at_utc=when,clock=now,transport=transport,
            response_validator=response_validator,evidence_validator=evidence_validator)
        terminal = ledger.finish_provider(path=path,intent=intent,execution=execution,wire=transport.wire)
        result = {'execution_receipt_id':execution['execution_receipt_id'],'terminal':terminal,
            'semantic_correctness_verified':False,'native_result_created':False,'production_authorized':False}
        if native_assessment:
            result['native_candidate_evidence_created'] = execution['status'] == 'SUCCEEDED'
            result['acceptance_scope'] = ('ONE_HISTORICAL_CONTROL_REQUEST_NOT_CURRENT_OR_WHOLE_FILING'
                if 'historical_control' in request_fields else 'ONE_REQUEST_SOURCE_ASSESSMENT_NOT_COMPLETE_METRIC')
        output = path/'wire/assistant-output.bin'
        if output.exists() and not transport.wire['error_class']:
            try:
                result['response_check'] = validate_response(request=strict_json_loads(text=prepared.request_bytes.decode()),
                    raw_response=output.read_bytes())
            except (ValueError,KeyError,TypeError) as error:
                result['response_check_error'] = str(error)
        filename = ('capacity-assessment.json' if request_fields.get('metric_id') == 'B13' else 'd04-assessment.json')
        control._exclusive_write_json(path=path/(filename if native_assessment else 'feasibility.json'),value=result)
        return path,result
