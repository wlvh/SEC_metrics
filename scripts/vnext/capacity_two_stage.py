"""Offline B13 two-stage request candidate over unchanged complete source groups.

The scan is only a model proposal of relevant references. It is not an
absence proof, native Evidence, or permission to make a live call. Both stages
carry every original source unit; an overlarge candidate set stops instead of
silently truncating the task. Existing request and success identities do not
change.
"""
from copy import deepcopy
import re

from .canonical import canonical_json_bytes, content_hash, sha256_bytes, strict_json_loads
from .capacity_reference_contract import RELEVANCE_VERSION, _owners, restore_base_request

SCAN_VERSION = 'B13_COMPLETE_REFERENCE_SCAN_V1'
ASSESS_VERSION = 'B13_SCANNED_INTERPRETATION_V1'
MAX_CANDIDATE_REFS = 64
_TYPED = re.compile(r'(?:B|F)[0-9]+|S[0-9]+:[0-9]+\Z')
SCAN_PROMPT = (
    'Scan EVERY supplied B13 source unit, including units without navigation hits. '
    'Return exactly every zero-based unit index in units_reviewed. Return typed '
    'original-source references only for remaining potentially relevant physical '
    'manufacturing production, available capacity, utilization, constraints, '
    'expansion plans, or unresolved relationships. Include EVERY supplied required '
    'candidate reference even if it appears irrelevant; the second stage will '
    'classify it. Do not enumerate ordinary sales, finance, tax, governance, '
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


def scan_request(request):
    """Keep original units/identities in a smaller-output scan protocol."""
    _base(request)
    body = {key: deepcopy(value) for key, value in request.items()
            if key not in {'request_id', 'source_reference_contract'}}
    body.update(record_type='B13_REFERENCE_SCAN_REQUEST',
                system_prompt=SCAN_PROMPT, response_protocol=deepcopy(SCAN_PROTOCOL),
                scan_contract={'version': SCAN_VERSION,
                               'interpretation_request_id': request['request_id']})
    return {**body, 'request_id': content_hash(value=body)}


def validate_scan(*, request, scan_request_value, raw_response):
    """Prove format and source ownership, not model relevance or absence."""
    _need(scan_request_value == scan_request(request), 'B13_SCAN_REQUEST_CHANGED')
    _need(type(raw_response) is bytes, 'B13_SCAN_RESPONSE_BYTES_REQUIRED')
    response = strict_json_loads(text=raw_response.decode('utf-8'))
    _need(type(response) is dict and set(response) == set(SCAN_PROTOCOL['root_fields']),
          'B13_SCAN_RESPONSE_FIELDS_CHANGED')
    units = response['units_reviewed']
    _need(type(units) is list and units == list(range(len(request['units']))),
          'B13_SCAN_UNIT_CENSUS_INCOMPLETE')
    inventory = _reference_inventory(request)
    for field in ('candidate_refs', 'unresolved_refs'):
        refs = response[field]
        _need(type(refs) is list and all(type(ref) is str and _TYPED.fullmatch(ref)
              and ref in inventory for ref in refs) and len(refs) == len(set(refs)),
              'B13_SCAN_REFERENCE_INVALID:' + field)
    candidates = response['candidate_refs']
    _need(len(candidates) <= MAX_CANDIDATE_REFS, 'B13_SCAN_CANDIDATE_CAP_EXCEEDED')
    _need(set(response['unresolved_refs']) <= set(candidates),
          'B13_SCAN_UNRESOLVED_NOT_CANDIDATE')
    _need(_required_references(request, inventory) <= set(candidates),
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


def interpretation_request(*, request, scan_result):
    """Carry the full original source and the exact validated scan proposal."""
    _base(request)
    _need(scan_result.get('scan_request_id') == scan_request(request)['request_id']
          and scan_result.get('interpretation_request_id') == request['request_id']
          and scan_result.get('source_id') == request['source_id']
          and scan_result.get('scan_result_id') == content_hash(value={
              key: value for key, value in scan_result.items() if key != 'scan_result_id'})
          and scan_result.get('native_credit') is False
          and scan_result.get('model_relevance_proven') is False,
          'B13_SCAN_RESULT_NOT_BOUND')
    body = {key: deepcopy(value) for key, value in request.items() if key != 'request_id'}
    body.update(system_prompt=body['system_prompt'] + ASSESS_SUFFIX,
                two_stage_scan=deepcopy(scan_result),
                two_stage_contract={'version': ASSESS_VERSION,
                                    'prior_request_id': request['request_id']})
    return {**body, 'request_id': content_hash(value=body)}


def validate_interpretation(*, request, scan_result, interpretation,
                            raw_response, source):
    """Use existing V4 semantics after checking stage linkage and references.

    This is an offline check; it does not create Candidate/Evidence or replay a
    provider receipt. A missed relevant source item remains a model risk.
    """
    _need(interpretation == interpretation_request(request=request, scan_result=scan_result),
          'B13_TWO_STAGE_INTERPRETATION_CHANGED')
    _need(type(raw_response) is bytes, 'B13_TWO_STAGE_RESPONSE_BYTES_REQUIRED')
    value = strict_json_loads(text=raw_response.decode('utf-8'))
    _need(type(value) is dict and type(value.get('findings')) is list
          and type(value.get('units')) is list, 'B13_TWO_STAGE_RESPONSE_INVALID')
    allowed = set(scan_result['response']['candidate_refs'])
    accounted = set()
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
            elif item.startswith('SCAN_OMISSION:'):
                ref = item[len('SCAN_OMISSION:'):]
                _need(ref in _reference_inventory(request),
                      'B13_TWO_STAGE_OMISSION_REFERENCE_INVALID')
    _need(allowed <= accounted, 'B13_TWO_STAGE_CANDIDATE_UNASSESSED')
    from .capacity_semantic_review import validate_response
    checked = validate_response(request=request, raw_response=raw_response, source=source)
    _need(not checked['unresolved'], 'B13_TWO_STAGE_UNRESOLVED')
    return {'scan_result_id': scan_result['scan_result_id'],
            'interpretation_request_id': interpretation['request_id'],
            'original_validator_result': checked,
            'native_credit': False,
            'model_accuracy_proven': False}


def scan_response_bytes(value):
    """Explicit helper for portable recorded checks; no live transport."""
    return canonical_json_bytes(value=value)
