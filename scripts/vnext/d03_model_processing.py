"""Complete development-model D03 proposals into native PENDING review.

Source preparation authenticates the saved ordinary material. Raw model wires
remain processing artifacts, not SEC sources or simulated provider executions.
The existing ordinary default, real controller and old D03 acceptor are intact.
"""
import json
import re
from pathlib import Path

from .canonical import content_hash, sha256_bytes, sha256_file, strict_json_loads
from .capacity_semantic_review import _restore_units
from .continuous_request_context import FORMAT_VERSION, measure_request, _load_tokenizer
from .r6_regulatory_semantics import prepare_regulatory_semantic_source
from .r6_semantic_review import _source_items
from .records import validate_record
from .native_unit_index import evidence_json_bytes
from .review import build_review_unit
from .specs import compile_spec_file

ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = 'catalog/r6/D03_model_source_development_v1.md'
POLICY_PATH = 'catalog/r6/regulatory_semantic_review_v5.json'
VERSION = 'D03_COMPLETE_MODEL_SOURCE_INPUT_V1'
PROMPT_SHA256 = 'b6094f993e40d48e16ce85791a7f9abce7e94ccce9147cf44aa17b5135dc9680'


def _need(ok, reason):
    if not ok:
        raise ValueError(reason)


def _bytes(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False,
                      sort_keys=True, separators=(',', ':')).encode('utf-8')


def _input(source, raw):
    wire = strict_json_loads(text=raw.decode('utf-8'))
    measured = measure_request(raw, require_reference=True)
    _need(measured['fits'] and len(wire['messages']) == 2
          and [m['role'] for m in wire['messages']] == ['system', 'user']
          and sha256_bytes(content=wire['messages'][0]['content'].encode()) == PROMPT_SHA256,
          'D03_MODEL_REQUEST_CONTRACT_OR_RESOURCE_CHANGED')
    value = strict_json_loads(text=wire['messages'][1]['content'])
    _need(value['source_id'] == source['semantic_source_id']
          and value['company_id'] == source['company_id']
          and value['target_period'] == source['prepared_annual_input']['table_input']['target_period']
          and value['source_filing'] == source['documents'][0]['filing']
          and value['visible_columns'] == ['source_index', 'html_quotation_context', 'text'],
          'D03_MODEL_INPUT_SOURCE_CONTEXT_CHANGED')
    visible = [u for u in source['units'] if u['kind'] == 'VISIBLE_TEXT']
    rows, bounds = [], []
    for unit in visible:
        start = len(rows)
        rows.extend([[b['block_index'], b['html_quotation_context'], b['text']]
                     for b in unit['payload']['blocks']])
        bounds.append({'unit_id': unit['unit_id'], 'start_row': start, 'end_row_exclusive': len(rows)})
    _need(_bytes(value['complete_visible_rows']) == _bytes(rows)
          and value['visible_unit_bounds'] == bounds, 'D03_MODEL_VISIBLE_CONTEXT_CHANGED')
    _need(type(value['native_units']) is list, 'D03_MODEL_NATIVE_UNIT_LIST_REQUIRED')
    native = (_restore_units(value['native_units'], value['shared_source_dictionaries'])
              if value['native_units'] else [])
    _need(bool(native) or value['shared_source_dictionaries'] == {},
          'D03_MODEL_EMPTY_NATIVE_DICTIONARY_CHANGED')
    by_id = {u['unit_id']: u for u in source['units']}
    for unit in native:
        _need(unit['unit_id'] in by_id and unit['kind'] != 'VISIBLE_TEXT'
              and _bytes(unit) == _bytes(by_id[unit['unit_id']]), 'D03_MODEL_NATIVE_PAYLOAD_CHANGED')
    owned = native if native else visible
    _need(value['responsibility_unit_ids'] == [u['unit_id'] for u in owned]
          and value['visible_context_role'] == ('CONTEXT_ONLY' if native else 'RESPONSIBILITY'),
          'D03_MODEL_RESPONSIBILITY_CHANGED')
    return value, {u['unit_id']: u for u in [*visible, *native]}, measured


