"""The target frame is fixed before it is filled, and it reports rather than executes.

These cases run against the repository's own saved SEC bytes with no network and
no new business call. They assert the frame's shape and its classification rules
rather than a particular set of values, so the matrix cannot silently shrink its
denominator as material arrives.

Two properties they exist to defend:

* a position's first blocking reason is not a statement that it is the only one.
  Counting first blockers as remaining work is what turns "these positions are
  waiting for a document" into a source budget that hides the routes those same
  positions also lack;
* the report does not compute the outcomes it reports. It used to build a second
  candidate, Evidence check, system review decision and Result for every wired
  position, and the two implementations disagreed in both directions.
"""
import hashlib
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.historical_coverage import (WIRED_ACCESSION_METRICS, WIRED_HISTORICAL_METRICS,
                                       CoverageError, build_coverage_matrix,
                                       declared_metric_ids, known_result_defects)
from vnext.historical_run_receipts import RunReceiptError, read_run_receipt

MACYS_PERIOD = "2026-01-31"


def _write_run(root, *, company_id, metric_id, period_end, result_id, quality="EXACT",
               value="1", applicability="APPLICABLE", publication="PUBLISHED",
               status="FROZEN", validation="PASSED", closure="sha256:" + "0" * 64,
               omit_hashes=()):
    """A minimal frozen run directory whose manifest describes its own files.

    Built here rather than copied from a real Run so the receipt reader is
    tested on identity and hashing, not on one archived company. A real FROZEN
    manifest carries all three file hashes, so this writes all three;
    ``omit_hashes`` is how the absent-field case is built deliberately.
    """
    run_dir = Path(root)
    run_dir.mkdir(parents=True, exist_ok=True)
    records = [{"record_type": "METRIC_RESULT", "metric_id": metric_id,
                "result_id": result_id, "value": value, "unit": "USD",
                "quality": quality, "publication": publication, "reason_code": "PASS",
                "applicability": applicability, "period_start": "2025-02-02",
                "period_end": period_end}]
    (run_dir / "records.jsonl").write_text(
        "".join(json.dumps(r, sort_keys=True) + "\n" for r in records), encoding="utf-8")
    (run_dir / "validation.json").write_text(
        json.dumps({"record_type": "VALIDATION_RECEIPT", "status": validation},
                   sort_keys=True) + "\n", encoding="utf-8")
    (run_dir / "review_decisions.jsonl").write_text("", encoding="utf-8")

    def digest(name):
        return hashlib.sha256((run_dir / name).read_bytes()).hexdigest()

    manifest = {
        "record_type": "SUCCESSOR_RUN", "run_id": "run:test:" + result_id[-8:],
        "status": status, "requirement_id": "issue_47_v1",
        "requirement_closure_hash": closure,
        "company_id": company_id,
        "target_period": {"fiscal_year": 2025, "period_start": "2025-02-02",
                          "period_end": period_end},
        "records_file_hash": digest("records.jsonl"),
        "review_decisions_file_hash": digest("review_decisions.jsonl"),
        "validation_file_hash": digest("validation.json")}
    for key in omit_hashes:
        manifest.pop(key)
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
    return run_dir


