"""Offline B13 two-stage request candidate over unchanged complete source groups.

The scan is only a model proposal of relevant references. It is not an
absence proof, native Evidence, or permission to make a live call. Both stages
carry every original source unit; an overlarge candidate set stops instead of
silently truncating the task. Existing request and success identities do not
change.
"""
from copy import deepcopy
import re

from .canonical import (canonical_json_bytes, content_hash, sha256_bytes,
                        sha256_file, strict_json_loads)
from .capacity_reference_contract import (RELEVANCE_VERSION, SCANNED_VERSION,
                                          _owners, restore_base_request)

SCAN_VERSION = 'B13_COMPLETE_REFERENCE_SCAN_V1'
ASSESS_VERSION = SCANNED_VERSION
MAX_CANDIDATE_REFS = 64
_TYPED = re.compile(r'(?:B|F)[0-9]+|S[0-9]+:[0-9]+\Z')
SCAN_PROMPT = (
    'Scan EVERY supplied B13 source unit, including units without navigation hits. '
    'Return exactly every zero-based unit index in units_reviewed. Return typed '
    'original-source references only for remaining potentially relevant physical '
    'manufacturing production, available capacity, utilization, constraints, '
    'expansion plans, or unresolved relationships. Include EVERY supplied required '
    'candidate reference not already proved by program_quantity_contract, '
    'even if it appears irrelevant; the second stage will classify it. '
    'Program-owned quantity and monetary roles need no duplicate model row. '
    'Do not enumerate ordinary sales, finance, tax, governance, '
    'product storage or other background without a plausible B13 relationship. '
    'Use B for visible blocks, F for native facts, and Sunit:object for native '
    'supplements. A source unit being scanned is not proof of absence. '
    'Do not summarize, omit, or rewrite source content. Return only the JSON '
    'shape specified in response_protocol.'
)
ASSESS_SUFFIX = (
    ' This is the second stage of a bounded complete-source scan. The '
    'two_stage_scan.response supplies candidate_refs and unresolved_refs, each '
    'bound to the same full source below. Classify every candidate reference '
    'using the original category meanings and report a finding or an unresolved '
    'item for it. Do not emit a finding for a reference outside candidate_refs. '
    'If you notice a potentially relevant item that the scan omitted, report '
    'its exact typed reference in the owning unit unresolved list, prefixed '
    'SCAN_OMISSION:, rather than silently ignoring it. Review every unit; '
    'all original blocks, facts, headings and context remain supplied.'
)
SCAN_PROTOCOL = {
    'root_fields': ['units_reviewed', 'candidate_refs', 'unresolved_refs'],
    'reference_format': 'B<block_index>|F<fact_ordinal>|S<unit_index>:<object_index>',
    'json_schema': {
        'type': 'object',
        'properties': {
            'units_reviewed': {'type': 'array', 'items': {'type': 'integer', 'minimum': 0}},
            'candidate_refs': {'type': 'array', 'items': {'type': 'string'}},
            'unresolved_refs': {'type': 'array', 'items': {'type': 'string'}},
        },
        'required': ['units_reviewed', 'candidate_refs', 'unresolved_refs'],
        'additionalProperties': False,
    },
}


def _need(ok, reason):
    if not ok:
        raise ValueError(reason)


def _direct_current_target_capacity(text, fiscal_year):
    """Only clear present-tense registrant/contract-manufacturer assertions.

    This necessary guard does not decide historical, conditional or other
    entities' capacity from a navigation hit alone.
    """
    from .regulatory_investigation_candidates import _sentences
    physical = re.compile(r'\b(?:manufacturing|production)\s+(?:capacity|capabilities)\b', re.I)
    direct = re.compile(
        r'\bour\s+(?:(?:total|annual|existing|global|domestic|current)\s+)*'
        r'(?:manufacturing|production)\s+(?:capacity|capabilities)\b|'
        r'\bwe\s+(?:have|operate|maintain|possess)\s+'
        r'(?:(?:our|the|existing|current)\s+)*'
        r'(?:manufacturing|production)\s+(?:capacity|capabilities)\b|'
        r'\bour\s+(?:contract\s+)?manufacturers?\b', re.I)
    excluded_context = re.compile(
        r'\b(?:if|unless|would|could|might|hypothetical|illustrative|'
        r'previously|formerly|historically|prior\s+years?|last\s+years?|'
        r'used\s+to|no\s+longer)\b', re.I)
    present = re.compile(r'\b(?:have|has|is|are|operate|maintain|possess|plan|expect)\b', re.I)
    for _, _, statement in _sentences(text):
        if not (physical.search(statement) and direct.search(statement)
                and present.search(statement)) or excluded_context.search(statement):
            continue
        years = {int(year) for year in re.findall(r'\b(?:19|20)\d{2}\b', statement)}
        if years and years != {fiscal_year}:
            continue
        return True
    return False


