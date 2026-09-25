"""An acceptance is bound to what its reading checked, not to what a batch says.

Two defects a reviewer measured, each reproduced here before it was fixed:

* the register generator pinned each acceptance's window, unit and scope from
  whatever results it was generated against, found by directory order. An
  unchanged reading regenerated beside a batch whose result had moved to a new
  unit or scope granted the new one. The identity now lives in the reading and
  the generator reads no Run;
* the staleness check ran over the register's reading table, so a table that
  was missing, empty or silent about a cited reading skipped the check for it.
  Every cited reading now gets a state, and only an unchanged, hashed one
  grants.

The cases build their own runs and readings where the property is the
predicate, and use the committed readings where the property is about this
repository's register.
"""
import hashlib
import json
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from tests.vnext.common import REPO_ROOT as ROOT
from tools import bind_acceptance_readings as binder
from tools import build_acceptance_register as generator
from vnext import historical_run_receipts
from vnext.historical_coverage import (ACCEPTANCE_IDENTITY_FIELDS,
                                       ACCEPTANCE_REGISTER_PATH, READING_CHANGED,
                                       READING_GRANTING, READING_NOT_HASHED,
                                       READING_UNREADABLE, _acceptance_for_position,
                                       acceptance_mismatch,
                                       independent_content_acceptances)
from vnext.historical_run_receipts import (collect_run_receipts, index_receipts,
                                           read_run_receipt)

CLOSURE = "sha256:" + "5" * 64
OTHER_CLOSURE = "sha256:" + "6" * 64
ACCESSION = "0001048286-26-000007"
PRIOR = "0001628280-25-004818"


def _digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write_bound_run(root, *, name, company_id="marriott_international", metric_id="C04",
                     period_end="2025-12-31", value="0", unit="flag",
                     scope_key="sha256:" + "a" * 64, accessions=(ACCESSION,),
                     entity=None, closure=CLOSURE, result_id=None,
                     spec_closure_hash="sha256:" + "c" * 64, pseudo_reference=True):
    """A frozen run whose result is linked to its filings the way a real one is.

    Result -> trace -> observation -> source references -> accessions, plus one
    submissions inventory reference, which names no filing and must not be
    counted as one.
    """
    run_dir = Path(root) / name
    run_dir.mkdir(parents=True)
    references = [{"record_type": "SOURCE_REFERENCE", "source_reference_id": "ref-" + str(i),
                   "accession": accession, "company_id": company_id,
                   "document_name": "doc.htm", "raw_asset_id": "raw-" + str(i),
                   "request_attempt_id": "attempt-" + str(i), "source_role": "target_primary",
                   "source_url": "https://www.sec.gov/x"}
                  for i, accession in enumerate(accessions)]
    if pseudo_reference:
        references.append({**references[0], "source_reference_id": "ref-inventory",
                           "accession": "SUBMISSIONS-1048286",
                           "source_role": "sec_submissions_inventory"})
    observation = {"record_type": "VERIFIED_OBSERVATION", "observation_id": "obs-1",
                   "source_binding": {"source_reference_ids": [r["source_reference_id"]
                                                               for r in references],
                                      **({"entity": entity} if entity else {})}}
    trace = {"record_type": "EXECUTION_TRACE", "trace_id": "trace-1",
             "calculation_target": {"accession": None, "entity": None},
             "input_observation_ids": ["obs-1"]}
    result = {"record_type": "METRIC_RESULT", "metric_id": metric_id,
              "result_id": result_id or ("sha256:" + hashlib.sha256(name.encode()).hexdigest()),
              "value": value, "unit": unit, "quality": "EXACT", "publication": "PUBLISHED",
              "reason_code": "PASS", "applicability": "APPLICABLE",
              "period_start": "2025-01-01", "period_end": period_end,
              "scope_key": scope_key, "spec_closure_hash": spec_closure_hash,
              "trace_id": "trace-1"}
    records = references + [observation, trace, result]
    (run_dir / "records.jsonl").write_text(
        "".join(json.dumps(r, sort_keys=True) + "\n" for r in records), encoding="utf-8")
    (run_dir / "validation.json").write_text(json.dumps({"status": "PASSED"}) + "\n",
                                             encoding="utf-8")
    (run_dir / "review_decisions.jsonl").write_text("", encoding="utf-8")
    manifest = {"record_type": "SUCCESSOR_RUN", "run_id": "run:test:" + name,
                "status": "FROZEN", "requirement_id": "issue_47_v1",
                "requirement_closure_hash": closure, "company_id": company_id,
                "target_period": {"fiscal_year": 2025, "period_start": "2025-01-01",
                                  "period_end": period_end},
                "records_file_hash": _digest(run_dir / "records.jsonl"),
                "review_decisions_file_hash": _digest(run_dir / "review_decisions.jsonl"),
                "validation_file_hash": _digest(run_dir / "validation.json")}
    (run_dir / "manifest.json").write_text(json.dumps(manifest, sort_keys=True) + "\n",
                                           encoding="utf-8")
    return run_dir


