"""Normal governance discovery is metadata/source-proof driven, never answers."""

import copy
import builtins
import io
import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

from tests.vnext.common import REPO_ROOT
from vnext.normal_governance_input import NormalGovernanceInputError
from vnext.normal_governance_input import prepare_saved_governance_input, select_governance_metadata
from vnext import normal_governance_input as normal
from vnext.governance_signals import C04_V2_SPEC_PATH, resolve_c04
from vnext.specs import compile_spec_file
from vnext.canonical import sha256_bytes
from vnext.sources import source_reference_record
from vnext.deterministic_router import source_set_manifest
from tests.vnext.test_governance_signals import c04_arguments, c04_events, c04_filing


def filing(form, report, filed, ordinal):
    return {"form": form, "reportDate": report, "filingDate": filed,
            "accessionNumber": "0000012345-26-" + str(ordinal).zfill(6),
            "primaryDocument": "source" + str(ordinal) + ".htm"}


def inputs(extra=None):
    current = filing("10-K", "2025-12-31", "2026-02-01", 1)
    rows = [current, filing("10-K/A", "2025-12-31", "2026-04-01", 2),
            filing("10-K", "2024-12-31", "2025-02-01", 3),
            filing("DEF 14A", "2026-05-01", "2026-03-01", 4),
            filing("8-K", "2025-06-01", "2025-06-01", 5),
            filing("8-K/A", "2025-06-01", "2025-07-01", 6)] + (extra or [])
    payload = {"cik": 12345, "filings": {"recent": {k: [r[k] for r in rows] for k in current}, "files": []}}
    prepared = {"filing": current, "table_input": {"target_period": {"period_start": "2025-01-01", "period_end": "2025-12-31", "fiscal_year": 2025}}}
    return dict(company={"primary_cik": "12345"}, prepared_input=prepared,
                inventories=[{"name": "CIK0000012345.json", "payload": payload}])


class NormalGovernanceMetadataTest(unittest.TestCase):
    def test_current_amendment_prior_proxy_and_amended_event_are_distinct(self):
        selected = select_governance_metadata(**inputs())
        self.assertEqual(["10-K/A", "10-K"], [f["form"] for f in selected["current_filing_chain"]])
        self.assertEqual("2024-12-31", selected["prior_ordinary"]["reportDate"])
        self.assertEqual("DEF 14A", selected["latest_def14a"]["form"])
        self.assertEqual(["8-K", "8-K/A"], [f["form"] for f in selected["events"]])

    def test_missing_relevant_history_or_overlapping_accession_is_not_ignored(self):
        args = inputs()
        args["inventories"][0]["payload"]["filings"]["files"] = [{"name": "CIK0000012345-submissions-001.json", "filingFrom": "2024-01-01", "filingTo": "2025-01-20"}]
        with self.assertRaisesRegex(NormalGovernanceInputError, "RELEVANT_HISTORY_NOT_LOADED"):
            select_governance_metadata(**args)
        args = inputs()
        args["inventories"].append({"name": "CIK0000012345-submissions-001.json", "payload": copy.deepcopy(args["inventories"][0]["payload"]["filings"]["recent"])})
        with self.assertRaisesRegex(NormalGovernanceInputError, "ACCESSIONS_OVERLAP"):
            select_governance_metadata(**args)

    def test_metadata_cik_history_range_and_columns_fail_closed(self):
        for change in (lambda p: p.update(cik=54321), lambda p: p["filings"]["recent"]["form"].pop(),
                       lambda p: p["filings"]["files"].append({"name": "CIK0000012345-submissions-001.json", "filingFrom": "unknown", "filingTo": "unknown"}),
                       lambda p: p["filings"]["files"].append({"name": "CIK0000054321-submissions-001.json", "filingFrom": "2024-01-01", "filingTo": "2025-01-01"})):
            args = inputs(); change(args["inventories"][0]["payload"])
            with self.assertRaises(NormalGovernanceInputError): select_governance_metadata(**args)

    def test_new_period_without_ordinary_cannot_choose_previous_success(self):
        args = inputs([filing("10-K/A", "2026-12-31", "2027-02-01", 7)])
        with self.assertRaisesRegex(NormalGovernanceInputError, "CURRENT_ORDINARY_MISSING_OR_CHANGED"):
            select_governance_metadata(**args)
        args = inputs([filing("10-K", "2025-12-31", "2026-02-02", 7)])
        with self.assertRaisesRegex(NormalGovernanceInputError, "CURRENT_ORDINARY_MISSING_OR_CHANGED"):
            select_governance_metadata(**args)

    def test_prior_in_newly_loaded_history_is_selected_by_report_period(self):
        args = inputs()
        row = filing("10-K", "2025-06-30", "2025-08-01", 9)
        shard = {k: [v] for k, v in row.items()}
        args["inventories"].append({"name": "CIK0000012345-submissions-001.json", "payload": shard})
        args["inventories"][0]["payload"]["filings"]["files"] = [{"name": "CIK0000012345-submissions-001.json", "filingFrom": "2025-08-01", "filingTo": "2025-08-01"}]
        self.assertEqual("2025-06-30", select_governance_metadata(**args)["prior_ordinary"]["reportDate"])

    def test_same_day_amendments_need_real_acceptance_time(self):
        args = inputs([filing("10-K/A", "2025-12-31", "2026-04-01", 8)])
        with self.assertRaisesRegex(NormalGovernanceInputError, "SAME_DAY_ORDER_NOT_PROVEN"):
            select_governance_metadata(**args)
        block = args["inventories"][0]["payload"]["filings"]["recent"]
        block["acceptanceDateTime"] = [""] * len(block["form"])
        block["acceptanceDateTime"][1] = "2026-04-01T19:00:00Z"
        block["acceptanceDateTime"][-1] = "2026-04-01T17:00:00-04:00"
        selected = select_governance_metadata(**args)
        self.assertTrue(selected["amendments"][0]["accessionNumber"].endswith("000008"))

    def test_saved_shard_range_conflict_is_a_coverage_gap_not_no_events(self):
        shard = {"name": "CIK0000012345-submissions-001.json", "filingFrom": "2025-07-15", "filingTo": "2025-08-13"}
        row = filing("8-K", "2025-07-01", "2025-07-01", 1)
        conflict = normal.history_body_alignment(shard=shard, rows=[row])
        self.assertEqual("SAVED_HISTORY_INDEX_AND_BODY_ARE_NOT_A_COHERENT_SNAPSHOT", conflict["reason"])
        self.assertEqual([row], conflict["out_of_range_filings"])

    def test_missing_same_subject_prior_does_not_borrow_predecessor(self):
        args = inputs(); block = args["inventories"][0]["payload"]["filings"]["recent"]
        for values in block.values(): values.pop(2)
        selected = select_governance_metadata(**args)
        self.assertIsNone(selected["prior_ordinary"])
        self.assertEqual("NO_SAME_CIK_PRIOR_IN_COMPLETE_SAVED_SUBMISSIONS", selected["prior_status"])


