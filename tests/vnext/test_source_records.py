"""Raw-byte provenance and SourceReference identity tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.vnext.common import SCRIPTS_DIR  # noqa: F401
from vnext.canonical import canonical_json_bytes, content_hash, sha256_bytes
from vnext.records import RecordError, validate_record
from vnext.sources import SourceError, companyfacts_structured_facts
from vnext.sources import load_raw_blob_bytes, raw_blob_record
from vnext.sources import source_reference_record


class SourceRecordTest(unittest.TestCase):
    """Prove portable raw binding, identity, and fail-closed I/O."""

    def test_same_bytes_support_multiple_distinct_source_references(
        self,
    ) -> None:
        """Reuse one RawBlob with distinct filing observation identities."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw_path = root / "evidence/raw.html"
            raw_path.parent.mkdir(parents=True)
            raw_path.write_bytes(b"<html>same immutable bytes</html>")
            raw = raw_blob_record(
                repo_root=root,
                repo_relative_path="evidence/raw.html",
                media_type="text/html",
            )
            first = source_reference_record(
                raw_blob=raw,
                company_id="company_one",
                source_url="https://www.sec.gov/Archives/one.htm",
                accession="0000000000-25-000001",
                document_name="one.htm",
                source_role="target_primary",
                request_attempt_id="request:attempt:001",
            )
            second = source_reference_record(
                raw_blob=raw,
                company_id="company_one",
                source_url="https://www.sec.gov/Archives/two.htm",
                accession="0000000000-25-000002",
                document_name="two.htm",
                source_role="target_primary",
                request_attempt_id="request:attempt:002",
            )
            self.assertEqual(first["raw_asset_id"], second["raw_asset_id"])
            self.assertNotEqual(
                first["source_reference_id"], second["source_reference_id"],
            )

    def test_changed_bytes_and_non_sec_origin_fail_closed(self) -> None:
        """Reject byte drift and provider substitution before evidence use."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw_path = root / "raw.html"
            raw_path.write_bytes(b"first")
            raw = raw_blob_record(
                repo_root=root,
                repo_relative_path="raw.html",
                media_type="text/html",
            )
            raw_path.write_bytes(b"second")
            with self.assertRaisesRegex(SourceError, "hash mismatch"):
                load_raw_blob_bytes(repo_root=root, raw_blob=raw)
            with self.assertRaisesRegex(SourceError, "official SEC"):
                source_reference_record(
                    raw_blob=raw,
                    company_id="company_one",
                    source_url="https://example.com/filing.htm",
                    accession="0000000000-25-000001",
                    document_name="one.htm",
                    source_role="target_primary",
                    request_attempt_id="request:attempt:001",
                )

    def test_explicit_port_is_not_an_official_sec_origin(self) -> None:
        """Reject a lookalike SEC authority with a non-standard port."""
        raw = {
            "record_type": "RAW_BLOB",
            "raw_asset_id": "sha256:" + "a" * 64,
            "byte_length": 1,
            "media_type": "text/html",
            "storage_uri": "evidence/raw.html",
        }
        with self.assertRaisesRegex(SourceError, "official SEC"):
            source_reference_record(
                raw_blob=raw,
                company_id="company_one",
                source_url=(
                    "https://www.sec.gov:444/Archives/filing.htm"
                ),
                accession="0000000000-25-000001",
                document_name="filing.htm",
                source_role="target_primary",
                request_attempt_id="request:attempt:001",
            )

    def test_handcrafted_reference_cannot_bypass_official_origin(self) -> None:
        """Reapply the SEC origin rule when records are loaded from disk."""
        identity = {
            "raw_asset_id": "sha256:" + "a" * 64,
            "company_id": "company_one",
            "source_url": "https://example.com/filing.htm",
            "accession": "0000000000-25-000001",
            "document_name": "filing.htm",
            "source_role": "target_primary",
        }
        reference = dict(identity)
        reference.update(
            {
                "record_type": "SOURCE_REFERENCE",
                "source_reference_id": content_hash(value=identity),
                "request_attempt_id": "request:attempt:001",
            }
        )
        with self.assertRaisesRegex(RecordError, "official SEC"):
            validate_record(record=reference)

    def test_parent_traversal_and_symlink_are_rejected(self) -> None:
        """Keep repository-relative bindings portable and non-aliased."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = root.parent / "outside-vnext-source.txt"
            outside.write_bytes(b"outside")
            try:
                with self.assertRaises(SourceError):
                    raw_blob_record(
                        repo_root=root,
                        repo_relative_path="../outside-vnext-source.txt",
                        media_type="text/plain",
                    )
                link = root / "alias.txt"
                link.symlink_to(outside)
                with self.assertRaisesRegex(SourceError, "symlink"):
                    raw_blob_record(
                        repo_root=root,
                        repo_relative_path="alias.txt",
                        media_type="text/plain",
                    )
            finally:
                outside.unlink()

    def test_companyfacts_adapter_binds_bytes_cik_and_accession(self) -> None:
        """Materialize only the Run-bound filing from exact company bytes."""
        payload = {
            "cik": 1048286,
            "entityName": "Fixture",
            "facts": {
                "us-gaap": {
                    "Revenues": {
                        "units": {
                            "EUR": [
                                {
                                    "start": "2024-01-01",
                                    "end": "2024-12-31",
                                    "val": 100,
                                    "accn": "0001628280-25-004818",
                                    "fp": "FY",
                                    "form": "10-K",
                                    "filed": "2025-02-11",
                                },
                                {
                                    "start": "2024-01-01",
                                    "end": "2024-12-31",
                                    "val": 200,
                                    "accn": "0001048286-26-000007",
                                    "fp": "FY",
                                    "form": "10-K",
                                    "filed": "2026-02-10",
                                },
                            ]
                        }
                    }
                }
            },
        }
        raw_bytes = canonical_json_bytes(value=payload)
        raw = {
            "record_type": "RAW_BLOB",
            "raw_asset_id": "sha256:" + sha256_bytes(content=raw_bytes),
            "byte_length": len(raw_bytes),
            "media_type": "application/json",
            "storage_uri": "evidence/companyfacts/CIK0001048286.json",
        }
        source = source_reference_record(
            raw_blob=raw,
            company_id="marriott_international",
            source_url=(
                "https://data.sec.gov/api/xbrl/companyfacts/"
                "CIK0001048286.json"
            ),
            accession="0001628280-25-004818",
            document_name="CIK0001048286.json",
            source_role="companyfacts",
            request_attempt_id="request:attempt:fixture",
        )
        facts = companyfacts_structured_facts(
            raw_bytes=raw_bytes,
            source_reference=source,
            approved_concepts=["us-gaap:Revenues"],
            allowed_ciks=["1048286"],
        )
        self.assertEqual(1, len(facts))
        self.assertEqual("100", facts[0]["value"])
        self.assertEqual("EUR", facts[0]["unit"])
        self.assertEqual(source["accession"], facts[0]["accession"])
        with self.assertRaisesRegex(SourceError, "company registry"):
            companyfacts_structured_facts(
                raw_bytes=raw_bytes,
                source_reference=source,
                approved_concepts=["us-gaap:Revenues"],
                allowed_ciks=["37996"],
            )
        with self.assertRaisesRegex(SourceError, "bytes differ"):
            companyfacts_structured_facts(
                raw_bytes=raw_bytes + b" ",
                source_reference=source,
                approved_concepts=["us-gaap:Revenues"],
                allowed_ciks=["1048286"],
            )


if __name__ == "__main__":
    unittest.main()