def _position(**overrides):
    base = {"company_id": "marriott_international", "metric_id": "C04",
            "period_end": "2025-12-31", "published": "0", "reading_filings": [ACCESSION],
            "reading_window": ["2025-01-01", "2025-12-31"],
            "filings_are_the_whole_set": False, "label": "marriott-2025"}
    return {**base, **overrides}


class TheReceiptNamesWhatTheResultWasComputedFromTest(unittest.TestCase):
    """The result side of the comparison: filings, entity and meaning."""

    def test_filings_come_from_the_result_s_own_links_and_skip_inventories(self):
        with TemporaryDirectory() as root:
            run = _write_bound_run(root, name="run-a", accessions=(ACCESSION, PRIOR),
                                   entity="1048286")
            result = read_run_receipt(run_dir=run)["results"][0]
        self.assertEqual(sorted([ACCESSION, PRIOR]), result["filings"])
        self.assertEqual(["1048286"], result["entities"])
        self.assertEqual("sha256:" + "c" * 64, result["spec_closure_hash"])

    def test_a_result_without_a_trace_binds_no_filing(self):
        """Nothing is guessed: no links, no filings - and no acceptance can bind."""
        with TemporaryDirectory() as root:
            run = _write_bound_run(root, name="run-a")
            lines = (run / "records.jsonl").read_text().splitlines()
            kept = [line for line in lines if '"EXECUTION_TRACE"' not in line]
            (run / "records.jsonl").write_text("\n".join(kept) + "\n")
            manifest = json.loads((run / "manifest.json").read_text())
            manifest["records_file_hash"] = _digest(run / "records.jsonl")
            (run / "manifest.json").write_text(json.dumps(manifest, sort_keys=True) + "\n")
            result = read_run_receipt(run_dir=run)["results"][0]
        self.assertEqual([], result["filings"])


