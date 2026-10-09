"""Company SecureGPT SDK edge: text messages, optional bootstrap, one request.

Purpose:
    Hold the only repository code that touches the corporate ``SecureGPT``
    SDK, so the connectivity probe and the later internal-mode transport
    (Issue #28 N1) send and read the same thing. Standard library only; the
    SDK, its configuration and credentials come from the corporate runtime and
    are imported lazily, never at module import time.

Call relationships:
    ``tools/probe_securegpt.py`` is the current caller. N1 is expected to call
    ``send``/``assistant_content`` from inside the existing provider boundary
    and WB-3 ledger; that transport is not implemented here.

Limits:
    One ``send`` is one ``SecureGPT.request`` call: no retry, no fallback to
    another provider, no guessed model/max_tokens/timeout/response_format
    fields. Whether the SDK retries internally is not known from this
    repository, so one call is not a claim of exactly one remote charge.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

ENVIRONMENTS = ('dev', 'pp', 'prod')
_ENVELOPE_KEYS = {'choices', 'output_text', 'text', 'content', 'error', 'errors', 'status_code'}


class SecureGPTResponseError(ValueError):
    """A returned SDK value is not a usable assistant answer."""


def securegpt_messages(messages: Any) -> list:
    """Convert OpenAI-style text messages to the SDK's text-part content.

    String content becomes ``[{"type": "text", "text": ...}]``; text parts
    pass through. Any other part (image, file, tool call) is rejected rather
    than silently dropped.
    """
    if not isinstance(messages, list) or not messages:
        raise ValueError('MESSAGES_EMPTY_OR_NOT_LIST')
    converted = []
    for message in messages:
        if (not isinstance(message, dict) or set(message) != {'role', 'content'}
                or not isinstance(message['role'], str) or not message['role']):
            raise ValueError('MESSAGE_SHAPE_UNSUPPORTED')
        content = message['content']
        if isinstance(content, str):
            parts = [{'type': 'text', 'text': content}]
        elif isinstance(content, list) and content and all(
                isinstance(part, dict) and set(part) == {'type', 'text'}
                and part['type'] == 'text' and isinstance(part['text'], str)
                for part in content):
            parts = [dict(part) for part in content]
        else:
            raise ValueError('MESSAGE_CONTENT_NOT_TEXT')
        converted.append({'role': message['role'], 'content': parts})
    return converted


def bootstrap(*, env: str, workspace_url: str, config_file: str) -> None:
    """Run the company initialization order supplied by the user.

    ``get_main_config`` -> ``load_config`` -> workspace/env check ->
    ``set_env_vars``. The workspace address is an input, never a repository
    literal; no Spark/dbutils object is created or faked here.
    """
    if env not in ENVIRONMENTS:
        raise ValueError('SECUREGPT_ENV_UNSUPPORTED')
    workspace = workspace_url.strip()
    for scheme in ('https://', 'http://'):
        if workspace.startswith(scheme):
            workspace = workspace[len(scheme):]
    workspace = workspace.rstrip('/')
    if not workspace:
        raise ValueError('SECUREGPT_WORKSPACE_REQUIRED')
    from config import get_main_config
    get_main_config(config_file, env, True)
    from utils.config_utils import load_config
    mapping = load_config(config='general', field='workspace').get('environment', {})
    if mapping.get(workspace) != env:
        raise ValueError('SECUREGPT_WORKSPACE_ENV_MISMATCH')
    from utils.setup_utils import set_env_vars
    set_env_vars(workspace, env)


def initialize_adls() -> None:
    """Optionally reproduce the company ADLS client side effects."""
    from data_io.adls.adls_connect import ADLSConnect
    ADLSConnect(logging.getLogger(__name__), 'adls')


def open_client(*, env: str) -> Any:
    """Construct ``SecureGPT(env)`` from the corporate runtime (lazy import)."""
    if env not in ENVIRONMENTS:
        raise ValueError('SECUREGPT_ENV_UNSUPPORTED')
    from utils.secure_gpt import SecureGPT
    return SecureGPT(env)


def send(*, client: Any, messages: Any) -> Any:
    """Issue exactly one ``client.request`` with the demonstrated payload."""
    return client.request({'messages': securegpt_messages(messages)})


def normalize_response(raw: Any) -> Any:
    """Return a JSON-compatible view of the SDK return value.

    This is the SDK's returned object, not an HTTP wire capture. A response
    object with a failing HTTP status raises; a non-JSON body falls back to
    its text so the one paid answer can still be saved and re-read offline.
    """
    if isinstance(raw, bytes):
        return raw.decode('utf-8')
    if raw is None or isinstance(raw, (str, dict, list, int, float, bool)):
        return raw
    if callable(getattr(raw, 'raise_for_status', None)):
        raw.raise_for_status()
    if callable(getattr(raw, 'model_dump', None)):
        return raw.model_dump(mode='json')
    if callable(getattr(raw, 'json', None)):
        try:
            return raw.json()
        except ValueError:
            if isinstance(getattr(raw, 'text', None), str):
                return raw.text
            raise
    raise TypeError('SDK_RETURN_TYPE_UNSUPPORTED: ' + type(raw).__name__)


def _text_value(value: Any) -> str:
    if isinstance(value, str) and value.strip():
        return value
    if isinstance(value, list) and value and all(
            isinstance(part, dict) and part.get('type') in {'text', 'output_text'}
            and isinstance(part.get('text'), str) for part in value):
        text = ''.join(part['text'] for part in value)
        if text.strip():
            return text
    raise SecureGPTResponseError('ASSISTANT_TEXT_NOT_FOUND: inspect the saved response; use --text-path')


def assistant_content(raw: Any, *, text_path: Optional[str] = None) -> Any:
    """Read only explicit assistant fields; never search error bodies.

    Supported without ``text_path``: a plain string, ``choices[0].message``
    (finish_reason stop/end_turn or absent, no refusal), and top-level
    ``output_text``/``text``/``content``. ``text_path`` is a dotted path such
    as ``data.answer`` or ``choices.0.message.content`` for other shapes.
    """
    if isinstance(raw, str):
        try:
            decoded = json.loads(raw)
        except ValueError:
            return _text_value(raw)
        # A returned string is either a JSON envelope or the answer itself,
        # which may legitimately be JSON (e.g. a structured extraction).
        if not text_path and not (isinstance(decoded, dict) and _ENVELOPE_KEYS & set(decoded)):
            return _text_value(raw)
        raw = decoded
    if isinstance(raw, dict):
        if raw.get('error') or raw.get('errors'):
            raise SecureGPTResponseError('SDK_ERROR_RESPONSE')
        if isinstance(raw.get('status_code'), int) and raw['status_code'] >= 400:
            raise SecureGPTResponseError('SDK_HTTP_ERROR_RESPONSE')
    if text_path:
        value = raw
        for part in text_path.split('.'):
            value = value[int(part)] if isinstance(value, list) else value[part]
        return value if isinstance(value, dict) else _text_value(value)
    if isinstance(raw, dict):
        if raw.get('choices'):
            choice = raw['choices'][0]
            if choice.get('finish_reason') not in {None, 'stop', 'end_turn'}:
                raise SecureGPTResponseError('INCOMPLETE_OR_FILTERED_RESPONSE')
            message = choice['message']
            if message.get('role') not in {None, 'assistant'} or message.get('refusal'):
                raise SecureGPTResponseError('NOT_AN_ASSISTANT_ANSWER')
            return _text_value(message.get('content'))
        for key in ('output_text', 'text', 'content'):
            if key in raw:
                return _text_value(raw[key])
    return _text_value(raw)
