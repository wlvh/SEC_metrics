"""Save and cold-read a D03 successor response without execution credit.

This packet is an offline development record. It does not open a provider,
enroll a real response, create Evidence/Result/Run, or authorize D03 calls.
"""
import json
from copy import deepcopy
from pathlib import Path

from git_workspace import first_symlink_in_path
from sec_http import write_immutable_bytes

from .canonical import content_hash, sha256_bytes, sha256_file, strict_json_file
from .normal_source_authority import ROOT
from .regulatory_fact_review import validate_candidate_response


_FILES = ('source.json', 'original-request.json', 'candidate-request.json',
          'raw-response.bin', 'checked.json')
# The first version-1 offline packet keeps its original creator identity.
# This read-only compatibility does not grant provider or native Run credit.
_HISTORICAL_V1_MODULE_SHA256 = '89e46c2bf900ff14935969a784efeac6786cea4a88ce89e1659b51c54eac0785'


def _need(condition, reason):
    if not condition:
        raise ValueError(reason)


def _json_bytes(value):
    # Original source strings and the received response remain distinguishable
    # even when semantic canonicalization would normalize their characters.
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(',', ':')) + '\n').encode('utf-8')


def _root(path):
    path = Path(path)
    _need(path.is_absolute() and first_symlink_in_path(path=path) is None,
          'D03_RECORDED_PACKET_ROOT_ALIAS_OR_RELATIVE')
    path = path.resolve()
    live_root = Path(strict_json_file(path=ROOT/
        'config/issue28_continuous_calls_v1.json')['budget_root']).resolve()
    _need(path != live_root and live_root not in path.parents,
          'D03_RECORDED_PACKET_LIVE_LEDGER_FORBIDDEN')
    _need(path != ROOT and ROOT not in path.parents
          and not any((parent/'outputs/active_publication.json').exists()
                      for parent in (path, *path.parents)),
          'D03_RECORDED_PACKET_OUTSIDE_CODE_AND_PUBLICATION_REQUIRED')
    return path


def record_offline_response(*, output_root, source, original_request,
                            raw_response, repo_root=ROOT):
    """Persist exact recorded bytes only after the existing semantic checks."""
    _need(Path(repo_root).resolve() == ROOT and type(raw_response) is bytes,
          'D03_RECORDED_PACKET_INPUT_OR_CODE_ROOT_INVALID')
    root = _root(output_root)
    _need(not root.exists(), 'D03_RECORDED_PACKET_ROOT_ALREADY_EXISTS')
    # One immutable in-operation input is authenticated once. Cold replay
    # separately re-authenticates against current saved source bytes.
    source_copy = deepcopy(source)
    original_copy = deepcopy(original_request)
    checked, request = validate_candidate_response(original_request=original_copy,
        source=source_copy, raw_response=raw_response, repo_root=ROOT,
        return_authenticated_request=True)
    _need(source == source_copy and original_request == original_copy,
          'D03_RECORDED_PACKET_INPUT_MUTATED')
    _need(checked['provider_response_raw_sha256'] ==
          sha256_bytes(content=raw_response)
          and checked['raw_provider_response_preserved_separately'] is False
          and checked['native_result_created'] is False,
          'D03_RECORDED_PACKET_UNSUPPORTED_CREDIT')
    payloads = {
        'source.json': _json_bytes(source_copy),
        'original-request.json': _json_bytes(original_copy),
        'candidate-request.json': _json_bytes(request),
        'raw-response.bin': raw_response,
        'checked.json': _json_bytes(checked),
    }
    root.mkdir(parents=True)
    for name in _FILES:
        write_immutable_bytes(path=root/name, content=payloads[name])
    body = {'record_type': 'D03_OFFLINE_RECORDED_RESPONSE_PACKET',
        'schema_version': 1, 'source_id': source_copy['semantic_source_id'],
        'original_request_id': original_copy['request_id'],
        'candidate_request_id': request['request_id'],
        'response_raw_sha256': sha256_bytes(content=raw_response),
        'module_sha256': sha256_file(path=Path(__file__)),
        'files': {name: {'sha256': sha256_bytes(content=payloads[name]),
                         'size': len(payloads[name])} for name in _FILES},
        'provider_execution_credit': 'RECORDED_TEST_ONLY',
        'native_result_created': False, 'calls': [0, 0, 0],
        'production_authorized': False}
    packet = {**body, 'packet_id': content_hash(value=body)}
    write_immutable_bytes(path=root/'packet.json', content=_json_bytes(packet))
    return {'packet_id': packet['packet_id'],
            'response_raw_sha256': packet['response_raw_sha256'],
            'checked': checked, 'native_result_created': False,
            'calls': [0, 0, 0], 'production_authorized': False}


def replay_offline_response(*, packet_root, repo_root=ROOT):
    """Rebuild the source and response checks before returning any review data."""
    _need(Path(repo_root).resolve() == ROOT,
          'D03_RECORDED_PACKET_CODE_ROOT_CHANGED')
    root = _root(packet_root)
    _need(root.is_dir() and {item.name for item in root.iterdir()} ==
          {*_FILES, 'packet.json'},
          'D03_RECORDED_PACKET_INCOMPLETE_OR_EXTRA_FILE')
    packet = strict_json_file(path=root/'packet.json')
    body = {key: value for key, value in packet.items() if key != 'packet_id'}
    _need(packet['packet_id'] == content_hash(value=body)
          and packet['record_type'] == 'D03_OFFLINE_RECORDED_RESPONSE_PACKET'
          and packet['schema_version'] == 1
          and packet['module_sha256'] in {
              sha256_file(path=Path(__file__)), _HISTORICAL_V1_MODULE_SHA256}
          and packet['provider_execution_credit'] == 'RECORDED_TEST_ONLY'
          and packet['native_result_created'] is False
          and packet['calls'] == [0, 0, 0]
          and packet['production_authorized'] is False
          and set(packet['files']) == set(_FILES),
          'D03_RECORDED_PACKET_IDENTITY_OR_CREDIT_CHANGED')
    for name in _FILES:
        path = root/name
        _need(first_symlink_in_path(path=path) is None
              and path.stat().st_size == packet['files'][name]['size']
              and sha256_file(path=path) == packet['files'][name]['sha256'],
              'D03_RECORDED_PACKET_FILE_CHANGED')
    source = strict_json_file(path=root/'source.json')
    original = strict_json_file(path=root/'original-request.json')
    request = strict_json_file(path=root/'candidate-request.json')
    raw = (root/'raw-response.bin').read_bytes()
    saved_checked = strict_json_file(path=root/'checked.json')
    _need(source['semantic_source_id'] == packet['source_id']
          and original['request_id'] == packet['original_request_id']
          and request['request_id'] == packet['candidate_request_id']
          and sha256_bytes(content=raw) == packet['response_raw_sha256'],
          'D03_RECORDED_PACKET_SOURCE_OR_RESPONSE_CHANGED')
    checked, rebuilt = validate_candidate_response(original_request=original,
        source=source, raw_response=raw, repo_root=ROOT,
        return_authenticated_request=True)
    _need(rebuilt == request, 'D03_RECORDED_PACKET_REQUEST_CHANGED')
    _need(checked == saved_checked
          and checked['provider_response_raw_sha256'] ==
              packet['response_raw_sha256'],
          'D03_RECORDED_PACKET_REPLAY_CHANGED')
    return {'packet_id': packet['packet_id'],
        'response_raw_sha256': packet['response_raw_sha256'],
        'checked': checked, 'raw_response_bytes': raw,
        'native_result_created': False, 'calls': [0, 0, 0],
        'production_authorized': False}