def _response(raw, payload, units):
    tokenizer, _ = _load_tokenizer()
    _need(len(tokenizer.encode(raw.decode('utf-8'), add_special_tokens=False).ids) <= 4096,
          'D03_MODEL_RESPONSE_OUTPUT_LIMIT')
    value = strict_json_loads(text=raw.decode('utf-8'))
    _need(type(value) is dict and set(value) == {
        'reviewed_unit_ids', 'findings', 'scope_current_involvement', 'unresolved'}, 'D03_MODEL_RESPONSE_SHAPE')
    _need(value['reviewed_unit_ids'] == payload['responsibility_unit_ids'], 'D03_MODEL_RESPONSE_OWNER_CHANGED')
    _need(type(value['findings']) is list and len(value['findings']) <= 64
          and value['scope_current_involvement'] in {'EXPLICIT_PRESENT', 'EXPLICIT_NONE', 'UNRESOLVED'}
          and type(value['unresolved']) is list
          and all(type(s) is str and s.strip() for s in value['unresolved']), 'D03_MODEL_RESPONSE_FIELDS')
    kinds = strict_json_loads(text=(ROOT/POLICY_PATH).read_text())['kinds']
    seen = set()
    for finding in value['findings']:
        _need(type(finding) is dict and set(finding) == {
            'kind', 'subject', 'event_dates', 'reported_context_times', 'status', 'evidence', 'description'},
            'D03_MODEL_FINDING_FIELDS')
        _need(finding['kind'] in kinds and all(type(finding[k]) is str and finding[k].strip()
              for k in ['subject', 'status', 'description']), 'D03_MODEL_FINDING_VALUE')
        for k in ['event_dates', 'reported_context_times']:
            _need(type(finding[k]) is list and all(type(s) is str and s.strip() for s in finding[k]),
                  'D03_MODEL_TIME_FIELDS')
        key = _bytes(finding)
        _need(key not in seen, 'D03_MODEL_DUPLICATE_FINDING_NO_CLEANUP')
        seen.add(key)
        _need(type(finding['evidence']) is list and finding['evidence'], 'D03_MODEL_EVIDENCE_REQUIRED')
        owned = False
        for ref in finding['evidence']:
            _need(type(ref) is dict and set(ref) == {'unit_id', 'kind', 'source_index'}
                  and type(ref['unit_id']) is str and ref['unit_id'] in units, 'D03_MODEL_REFERENCE_UNIT')
            kind, items = _source_items(units[ref['unit_id']])
            _need(ref['kind'] == kind and type(ref['source_index']) is int
                  and ref['source_index'] in items, 'D03_MODEL_REFERENCE_KIND_OR_INDEX')
            owned |= ref['unit_id'] in payload['responsibility_unit_ids']
        _need(owned, 'D03_MODEL_CONTEXT_ONLY_FINDING')
    return value


def _complete(source, packets):
    _need(type(packets) is list and packets, 'D03_MODEL_COMPLETE_PACKETS_REQUIRED')
    owners, rows, wires = [], [], []
    for packet in packets:
        _need(type(packet) is dict and set(packet) == {
            'request_body', 'response_body', 'expected_request_sha256', 'expected_response_sha256'}
              and type(packet['request_body']) is bytes and type(packet['response_body']) is bytes,
              'D03_MODEL_RAW_PACKET_REQUIRED')
        request, response = packet['request_body'], packet['response_body']
        _need(sha256_bytes(content=request) == packet['expected_request_sha256']
              and sha256_bytes(content=response) == packet['expected_response_sha256'],
              'D03_MODEL_EXTERNAL_WIRE_CHANGED')
        payload, units, measured = _input(source, request)
        value = _response(response, payload, units)
        owners.extend(payload['responsibility_unit_ids'])
        rows.append({'request_sha256': packet['expected_request_sha256'],
            'response_sha256': packet['expected_response_sha256'],
            'request_context': measured, 'responsibility_unit_ids': value['reviewed_unit_ids'],
            'original_response': value})
        wires.append([packet['expected_request_sha256'], packet['expected_response_sha256']])
    _need(owners == source['required_unit_ids'] and len(owners) == len(set(owners)),
          'D03_MODEL_COMPLETE_OWNER_SET_CHANGED')
    return rows, wires


