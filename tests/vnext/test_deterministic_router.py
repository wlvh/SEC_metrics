"""Verify WB-2B multi-source planning and five deterministic adapters."""

from __future__ import annotations

import ast
import json
import socket
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from sec_pipeline import event_rows_for_metric
from tests.vnext.common import REPO_ROOT
from vnext.canonical import sha256_file
from vnext.deterministic_router import DeterministicRouterError
from vnext.deterministic_router import adapt_8k_item_index
from vnext.deterministic_router import adapt_accession_xbrl
from vnext.deterministic_router import adapt_auditor_fact
from vnext.deterministic_router import adapt_companyfacts, adapt_ecd_xbrl
from vnext.deterministic_router import build_multi_source_release_input_plan
from vnext.deterministic_router import load_event_route_catalog
from vnext.deterministic_router import matched_event_key_set
from vnext.deterministic_router import project_event_result
from vnext.deterministic_router import source_role_plan, source_set_manifest
from vnext.deterministic_router import validate_source_set_manifest
from vnext.sources import raw_blob_record, source_reference_record


COMPANY_ID = "company:test"
ACCESSION = "0000000001-25-000001"
ECD_ACCESSION = "0000000001-25-000002"
EVENT_ACCESSION = "0000000001-25-000003"
TARGET_PERIOD = {
    "fiscal_year": 2025,
    "period_start": "2025-01-01",
    "period_end": "2025-12-31",
}


def make_reference(
    *, root: Path, relative: str, content: bytes, source_url: str,
    accession: str, document_name: str, source_role: str,
) -> dict:
    """Persist test bytes and return one exact SourceReference.

    Args:
        root: Temporary repository root.
        relative: Portable source path.
        content: Exact fixture bytes.
        source_url: Official SEC source URL.
        accession: Filing or submissions observation identity.
        document_name: Source document identity.
        source_role: Run/source-set role.

    Returns:
        Strict SourceReference.
    """
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    raw_blob = raw_blob_record(
        repo_root=root, repo_relative_path=relative, media_type="application/octet-stream",
    )
    return source_reference_record(
        raw_blob=raw_blob,
        company_id=COMPANY_ID,
        source_url=source_url,
        accession=accession,
        document_name=document_name,
        source_role=source_role,
        request_attempt_id="request:attempt:" + raw_blob["raw_asset_id"].split(":", 1)[1],
    )


