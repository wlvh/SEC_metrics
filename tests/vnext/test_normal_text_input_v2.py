"""Normal C02/D02 source choice, amendment boundaries and authentic saved input."""
import copy
import builtins
import io
import inspect
from pathlib import Path
import socket
import tempfile
import shutil
import unittest
from unittest.mock import patch

from tests.vnext.common import REPO_ROOT
from tests.vnext.test_text_coverage import annual
from tests.vnext.test_text_results_v2 import source
from vnext.normal_text_input_v2 import prepare_normal_business_text_input
from vnext.normal_text_input_v2 import _source_plan, _part_iii_proof, _check_selected_metadata_scope, _current_metadata_context
from vnext.normal_governance_input import _Sources
from vnext.annual_update import AnnualUpdateError
from vnext.batch_workflow import BatchWorkflowError
from vnext.text_results_v2 import prepare_business_text_sources


def filing(form, date, ordinal, report="2025-12-31"):
    return {"form":form,"filingDate":date,"reportDate":report,
            "accessionNumber":"0000012345-26-"+str(ordinal).zfill(6),"primaryDocument":"source"+str(ordinal)+".htm"}


def governance(*, proxy=True, amendments=None, proxy_amendments=None):
    ordinary=filing("10-K","2026-02-01",1)
    amendments=[] if amendments is None else amendments
    p=filing("DEF 14A","2026-03-27",2,report="2026-05-08") if proxy else None
    return {"prepared_annual_input":{"filing":ordinary,"table_input":{"target_period":{"period_start":"2025-01-01","period_end":"2025-12-31"}},
            "update_status":"AMENDMENT_PROCESSING_REQUIRED" if amendments else "ORIGINAL_INPUT_READY"},
            "selection":{"ordinary":ordinary,"amendments":amendments,"latest_def14a":p,"def14a_amendments":proxy_amendments or []}}


class NormalTextInputV2SelectionTest(unittest.TestCase):
    def test_public_api_does_not_accept_an_answer_or_filing_selector(self):
        self.assertEqual({"repo_root","company_id","metric_id"},set(inspect.signature(prepare_normal_business_text_input).parameters))

    def test_current_proxy_is_selected_after_earlier_annual_amendment(self):
        g=governance(amendments=[filing("10-K/A","2026-02-06",3)])
        p=_source_plan(governance_binding=g,metric_id="C02")
        self.assertEqual(["10-K","DEF 14A"],[f["form"] for f in p["text_filings"]])
        self.assertEqual("EARLIER_ANNUAL_AMENDMENTS_RETAINED",p["amendment_status"])
        self.assertFalse(p["current_latest_verified"])

    def test_missing_current_proxy_uses_unique_amendment_but_requires_raw_part_iii(self):
        g=governance(amendments=[filing("10-K/A","2026-04-24",3)])
        g["selection"]["latest_def14a"]["filingDate"]="2025-03-27"
        p=_source_plan(governance_binding=g,metric_id="C02")
        self.assertTrue(p["requires_part_iii_proof"])
        self.assertEqual("SAME_PERIOD_PART_III_ANNUAL_AMENDMENT",p["basis"])
        self.assertEqual("2025-03-27",p["prior_proxy_not_used"]["filingDate"])
        self.assertNotEqual(p["prior_proxy_not_used"]["accessionNumber"],p["text_filings"][1]["accessionNumber"])

    def test_proxy_revision_later_annual_revision_and_multiple_amendments_do_not_fallback(self):
        cases=[governance(proxy_amendments=[filing("DEF 14A/A","2026-04-10",4)]),
               governance(amendments=[filing("10-K/A","2026-04-24",3)]),
               governance(proxy=False,amendments=[filing("10-K/A","2026-03-24",3),filing("10-K/A","2026-04-24",4)])]
        for g in cases:
            with self.subTest(g=g),self.assertRaises(ValueError):_source_plan(governance_binding=g,metric_id="C02")

    def test_same_day_unordered_cross_form_sources_are_ambiguous(self):
        g=governance(amendments=[filing("10-K/A","2026-03-27",3)])
        with self.assertRaisesRegex(ValueError,"SAME_DAY_ORDER_NOT_PROVEN"):_source_plan(governance_binding=g,metric_id="C02")

    def test_d02_preserves_original_and_explicit_unprocessed_amendments(self):
        g=governance(amendments=[filing("10-K/A","2026-04-24",3)])
        p=_source_plan(governance_binding=g,metric_id="D02")
        self.assertEqual([g["selection"]["ordinary"]],p["text_filings"])
        self.assertEqual("AMENDMENT_PROCESSING_REQUIRED",p["amendment_status"])
        self.assertFalse(p["current_latest_verified"])

    def test_history_snapshot_conflict_cannot_supply_a_current_selected_filing(self):
        p=_source_plan(governance_binding=governance(),metric_id="C02")
        for f in p["text_filings"]:f["metadata_origin"]={"inventory_name":"CIK0000012345.json"}
        refs=[{"source_role":"sec_submissions_inventory","document_name":"CIK0000012345.json"}]
        _check_selected_metadata_scope(plan=p,references=refs)
        p["text_filings"][1]["metadata_origin"]["inventory_name"]="CIK0000012345-submissions-001.json"
        with self.assertRaisesRegex(ValueError,"OUTSIDE_CURRENT_METADATA_BLOCK"):_check_selected_metadata_scope(plan=p,references=refs)