def build_development_company_assessment(*, data_root, company_id, packets,
                                         expected_source_sha256, origin='DEVELOPMENT_MODEL'):
    """Make one pending company review; never impersonate a provider/HUMAN."""
    _need(origin == 'DEVELOPMENT_MODEL', 'D03_MODEL_REAL_EXECUTION_NOT_AUTHORIZED')
    source = prepare_regulatory_semantic_source(repo_root=Path(data_root), company_id=company_id,
        request_context_format=FORMAT_VERSION, ordinary_registered=True)
    _need(sha256_bytes(content=evidence_json_bytes(source)) == expected_source_sha256
          and source['source_serialization_complete'] is True
          and len(source['documents']) == 1, 'D03_MODEL_AUTHENTICATED_SOURCE_CHANGED')
    rows, wires = _complete(source, packets)
    spec = compile_spec_file(path=ROOT/SPEC_PATH, dependency_specs={})
    _need(spec['compiled']['quality_rule'] == {'model_development_method': VERSION},
          'D03_MODEL_DRAFT_SPEC_CHANGED')
    refs = [doc['source_reference'] for doc in source['documents']]
    processing = {'origin': origin, 'version': VERSION, 'source_id': source['semantic_source_id'],
        'source_sha256': expected_source_sha256, 'source_proofs': source['source_proofs'],
        'source_admission': source['source_admission'], 'rows': rows,
        'mapper_sha256': sha256_file(path=Path(__file__)), 'spec_closure_hash': spec['spec_closure_hash'],
        'semantic_acceptance': False, 'company_result_created': False}
    asset_body = {'parent_raw_asset_ids': [d['raw_blob']['raw_asset_id'] for d in source['documents']],
        'transform_id': VERSION, 'transform_semantic_version': '1', 'content_type': 'application/json',
        'tables': [processing]}
    asset = validate_record(record={'record_type': 'DERIVED_ASSET', **asset_body,
        'derived_asset_id': content_hash(value=asset_body), 'storage_uri': 'processing/d03/metadata.json'})
    selected = {'complete_development_assessment': {'source_id': source['semantic_source_id'],
        'required_unit_ids': source['required_unit_ids'], 'rows': rows,
        'provider_execution_verified': False, 'semantic_correctness_verified': False}}
    pending = [{'reason': 'D03_DEVELOPMENT_SEMANTICS_NOT_APPROVED'}]
    pending.extend({'request_sha256': row['request_sha256'], 'reason': reason}
                   for row in rows for reason in row['original_response']['unresolved'])
    body = {'disclosure_group': spec['compiled']['disclosure_group'],
        'source_reference_ids': [r['source_reference_id'] for r in refs],
        'derived_asset_ids': [asset['derived_asset_id']], 'selected': selected,
        'competing_candidates': [], 'unresolved_competing_claims': pending}
    candidate = validate_record(record={'record_type': 'OBSERVATION_CANDIDATE', **body,
        'candidate_hash': content_hash(value=body), 'attempt_id': 'development:d03:'+content_hash(value=wires)[7:],
        'assistant_output_sha256': sha256_bytes(content=_bytes(wires)), 'status': 'REVIEW_REQUIRED'})
    evidence_body = {'candidate_hash': candidate['candidate_hash'], 'status': 'PASS',
        'normalized_values': selected, 'checks': [{'check': 'COMPLETE_SOURCE_REQUEST_RAW_BYTE_AND_REFERENCE_BINDING',
        'status': 'PASS', 'unit_ids': source['required_unit_ids'], 'semantic_acceptance': False}],
        'reason_codes': [], 'identity_constraints': [], 'normalized_scope': {},
        'unresolved_scope_dimensions': list(spec['compiled']['required_claims']), 'system_approval_eligible': False}
    evidence = validate_record(record={'record_type': 'EVIDENCE_CHECK', **evidence_body,
        'evidence_check_id': content_hash(value=evidence_body)})
    context = {'compiled_spec': spec, 'candidate': candidate, 'evidence': evidence,
        'source_bindings': refs, 'complete_original_source': source, 'processing': processing}
    context_bytes = _bytes(context)
    literal = lambda text: re.sub(r'([\\`*_{}\[\]()#+.!|<>])', r'\\\1', str(text))
    display = ['# D03 DEVELOPMENT MODEL: PENDING semantic review', '',
        'All source units have an owner; this does not establish a company conclusion.', '']
    for i, row in enumerate(rows):
        display.extend(['## Request '+str(i), literal(row['request_sha256']),
            'Proposed scope: '+literal(row['original_response']['scope_current_involvement'])])
        for finding in row['original_response']['findings']:
            display.extend([literal(finding['kind'])+': '+literal(finding['subject']),
                'Reported status: '+literal(finding['status']), literal(finding['description']),
                'Events: '+literal(finding['event_dates']),
                'Reported context: '+literal(finding['reported_context_times'])])
            for ref in finding['evidence']:
                unit = next(u for u in source['units'] if u['unit_id'] == ref['unit_id'])
                _, items = _source_items(unit)
                item = items[ref['source_index']]
                text = item['raw_xml'] if ref['kind'] == 'NATIVE_SUPPLEMENT' else item['text']
                display.extend([literal(ref), literal(text)])
                if ref['kind'] == 'NATIVE_FACT':
                    wrapper = next(r for r in unit['payload']['facts']
                                   if r['fact']['ordinal'] == ref['source_index'])
                    display.append('Native attributes: '+literal(wrapper['attributes']))
                    display.append('Native context: '+literal(
                        unit['payload']['contexts'].get(item['context_ref'])))
                    display.append('Native unit: '+literal(
                        unit['payload']['units'].get(item['unit_ref'])))
        display.extend('UNRESOLVED: '+literal(s) for s in row['original_response']['unresolved'])
    rendered_bytes = '\n\n'.join(display).encode('utf-8')
    review = build_review_unit(candidate=candidate, evidence_check=evidence, source_bindings=refs,
        compiled_spec=spec, review_context_hash=sha256_bytes(content=context_bytes),
        rendered_review_hash=sha256_bytes(content=rendered_bytes), renderer_semantic_version=VERSION)
    return {'records': [asset, candidate, evidence, review], 'review_context_bytes': context_bytes,
        'rendered_review_bytes': rendered_bytes, 'processing': processing,
        'native_result_created': False, 'native_run_created': False, 'provider_attempt_created': False}