def fixture_sources(*, root: Path) -> dict:
    """Create exact bytes and SourceReferences for all five adapters.

    Args:
        root: Temporary repository root.

    Returns:
        Source bytes, references, and complete source-set manifests.
    """
    inventory_payload = {
        "cik": "0000000001",
        "filings": {
            "recent": {
                "accessionNumber": [ACCESSION, ECD_ACCESSION, EVENT_ACCESSION],
                "filingDate": ["2025-02-01", "2025-03-01", "2025-04-01"],
                "form": ["10-K", "DEF 14A", "8-K"],
            }
        },
    }
    inventory_bytes = json.dumps(inventory_payload, sort_keys=True).encode("utf-8")
    inventory = make_reference(
        root=root,
        relative="evidence/submissions/CIK0000000001.json",
        content=inventory_bytes,
        source_url="https://data.sec.gov/submissions/CIK0000000001.json",
        accession="SUBMISSIONS-2025",
        document_name="CIK0000000001.json",
        source_role="sec_submissions_inventory",
    )
    companyfacts_payload = {
        "cik": 1,
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {
                                "start": "2025-01-01",
                                "end": "2025-12-31",
                                "val": 123,
                                "accn": ACCESSION,
                                "filed": "2026-02-01",
                                "fp": "FY",
                                "form": "10-K",
                            }
                        ]
                    }
                }
            }
        },
    }
    companyfacts_bytes = (
        json.dumps(companyfacts_payload, sort_keys=True).encode("utf-8") + b"\n"
    )
    companyfacts = make_reference(
        root=root,
        relative="evidence/companyfacts/CIK0000000001.json",
        content=companyfacts_bytes,
        source_url=(
            "https://data.sec.gov/api/xbrl/companyfacts/CIK0000000001.json"
        ),
        accession=ACCESSION,
        document_name="CIK0000000001.json",
        source_role="companyfacts",
    )
    accession_bytes = (
        b'<xbrl xmlns:us-gaap="urn:us-gaap">'
        b'<us-gaap:Assets contextRef="FY" unitRef="USD">456</us-gaap:Assets>'
        b"</xbrl>"
    )
    accession = make_reference(
        root=root,
        relative="evidence/accession/test-instance.xml",
        content=accession_bytes,
        source_url=(
            "https://www.sec.gov/Archives/edgar/data/1/"
            "000000000125000001/test-instance.xml"
        ),
        accession=ACCESSION,
        document_name="test-instance.xml",
        source_role="target_accession_instance",
    )
    ecd_bytes = (
        b'<xbrl xmlns:ecd="urn:ecd">'
        b'<ecd:PayRatio contextRef="FY" unitRef="pure">42</ecd:PayRatio>'
        b"</xbrl>"
    )
    ecd = make_reference(
        root=root,
        relative="evidence/accession/test-ecd.xml",
        content=ecd_bytes,
        source_url=(
            "https://www.sec.gov/Archives/edgar/data/1/"
            "000000000125000002/test-ecd.xml"
        ),
        accession=ECD_ACCESSION,
        document_name="test-ecd.xml",
        source_role="def14a_ecd",
    )
    auditor_bytes = (
        b'<xbrl xmlns:dei="urn:dei">'
        b'<dei:AuditorName contextRef="FY">Example Audit LLP</dei:AuditorName>'
        b"</xbrl>"
    )
    auditor = make_reference(
        root=root,
        relative="evidence/accession/test-auditor.xml",
        content=auditor_bytes,
        source_url=(
            "https://www.sec.gov/Archives/edgar/data/1/"
            "000000000125000001/test-auditor.xml"
        ),
        accession=ACCESSION,
        document_name="test-auditor.xml",
        source_role="auditor_facts",
    )
    hdr_bytes = (
        b"<ITEMS><ITEM>1.01</ITEM><ITEM>5.02</ITEM>"
        b"<ITEM>8.01</ITEM></ITEMS>"
    )
    hdr = make_reference(
        root=root,
        relative="evidence/accession/test.hdr.sgml",
        content=hdr_bytes,
        source_url=(
            "https://www.sec.gov/Archives/edgar/data/1/"
            "000000000125000003/test.hdr.sgml"
        ),
        accession=EVENT_ACCESSION,
        document_name="test.hdr.sgml",
        source_role="fy_8k_hdr",
    )
    primary_bytes = (
        b"<html><body><h2>Item 1.01 Entry into an agreement</h2>"
        b"<h2>Item 5.02 Departure of an officer</h2>"
        b"<h2>Item 8.01 The company announced an acquisition transaction</h2>"
        b"</body></html>"
    )
    primary = make_reference(
        root=root,
        relative="evidence/accession/test-8k.htm",
        content=primary_bytes,
        source_url=(
            "https://www.sec.gov/Archives/edgar/data/1/"
            "000000000125000003/test-8k.htm"
        ),
        accession=EVENT_ACCESSION,
        document_name="test-8k.htm",
        source_role="fy_8k_primary",
    )
    references = {
        "inventory": inventory,
        "companyfacts": companyfacts,
        "accession": accession,
        "ecd": ecd,
        "auditor": auditor,
        "hdr": hdr,
        "primary": primary,
    }
    source_bytes = {
        "companyfacts": companyfacts_bytes,
        "inventory": inventory_bytes,
        "accession": accession_bytes,
        "ecd": ecd_bytes,
        "auditor": auditor_bytes,
        "hdr": hdr_bytes,
        "primary": primary_bytes,
    }
    role_inputs = {
        "companyfacts": ("10-K", [companyfacts]),
        "target_accession_instance": ("10-K", [accession]),
        "def14a_ecd": ("DEF 14A", [ecd]),
        "auditor_facts": ("10-K", [auditor]),
        "fy_8k_item_inventory": ("8-K", [hdr, primary]),
    }
    manifests = {
        role: source_set_manifest(
            company_id=COMPANY_ID,
            source_role=role,
            form_types=[form_type],
            fiscal_or_date_window=TARGET_PERIOD,
            discovery_policy="PINNED_SUBMISSIONS_FISCAL_WINDOW_V1",
            inventory_source_reference=inventory,
            inventory_bytes=inventory_bytes,
            ordered_source_references=role_references,
            cutoff_timestamp_or_pinned_submissions_attempt=(
                inventory["request_attempt_id"]
            ),
        )
        for role, (form_type, role_references) in role_inputs.items()
    }
    return {
        "bytes": source_bytes,
        "references": references,
        "manifests": manifests,
    }