class NormalGovernanceBoundaryTest(unittest.TestCase):
    def test_actual_legacy_attempt_is_pinned_without_inventing_id(self):
        from vnext.normal_annual_input import _registry_rows
        from sec_urls import accession_document_url
        from vnext.batch_workflow import validate_planned_request_binding
        company = next(c for c in _registry_rows(repo_root=REPO_ROOT) if c["company_id"] == "marriott_international")
        inventory = normal.saved_source(repo_root=REPO_ROOT, url="https://data.sec.gov/submissions/CIK0001048286.json")
        block = json.loads(inventory["raw"])["filings"]["recent"]
        i = next(i for i, f in enumerate(block["form"]) if f == "DEF 14A")
        reader = normal._Sources(REPO_ROOT, company["company_id"], company["primary_cik"])
        entry = reader.read(accession_document_url(cik=1048286, accession=block["accessionNumber"][i], document_name=block["primaryDocument"][i]),
            accession=block["accessionNumber"][i], role="governance_proxy", media_type="text/html")
        proof = next(iter(reader.proofs.values()))["proof"]
        self.assertTrue(proof["request_attempt_id"].startswith("request:attempt:"))
        self.assertEqual(proof["request_attempt_id"], entry["source_reference"]["request_attempt_id"])
        self.assertEqual(proof["request_attempt_id"], validate_planned_request_binding(repo_root=REPO_ROOT, source=proof))

    def test_later_failed_get_never_falls_back_to_success(self):
        with patch.object(normal, "saved_source", side_effect=normal.AnnualUpdateError("LATEST_SOURCE_REQUEST_FAILED: TEST_ONLY")):
            reader = normal._Sources(REPO_ROOT, "sample_entity", "12345")
            with self.assertRaisesRegex(normal.AnnualUpdateError, "LATEST_SOURCE_REQUEST_FAILED"):
                reader.read("https://data.sec.gov/submissions/CIK0000012345.json", role="sec_submissions_inventory", media_type="application/json")

    def test_preparation_reads_original_proofs_without_derived_inventories(self):
        original_io, original_open = io.open, builtins.open
        forbidden = {"latest_filings_inventory.csv", "accession_materials_inventory.csv", "metrics_matrix.csv", "metric_evidence.csv", "governance_signals.csv"}
        def guarded(opener):
            def call(file, *args, **kwargs):
                if isinstance(file, (str, Path)) and Path(file).name in forbidden:
                    raise AssertionError("Derived inventory or result read: " + str(file))
                return opener(file, *args, **kwargs)
            return call
        with patch("io.open", guarded(original_io)), patch("builtins.open", guarded(original_open)), patch.object(socket.socket, "connect", side_effect=AssertionError("network")):
            prepared = prepare_saved_governance_input(repo_root=REPO_ROOT, company_id="marriott_international")
        binding = prepared["input_binding"]
        self.assertEqual("PREPARED", binding["metric_input_status"]["C03"])
        self.assertEqual("PREPARED", binding["metric_input_status"]["C04"])
        self.assertTrue(all(p["request_attempt_id"].startswith("request:attempt:") for p in binding["source_proofs"]))
        self.assertIn("8-K/A", {f["form"] for f in binding["selection"]["events"]})

    def test_imported_registry_cannot_relabel_a_different_subject(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name);(root / "config").mkdir();(root / "evidence").mkdir()
            (root / "evidence/requests_log.csv").write_bytes((REPO_ROOT / "evidence/requests_log.csv").read_bytes())
            (root / "config/company_registry.csv").write_bytes((REPO_ROOT / "config/company_registry.csv").read_bytes().replace(b"Marriott International", b"Different Registrant"))
            with self.assertRaisesRegex(NormalGovernanceInputError, "COMPANY_REGISTRY_DIFFERS_FROM_INSTALLED_SCOPE"):
                prepare_saved_governance_input(repo_root=root, company_id="marriott_international")


