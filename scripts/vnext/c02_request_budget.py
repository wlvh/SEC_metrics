"""Keep a C02 development request's textual and envelope budgets consistent.

This only prepares new bytes. It never calls a model, changes a saved request,
trims source/answers or supplies business acceptance. Default bytes are retained.
"""
import json
import re

from .continuous_request_context import with_request_limits
from .request_limits import configured_limits

_TASK_LIMIT = re.compile(r'complete JSON within [0-9]+ output tokens')


def c02_request_limits(limits=None):
    """Check the received development ceiling before preparing any source."""
    limits = configured_limits(limits)
    if (limits.output_tokens > 8192 or limits.max_context_tokens > 200000
            or limits.max_payload_bytes > 8 * 1024 * 1024):
        raise ValueError('C02_OUTPUT_BUDGET_RESOURCE_CEILING_EXCEEDED')
    return limits


def with_c02_output_budget(request_body, *, limits=None):
    limits = c02_request_limits(limits)
    wire = with_request_limits(request_body, limits=limits)
    body = json.loads(wire)
    prompt = body['messages'][0]['content']
    changed, count = _TASK_LIMIT.subn(
        f'complete JSON within {limits.output_tokens} output tokens', prompt)
    if count > 1:
        raise ValueError('C02_OUTPUT_BUDGET_MULTIPLE_TEXTUAL_LIMITS')
    # Some request templates state no separate textual limit. The envelope
    # alone then owns that limit; do not insert invented task instructions.
    if changed == prompt:
        return wire
    body['messages'][0]['content'] = changed
    return json.dumps(body, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')