class NormalTextInputV2PartIIITest(unittest.TestCase):
    def call(self,body,*,truncate=False,period="2025-12-31"):
        f=filing("10-K/A","2026-04-24",3)
        raw=annual(body,form="10-K/A",period=period)
        if truncate:raw=raw.replace(b"</body></html>",b"")
        blob,ref,raw=source(raw,accession=f["accessionNumber"],filename=f["primaryDocument"])
        return _part_iii_proof(source=ref,blob=blob,raw=raw,filing=f,company_id="sample_entity",cik="12345",period_end="2025-12-31")

    def test_actual_part_and_item_body_are_required(self):
        body='<h2>PART III</h2><h2>Item 10. Directors, Executive Officers and Corporate Governance</h2><p>'+('The Board provides information on directors and committees. '*5)+'</p><h2>PART IV</h2>'
        proof=self.call(body)
        self.assertEqual("10",proof["range"]["item_headings"][0]["item"])
        for changes in (body.replace("PART III","PART II"),'<p><b>PART III</b></p><p>Item 10. Directors</p><p>4</p>',body):
            with self.subTest(changes=changes),self.assertRaises(ValueError):self.call(changes,truncate=changes==body)
        with self.assertRaisesRegex(ValueError,"PERIOD"):self.call(body,period="2024-12-31")


class NormalTextInputV2ActualBoundaryTest(unittest.TestCase):
    def test_actual_normal_preparation_uses_proofs_without_derived_answers_or_network(self):
        old_io,old_open=io.open,builtins.open
        forbidden={"latest_filings_inventory.csv","accession_materials_inventory.csv","metrics_matrix.csv","metric_evidence.csv","governance_signals.csv"}
        def guarded(opener):
            def call(file,*args,**kwargs):
                if isinstance(file,(str,Path)) and Path(file).name in forbidden:raise AssertionError("derived answers read")
                return opener(file,*args,**kwargs)
            return call
        with patch("io.open",guarded(old_io)),patch("builtins.open",guarded(old_open)),patch.object(socket.socket,"connect",side_effect=AssertionError("network forbidden")),patch.object(_Sources,"auditor_filing",side_effect=AssertionError("unrelated C04 dependency")):
            out=prepare_normal_business_text_input(repo_root=REPO_ROOT,company_id="marriott_international",metric_id="C02")
        self.assertEqual("PREPARED",out["input_status"])
        self.assertEqual("CURRENT_SAME_CIK_DEF14A",out["input_binding"]["source_plan"]["basis"])
        self.assertEqual("SOURCE_TEXT_READY",prepare_business_text_sources(metric_id="C02",**out["text_arguments"])["capability_status"])
        self.assertTrue(all(p["request_attempt_id"].startswith("request:attempt:") for p in out["source_proofs"]))
        self.assertIn("LEGACY_WORKING_LOCATOR",{p["request_locator_kind"] for p in out["source_proofs"]})
        self.assertEqual("PREEXISTING_SAVED_ACQUISITIONS_ONLY",out["admission"]["source_credit"])
        self.assertFalse(out["input_binding"]["current_latest_verified"])
        self.assertEqual([],out["source_set_manifests"])
        self.assertEqual(4,len(out["source_proofs"]))
        self.assertEqual(8,len(out["records"]))
        self.assertEqual({"sec_submissions_inventory","target_primary","companyfacts","governance_proxy"},{s["source_role"] for s in out["source_references"]})

    def test_selected_proxy_failure_blocks_instead_of_falling_back(self):
        original=_Sources.primary
        seen=[]
        def failing(reader,filing,**kwargs):
            seen.append(filing["form"])
            if filing["form"]=="DEF 14A":raise AnnualUpdateError("LATEST_SOURCE_REQUEST_FAILED: TEST_ONLY_SELECTED_PROXY")
            return original(reader,filing,**kwargs)
        with patch.object(_Sources,"primary",new=failing):
            out=prepare_normal_business_text_input(repo_root=REPO_ROOT,company_id="marriott_international",metric_id="C02")
        self.assertEqual("BLOCKED",out["input_status"])
        self.assertIsNone(out["text_arguments"])
        self.assertEqual(["10-K","DEF 14A"],seen)
        self.assertIn("LATEST_SOURCE_REQUEST_FAILED",out["input_binding"]["limitations"][0]["reason"])
        self.assertEqual("SOURCE_ACCESS_FAILED",out["input_binding"]["limitations"][0]["category"])

    def test_minimal_import_still_requires_complete_current_metadata(self):
        out=prepare_normal_business_text_input(repo_root=REPO_ROOT,company_id="marriott_international",metric_id="D02")
        self.assertEqual(3,len(out["source_proofs"]))
        paths={"config/company_registry.csv","evidence/requests_log.csv","evidence/requests_log_manifest.json"}
        for proof in out["source_proofs"]:paths.update([proof["request_repo_relative_path"],proof["request_headers_repo_relative_path"]])
        with tempfile.TemporaryDirectory() as name:
            root=Path(name)
            for relative in paths:
                target=root/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(REPO_ROOT/relative,target)
            rebuilt=prepare_normal_business_text_input(repo_root=root,company_id="marriott_international",metric_id="D02")
            self.assertEqual(out["input_binding"],rebuilt["input_binding"])
            inventory=next(p for p in out["source_proofs"] if p["source_url"].startswith("https://data.sec.gov/submissions/"))
            (root/inventory["request_repo_relative_path"]).unlink()
            with self.assertRaisesRegex(BatchWorkflowError,"locator evidence is invalid"):
                prepare_normal_business_text_input(repo_root=root,company_id="marriott_international",metric_id="D02")


if __name__=="__main__":unittest.main()