def _base(request):
    _need(request.get('source_reference_contract', {}).get('version') == RELEVANCE_VERSION,
          'B13_TWO_STAGE_V4_SOURCE_REQUIRED')
    return restore_base_request(request)


def _reference_inventory(request):
    owners = _owners(_base(request))
    values = {}
    for key, unit_index in owners.items():
        kind = key[0]
        text = ('B' + str(key[-1]) if kind == 'VISIBLE_BLOCK' else
                'F' + str(key[-1]) if kind == 'NATIVE_FACT' else
                'S' + str(key[1]) + ':' + str(key[2]))
        _need(text not in values, 'B13_SCAN_REFERENCE_COLLISION')
        values[text] = unit_index
    return values


def _required_references(request, inventory):
    base = _base(request)
    positions = {unit['unit_id']: index for index, unit in enumerate(base['units'])}
    required = set()
    for row in base['required_candidate_assessments']:
        prefix = {'VISIBLE_BLOCK': 'B', 'NATIVE_FACT': 'F'}.get(row['kind'])
        ref = ((prefix + str(row['source_index'])) if prefix else
               'S' + str(positions[row['unit_id']]) + ':' + str(row['source_index']))
        _need(ref in inventory and inventory[ref] == positions[row['unit_id']],
              'B13_SCAN_REQUIRED_SOURCE_CHANGED')
        required.add(ref)
    return required


def _program_owned_references(request, inventory):
    base = _base(request)
    positions = {unit['unit_id']: index for index, unit in enumerate(base['units'])}
    owned = set()
    contract = base['program_quantity_contract']
    for row in [*contract['verified_quantity_roles'],
                *contract['verified_nonphysical_references']]:
        kind, index = row['source_kind'], row['source_index']
        prefix = {'VISIBLE_BLOCK': 'B', 'NATIVE_FACT': 'F'}.get(kind)
        ref = ((prefix + str(index)) if prefix else
               'S' + str(positions[row['unit_id']]) + ':' + str(index))
        _need(ref in inventory and inventory[ref] == positions[row['unit_id']],
              'B13_SCAN_PROGRAM_SOURCE_CHANGED')
        owned.add(ref)
    return owned


def scan_request(request):
    """Keep original units/identities in a smaller-output scan protocol."""
    _base(request)
    body = {key: deepcopy(value) for key, value in request.items()
            if key not in {'request_id', 'source_reference_contract'}}
    inventory = _reference_inventory(request)
    body.update(record_type='B13_REFERENCE_SCAN_REQUEST',
                system_prompt=SCAN_PROMPT, response_protocol=deepcopy(SCAN_PROTOCOL),
                scan_contract={'version': SCAN_VERSION,
                               'interpretation_request_id': request['request_id'],
                               'original_required_refs': sorted(_required_references(request, inventory)),
                               'program_accounted_refs': sorted(_program_owned_references(request, inventory))})
    return {**body, 'request_id': content_hash(value=body)}


def prior_for_scan(*, source, scan):
    """Rebuild a scan's one exact V4 parent from the complete saved source."""
    from .continuous_semantic_calls import source_requests
    from .capacity_reference_contract import upgrade_request
    matches = []
    for original in source_requests(source):
        prior = upgrade_request(original, compact=True, role_labels=True,
                                relevance_scope=True)
        if scan_request(prior) == scan:
            matches.append(prior)
    _need(len(matches) == 1, 'B13_SCAN_PRIOR_SOURCE_NOT_UNIQUE')
    return matches[0]


