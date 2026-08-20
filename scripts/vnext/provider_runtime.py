"""Load repository-bound provider context and billing observability policy.

The loader maps the effective D-01 provider/model/API tuple to one versioned
context authority and deterministic estimator. Invocation planning consumes
the returned data; this module never opens a provider socket or enforces a
monetary budget.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Mapping

from .canonical import parse_utc_timestamp, sha256_bytes, strict_json_file


ROOT_FIELDS = {"models", "schema_version"}
MODEL_FIELDS = {
    "api",
    "billing_class",
    "context_authority_checked_at_utc",
    "context_authority_url",
    "estimator_id",
    "estimator_method",
    "estimator_version",
    "maximum_context_tokens",
    "model",
    "paid_call_observation_source",
    "provider",
}
ESTIMATOR_METHOD = "UTF8_BYTE_UPPER_BOUND"
BILLING_CLASS = "PAID_MODEL_ENDPOINT"
PAID_CALL_OBSERVATION_SOURCE = (
    "PROVIDER_POLICY_BILLING_CLASS_X_EGRESS_MARKER"
)


class ProviderRuntimeError(ValueError):
    """Report malformed or missing provider runtime authority."""


def _required_text(*, value: object, label: str) -> str:
    """Return one required non-empty text value."""
    if not isinstance(value, str) or not value:
        raise ProviderRuntimeError("{} must be non-empty text".format(label))
    return value


def load_provider_runtime_authority(
    *, repo_root: Path, provider: str, model: str, api: str,
) -> Dict[str, object]:
    """Load one exact provider/model context and paid-endpoint policy.

    Args:
        repo_root: Repository containing the versioned runtime authority.
        provider: Effective D-01 provider identity.
        model: Effective D-01 model identity.
        api: Effective D-01 API identity.

    Returns:
        Exact authority fields plus the complete file SHA-256 identity.
    """
    path = repo_root / "config" / "provider_model_runtime.json"
    if path.is_symlink() or not path.is_file():
        raise ProviderRuntimeError("Provider runtime authority is unsafe")
    raw = path.read_bytes()
    value = strict_json_file(path=path)
    if (
        not isinstance(value, dict)
        or set(value) != ROOT_FIELDS
        or value["schema_version"] != 1
        or not isinstance(value["models"], list)
    ):
        raise ProviderRuntimeError(
            "Provider runtime authority root is invalid"
        )
    matches = []
    for entry_value in value["models"]:
        if (
            not isinstance(entry_value, dict)
            or set(entry_value) != MODEL_FIELDS
        ):
            raise ProviderRuntimeError("Provider runtime model fields differ")
        entry = dict(entry_value)
        for field in MODEL_FIELDS - {"maximum_context_tokens"}:
            _required_text(value=entry[field], label=field)
        if (
            type(entry["maximum_context_tokens"]) is not int
            or entry["maximum_context_tokens"] <= 0
        ):
            raise ProviderRuntimeError("Provider context limit is invalid")
        try:
            parse_utc_timestamp(
                value=str(entry["context_authority_checked_at_utc"])
            )
        except ValueError as error:
            raise ProviderRuntimeError(
                "Provider context authority timestamp is invalid"
            ) from error
        if (
            entry["estimator_method"] != ESTIMATOR_METHOD
            or entry["billing_class"] != BILLING_CLASS
            or entry["paid_call_observation_source"]
            != PAID_CALL_OBSERVATION_SOURCE
        ):
            raise ProviderRuntimeError("Provider runtime semantics differ")
        if (
            entry["provider"] == provider
            and entry["model"] == model
            and entry["api"] == api
        ):
            matches.append(entry)
    if len(matches) != 1:
        raise ProviderRuntimeError(
            "Provider runtime tuple is absent or ambiguous"
        )
    return {
        **matches[0],
        "context_authority_hash": "sha256:" + sha256_bytes(content=raw),
    }


def estimate_context_tokens(
    *, request_body: bytes, authority: Mapping[str, object],
) -> int:
    """Return a conservative UTF-8-byte upper bound, never an exact count.

    Args:
        request_body: Exact serialized provider envelope bytes.
        authority: Validated provider runtime authority.

    Returns:
        A deterministic upper bound where each UTF-8 byte may consume at most
        one model token; provider framing is already inside the envelope.
    """
    if not isinstance(request_body, bytes) or not request_body:
        raise ProviderRuntimeError("Provider request body must be bytes")
    if (
        not isinstance(authority, Mapping)
        or "estimator_method" not in authority
        or authority["estimator_method"] != ESTIMATOR_METHOD
    ):
        raise ProviderRuntimeError("Provider context estimator is invalid")
    return len(request_body)