class DeterministicRouterTest(unittest.TestCase):
    """Prove multi-source completeness, adapters, and event parity."""

    def test_five_adapters_emit_deterministic_verified_claims(self) -> None:
        """Run all five adapters with a socket-open canary fixed at zero."""
        with tempfile.TemporaryDirectory() as directory:
            fixtures = fixture_sources(root=Path(directory))
            references = fixtures["references"]
            manifests = fixtures["manifests"]
            source_bytes = fixtures["bytes"]
            with mock.patch.object(
                socket,
                "socket",
                side_effect=AssertionError("provider socket opened"),
            ):
                companyfacts = adapt_companyfacts(
                    raw_bytes=source_bytes["companyfacts"],
                    source_reference=references["companyfacts"],
                    source_set_manifest=manifests["companyfacts"],
                    approved_concepts=["us-gaap:Revenues"],
                    allowed_ciks=["1"],
                    include_instant=False,
                )
                accession = adapt_accession_xbrl(
                    raw_bytes=source_bytes["accession"],
                    source_reference=references["accession"],
                    source_set_manifest=manifests["target_accession_instance"],
                    fact_names=["Assets"],
                )
                ecd = adapt_ecd_xbrl(
                    raw_bytes=source_bytes["ecd"],
                    source_reference=references["ecd"],
                    source_set_manifest=manifests["def14a_ecd"],
                    fact_names=["PayRatio"],
                )
                auditor = adapt_auditor_fact(
                    raw_bytes=source_bytes["auditor"],
                    source_reference=references["auditor"],
                    source_set_manifest=manifests["auditor_facts"],
                    fact_names=["AuditorName"],
                )
                events = adapt_8k_item_index(
                    filing_documents=[
                        {
                            "hdr_bytes": source_bytes["hdr"],
                            "hdr_source_reference": references["hdr"],
                            "primary_document_bytes": source_bytes["primary"],
                            "primary_source_reference": references["primary"],
                        }
                    ],
                    source_set_manifest=manifests["fy_8k_item_inventory"],
                    inventory_source_reference=references["inventory"],
                    inventory_bytes=source_bytes["inventory"],
                )
        self.assertEqual(["123"], [claim["value"] for claim in companyfacts])
        self.assertEqual(["456"], [claim["value"] for claim in accession])
        self.assertEqual(["42"], [claim["value"] for claim in ecd])
        self.assertEqual(["Example Audit LLP"], [claim["value"] for claim in auditor])
        self.assertEqual(["1.01", "5.02", "8.01"], [
            claim["attributes"]["item_code"] for claim in events
        ])

    def test_multi_source_plan_uses_only_sources_arrays_and_manifests(self) -> None:
        """Bind every single/multi source role through one uniform shape."""
        with tempfile.TemporaryDirectory() as directory:
            fixtures = fixture_sources(root=Path(directory))
            references = list(fixtures["references"].values())
            manifests = fixtures["manifests"]
            roles = [
                source_role_plan(
                    manifest=manifests["companyfacts"],
                    source_mode="STRUCTURED_JSON",
                ),
                source_role_plan(
                    manifest=manifests["target_accession_instance"],
                    source_mode="ACCESSION_XBRL",
                ),
                source_role_plan(
                    manifest=manifests["def14a_ecd"],
                    source_mode="ECD_XBRL",
                ),
                source_role_plan(
                    manifest=manifests["auditor_facts"],
                    source_mode="AUDITOR_FACT",
                ),
                source_role_plan(
                    manifest=manifests["fy_8k_item_inventory"],
                    source_mode="ITEM_CODE_INDEX",
                ),
            ]
            plan = build_multi_source_release_input_plan(
                release_plan_id="issue_15_zero_ai_r0_registry",
                requirement_id="issue_15_v1",
                authority_hashes={"source_strategy_registry_sha256": "a" * 64},
                companies=[
                    {
                        "company_id": COMPANY_ID,
                        "result_metric_ids": ["A01", "C01", "E01"],
                        "sources": roles,
                        "target_period": TARGET_PERIOD,
                    }
                ],
                source_references=references,
                source_set_manifests=list(manifests.values()),
                event_route_catalog_sha256=sha256_file(
                    path=REPO_ROOT / "catalog" / "event_routes.json"
                ),
            )
        company = plan["companies"][0]
        self.assertIsInstance(company["sources"], list)
        self.assertNotIn("companyfacts_source", company)
        self.assertNotIn("table_source", company)
        self.assertTrue(all(isinstance(role["source_reference_ids"], list) for role in roles))
        singleton_roles = roles[:4]
        self.assertTrue(all(len(role["source_reference_ids"]) == 1 for role in singleton_roles))
        self.assertTrue(
            all(
                role["source_set_manifest_id"].startswith("sha256:")
                for role in roles
            )
        )

    def test_c01_and_e03_share_item_claims_then_project_separately(self) -> None:
        """Use one Item 5.02 claim set for two metric-specific results."""
        with tempfile.TemporaryDirectory() as directory:
            fixtures = fixture_sources(root=Path(directory))
            claims = adapt_8k_item_index(
                filing_documents=[
                    {
                        "hdr_bytes": fixtures["bytes"]["hdr"],
                        "hdr_source_reference": fixtures["references"]["hdr"],
                        "primary_document_bytes": fixtures["bytes"]["primary"],
                        "primary_source_reference": fixtures["references"]["primary"],
                    }
                ],
                source_set_manifest=fixtures["manifests"]["fy_8k_item_inventory"],
                inventory_source_reference=fixtures["references"]["inventory"],
                inventory_bytes=fixtures["bytes"]["inventory"],
            )
            catalog = load_event_route_catalog(repo_root=REPO_ROOT)
            outputs = {
                metric_id: project_event_result(
                    metric_id=metric_id,
                    claims=claims,
                    source_set_manifest=fixtures["manifests"]["fy_8k_item_inventory"],
                    inventory_source_reference=fixtures["references"]["inventory"],
                    target_period=TARGET_PERIOD,
                    catalog=catalog,
                )
                for metric_id in ("C01", "E03")
            }
        self.assertEqual(
            outputs["C01"]["matched_verified_claim_ids"],
            outputs["E03"]["matched_verified_claim_ids"],
        )
        self.assertNotEqual(
            outputs["C01"]["observation"]["observation_id"],
            outputs["E03"]["observation"]["observation_id"],
        )
        self.assertEqual("1", outputs["C01"]["result"]["value"])
        self.assertEqual("1", outputs["E03"]["result"]["value"])

    def test_closed_world_zero_results_keep_complete_source_set(self) -> None:
        """Project E02/E04 zero only through the complete FY 8-K manifest."""
        with tempfile.TemporaryDirectory() as directory:
            fixtures = fixture_sources(root=Path(directory))
            claims = adapt_8k_item_index(
                filing_documents=[
                    {
                        "hdr_bytes": fixtures["bytes"]["hdr"],
                        "hdr_source_reference": fixtures["references"]["hdr"],
                        "primary_document_bytes": fixtures["bytes"]["primary"],
                        "primary_source_reference": fixtures["references"]["primary"],
                    }
                ],
                source_set_manifest=fixtures["manifests"]["fy_8k_item_inventory"],
                inventory_source_reference=fixtures["references"]["inventory"],
                inventory_bytes=fixtures["bytes"]["inventory"],
            )
            catalog = load_event_route_catalog(repo_root=REPO_ROOT)
            outputs = [
                project_event_result(
                    metric_id=metric_id,
                    claims=claims,
                    source_set_manifest=fixtures["manifests"]["fy_8k_item_inventory"],
                    inventory_source_reference=fixtures["references"]["inventory"],
                    target_period=TARGET_PERIOD,
                    catalog=catalog,
                )
                for metric_id in ("E02", "E04")
            ]
        self.assertEqual(["0", "0"], [output["result"]["value"] for output in outputs])
        for output in outputs:
            self.assertEqual(
                fixtures["manifests"]["fy_8k_item_inventory"]["source_set_manifest_id"],
                output["observation"]["source_binding"]["source_set_manifest_id"],
            )

    def test_e01_matched_event_key_set_has_exact_legacy_parity(self) -> None:
        """Compare declarative E01 keys with the frozen legacy matcher."""
        with tempfile.TemporaryDirectory() as directory:
            fixtures = fixture_sources(root=Path(directory))
            claims = adapt_8k_item_index(
                filing_documents=[
                    {
                        "hdr_bytes": fixtures["bytes"]["hdr"],
                        "hdr_source_reference": fixtures["references"]["hdr"],
                        "primary_document_bytes": fixtures["bytes"]["primary"],
                        "primary_source_reference": fixtures["references"]["primary"],
                    }
                ],
                source_set_manifest=fixtures["manifests"]["fy_8k_item_inventory"],
                inventory_source_reference=fixtures["references"]["inventory"],
                inventory_bytes=fixtures["bytes"]["inventory"],
            )
        catalog = load_event_route_catalog(repo_root=REPO_ROOT)
        actual = matched_event_key_set(metric_id="E01", claims=claims, catalog=catalog)
        legacy_rows = [
            {
                "source_url": claim["attributes"]["source_url"],
                "accession": claim["attributes"]["accession"],
                "item_code": claim["attributes"]["item_code"],
                "brief": claim["attributes"]["brief"],
            }
            for claim in claims
        ]
        expected = [
            {
                "source_url": row["source_url"],
                "accession": row["accession"],
                "item_code": row["item_code"],
            }
            for row in event_rows_for_metric(events=legacy_rows, metric_id="E01")
        ]
        self.assertEqual(expected, actual)
        self.assertEqual(
            ["merger", "acquisition", "combine", "transaction"],
            catalog["routes"]["E01"]["keyword_item_rules"][0]["aliases"],
        )

    def test_source_set_tamper_and_metric_specific_branch_fail(self) -> None:
        """Reject manifest drift and ban a shared E01 identity branch."""
        with tempfile.TemporaryDirectory() as directory:
            fixtures = fixture_sources(root=Path(directory))
            manifest = dict(fixtures["manifests"]["fy_8k_item_inventory"])
            manifest["ordered_source_reference_ids"] = []
            with self.assertRaisesRegex(
                DeterministicRouterError, "identity differs",
            ):
                validate_source_set_manifest(manifest=manifest)
            with self.assertRaisesRegex(
                DeterministicRouterError,
                "differ from submissions discovery",
            ):
                source_set_manifest(
                    company_id=COMPANY_ID,
                    source_role="fy_8k_item_inventory",
                    form_types=["8-K"],
                    fiscal_or_date_window=TARGET_PERIOD,
                    discovery_policy="PINNED_SUBMISSIONS_FISCAL_WINDOW_V1",
                    inventory_source_reference=fixtures["references"][
                        "inventory"
                    ],
                    inventory_bytes=fixtures["bytes"]["inventory"],
                    ordered_source_references=[],
                    cutoff_timestamp_or_pinned_submissions_attempt=fixtures[
                        "references"
                    ]["inventory"]["request_attempt_id"],
                )

        module_path = REPO_ROOT / "scripts" / "vnext" / "deterministic_router.py"
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        forbidden = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.If) or not isinstance(node.test, ast.Compare):
                continue
            names = [child.id for child in ast.walk(node.test) if isinstance(child, ast.Name)]
            strings = [
                child.value
                for child in ast.walk(node.test)
                if isinstance(child, ast.Constant) and isinstance(child.value, str)
            ]
            if "metric_id" in names and "E01" in strings:
                forbidden.append(node.lineno)
        self.assertEqual([], forbidden)


if __name__ == "__main__":
    unittest.main()