def validate_scan(*, request, scan_request_value, raw_response):
    """Prove format and source ownership, not model relevance or absence."""
    _need(scan_request_value == scan_request(request), 'B13_SCAN_REQUEST_CHANGED')
    _need(type(raw_response) is bytes, 'B13_SCAN_RESPONSE_BYTES_REQUIRED')
    response = strict_json_loads(text=raw_response.decode('utf-8'))
    _need(type(response) is dict and set(response) == set(SCAN_PROTOCOL['root_fields']),
          'B13_SCAN_RESPONSE_FIELDS_CHANGED')
    units = response['units_reviewed']
    _need(type(units) is list and all(type(index) is int for index in units)
          and units == list(range(len(request['units']))),
          'B13_SCAN_UNIT_CENSUS_INCOMPLETE')
    inventory = _reference_inventory(request)
    for field in ('candidate_refs', 'unresolved_refs'):
        refs = response[field]
        _need(type(refs) is list and all(type(ref) is str and _TYPED.fullmatch(ref)
              and ref in inventory for ref in refs) and len(refs) == len(set(refs)),
              'B13_SCAN_REFERENCE_INVALID:' + field)
    candidates = response['candidate_refs']
    _need(len(candidates) <= MAX_CANDIDATE_REFS, 'B13_SCAN_CANDIDATE_CAP_EXCEEDED')
    program_owned = _program_owned_references(request, inventory)
    _need(not (program_owned & set(candidates)), 'B13_SCAN_PROGRAM_OWNED_DUPLICATED')
    _need(set(response['unresolved_refs']) <= set(candidates),
          'B13_SCAN_UNRESOLVED_NOT_CANDIDATE')
    _need((_required_references(request, inventory) - program_owned) <= set(candidates),
          'B13_SCAN_REQUIRED_CANDIDATE_OMITTED')
    body = {'record_type': 'B13_REFERENCE_SCAN_SHAPE_RESULT',
            'scan_request_id': scan_request_value['request_id'],
            'interpretation_request_id': request['request_id'],
            'source_id': request['source_id'],
            'raw_response_sha256': sha256_bytes(content=raw_response),
            'response': response,
            'candidate_cap': MAX_CANDIDATE_REFS,
            'model_relevance_proven': False,
            'absence_established': False,
            'native_credit': False}
    return {**body, 'scan_result_id': content_hash(value=body)}


def build_scan_acceptance(*, prepared, plan, response_body):
    """Persist a scan-stage receipt without claiming a B13 metric result."""
    from pathlib import Path
    from .normal_source_authority import ROOT
    from .records import validate_record
    from .specs import compile_spec_file
    scan = strict_json_loads(text=prepared.request_bytes.decode('utf-8'))
    source = strict_json_loads(text=prepared.source_bytes.decode('utf-8'))
    prior = prior_for_scan(source=source, scan=scan)
    result = validate_scan(request=prior, scan_request_value=scan,
                           raw_response=response_body)
    document = next(doc for doc in source['documents']
                    if doc['document_id'] == scan['document_context']['document_id'])
    references = [document['source_reference']['source_reference_id']]
    selected = {'source_scan': result}
    body = {'disclosure_group': 'b13_reference_scan_stage_v1',
            'source_reference_ids': references,
            'derived_asset_ids': [plan['selected_representation_hash']],
            'selected': selected, 'competing_candidates': [],
            'unresolved_competing_claims': []}
    candidate = validate_record(record={'record_type': 'OBSERVATION_CANDIDATE',
        **body, 'candidate_hash': content_hash(value=body),
        'attempt_id': 'capacity-scan:' + plan['ai_invocation_plan_id'][7:],
        'assistant_output_sha256': sha256_bytes(content=response_body),
        'status': 'CANDIDATE'})
    evidence_body = {'candidate_hash': candidate['candidate_hash'],
        'status': 'PASS', 'normalized_values': selected,
        'checks': [{'check': 'B13_SCAN_COMPLETE_SOURCE_REFERENCE_SHAPE_ONLY',
                    'status': 'PASS', 'scan_result_id': result['scan_result_id'],
                    'metric_result_created': False}],
        'reason_codes': [], 'identity_constraints': []}
    evidence = validate_record(record={'record_type': 'EVIDENCE_CHECK',
        **evidence_body, 'evidence_check_id': content_hash(value=evidence_body)})
    spec = compile_spec_file(path=ROOT/'catalog/r5/B13_capacity_disclosures_v1.md',
                             dependency_specs={})
    return {'candidate_hash': candidate['candidate_hash'],
        'candidate_record': candidate,
        'derived_asset_id': plan['selected_representation_hash'],
        'evidence_candidate_hash': candidate['candidate_hash'],
        'evidence_check_id': evidence['evidence_check_id'],
        'evidence_record': evidence, 'evidence_status': 'PASS',
        'reader_input_manifest_id': plan['source_identity_hash'],
        'source_reference_ids': references,
        'spec_semantic_hash': spec['spec_semantic_hash'],
        'task_contract_hash': plan['task_contract_hash'],
        'validator_semantic_hash': content_hash(value={
            'module': sha256_file(path=Path(__file__)),
            'scan_protocol': content_hash(value=SCAN_PROTOCOL)}),
        'validator_semantic_version': 'B13_SCAN_SHAPE_STAGE_V1'}


