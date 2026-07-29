"""Strict JSON, canonical collection, Decimal, and runtime hash tests."""

from __future__ import annotations

import unittest
from decimal import Decimal, getcontext

from vnext.canonical import (
    CanonicalError,
    arithmetic_context,
    canonical_json_bytes,
    content_hash,
    decimal_text,
    execution_semantics_hash,
    parse_decimal,
    parse_utc_timestamp,
    strict_json_loads,
)


class CanonicalHashTest(unittest.TestCase):
    """Exercise every canonicalization fail-closed boundary."""

    def test_strict_json_rejects_ambiguous_extensions(self) -> None:
        """Reject duplicates, non-finite values, unknowns, and surrogates."""
        for text in (
            '{"a":1,"a":2}',
            '{"a":NaN}',
            '{"a":Infinity}',
            '{"a":1e3}',
            '{"a":' + "9" * 129 + "}",
            '"\\ud800"',
        ):
            with self.subTest(text=text), self.assertRaises(CanonicalError):
                strict_json_loads(text=text)
        with self.assertRaises(CanonicalError):
            strict_json_loads(text='{"a":1,"b":2}', allowed_fields={"a"})

    def test_ordered_and_set_collections_have_distinct_contracts(self) -> None:
        """Preserve arrays and canonicalize declared mathematical sets."""
        self.assertNotEqual(
            content_hash(value={"items": ["a", "b"]}),
            content_hash(value={"items": ["b", "a"]}),
        )
        set_paths = frozenset({("items",)})
        self.assertEqual(
            content_hash(value={"items": ["a", "b"]}, set_paths=set_paths),
            content_hash(value={"items": ["b", "a"]}, set_paths=set_paths),
        )
        with self.assertRaises(CanonicalError):
            canonical_json_bytes(
                value={"items": ["a", "a"]}, set_paths=set_paths,
            )

    def test_unicode_decimal_and_missing_are_distinct(self) -> None:
        """Normalize NFC/-0/trailing zeros without conflating missing/null."""
        self.assertEqual(
            content_hash(value={"text": "e\u0301"}),
            content_hash(value={"text": "\u00e9"}),
        )
        self.assertEqual(
            "0", decimal_text(value=parse_decimal(value="-0.000"))
        )
        self.assertEqual(
            "1.23", decimal_text(value=parse_decimal(value="1.2300"))
        )
        self.assertNotEqual(
            content_hash(value={}), content_hash(value={"a": None})
        )
        with self.assertRaises(CanonicalError):
            parse_decimal(value="1e3")
        with self.assertRaises(CanonicalError):
            parse_decimal(value="1." + "0" * 65)

    def test_decimal_context_and_runtime_versions_are_explicit(self) -> None:
        """Ignore external Decimal context and bind semantic versions."""
        previous = getcontext().prec
        try:
            getcontext().prec = 3
            with arithmetic_context():
                value = Decimal("1") / Decimal("7")
            self.assertEqual(
                "0.1428571428571428571428571429", decimal_text(value=value)
            )
        finally:
            getcontext().prec = previous
        changed = {
            "calculator_semantic_version": "3",
            "canonicalizer_semantic_version": "1",
            "projector_semantic_version": "1",
            "review_renderer_semantic_version": "1",
            "spec_interpreter_semantic_version": "1",
        }
        self.assertNotEqual(
            execution_semantics_hash(),
            execution_semantics_hash(versions=changed),
        )

    def test_utc_timestamp_format_is_cross_interpreter_stable(self) -> None:
        """Reject newer-only ISO forms while preserving exact UTC forms."""
        for value in (
            "2026-07-29T13:00:00Z",
            "2026-07-29T13:00:00.123456+00:00",
        ):
            parse_utc_timestamp(value=value)
        for value in (
            "20260729T130000+00:00",
            "2026-W31-3T13:00:00+00:00",
        ):
            with self.subTest(value=value), self.assertRaises(CanonicalError):
                parse_utc_timestamp(value=value)


if __name__ == "__main__":
    unittest.main()