class TheRegisterReadsNoRunTest(unittest.TestCase):
    """The generator copies identity from readings; results are not an input."""

    def test_the_register_is_built_with_every_run_reader_disabled(self):
        """Disabled at every binding, not at the defining module.

        A caller that did ``from ... import collect_run_receipts`` holds the
        original, so patching the definition alone would read zero for code
        that really does read Runs. Every loaded module's reference is replaced,
        and a reader with no reference to replace is a refusal, because then
        this case would be measuring nothing.
        """
        import sys

        def refuse(**_):
            raise AssertionError("the register generator read a Run")
        originals = {name: getattr(historical_run_receipts, name)
                     for name in ("collect_run_receipts", "index_receipts",
                                  "read_run_receipt")}
        patches = []
        for module in list(sys.modules.values()):
            for name, original in originals.items():
                if getattr(module, name, None) is original:
                    patches.append(patch.object(module, name, refuse))
        self.assertGreaterEqual(len(patches), len(originals))
        for active in patches:
            active.start()
        try:
            register = generator.build_register(repo_root=ROOT)
        finally:
            for active in patches:
                active.stop()
        self.assertTrue(register["acceptances"])
        for entry in register["acceptances"]:
            with self.subTest(entry["acceptance_id"]):
                self.assertEqual(set(ACCEPTANCE_IDENTITY_FIELDS),
                                 set(ACCEPTANCE_IDENTITY_FIELDS)
                                 & set(entry["checked_identity"]))

    def test_the_committed_register_is_what_the_readings_build(self):
        """Regenerating changes nothing while the readings do not change."""
        committed = json.loads((ROOT / ACCEPTANCE_REGISTER_PATH).read_text(encoding="utf-8"))
        self.assertEqual(committed, generator.build_register(repo_root=ROOT))

    def test_a_result_that_moved_is_not_granted_by_regenerating(self):
        """The reviewer's case, end to end on this repository's register.

        An unchanged reading, and a batch whose result kept its value while its
        unit, scope, filing or meaning moved - put where the old generator
        looked for results, through the environment knob it read and as a run
        directory it globbed. Regenerating used to pin the moved identity and
        grant it. Now the regenerated register is the committed one, byte for
        byte, and the moved result is refused by name.
        """
        import os
        committed = json.loads((ROOT / ACCEPTANCE_REGISTER_PATH).read_text(encoding="utf-8"))
        entry = next(e for e in committed["acceptances"]
                     if e["acceptance_id"] == "CONTENT_C04_MARRIOTT_2025")
        identity = entry["checked_identity"]
        read = {"value": entry["accepted_value"],
                **{field: identity[field] for field in ACCEPTANCE_IDENTITY_FIELDS}}
        coordinate = {"company_id": entry["company_id"], "metric_id": entry["metric_id"],
                      "report_end": entry["period_end"]}
        self.assertEqual([], acceptance_mismatch(acceptance=entry, result=read, **coordinate),
                         "the control has to hold or the moves below say nothing")
        for field, moved, run in (
                ("unit", "count", {"unit": "count"}),
                ("scope_key", "sha256:" + "b" * 64, {"scope_key": "sha256:" + "b" * 64}),
                ("filings", [PRIOR], {"accessions": (PRIOR,)}),
                ("spec_closure_hash", "sha256:" + "d" * 64,
                 {"spec_closure_hash": "sha256:" + "d" * 64})):
            with self.subTest(field), TemporaryDirectory() as runs:
                _write_bound_run(runs, name="run-marriott-2025-C04",
                                 unit=run.get("unit", identity["unit"]),
                                 scope_key=run.get("scope_key", identity["scope_key"]),
                                 accessions=run.get("accessions", tuple(identity["filings"])),
                                 spec_closure_hash=run.get("spec_closure_hash",
                                                           identity["spec_closure_hash"]),
                                 closure=identity["bound_from"]["requirement_closure_hash"])
                with patch.dict(os.environ, {"ISSUE47_RUNS_ROOT": runs}):
                    regenerated = generator.build_register(repo_root=ROOT)
                self.assertEqual(committed, regenerated)
                again = next(e for e in regenerated["acceptances"]
                             if e["acceptance_id"] == entry["acceptance_id"])
                self.assertEqual([field], acceptance_mismatch(
                    acceptance=again, result={**read, field: moved}, **coordinate))

    def test_an_accepted_position_without_an_identity_is_refused(self):
        """A reading that concluded MATCH and recorded no identity cannot grant.

        Refused loudly rather than skipped: skipping would drop an acceptance
        without saying so, and the old register that still names it would then
        be the only record of it.
        """
        original = generator.load

        def stripped(*, repo_root, path):
            body, options = original(repo_root=repo_root, path=path)
            if path == generator.GOVERNANCE:
                body["per_position"]["marriott-2025"]["C04"].pop("checked_identity")
            return body, options
        with patch.object(generator, "load", stripped):
            with self.assertRaises(generator.RegisterError) as raised:
                generator.build_register(repo_root=ROOT)
        self.assertIn("READING_POSITION_HAS_NO_CHECKED_IDENTITY", str(raised.exception))
        self.assertIn("marriott-2025:C04", str(raised.exception))


