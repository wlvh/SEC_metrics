"""The accession route reads a report whose FASB namespaces carry the release date.

Releases of US GAAP and SRT through 2021 are named with the date after the
year (``us-gaap/2021-01-31``); the accession policy spells each namespace as
the year alone, so JPMorgan's FY2021 capital ratios stopped at
NORMAL_ACCESSION_STANDARD_NAMESPACE_CHANGED and Salesforce's FY2022 RPO at
NORMAL_ACCESSION_CONCEPT_NAMESPACE_NOT_APPROVED. These cases hold
``historical_accession_results.inspect_with_dated_releases`` to exactly that
difference, on the saved reports: the frozen inspection is what answers a
report whose namespaces are the year alone, record for record; the
release-aware rerun happens only after the frozen inspection refused for a
release, says so, and accepts the date form and nothing else. Zero calls.
"""
import copy
import hashlib
import json
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.saved_filings import saved_filing
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext import historical_accession_results as route
from vnext import historical_dei
from vnext.canonical import content_hash
from vnext.normal_accession_results import (NormalAccessionError, inspect_ordinary_accession_facts,
                                            resolve_ordinary_accession_metrics)
from vnext.sources import source_reference_record

POLICY = json.loads((ROOT / "config/normal_accession_metrics_v1.json").read_text(encoding="utf-8"))
CATALOG = json.loads((ROOT / "catalog/deterministic_metrics.json").read_text(encoding="utf-8"))


def _rebound(case, raw):
    """The latest case's source set with the reference rebound to other saved bytes."""
    old = next(r for r in case["source_records"]
               if r["record_type"] == "SOURCE_REFERENCE" and r["source_role"] == "target_primary")
    blob = next(r for r in case["source_records"]
                if r["record_type"] == "RAW_BLOB" and r["raw_asset_id"] == old["raw_asset_id"])
    changed = {**blob, "raw_asset_id": "sha256:" + hashlib.sha256(raw).hexdigest(),
               "byte_length": len(raw)}
    reference = source_reference_record(
        raw_blob=changed, company_id=old["company_id"], source_url=old["source_url"],
        accession=old["accession"], document_name=old["document_name"],
        source_role=old["source_role"], request_attempt_id=old["request_attempt_id"])
    manifest = {**case["source_set"], "ordered_source_reference_ids": [reference["source_reference_id"]]}
    manifest["source_set_manifest_id"] = content_hash(
        value={k: v for k, v in manifest.items() if k != "source_set_manifest_id"})
    return reference, manifest


class OnTheSavedReportsTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with original_sources_only():
            cls.cases = {company: resolve_ordinary_accession_metrics(repo_root=ROOT, company_id=company)
                         for company in ("jpmorgan_chase", "salesforce")}

    def _arguments(self, company, file_name, metric, period_end, cik):
        raw, _ = saved_filing(file_name)
        reference, manifest = _rebound(self.cases[company], raw)
        return dict(raw_bytes=raw, source_reference=reference, source_set_manifest=manifest,
                    expected_cik=cik, period_end=period_end, route=CATALOG["metrics"][metric],
                    metric_id=metric, policy=POLICY)

    def test_the_fy2021_capital_ratios_are_read_after_the_frozen_refusal(self):
        for metric in ("A01", "A02"):
            arguments = self._arguments("jpmorgan_chase", "jpm-20211231.htm", metric,
                                        "2021-12-31", "19617")
            with self.subTest(metric), original_sources_only():
                self.assertIn(b"http://fasb.org/srt/2021-01-31", arguments["raw_bytes"])
                with self.assertRaisesRegex(NormalAccessionError,
                                            "^NORMAL_ACCESSION_STANDARD_NAMESPACE_CHANGED$"):
                    inspect_ordinary_accession_facts(**arguments)
                inspection, policy = route.inspect_with_dated_releases(**arguments)
                self.assertEqual("SOURCE_SCOPE_PROVEN", inspection["status"])
                self.assertEqual(["NORMAL_ACCESSION_STANDARD_NAMESPACE_CHANGED"],
                                 inspection["dated_release_successor"]["frozen_refusal"])
                self.assertEqual(route.release_aware_policy(POLICY), policy)
                self.assertEqual(1, len({c["value"] for c in inspection["selected_claims"]}))

    def test_the_fy2022_rpo_is_read_after_the_frozen_refusal(self):
        arguments = self._arguments("salesforce", "crm-20220131.htm", "B12", "2022-01-31", "1108524")
        with original_sources_only():
            frozen = inspect_ordinary_accession_facts(**arguments)
            self.assertEqual("UNRESOLVED", frozen["status"])
            self.assertIn("NORMAL_ACCESSION_CONCEPT_NAMESPACE_NOT_APPROVED",
                          {c["reason"] for c in frozen["conflicts"]})
            inspection, _ = route.inspect_with_dated_releases(**arguments)
        self.assertEqual("SOURCE_SCOPE_PROVEN", inspection["status"])
        self.assertEqual(["NORMAL_ACCESSION_CONCEPT_NAMESPACE_NOT_APPROVED"],
                         inspection["dated_release_successor"]["frozen_refusal"])

    def test_a_year_alone_report_is_the_frozen_inspection(self):
        for company, file_name, metric, period_end, cik in (
                ("jpmorgan_chase", "jpm-20251231.htm", "A01", "2025-12-31", "19617"),
                ("salesforce", "crm-20260131.htm", "B12", "2026-01-31", "1108524")):
            arguments = self._arguments(company, file_name, metric, period_end, cik)
            with self.subTest(company), original_sources_only():
                frozen = inspect_ordinary_accession_facts(**arguments)
                inspection, policy = route.inspect_with_dated_releases(**arguments)
                self.assertEqual(frozen, inspection)
                self.assertIs(POLICY, policy)

    def test_a_namespace_that_is_not_a_fasb_release_is_still_refused(self):
        arguments = self._arguments("jpmorgan_chase", "jpm-20211231.htm", "A01", "2021-12-31", "19617")
        arguments["raw_bytes"] = arguments["raw_bytes"].replace(
            b"http://fasb.org/srt/2021-01-31", b"http://fasb.org/srt/2021-1-31")
        reference, manifest = _rebound(self.cases["jpmorgan_chase"], arguments["raw_bytes"])
        arguments.update(source_reference=reference, source_set_manifest=manifest)
        with original_sources_only(), self.assertRaisesRegex(
                NormalAccessionError, "^NORMAL_ACCESSION_STANDARD_NAMESPACE_CHANGED$"):
            route.inspect_with_dated_releases(**arguments)

    def test_another_refusal_is_the_frozen_one(self):
        arguments = self._arguments("jpmorgan_chase", "jpm-20211231.htm", "A01", "2021-12-31", "19617")
        arguments["source_reference"] = copy.deepcopy(arguments["source_reference"])
        arguments["source_reference"]["raw_asset_id"] = "sha256:" + "0" * 64
        with original_sources_only(), self.assertRaisesRegex(
                NormalAccessionError, "^NORMAL_ACCESSION_SOURCE_BYTES_CHANGED$"):
            route.inspect_with_dated_releases(**arguments)


class TheReleaseAwarePatternTest(unittest.TestCase):

    def test_each_policy_namespace_has_a_release_aware_form(self):
        widened = route.release_aware_policy(POLICY)
        for key, uri in (("us_gaap_namespace_pattern", "http://fasb.org/us-gaap/2021-01-31"),
                         ("srt_namespace_pattern", "https://fasb.org/srt/2020-01-31"),
                         ("dei_namespace_pattern", "http://xbrl.sec.gov/dei/2021q4")):
            with self.subTest(key):
                import re
                self.assertIsNone(re.fullmatch(POLICY[key], uri))
                self.assertIsNotNone(re.fullmatch(widened[key], uri))
        self.assertEqual({k: v for k, v in POLICY.items() if k not in route.NAMESPACE_POLICY_KEYS},
                         {k: v for k, v in widened.items() if k not in route.NAMESPACE_POLICY_KEYS})

    def test_anything_but_a_release_is_still_refused(self):
        import re
        widened = route.release_aware_policy(POLICY)
        for key, uri in (("srt_namespace_pattern", "http://fasb.org/srt/2021q4"),
                         ("srt_namespace_pattern", "http://example.com/srt/2021-01-31"),
                         ("us_gaap_namespace_pattern", "http://fasb.org/us-gaap/2021-01-31x")):
            with self.subTest(uri):
                self.assertIsNone(re.fullmatch(widened[key], uri))

    def test_a_pattern_that_is_not_frozen_is_refused(self):
        with self.assertRaises(historical_dei.HistoricalDeiError):
            historical_dei.release_aware_pattern(r"https?://fasb\.org/srt/.*")


if __name__ == "__main__":
    unittest.main()