def saved_scan_stage(*, prepared, scan_path):
    """Replay the original scan success before any interpretation credit."""
    from dataclasses import replace
    from pathlib import Path
    from .continuous_call_policy import configured_transport_policy
    from .continuous_semantic_calls import _json, _source_json, request_body
    from .native_assessment_replay import replay_native_response
    from .canonical import strict_json_file
    from .normal_source_authority import ROOT
    path = Path(scan_path)
    _need(path.parent.name == 'calls' and re.fullmatch(r'[0-9]{4}', path.name)
          and not path.is_symlink(), 'B13_SCAN_SAVED_PATH_INVALID')
    interpretation = strict_json_loads(text=prepared.request_bytes.decode('utf-8'))
    prior = restore_prior_interpretation_request(interpretation)
    scan = scan_request(prior)
    policy = configured_transport_policy(requirement=prepared.requirement,
                                         repo_root=ROOT)
    scan_prepared = replace(prepared, request_bytes=_source_json(scan),
        provider_request_body_bytes=request_body(scan, policy),
        output_schema_bytes=_json(scan['response_protocol']))
    replay = replay_native_response(prepared=scan_prepared, path=path)
    raw = replay['success']['response_body']
    result = validate_scan(request=prior, scan_request_value=scan,
                           raw_response=raw)
    terminal = strict_json_file(path=path/'terminal.json')
    accepted = replay['success']['acceptance_receipt']
    body = {'record_type': 'B13_SCAN_STAGE_EXECUTION_PROOF',
            'scan_ordinal': int(path.name),
            'scan_request_id': scan['request_id'],
            'scan_result_id': result['scan_result_id'],
            'scan_terminal_id': terminal['terminal_id'],
            'scan_acceptance_receipt_id': accepted['acceptance_receipt_id'],
            'scan_output_sha256': sha256_bytes(content=raw),
            'source_id': prior['source_id']}
    proof = {**body, 'proof_id': content_hash(value=body)}
    return {'prior_request': prior, 'scan_request': scan,
            'scan_result': result, 'scan_raw_response': raw,
            'scan_prepared': scan_prepared, 'stage_proof': proof,
            'replay': replay}


def build_interpretation_acceptance(*, prepared, plan, response_body,
                                    scan_path):
    """Native B13 Evidence binds both actual stage executions, not V4 bytes."""
    from pathlib import Path
    from .capacity_native_assessment import _build_acceptance
    original = saved_scan_stage(prepared=prepared, scan_path=scan_path)
    interpretation = strict_json_loads(text=prepared.request_bytes.decode('utf-8'))
    link = interpretation['two_stage_contract']
    _need(link.get('scan_execution_proof') == original['stage_proof'],
          'B13_TWO_STAGE_SAVED_SCAN_PROOF_CHANGED')
    checked = validate_interpretation(request=original['prior_request'],
        scan_result=original['scan_result'],
        scan_raw_response=original['scan_raw_response'],
        interpretation=interpretation, raw_response=response_body,
        source=strict_json_loads(text=prepared.source_bytes.decode('utf-8')))
    return _build_acceptance(prepared=prepared, plan=plan,
        response_body=response_body,
        checked=checked['original_validator_result'], metric_id='B13',
        group='b13_capacity_source_assessment_v1',
        spec_path='catalog/r5/B13_capacity_disclosures_v1.md',
        validator_path=Path(__file__), stage_proof=original['stage_proof'])


