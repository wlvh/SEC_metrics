"""Explicit request resource configuration; never business-call authorization."""
from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class RequestLimits:
    output_tokens: int = 4096
    max_context_tokens: int = 200000
    max_payload_bytes: int = 8 * 1024 * 1024

    def __post_init__(self):
        if any(type(v) is not int or v <= 0 for v in asdict(self).values()):
            raise ValueError('REQUEST_LIMITS_REQUIRE_POSITIVE_INTEGERS')
        if self.output_tokens >= self.max_context_tokens:
            raise ValueError('REQUEST_OUTPUT_RESERVE_EXHAUSTS_CONTEXT')

    def as_dict(self):
        return asdict(self)


DEFAULT_LIMITS = RequestLimits()


def configured_limits(value=None):
    if value is None: return DEFAULT_LIMITS
    if type(value) is not RequestLimits: raise ValueError('REQUEST_LIMITS_TYPE_REQUIRED')
    return value