class AuditorV2InputTest(unittest.TestCase):
    def test_amended_8k_keeps_its_form_and_cannot_be_deleted_before_zero(self):
        args = c04_arguments(); event = c04_events("4.01")
        payload = json.loads(event["inventory_bytes"]);payload["filings"]["recent"]["form"] = ["8-K/A"]
        raw = json.dumps(payload).encode();old = event["inventory_source_reference"]
        blob = {"record_type": "RAW_BLOB", "raw_asset_id": "sha256:" + sha256_bytes(content=raw), "byte_length": len(raw), "media_type": "application/json", "storage_uri": "fixture/submissions.json"}
        reference = source_reference_record(raw_blob=blob, company_id=old["company_id"], source_url=old["source_url"], accession=old["accession"], document_name=old["document_name"], source_role=old["source_role"], request_attempt_id=old["request_attempt_id"])
        event["inventory_bytes"], event["inventory_source_reference"] = raw, reference
        refs = [doc[k] for doc in event["filing_documents"] for k in ("hdr_source_reference", "primary_source_reference")]
        event["source_set_manifest"] = source_set_manifest(company_id="sample_entity", source_role="fy_8k", form_types=["8-K", "8-K/A"], fiscal_or_date_window={"period_start": "2025-01-01", "period_end": "2025-12-31"}, discovery_policy="PINNED_SUBMISSIONS", inventory_source_reference=reference, inventory_bytes=raw, ordered_source_references=refs, cutoff_timestamp_or_pinned_submissions_attempt=reference["request_attempt_id"])
        args["event_input"] = event;args["compiled_spec"] = compile_spec_file(path=REPO_ROOT / C04_V2_SPEC_PATH, dependency_specs={})
        self.assertEqual("1", resolve_c04(**args)["result"]["value"])
        event["filing_documents"] = []
        with self.assertRaises(ValueError): resolve_c04(**args)

    def test_v2_preserves_ordered_current_and_prior_amendments_without_changing_v1(self):
        args = c04_arguments(events=False)
        args["current_filings"] = [[c04_filing("", form="10-K/A")],
            [c04_filing("New Audit LLP", accession="0000012345-26-000002", form="10-K/A")],
            [c04_filing("Old Audit LLP", accession="0000012345-26-000003")]]
        with self.assertRaisesRegex(ValueError, "ORDERED_CURRENT_FILINGS_REQUIRED"):
            resolve_c04(**args)
        args["compiled_spec"] = compile_spec_file(path=REPO_ROOT / C04_V2_SPEC_PATH, dependency_specs={})
        args["prior_sources"] = []
        args["prior_filings"] = [[c04_filing("", accession="0000012345-25-000002", year="2024", form="10-K/A")],
                                 [c04_filing("Old Audit LLP", accession="0000012345-25-000001", year="2024")]]
        result = resolve_c04(**args)
        self.assertEqual("1", result["result"]["value"])
        self.assertEqual("0000012345-26-000002", result["selection"]["selected_current_accession"])
        self.assertEqual("0000012345-25-000001", result["selection"]["prior_filing_check"]["accession"])
        self.assertEqual(2, len(result["selection"]["prior_filing_checks"]))


if __name__ == "__main__":
    unittest.main()