def validate_registered_scan_stage(*, prepared, stage_record):
    """Cold-read one saved scan without access to its original ledger directory."""
    from pathlib import Path
    from types import SimpleNamespace
    from . import invocation_control as control
    from .continuous_call_policy import configured_transport_policy
    from .continuous_semantic_calls import request_body
    from .native_assessment_replay import revalidation_receipt
    from .normal_source_authority import ROOT
    from .native_unit_index import evidence_json_bytes

    request = strict_json_loads(text=prepared.request_bytes.decode('utf-8'))
    prior = restore_prior_interpretation_request(request)
    scan = scan_request(prior)
    _need(type(stage_record) is dict and stage_record.get('semantic_request') == scan
          and stage_record.get('request_id') == scan['request_id']
          and type(stage_record.get('ordinal')) is int and stage_record['ordinal'] > 0,
          'B13_REGISTERED_SCAN_REQUEST_CHANGED')
    _need(type(stage_record.get('assistant_output')) is str,
          'B13_REGISTERED_SCAN_OUTPUT_CHANGED')
    raw = stage_record['assistant_output'].encode('utf-8')
    result = validate_scan(request=prior, scan_request_value=scan, raw_response=raw)
    plan = stage_record['plan']
    terminal = stage_record['terminal']
    intent = stage_record['intent']
    wire = stage_record['wire']
    receipt = stage_record['acceptance_receipt']
    policy = configured_transport_policy(requirement=prepared.requirement, repo_root=ROOT)
    _need(plan['selected_representation_hash'] == scan['request_id']
          and plan['provider_request_body_sha256'] == sha256_bytes(
              content=request_body(scan, policy))
          and intent['plan_id'] == plan['ai_invocation_plan_id']
          and intent['requirement_closure_hash'] == plan['requirement_closure_hash']
          and intent['ordinal'] == stage_record['ordinal']
          and terminal['intent_id'] == intent['intent_id']
          and terminal['terminal_id'] == content_hash(value={
              key: value for key, value in terminal.items() if key != 'terminal_id'})
          and terminal['status'] == 'SUCCEEDED' and not terminal['stop_reason']
          and wire['assistant_output_sha256'] == sha256_bytes(content=raw)
          and not wire['error_class'], 'B13_REGISTERED_SCAN_EXECUTION_CHANGED')
    scan_prepared = SimpleNamespace(source_bytes=prepared.source_bytes,
        request_bytes=evidence_json_bytes(scan), requirement=prepared.requirement)
    expected = build_scan_acceptance(prepared=scan_prepared, plan=plan,
                                     response_body=raw)
    checked = revalidation_receipt(prepared=scan_prepared, plan=plan,
        original=receipt, expected=expected)
    _need(stage_record['source_revalidation'] == checked,
          'B13_REGISTERED_SCAN_REVALIDATION_CHANGED')
    control._validate_acceptance_receipt(value=receipt, plan=plan,
                                         response_body=raw)
    body = {'record_type': 'B13_SCAN_STAGE_EXECUTION_PROOF',
            'scan_ordinal': stage_record['ordinal'],
            'scan_request_id': scan['request_id'],
            'scan_result_id': result['scan_result_id'],
            'scan_terminal_id': terminal['terminal_id'],
            'scan_acceptance_receipt_id': receipt['acceptance_receipt_id'],
            'scan_output_sha256': sha256_bytes(content=raw),
            'source_id': prior['source_id']}
    proof = {**body, 'proof_id': content_hash(value=body)}
    _need(stage_record['stage_proof'] == proof
          and request['two_stage_contract'].get('scan_execution_proof') == proof,
          'B13_REGISTERED_SCAN_STAGE_LINK_CHANGED')
    return {'prior_request': prior, 'scan_result': result,
            'scan_raw_response': raw, 'stage_proof': proof}


