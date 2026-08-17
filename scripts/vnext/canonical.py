"""Implement strict canonical JSON, Decimal policy, hashes, and atomic files.

Callers parse untrusted JSON with :func:`strict_json_loads`, normalize semantic
objects with :func:`canonical_json_bytes`, and bind execution behavior with
:func:`execution_semantics_hash`. Publication and Run modules reuse the atomic
file helpers so authoritative writes share one fail-closed implementation.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Context, Decimal, ROUND_HALF_EVEN, localcontext
from pathlib import Path
from typing import Dict, FrozenSet, Iterator, List, Mapping, Optional, Sequence
from typing import Set, Tuple, Union


CanonicalScalar = Union[None, bool, int, str]
CanonicalValue = Union[
    CanonicalScalar, List["CanonicalValue"], Dict[str, "CanonicalValue"]
]
SetPath = Tuple[str, ...]
DECIMAL_PATTERN = re.compile(r"^-?[0-9]+(?:\.[0-9]+)?$")
UTC_TIMESTAMP_PATTERN = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T"
    r"[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{1,6})?(?:Z|\+00:00)$"
)
SEMANTIC_VERSIONS = {
    "calculator_semantic_version": "5",
    "canonicalizer_semantic_version": "4",
    "projector_semantic_version": "3",
    "review_renderer_semantic_version": "3",
    "spec_interpreter_semantic_version": "2",
}


class CanonicalError(ValueError):
    """Report non-canonical, ambiguous, or unsupported semantic input."""


def _reject_constant(*, value: str) -> None:
    """Reject JSON constants that Python otherwise accepts as extensions.

    Args:
        value: Parser token such as ``NaN`` or ``Infinity``.

    Raises:
        CanonicalError: Always, because non-finite values have no contract
            identity.
    """
    raise CanonicalError(
        "Non-finite JSON number is forbidden: {}".format(value)
    )


def _pairs_to_object(
    *, pairs: Sequence[Tuple[str, object]]
) -> Dict[str, object]:
    """Build one JSON object while rejecting duplicate source keys.

    Args:
        pairs: Ordered key/value pairs emitted by ``json.loads``.

    Returns:
        A plain dictionary whose keys were unique in the source bytes.

    Raises:
        CanonicalError: When a source object repeats a key.
    """
    output: Dict[str, object] = {}
    for key, value in pairs:
        if key in output:
            raise CanonicalError("Duplicate JSON key: {}".format(key))
        output[key] = value
    return output


def _parse_json_decimal(*, value: str) -> Decimal:
    """Parse one JSON fractional token through the fixed-point policy.

    Args:
        value: Exact JSON number token.

    Returns:
        Bounded fixed-point Decimal.

    Raises:
        CanonicalError: On exponent notation or Decimal policy overflow.
    """
    return parse_decimal(value=value)


def _parse_json_integer(*, value: str) -> int:
    """Parse one JSON integer after applying the shared digit bound.

    Args:
        value: Exact JSON integer token.

    Returns:
        Bounded Python integer.
    """
    parse_decimal(value=value)
    return int(value)


def _validate_unicode(*, value: str) -> str:
    """Return NFC semantic text after rejecting lone surrogate code points.

    Args:
        value: Semantic string or object key.

    Returns:
        NFC-normalized text.

    Raises:
        CanonicalError: When UTF-8 cannot represent the value.
    """
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise CanonicalError("Lone surrogate is forbidden") from error
    return unicodedata.normalize("NFC", value)


def _validate_tree_unicode(*, value: object) -> None:
    """Reject lone surrogates anywhere in a parsed JSON tree.

    Args:
        value: Parsed JSON value.

    Expected output:
        The function returns normally only when every key and string is valid
        UTF-8 semantic text.
    """
    if isinstance(value, str):
        _validate_unicode(value=value)
        return
    if isinstance(value, list):
        for item in value:
            _validate_tree_unicode(value=item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _validate_unicode(value=key)
            _validate_tree_unicode(value=item)


def strict_json_loads(
    *, text: str, allowed_fields: Optional[Set[str]] = None
) -> object:
    """Parse strict JSON and optionally enforce an exact root-field set.

    Args:
        text: UTF-8-decoded JSON text.
        allowed_fields: Exact allowed root keys, or ``None`` when the caller
            validates a non-object or owns a deeper schema.

    Returns:
        Parsed JSON with fractional numbers represented as ``Decimal``.

    Raises:
        CanonicalError: On duplicate keys, non-finite numbers, lone
            surrogates, invalid JSON, a non-object constrained root, or an
            unknown root field.
    """
    try:
        value = json.loads(
            text,
            object_pairs_hook=lambda pairs: _pairs_to_object(pairs=pairs),
            parse_float=lambda token: _parse_json_decimal(value=token),
            parse_int=lambda token: _parse_json_integer(value=token),
            parse_constant=lambda token: _reject_constant(value=token),
        )
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise CanonicalError("Invalid strict JSON") from error
    _validate_tree_unicode(value=value)
    if allowed_fields is not None:
        if not isinstance(value, dict):
            raise CanonicalError("Constrained JSON root must be an object")
        unknown = sorted(set(value) - allowed_fields)
        if unknown:
            raise CanonicalError(
                "Unknown JSON fields: {}".format(",".join(unknown))
            )
    return value


def strict_json_file(
    *, path: Path, allowed_fields: Optional[Set[str]] = None
) -> object:
    """Read one regular UTF-8 file through the strict JSON boundary.

    Args:
        path: Input JSON path.
        allowed_fields: Optional exact root field set.

    Returns:
        Strict parsed JSON.

    Raises:
        CanonicalError: When the path is not a regular non-symlink file or its
            bytes are not valid UTF-8 strict JSON.
    """
    if path.is_symlink() or not path.is_file():
        raise CanonicalError(
            "JSON input must be a regular file: {}".format(path)
        )
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise CanonicalError(
            "JSON input must be UTF-8: {}".format(path)
        ) from error
    return strict_json_loads(text=text, allowed_fields=allowed_fields)


def parse_decimal(*, value: str) -> Decimal:
    """Parse a bounded fixed-point Decimal without exponent notation.

    Args:
        value: Signed fixed-point decimal text with at most 128 significant
            digits and at most 64 fractional digits.

    Returns:
        A finite ``Decimal``; negative zero remains numeric zero and is
        canonicalized during serialization.

    Raises:
        CanonicalError: On exponent notation, non-finite input, excessive
            precision, or excessive scale.
    """
    if DECIMAL_PATTERN.fullmatch(value) is None:
        raise CanonicalError(
            "Decimal must use fixed-point notation: {}".format(value)
        )
    unsigned = value[1:] if value.startswith("-") else value
    parts = unsigned.split(".")
    digits = "".join(parts).lstrip("0")
    significant_digits = len(digits) if digits else 1
    scale = len(parts[1]) if len(parts) == 2 else 0
    if significant_digits > 128:
        raise CanonicalError("Decimal exceeds 128 significant digits")
    if scale > 64:
        raise CanonicalError("Decimal scale exceeds 64")
    parsed = Decimal(value)
    if not parsed.is_finite():
        raise CanonicalError("Decimal must be finite")
    return parsed


def parse_utc_timestamp(*, value: str) -> datetime:
    """Parse one timezone-aware UTC ISO-8601 timestamp.

    Args:
        value: Text using ``Z`` or an explicit zero offset.

    Returns:
        Parsed UTC datetime.

    Raises:
        CanonicalError: When the text is invalid, naive, or non-UTC.
    """
    if type(value) is not str:
        raise CanonicalError("UTC timestamp must be text")
    if UTC_TIMESTAMP_PATTERN.fullmatch(value) is None:
        raise CanonicalError(
            "UTC timestamp must use extended date/time fields"
        )
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise CanonicalError("UTC timestamp is not ISO-8601") from error
    if (
        parsed.tzinfo is None
        or parsed.utcoffset() != timezone.utc.utcoffset(None)
    ):
        raise CanonicalError("Timestamp must use UTC")
    return parsed


def decimal_text(*, value: Decimal) -> str:
    """Serialize a finite Decimal as normalized fixed-point text.

    Args:
        value: Decimal result to serialize.

    Returns:
        Fixed-point text with no exponent or insignificant trailing zeros;
        every signed zero becomes ``0``.

    Raises:
        CanonicalError: When the Decimal is non-finite.
    """
    if not value.is_finite():
        raise CanonicalError("Decimal must be finite")
    if value == 0:
        return "0"
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


@contextmanager
def arithmetic_context() -> Iterator[Context]:
    """Yield the explicit contract Decimal context.

    Returns:
        Context with precision 28 and ``ROUND_HALF_EVEN``. The global Decimal
        context is never mutated.
    """
    contract = Context(prec=28, rounding=ROUND_HALF_EVEN)
    with localcontext(contract) as active:
        yield active


def _canonicalize(
    *, value: object, path: SetPath, set_paths: FrozenSet[SetPath]
) -> CanonicalValue:
    """Normalize one semantic value using explicit collection semantics.

    Args:
        value: Supported JSON-like value, optionally containing ``Decimal``.
        path: Current semantic field path.
        set_paths: Paths whose arrays have mathematical set semantics.

    Returns:
        JSON-serializable canonical value.

    Raises:
        CanonicalError: On floats, unsupported types, duplicate normalized
            keys, or duplicate set members.
    """
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, Decimal):
        return decimal_text(value=value)
    if isinstance(value, float):
        raise CanonicalError("Binary float is forbidden; use Decimal")
    if isinstance(value, str):
        return _validate_unicode(value=value)
    if isinstance(value, Mapping):
        output: Dict[str, CanonicalValue] = {}
        for raw_key, item in value.items():
            if not isinstance(raw_key, str):
                raise CanonicalError("Canonical object keys must be strings")
            key = _validate_unicode(value=raw_key)
            if key in output:
                raise CanonicalError(
                    "Duplicate object key after NFC normalization: {}".format(
                        key
                    )
                )
            output[key] = _canonicalize(
                value=item, path=path + (key,), set_paths=set_paths,
            )
        return {key: output[key] for key in sorted(output)}
    if isinstance(value, (list, tuple)):
        items = [
            _canonicalize(value=item, path=path + ("*",), set_paths=set_paths,)
            for item in value
        ]
        if path not in set_paths:
            return items
        encoded = [
            json.dumps(
                item,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            for item in items
        ]
        if len(encoded) != len(set(encoded)):
            raise CanonicalError(
                "Set collection contains duplicate members: {}".format(
                    ".".join(path)
                )
            )
        return [
            item
            for _key, item in sorted(
                zip(encoded, items), key=lambda pair: pair[0]
            )
        ]
    raise CanonicalError(
        "Unsupported canonical type: {}".format(type(value).__name__)
    )


def canonical_json_bytes(
    *, value: object, set_paths: FrozenSet[SetPath] = frozenset()
) -> bytes:
    """Serialize semantic content as deterministic UTF-8 canonical JSON.

    Args:
        value: JSON-like semantic value.
        set_paths: Explicit array paths with set semantics. All other arrays
            preserve order.

    Returns:
        Compact UTF-8 JSON terminated by one LF.
    """
    normalized = _canonicalize(value=value, path=(), set_paths=set_paths)
    text = json.dumps(
        normalized, ensure_ascii=False, separators=(",", ":"), sort_keys=True,
    )
    return (text + "\n").encode("utf-8")


def sha256_bytes(*, content: bytes) -> str:
    """Return the lowercase SHA-256 digest of exact bytes.

    Args:
        content: Bytes to bind.

    Returns:
        Sixty-four lowercase hexadecimal characters.
    """
    return hashlib.sha256(content).hexdigest()


def sha256_file(*, path: Path) -> str:
    """Hash one regular non-symlink file.

    Args:
        path: File whose exact bytes form the identity.

    Returns:
        SHA-256 digest.

    Raises:
        CanonicalError: When the path is not a regular non-symlink file.
    """
    if path.is_symlink() or not path.is_file():
        raise CanonicalError(
            "Hash input must be a regular file: {}".format(path)
        )
    return sha256_bytes(content=path.read_bytes())


def content_hash(
    *, value: object, set_paths: FrozenSet[SetPath] = frozenset()
) -> str:
    """Hash canonical semantic content.

    Args:
        value: Semantic value.
        set_paths: Explicit set-semantics paths.

    Returns:
        ``sha256:<hex>`` content identifier.
    """
    return "sha256:" + sha256_bytes(
        content=canonical_json_bytes(value=value, set_paths=set_paths)
    )


def execution_semantics_hash(
    *, versions: Mapping[str, str] = SEMANTIC_VERSIONS
) -> str:
    """Bind every semantic runtime version into one execution identity.

    Args:
        versions: Exact version mapping. Callers may inject a changed version
            in regression tests.

    Returns:
        Content hash of the complete, exact version mapping.

    Raises:
        CanonicalError: When required version keys are missing or additional
            hidden semantic versions are supplied.
    """
    required = set(SEMANTIC_VERSIONS)
    if set(versions) != required:
        raise CanonicalError("Semantic runtime version keys are not exact")
    for key in sorted(versions):
        if not versions[key]:
            raise CanonicalError(
                "Semantic runtime version is empty: {}".format(key)
            )
    return content_hash(value=dict(versions))


def atomic_write_bytes(*, path: Path, content: bytes) -> None:
    """Atomically replace one regular file and fsync file plus parent.

    Args:
        path: Authoritative destination.
        content: Complete replacement bytes.

    Expected output:
        Either the old file or the complete new bytes are visible. Symlink and
        non-regular destinations fail before replacement.
    """
    if path.exists() and (path.is_symlink() or not path.is_file()):
        raise CanonicalError(
            "Atomic destination is not a regular file: {}".format(path)
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(
        ".{}.{}.tmp".format(path.name, uuid.uuid4().hex)
    )
    try:
        with temporary.open(mode="xb") as file_obj:
            file_obj.write(content)
            file_obj.flush()
            os.fsync(file_obj.fileno())
        os.replace(str(temporary), str(path))
        directory_fd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary.exists():
            temporary.unlink()
    if path.is_symlink() or not path.is_file() or path.read_bytes() != content:
        raise CanonicalError(
            "Atomic-write postcondition failed: {}".format(path)
        )


def atomic_write_json(*, path: Path, value: object) -> None:
    """Atomically write indented UTF-8 JSON with one terminal LF.

    Args:
        path: Authoritative JSON destination.
        value: JSON-serializable value. Decimal values must already be
            converted because this format is human/audit JSON, not canonical
            hash bytes.

    Expected output:
        A complete, readable JSON file or the prior file.
    """
    # Validate with the same semantic boundary used for hashes before writing
    # human-readable JSON; json.dumps otherwise emits NaN/Infinity by default.
    try:
        canonical_json_bytes(value=value)
        serialized = json.dumps(
            value, ensure_ascii=False, indent=2, allow_nan=False,
        )
        content = (serialized + "\n").encode("utf-8")
    except (
        CanonicalError, TypeError, ValueError, UnicodeEncodeError,
    ) as error:
        raise CanonicalError("Atomic JSON value is not strict") from error
    atomic_write_bytes(path=path, content=content)