class HistoricalCoverageTest(unittest.TestCase):
    def test_the_declared_metric_universe_is_checked_against_its_own_total(self):
        metrics, policy = declared_metric_ids(repo_root=ROOT)
        self.assertEqual(39, len(metrics))
        self.assertEqual(policy["declared_issue_metric_count"], len(metrics))
        for pending in policy["pending_metric_ids"]:
            self.assertIn(pending, metrics)
        self.assertEqual(sorted(set(metrics)), metrics)

    def test_every_target_position_carries_exactly_one_classified_status(self):
        with original_sources_only():
            matrix = build_coverage_matrix(repo_root=ROOT, company_ids=["macys"], years=5)
        self.assertEqual(39 * 5, matrix["target_frame_positions"])
        self.assertEqual(39 * 5, matrix["enumerated_positions"])
        self.assertEqual(3, matrix["schema_version"])
        self.assertEqual(sum(matrix["status_counts"].values()), matrix["enumerated_positions"])
        self.assertEqual({"provider": 0, "paid": 0, "sec": 0}, matrix["calls"])
        self.assertFalse(matrix["native_run_created"])
        self.assertFalse(matrix["business_execution_invoked"])
        self.assertFalse(matrix["runs_root_supplied"])
        self.assertEqual(0, matrix["run_receipts_read"])
        seen = {(p["company_id"], p["report_end"], p["metric_id"]) for p in matrix["positions"]}
        self.assertEqual(len(seen), len(matrix["positions"]))
        established = [p for p in matrix["company_reports"][0]["periods"]
                       if p["period_status"] == "PERIOD_ESTABLISHED"]
        self.assertEqual(1, len(established))
        self.assertEqual(MACYS_PERIOD, established[0]["report_end"])
        missing = [p for p in matrix["positions"]
                   if p["status"] == "SOURCE_MISSING_TARGET_ORIGINAL"]
        self.assertEqual(39 * 4, len(missing))
        # Of those 156 positions whose first blocker is a missing document, the
        # unwired ones have no historical route either. Acquiring all 156
        # documents would fill only the wired share.
        also_unwired = [p for p in missing if not p["historical_route_implemented"]]
        self.assertEqual((39 - len(WIRED_HISTORICAL_METRICS)) * 4, len(also_unwired))
        self.assertEqual(len(also_unwired), matrix["positions_missing_source_and_route"])
        self.assertTrue(matrix["first_blocking_reason_is_not_the_only_blocker"])
        self.assertEqual({"target_period_established": 39 * 5, "target_original_saved": 39,
                          "run_receipt_hashes_verified": 0,
                          "historical_route_implemented": len(WIRED_HISTORICAL_METRICS) * 5,
                          "native_run_receipt": 0, "known_content_defect": 0,
                          "business_content_accepted": 0, "verified_outcome": 0},
                         matrix["dimension_counts"])
        # Implemented and not run is its own state. It is neither an
        # unimplemented route nor a disclosure claim.
        resolved = [p for p in matrix["positions"] if p["report_end"] == MACYS_PERIOD]
        wired = [p for p in resolved if p["metric_id"] in WIRED_HISTORICAL_METRICS]
        self.assertEqual(len(WIRED_HISTORICAL_METRICS), len(wired))
        self.assertEqual({"ROUTE_IMPLEMENTED_NOT_RUN"}, {p["status"] for p in wired})
        unwired = [p for p in resolved if p["metric_id"] not in WIRED_HISTORICAL_METRICS]
        self.assertEqual({"HISTORICAL_ROUTE_NOT_WIRED"}, {p["status"] for p in unwired})

    def test_the_report_entry_computes_no_metric_outcome(self):
        """The acceptance condition for removing the second execution chain.

        Not "it looks read-only" but "it still works when the things that
        compute outcomes cannot run": the three metric resolvers, both text
        candidate factories and the system review decision factory are made to
        raise, and the report must still be produced.

        This deliberately does not forbid every HTML parse. Establishing which
        period a filing covers reads that filing's own DEI, so the plan layer
        parses source bytes and always did; forbidding `HTMLParser.feed`
        outright fails here for a reason that is about cost, not about a second
        execution chain. That cost is measured and reduced separately.
        """
        from vnext import historical_accession_results, historical_results
        from vnext import historical_text_results, historical_zero_ai_results
        from vnext import review, text_results_v2

        def refuse(*args, **kwargs):
            raise AssertionError("the report entry computed a metric outcome")

        targets = ((historical_results, "resolve_historical_companyfacts_metrics"),
                   (historical_zero_ai_results, "resolve_historical_zero_ai_metric"),
                   (historical_accession_results, "resolve_historical_accession_metrics"),
                   (historical_text_results, "create_deterministic_text_candidate"),
                   (text_results_v2, "create_deterministic_text_candidate"),
                   (review, "create_system_review_decision"))
        with original_sources_only():
            with patch.multiple(historical_results,
                                resolve_historical_companyfacts_metrics=refuse), \
                    patch.object(historical_zero_ai_results,
                                 "resolve_historical_zero_ai_metric", refuse), \
                    patch.object(historical_accession_results,
                                 "resolve_historical_accession_metrics", refuse), \
                    patch.object(historical_text_results,
                                 "create_deterministic_text_candidate", refuse), \
                    patch.object(text_results_v2,
                                 "create_deterministic_text_candidate", refuse), \
                    patch.object(review, "create_system_review_decision", refuse):
                matrix = build_coverage_matrix(repo_root=ROOT, company_ids=["macys"], years=5)
        self.assertEqual(len(targets), 6)
        self.assertEqual(39 * 5, matrix["enumerated_positions"])
        self.assertFalse(matrix["business_execution_invoked"])

    def test_a_recorded_exact_result_is_not_a_verified_outcome_when_a_defect_names_it(self):
        """EXACT is the result's own quality. Acceptance is a separate state.

        The Pfizer D02 Result that held executive-officer biography was EXACT,
        PUBLISHED and PASS, so a report keyed on quality counted it. This keeps
        the recorded status and withdraws it from the verified count.
        """
        defects = known_result_defects(repo_root=ROOT)
        self.assertTrue(defects)
        with TemporaryDirectory(prefix="coverage-receipts-") as temporary:
            root = Path(temporary)
            _write_run(root / "run-a", company_id="macys", metric_id="B01",
                       period_end=MACYS_PERIOD, result_id="sha256:" + "a" * 64)
            _write_run(root / "run-b", company_id="macys", metric_id="B02",
                       period_end=MACYS_PERIOD, result_id="sha256:" + "b" * 64)
            register = {"record_type": "KNOWN_RESULT_DEFECT_REGISTER", "schema_version": 1,
                        "defects": [{"defect_id": "TEST_DEFECT", "company_id": "macys",
                                     "metric_id": "B02", "period_end": MACYS_PERIOD,
                                     "result_id": "sha256:" + "b" * 64}]}
            with original_sources_only(), \
                    patch("vnext.historical_coverage.known_result_defects",
                          return_value=register["defects"]):
                matrix = build_coverage_matrix(repo_root=ROOT, company_ids=["macys"],
                                               years=5, runs_root=root)
        self.assertEqual(2, matrix["run_receipts_read"])
        rows = {p["metric_id"]: p for p in matrix["positions"]
                if p["report_end"] == MACYS_PERIOD}
        self.assertEqual("VALUE_EXACT", rows["B01"]["status"])
        self.assertIsNone(rows["B01"]["known_content_defect"])
        self.assertTrue(rows["B01"]["verified_outcome"])
        # Same recorded quality, withdrawn by the register rather than relabelled.
        self.assertEqual("VALUE_EXACT", rows["B02"]["status"])
        self.assertEqual("TEST_DEFECT", rows["B02"]["known_content_defect"])
        self.assertFalse(rows["B02"]["verified_outcome"])
        self.assertTrue(rows["B02"]["native_run_receipt"])
        # No receipt ever amounts to business acceptance.
        self.assertFalse(any(p["business_content_accepted"] for p in matrix["positions"]))
        self.assertEqual(2, matrix["dimension_counts"]["native_run_receipt"])
        self.assertEqual(1, matrix["dimension_counts"]["verified_outcome"])

    def test_a_missing_identity_hash_is_not_a_passed_check(self):
        """"Found no conflict" and "was not asked to check" are different answers.

        The reader skipped an absent hash field and then reported
        `manifest_file_hashes_verified: True` regardless, so a manifest that
        supplied nothing to check read as fully verified.
        """
        with TemporaryDirectory(prefix="coverage-absent-") as temporary:
            root = Path(temporary)
            frozen = _write_run(root / "frozen", company_id="macys", metric_id="B01",
                                period_end=MACYS_PERIOD, result_id="sha256:" + "c" * 64,
                                omit_hashes=("review_decisions_file_hash",))
            with self.assertRaises(RunReceiptError) as absent:
                read_run_receipt(run_dir=frozen)
            self.assertEqual("RUN_RECEIPT_HASH_ABSENT:review_decisions_file_hash",
                             str(absent.exception))
            # An OPEN Run may legitimately lack them; it is recorded as
            # unverified rather than refused, and it is not a verified outcome.
            opened = _write_run(root / "open", company_id="macys", metric_id="B01",
                                period_end=MACYS_PERIOD, result_id="sha256:" + "d" * 64,
                                status="OPEN", omit_hashes=("validation_file_hash",))
            receipt = read_run_receipt(run_dir=opened)
            self.assertFalse(receipt["manifest_file_hashes_verified"])
            self.assertEqual(["validation.json"], receipt["unverified_files"])
            self.assertEqual(["records.jsonl", "review_decisions.jsonl"],
                             receipt["verified_files"])

    def test_an_open_or_unvalidated_run_is_not_a_verified_outcome(self):
        """FROZEN and PASSED are what make a recorded value a checked one."""
        with TemporaryDirectory(prefix="coverage-states-") as temporary:
            root = Path(temporary)
            _write_run(root / "run-open", company_id="macys", metric_id="B01",
                       period_end=MACYS_PERIOD, result_id="sha256:" + "e" * 64,
                       status="OPEN")
            _write_run(root / "run-failed", company_id="macys", metric_id="B02",
                       period_end=MACYS_PERIOD, result_id="sha256:" + "f" * 64,
                       validation="FAILED")
            _write_run(root / "run-good", company_id="macys", metric_id="B03",
                       period_end=MACYS_PERIOD, result_id="sha256:" + "1" * 64)
            with original_sources_only():
                matrix = build_coverage_matrix(repo_root=ROOT, company_ids=["macys"],
                                               years=5, runs_root=root)
        rows = {p["metric_id"]: p for p in matrix["positions"]
                if p["report_end"] == MACYS_PERIOD}
        for metric in ("B01", "B02", "B03"):
            # The recorded status is kept in every case; only the verified
            # count moves, so nothing is relabelled to make the number work.
            self.assertEqual("VALUE_EXACT", rows[metric]["status"])
            self.assertTrue(rows[metric]["native_run_receipt"])
        self.assertFalse(rows["B01"]["verified_outcome"])
        self.assertFalse(rows["B02"]["verified_outcome"])
        self.assertTrue(rows["B03"]["verified_outcome"])
        self.assertEqual(1, matrix["dimension_counts"]["verified_outcome"])

    def test_the_same_result_recorded_twice_is_one_outcome_not_an_ambiguity(self):
        """A dependency metric's result is recorded in two Runs, and that is fine.

        B03 consumes B01, so the B03 Run carries B01's result as well as its
        own and the coordinate has two receipts under one closure. Measured on
        the real batch: both carry the same result_id. Calling that ambiguous
        withdrew four correct outcomes, so the test is on the result and not on
        the count.
        """
        with TemporaryDirectory(prefix="coverage-same-") as temporary:
            root = Path(temporary)
            for name in ("run-b01", "run-b03-carrying-b01"):
                _write_run(root / name, company_id="macys", metric_id="B01",
                           period_end=MACYS_PERIOD, result_id="sha256:" + "4" * 64,
                           value="4444")
            with original_sources_only():
                matrix = build_coverage_matrix(repo_root=ROOT, company_ids=["macys"],
                                               years=5, runs_root=root)
        row = next(p for p in matrix["positions"]
                   if p["report_end"] == MACYS_PERIOD and p["metric_id"] == "B01")
        self.assertEqual("VALUE_EXACT", row["status"])
        self.assertEqual("4444", row["detail"]["value"])
        self.assertEqual(2, row["run_receipt_count"])
        self.assertTrue(row["verified_outcome"])

    def test_two_closures_for_one_coordinate_are_reported_not_picked(self):
        """found[-1] took whichever directory sorted last and called it newest.

        The two receipts here disagree on the value, and the one that sorts
        last is the one the caller is not asking about, so an alphabetical pick
        is visible rather than merely unproven.
        """
        old_closure, new_closure = "sha256:" + "0" * 64, "sha256:" + "9" * 64
        with TemporaryDirectory(prefix="coverage-closures-") as temporary:
            root = Path(temporary)
            _write_run(root / "run-a-new", company_id="macys", metric_id="B01",
                       period_end=MACYS_PERIOD, result_id="sha256:" + "2" * 64,
                       value="222", closure=new_closure)
            _write_run(root / "run-z-old", company_id="macys", metric_id="B01",
                       period_end=MACYS_PERIOD, result_id="sha256:" + "3" * 64,
                       value="333", closure=old_closure)
            with original_sources_only():
                ambiguous = build_coverage_matrix(repo_root=ROOT, company_ids=["macys"],
                                                  years=5, runs_root=root)
                selected = build_coverage_matrix(
                    repo_root=ROOT, company_ids=["macys"], years=5, runs_root=root,
                    requirement_closure_hash=new_closure)
                absent = build_coverage_matrix(
                    repo_root=ROOT, company_ids=["macys"], years=5, runs_root=root,
                    requirement_closure_hash="sha256:" + "7" * 64)

        def row(matrix):
            return next(p for p in matrix["positions"]
                        if p["report_end"] == MACYS_PERIOD and p["metric_id"] == "B01")

        self.assertEqual("RUN_RECEIPT_AMBIGUOUS", row(ambiguous)["status"])
        self.assertEqual(2, row(ambiguous)["run_receipt_count"])
        self.assertFalse(row(ambiguous)["verified_outcome"])
        self.assertEqual(sorted([old_closure, new_closure]),
                         row(ambiguous)["detail"]["requirement_closure_hashes"])

        self.assertEqual("VALUE_EXACT", row(selected)["status"])
        self.assertEqual("222", row(selected)["detail"]["value"])
        self.assertEqual(new_closure, row(selected)["requirement_closure_hash"])
        self.assertTrue(row(selected)["verified_outcome"])
        self.assertEqual(new_closure, selected["requested_requirement_closure_hash"])

        # A closure nothing ran is not a failure of the route and not a
        # disclosure claim; it is that closure not having run this position.
        self.assertEqual("ROUTE_IMPLEMENTED_NOT_RUN", row(absent)["status"])
        self.assertEqual(2, row(absent)["detail"]["receipts_under_other_closures"])
        self.assertFalse(row(absent)["verified_outcome"])

    def test_a_repaired_coordinate_defect_stops_withdrawing_the_repaired_result(self):
        """A defect that has been fixed must not keep withdrawing the fix.

        The item-bound entry named a coordinate that could not produce a result
        at all. Once the capacity was raised the coordinate produced the
        correct 92-excerpt result, and the entry went on withdrawing it -
        measured on the real batch, where Pfizer's D02 read as defective while
        being exactly what the entry had asked for.
        """
        register = [
            {"defect_id": "REPAIRED", "company_id": "macys", "metric_id": "B01",
             "period_end": MACYS_PERIOD, "result_id": None,
             "repair_state": "RULE_FIXED_RESULT_RECOMPUTED"},
            {"defect_id": "OPEN", "company_id": "macys", "metric_id": "B02",
             "period_end": MACYS_PERIOD, "result_id": None,
             "repair_state": "RULE_FIXED_RESULT_NOT_YET_RECOMPUTED"},
            # A named result stays withdrawn whatever the repair state says:
            # it points at one bad result, not at a coordinate.
            {"defect_id": "NAMED", "company_id": "macys", "metric_id": "B03",
             "period_end": MACYS_PERIOD, "result_id": "sha256:" + "5" * 64,
             "repair_state": "RULE_FIXED_RESULT_RECOMPUTED"},
        ]
        with TemporaryDirectory(prefix="coverage-repaired-") as temporary:
            root = Path(temporary)
            for metric, result_id in (("B01", "a"), ("B02", "b"), ("B03", "5")):
                _write_run(root / ("run-" + metric), company_id="macys", metric_id=metric,
                           period_end=MACYS_PERIOD, result_id="sha256:" + result_id * 64)
            with original_sources_only(), \
                    patch("vnext.historical_coverage.known_result_defects",
                          return_value=register):
                matrix = build_coverage_matrix(repo_root=ROOT, company_ids=["macys"],
                                               years=5, runs_root=root)
        rows = {p["metric_id"]: p for p in matrix["positions"]
                if p["report_end"] == MACYS_PERIOD}
        self.assertIsNone(rows["B01"]["known_content_defect"])
        self.assertTrue(rows["B01"]["verified_outcome"])
        self.assertEqual("OPEN", rows["B02"]["known_content_defect"])
        self.assertFalse(rows["B02"]["verified_outcome"])
        self.assertEqual("NAMED", rows["B03"]["known_content_defect"])
        self.assertFalse(rows["B03"]["verified_outcome"])

    def test_an_edited_run_directory_is_not_the_run_its_manifest_describes(self):
        with TemporaryDirectory(prefix="coverage-receipts-") as temporary:
            run_dir = _write_run(Path(temporary) / "run", company_id="macys",
                                 metric_id="B01", period_end=MACYS_PERIOD,
                                 result_id="sha256:" + "c" * 64)
            self.assertIsNotNone(read_run_receipt(run_dir=run_dir))
            (run_dir / "records.jsonl").write_text("{}\n", encoding="utf-8")
            with self.assertRaises(RunReceiptError) as changed:
                read_run_receipt(run_dir=run_dir)
        self.assertEqual("RUN_RECEIPT_FILE_CHANGED:records.jsonl", str(changed.exception))

    def test_one_route_s_limitation_does_not_remove_the_metrics_another_resolved(self):
        """Adapters fail separately because they answer separate questions.

        Southwest's most recent annual period carries a 10-K/A. The Company
        Facts and revenue routes both refuse an amended target, and that refusal
        says nothing about whether an instant fact can be read from the selected
        filing's own inline XBRL. The property lives in the resolvers, so it is
        asserted by calling them, not by making the report run them.
        """
        from vnext.historical_accession_results import resolve_historical_accession_metrics
        from vnext.historical_results import resolve_historical_companyfacts_metrics
        from vnext.historical_zero_ai_results import resolve_historical_zero_ai_metric
        from vnext.normal_period_selection import resolve_period_selection

        with original_sources_only():
            selection = resolve_period_selection(repo_root=ROOT,
                                                 company_id="southwest_airlines",
                                                 report_end="2025-12-31")
            with self.assertRaises(ValueError) as facts:
                resolve_historical_companyfacts_metrics(repo_root=ROOT,
                                                        company_id="southwest_airlines",
                                                        period_selection=selection)
            with self.assertRaises(ValueError) as revenue:
                resolve_historical_zero_ai_metric(repo_root=ROOT,
                                                  company_id="southwest_airlines",
                                                  metric_id="B01",
                                                  period_selection=selection)
            instants = resolve_historical_accession_metrics(repo_root=ROOT,
                                                            company_id="southwest_airlines",
                                                            period_selection=selection)
        self.assertEqual("HISTORICAL_COMPANYFACTS_AMENDED_TARGET_NOT_IMPLEMENTED",
                         str(facts.exception))
        self.assertEqual("HISTORICAL_ZERO_AI_AMENDED_TARGET_NOT_IMPLEMENTED",
                         str(revenue.exception))
        self.assertEqual("IMPLEMENTATION_GAP",
                         getattr(revenue.exception, "category", "IMPLEMENTATION_GAP"))
        # The instant route ran on the same period and its own rules decided it.
        self.assertEqual(set(WIRED_ACCESSION_METRICS), set(instants["metrics"]))
        for metric_id in WIRED_ACCESSION_METRICS:
            self.assertEqual("N_A_STRUCTURAL",
                             "N_A_STRUCTURAL"
                             if instants["metrics"][metric_id]["result"]["applicability"]
                             != "APPLICABLE" else "APPLICABLE")

    def test_an_unknown_company_set_is_an_explicit_refusal(self):
        with original_sources_only():
            with self.assertRaises(CoverageError) as unknown:
                build_coverage_matrix(repo_root=ROOT, company_ids=["not_a_company"], years=1)
            with self.assertRaises(CoverageError) as duplicated:
                build_coverage_matrix(repo_root=ROOT, company_ids=["macys", "macys"], years=1)
        self.assertEqual("COVERAGE_COMPANY_SET_INVALID", str(unknown.exception))
        self.assertEqual("COVERAGE_COMPANY_SET_INVALID", str(duplicated.exception))


if __name__ == "__main__":
    unittest.main()