def build_registered_interpretation_acceptance(*, prepared, plan,
                                               response_body, stage_record):
    """Recheck both stages from a creator-saved, portable input record."""
    from pathlib import Path
    from .capacity_native_assessment import _build_acceptance
    stage = validate_registered_scan_stage(prepared=prepared,
                                          stage_record=stage_record)
    request = strict_json_loads(text=prepared.request_bytes.decode('utf-8'))
    source = strict_json_loads(text=prepared.source_bytes.decode('utf-8'))
    checked = validate_interpretation(request=stage['prior_request'],
        scan_result=stage['scan_result'],
        scan_raw_response=stage['scan_raw_response'],
        interpretation=request, raw_response=response_body, source=source)
    return _build_acceptance(prepared=prepared, plan=plan,
        response_body=response_body,
        checked=checked['original_validator_result'], metric_id='B13',
        group='b13_capacity_source_assessment_v1',
        spec_path='catalog/r5/B13_capacity_disclosures_v1.md',
        validator_path=Path(__file__), stage_proof=stage['stage_proof'])


def interpretation_request(*, request, scan_result, scan_raw_response,
                           scan_execution_proof=None):
    """Carry the full original source and the exact validated scan proposal."""
    _base(request)
    _need(type(scan_result) is dict and type(scan_raw_response) is bytes
          and scan_result == validate_scan(request=request,
              scan_request_value=scan_request(request), raw_response=scan_raw_response),
          'B13_SCAN_RESULT_NOT_BOUND')
    body = {key: deepcopy(value) for key, value in request.items() if key != 'request_id'}
    link = {'version': ASSESS_VERSION, 'prior_request_id': request['request_id']}
    if scan_execution_proof is not None:
        _need(type(scan_execution_proof) is dict
              and scan_execution_proof.get('proof_id') == content_hash(value={
                  key: value for key, value in scan_execution_proof.items()
                  if key != 'proof_id'})
              and scan_execution_proof.get('scan_request_id') == scan_result['scan_request_id']
              and scan_execution_proof.get('scan_result_id') == scan_result['scan_result_id']
              and scan_execution_proof.get('scan_output_sha256') ==
                  scan_result['raw_response_sha256'],
              'B13_SCAN_EXECUTION_PROOF_NOT_BOUND')
        link['scan_execution_proof'] = deepcopy(scan_execution_proof)
    body.update(system_prompt=body['system_prompt'] + ASSESS_SUFFIX,
                two_stage_scan=deepcopy(scan_result),
                two_stage_contract=link)
    body['source_reference_contract']['version'] = ASSESS_VERSION
    return {**body, 'request_id': content_hash(value=body)}


def restore_prior_interpretation_request(request):
    """Invert only this explicit successor without rewriting the saved stage."""
    _need(type(request) is dict and request.get('request_id') == content_hash(
          value={key: value for key, value in request.items() if key != 'request_id'}),
          'B13_TWO_STAGE_REQUEST_CHANGED')
    link = request.get('two_stage_contract')
    _need(type(link) is dict and set(link) in (
              {'version', 'prior_request_id'},
              {'version', 'prior_request_id', 'scan_execution_proof'})
          and link['version'] == ASSESS_VERSION
          and request.get('source_reference_contract', {}).get('version') == ASSESS_VERSION
          and type(request.get('system_prompt')) is str
          and request['system_prompt'].endswith(ASSESS_SUFFIX),
          'B13_TWO_STAGE_CONTRACT_CHANGED')
    body = {key: deepcopy(value) for key, value in request.items()
            if key not in {'request_id', 'two_stage_scan', 'two_stage_contract'}}
    body['system_prompt'] = body['system_prompt'][:-len(ASSESS_SUFFIX)]
    body['source_reference_contract']['version'] = RELEVANCE_VERSION
    prior = {**body, 'request_id': content_hash(value=body)}
    _need(prior['request_id'] == link['prior_request_id'],
          'B13_TWO_STAGE_PRIOR_REQUEST_CHANGED')
    _base(prior)
    scan = request.get('two_stage_scan')
    _need(type(scan) is dict and scan.get('scan_result_id') == content_hash(
          value={key: value for key, value in scan.items() if key != 'scan_result_id'})
          and scan.get('interpretation_request_id') == prior['request_id']
          and scan.get('scan_request_id') == scan_request(prior)['request_id']
          and scan.get('source_id') == prior['source_id']
          and scan.get('native_credit') is False,
          'B13_TWO_STAGE_SCAN_BINDING_CHANGED')
    if 'scan_execution_proof' in link:
        proof = link['scan_execution_proof']
        _need(type(proof) is dict and proof.get('proof_id') == content_hash(value={
              key: value for key, value in proof.items() if key != 'proof_id'})
              and proof.get('scan_request_id') == scan['scan_request_id']
              and proof.get('scan_result_id') == scan['scan_result_id']
              and proof.get('scan_output_sha256') == scan['raw_response_sha256'],
              'B13_TWO_STAGE_SCAN_EXECUTION_LINK_CHANGED')
    return prior