class TheBindingIsCheckedAgainstTheReadingTest(unittest.TestCase):
    """Binding is a one-time act, and it must agree with what the reading names."""

    def _index(self, root):
        return index_receipts(receipts=collect_run_receipts(runs_root=Path(root))["receipts"])

    def test_the_control_binds_with_the_checks_it_ran(self):
        with TemporaryDirectory() as root:
            _write_bound_run(root, name="run-a")
            identity, refusal = binder.identity_for(position=_position(),
                                                    index=self._index(root), closure=CLOSURE)
        self.assertIsNone(refusal)
        self.assertEqual("BOUND_AFTER_THE_READING", identity["established_by"])
        self.assertEqual(["value", "filings_contain_the_filing_the_reading_opened", "window"],
                         identity["checked_against_the_reading"])
        self.assertEqual([ACCESSION], identity["filings"])

    def test_each_disagreement_refuses_by_name(self):
        cases = (
            ("value", {"published": "1"}, {},
             "RESULT_VALUE_IS_NOT_THE_VALUE_THE_READING_COMPARED"),
            ("filing", {"reading_filings": [PRIOR]}, {},
             "READING_OPENED_A_FILING_THE_RESULT_DOES_NOT_NAME"),
            ("whole set", {"reading_filings": [ACCESSION], "filings_are_the_whole_set": True},
             {"accessions": (ACCESSION, PRIOR)},
             "READING_AND_RESULT_ENUMERATE_DIFFERENT_FILINGS"),
            ("window", {"reading_window": ["2024-01-01", "2024-12-31"]}, {},
             "READING_AND_RESULT_DISAGREE_ON_THE_WINDOW"),
            ("closure", {}, {"closure": OTHER_CLOSURE}, "NO_RESULT_UNDER_THE_NAMED_CLOSURE"),
        )
        for label, position, run, reason in cases:
            with self.subTest(label), TemporaryDirectory() as root:
                _write_bound_run(root, name="run-a", **run)
                identity, refusal = binder.identity_for(
                    position=_position(**position), index=self._index(root), closure=CLOSURE)
                self.assertIsNone(identity)
                self.assertTrue(refusal.startswith(reason), refusal)

    def test_two_different_results_for_one_coordinate_are_not_chosen_between(self):
        """Directory order was the old selector; now it is an ambiguity."""
        with TemporaryDirectory() as root:
            _write_bound_run(root, name="run-a")
            _write_bound_run(root, name="run-b", unit="count")
            identity, refusal = binder.identity_for(position=_position(),
                                                    index=self._index(root), closure=CLOSURE)
        self.assertIsNone(identity)
        self.assertEqual("RESULT_SELECTION_AMBIGUOUS:RUN_RECEIPT_AMBIGUOUS", refusal)

    def test_a_recorded_identity_is_never_moved_by_a_batch_that_differs(self):
        """The binder must not become the back-fill it replaces.

        Every committed reading already records its identities. Binding them
        against a batch whose only result has moved must leave every reading's
        bytes as they were and report the difference.
        """
        from tools import acceptance_readings as readings
        with TemporaryDirectory() as directory:
            repo = Path(directory) / "repo"
            for path in readings.READINGS:
                (repo / path).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / path, repo / path)
            (repo / "evidence").symlink_to(ROOT / "evidence")
            runs = Path(directory) / "runs"
            runs.mkdir()
            _write_bound_run(runs, name="run-marriott-c04", unit="count")
            before = {path: (repo / path).read_bytes() for path in readings.READINGS}
            report = binder.bind(repo_root=repo, runs_root=runs, closure=CLOSURE)
            after = {path: (repo / path).read_bytes() for path in readings.READINGS}
        self.assertEqual(before, after)
        self.assertNotIn("BOUND", report["outcomes"])
        moved = [entry for entry in report["positions"]
                 if (entry["label"], entry["metric_id"]) == ("marriott-2025", "C04")]
        self.assertEqual(["ALREADY_RECORDED_AND_THE_BATCH_DIFFERS"],
                         [entry["outcome"] for entry in moved])