def read_development_company_assessment(*, directory, data_root, company_id,
                                        expected_candidate_hash, expected_review_unit_hash):
    """Authenticate sources and actual saved wires again; consume no decision."""
    root = Path(directory)
    records = [validate_record(record=strict_json_loads(text=line))
               for line in (root/'records.jsonl').read_text().splitlines()]
    _need(len(records) == 4 and [r['record_type'] for r in records] ==
          ['DERIVED_ASSET', 'OBSERVATION_CANDIDATE', 'EVIDENCE_CHECK', 'REVIEW_UNIT'],
          'D03_MODEL_SAVED_RECORD_SET_CHANGED')
    _need(records[1]['candidate_hash'] == expected_candidate_hash
          and records[3]['review_unit_hash'] == expected_review_unit_hash,
          'D03_MODEL_EXPECTED_NATIVE_IDENTITIES_CHANGED')
    metadata = strict_json_loads(text=(root/'processing/d03/metadata.json').read_text())
    _need(records[0]['tables'] == [metadata], 'D03_MODEL_SAVED_PROCESSING_CHANGED')
    packets = []
    for i, row in enumerate(metadata['rows']):
        packets.append({'request_body': (root/'wires'/str(i)/'request-body.bin').read_bytes(),
            'response_body': (root/'wires'/str(i)/'response.bin').read_bytes(),
            'expected_request_sha256': row['request_sha256'], 'expected_response_sha256': row['response_sha256']})
    out = build_development_company_assessment(data_root=data_root, company_id=company_id,
        packets=packets, expected_source_sha256=metadata['source_sha256'], origin=metadata['origin'])
    _need(out['records'] == records
          and out['review_context_bytes'] == (root/'review-context.json').read_bytes()
          and out['rendered_review_bytes'] == (root/'review.md').read_bytes(),
          'D03_MODEL_SAVED_NATIVE_REPLAY_CHANGED')
    return out