def validate_interpretation(*, request, scan_result, scan_raw_response,
                            interpretation, raw_response, source):
    """Use existing V4 semantics after checking stage linkage and references.

    This is an offline check; it does not create Candidate/Evidence or replay a
    provider receipt. A missed relevant source item remains a model risk.
    """
    _need(interpretation == interpretation_request(
              request=request, scan_result=scan_result,
              scan_raw_response=scan_raw_response,
              scan_execution_proof=interpretation.get('two_stage_contract', {}).get(
                  'scan_execution_proof')),
          'B13_TWO_STAGE_INTERPRETATION_CHANGED')
    _need(type(raw_response) is bytes, 'B13_TWO_STAGE_RESPONSE_BYTES_REQUIRED')
    value = strict_json_loads(text=raw_response.decode('utf-8'))
    _need(type(value) is dict and type(value.get('findings')) is list
          and type(value.get('units')) is list, 'B13_TWO_STAGE_RESPONSE_INVALID')
    allowed = set(scan_result['response']['candidate_refs'])
    accounted = set()
    still_unresolved = set()
    for finding in value['findings']:
        _need(type(finding) is list and len(finding) == 5
              and type(finding[3]) is list, 'B13_TWO_STAGE_FINDING_INVALID')
        refs = finding[3]
        _need(all(type(ref) is str and ref in allowed for ref in refs),
              'B13_TWO_STAGE_FINDING_OUTSIDE_SCAN')
        accounted.update(refs)
    for row in value['units']:
        _need(type(row) is dict and type(row.get('unresolved')) is list,
              'B13_TWO_STAGE_UNRESOLVED_INVALID')
        for item in row['unresolved']:
            _need(type(item) is str, 'B13_TWO_STAGE_UNRESOLVED_INVALID')
            if item in allowed:
                accounted.add(item)
                still_unresolved.add(item)
            elif item.startswith('SCAN_OMISSION:'):
                ref = item[len('SCAN_OMISSION:'):]
                _need(ref in _reference_inventory(request),
                      'B13_TWO_STAGE_OMISSION_REFERENCE_INVALID')
    _need(allowed <= accounted, 'B13_TWO_STAGE_CANDIDATE_UNASSESSED')
    _need(set(scan_result['response']['unresolved_refs']) <= still_unresolved,
          'B13_TWO_STAGE_SCAN_UNRESOLVED_LOST')
    from .capacity_semantic_review import validate_response
    checked = validate_response(request=interpretation, raw_response=raw_response,
                                source=source)
    # A scan can legitimately overselect sales or another entity's capacity.
    # A directly bound present-tense registrant assertion cannot be discarded
    # by swapping the category, subject or time label. This bounded relation
    # is necessary, never a general proof of semantic accuracy.
    relevant = {'ACTUAL_PRODUCTION', 'AVAILABLE_CAPACITY',
                'CAPACITY_QUALITATIVE', 'PLANNED_CAPACITY'}
    fiscal_year = request['target_period']['fiscal_year']
    for finding in checked['findings']:
        if ((finding['kind'] not in relevant
             or finding['subject'] != 'TARGET_REGISTRANT'
             or finding['timing'] != 'CURRENT_REPORT')
            and any(evidence['kind'] == 'VISIBLE_BLOCK'
                    and _direct_current_target_capacity(evidence['text'], fiscal_year)
                    for evidence in finding['resolved_evidence'])):
            raise ValueError('B13_TWO_STAGE_EXCLUDED_PHYSICAL_CAPACITY_REQUIRES_REVIEW')
    _need(not checked['unresolved'], 'B13_TWO_STAGE_UNRESOLVED')
    return {'scan_result_id': scan_result['scan_result_id'],
            'interpretation_request_id': interpretation['request_id'],
            'original_validator_result': checked,
            'native_credit': False,
            'model_accuracy_proven': False}


def scan_response_bytes(value):
    """Explicit helper for portable recorded checks; no live transport."""
    return canonical_json_bytes(value=value)
