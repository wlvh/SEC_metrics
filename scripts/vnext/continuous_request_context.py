"""Count the complete, bounded continuous Chat Completions prompt offline.

This is a pinned reference-format count, not a provider usage receipt. Only
the currently used two-message, non-thinking JSON format is supported. Missing
tokenizer support falls back to the UTF-8 size of that complete rendered
prompt. Nothing here selects a model, grants calls, or enforces money limits.
"""
from functools import lru_cache
import gzip
import json

from .canonical import content_hash, sha256_bytes, strict_json_loads
from .normal_source_authority import ROOT

TOKENIZER_PATH = 'config/tokenizers/deepseek_v41/tokenizer.json.gz'
TOKENIZER_SHA256 = 'c90dfa01249db1be4245780a052ede752e1361c612ac6d08e2bdada7d599476b'
ARCHIVE_SHA256 = 'd0a53c1a5e7f998a5f42b4f428888da70ed47ad33eb2a8afe32294f39f17ef5a'
UPSTREAM_REVISION = 'dba1be0a40aa45a94ad051997016db3960a90277'
UPSTREAM_FORMAT_SHA256 = '502bdaec8a3fd88ebc24c4721a7038fbe42f2063c664638127056107920035c1'
FORMAT_VERSION = 'deepseek-v41-two-message-json-chat-1'
ENGINE_VERSION = '0.22.2'
MAX_CONTEXT = 200000
MAX_BYTES = 8 * 1024 * 1024
OUTPUT_RESERVE = 4096


def _need(ok, reason):
    if not ok:
        raise ValueError(reason)


def render_prompt(request_body, *, provider, model, api):
    """Render every model-visible byte, including the JSON response hint."""
    _need((provider, model, api) == ('deepseek', 'deepseek-flash', 'chat_completions'),
          'CONTINUOUS_CONTEXT_SERVICE_UNSUPPORTED')
    _need(type(request_body) is bytes and 0 < len(request_body) <= MAX_BYTES,
          'CONTINUOUS_CONTEXT_PAYLOAD_LIMIT')
    body = strict_json_loads(text=request_body.decode('utf-8'))
    _need(type(body) is dict and set(body) == {
        'model', 'messages', 'response_format', 'temperature', 'max_tokens', 'stream', 'thinking'},
        'CONTINUOUS_CONTEXT_FORMAT_UNSUPPORTED')
    _need(body['model'] == model and body['response_format'] == {'type': 'json_object'}
          and type(body['temperature']) is int and body['temperature'] == 0
          and type(body['max_tokens']) is int and body['max_tokens'] == OUTPUT_RESERVE
          and body['stream'] is False and body['thinking'] == {'type': 'disabled'},
          'CONTINUOUS_CONTEXT_PARAMETERS_UNSUPPORTED')
    messages = body['messages']
    _need(type(messages) is list and len(messages) == 2, 'CONTINUOUS_CONTEXT_MESSAGES_UNSUPPORTED')
    for message, role in zip(messages, ('system', 'user')):
        _need(type(message) is dict and set(message) == {'role', 'content'}
              and message['role'] == role and type(message['content']) is str,
              'CONTINUOUS_CONTEXT_MESSAGES_UNSUPPORTED')
        # Special marker handling by the hosted service is not established by
        # the ordinary-text reference. Do not silently undercount such input.
        _need(not any(marker in message['content'] for marker in ('<｜', '<think>', '</think>')),
              'CONTINUOUS_CONTEXT_LITERAL_SPECIAL_TOKEN_UNSUPPORTED')
    hint = ('\n\n## Response Format:\n\nYou MUST strictly adhere to the following schema to reply:\n'
            + json.dumps(body['response_format'], ensure_ascii=False))
    return ('<｜begin▁of▁sentence｜><｜System｜>' + messages[0]['content'] + hint
            + '<｜User｜>' + messages[1]['content'] + '<｜Assistant｜></think>')