class EveryCitedReadingIsHashedTest(unittest.TestCase):
    """A cited reading the table does not hash cannot have been checked."""

    def _repo(self, directory, *, readings_table, write_readings=True):
        root = Path(directory)
        acceptances = []
        for name in ("a", "b"):
            evidence = "docs/evidence/reading-" + name + ".json"
            if write_readings:
                (root / evidence).parent.mkdir(parents=True, exist_ok=True)
                (root / evidence).write_text('{"per_position": {}}\n')
            acceptances.append({
                "acceptance_id": "ACCEPT_" + name, "company_id": "marriott_international",
                "metric_id": "C04", "period_end": "2025-12-31", "accepted_value": "0",
                "method": "m", "what_this_does_not_establish": "w", "evidence": evidence,
                "read_from": {"document": "d"},
                "checked_identity": {"period_start": "2025-01-01", "period_end": "2025-12-31",
                                     "unit": "flag", "scope_key": "sha256:" + "a" * 64,
                                     "value_kind": None,
                                     "spec_closure_hash": "sha256:" + "c" * 64,
                                     "filings": [ACCESSION], "entities": [],
                                     "established_by": "BOUND_AFTER_THE_READING"}})
        table = readings_table(root, [entry["evidence"] for entry in acceptances])
        register = {"record_type": "INDEPENDENT_CONTENT_ACCEPTANCE_REGISTER",
                    "acceptances": acceptances, **({} if table is None else {"readings": table})}
        (root / ACCEPTANCE_REGISTER_PATH).parent.mkdir(parents=True, exist_ok=True)
        (root / ACCEPTANCE_REGISTER_PATH).write_text(json.dumps(register))
        return root

    @staticmethod
    def _hashed(root, sources):
        return {source: {"content_sha256": "sha256:" + _digest(root / source)}
                for source in sources}

    def _states(self, **arguments):
        with TemporaryDirectory() as directory:
            root = self._repo(directory, **arguments)
            return {entry["acceptance_id"]: entry["grant_state"]
                    for entry in independent_content_acceptances(repo_root=root)}

    def test_a_fully_hashed_table_grants(self):
        self.assertEqual({"ACCEPT_a": READING_GRANTING, "ACCEPT_b": READING_GRANTING},
                         self._states(readings_table=self._hashed))

    def test_a_missing_empty_or_silent_table_does_not_skip_the_check(self):
        cases = {"missing": lambda root, sources: None,
                 "empty": lambda root, sources: {},
                 "silent about one": lambda root, sources: self._hashed(root, sources[:1]),
                 "malformed hash": lambda root, sources: {
                     source: {"content_sha256": "not-a-hash"} for source in sources}}
        expected = {"missing": (READING_NOT_HASHED, READING_NOT_HASHED),
                    "empty": (READING_NOT_HASHED, READING_NOT_HASHED),
                    "silent about one": (READING_GRANTING, READING_NOT_HASHED),
                    "malformed hash": (READING_NOT_HASHED, READING_NOT_HASHED)}
        for label, table in cases.items():
            with self.subTest(label):
                states = self._states(readings_table=table)
                self.assertEqual(expected[label], (states["ACCEPT_a"], states["ACCEPT_b"]))

    def test_unreadable_changed_and_unhashed_are_three_states(self):
        with TemporaryDirectory() as directory:
            root = self._repo(directory, readings_table=self._hashed)
            (root / "docs/evidence/reading-a.json").write_text('{"changed": true}\n')
            (root / "docs/evidence/reading-b.json").unlink()
            states = {entry["acceptance_id"]: entry["grant_state"]
                      for entry in independent_content_acceptances(repo_root=root)}
        self.assertEqual({"ACCEPT_a": READING_CHANGED, "ACCEPT_b": READING_UNREADABLE}, states)
        self.assertEqual(4, len({READING_GRANTING, READING_CHANGED, READING_UNREADABLE,
                                 READING_NOT_HASHED}))

    def test_a_reading_that_contributes_nothing_is_a_legal_table_entry(self):
        """A completed reading that accepted nothing updates the table normally."""
        def with_a_silent_reading(root, sources):
            extra = "docs/evidence/reading-empty.json"
            (root / extra).write_text('{"per_position": {}}\n')
            return {**self._hashed(root, sources), extra:
                    {"content_sha256": "sha256:" + _digest(root / extra),
                     "acceptances_contributed": 0}}
        self.assertEqual({READING_GRANTING},
                         set(self._states(readings_table=with_a_silent_reading).values()))

    def test_the_position_says_which_failure_it_was(self):
        """Not granting, and not about this result, are different findings."""
        with TemporaryDirectory() as directory:
            root = self._repo(directory, readings_table=lambda root, sources:
                              self._hashed(root, sources[:1]))
            acceptances = independent_content_acceptances(repo_root=root)
        granting = [e for e in acceptances if e["grant_state"] == READING_GRANTING]
        silent = [e for e in acceptances if e["grant_state"] == READING_NOT_HASHED]
        result = {"value": "0", **{field: granting[0]["checked_identity"][field]
                                   for field in ACCEPTANCE_IDENTITY_FIELDS}}
        coordinate = {"company_id": "marriott_international", "metric_id": "C04",
                      "report_end": "2025-12-31"}
        accepted, reason, _ = _acceptance_for_position(acceptances=granting, result=result,
                                                       **coordinate)
        self.assertEqual("ACCEPT_a", accepted["acceptance_id"])
        self.assertIsNone(reason)
        accepted, reason, findings = _acceptance_for_position(acceptances=silent,
                                                              result=result, **coordinate)
        self.assertIsNone(accepted)
        self.assertEqual("NOT_PROVEN:ACCEPTANCE_NOT_GRANTING:" + READING_NOT_HASHED, reason)
        accepted, reason, findings = _acceptance_for_position(
            acceptances=granting, result={**result, "unit": "count"}, **coordinate)
        self.assertIsNone(accepted)
        self.assertEqual("NOT_PROVEN:ACCEPTANCE_DOES_NOT_MATCH_THIS_RESULT:unit", reason)
        self.assertEqual(["unit"], findings[0]["fields_that_differ"])


if __name__ == "__main__":
    unittest.main()
