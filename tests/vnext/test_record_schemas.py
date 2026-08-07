"""Strict top-level record type and JSON publication tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from vnext.canonical import CanonicalError, atomic_write_json, content_hash
from vnext.records import RecordError, validate_record


def recorded_transport_observation(*, request_body_bytes: int) -> dict:
    """Return strict no-egress facts for one recorded fixture request.

    Args:
        request_body_bytes: Exact request payload size.

    Returns:
        AIExtractionAttempt transport-observation mapping.
    """
    return {
        "egress_attempted": False,
        "provider": "recorded",
        "model": "recorded-response-v1",
        "model_requested": "recorded-response-v1",
        "model_returned": "none",
        "api": "recorded",
        "store": False,
        "endpoint_host": "none",
        "region": "local",
        "retention": "immutable-fixture",
        "data_use": "none",
        "timeout_seconds": 0,
        "retry_count": 0,
        "retries_performed": 0,
        "maximum_payload_bytes": request_body_bytes,
        "filing_egress_policy": "none",
        "request_body_bytes": request_body_bytes,
    }


class RecordSchemaTest(unittest.TestCase):
    """Prove records and authoritative JSON reject type ambiguity."""

    def test_raw_blob_rejects_wrong_scalar_types(self) -> None:
        """Reject a byte length or media type with the wrong JSON type."""
        base = {
            "record_type": "RAW_BLOB",
            "raw_asset_id": "sha256:" + "a" * 64,
            "byte_length": 1,
            "media_type": "text/html",
            "storage_uri": "evidence/raw.html",
        }
        for field, value in (("byte_length", "1"), ("media_type", 1)):
            with self.subTest(field=field):
                changed = dict(base)
                changed[field] = value
                with self.assertRaisesRegex(RecordError, "type"):
                    validate_record(record=changed)

    def test_nested_binary_float_is_not_a_strict_record(self) -> None:
        """Reject NaN before an audit record reaches JSON persistence."""
        record = {
            "record_type": "AI_EXTRACTION_ATTEMPT",
            "attempt_id": "attempt:fixture",
            "status": "SUCCEEDED",
            "provider": "recorded",
            "model": "recorded-response-v1",
            "model_requested": "recorded-response-v1",
            "model_returned": "none",
            "api": "recorded",
            "endpoint_host": "none",
            "transport_observation": recorded_transport_observation(
                request_body_bytes=1,
            ),
            "sampling_parameters": {
                "temperature": float("nan"),
                "reasoning_effort": "none",
            },
            "reader_input_manifest_hash": "sha256:" + "a" * 64,
            "request_body_sha256": "b" * 64,
            "request_body_path": "attempt_payloads/request_{}.bin".format(
                "b" * 64
            ),
            "reader_payload_sha256": "f" * 64,
            "reader_payload_path": (
                "attempt_payloads/reader_payload_{}.json".format("f" * 64)
            ),
            "task_contract_sha256": "d" * 64,
            "task_contract_path": (
                "attempt_payloads/task_contract_{}.json".format("d" * 64)
            ),
            "task_spec_semantic_hash": "sha256:" + "e" * 64,
            "output_schema_sha256": "a" * 64,
            "output_schema_path": (
                "attempt_payloads/output_schema_{}.json".format("a" * 64)
            ),
            "assistant_output_sha256": "c" * 64,
            "assistant_output_path": (
                "attempt_payloads/assistant_output_{}.json".format("c" * 64)
            ),
            "raw_response_sha256": "c" * 64,
            "raw_response_path": "attempt_payloads/response_{}.bin".format(
                "c" * 64
            ),
            "provider_request_id": "fixture:request",
            "started_at_utc": "2026-07-29T13:00:00+00:00",
            "finished_at_utc": "2026-07-29T13:00:01+00:00",
            "error_class": "",
        }
        with self.assertRaisesRegex(RecordError, "canonical"):
            validate_record(record=record)

    def test_loaded_attempt_reapplies_sampling_and_utc_invariants(
        self,
    ) -> None:
        """Reject caller-crafted attempts that bypass the adapter checks."""
        record = {
            "record_type": "AI_EXTRACTION_ATTEMPT",
            "attempt_id": "attempt:fixture",
            "status": "SUCCEEDED",
            "provider": "recorded",
            "model": "recorded-response-v1",
            "model_requested": "recorded-response-v1",
            "model_returned": "none",
            "api": "recorded",
            "endpoint_host": "none",
            "transport_observation": recorded_transport_observation(
                request_body_bytes=1,
            ),
            "sampling_parameters": {
                "temperature": 0,
                "reasoning_effort": "none",
            },
            "reader_input_manifest_hash": "sha256:" + "a" * 64,
            "request_body_sha256": "b" * 64,
            "request_body_path": "attempt_payloads/request_{}.bin".format(
                "b" * 64
            ),
            "reader_payload_sha256": "f" * 64,
            "reader_payload_path": (
                "attempt_payloads/reader_payload_{}.json".format("f" * 64)
            ),
            "task_contract_sha256": "d" * 64,
            "task_contract_path": (
                "attempt_payloads/task_contract_{}.json".format("d" * 64)
            ),
            "task_spec_semantic_hash": "sha256:" + "e" * 64,
            "output_schema_sha256": "a" * 64,
            "output_schema_path": (
                "attempt_payloads/output_schema_{}.json".format("a" * 64)
            ),
            "assistant_output_sha256": "c" * 64,
            "assistant_output_path": (
                "attempt_payloads/assistant_output_{}.json".format("c" * 64)
            ),
            "raw_response_sha256": "c" * 64,
            "raw_response_path": "attempt_payloads/response_{}.bin".format(
                "c" * 64
            ),
            "provider_request_id": "fixture:request",
            "started_at_utc": "2026-07-29T13:00:00+00:00",
            "finished_at_utc": "2026-07-29T13:00:01+00:00",
            "error_class": "",
        }
        invalid_cases = (
            (
                "sampling_parameters",
                {"temperature": False, "reasoning_effort": "none"},
            ),
            ("started_at_utc", "2026-07-29T13:00:00+08:00"),
            ("finished_at_utc", "2026-07-29T12:00:00+00:00"),
        )
        for field, value in invalid_cases:
            with self.subTest(field=field):
                changed = dict(record)
                changed[field] = value
                with self.assertRaises(RecordError):
                    validate_record(record=changed)
        succeeded_without_response = dict(record)
        succeeded_without_response["raw_response_sha256"] = ""
        succeeded_without_response["raw_response_path"] = ""
        with self.assertRaisesRegex(RecordError, "response state"):
            validate_record(record=succeeded_without_response)
        failed_without_error = dict(record)
        failed_without_error["status"] = "FAILED"
        with self.assertRaisesRegex(RecordError, "error class"):
            validate_record(record=failed_without_error)

    def test_loaded_run_reapplies_period_and_trait_invariants(self) -> None:
        """Reject caller-crafted Run coordinates at the disk boundary."""
        digest = "a" * 64
        record = {
            "record_type": "RUN",
            "run_id": "run:fixture",
            "status": "OPEN",
            "company_id": "company_fixture",
            "company_traits": ["non_financial"],
            "target_period": {
                "fiscal_year": 2025,
                "period_start": "2025-01-01",
                "period_end": "2025-12-31",
            },
            "source_references": [],
            "missing_required_source_roles": [],
            "spec_file_hashes": {},
            "requirement_hashes": {},
            "records_file_hash": digest,
            "review_decisions_file_hash": digest,
            "validation_file_hash": digest,
            "content_manifest_hash": "sha256:" + digest,
            "audit_manifest_hash": "sha256:" + digest,
            "execution_semantics_hash": "sha256:" + digest,
        }
        validate_record(record=record)
        year_boundary = dict(record)
        year_boundary["target_period"] = {
            "fiscal_year": 2025,
            "period_start": "2025-02-02",
            "period_end": "2026-01-31",
        }
        validate_record(record=year_boundary)
        invalid_cases = (
            ("company_traits", ["non_financial", "non_financial"]),
            (
                "target_period",
                {
                    "fiscal_year": 2025,
                    "period_start": "2025-12-31",
                    "period_end": "2025-01-01",
                },
            ),
            (
                "target_period",
                {
                    "fiscal_year": 2025,
                    "period_start": "2030-01-01",
                    "period_end": "2030-12-31",
                },
            ),
            (
                "target_period",
                {
                    "fiscal_year": 2025,
                    "period_start": "2024-01-01",
                    "period_end": "2025-12-31",
                },
            ),
            (
                "target_period",
                {
                    "fiscal_year": 2025,
                    "period_start": "2025-W01-1",
                    "period_end": "2025-12-31",
                },
            ),
            (
                "target_period",
                {
                    "fiscal_year": 2025,
                    "period_start": "20250101",
                    "period_end": "20251231",
                },
            ),
        )
        for field, value in invalid_cases:
            with self.subTest(field=field):
                changed = dict(record)
                changed[field] = value
                with self.assertRaises(RecordError):
                    validate_record(record=changed)

    def test_atomic_json_rejects_non_finite_binary_float(self) -> None:
        """Never publish Python's non-standard NaN JSON extension."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            with self.assertRaises(CanonicalError):
                atomic_write_json(path=path, value={"value": float("nan")})
            self.assertFalse(path.exists())

    def test_observation_scope_is_recomputed_when_loaded(self) -> None:
        """Reject a content-addressed observation with a forged scope key."""
        identity = {
            "semantic_role": "revenue",
            "metric_id": "B01",
            "company_id": "company_fixture",
            "period_start": "2025-01-01",
            "period_end": "2025-12-31",
            "scope": {"consolidation": "entity"},
            "scope_key": "sha256:" + "0" * 64,
            "value": "1000",
            "unit": "USD",
            "source_binding": {
                "raw_asset_id": "sha256:" + "a" * 64,
                "source_reference_id": "sha256:" + "b" * 64,
                "accession": "0000000000-25-000001",
                "document_name": "companyfacts.json",
                "source_role": "companyfacts",
            },
        }
        record = dict(identity)
        record.update(
            {
                "record_type": "VERIFIED_OBSERVATION",
                "observation_id": content_hash(value=identity),
                "quality": "EXACT",
                "approval_effect_hash": "",
            }
        )
        with self.assertRaisesRegex(RecordError, "scope identity"):
            validate_record(record=record)


if __name__ == "__main__":
    unittest.main()