def _load_tokenizer():
    try:
        import tokenizers
    except ImportError:
        return None, 'TOKENIZER_DEPENDENCY_UNAVAILABLE'
    if tokenizers.__version__ != ENGINE_VERSION:
        return None, 'TOKENIZER_ENGINE_VERSION_UNSUPPORTED'
    path = ROOT / TOKENIZER_PATH
    _need(path.is_file() and not path.is_symlink(), 'CONTINUOUS_TOKENIZER_FILE_UNSAFE')
    archived = path.read_bytes()
    _need(sha256_bytes(content=archived) == ARCHIVE_SHA256, 'CONTINUOUS_TOKENIZER_ARCHIVE_CHANGED')
    return _decode_tokenizer(archived), None


@lru_cache(maxsize=1)
def _decode_tokenizer(archived):
    """Cache parsing only; every use still verifies the current resource bytes."""
    import tokenizers
    raw = gzip.decompress(archived)
    _need(sha256_bytes(content=raw) == TOKENIZER_SHA256, 'CONTINUOUS_TOKENIZER_BYTES_CHANGED')
    return tokenizers.Tokenizer.from_str(raw.decode('utf-8'))


def measure_request(request_body, *, provider='deepseek', model='deepseek-flash',
                    api='chat_completions', require_reference=False):
    prompt = render_prompt(request_body, provider=provider, model=model, api=api)
    tokenizer, fallback = _load_tokenizer()
    _need(not require_reference or tokenizer is not None,
          'CONTINUOUS_CONTEXT_REFERENCE_REQUIRED:' + str(fallback))
    tokens = (len(tokenizer.encode(prompt, add_special_tokens=False).ids) if tokenizer is not None
              else len(prompt.encode('utf-8')))
    method = 'PINNED_REFERENCE_CHAT_FORMAT' if tokenizer is not None else 'UTF8_RENDERED_PROMPT_UPPER_BOUND'
    identity = {'provider': provider, 'model': model, 'api': api, 'format_version': FORMAT_VERSION,
                'upstream_revision': UPSTREAM_REVISION, 'upstream_format_sha256': UPSTREAM_FORMAT_SHA256,
                'tokenizer_sha256': TOKENIZER_SHA256, 'tokenizer_engine': 'tokenizers',
                'tokenizer_engine_version': ENGINE_VERSION, 'method': method,
                'output_reserve': OUTPUT_RESERVE}
    return {'request_sha256': sha256_bytes(content=request_body), 'request_bytes': len(request_body),
            'rendered_prompt_sha256': sha256_bytes(content=prompt.encode('utf-8')),
            'rendered_prompt_bytes': len(prompt.encode('utf-8')), 'input_tokens': tokens,
            'output_reserve_tokens': OUTPUT_RESERVE, 'context_tokens': tokens + OUTPUT_RESERVE,
            'maximum_context_tokens': MAX_CONTEXT, 'maximum_payload_bytes': MAX_BYTES,
            'fits': tokens + OUTPUT_RESERVE <= MAX_CONTEXT, 'fallback_reason': fallback,
            'context_authority_hash': content_hash(value=identity),
            'estimator_id': 'continuous_bounded_chat_context', 'estimator_version': FORMAT_VERSION,
            'estimator_method': method, 'identity': identity}


def measured_groups(units, request_for_group):
    """Greedy full-envelope grouping; document and source order stay intact.

    The factory must include final source/navigation/prompt/schema/request IDs.
    An oversized indivisible unit fails explicitly; no source text is removed.
    """
    from types import SimpleNamespace
    from .continuous_semantic_calls import request_body
    policy = SimpleNamespace(model='deepseek-flash')
    groups, current = [], []

    def fits(group):
        body = request_body(request_for_group(group), policy)
        if len(body) > MAX_BYTES:
            return False
        return measure_request(body, require_reference=True)['fits']

    for unit in units:
        if current and (unit['document_id'] != current[0]['document_id'] or not fits(current + [unit])):
            groups.append(current)
            current = []
        if not current:
            _need(fits([unit]), 'CONTINUOUS_CONTEXT_SINGLE_SOURCE_UNIT_EXCEEDS_BOUND:' + unit['unit_id'])
        current.append(unit)
    if current:
        groups.append(current)
    _need([u for group in groups for u in group] == units, 'CONTINUOUS_CONTEXT_SOURCE_CENSUS_CHANGED')
    return groups
