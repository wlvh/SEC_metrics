"""One complete D03 recorded-response set; no provider or native Result credit.

The D03 source is authenticated once for a company, then every current request
has one exact raw response. This offline packet removes repeated full-source
reconstruction from per-group storage. It does not decide whether a provider's
semantic classifications are correct or authorize a live request.
"""
from pathlib import Path
from copy import deepcopy

from sec_http import write_immutable_bytes
from git_workspace import first_symlink_in_path

from .canonical import (content_hash, sha256_bytes, sha256_file,
                        strict_json_file, strict_json_loads)
from .d03_recorded_response_store import _json_bytes, _root
from .normal_source_authority import ROOT


VERSION = 'D03_COMPLETE_OFFLINE_RECORDED_SET_V1'


def _need(condition, reason):
    if not condition:
        raise ValueError(reason)


def _requests(source):
    from .continuous_request_context import FORMAT_VERSION
    from .r6_regulatory_semantics import (
        prepare_regulatory_semantic_source, requests_from_source)
    _need(type(source) is dict and type(source.get('company_id')) is str,
          'D03_RECORDED_SET_SOURCE_REQUIRED')
    _need(source.get('request_context_format') == FORMAT_VERSION,
          'D03_RECORDED_SET_MEASURED_GROUPING_REQUIRED')
    rebuilt = prepare_regulatory_semantic_source(repo_root=ROOT,
        company_id=source['company_id'],
        request_context_format=source.get('request_context_format'))
    _need(source == rebuilt, 'D03_RECORDED_SET_SAVED_SOURCE_CHANGED')
    requests = requests_from_source(rebuilt)
    _need(bool(requests)
          and len({request['request_id'] for request in requests}) == len(requests)
          and [unit['unit_id'] for request in requests
               for unit in request['units']] == source['required_unit_ids'],
          'D03_RECORDED_SET_REQUEST_CENSUS_CHANGED')
    return requests


def _checked_rows(source, requests, responses):
    from .r6_regulatory_semantics import validate_response
    from .regulatory_fact_review import validate_candidate_response
    ids = [request['request_id'] for request in requests]
    _need(type(responses) is dict and set(responses) == set(ids)
          and all(type(value) is bytes for value in responses.values()),
          'D03_RECORDED_SET_MISSING_EXTRA_OR_NONBYTE_RESPONSE')
    rows = []
    for index, original in enumerate(requests):
        raw = responses[original['request_id']]
        if original['source_statement_facts']:
            checked, effective = validate_candidate_response(
                original_request=original, source=source, raw_response=raw,
                return_authenticated_request=True)
            successor = True
        else:
            effective = original
            checked = validate_response(request=original, raw_response=raw)
            successor = False
        rows.append({'original_request_id': original['request_id'],
            'effective_request_id': effective['request_id'],
            'source_anchor_successor': successor,
            'response_file': 'responses/%04d.bin' % index,
            'response_sha256': sha256_bytes(content=raw),
            'response_size': len(raw),
            'finding_count': len(checked['findings']),
            'unresolved_count': len(checked['unresolved'])})
    return rows


def record_offline_set(*, output_root, source, responses_by_original_id,
                       repo_root=ROOT):
    """Validate and save every raw response, then seal one packet index last."""
    _need(Path(repo_root).resolve() == ROOT,
          'D03_RECORDED_SET_CODE_ROOT_CHANGED')
    root = _root(output_root)
    _need(not root.exists(), 'D03_RECORDED_SET_ROOT_ALREADY_EXISTS')
    _need(type(responses_by_original_id) is dict,
          'D03_RECORDED_SET_MISSING_EXTRA_OR_NONBYTE_RESPONSE')
    source_copy = deepcopy(source)
    responses = dict(responses_by_original_id)
    requests = _requests(source_copy)
    rows = _checked_rows(source_copy, requests, responses)
    _need(source == source_copy and responses_by_original_id == responses,
          'D03_RECORDED_SET_INPUT_MUTATED')
    source_bytes = _json_bytes(source_copy)
    body = {'record_type': 'D03_COMPLETE_OFFLINE_RECORDED_RESPONSE_SET',
        'schema_version': VERSION, 'company_id': source_copy['company_id'],
        'source_id': source_copy['semantic_source_id'],
        'source_sha256': sha256_bytes(content=source_bytes),
        'source_size': len(source_bytes),
        'module_sha256': sha256_file(path=Path(__file__)),
        'rows': rows, 'request_count': len(rows),
        'provider_execution_credit': 'RECORDED_TEST_ONLY',
        'native_result_created': False, 'calls': [0, 0, 0],
        'production_authorized': False}
    packet = {**body, 'packet_id': content_hash(value=body)}
    root.mkdir(parents=True)
    (root/'responses').mkdir()
    write_immutable_bytes(path=root/'source.json', content=source_bytes)
    for row in rows:
        write_immutable_bytes(path=root/row['response_file'],
            content=responses[row['original_request_id']])
    write_immutable_bytes(path=root/'packet.json', content=_json_bytes(packet))
    return {'packet_id': packet['packet_id'], 'request_count': len(rows),
        'unresolved_request_count': sum(row['unresolved_count'] > 0 for row in rows),
        'calls': [0, 0, 0], 'native_result_created': False}


