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
from vnext.historical_coverage import (STRUCTURAL_APPLICABILITY_METRICS,
                                       WIRED_ACCESSION_METRICS, WIRED_HISTORICAL_METRICS,
                                       CoverageError, build_coverage_matrix,
                                       declared_metric_ids, known_result_defects)
from vnext.historical_run_receipts import RunReceiptError, read_run_receipt
from vnext.normal_period_selection import resolve_period_selection

MACYS_PERIOD = "2026-01-31"
_SELECTION = {}


def _selection_id():
    """The period selection this coordinate really resolves to.

    A bundle carries the selection the renderer used, and the report now
    compares it with the one the coordinate resolves to. A fixture that wrote
    a placeholder there would be testing the comparison against a value no
    coordinate has, so it reads the real one once and caches it.
    """
    if not _SELECTION:
        with original_sources_only():
            _SELECTION["id"] = resolve_period_selection(
                repo_root=ROOT, company_id="macys",
                report_end=MACYS_PERIOD)["selection_id"]
    return _SELECTION["id"]


def _write_run(root, *, company_id, metric_id, period_end, result_id, quality="EXACT",
               value="1", applicability="APPLICABLE", publication="PUBLISHED",
               status="FROZEN", validation="PASSED", closure="sha256:" + "0" * 64,
               omit_hashes=(), run_id=None, row_bundle=None, extra_results=(),
               row_bundle_metric="B01", row_bundle_overrides=None):
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
    # A Run records the results it consumed as well as the one it targeted -
    # B01's result appears in the B01 Run and again in the B03 Run - so a
    # fixture has to be able to hold more than one.
    for other_metric, other_result in extra_results:
        records.append({**records[0], "metric_id": other_metric,
                        "result_id": other_result})
    (run_dir / "records.jsonl").write_text(
        "".join(json.dumps(r, sort_keys=True) + "\n" for r in records), encoding="utf-8")
    (run_dir / "validation.json").write_text(
        json.dumps({"record_type": "VALIDATION_RECEIPT", "status": validation},
                   sort_keys=True) + "\n", encoding="utf-8")
    (run_dir / "review_decisions.jsonl").write_text("", encoding="utf-8")

    def digest(name):
        return hashlib.sha256((run_dir / name).read_bytes()).hexdigest()

    manifest = {
        "record_type": "SUCCESSOR_RUN",
        "run_id": run_id or ("run:test:" + result_id[-8:]),
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
    if row_bundle is not None:
        _write_row_bundle(run_dir, run_id=manifest["run_id"], status=status,
                          result_id=row_bundle, metric_id=row_bundle_metric,
                          overrides=row_bundle_overrides)
    return run_dir


def _write_row_bundle(run_dir, *, run_id, status, result_id, evidence_count=2,
                      corrupt=False, reseal=True, metric_id="B01", overrides=None):
    """What the public renderer persists beside a Run, built the same way.

    ``corrupt`` edits the row after its hash is taken. ``overrides`` edits the
    receipt - by name rather than by keyword, because several of its fields
    share names with this function's own arguments - and ``reseal`` decides
    whether its own identity is
    recomputed afterwards - which is the difference between a bundle that has
    obviously been edited and one that agrees with itself while describing
    another Run. The second is the case the first version of the reader
    accepted.
    """
    from vnext.canonical import content_hash
    row = {"metric_id": metric_id, "value": "1", "status": "EXACT"}
    evidence = [{"n": index} for index in range(evidence_count)]
    receipt = {"record_type": "HISTORICAL_PERIOD_ROW_RECEIPT",
               "status": "FROZEN_CANDIDATE" if status == "FROZEN" else "VERIFIED_OPEN_PREVIEW",
               "run_id": run_id, "run_status": status, "requirement_id": "issue_47_v1",
               "result_id": result_id, "primary_metric_id": metric_id,
               "period_selection_id": _selection_id(),
               "row_hash": content_hash(value=row),
               "evidence_hash": content_hash(value=evidence),
               "evidence_count": len(evidence),
               "source_validation": "FULL_NATIVE_HISTORICAL_RUN_REPLAY",
               "presentation_policy_sha256": "e" * 64, "renderer_sha256": "f" * 64,
               "production_authorized": False}
    sealed = content_hash(value=receipt)
    receipt = {**receipt, **(overrides or {})}
    receipt["receipt_id"] = content_hash(value=receipt) if reseal else sealed
    if corrupt:
        row = {**row, "value": "999"}
    bundle = {"record_type": "HISTORICAL_PERIOD_ROW_BUNDLE", "schema_version": 1,
              "row": row, "evidence": evidence, "receipt": receipt}
    (Path(run_dir) / "row_receipt.json").write_text(
        json.dumps(bundle, sort_keys=True) + "\n", encoding="utf-8")
    return bundle


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
        self.assertEqual(4, matrix["schema_version"])
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
        # documents would fill only the routed share.
        #
        # Macy's is a retailer, so the eight trait-gated metrics have a route
        # here - the structural one - and the count is per position rather than
        # per metric. At Marriott two of the eight would not be routed and at a
        # bank six would not; that is the property, not an accident of this
        # company.
        also_unwired = [p for p in missing if not p["historical_route_implemented"]]
        routed = len(WIRED_HISTORICAL_METRICS) + len(STRUCTURAL_APPLICABILITY_METRICS)
        self.assertEqual((39 - routed) * 4, len(also_unwired))
        self.assertEqual(31, routed)
        self.assertEqual(len(also_unwired), matrix["positions_missing_source_and_route"])
        self.assertTrue(matrix["first_blocking_reason_is_not_the_only_blocker"])
        self.assertEqual({"target_period_established": 39 * 5, "target_original_saved": 39,
                          "run_receipt_hashes_verified": 0,
                          "historical_route_implemented": routed * 5,
                          "native_run_receipt": 0, "known_content_defect": 0,
                          "business_content_accepted": 0, "verified_outcome": 0},
                         matrix["dimension_counts"])
        # Implemented and not run is its own state. It is neither an
        # unimplemented route nor a disclosure claim.
        resolved = [p for p in matrix["positions"] if p["report_end"] == MACYS_PERIOD]
        wired = [p for p in resolved if p["metric_id"] in WIRED_HISTORICAL_METRICS]
        self.assertEqual(len(WIRED_HISTORICAL_METRICS), len(wired))
        self.assertEqual({"ROUTE_IMPLEMENTED_NOT_RUN"}, {p["status"] for p in wired})
        # The eight trait-gated metrics also have a route at a retailer, and it
        # is the structural one, so they read as implemented-and-not-run too.
        structural = [p for p in resolved
                      if p["metric_id"] in STRUCTURAL_APPLICABILITY_METRICS]
        self.assertEqual(len(STRUCTURAL_APPLICABILITY_METRICS), len(structural))
        self.assertEqual({"ROUTE_IMPLEMENTED_NOT_RUN"}, {p["status"] for p in structural})
        unwired = [p for p in resolved
                   if p["metric_id"] not in WIRED_HISTORICAL_METRICS
                   and p["metric_id"] not in STRUCTURAL_APPLICABILITY_METRICS]
        self.assertEqual(39 - routed, len(unwired))
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

    def test_the_reported_receipt_does_not_change_when_the_directories_swap_names(self):
        """Same version, same result, two Runs in different states.

        Deduplicating by result_id and then taking the first entry left the
        answer to the order the run directories were read in: with one Run
        frozen and validated and the other neither, swapping the two names
        flipped the position between verified and not. The three questions are
        now answered in order - version, then each receipt's state, then
        duplicates - so the reported outcome is the same either way, and the
        disagreement is reported rather than absorbed.
        """
        result_id = "sha256:" + "a" * 64

        def matrix_with(first, second):
            with TemporaryDirectory(prefix="coverage-order-") as temporary:
                root = Path(temporary)
                _write_run(root / first, company_id="macys", metric_id="B01",
                           period_end=MACYS_PERIOD, result_id=result_id,
                           run_id="run:test:complete")
                _write_run(root / second, company_id="macys", metric_id="B01",
                           period_end=MACYS_PERIOD, result_id=result_id,
                           status="OPEN", validation="FAILED", run_id="run:test:open")
                with original_sources_only():
                    matrix = build_coverage_matrix(repo_root=ROOT, company_ids=["macys"],
                                                   years=5, runs_root=root)
            return next(p for p in matrix["positions"]
                        if p["report_end"] == MACYS_PERIOD and p["metric_id"] == "B01")

        forward = matrix_with("run-a-complete", "run-z-open")
        reversed_ = matrix_with("run-z-complete", "run-a-open")
        self.assertEqual(forward["run_id"], reversed_["run_id"])
        self.assertEqual(forward["verified_outcome"], reversed_["verified_outcome"])
        self.assertEqual(forward["run_status"], reversed_["run_status"])
        # And the answer is the strongest evidence, with the rest still visible.
        self.assertEqual("run:test:complete", forward["run_id"])
        self.assertTrue(forward["verified_outcome"])
        self.assertEqual(2, forward["run_receipt_count"])
        self.assertFalse(forward["receipt_status_uniform"])
        self.assertFalse(reversed_["receipt_status_uniform"])

    def test_one_result_under_two_versions_is_a_version_question_not_a_match(self):
        """Identical results do not make the version they are reported under moot.

        Deduplicating by result_id before choosing a version meant two
        generations that happened to agree were reported as one receipt, and
        which generation got the credit depended on directory order. The
        version is chosen first, so with no selector this is reported.
        """
        result_id = "sha256:" + "a" * 64
        old_closure, new_closure = "sha256:" + "1" * 64, "sha256:" + "2" * 64

        def matrix_with(first, second, closure=None):
            with TemporaryDirectory(prefix="coverage-versions-") as temporary:
                root = Path(temporary)
                _write_run(root / first, company_id="macys", metric_id="B01",
                           period_end=MACYS_PERIOD, result_id=result_id,
                           closure=old_closure, run_id="run:test:old")
                _write_run(root / second, company_id="macys", metric_id="B01",
                           period_end=MACYS_PERIOD, result_id=result_id,
                           closure=new_closure, run_id="run:test:new")
                with original_sources_only():
                    matrix = build_coverage_matrix(repo_root=ROOT, company_ids=["macys"],
                                                   years=5, runs_root=root,
                                                   requirement_closure_hash=closure)
            return next(p for p in matrix["positions"]
                        if p["report_end"] == MACYS_PERIOD and p["metric_id"] == "B01")

        for first, second in (("run-a-old", "run-z-new"), ("run-a-new", "run-z-old")):
            with self.subTest(order=first):
                row = matrix_with(first, second)
                self.assertEqual("RUN_RECEIPT_VERSION_AMBIGUOUS", row["status"])
                self.assertIsNone(row["requirement_closure_hash"])
                self.assertFalse(row["verified_outcome"])
                self.assertEqual(sorted([old_closure, new_closure]),
                                 row["detail"]["requirement_closure_hashes"])
        # Naming the version answers it, and names which one answered.
        selected = matrix_with("run-a-old", "run-z-new", closure=new_closure)
        self.assertEqual("VALUE_EXACT", selected["status"])
        self.assertEqual(new_closure, selected["requirement_closure_hash"])
        self.assertEqual("run:test:new", selected["run_id"])
        self.assertTrue(selected["verified_outcome"])

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

        self.assertEqual("RUN_RECEIPT_VERSION_AMBIGUOUS", row(ambiguous)["status"])
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

    def test_a_release_names_the_repaired_result_and_not_merely_a_state(self):
        """A defect that has been fixed must not keep withdrawing the fix.

        The item-bound entry named a coordinate that could not produce a result
        at all. Once the capacity was raised the coordinate produced the
        correct 92-excerpt result, and the entry went on withdrawing it -
        measured on the real batch, where Pfizer's D02 read as defective while
        being exactly what the entry had asked for.

        The first fix released on ``repair_state`` ending in
        ``_RESULT_RECOMPUTED``, so the same unrepaired receipt and the same
        unrepaired result changed from withdrawn to verified when that string
        was edited. B04 below is that negative: identical run, identical
        result, a state string that says the work is done, and nothing
        pointing at a repaired result.
        """
        repaired = "sha256:" + "a" * 64
        register = [
            {"defect_id": "RELEASED", "company_id": "macys", "metric_id": "B01",
             "period_end": MACYS_PERIOD, "result_id": None,
             "repair_state": "RULE_FIXED_RESULT_RECOMPUTED",
             "released": {"result_id": repaired,
                          "requirement_closure_hash": "sha256:" + "0" * 64}},
            {"defect_id": "OPEN", "company_id": "macys", "metric_id": "B02",
             "period_end": MACYS_PERIOD, "result_id": None,
             "repair_state": "RULE_FIXED_RESULT_NOT_YET_RECOMPUTED"},
            # A named result stays withdrawn whatever the repair state says:
            # it points at one bad result, not at a coordinate.
            {"defect_id": "NAMED", "company_id": "macys", "metric_id": "B03",
             "period_end": MACYS_PERIOD, "result_id": "sha256:" + "5" * 64,
             "repair_state": "RULE_FIXED_RESULT_RECOMPUTED"},
            # The negative: a state string asserting the repair, with no
            # repaired result named.
            {"defect_id": "ASSERTED", "company_id": "macys", "metric_id": "B04",
             "period_end": MACYS_PERIOD, "result_id": None,
             "repair_state": "RULE_FIXED_RESULT_RECOMPUTED"},
            # A release naming a different result does not cover this one.
            {"defect_id": "OTHER_RESULT", "company_id": "macys", "metric_id": "B05",
             "period_end": MACYS_PERIOD, "result_id": None,
             "repair_state": "RULE_FIXED_RESULT_RECOMPUTED",
             "released": {"result_id": "sha256:" + "e" * 64}},
        ]
        with TemporaryDirectory(prefix="coverage-repaired-") as temporary:
            root = Path(temporary)
            for metric, result_id in (("B01", "a"), ("B02", "b"), ("B03", "5"),
                                      ("B04", "d"), ("B05", "9")):
                _write_run(root / ("run-" + metric), company_id="macys", metric_id=metric,
                           period_end=MACYS_PERIOD, result_id="sha256:" + result_id * 64)
            with original_sources_only(), \
                    patch("vnext.historical_coverage.known_result_defects",
                          return_value=register):
                matrix = build_coverage_matrix(repo_root=ROOT, company_ids=["macys"],
                                               years=5, runs_root=root)
        rows = {p["metric_id"]: p for p in matrix["positions"]
                if p["report_end"] == MACYS_PERIOD}
        self.assertEqual(repaired, rows["B01"]["result_id"])
        self.assertIsNone(rows["B01"]["known_content_defect"])
        self.assertTrue(rows["B01"]["verified_outcome"])
        for metric, defect_id in (("B02", "OPEN"), ("B03", "NAMED"),
                                  ("B04", "ASSERTED"), ("B05", "OTHER_RESULT")):
            self.assertEqual(defect_id, rows[metric]["known_content_defect"], metric)
            self.assertFalse(rows[metric]["verified_outcome"], metric)

    def test_a_release_must_also_name_the_version_that_produced_the_result(self):
        """The same result identity under another closure is not this release."""
        repaired = "sha256:" + "a" * 64
        other = "sha256:" + "9" * 64
        register = [{"defect_id": "RELEASED", "company_id": "macys", "metric_id": "B01",
                     "period_end": MACYS_PERIOD, "result_id": None,
                     "released": {"result_id": repaired,
                                  "requirement_closure_hash": other}}]
        with TemporaryDirectory(prefix="coverage-release-version-") as temporary:
            root = Path(temporary)
            _write_run(root / "run-B01", company_id="macys", metric_id="B01",
                       period_end=MACYS_PERIOD, result_id=repaired)
            with original_sources_only(), \
                    patch("vnext.historical_coverage.known_result_defects",
                          return_value=register):
                matrix = build_coverage_matrix(repo_root=ROOT, company_ids=["macys"],
                                               years=5, runs_root=root)
        row = next(p for p in matrix["positions"]
                   if p["report_end"] == MACYS_PERIOD and p["metric_id"] == "B01")
        self.assertEqual("RELEASED", row["known_content_defect"])
        self.assertFalse(row["verified_outcome"])

    def test_a_release_block_that_names_no_result_is_refused_at_load(self):
        """An unreadable release is a refusal, not a silent non-release."""
        register = {"record_type": "KNOWN_RESULT_DEFECT_REGISTER", "schema_version": 2,
                    "defects": [{"defect_id": "X", "company_id": "macys",
                                 "metric_id": "B01", "period_end": MACYS_PERIOD,
                                 "result_id": None, "released": {"note": "done"}}]}
        with TemporaryDirectory(prefix="coverage-release-bad-") as temporary:
            root = Path(temporary)
            (root / "docs" / "evidence" / "issue47_history").mkdir(parents=True)
            (root / "docs" / "evidence" / "issue47_history"
             / "known_result_defects.json").write_text(
                json.dumps(register, sort_keys=True) + "\n", encoding="utf-8")
            with self.assertRaises(CoverageError) as refused:
                known_result_defects(repo_root=root)
        self.assertEqual("COVERAGE_DEFECT_RELEASE_NAMES_NO_RESULT", str(refused.exception))

    def test_the_three_delivery_layers_are_reported_separately(self):
        """A frozen Run, a rendered row and a checked value are three facts.

        verified_outcome answers the first. Presenting it as a delivery rate
        would read "a Run exists" as "the number is right and it reached the
        output", so each layer carries its own proven flag and its own reason
        when it is not proven.
        """
        result_id = "sha256:" + "a" * 64
        with TemporaryDirectory(prefix="coverage-delivery-") as temporary:
            root = Path(temporary)
            _write_run(root / "run-B01", company_id="macys", metric_id="B01",
                       period_end=MACYS_PERIOD, result_id=result_id,
                       row_bundle=result_id)
            _write_run(root / "run-B02", company_id="macys", metric_id="B02",
                       period_end=MACYS_PERIOD, result_id="sha256:" + "b" * 64)
            with original_sources_only():
                matrix = build_coverage_matrix(repo_root=ROOT, company_ids=["macys"],
                                               years=5, runs_root=root)
        rows = {p["metric_id"]: p for p in matrix["positions"]
                if p["report_end"] == MACYS_PERIOD}
        # B01 froze, validated and has a bundle naming its own result.
        self.assertTrue(rows["B01"]["delivery"]["native_run"]["proven"])
        self.assertTrue(rows["B01"]["delivery"]["public_row"]["proven"])
        self.assertEqual(2, rows["B01"]["delivery"]["public_row"]["evidence_count"])
        # B02 froze and validated and never reached a row.
        self.assertTrue(rows["B02"]["delivery"]["native_run"]["proven"])
        self.assertFalse(rows["B02"]["delivery"]["public_row"]["proven"])
        self.assertEqual("NOT_PROVEN:NO_ROW_BUNDLE_BESIDE_THE_RUN",
                         rows["B02"]["delivery"]["public_row"]["reason"])
        # Neither is content-accepted, and both say why rather than omitting it.
        for metric in ("B01", "B02"):
            layer = rows[metric]["delivery"]["content_acceptance"]
            self.assertFalse(layer["proven"])
            self.assertTrue(layer["reason"].startswith("NOT_PROVEN:"))
        self.assertEqual({"native_run": 2, "public_row": 1, "content_acceptance": 0},
                         matrix["delivery_layer_counts"])
        self.assertEqual(0, matrix["delivery_layer_counts"]["content_acceptance"])

    def test_a_row_bundle_for_another_result_does_not_count_as_this_one_s_row(self):
        """A rendered row is evidence for the result it was rendered from.

        Two different facts wear that description and they are not the same
        strength. A bundle naming a result the Run does hold, under the metric
        it says, is a real bundle for a different coordinate - the B01 row
        rendered beside a Run that also recorded B03. A bundle naming a result
        the Run never recorded is not a bundle for another coordinate; it does
        not describe the Run it is lying beside at all, and the reader refuses
        it by name instead of leaving the report to infer it.
        """
        b01, b03 = "sha256:" + "a" * 64, "sha256:" + "b" * 64
        with TemporaryDirectory(prefix="coverage-rowid-") as temporary:
            root = Path(temporary)
            _write_run(root / "run-B03", company_id="macys", metric_id="B03",
                       period_end=MACYS_PERIOD, result_id=b03,
                       extra_results=(("B01", b01),),
                       row_bundle=b03, row_bundle_metric="B03")
            with original_sources_only():
                held = build_coverage_matrix(repo_root=ROOT, company_ids=["macys"],
                                             years=5, runs_root=root)
        rows = {p["metric_id"]: p for p in held["positions"]
                if p["report_end"] == MACYS_PERIOD}
        # The bundle is B03's, so B03 reaches a public row and B01 does not.
        self.assertTrue(rows["B03"]["delivery"]["public_row"]["proven"])
        self.assertTrue(rows["B01"]["delivery"]["native_run"]["proven"])
        self.assertFalse(rows["B01"]["delivery"]["public_row"]["proven"])
        self.assertEqual("ROW_BUNDLE_IS_FOR_ANOTHER_RESULT",
                         rows["B01"]["delivery"]["public_row"]["reason"])
        with TemporaryDirectory(prefix="coverage-rowid-absent-") as temporary:
            root = Path(temporary)
            _write_run(root / "run-B01", company_id="macys", metric_id="B01",
                       period_end=MACYS_PERIOD, result_id=b01,
                       row_bundle="sha256:" + "e" * 64)
            with original_sources_only():
                absent = build_coverage_matrix(repo_root=ROOT, company_ids=["macys"],
                                               years=5, runs_root=root)
        row = next(p for p in absent["positions"]
                   if p["report_end"] == MACYS_PERIOD and p["metric_id"] == "B01")
        self.assertTrue(row["delivery"]["native_run"]["proven"])
        self.assertFalse(row["delivery"]["public_row"]["proven"])
        self.assertEqual("ROW_BUNDLE_RESULT_IS_NOT_THIS_RUNS",
                         row["delivery"]["public_row"]["reason"])

    def test_a_row_rendered_for_another_period_selection_is_not_this_coordinate_s(self):
        """The selection the coordinate resolves to is compared, not carried.

        The report re-resolves the period selection for every established
        coordinate and the renderer writes the one it used into the bundle.
        Until they were compared, both were true statements sitting beside
        each other: a row rendered from a different filing choice of the same
        company and period end counted as this coordinate's public row.

        A refusal here does not have to mean a bad bundle. It also happens
        when saved metadata has moved since the Run - a later filing, a
        refreshed shard - and the coordinate now selects a different original.
        That is worth reporting rather than resolving, because which original
        was measured is the difference the row would otherwise hide.
        """
        result_id = "sha256:" + "a" * 64
        with TemporaryDirectory(prefix="coverage-rowsel-") as temporary:
            root = Path(temporary)
            _write_run(root / "run-B01", company_id="macys", metric_id="B01",
                       period_end=MACYS_PERIOD, result_id=result_id,
                       row_bundle=result_id,
                       row_bundle_overrides={"period_selection_id":
                                             "sha256:" + "7" * 64})
            with original_sources_only():
                matrix = build_coverage_matrix(repo_root=ROOT, company_ids=["macys"],
                                               years=5, runs_root=root)
        row = next(p for p in matrix["positions"]
                   if p["report_end"] == MACYS_PERIOD and p["metric_id"] == "B01")
        self.assertTrue(row["delivery"]["native_run"]["proven"])
        self.assertFalse(row["delivery"]["public_row"]["proven"])
        self.assertEqual("ROW_BUNDLE_PERIOD_SELECTION_IS_NOT_THIS_COORDINATE_S",
                         row["delivery"]["public_row"]["reason"])
        # And the coordinate reports which selection it resolved to, so the
        # two can be compared by a reader rather than taken on trust.
        self.assertEqual(_selection_id(), row["period_selection_id"])

    def test_every_field_the_reader_requires_is_one_the_renderer_writes(self):
        """The fixture is not the writer, so the two are bound to each other.

        These cases build bundles by hand. A reader that required a field the
        renderer never writes would pass all of them and refuse every real
        bundle, and a reader that stopped requiring one would pass them too.
        So the required set is read off the renderer's own receipt literal
        rather than off another copy of the list.
        """
        import ast
        from vnext.historical_run_receipts import _ROW_BUNDLE_FIELDS
        source = ast.parse(
            (ROOT / "scripts/vnext/historical_projection.py").read_text(encoding="utf-8"))
        function = next(node for node in ast.walk(source)
                        if isinstance(node, ast.FunctionDef)
                        and node.name == "render_historical_run")
        written = set()
        for node in ast.walk(function):
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Dict):
                continue
            if [t.id for t in node.targets if isinstance(t, ast.Name)] != ["receipt"]:
                continue
            written = {key.value for key in node.value.keys
                       if isinstance(key, ast.Constant) and isinstance(key.value, str)}
        self.assertTrue(written, "the renderer's receipt literal was not found")
        # receipt_id is sealed over the rest afterwards, so it is not in the
        # literal; every other required field has to be.
        self.assertEqual(set(), set(_ROW_BUNDLE_FIELDS) - {"receipt_id"} - written)

    def test_two_rows_from_different_renderers_are_not_two_views_of_one_row(self):
        """The renderer is closure-bound, so agreement is that binding holding.

        The bundle records which renderer bytes and which presentation policy
        produced the row. Both sat unread, so two rows for one result that came
        out of different renderers would have been merged and whichever sorted
        first reported - the same shape of mistake as picking a run and reading
        every layer off it.
        """
        result_id = "sha256:" + "a" * 64
        with TemporaryDirectory(prefix="coverage-renderer-") as temporary:
            root = Path(temporary)
            _write_run(root / "run-a", company_id="macys", metric_id="B01",
                       period_end=MACYS_PERIOD, result_id=result_id,
                       run_id="run:test:a", row_bundle=result_id)
            _write_run(root / "run-b", company_id="macys", metric_id="B01",
                       period_end=MACYS_PERIOD, result_id=result_id,
                       run_id="run:test:b", row_bundle=result_id,
                       row_bundle_overrides={"renderer_sha256": "1" * 64})
            with original_sources_only():
                matrix = build_coverage_matrix(repo_root=ROOT, company_ids=["macys"],
                                               years=5, runs_root=root)
        row = next(p for p in matrix["positions"]
                   if p["report_end"] == MACYS_PERIOD and p["metric_id"] == "B01")
        self.assertTrue(row["delivery"]["native_run"]["proven"])
        self.assertFalse(row["delivery"]["public_row"]["proven"])
        self.assertEqual("ROW_BUNDLE_RENDERER_AMBIGUOUS",
                         row["delivery"]["public_row"]["reason"])

    def test_an_edited_row_bundle_is_refused_without_erasing_the_run(self):
        """The bundle is checked against its own hashes - and only the bundle.

        This used to raise out of the whole read, which took the coverage
        matrix down over one side-car file and discarded every other Run's
        independently verified evidence with it. The manifest's three file
        hashes are the Run's integrity envelope and they are checked
        separately; row_receipt.json is not inside it, so an edited side-car
        cannot forge the records and must not be allowed to erase them.
        """
        with TemporaryDirectory(prefix="coverage-rowedit-") as temporary:
            run_dir = _write_run(Path(temporary) / "run", company_id="macys",
                                 metric_id="B01", period_end=MACYS_PERIOD,
                                 result_id="sha256:" + "a" * 64,
                                 row_bundle="sha256:" + "a" * 64)
            self.assertTrue(read_run_receipt(run_dir=run_dir)["public_row"]["accepted"])
            _write_row_bundle(run_dir, run_id="run:test:" + "a" * 8, status="FROZEN",
                              result_id="sha256:" + "a" * 64, corrupt=True)
            receipt = read_run_receipt(run_dir=run_dir)
        self.assertFalse(receipt["public_row"]["accepted"])
        self.assertEqual("ROW_BUNDLE_ROW_CHANGED", receipt["public_row"]["refusal"])
        # The Run itself still reads: its own files still hash to its manifest.
        self.assertTrue(receipt["manifest_file_hashes_verified"])
        self.assertEqual(["B01"], [r["metric_id"] for r in receipt["results"]])
        # An unreadable bundle is a third state, named rather than reported as
        # an absent row.
        with TemporaryDirectory(prefix="coverage-rowjunk-") as temporary:
            run_dir = _write_run(Path(temporary) / "run", company_id="macys",
                                 metric_id="B01", period_end=MACYS_PERIOD,
                                 result_id="sha256:" + "a" * 64,
                                 row_bundle="sha256:" + "a" * 64)
            (run_dir / "row_receipt.json").write_text("{not json", encoding="utf-8")
            junk = read_run_receipt(run_dir=run_dir)
        self.assertFalse(junk["public_row"]["accepted"])
        self.assertTrue(junk["public_row"]["refusal"].startswith("ROW_BUNDLE_UNREADABLE:"))

    def test_one_unreadable_run_directory_does_not_take_the_report_down(self):
        """A runs root read while a batch is writing always holds one.

        Reading one Run and refusing it is right - the directory is not the Run
        its manifest claims. Reading many and refusing all of them over one is
        not, and that is what used to happen: the whole matrix raised. Measured
        against a live batch of 87 run directories, three were OPEN with a
        manifest seconds old and no report could be produced at all.

        The two cases are not the same strength and the record says which. An
        OPEN run whose files do not match is being written; a FROZEN one is a
        directory that is not the Run it claims.
        """
        result_id = "sha256:" + "a" * 64
        for status, reading in (("OPEN", "RUN_IS_BEING_WRITTEN"),
                                ("FROZEN", "DIRECTORY_IS_NOT_THE_RUN_IT_CLAIMS")):
            with self.subTest(status=status):
                with TemporaryDirectory(prefix="coverage-partial-") as temporary:
                    root = Path(temporary)
                    _write_run(root / "run-good", company_id="macys", metric_id="B01",
                               period_end=MACYS_PERIOD, result_id=result_id,
                               run_id="run:test:good", row_bundle=result_id)
                    mid = _write_run(root / "run-mid-write", company_id="macys",
                                     metric_id="B02", period_end=MACYS_PERIOD,
                                     result_id="sha256:" + "b" * 64, status=status,
                                     run_id="run:test:mid")
                    # What a writer in progress leaves behind: the manifest is
                    # already there and the records file is still growing.
                    with (mid / "records.jsonl").open("a", encoding="utf-8") as file:
                        file.write('{"record_type": "PARTIAL"}\n')
                    with original_sources_only():
                        matrix = build_coverage_matrix(repo_root=ROOT,
                                                       company_ids=["macys"], years=5,
                                                       runs_root=root)
                rows = {p["metric_id"]: p for p in matrix["positions"]
                        if p["report_end"] == MACYS_PERIOD}
                # The readable Run still reports, all three layers.
                self.assertTrue(rows["B01"]["delivery"]["native_run"]["proven"])
                self.assertTrue(rows["B01"]["delivery"]["public_row"]["proven"])
                # The unreadable one is named rather than silently absent.
                self.assertEqual("ROUTE_IMPLEMENTED_NOT_RUN", rows["B02"]["status"])
                named = matrix["unreadable_run_directories"]
                self.assertEqual(1, len(named))
                self.assertEqual("run-mid-write", named[0]["run_directory_name"])
                self.assertEqual(status, named[0]["claimed_run_status"])
                self.assertEqual(reading, named[0]["reading"])
                self.assertTrue(named[0]["reason"].startswith("RUN_RECEIPT_FILE_CHANGED"))

    def test_a_row_bundle_must_describe_the_run_it_is_lying_beside(self):
        """Agreeing with itself is not describing this Run.

        The first version of the reader checked the receipt's summary of its
        own row and evidence and stopped there. An external probe rewrote the
        receipt's run, its Requirement and its source validation, left the row
        and the evidence untouched, and the bundle was still read - so the
        position still counted as having reached a public row.

        Each case here reseals the receipt, so its own identity is consistent
        and the Run-binding checks are what has to refuse it. Without that
        every case would stop at the identity check and the rest would be
        unexercised.
        """
        result_id = "sha256:" + "a" * 64
        run_id = "run:test:complete"
        cases = {
            "ROW_BUNDLE_IS_FOR_ANOTHER_RUN": {"run_id": "run:test:elsewhere"},
            "ROW_BUNDLE_SOURCE_VALIDATION_CHANGED:NOT_REPLAYED":
                {"source_validation": "NOT_REPLAYED"},
            "ROW_BUNDLE_RESULT_IS_NOT_THIS_RUNS": {"result_id": "sha256:" + "e" * 64},
            "ROW_BUNDLE_PERIOD_SELECTION_INVALID": {"period_selection_id": "not-a-hash"},
            "ROW_BUNDLE_STATE_DISAGREES_WITH_RUN": {"status": "VERIFIED_OPEN_PREVIEW"},
        }
        for reason, changes in cases.items():
            with self.subTest(reason=reason):
                with TemporaryDirectory(prefix="coverage-bundle-bind-") as temporary:
                    run_dir = _write_run(Path(temporary) / "run", company_id="macys",
                                         metric_id="B01", period_end=MACYS_PERIOD,
                                         result_id=result_id, run_id=run_id)
                    _write_row_bundle(run_dir, run_id=run_id, status="FROZEN",
                                      result_id=result_id, overrides=changes)
                    refused = read_run_receipt(run_dir=run_dir)
                self.assertFalse(refused["public_row"]["accepted"])
                self.assertEqual(reason, refused["public_row"]["refusal"])
                # Refusing the side-car does not refuse the Run. Its own three
                # file hashes are checked separately and still hold.
                self.assertTrue(refused["manifest_file_hashes_verified"])
        # A receipt whose own identity was not recomputed is refused before any
        # of those, which is a different failure and has its own reason.
        with TemporaryDirectory(prefix="coverage-bundle-stale-") as temporary:
            run_dir = _write_run(Path(temporary) / "run", company_id="macys",
                                 metric_id="B01", period_end=MACYS_PERIOD,
                                 result_id=result_id, run_id=run_id)
            _write_row_bundle(run_dir, run_id=run_id, status="FROZEN",
                              result_id=result_id, reseal=False,
                              overrides={"requirement_id": "issue_28_v13"})
            stale = read_run_receipt(run_dir=run_dir)
        self.assertEqual("ROW_BUNDLE_RECEIPT_IDENTITY_CHANGED",
                         stale["public_row"]["refusal"])

    def test_a_row_rendered_by_one_run_is_not_lost_because_another_was_reported(self):
        """B01's row is rendered beside the B01 Run, not beside B03's.

        Choosing one receipt to represent the position and reading every layer
        off it made the row layer depend on two run_ids: whichever sorted
        first decided whether the position had reached a public row. The
        version, the result identity and the period selection settle which
        runs are comparable; after that each layer is associated with the
        evidence that carries it, and the row layer names its own run.
        """
        result_id = "sha256:" + "a" * 64

        def row_layer(with_bundle, without_bundle):
            with TemporaryDirectory(prefix="coverage-row-assoc-") as temporary:
                root = Path(temporary)
                carrier = _write_run(root / with_bundle, company_id="macys",
                                     metric_id="B01", period_end=MACYS_PERIOD,
                                     result_id=result_id, run_id="run:test:" + with_bundle)
                _write_row_bundle(carrier, run_id="run:test:" + with_bundle,
                                  status="FROZEN", result_id=result_id)
                _write_run(root / without_bundle, company_id="macys", metric_id="B01",
                           period_end=MACYS_PERIOD, result_id=result_id,
                           run_id="run:test:" + without_bundle)
                with original_sources_only():
                    matrix = build_coverage_matrix(repo_root=ROOT, company_ids=["macys"],
                                                   years=5, runs_root=root)
            row = next(p for p in matrix["positions"]
                       if p["report_end"] == MACYS_PERIOD and p["metric_id"] == "B01")
            return row["delivery"]

        later = row_layer("run-z-carrier", "run-a-plain")
        earlier = row_layer("run-a-carrier", "run-z-plain")
        for layers in (later, earlier):
            self.assertTrue(layers["native_run"]["proven"])
            self.assertTrue(layers["public_row"]["proven"])
        # And the row names the run that rendered it, which is not always the
        # run the native layer reports.
        self.assertEqual("run:test:run-z-carrier", later["public_row"]["rendered_by"])
        self.assertEqual("run:test:run-a-carrier", earlier["public_row"]["rendered_by"])
        self.assertEqual("run:test:run-a-plain", later["native_run"]["run_id"])

    def test_a_row_rendered_from_an_open_run_is_a_preview_not_a_public_row(self):
        with TemporaryDirectory(prefix="coverage-row-preview-") as temporary:
            root = Path(temporary)
            run_dir = _write_run(root / "run-open", company_id="macys", metric_id="B01",
                                 period_end=MACYS_PERIOD, result_id="sha256:" + "a" * 64,
                                 status="OPEN", validation="PASSED",
                                 run_id="run:test:open")
            _write_row_bundle(run_dir, run_id="run:test:open", status="OPEN",
                              result_id="sha256:" + "a" * 64)
            with original_sources_only():
                matrix = build_coverage_matrix(repo_root=ROOT, company_ids=["macys"],
                                               years=5, runs_root=root)
        layers = next(p for p in matrix["positions"]
                      if p["report_end"] == MACYS_PERIOD
                      and p["metric_id"] == "B01")["delivery"]
        self.assertFalse(layers["native_run"]["proven"])
        self.assertFalse(layers["public_row"]["proven"])
        self.assertEqual("ROW_BUNDLE_IS_AN_OPEN_RUN_PREVIEW",
                         layers["public_row"]["reason"])

    def test_a_release_without_a_version_does_not_match_every_version(self):
        """The case name said the version must be named; the code did not.

        "closure is None or it matches" reads as optional, so an entry that
        omitted the field, or wrote null, released the coordinate under every
        version. The display list had the same hole from the other side: it
        compared only the result identity, so one entry could appear as both
        withdrawn_by and released.
        """
        result_id = "sha256:" + "a" * 64
        closure = "sha256:" + "0" * 64
        def register(release):
            return [{"defect_id": "D", "company_id": "macys", "metric_id": "B01",
                     "period_end": MACYS_PERIOD, "result_id": None, "released": release}]
        cases = {
            "names this version": ({"result_id": result_id,
                                    "requirement_closure_hash": closure}, True),
            "names another version": ({"result_id": result_id,
                                       "requirement_closure_hash": "sha256:" + "9" * 64}, False),
            "omits the version": ({"result_id": result_id}, False),
            "version is null": ({"result_id": result_id,
                                 "requirement_closure_hash": None}, False),
            "version is not a hash": ({"result_id": result_id,
                                       "requirement_closure_hash": "any"}, False),
        }
        for name, (release, released) in cases.items():
            with self.subTest(release=name):
                with TemporaryDirectory(prefix="coverage-release-version-") as temporary:
                    root = Path(temporary)
                    _write_run(root / "run-B01", company_id="macys", metric_id="B01",
                               period_end=MACYS_PERIOD, result_id=result_id)
                    with original_sources_only(), \
                            patch("vnext.historical_coverage.known_result_defects",
                                  return_value=register(release)):
                        matrix = build_coverage_matrix(repo_root=ROOT,
                                                       company_ids=["macys"], years=5,
                                                       runs_root=root)
                row = next(p for p in matrix["positions"]
                           if p["report_end"] == MACYS_PERIOD and p["metric_id"] == "B01")
                acceptance = row["delivery"]["content_acceptance"]
                self.assertEqual(released, row["known_content_defect"] is None, name)
                self.assertEqual(released, "D" in acceptance["released_defect_ids"], name)
                # Withdrawn and released are the same predicate seen from two
                # sides; an entry can never be both.
                self.assertFalse(acceptance["withdrawn_by"] == "D"
                                 and "D" in acceptance["released_defect_ids"], name)

    def test_a_release_that_names_no_version_is_refused_at_load(self):
        register = {"record_type": "KNOWN_RESULT_DEFECT_REGISTER", "schema_version": 2,
                    "defects": [{"defect_id": "X", "company_id": "macys",
                                 "metric_id": "B01", "period_end": MACYS_PERIOD,
                                 "result_id": None,
                                 "released": {"result_id": "sha256:" + "a" * 64}}]}
        with TemporaryDirectory(prefix="coverage-release-noversion-") as temporary:
            root = Path(temporary)
            (root / "docs" / "evidence" / "issue47_history").mkdir(parents=True)
            (root / "docs" / "evidence" / "issue47_history"
             / "known_result_defects.json").write_text(
                json.dumps(register, sort_keys=True) + "\n", encoding="utf-8")
            with self.assertRaises(CoverageError) as refused:
                known_result_defects(repo_root=root)
        self.assertEqual("COVERAGE_DEFECT_RELEASE_NAMES_NO_VERSION", str(refused.exception))

    def test_what_a_coordinate_key_does_not_distinguish_is_carried_beside_it(self):
        """Same coordinate, different measurement, and the report can say so.

        Company, metric and period end is the frame's coordinate and it is
        coarser than a measurement: the pinned fiscal coordinate, the window
        actually measured, the scope and the filing are separate facts. They
        are not folded into the key - the frame has a row per coordinate - so
        they travel beside it, and result_id already differs whenever any of
        them does.
        """
        from vnext.historical_run_receipts import collect_run_receipts, index_receipts
        with TemporaryDirectory(prefix="coverage-identity-") as temporary:
            root = Path(temporary)
            _write_run(root / "run-full", company_id="macys", metric_id="B01",
                       period_end=MACYS_PERIOD, result_id="sha256:" + "a" * 64,
                       run_id="run:test:full")
            _write_run(root / "run-stub", company_id="macys", metric_id="B01",
                       period_end=MACYS_PERIOD, result_id="sha256:" + "b" * 64,
                       run_id="run:test:stub")
            index = index_receipts(
                receipts=collect_run_receipts(runs_root=root)["receipts"])
            with original_sources_only():
                matrix = build_coverage_matrix(repo_root=ROOT, company_ids=["macys"],
                                               years=5, runs_root=root)
        entries = index[("macys", "B01", MACYS_PERIOD)]
        self.assertEqual(2, len(entries))
        for entry in entries:
            self.assertEqual({"pinned_fiscal_year", "pinned_period_end",
                              "measured_period_start", "measured_period_end",
                              "scope_key", "value_kind", "requirement_closure_hash",
                              "run_id"}, set(entry["identity"]))
            self.assertEqual(2025, entry["identity"]["pinned_fiscal_year"])
        self.assertEqual({"run:test:full", "run:test:stub"},
                         {entry["identity"]["run_id"] for entry in entries})
        # Two different results at one coordinate stay two, and the position
        # reports the disagreement rather than reporting one of them.
        row = next(p for p in matrix["positions"]
                   if p["report_end"] == MACYS_PERIOD and p["metric_id"] == "B01")
        self.assertEqual("RUN_RECEIPT_AMBIGUOUS", row["status"])

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

    def test_three_routes_at_one_amended_period_give_three_different_answers(self):
        """Adapters fail separately because they answer separate questions.

        Paramount's most recent annual period carries a 10-K/A that adds Part
        III and says it changes nothing else. The approved policy reads that as
        clearing the fiscal-event window and not the original statement values,
        so the statement routes are refused by policy and name which class was
        not cleared. The event route is cleared by that same amendment,
        resolves over the widened successor window, and withholds on a named
        missing predecessor document. The instant-fact route reads the selected
        filing's own inline XBRL and succeeds. One period, three answers, three
        reasons - a policy refusal, a source gap and a value.

        Written against Southwest until the amendment policy was wired, where
        it asserted two refusals that the policy then correctly stopped making;
        that version went on asserting them and was red at HEAD. The property
        lives in the resolvers, so it is asserted by calling them, not by
        making the report run them.
        """
        from vnext.historical_accession_results import resolve_historical_accession_metrics
        from vnext.historical_results import resolve_historical_companyfacts_metrics
        from vnext.historical_zero_ai_results import resolve_historical_zero_ai_metric
        from vnext.normal_period_selection import resolve_period_selection

        company = "paramount_skydance_paramount_global"
        with original_sources_only():
            selection = resolve_period_selection(repo_root=ROOT, company_id=company,
                                                 report_end="2025-12-31")
            with self.assertRaises(ValueError) as facts:
                resolve_historical_companyfacts_metrics(repo_root=ROOT, company_id=company,
                                                        period_selection=selection)
            with self.assertRaises(ValueError) as revenue:
                resolve_historical_zero_ai_metric(repo_root=ROOT, company_id=company,
                                                  metric_id="B01",
                                                  period_selection=selection)
            event = resolve_historical_zero_ai_metric(repo_root=ROOT, company_id=company,
                                                      metric_id="C01",
                                                      period_selection=selection)
            instants = resolve_historical_accession_metrics(repo_root=ROOT,
                                                            company_id=company,
                                                            period_selection=selection)
        refused_class = ("HISTORICAL_AMENDMENT_INPUT_CLASS_NOT_CLEARED:"
                         "ORIGINAL_STATEMENT_VALUES:"
                         "PART_III_ADDITION_WITH_EXPLICIT_NO_NEW_FINANCIAL_STATEMENTS")
        self.assertEqual(refused_class, str(facts.exception))
        self.assertEqual(refused_class, str(revenue.exception))
        # The same amendment clears the event window, so the event route is not
        # refused by policy at all. It resolves, reads the registered CIKs over
        # the widened window, and withholds on a named missing document - a
        # source gap, which is a third state again and not either refusal.
        self.assertEqual("HISTORICAL_ZERO_AI_SOURCE_ROUTE_UNRESOLVED",
                         event["result"]["reason_code"])
        self.assertEqual("SOURCE_UNAVAILABLE", event["selection"]["category"])
        self.assertTrue(event["selection"]["reason"].startswith("SAVED_SOURCE_MISSING:"))
        self.assertEqual({"fiscal_year": 2025, "period_start": "2024-01-01",
                          "period_end": "2025-12-31"},
                         event["input_binding"]["registered_event_scope"]["window"])
        self.assertTrue(instants["metrics"])

    def test_an_exhibit_link_correction_clears_both_input_classes(self):
        """The positive control for the same policy, on the other classification.

        Southwest's 10-K/A corrects an exhibit hyperlink and states in its own
        explanatory note that it modifies no disclosure in the original filing.
        Every route that was blocked by the presence of an amendment resolves.
        """
        from vnext.historical_accession_results import resolve_historical_accession_metrics
        from vnext.historical_results import resolve_historical_companyfacts_metrics
        from vnext.historical_zero_ai_results import resolve_historical_zero_ai_metric
        from vnext.normal_period_selection import resolve_period_selection

        company = "southwest_airlines"
        with original_sources_only():
            selection = resolve_period_selection(repo_root=ROOT, company_id=company,
                                                 report_end="2025-12-31")
            self.assertTrue(selection["current_amendments"])
            facts = resolve_historical_companyfacts_metrics(repo_root=ROOT,
                                                            company_id=company,
                                                            period_selection=selection)
            revenue = resolve_historical_zero_ai_metric(repo_root=ROOT, company_id=company,
                                                        metric_id="B01",
                                                        period_selection=selection)
            instants = resolve_historical_accession_metrics(repo_root=ROOT,
                                                            company_id=company,
                                                            period_selection=selection)
        self.assertTrue(facts["metrics"])
        self.assertIsNotNone(revenue["result"])
        self.assertTrue(instants["metrics"])
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