def replay_offline_set(*, packet_root, expected_packet_id, repo_root=ROOT):
    """Cold-read exact files and current source; the caller supplies identity."""
    _need(Path(repo_root).resolve() == ROOT,
          'D03_RECORDED_SET_CODE_ROOT_CHANGED')
    _need(type(expected_packet_id) is str and bool(expected_packet_id),
          'D03_RECORDED_SET_EXTERNAL_EXPECTED_ID_REQUIRED')
    root = _root(packet_root)
    _need(root.is_dir() and {item.name for item in root.iterdir()} ==
          {'packet.json', 'source.json', 'responses'}
          and (root/'responses').is_dir()
          and first_symlink_in_path(path=root/'packet.json') is None,
          'D03_RECORDED_SET_INCOMPLETE_OR_EXTRA_FILE')
    packet = strict_json_file(path=root/'packet.json')
    body = {key: value for key, value in packet.items()
            if key != 'packet_id'}
    _need(packet['packet_id'] == expected_packet_id
          and packet['packet_id'] == content_hash(value=body)
          and packet['record_type'] ==
              'D03_COMPLETE_OFFLINE_RECORDED_RESPONSE_SET'
          and packet['schema_version'] == VERSION
          and packet['module_sha256'] == sha256_file(path=Path(__file__))
          and packet['provider_execution_credit'] == 'RECORDED_TEST_ONLY'
          and packet['native_result_created'] is False
          and packet['calls'] == [0, 0, 0]
          and packet['production_authorized'] is False
          and type(packet['rows']) is list
          and packet['request_count'] == len(packet['rows']),
          'D03_RECORDED_SET_IDENTITY_OR_CREDIT_CHANGED')
    names = {row['response_file'] for row in packet['rows']}
    _need(len(names) == len(packet['rows'])
          and names == {'responses/%04d.bin' % i
                        for i in range(len(packet['rows']))}
          and {item.name for item in (root/'responses').iterdir()} ==
              {name.split('/')[1] for name in names},
          'D03_RECORDED_SET_RESPONSE_CENSUS_CHANGED')
    source_path = root/'source.json'
    _need(first_symlink_in_path(path=source_path) is None,
          'D03_RECORDED_SET_FILE_CHANGED')
    source_bytes = source_path.read_bytes()
    _need(len(source_bytes) == packet['source_size']
          and sha256_bytes(content=source_bytes) == packet['source_sha256'],
          'D03_RECORDED_SET_FILE_CHANGED')
    source = strict_json_loads(text=source_bytes.decode('utf-8'))
    _need(source['semantic_source_id'] == packet['source_id']
          and source['company_id'] == packet['company_id']
          and _json_bytes(source) == source_bytes,
          'D03_RECORDED_SET_SOURCE_IDENTITY_CHANGED')
    requests = _requests(source)
    responses = {}
    for row in packet['rows']:
        path = root/row['response_file']
        _need(first_symlink_in_path(path=path) is None,
              'D03_RECORDED_SET_FILE_CHANGED')
        raw = path.read_bytes()
        _need(len(raw) == row['response_size']
              and sha256_bytes(content=raw) == row['response_sha256'],
              'D03_RECORDED_SET_FILE_CHANGED')
        responses[row['original_request_id']] = raw
    checked = _checked_rows(source, requests, responses)
    _need(checked == packet['rows'], 'D03_RECORDED_SET_REPLAY_CHANGED')
    return {'packet_id': packet['packet_id'],
        'request_count': len(checked),
        'unresolved_request_count': sum(row['unresolved_count'] > 0
                                        for row in checked),
        'raw_response_bytes': responses,
        'calls': [0, 0, 0], 'native_result_created': False}
