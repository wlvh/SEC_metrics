"""Issue #47's acquisition chain, offline: allowance, count, request, save, install.

The chain is exercised with recorded responses because Issue #47 has no SEC
allowance. That is the point of building it now rather than beside a grant: an
execution path that first runs on the day it is authorized is a path nobody has
run, and the failures in this repository's history are mostly of the shape
"each part worked alone and the seam did not".

The load-bearing cases here are the ones that would pass under a weaker
implementation: that a failed request still consumes a call, that a claim with
no terminal blocks the channel, that the provenance guarantee comes from the
frozen validator rather than from a self-consistent record, and that nothing
in the recorded path opens a socket.
"""
from pathlib import Path
from unittest.mock import patch
import ast
import atexit
import copy
import hashlib
import importlib.util
import inspect
import json
import os
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import types
import unittest

from vnext.canonical import canonical_json_bytes, content_hash, strict_json_file, strict_json_loads
from vnext.continuous_sec_acquisition import validate_acquisition_checkpoint
from vnext.annual_update import saved_source
from vnext.historical_sec_session import HistoricalCallLedger as SESSION_LEDGER
from vnext.historical_sec_session import (HistoricalSessionError,
                                          install_historical_source_inputs,
                                          live_historical_session,
                                          recorded_historical_session,
                                          verify_offline_wiring)
from vnext.historical_event_sources import (EVENT_METRICS, declare_event_sources,
                                            _registry_row, _window)
from vnext.historical_source_acquisition import (POLICY_PATH, DELEGATION_TYPE,
                                                 APPROVAL_RECORD_PATH,
                                                 TRUSTED_APPROVER, TRUSTED_REPOSITORY,
                                                 HistoricalAcquisitionError,
                                                 acquisition_allowance,
                                                 declared_dependencies,
                                                 declared_frame,
                                                 historical_dependency,
                                                 request_is_in_scope)
from vnext.normal_annual_input import _subject_policy
from vnext.normal_governance_input import _Sources, _filings, _history_index
from vnext.normal_history_catalog import target_period_candidates
from vnext.normal_source_authority import MANIFEST_PATH, ROOT
from vnext.normal_zero_ai_results import _event_sources
from vnext.ordinary_source_authority import checkpoint_installation
from sec_urls import submissions_file_url, submissions_url


def _tip(checkout=ROOT):
    """What the branch tip carries, for a case whose checkout is at the tip: its export index."""
    path = Path(checkout) / "evidence/issue47_acquired/export.json"
    return path.read_bytes() if path.is_file() else None


def _load_tool(name, relative):
    """Import a ``tools/`` entry point by path; the directory is not a package."""
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# The build side. Tests may import it; the business module may not, which is
# the whole point of it living here.
WIRING = _load_tool("vnext_historical_wiring", "tools/vnext_historical_wiring.py")


def _receipt_under_check():
    """Which receipt this run is asking about.

    The builder produces a candidate, checks it, and only then installs it, so
    it points these cases at the candidate by name. A hard-coded default would
    make them answer about the file already on disk - the one file the run did
    not produce - which is how an unchecked artifact came to be accepted while
    it was still being checked. Standalone runs still get the installed path.
    """
    return os.environ.get(WIRING.RECEIPT_PATH_VARIABLE, WIRING.RECEIPT_PATH)


# How "this class reads the receipt the run produces" is detected, assembled
# out here rather than inside the class that scans with it: a scanner whose
# own body spells its tokens matches itself, which is exactly how the first
# version of that check flagged the class doing the scanning.
RECEIPT_READER_TOKENS = ("_receipt_under_check" + "()",
                         WIRING.RECEIPT_PATH.rsplit("/", 1)[1])

_FRAMES = {}


# ------------------------------------------------ one frame per exact data root
# Planning a company's declared frame is most of what a recorded capture costs:
# measured over this module, 26 captures spent 457 of 969 seconds in it, and 21
# of them planned Marriott on a freshly installed baseline whose files are byte
# for byte those of every other fresh baseline - 336 seconds computing one
# answer 21 times, while the saved-source CI tier ran out of time before any of
# its cases failed. The frame is a function of the company, the years and the
# files under the data root, so the session's reference is replaced for this
# module's run by one that computes it once per exact root content and hands
# each capture a fresh copy. The key is every entry under the root - its
# relative path, its kind (a symlink is not the file it points at), its mode
# and the SHA-256 of its bytes - so a case that deletes, adds, edits or
# relinks anything gets a real computation, which is what the cases about
# tampered evidence need. A frame that raises is never kept. Cases that patch
# the reference themselves still do; the patch sits on top of this one.
_SHARED_FRAMES = {}
_REAL_DECLARED_FRAME = []


def _root_content(root):
    digest = hashlib.sha256()
    root = Path(root)
    for path in sorted(root.rglob("*")):
        status = path.lstat()
        digest.update(str(path.relative_to(root)).encode("utf-8") + b"\0"
                      + str(stat.S_IFMT(status.st_mode)).encode() + b"\0"
                      + str(stat.S_IMODE(status.st_mode)).encode() + b"\0")
        if stat.S_ISLNK(status.st_mode):
            digest.update(os.readlink(path).encode("utf-8"))
        elif stat.S_ISREG(status.st_mode):
            digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def _shared_frame(**arguments):
    key = (arguments.get("company_id"), arguments.get("years"),
           _root_content(arguments["repo_root"]))
    if key not in _SHARED_FRAMES:
        _SHARED_FRAMES[key] = _REAL_DECLARED_FRAME[0](**arguments)
    return copy.deepcopy(_SHARED_FRAMES[key])


def setUpModule():
    from vnext import historical_sec_session as session_module
    _REAL_DECLARED_FRAME.append(session_module.declared_frame)
    patcher = patch.object(session_module, "declared_frame", _shared_frame)
    patcher.start()
    unittest.addModuleCleanup(patcher.stop)


def _frame(company_id):
    """One declaration per company per process, deep-copied to each caller.

    Building it reads a company's whole saved submissions history - ten
    seconds for JPMorgan's sixty-nine shards - and twelve cases ask for one.
    It is an input here and never the thing under assertion: every case that
    uses it asserts what the gate, the union or the route does *with* the
    rows, so sharing the rows weakens nothing. The copy is what keeps that
    true, since a case that mutated a shared row would change another's input.
    """
    if company_id not in _FRAMES:
        _FRAMES[company_id] = declared_frame(repo_root=ROOT, company_id=company_id)
    return copy.deepcopy(_FRAMES[company_id])


def _rows(company_id):
    return _frame(company_id)["requirements"]


_EVENTS = {}


def _events(company_id):
    """The event declaration alone, shared on the same terms as the frame."""
    if company_id not in _EVENTS:
        _EVENTS[company_id] = declare_event_sources(repo_root=ROOT,
                                                    company_id=company_id, count=5)
    return copy.deepcopy(_EVENTS[company_id])

# A declared Marriott dependency: the prior annual primary accession index that
# B02 reads. Taken from the planner's own output, not written by hand.
DECLARED = ("https://www.sec.gov/Archives/edgar/data/1048286/"
            "000162828021002433/index.json")
OTHER_COMPANY = "ford_motor_company"
BODY = json.dumps({"directory": {"item": [], "name": "recorded-development-fixture"}}).encode()


def _seal(body, field):
    return {**body, field: content_hash(value=body)}


class _Chain:
    """One successful recorded capture, installed once and copied per test.

    Installing the baseline corpus is the expensive step and it is an input,
    never the thing under assertion, so sharing it does not weaken a case.

    It also removes itself at exit. An installed corpus is large, every
    recorded session makes one, and an earlier version of this file left one
    behind per process - which eventually filled the disk and turned every
    case in the suite into an unrelated OSError. A fixture that leaks is a
    fixture that will one day be blamed for a defect it did not cause.
    """

    root = None
    result = None

    @classmethod
    def build(cls):
        if cls.root is not None:
            return
        cls.root = Path(tempfile.mkdtemp(prefix="issue47-chain-"))
        atexit.register(shutil.rmtree, cls.root, ignore_errors=True)
        session = recorded_historical_session(root=cls.root / "ledger", response=BODY)
        cls.result = session.capture(company_id="marriott_international", url=DECLARED)

    @classmethod
    def copy(cls, destination):
        cls.build()
        _copy_ledger(cls.root / "ledger", destination)
        return destination


def _rewrite_log_row(log, index, row):
    """Replace one request-log row, keeping the file's own header and line ends."""
    import csv
    import io
    from sec_http import REQUEST_LOG_FIELDNAMES
    text = log.read_text(encoding="utf-8")
    rows = list(csv.DictReader(io.StringIO(text)))
    rows[index] = row
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=REQUEST_LOG_FIELDNAMES,
                            lineterminator="\r\n" if "\r\n" in text else "\n")
    writer.writeheader()
    writer.writerows(rows)
    log.write_text(out.getvalue(), encoding="utf-8")


def _copy_ledger(source, destination):
    """A ledger with its initialization anchor and its claim-log copy, which live beside it.

    Copying only the directory leaves them behind, and a ledger with a binding
    and no anchor, or no copy of its claim log, is refused as one reset.
    """
    shutil.copytree(source, destination)
    shutil.copyfile(SESSION_LEDGER.anchor_path(source), SESSION_LEDGER.anchor_path(destination))
    shutil.copyfile(SESSION_LEDGER.mirror_path(source), SESSION_LEDGER.mirror_path(destination))


class TheChainProducesASourceTheExistingReaderAccepts(unittest.TestCase):
    """The deliverable is not a receipt; it is a source something can read."""

    @classmethod
    def setUpClass(cls):
        _Chain.build()

    def test_one_capture_runs_gate_request_save_and_checkpoint(self):
        self.assertEqual(_Chain.result["status"], "SUCCEEDED")
        self.assertEqual(_Chain.result["calls"], [0, 0, 0],
                         "a recorded capture is not a real SEC call")
        self.assertIs(_Chain.result["production_authorized"], False)
        self.assertEqual(_Chain.result["terminal"]["counts"], [0, 0, 1],
                         "the ledger still consumed its slot")

    def test_the_unmodified_downstream_finds_and_verifies_the_source(self):
        from vnext.ordinary_source_authority import (checkpoint_installation,
                                                     verify_ordinary_source_proofs)
        data_root = _Chain.root / "ledger/source-inputs"
        checkpoint, paths = checkpoint_installation(source_root=data_root)
        self.assertEqual(checkpoint["checkpoint_id"], _Chain.result["checkpoint_id"])
        self.assertEqual(checkpoint["execution_mode"], "RECORDED_TEST_ONLY")
        self.assertEqual(checkpoint["source_credit"], "RECORDED_TEST_ONLY")
        self.assertTrue(paths, "the acquired attempt carries its body and headers")
        proof = checkpoint["captures"][0]["receipt"]["proof"]
        self.assertTrue(verify_ordinary_source_proofs(data_root=data_root, proofs=[proof]))

    def test_attribution_is_separate_from_the_shared_checkpoint(self):
        # The shared journal record carries mode and captures but not an issue,
        # so reading it as Issue #47 credit would be reading in something that
        # is not there. The attribution record beside this ledger is where the
        # issue is named, and the ledger's own slots name it too.
        from vnext.ordinary_source_authority import checkpoint_installation
        checkpoint = checkpoint_installation(
            source_root=_Chain.root / "ledger/source-inputs")[0]
        self.assertNotIn("issue_47_v1", json.dumps(
            {key: checkpoint[key] for key in
             ("record_type", "execution_mode", "source_credit", "real_sec_credit")}),
            "the shared record does not carry the issue")
        written = sorted((_Chain.root / "ledger/acquisition-attribution").iterdir())
        self.assertEqual(len(written), 1)
        attribution = strict_json_file(path=written[0])
        self.assertEqual(attribution["requirement_id"], "issue_47_v1")
        self.assertEqual(attribution["checkpoint_id"], _Chain.result["checkpoint_id"])
        self.assertEqual(attribution["ledger_sha256"], checkpoint["ledger_sha256"])
        self.assertIn("not Issue #47 credit by itself",
                      attribution["what_the_shared_checkpoint_does_not_say"])
        slot = strict_json_file(path=_Chain.root / "ledger/calls/0001/intent.json")
        self.assertEqual(slot["requirement_id"], "issue_47_v1")


class TheGuaranteeComesFromTheFrozenValidator(unittest.TestCase):
    """A self-consistent record is not provenance; the frozen replay is."""

    @classmethod
    def setUpClass(cls):
        _Chain.build()

    def _checkpoint(self):
        from vnext.ordinary_source_authority import checkpoint_installation
        return checkpoint_installation(source_root=_Chain.root / "ledger/source-inputs")[0]

    def test_a_resealed_record_that_disagrees_with_the_ledger_is_rejected(self):
        # Re-sealing keeps every hash self-consistent, so a validator that only
        # checked its own seals would accept this. The row it names no longer
        # matches the ledger, which is what must be caught.
        data_root = _Chain.root / "ledger/source-inputs"
        baseline = strict_json_file(path=ROOT / MANIFEST_PATH)
        checkpoint = self._checkpoint()
        capture = dict(checkpoint["captures"][0])
        receipt = dict(capture["receipt"])
        row = dict(receipt["ledger_row"])
        row["content_sha256"] = "0" * 64
        receipt["ledger_row"] = row
        receipt.pop("receipt_id")
        capture["receipt"] = _seal(receipt, "receipt_id")
        altered = dict(checkpoint)
        altered["captures"] = [capture]
        altered.pop("checkpoint_id")
        with self.assertRaises(Exception) as caught:
            validate_acquisition_checkpoint(data_root, _seal(altered, "checkpoint_id"),
                                            baseline)
        self.assertIn("CHANGED", str(caught.exception))

    def test_a_recorded_capture_cannot_be_relabelled_live(self):
        data_root = _Chain.root / "ledger/source-inputs"
        baseline = strict_json_file(path=ROOT / MANIFEST_PATH)
        checkpoint = dict(self._checkpoint())
        checkpoint["execution_mode"] = "LIVE"
        checkpoint["real_sec_credit"] = True
        checkpoint["source_credit"] = "VERIFIED_SEC_ACQUISITION"
        checkpoint.pop("checkpoint_id")
        with self.assertRaises(Exception) as caught:
            validate_acquisition_checkpoint(data_root, _seal(checkpoint, "checkpoint_id"),
                                            baseline)
        self.assertIn("CHANGED", str(caught.exception))


class TheSessionActuallyRoutesThroughTheFrozenValidator(unittest.TestCase):
    """Proving the validator works is not proving this session calls it.

    Added after a fault injection: replacing the ``validate_acquisition_
    checkpoint`` call in ``register_checkpoint`` with ``pass`` left all the
    other cases green, because they exercise the validator directly. The
    module's central claim - that the provenance guarantee rests on frozen
    code - had no case defending it.
    """

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="issue47-routed-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def test_a_capture_calls_the_frozen_replay_once_on_what_it_enrolls(self):
        import vnext.continuous_sec_acquisition as frozen
        seen = []
        real = frozen.validate_acquisition_checkpoint

        def watched(data_root, checkpoint, baseline):
            seen.append((Path(data_root), checkpoint))
            return real(data_root, checkpoint, baseline)

        session = recorded_historical_session(root=self.root / "ledger", response=BODY)
        with patch.object(frozen, "validate_acquisition_checkpoint", watched):
            result = session.capture(company_id="marriott_international", url=DECLARED)
        self.assertEqual(len(seen), 1, "exactly one replay, over the whole ledger")
        data_root, checked = seen[0]
        self.assertEqual(data_root, session.data_root,
                         "the replay must read this session's own installed root")
        self.assertEqual(checked["checkpoint_id"], result["checkpoint_id"],
                         "the record replayed is the record returned")

    def test_a_refused_replay_enrolls_nothing(self):
        from vnext.continuous_sec_acquisition import _journal
        import vnext.continuous_sec_acquisition as frozen
        session = recorded_historical_session(root=self.root / "ledger2", response=BODY)
        before = set(_journal().iterdir()) if _journal().is_dir() else set()
        with patch.object(frozen, "validate_acquisition_checkpoint",
                          side_effect=ValueError("SEC_ACQUISITION_CHECKPOINT_MODE_CHANGED")):
            with self.assertRaises(ValueError):
                session.capture(company_id="marriott_international", url=DECLARED)
        after = set(_journal().iterdir()) if _journal().is_dir() else set()
        self.assertEqual(before, after,
                         "a checkpoint the replay refused must not reach the journal")


class TheGateRefusesWhatNothingDeclared(unittest.TestCase):
    """The declaration is what may be fetched; the plan is not a suggestion."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="issue47-gate-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def test_an_undeclared_url_is_refused_by_name(self):
        session = recorded_historical_session(root=self.root / "ledger", response=BODY)
        undeclared = "https://www.sec.gov/Archives/edgar/data/1048286/undeclared.htm"
        with self.assertRaises(HistoricalAcquisitionError) as caught:
            session.capture(company_id="marriott_international", url=undeclared)
        self.assertIn("HISTORICAL_URL_IS_NOT_A_DECLARED_DEPENDENCY", str(caught.exception))
        self.assertFalse((self.root / "ledger/calls").exists(),
                         "a refused URL must not consume a slot")

    def test_a_url_declared_for_one_company_is_not_declared_for_another(self):
        # Load-bearing: a gate that accepted any declared URL regardless of
        # company would pass the case above and fail only here.
        session = recorded_historical_session(root=self.root / "ledger2", response=BODY)
        with self.assertRaises(HistoricalAcquisitionError) as caught:
            session.capture(company_id=OTHER_COMPANY, url=DECLARED)
        self.assertIn("HISTORICAL_URL_IS_NOT_A_DECLARED_DEPENDENCY", str(caught.exception))


class TheCountIsCumulativeAndCountsFailures(unittest.TestCase):
    """A ceiling that only counted successes would not be a ceiling."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="issue47-count-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def test_a_failed_request_consumes_its_call_and_admits_no_source(self):
        ledger = self.root / "ledger"
        session = recorded_historical_session(root=ledger, response=b"", status=404)
        result = session.capture(company_id="marriott_international", url=DECLARED)
        self.assertEqual(result["status"], "FAILED_TERMINAL")
        self.assertIsNone(result["receipt"]["proof"],
                          "a failed request cannot admit a source")
        self.assertEqual(session.ledger.snapshot()["counts"], [0, 0, 1],
                         "the failure still consumed a call")

    def test_the_cumulative_limit_stops_the_next_capture(self):
        ledger = self.root / "ledger-limit"
        first = recorded_historical_session(root=ledger, response=BODY, limits=(0, 0, 1))
        first.capture(company_id="marriott_international", url=DECLARED)
        second = recorded_historical_session(root=ledger, response=BODY, limits=(0, 0, 1))
        with self.assertRaises(HistoricalSessionError) as caught:
            second.capture(company_id="marriott_international",
                           url=DECLARED.replace("index.json", "mar-20201231.htm"))
        self.assertIn("ISSUE_47_CUMULATIVE_LIMIT_REACHED", str(caught.exception))

    def test_a_claim_with_no_terminal_blocks_the_channel(self):
        # An intent with no terminal means the request may have gone out and
        # nobody knows. Continuing past it is what makes a cumulative number
        # untrustworthy, so it stops the channel rather than being skipped.
        ledger = _Chain.copy(self.root / "lost")
        (ledger / "calls/0001/terminal.json").unlink()
        session = recorded_historical_session(root=ledger, response=BODY)
        with self.assertRaises(HistoricalSessionError) as caught:
            session.capture(company_id="marriott_international", url=DECLARED)
        self.assertIn("ISSUE_47_UNRESOLVED_TERMINAL_BLOCKS_THE_CHANNEL",
                      str(caught.exception))
        self.assertIn("0001", str(caught.exception))


class TheGrantedPathIsSeparateFromTheTestPath(unittest.TestCase):
    """Recorded work must not be able to write where a grant is counted."""

    def test_live_refuses_where_no_allowance_is_registered(self):
        # Asked of a tree without an allowance rather than of this checkout,
        # which will hold one once the owner registers the approval. The
        # refusal must come from the gate, before any transport exists.
        with tempfile.TemporaryDirectory(prefix="issue47-no-grant-") as empty:
            with patch("vnext.historical_sec_session.ROOT", Path(empty)), \
                    patch("vnext.historical_sec_session.SecHttpClient",
                          side_effect=AssertionError("a transport was built")):
                with self.assertRaises(HistoricalAcquisitionError) as caught:
                    live_historical_session(branch_tip=lambda: self.fail(
                        "the branch was read before the allowance refused"))
        self.assertIn("ISSUE_47_SEC_ALLOWANCE_NOT_GRANTED", str(caught.exception))
        self.assertIn(POLICY_PATH, str(caught.exception))

    def test_a_recorded_session_cannot_use_a_granted_budget_root(self):
        from vnext.continuous_call_policy import POLICY_PATH as continuous
        granted = strict_json_file(path=ROOT / continuous)["budget_root"]
        with self.assertRaises(HistoricalSessionError) as caught:
            recorded_historical_session(root=Path(granted), response=BODY)
        self.assertIn("ISSUE_47_TEST_CANNOT_USE_A_GRANTED_LEDGER", str(caught.exception))

    def test_a_recorded_session_refuses_to_be_handed_no_response(self):
        with self.assertRaises(HistoricalSessionError) as caught:
            recorded_historical_session(root=Path(tempfile.mkdtemp()), response=None)
        self.assertIn("ISSUE_47_TRANSPORT_MODE_CHANGED", str(caught.exception))


class AGrantMustBindToAWiringReceiptThatIsStillTrue(unittest.TestCase):
    """The receipt is what makes "it was exercised offline" checkable later.

    Issue #28's live path carries the same requirement. Without it, a grant
    could point at a receipt written before the chain changed, which is the
    same failure as a stale manifest: the evidence describes a version that is
    no longer the one that would run.
    """

    def setUp(self):
        self.RECEIPT = _receipt_under_check()

    def test_the_committed_receipt_verifies_against_the_current_tree(self):
        receipt = verify_offline_wiring(receipt_path=self.RECEIPT)
        self.assertEqual(receipt["requirement_id"], "issue_47_v1")
        self.assertEqual(receipt["calls"], [0, 0, 0])
        self.assertEqual(receipt["execution_mode"], "RECORDED_TEST_ONLY")
        self.assertIs(receipt["real_sec_credit"], False)
        self.assertIn("frozen under issue_28_v14", receipt["checkpoint_validated_by"])

    def test_a_receipt_naming_a_changed_file_is_refused(self):
        # Load-bearing: a check that only read the flags would pass every other
        # case here and still accept a receipt for code that has since changed.
        original = strict_json_file(path=ROOT / self.RECEIPT)
        stale = dict(original)
        stale["evidence"] = {**original["evidence"],
                             "scripts/vnext/historical_sec_session.py": "0" * 64}
        stale.pop("receipt_id")
        scratch = Path(tempfile.mkdtemp(prefix="issue47-stale-"))
        self.addCleanup(shutil.rmtree, scratch, ignore_errors=True)
        relative = "docs/evidence/issue47_history/acquisition-wiring/stale.json"
        target = ROOT / relative
        self.addCleanup(target.unlink, missing_ok=True)
        target.write_text(json.dumps(_seal(stale, "receipt_id")), encoding="utf-8")
        with self.assertRaises(HistoricalSessionError) as caught:
            verify_offline_wiring(receipt_path=relative)
        self.assertIn("ISSUE_47_OFFLINE_WIRING_EVIDENCE_CHANGED", str(caught.exception))
        self.assertIn("historical_sec_session.py", str(caught.exception))

    def test_the_receipt_accounts_for_the_suite_as_it_stands_now(self):
        # What the hand-maintained selector list used to be for, moved to
        # where it can be derived: the record says which cases the suite
        # declared, and this compares that against reading the suite.
        summary = WIRING.check(receipt_path=self.RECEIPT)
        self.assertEqual("OFFLINE_WIRING_CURRENT", summary["status"])
        receipt = strict_json_file(path=ROOT / self.RECEIPT)
        run = receipt["verification_run"]
        self.assertEqual(WIRING.declared_cases(), sorted(run["classes_declared"]))
        self.assertEqual(sorted(WIRING.RECEIPT_DEPENDENT),
                         sorted(run["classes_excluded"]))
        self.assertGreaterEqual(run["tests_run"], len(run["classes_run"]))

    def test_a_run_that_covered_only_part_of_the_suite_is_refused(self):
        # Load-bearing: this is the defect the previous version shipped - a
        # green run that excluded every regression the round had added. A
        # verifier that only read the pass flag accepts it.
        original = strict_json_file(path=ROOT / self.RECEIPT)
        partial = {k: v for k, v in original.items() if k != "receipt_id"}
        run = dict(original["verification_run"])
        dropped = sorted(run["classes_run"])[0]
        run["classes_run"] = [n for n in run["classes_run"] if n != dropped]
        partial["verification_run"] = run
        relative = "docs/evidence/issue47_history/acquisition-wiring/_partial.json"
        target = ROOT / relative
        self.addCleanup(target.unlink, missing_ok=True)
        target.write_text(json.dumps(_seal(partial, "receipt_id")), encoding="utf-8")
        with self.assertRaises(HistoricalSessionError) as caught:
            verify_offline_wiring(receipt_path=relative)
        self.assertIn("ISSUE_47_OFFLINE_WIRING_CASES_NOT_ACCOUNTED_FOR",
                      str(caught.exception))
        self.assertIn(dropped, str(caught.exception))

    def test_a_case_counted_as_both_run_and_excluded_is_refused(self):
        # Otherwise the partition check above is satisfiable by moving a name
        # into both lists, which would let an excluded class be reported as
        # covered.
        original = strict_json_file(path=ROOT / self.RECEIPT)
        doubled = {k: v for k, v in original.items() if k != "receipt_id"}
        run = dict(original["verification_run"])
        run["classes_excluded"] = list(run["classes_excluded"]) + [run["classes_run"][0]]
        doubled["verification_run"] = run
        relative = "docs/evidence/issue47_history/acquisition-wiring/_doubled.json"
        target = ROOT / relative
        self.addCleanup(target.unlink, missing_ok=True)
        target.write_text(json.dumps(_seal(doubled, "receipt_id")), encoding="utf-8")
        with self.assertRaises(HistoricalSessionError) as caught:
            verify_offline_wiring(receipt_path=relative)
        self.assertIn("ISSUE_47_OFFLINE_WIRING_CASES_NOT_ACCOUNTED_FOR",
                      str(caught.exception))

    def test_a_receipt_claiming_success_it_did_not_have_is_refused(self):
        original = strict_json_file(path=ROOT / self.RECEIPT)
        forged = dict(original)
        forged["chain_executed_over_recorded_responses"] = False
        forged.pop("receipt_id")
        relative = "docs/evidence/issue47_history/acquisition-wiring/forged.json"
        target = ROOT / relative
        self.addCleanup(target.unlink, missing_ok=True)
        target.write_text(json.dumps(_seal(forged, "receipt_id")), encoding="utf-8")
        with self.assertRaises(HistoricalSessionError) as caught:
            verify_offline_wiring(receipt_path=relative)
        self.assertIn("ISSUE_47_OFFLINE_WIRING_CHANGED", str(caught.exception))


class TheRecordedPathOpensNoSocket(unittest.TestCase):
    """Zero egress is asserted by counting connects, not by trusting the mode."""

    def test_a_whole_recorded_capture_makes_no_connection(self):
        root = Path(tempfile.mkdtemp(prefix="issue47-egress-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        session = recorded_historical_session(root=root / "ledger", response=BODY)
        with patch.object(socket.socket, "connect",
                          side_effect=AssertionError("network forbidden")) as connect, \
             patch.object(socket.socket, "connect_ex",
                          side_effect=AssertionError("network forbidden")):
            result = session.capture(company_id="marriott_international", url=DECLARED)
        self.assertEqual(result["status"], "SUCCEEDED")
        self.assertEqual(connect.call_count, 0)


class TheInstallerCarriesTheRuleInputsItClaims(unittest.TestCase):
    """The installed root must hold the configuration the manifest records."""

    @classmethod
    def setUpClass(cls):
        # One installation for every case: it copies the whole baseline corpus,
        # and the cases ask different questions of the same result.
        cls.scratch = Path(tempfile.mkdtemp(prefix="issue47-install-"))
        atexit.register(shutil.rmtree, cls.scratch, ignore_errors=True)
        cls.installed = cls.scratch / "source-inputs"
        install_historical_source_inputs(root=cls.installed)

    def test_the_presentation_path_under_config_is_excluded(self):
        # It is installed from current bound code in the candidate runtime, and
        # it is under config/, so "copy the data directories" is not a
        # substitute for reading the parent's exclusion.
        self.assertTrue((self.installed / "config/company_registry.csv").is_file())
        self.assertFalse(
            (self.installed / "config/ordinary_public_projection_v1.json").is_file(),
            "the parent's presentation path must not be installed as a source input")

    def test_the_installed_root_answers_b13s_scope_question(self):
        # The measured failure. B13's scope is read from the approved
        # definition, which sits at the repository root, and the route reads it
        # from the data root. The installer copied config/ and catalog/ only -
        # the two directories the parent's installer knew - so a recorded run
        # over an installed root stopped with "No such file" at the definition.
        from vnext.historical_capacity_results import approved_scope
        self.assertEqual(approved_scope(repo_root=self.installed),
                         approved_scope(repo_root=ROOT))

    def test_every_rule_input_is_installed_and_no_code_is(self):
        # Both directions, because the rule can fail either way. Short, and a
        # route stops on a file a Run of this generation opens from the data
        # root. Long, and code sits in the data root where nothing is supposed
        # to import it from. A directory list is what was short; the rule is
        # the kind of file, not where it happens to live.
        from vnext.historical_sec_session import _presentation_paths
        presentation, manifest = _presentation_paths()
        authority = manifest["execution_authority"]["files"]
        expected = {p for p in authority if p not in presentation and not p.endswith(".py")}
        installed = {p for p in authority if (self.installed / p).is_file()}
        self.assertEqual(installed - expected, set(),
                         "code or presentation installed as a source input")
        self.assertEqual(expected - installed, set(), "rule inputs the installer missed")
        for relative in sorted(expected):
            raw = (self.installed / relative).read_bytes()
            self.assertEqual({"sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)},
                             authority[relative], relative)

    def test_an_unowned_existing_root_is_refused(self):
        root = Path(tempfile.mkdtemp(prefix="issue47-unowned-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        (root / "source-inputs").mkdir()
        with self.assertRaises(HistoricalSessionError) as caught:
            install_historical_source_inputs(root=root / "source-inputs")
        self.assertIn("ISSUE_47_SOURCE_ROOT_UNOWNED", str(caught.exception))


class RuleInputsFollowTheMintedGeneration(unittest.TestCase):
    """A re-mint may change a rule input; within one generation nothing may.

    The first ledger root stopped before its second round's first request:
    merging the base had changed a configuration file the parent generation
    records, the re-mint carried it, and the installer refused the new bytes
    because it allowed no difference at all.
    """

    RELATIVE = "config/issue28_normal_results_v2.json"  # a rule input, not a baseline file
    OLDER_STAMP = {"rule_inputs_sha256": "sha256:" + "0" * 64}

    @classmethod
    def setUpClass(cls):
        from vnext.historical_sec_session import RULE_INPUT_STAMP, RULE_INPUT_TRANSITIONS
        cls.scratch = Path(tempfile.mkdtemp(prefix="issue47-generation-"))
        atexit.register(shutil.rmtree, cls.scratch, ignore_errors=True)
        cls.root = cls.scratch / "source-inputs"
        install_historical_source_inputs(root=cls.root)
        cls.stamp_path = cls.root / RULE_INPUT_STAMP
        cls.transitions = cls.root / RULE_INPUT_TRANSITIONS
        # Saved as found, absent included, so a case that fails part way
        # leaves the next one the same root.
        cls.saved = {path: path.read_bytes() if path.exists() else None for path in (
            cls.root / cls.RELATIVE, cls.root / "config/company_registry.csv",
            cls.stamp_path, cls.transitions)}

    def setUp(self):
        self.addCleanup(self._restore)

    def _restore(self):
        for path, raw in self.saved.items():
            if raw is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(raw)

    def _records(self):
        return [json.loads(line) for line in self.transitions.read_text().splitlines()]

    def test_the_installation_records_the_generation_it_installed(self):
        records = self._records()
        self.assertEqual(1, len(records))
        self.assertIsNone(records[0]["from"])
        self.assertEqual(json.loads(self.stamp_path.read_text()), records[0]["to"])

    def test_within_one_generation_a_changed_input_is_refused(self):
        (self.root / self.RELATIVE).write_bytes(self.saved[self.root / self.RELATIVE] + b" ")
        with self.assertRaises(Exception) as caught:
            install_historical_source_inputs(root=self.root)
        self.assertIn("Immutable receipt bytes differ", str(caught.exception))
        self.assertEqual(1, len(self._records()), "a refusal records no transition")

    def test_a_new_generation_replaces_the_input_and_records_it(self):
        self.stamp_path.write_bytes(canonical_json_bytes(value=self.OLDER_STAMP))
        (self.root / self.RELATIVE).write_bytes(b'{"older": true}\n')
        install_historical_source_inputs(root=self.root)
        self.assertEqual(self.saved[self.root / self.RELATIVE],
                         (self.root / self.RELATIVE).read_bytes())
        last = self._records()[-1]
        self.assertEqual([self.RELATIVE], last["changed"], "only what differed is replaced")
        self.assertEqual(self.OLDER_STAMP, last["from"])
        install_historical_source_inputs(root=self.root)
        self.assertEqual(2, len(self._records()), "the next call is a check, not a transition")

    def test_a_root_from_before_the_stamp_takes_the_current_inputs(self):
        self.stamp_path.unlink()
        (self.root / self.RELATIVE).write_bytes(b'{"older": true}\n')
        install_historical_source_inputs(root=self.root)
        self.assertEqual(self.saved[self.root / self.RELATIVE],
                         (self.root / self.RELATIVE).read_bytes())
        self.assertIsNone(self._records()[-1]["from"])

    def test_a_baseline_file_is_never_replaced_as_a_rule_input(self):
        registry = self.root / "config/company_registry.csv"
        self.stamp_path.write_bytes(canonical_json_bytes(value=self.OLDER_STAMP))
        registry.write_bytes(self.saved[registry] + b"\n")
        with self.assertRaises(HistoricalSessionError) as caught:
            install_historical_source_inputs(root=self.root)
        self.assertIn("ISSUE_47_BASELINE_RULE_INPUT_CHANGED:config/company_registry.csv",
                      str(caught.exception))
        self.assertEqual(self.saved[registry] + b"\n", registry.read_bytes())


def _whole_envelope(scope):
    """One grant as large as the envelope, for cases about something other than grants."""
    return {"grant": "WHOLE_ENVELOPE", "company_ids": list(scope["company_ids"]),
            "dependency_classes": list(scope["dependency_classes"]),
            "earliest_report_end": scope["earliest_report_end"],
            "latest_report_end": scope["latest_report_end"]}


def _grant_tree(*, scope_overrides=None, body_overrides=None, digest=None, url=None,
                repository="wlvh/SEC_metrics", approver=None):
    """A tree holding a real, internally consistent Issue #47 allowance.

    Built rather than fixtured, because every case needs to move exactly one
    field and see the refusal name that field. ``repository`` is separate from
    ``url`` on purpose: a policy that declares this repository while pointing
    at another one's comment is precisely the case worth refusing.
    """
    root = Path(tempfile.mkdtemp(prefix="issue47-grant-"))
    budget = Path(tempfile.mkdtemp(prefix="issue47-budget-"))
    for leaked in (root, budget):
        atexit.register(shutil.rmtree, leaked, ignore_errors=True)
    scope = {"purposes": ["historical_five_year_source_acquisition"],
             "company_ids": ["marriott_international"],
             "dependency_classes": ["ACCESSION_INSTANCE_DISCOVERY",
                                    "ANNUAL_PERIOD_IDENTITY", "COMPANYFACTS",
                                    "FISCAL_EVENT_FILING", "SUBMISSIONS_HISTORY",
                                    "SUBMISSIONS_INDEX"],
             "earliest_report_end": "2000-01-01",
             "latest_report_end": "2099-12-31", **(scope_overrides or {})}
    scope.setdefault("grants", [_whole_envelope(scope)])
    limits = [0, 0, 80]
    approved = {"record_type": DELEGATION_TYPE, "requirement_id": "issue_47_v1",
                "maximum_additional_provider_paid_sec_calls": limits,
                "budget_root": str(budget), "scope": scope,
                "production_authorized": False, **(body_overrides or {})}
    body = json.dumps(approved, sort_keys=True)
    comment_url = url or ("https://github.com/" + repository
                          + "/issues/47#issuecomment-1")
    login = approver or repository.split("/")[0]
    comment = {"html_url": comment_url, "body": body, "id": 1,
               "issue_url": "https://api.github.com/repos/" + repository + "/issues/47",
               "user": {"login": login, "id": 30534800, "type": "User"},
               "author_association": "OWNER", "created_at": "2026-09-27T00:00:00Z",
               "updated_at": "2026-09-27T00:00:00Z", "performed_via_github_app": None}
    (root / "docs").mkdir(parents=True)
    (root / "docs/delegation.json").write_text(json.dumps(comment), encoding="utf-8")
    (root / "config").mkdir(parents=True)
    (root / POLICY_PATH).write_text(json.dumps({
        "requirement_id": "issue_47_v1", "repository": repository,
        "approver_login": login, "delegation_url": comment_url,
        "delegation_body_sha256": digest or hashlib.sha256(body.encode()).hexdigest(),
        "delegation_record_path": "docs/delegation.json", "budget_root": str(budget),
        "maximum_additional_provider_paid_sec_calls": limits, "scope": scope,
        "sec_wiring_receipt_path": ("docs/evidence/issue47_history/"
                                    "acquisition-wiring/offline-wiring-receipt.json"),
    }), encoding="utf-8")
    return root, budget


class AnAllowanceMustBeVerifiedNotMerelyPresent(unittest.TestCase):
    """Field presence is not authorization.

    Reproduced before this was written: a policy carrying
    ``delegation_url = "NOT-A-URL-AT-ALL"`` and
    ``delegation_body_sha256 = "NOT-A-DIGEST"`` built a LIVE session and passed
    the pre-request check, because no code path read the body those fields
    describe.
    """

    def setUp(self):
        self.made = []
        self.addCleanup(lambda: [shutil.rmtree(p, ignore_errors=True)
                                 for pair in self.made for p in pair])

    def _tree(self, **kwargs):
        pair = _grant_tree(**kwargs)
        self.made.append(pair)
        return pair

    def test_a_valid_grant_is_read_hashed_and_accepted(self):
        # The legal branch, exercised rather than assumed. A suite that only
        # tested refusals would pass with a verifier that refuses everything.
        root, budget = self._tree()
        allowance = acquisition_allowance(repo_root=root)
        self.assertEqual(allowance["requirement_id"], "issue_47_v1")
        self.assertEqual(allowance["approved_delegation"]["record_type"], DELEGATION_TYPE)
        self.assertEqual(allowance["budget_root"], str(budget))

    def test_a_digest_that_matches_nothing_is_refused(self):
        root, _ = self._tree(digest="0" * 64)
        with self.assertRaises(HistoricalAcquisitionError) as caught:
            acquisition_allowance(repo_root=root)
        self.assertIn("ISSUE_47_DELEGATION_BODY_DOES_NOT_MATCH_ITS_DIGEST",
                      str(caught.exception))

    def test_a_non_digest_and_a_non_url_are_refused_by_shape(self):
        root, _ = self._tree(digest="NOT-A-DIGEST")
        with self.assertRaises(HistoricalAcquisitionError) as caught:
            acquisition_allowance(repo_root=root)
        self.assertIn("ISSUE_47_ALLOWANCE_DIGEST_IS_NOT_A_SHA256", str(caught.exception))
        root2, _ = self._tree(url="NOT-A-URL-AT-ALL")
        with self.assertRaises(HistoricalAcquisitionError) as caught:
            acquisition_allowance(repo_root=root2)
        self.assertIn("ISSUE_47_ALLOWANCE_URL_IS_NOT_THIS_ISSUE_S_COMMENT",
                      str(caught.exception))

    def test_a_policy_cannot_grant_more_than_the_body_approved(self):
        # Load-bearing: the policy file is a pointer to an approval, not a
        # second place the approval can be written. A verifier that read the
        # body but never compared it would pass every other case here.
        root, _ = self._tree(body_overrides={
            "scope": {"purposes": ["historical_five_year_source_acquisition"],
                      "company_ids": ["marriott_international"],
                      "dependency_classes": ["COMPANYFACTS"],
                      "earliest_report_end": "2024-01-01",
                      "latest_report_end": "2025-12-31"}})
        with self.assertRaises(HistoricalAcquisitionError) as caught:
            acquisition_allowance(repo_root=root)
        self.assertIn("ISSUE_47_ALLOWANCE_WIDENS_THE_APPROVED_GRANT:scope",
                      str(caught.exception))

    def test_a_request_outside_the_approved_scope_is_refused_before_any_request(self):
        root, budget = self._tree(scope_overrides={"company_ids": ["pfizer"]})
        # The body must agree, or the widening check fires first.
        record = json.loads((root / "docs/delegation.json").read_text())
        allowance = json.loads((root / POLICY_PATH).read_text())
        body = json.dumps({**json.loads(record["body"]),
                           "scope": allowance["scope"]}, sort_keys=True)
        record["body"] = body
        (root / "docs/delegation.json").write_text(json.dumps(record), encoding="utf-8")
        allowance["delegation_body_sha256"] = hashlib.sha256(body.encode()).hexdigest()
        (root / POLICY_PATH).write_text(json.dumps(allowance), encoding="utf-8")
        verified = acquisition_allowance(repo_root=root)
        row = _rows("marriott_international")[0]
        with self.assertRaises(HistoricalAcquisitionError) as caught:
            request_is_in_scope(allowance=verified, company_id="marriott_international",
                                dependency=row,
                                purpose="historical_five_year_source_acquisition")
        self.assertIn("ISSUE_47_COMPANY_NOT_IN_SCOPE", str(caught.exception))

    def test_the_whole_legal_path_runs_over_recorded_transport(self):
        # What the review asked for: not only "refuses when the file is
        # missing", but a grant that is read, hashed, scope-checked and then
        # actually used to capture.
        root, budget = self._tree()
        session = recorded_historical_session(root=budget / "ledger", response=BODY,
                                              allowance_root=root)
        result = session.capture(company_id="marriott_international", url=DECLARED)
        self.assertEqual(result["status"], "SUCCEEDED")
        self.assertEqual(result["calls"], [0, 0, 0])
        plan = strict_json_file(path=budget / "ledger/calls/0001/sec-plan.json")
        self.assertEqual(plan["scope_admission"]["company_id"], "marriott_international")
        self.assertTrue(plan["scope_admission"]["periods"])


class ATerminalFileIsNotAnOutcome(unittest.TestCase):
    """Four states, because collapsing them is what hid the defect.

    Reproduced before this was written: a terminal whose whole content was
    ``{}``, and a sealed terminal recording ``UNKNOWN_REMOTE_OUTCOME``, both
    stopped blocking the channel. Only an absent file blocked.
    """

    @classmethod
    def setUpClass(cls):
        _Chain.build()

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="issue47-terminal-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def _with_terminal(self, content, *, intent_id=None):
        ledger = _Chain.copy(self.root / ("slot-" + str(len(list(self.root.iterdir())))))
        slot = ledger / "calls/0001"
        intent = strict_json_file(path=slot / "intent.json")
        (slot / "terminal.json").unlink(missing_ok=True)
        if content is not None:
            body = content if intent_id is None else {**content, "intent_id": intent_id}
            (slot / "terminal.json").write_text(json.dumps(body), encoding="utf-8")
        session = recorded_historical_session(root=ledger, response=BODY)
        del intent
        try:
            session.ledger.require_unblocked()
            return None
        except HistoricalSessionError as error:
            return str(error)

    def test_a_known_failure_resolves_the_slot_and_the_run_continues(self):
        # Both records have to say the same thing now, which is the point: a
        # terminal that disagrees with its receipt is a fifth state, not a
        # failure that may be counted and moved past.
        sealed = strict_json_file(path=_Chain.root / "ledger/calls/0001/terminal.json")
        failed = {k: v for k, v in sealed.items()
                  if k not in {"terminal_id", "status", "stop_reason"}}
        failed.update({"status": "FAILED_TERMINAL", "stop_reason": ""})

        def all_three(ledger):
            # The logged row is the third record, and the one nothing in the
            # slot can rewrite for itself. A known failure is a row that
            # records one, so the row changes too and the receipt carries the
            # changed row, exactly as the SEC client would have written it.
            slot = ledger / "calls/0001"
            receipt = strict_json_file(path=slot / "sec-receipt.json")
            log = ledger / "source-inputs/evidence/requests_log.csv"
            index = receipt["ledger_row_index"]
            row = {**receipt["ledger_row"], "status_code": "404",
                   "error": "HTTP Error 404: Not Found"}
            _rewrite_log_row(log, index, row)
            changed = {k: v for k, v in receipt.items() if k != "receipt_id"}
            changed.update({"status": "FAILED_TERMINAL", "ledger_row": row})
            resealed = _seal(changed, "receipt_id")
            (slot / "sec-receipt.json").write_text(json.dumps(resealed), encoding="utf-8")
            bound = {**failed, "sec_receipt_id": resealed["receipt_id"]}
            (slot / "terminal.json").write_text(
                json.dumps(_seal(bound, "terminal_id")), encoding="utf-8")

        ledger = _Chain.copy(self.root / "known-failure")
        all_three(ledger)
        session = recorded_historical_session(root=ledger, response=BODY)
        session.ledger.require_unblocked()

    def test_a_failure_written_only_into_the_slot_is_not_a_known_failure(self):
        # The previous form of the case above: receipt and terminal say the
        # request failed while the row the client logged says it succeeded.
        # Resolving that would let a slot's own records overrule the log.
        sealed = strict_json_file(path=_Chain.root / "ledger/calls/0001/terminal.json")
        failed = {k: v for k, v in sealed.items()
                  if k not in {"terminal_id", "status", "stop_reason"}}
        failed.update({"status": "FAILED_TERMINAL", "stop_reason": ""})
        ledger = _Chain.copy(self.root / "slot-only-failure")
        slot = ledger / "calls/0001"
        receipt = strict_json_file(path=slot / "sec-receipt.json")
        changed = {k: v for k, v in receipt.items() if k != "receipt_id"}
        changed["status"] = "FAILED_TERMINAL"
        resealed = _seal(changed, "receipt_id")
        (slot / "sec-receipt.json").write_text(json.dumps(resealed), encoding="utf-8")
        (slot / "terminal.json").write_text(json.dumps(_seal(
            {**failed, "sec_receipt_id": resealed["receipt_id"]}, "terminal_id")),
            encoding="utf-8")
        session = recorded_historical_session(root=ledger, response=BODY)
        with self.assertRaises(HistoricalSessionError) as caught:
            session.ledger.require_unblocked()
        self.assertIn("TERMINAL_DISAGREES_WITH_THE_LOGGED_ROW:SUCCEEDED", str(caught.exception))

    def test_a_sealed_unknown_outcome_does_not_resolve_it(self):
        sealed = strict_json_file(
            path=_Chain.root / "ledger/calls/0001/terminal.json")
        unknown = {k: v for k, v in sealed.items()
                   if k not in {"terminal_id", "status", "stop_reason"}}
        unknown.update({"status": "UNKNOWN_REMOTE_OUTCOME",
                        "stop_reason": "UNKNOWN_REMOTE_OUTCOME"})
        message = self._with_terminal(_seal(unknown, "terminal_id"))
        self.assertIsNotNone(message)
        self.assertIn("OUTCOME_NOT_KNOWN", message)

    def test_an_empty_terminal_does_not_resolve_it(self):
        message = self._with_terminal({})
        self.assertIsNotNone(message)
        self.assertIn("TERMINAL_RECORD_DAMAGED", message)

    def test_a_terminal_bound_to_another_intent_does_not_resolve_it(self):
        sealed = strict_json_file(
            path=_Chain.root / "ledger/calls/0001/terminal.json")
        other = {k: v for k, v in sealed.items() if k != "terminal_id"}
        other["intent_id"] = "sha256:" + "f" * 64
        message = self._with_terminal(_seal(other, "terminal_id"))
        self.assertIsNotNone(message)
        self.assertIn("TERMINAL_BOUND_TO_ANOTHER_INTENT", message)

    def test_an_absent_terminal_still_blocks(self):
        message = self._with_terminal(None)
        self.assertIsNotNone(message)
        self.assertIn("TERMINAL_ABSENT", message)


class BelongingToTheTaskIsNotNeedingAFetch(unittest.TestCase):
    """Two questions the gate used to answer with one field.

    Reproduced before this was written: an already-saved declared dependency
    was refused as "not a declared dependency", and a planner row marked
    ``SNAPSHOT_REFRESH`` - intact bytes that disagree with their index - was
    short-circuited as a reuse and never reached a request.
    """

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="issue47-gate2-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def test_an_already_saved_dependency_resolves_and_reports_reuse(self):
        rows = _rows("marriott_international")
        saved = [r for r in rows if not r["new_acquisition_required"]]
        self.assertTrue(saved, "this company has saved dependencies to test with")
        row = historical_dependency(repo_root=ROOT,
                                    company_id="marriott_international",
                                    url=saved[0]["source_url"])
        self.assertEqual(row["source_url"], saved[0]["source_url"])
        session = recorded_historical_session(root=self.root / "ledger", response=BODY)
        result = session.capture(company_id="marriott_international",
                                 url=saved[0]["source_url"])
        self.assertEqual(result["status"], "EXISTING_VERIFIED_SOURCE_REUSED")
        self.assertEqual(result["calls"], [0, 0, 0])

    def test_a_snapshot_refresh_row_reaches_a_request(self):
        # Load-bearing: this row carries VERIFIED_SAVED_SOURCE *and*
        # new_acquisition_required, so an implementation reading only the
        # first field passes every other case and fails here.
        rows = _rows("marriott_international")
        pending = [r for r in rows if r["new_acquisition_required"]][0]
        stale = {**pending, "saved_status": "VERIFIED_SAVED_SOURCE",
                 "new_acquisition_required": True,
                 "acquisition_kind": "SNAPSHOT_REFRESH"}
        session = recorded_historical_session(root=self.root / "refresh", response=BODY)
        with patch("vnext.historical_sec_session.historical_dependency",
                   return_value=stale):
            result = session.capture(company_id="marriott_international",
                                     url=stale["source_url"])
        self.assertEqual(result["status"], "SUCCEEDED",
                         "a refresh must reach a request, not report reuse")


class DeletingEvidenceMustNotReduceTheCheck(unittest.TestCase):
    """Reproduced: a receipt carrying ``evidence: {}`` was accepted."""

    def setUp(self):
        self.RECEIPT = _receipt_under_check()

    def _write(self, receipt, name):
        relative = "docs/evidence/issue47_history/acquisition-wiring/" + name
        target = ROOT / relative
        self.addCleanup(target.unlink, missing_ok=True)
        target.write_text(json.dumps(receipt), encoding="utf-8")
        return relative

    def test_an_empty_evidence_set_is_refused(self):
        original = strict_json_file(path=ROOT / self.RECEIPT)
        empty = {k: v for k, v in original.items() if k != "receipt_id"}
        empty["evidence"] = {}
        relative = self._write(_seal(empty, "receipt_id"), "_empty.json")
        with self.assertRaises(HistoricalSessionError) as caught:
            verify_offline_wiring(receipt_path=relative)
        self.assertIn("ISSUE_47_OFFLINE_WIRING_EVIDENCE_SET_CHANGED", str(caught.exception))

    def test_dropping_one_required_file_is_refused_by_name(self):
        original = strict_json_file(path=ROOT / self.RECEIPT)
        dropped = {k: v for k, v in original.items() if k != "receipt_id"}
        gone = "scripts/vnext/historical_sec_session.py"
        dropped["evidence"] = {k: v for k, v in original["evidence"].items() if k != gone}
        relative = self._write(_seal(dropped, "receipt_id"), "_dropped.json")
        with self.assertRaises(HistoricalSessionError) as caught:
            verify_offline_wiring(receipt_path=relative)
        self.assertIn(gone, str(caught.exception))

    def test_a_verification_run_that_did_not_pass_is_refused(self):
        # The acceptance claim is a recorded outcome, so a receipt claiming a
        # run that failed must not confer a grant.
        original = strict_json_file(path=ROOT / self.RECEIPT)
        bad = {k: v for k, v in original.items() if k != "receipt_id"}
        bad["verification_run"] = {**original["verification_run"],
                                   "failures": 1, "passed": False, "return_code": 1}
        relative = self._write(_seal(bad, "receipt_id"), "_failedrun.json")
        with self.assertRaises(HistoricalSessionError) as caught:
            verify_offline_wiring(receipt_path=relative)
        self.assertIn("ISSUE_47_OFFLINE_WIRING_VERIFICATION_RUN_DID_NOT_PASS",
                      str(caught.exception))


class TheScopeGateMustPassTheRealDeclaration(unittest.TestCase):
    """Refusing bad input is half a gate; the other half is letting work through.

    This class exists because the previous round's scope check was written and
    tested against a row that happens to carry a ``period:`` consumer, and so
    the case that proved refresh worked passed while the gate refused most of
    the real declaration: 71 of JPMorgan's 75 rows, including all 69 history
    shards and the 12 SNAPSHOT_REFRESH rows the refresh fix was for.
    """

    def _allowance(self, frame, company):
        rows = frame["requirements"]
        scope = {"purposes": ["p"], "company_ids": [company],
                 "dependency_classes": sorted({r["dependency_class"] for r in rows}),
                 "earliest_report_end": "2000-01-01", "latest_report_end": "2099-12-31"}
        return {"scope": {**scope, "grants": [_whole_envelope(scope)]}}

    def _admit(self, frame, company, row, allowance=None):
        return request_is_in_scope(allowance=allowance or self._allowance(frame, company),
                                   company_id=company, dependency=row, purpose="p",
                                   frame_report_dates=frame["target_report_dates"])

    def test_every_row_the_planner_declares_is_admissible(self):
        # Load-bearing and deliberately not a fixture: these are the rows the
        # production planner emits today.
        for company in ("marriott_international", "jpmorgan_chase"):
            with self.subTest(company=company):
                frame = _frame(company)
                self.assertTrue(frame["requirements"])
                for row in frame["requirements"]:
                    self._admit(frame, company, row)

    def test_a_frame_level_dependency_is_admitted_on_the_frame_window(self):
        frame = _frame("jpmorgan_chase")
        shards = [r for r in frame["requirements"]
                  if not any(str(c).startswith("period:") for c in r.get("consumers", []))]
        self.assertTrue(shards, "the declaration carries frame-level dependencies")
        admitted = self._admit(frame, "jpmorgan_chase", shards[0])
        self.assertEqual("FRAME_TARGET_WINDOW", admitted["period_basis"])
        self.assertEqual(frame["target_report_dates"], admitted["periods"])

    def test_a_row_that_names_periods_is_admitted_on_those(self):
        frame = _frame("marriott_international")
        named = [r for r in frame["requirements"]
                 if any(str(c).startswith("period:") for c in r.get("consumers", []))]
        admitted = self._admit(frame, "marriott_international", named[0])
        self.assertEqual("PERIOD_CONSUMERS", admitted["period_basis"])

    def test_the_refresh_rows_the_planner_actually_marks_are_admissible(self):
        # Not a hand-edited row this time: JPMorgan's shards are the real
        # SNAPSHOT_REFRESH population, and they are what the previous gate
        # refused.
        frame = _frame("jpmorgan_chase")
        refresh = [r for r in frame["requirements"]
                   if r.get("acquisition_kind") == "SNAPSHOT_REFRESH"]
        self.assertTrue(refresh, "the planner marks refreshes for this company")
        for row in refresh:
            self._admit(frame, "jpmorgan_chase", row)

    def test_wrong_company_class_and_window_are_still_refused(self):
        frame = _frame("jpmorgan_chase")
        row = frame["requirements"][0]
        base = self._allowance(frame, "jpmorgan_chase")["scope"]
        for label, scope, expected in (
                ("company", {**base, "company_ids": ["pfizer"]},
                 "ISSUE_47_COMPANY_NOT_IN_SCOPE"),
                ("class", {**base, "dependency_classes": ["NOTHING"]},
                 "ISSUE_47_DEPENDENCY_CLASS_NOT_IN_SCOPE"),
                ("window", {**base, "earliest_report_end": "1900-01-01",
                            "latest_report_end": "1900-12-31"},
                 "ISSUE_47_TARGET_PERIOD_NOT_IN_SCOPE"),
                ("purpose", base, "ISSUE_47_PURPOSE_NOT_IN_SCOPE")):
            with self.subTest(label):
                with self.assertRaises(HistoricalAcquisitionError) as caught:
                    request_is_in_scope(allowance={"scope": scope},
                                        company_id=("jpmorgan_chase" if label != "company"
                                                    else "jpmorgan_chase"),
                                        dependency=row,
                                        purpose=("q" if label == "purpose" else "p"),
                                        frame_report_dates=frame["target_report_dates"])
                self.assertIn(expected, str(caught.exception))


class TheApprovalIsReadGrantByGrant(unittest.TestCase):
    """The envelope is a cross product; the grants are what was approved.

    The plan's text left JPMorgan's event windows out while the proposed
    envelope listed JPMorgan and the event class, so the gate would have
    admitted what the approval's own text excluded. A request now has to fall
    inside one grant whole.
    """

    GRANTS = [{"grant": "B_EVENT_WINDOWS", "company_ids": ["marriott_international"],
               "dependency_classes": ["FISCAL_EVENT_FILING"],
               "earliest_report_end": "2021-12-31", "latest_report_end": "2025-12-31"},
              {"grant": "B_KNOWN_FAILED_HEADER", "company_ids": ["jpmorgan_chase"],
               "dependency_classes": ["FISCAL_EVENT_FILING"],
               "earliest_report_end": "2025-12-31", "latest_report_end": "2025-12-31"},
              {"grant": "A_METADATA", "company_ids": ["jpmorgan_chase"],
               "dependency_classes": ["SUBMISSIONS_HISTORY"],
               "earliest_report_end": "2021-12-31", "latest_report_end": "2025-12-31"}]
    DATES = ["2021-12-31", "2022-12-31", "2023-12-31", "2024-12-31", "2025-12-31"]

    def _scope(self, **overrides):
        return {"purposes": ["p"], "company_ids": ["jpmorgan_chase", "marriott_international"],
                "dependency_classes": ["FISCAL_EVENT_FILING", "SUBMISSIONS_HISTORY"],
                "earliest_report_end": "2021-12-31", "latest_report_end": "2025-12-31",
                "grants": self.GRANTS, **overrides}

    def _ask(self, company, dependency_class, period=None):
        row = {"dependency_class": dependency_class,
               "consumers": ["period:" + period + ":E01"] if period else ["historical_catalog"]}
        return request_is_in_scope(allowance={"scope": self._scope()}, company_id=company,
                                   dependency=row, purpose="p", frame_report_dates=self.DATES)

    def test_the_envelope_admits_it_and_no_grant_covers_it(self):
        with self.assertRaises(HistoricalAcquisitionError) as caught:
            self._ask("jpmorgan_chase", "FISCAL_EVENT_FILING", "2024-12-31")
        self.assertIn("ISSUE_47_REQUEST_OUTSIDE_EVERY_GRANT:jpmorgan_chase:FISCAL_EVENT_FILING:"
                      "2024-12-31", str(caught.exception))
        with self.assertRaises(HistoricalAcquisitionError):
            self._ask("marriott_international", "SUBMISSIONS_HISTORY")

    def test_the_grant_that_covers_a_request_is_named(self):
        self.assertEqual(["B_KNOWN_FAILED_HEADER"],
                         self._ask("jpmorgan_chase", "FISCAL_EVENT_FILING", "2025-12-31")["grants"])
        self.assertEqual(["B_EVENT_WINDOWS"],
                         self._ask("marriott_international", "FISCAL_EVENT_FILING",
                                   "2023-12-31")["grants"])
        self.assertEqual(["A_METADATA"], self._ask("jpmorgan_chase", "SUBMISSIONS_HISTORY")["grants"])

    def test_an_envelope_wider_than_its_grants_is_malformed(self):
        from vnext.historical_source_acquisition import _typed_grants
        for label, scope, reason in (
                ("company", self._scope(company_ids=["jpmorgan_chase", "marriott_international",
                                                     "pfizer"]),
                 "ISSUE_47_ALLOWANCE_ENVELOPE_WIDER_THAN_ITS_GRANTS:company_ids"),
                ("window", self._scope(earliest_report_end="2020-12-31"),
                 "ISSUE_47_ALLOWANCE_ENVELOPE_WIDER_THAN_ITS_GRANTS:window"),
                ("grant", self._scope(grants=[*self.GRANTS, {**self.GRANTS[0], "grant": "X",
                                                             "company_ids": ["pfizer"]}]),
                 "ISSUE_47_ALLOWANCE_GRANT_OUTSIDE_THE_ENVELOPE:X:company_ids"),
                ("names", self._scope(grants=[*self.GRANTS, self.GRANTS[0]]),
                 "ISSUE_47_ALLOWANCE_GRANT_NAMES_REPEAT")):
            with self.subTest(label):
                with self.assertRaises(HistoricalAcquisitionError) as caught:
                    _typed_grants(scope)
                self.assertIn(reason, str(caught.exception))
        _typed_grants(self._scope())

    def test_a_budget_root_is_its_own_absolute_path(self):
        from vnext.historical_source_acquisition import _typed_budget_root
        from vnext.normal_source_authority import ROOT as CHECKOUT
        issue_28 = json.loads((CHECKOUT / "config/issue28_continuous_calls_v1.json")
                              .read_text(encoding="utf-8"))["budget_root"]
        # The last four are the spellings an independent review had accepted
        # when the comparison was of strings: a leading "//", a symlink, a
        # case variant (one directory on a case-insensitive filesystem) and an
        # ancestor of the checkout.
        aliases = Path(tempfile.mkdtemp(prefix="issue47-alias-"))
        self.addCleanup(shutil.rmtree, aliases, ignore_errors=True)
        (aliases / "to-28").symlink_to(issue_28)
        for root, reason in ((issue_28, "ISSUE_47_BUDGET_ROOT_OVERLAPS_ISSUE_28_S"),
                             (issue_28 + "/issue47", "ISSUE_47_BUDGET_ROOT_OVERLAPS_ISSUE_28_S"),
                             ("ledger/issue47", "ISSUE_47_BUDGET_ROOT_NOT_AN_ABSOLUTE_PATH"),
                             ("/tmp/a/../b", "ISSUE_47_BUDGET_ROOT_NOT_AN_ABSOLUTE_PATH"),
                             (str(CHECKOUT / "ledger"), "ISSUE_47_BUDGET_ROOT_INSIDE_THE_CHECKOUT"),
                             ("/" + issue_28, "ISSUE_47_BUDGET_ROOT_NOT_AN_ABSOLUTE_PATH"),
                             (str(aliases / "to-28"), "ISSUE_47_BUDGET_ROOT_OVERLAPS_ISSUE_28_S"),
                             (issue_28.upper(), "ISSUE_47_BUDGET_ROOT_OVERLAPS_ISSUE_28_S"),
                             (str(CHECKOUT.parent), "ISSUE_47_BUDGET_ROOT_CONTAINS_THE_CHECKOUT")):
            with self.subTest(root):
                with self.assertRaises(HistoricalAcquisitionError) as caught:
                    _typed_budget_root(root)
                self.assertIn(reason, str(caught.exception))
        # The root the approval body proposes is one the gate accepts.
        plan = strict_json_file(path=ROOT / "docs/evidence/issue47_history/acquisition-plan.json")
        _typed_budget_root(plan["revision_6"]["ledger"]["proposed_budget_root"])


class AGrantMustComeFromAnApprovalNotFromTwoLocalFiles(unittest.TestCase):
    """Two files agreeing with each other is not an approval.

    Reproduced against the previous version: a comment record and a policy
    written side by side in a temporary tree were accepted, with any author and
    any repository's URL, so the executor could write an approval and then have
    the executor's other file confirm it.
    """

    def setUp(self):
        self.made = []
        self.addCleanup(lambda: [shutil.rmtree(p, ignore_errors=True)
                                 for pair in self.made for p in pair])

    def _tree(self, **kwargs):
        pair = _grant_tree(**kwargs)
        self.made.append(pair)
        return pair

    def _reader_for(self, root):
        comment = json.loads((root / "docs/delegation.json").read_text())
        return lambda path: comment

    def test_a_comment_url_from_another_repository_is_refused(self):
        root, _ = self._tree(url="https://github.com/someone/else/issues/47#issuecomment-1",
                             repository="wlvh/SEC_metrics")
        with self.assertRaises(HistoricalAcquisitionError) as caught:
            acquisition_allowance(repo_root=root)
        self.assertIn("ISSUE_47_ALLOWANCE_URL_IS_NOT_THIS_ISSUE_S_COMMENT",
                      str(caught.exception))

    def test_a_comment_by_someone_other_than_the_approver_is_refused(self):
        root, _ = self._tree()
        comment = json.loads((root / "docs/delegation.json").read_text())
        comment["user"] = {"login": "not-the-approver"}
        (root / "docs/delegation.json").write_text(json.dumps(comment), encoding="utf-8")
        with self.assertRaises(HistoricalAcquisitionError) as caught:
            acquisition_allowance(repo_root=root)
        self.assertIn("ISSUE_47_DELEGATION_AUTHOR_IS_NOT_THE_APPROVER",
                      str(caught.exception))

    def test_a_locally_written_pair_does_not_survive_a_real_read(self):
        # Load-bearing: this is the case the previous version passed. The local
        # pair is self-consistent; what refuses it is the comment GitHub
        # actually returns.
        root, _ = self._tree()
        acquisition_allowance(repo_root=root)  # consistent on its own
        elsewhere = {"html_url": json.loads((root / POLICY_PATH).read_text())["delegation_url"],
                     "id": 1, "issue_url": "https://api.github.com/repos/wlvh/SEC_metrics/issues/47",
                     "user": {"login": "wlvh", "id": 30534800, "type": "User"},
                     "author_association": "OWNER", "body": '{"record_type": "SOMETHING_ELSE"}',
                     "created_at": "2026-09-27T00:00:00Z", "updated_at": "2026-09-27T00:00:00Z",
                     "performed_via_github_app": None}
        with self.assertRaises(HistoricalAcquisitionError) as caught:
            acquisition_allowance(repo_root=root, delegation_reader=lambda path: elsewhere)
        self.assertIn("ISSUE_47_SAVED_DELEGATION_DIFFERS_FROM_THE_ONE_ON_GITHUB",
                      str(caught.exception))

    def test_an_app_s_mark_on_either_copy_is_a_refusal(self):
        """The saved record and the comment GitHub returns are each read for it."""
        for where, change in (("saved_record", {"performed_via_github_app": {"slug": "claude"}}),
                              ("saved_record", "DROPPED"),
                              ("fetched", {"performed_via_github_app": {"slug": "claude"}})):
            with self.subTest(where=where, change=change):
                root, _ = self._tree()
                path = root / "docs/delegation.json"
                saved = json.loads(path.read_text())
                fetched = copy.deepcopy(saved)
                target = saved if where == "saved_record" else fetched
                if change == "DROPPED":
                    del target["performed_via_github_app"]
                else:
                    target.update(change)
                path.write_text(json.dumps(saved), encoding="utf-8")
                with self.assertRaises(HistoricalAcquisitionError) as caught:
                    acquisition_allowance(repo_root=root, delegation_reader=lambda _: fetched)
                self.assertIn("ISSUE_47_DELEGATION_WAS_POSTED_THROUGH_AN_APP:" + where,
                              str(caught.exception))

    def test_a_matching_real_read_is_accepted_and_says_so(self):
        root, _ = self._tree()
        allowance = acquisition_allowance(repo_root=root,
                                          delegation_reader=self._reader_for(root))
        self.assertTrue(allowance["approved_delegation"]
                        ["provenance_verified_against_github"])
        offline = acquisition_allowance(repo_root=root)
        self.assertFalse(offline["approved_delegation"]
                         ["provenance_verified_against_github"],
                         "an offline read must not claim it was verified")

    def test_the_fetched_comment_must_also_be_on_this_issue(self):
        root, _ = self._tree()
        comment = json.loads((root / "docs/delegation.json").read_text())
        foreign = {**comment, "issue_url":
                   "https://api.github.com/repos/wlvh/SEC_metrics/issues/28"}
        with self.assertRaises(HistoricalAcquisitionError) as caught:
            acquisition_allowance(repo_root=root, delegation_reader=lambda path: foreign)
        self.assertIn("ISSUE_47_DELEGATION_IS_NOT_ON_THIS_ISSUE:fetched",
                      str(caught.exception))


class ATerminalMustAgreeWithTheReceiptItNames(unittest.TestCase):
    """A terminal names a receipt; until this, nothing read it.

    Reproduced: a sealed terminal naming a missing receipt, and one naming a
    receipt belonging to another request, both left the channel unblocked and
    the next claim succeeded.
    """

    @classmethod
    def setUpClass(cls):
        _Chain.build()

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="issue47-receipt-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def _blocked(self, mutate):
        ledger = _Chain.copy(self.root / ("case-" + str(len(list(self.root.iterdir())))))
        mutate(ledger / "calls/0001")
        session = recorded_historical_session(root=ledger, response=BODY)
        try:
            session.ledger.require_unblocked()
            return None
        except HistoricalSessionError as error:
            return str(error)

    def test_a_missing_receipt_blocks(self):
        message = self._blocked(lambda slot: (slot / "sec-receipt.json").unlink())
        self.assertIsNotNone(message)
        self.assertIn("RECEIPT_ABSENT", message)

    def test_a_terminal_naming_another_receipt_blocks(self):
        def mutate(slot):
            terminal = strict_json_file(path=slot / "terminal.json")
            other = {k: v for k, v in terminal.items() if k != "terminal_id"}
            other["sec_receipt_id"] = "sha256:" + "a" * 64
            (slot / "terminal.json").write_text(
                json.dumps(_seal(other, "terminal_id")), encoding="utf-8")
        message = self._blocked(mutate)
        self.assertIsNotNone(message)
        self.assertIn("TERMINAL_NAMES_ANOTHER_RECEIPT", message)

    def test_a_receipt_that_disagrees_about_the_outcome_blocks(self):
        def mutate(slot):
            receipt = strict_json_file(path=slot / "sec-receipt.json")
            changed = {k: v for k, v in receipt.items() if k != "receipt_id"}
            changed["status"] = "FAILED_TERMINAL"
            sealed = _seal(changed, "receipt_id")
            (slot / "sec-receipt.json").write_text(json.dumps(sealed), encoding="utf-8")
            terminal = strict_json_file(path=slot / "terminal.json")
            bound = {k: v for k, v in terminal.items() if k != "terminal_id"}
            bound["sec_receipt_id"] = sealed["receipt_id"]
            (slot / "terminal.json").write_text(
                json.dumps(_seal(bound, "terminal_id")), encoding="utf-8")
        message = self._blocked(mutate)
        self.assertIsNotNone(message)
        self.assertIn("RECEIPT_AND_TERMINAL_DISAGREE", message)

    def test_a_complete_and_agreeing_slot_does_not_block(self):
        self.assertIsNone(self._blocked(lambda slot: None),
                          "the unmodified chain must still resolve")


class TheSuiteIsReadNotListed(unittest.TestCase):
    """The builder must find the cases, not be told them.

    Reproduced on the previous version: the receipt attested a run of eight
    classes, written by hand and never revisited when sixteen new cases
    arrived, so it excluded every regression that round had just added -
    thirteen of which do not read the receipt at all. A coverage check over
    the list was the first fix; reading the module instead is the second, and
    it also takes the ``unittest`` import out of the business module.
    """

    def test_every_declared_case_lands_in_exactly_one_phase(self):
        declared = WIRING.declared_cases()
        first, excluded = WIRING.split_cases(declared=declared)
        self.assertEqual(sorted(set(first) | set(excluded)), sorted(declared))
        self.assertEqual([], sorted(set(first) & set(excluded)))
        self.assertIn(type(self).__name__, first,
                      "this very class must be one the builder runs")

    def test_the_collector_agrees_with_an_independent_reading_of_the_file(self):
        # The collector introspects the imported module; this parses the file.
        # Two derivations, so a collector quietly narrowed to a subset - the
        # exact shape of the defect this replaced - disagrees with the source
        # instead of producing a smaller receipt that is self-consistent.
        source = ast.parse((ROOT / "tests/vnext/test_historical_sec_session.py")
                           .read_text(encoding="utf-8"))
        from_text = sorted(
            node.name for node in source.body
            if isinstance(node, ast.ClassDef)
            and any(isinstance(base, ast.Attribute) and base.attr == "TestCase"
                    for base in node.bases))
        self.assertEqual(from_text, WIRING.declared_cases())
        self.assertGreater(len(from_text), 1)

    def test_a_new_case_needs_no_edit_in_any_list(self):
        # The point of reading over listing. A class that exists only in this
        # test is picked up, and lands in the phase that runs, without the
        # builder or the business module naming it.
        module = types.ModuleType("tests.vnext._synthetic_suite")

        class AnOrdinaryNewRegression(unittest.TestCase):
            pass

        AnOrdinaryNewRegression.__module__ = module.__name__
        module.AnOrdinaryNewRegression = AnOrdinaryNewRegression
        module.BorrowedFromElsewhere = TheSuiteIsReadNotListed
        with patch.object(WIRING.importlib, "import_module", return_value=module):
            declared = WIRING.declared_cases("tests.vnext._synthetic_suite")
        self.assertEqual(["AnOrdinaryNewRegression"], declared,
                         "a class this module did not declare is not its case")
        first, _ = WIRING.split_cases(declared=declared + list(WIRING.RECEIPT_DEPENDENT))
        self.assertIn("AnOrdinaryNewRegression", first)

    def test_the_business_module_names_no_test_case_and_imports_no_harness(self):
        # Criterion: an ordinary new test must not require editing business
        # code. The strongest form of that is that business code contains no
        # case name at all, which this asserts against every declared name.
        source = (ROOT / "scripts/vnext/historical_sec_session.py").read_text(
            encoding="utf-8")
        for name in WIRING.declared_cases():
            self.assertNotIn(name, source)
        # Imports, not words. The module still names the suite file, because
        # it hashes it as evidence, and still explains in prose what used to
        # live there; neither makes it depend on a test package. An import
        # would, including one hidden inside a function, so the whole tree is
        # walked rather than the top of the file.
        imported = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
        for forbidden in ("unittest", "importlib", "inspect", "subprocess"):
            self.assertNotIn(forbidden, imported)
        self.assertEqual([], [name for name in imported
                              if name.split(".")[0] == "tests"])

    def test_the_excluded_names_are_exactly_those_that_read_the_receipt(self):
        # The one hand-written list, checked against what the classes do
        # rather than against another list. Two directions fail here: a class
        # moved into the exclusion without reading the receipt stops running
        # and nothing else notices, and a class that does read it, left in
        # phase one, makes the artifact unrebuildable after any change to the
        # tree - because phase one runs before the new receipt is installed.
        module = importlib.import_module(WIRING.SUITE_MODULE)
        reads = {name for name in WIRING.declared_cases()
                 if any(token in inspect.getsource(getattr(module, name))
                        for token in RECEIPT_READER_TOKENS)}
        self.assertEqual(set(WIRING.RECEIPT_DEPENDENT), reads,
                         "both spellings count: asking for the receipt under "
                         "check, and naming the installed file directly")

    def test_an_exclusion_naming_no_case_is_refused(self):
        # Renaming an excluded class would otherwise shrink the exclusion set
        # to nothing and look like an improvement, while the class it named
        # stopped running in either phase.
        with self.assertRaises(WIRING.WiringBuildError) as caught:
            WIRING.split_cases(declared=["Something"],
                               receipt_dependent=("RenamedAwhileAgo",))
        self.assertIn("ISSUE_47_WIRING_EXCLUSION_NAMES_NO_CASE", str(caught.exception))


class TheBusinessModuleLoadsWhereNoTestPackageExists(unittest.TestCase):
    """A delivery runtime has scripts/ and no tests/, and must still verify.

    This is what 200 lines of selector lists, an ``importlib`` walk and a
    ``unittest`` subprocess inside the business module cost: the module could
    not honestly be said to load without the test package, and the check that
    gates a live grant lived in the same file as the machinery that runs the
    tests. Asserted by running a child whose path holds scripts/ only.
    """

    SOURCE = """
import json
import sys
# Not a wiped path - the standard library still has to be there, or the child
# fails for a reason that has nothing to do with the question. What is removed
# is every entry that could make the repository root importable; the script
# lives in a scratch directory, so sys.path[0] is that directory.
sys.path[:] = [p for p in sys.path if p not in (%r, "", ".")]
sys.path.insert(0, %r)
try:
    import tests  # noqa: F401
    print(json.dumps({"test_package_importable": True}))
    raise SystemExit(0)
except ImportError:
    pass
from vnext.historical_sec_session import verify_offline_wiring
receipt = verify_offline_wiring(receipt_path=%r)
print(json.dumps({"test_package_importable": False,
                  "receipt_id": receipt["receipt_id"],
                  "modules": sorted(m for m in sys.modules if m.startswith("tests"))}))
"""

    def test_the_gate_still_answers_with_no_tests_directory_on_the_path(self):
        receipt_path = _receipt_under_check()
        scratch = Path(tempfile.mkdtemp(prefix="issue47-delivery-"))
        self.addCleanup(shutil.rmtree, scratch, ignore_errors=True)
        script = scratch / "delivery.py"
        script.write_text(
            self.SOURCE % (str(ROOT), str(ROOT / "scripts"), receipt_path),
            encoding="utf-8")
        done = subprocess.run([sys.executable, str(script)], cwd=str(scratch),
                              capture_output=True, encoding="utf-8", timeout=600)
        self.assertEqual(0, done.returncode, done.stderr[-2000:])
        observed = json.loads(done.stdout)
        self.assertIs(False, observed["test_package_importable"],
                      "the child must not be able to reach the test package")
        self.assertEqual([], observed["modules"])
        self.assertEqual(strict_json_file(path=ROOT / receipt_path)["receipt_id"],
                         observed["receipt_id"])


class AFailedVerificationReleasesNothing(unittest.TestCase):
    """One operation: nothing reaches the installed path until it has passed.

    An earlier version installed first and put the previous bytes back if the
    second phase failed. An external review measured what that left open: in
    the window between the write and the verdict, the gate and ``--check``
    accepted a receipt that was still being checked, and a process killed in
    that window left the unchecked artifact installed, because the code that
    would have restored the old one never ran.

    So the order is the fix, not a bigger restore. The candidate is written
    beside the installed path, the second phase is told to check that name,
    and only a pass reaches the installed path - atomically. A kill needs no
    code to run in order to leave the previous bytes in place.
    """

    PHASE_ONE = {"tests_run": 7, "failures": 0, "errors": 0,
                 "return_code": 0, "passed": True, "tail": ""}
    PHASE_TWO_FAILS = {"tests_run": 0, "failures": 1, "errors": 0,
                       "return_code": 1, "passed": False, "tail": "phase two said no"}

    def _runner(self):
        outcomes = [self.PHASE_ONE, self.PHASE_TWO_FAILS]

        def runner(names, *, receipt_path=None):
            self.calls.append({"names": list(names), "receipt_path": receipt_path})
            return outcomes[len(self.calls) - 1]

        self.calls = []
        return runner

    def _scratch_receipt_path(self, name):
        relative = "docs/evidence/issue47_history/acquisition-wiring/" + name
        candidate = relative.rsplit("/", 1)[0] + "/" + WIRING.CANDIDATE_PREFIX + name
        self.addCleanup((ROOT / relative).unlink, missing_ok=True)
        self.addCleanup((ROOT / candidate).unlink, missing_ok=True)
        return relative, candidate

    def test_an_existing_receipt_is_never_written_over_before_the_check_passes(self):
        relative, candidate = self._scratch_receipt_path("_prior.json")
        before = b'{"this": "is the receipt that was already installed"}\n'
        (ROOT / relative).write_bytes(before)
        with self.assertRaises(WIRING.WiringBuildError) as caught:
            WIRING.build_and_install(receipt_path=relative, runner=self._runner())
        self.assertIn("ISSUE_47_WIRING_SECOND_PHASE_DID_NOT_PASS", str(caught.exception))
        self.assertEqual(before, (ROOT / relative).read_bytes())
        self.assertFalse((ROOT / candidate).exists(), "the candidate is cleaned up")
        self.assertEqual(2, len(self.calls), "both phases must have been reached")

    def test_where_there_was_none_none_is_left(self):
        relative, candidate = self._scratch_receipt_path("_fresh.json")
        self.assertFalse((ROOT / relative).exists())
        with self.assertRaises(WIRING.WiringBuildError):
            WIRING.build_and_install(receipt_path=relative, runner=self._runner())
        self.assertFalse((ROOT / relative).exists(),
                         "a failed run must not release an artifact")
        self.assertFalse((ROOT / candidate).exists())

    def test_a_first_phase_failure_never_reaches_the_file(self):
        relative, candidate = self._scratch_receipt_path("_neverwritten.json")
        self.calls = []

        def runner(names, *, receipt_path=None):
            self.calls.append({"names": list(names), "receipt_path": receipt_path})
            return self.PHASE_TWO_FAILS

        with self.assertRaises(WIRING.WiringBuildError) as caught:
            WIRING.build_and_install(receipt_path=relative, runner=runner)
        self.assertIn("ISSUE_47_WIRING_FIRST_PHASE_DID_NOT_PASS", str(caught.exception))
        self.assertEqual(1, len(self.calls))
        self.assertFalse((ROOT / relative).exists())
        self.assertFalse((ROOT / candidate).exists())

    def test_the_second_phase_checks_the_candidate_while_the_old_one_is_installed(self):
        # Load-bearing, and the case an implementation that installs first and
        # restores afterwards cannot pass: at the moment the second phase
        # runs, the path it was handed must exist, must not be the installed
        # path, and the installed path must still hold the previous bytes.
        relative, candidate = self._scratch_receipt_path("_ordering.json")
        before = b'{"installed": "before this run"}\n'
        (ROOT / relative).write_bytes(before)
        seen = {}

        def runner(names, *, receipt_path=None):
            self.calls.append({"names": list(names), "receipt_path": receipt_path})
            if len(self.calls) == 1:
                return self.PHASE_ONE
            seen["receipt_path"] = receipt_path
            seen["candidate_bytes"] = (ROOT / receipt_path).read_bytes()
            seen["installed_bytes"] = (ROOT / relative).read_bytes()
            return {**self.PHASE_ONE, "tests_run": 3}

        self.calls = []
        summary = WIRING.build_and_install(receipt_path=relative, runner=runner)
        self.assertEqual(candidate, seen["receipt_path"])
        self.assertNotEqual(relative, seen["receipt_path"])
        self.assertEqual(before, seen["installed_bytes"],
                         "the installed receipt must still be the previous one "
                         "while its replacement is being checked")
        # And only then does the checked candidate become the installed file.
        self.assertEqual(seen["candidate_bytes"], (ROOT / relative).read_bytes())
        self.assertEqual(summary["receipt_id"],
                         json.loads(seen["candidate_bytes"])["receipt_id"])
        self.assertFalse((ROOT / candidate).exists())


class TheApprovalAuthorityCannotComeFromTheFileBeingVerified(unittest.TestCase):
    """A policy that names its own approver proves only self-consistency.

    Reproduced against the previous version: changing the comment author alone
    was refused, but changing the author *and* ``approver_login`` together was
    accepted, and so was moving the URL, the issue and ``repository`` to
    another repository together. The one-sided cases were real tests; what was
    missing was the case where both sides move.
    """

    def setUp(self):
        self.made = []
        self.addCleanup(lambda: [shutil.rmtree(p, ignore_errors=True)
                                 for pair in self.made for p in pair])

    def _tree(self, **kwargs):
        pair = _grant_tree(**kwargs)
        self.made.append(pair)
        return pair

    def test_moving_the_author_and_the_approver_field_together_is_refused(self):
        root, _ = self._tree(repository=TRUSTED_REPOSITORY, approver="somebody-else")
        with self.assertRaises(HistoricalAcquisitionError) as caught:
            acquisition_allowance(repo_root=root)
        self.assertIn("ISSUE_47_ALLOWANCE_NAMES_ANOTHER_APPROVER", str(caught.exception))

    def test_moving_the_url_and_the_repository_field_together_is_refused(self):
        root, _ = self._tree(repository="attacker/repo", approver="attacker",
                             url="https://github.com/attacker/repo/issues/47#issuecomment-1")
        with self.assertRaises(HistoricalAcquisitionError) as caught:
            acquisition_allowance(repo_root=root)
        self.assertIn("ISSUE_47_ALLOWANCE_NAMES_ANOTHER_REPOSITORY", str(caught.exception))

    def test_the_anchor_is_this_repository_and_its_owner(self):
        # The constant is the authority, so a case has to say what it is -
        # otherwise a future edit could point it anywhere and every other case
        # here would still pass.
        self.assertEqual("wlvh/SEC_metrics", TRUSTED_REPOSITORY)
        self.assertEqual(TRUSTED_REPOSITORY.split("/")[0], TRUSTED_APPROVER)

    def test_the_anchor_agrees_with_the_repository_identity_already_committed(self):
        # A second witness, so the constant is not the only thing that knows
        # which repository this is. The existing approved call policy names it
        # for its own issue; borrowing the identity is not borrowing the grant.
        from vnext.continuous_call_policy import POLICY_PATH as continuous
        self.assertEqual(TRUSTED_REPOSITORY,
                         strict_json_file(path=ROOT / continuous)["repository"])

    def test_a_grant_on_the_trusted_repository_is_still_accepted(self):
        root, budget = self._tree()
        allowance = acquisition_allowance(repo_root=root)
        self.assertEqual(TRUSTED_REPOSITORY, allowance["repository"])
        self.assertEqual(str(budget), allowance["budget_root"])


class ThisInvocationsCallCountIsNotTheLedgerDelta(unittest.TestCase):
    """Two unlocked reads of a shared total cannot attribute a call.

    The previous version reported one call for this invocation whenever the
    ledger's SEC total had grown between the reads around a capture. Those
    reads are not inside the capture's lock, so a request another process
    finished in between was reported as ours.
    """

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="issue47-attrib-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def test_a_session_that_claimed_nothing_reports_nothing(self):
        session = recorded_historical_session(root=self.root / "a", response=BODY)
        self.assertEqual([0, 0, 0], session.calls_this_session())
        with self.assertRaises(HistoricalAcquisitionError):
            session.capture(company_id="marriott_international",
                            url="https://www.sec.gov/Archives/edgar/data/1048286/none.htm")
        self.assertEqual([0, 0, 0], session.calls_this_session(),
                         "a refusal before the claim consumes nothing")

    def test_another_process_advancing_the_total_is_not_attributed_here(self):
        # The interleaving the old expression got wrong: we read the total,
        # somebody else completes a request, we refuse before claiming, and we
        # read the total again. Simulated by moving the ledger forward between
        # the reads, which is exactly what a second process would do.
        ledger_root = self.root / "shared"
        other = recorded_historical_session(root=ledger_root, response=BODY)
        mine = recorded_historical_session(root=ledger_root, response=BODY)
        before = mine.ledger.snapshot()["counts"][2]
        other.capture(company_id="marriott_international", url=DECLARED)
        after = mine.ledger.snapshot()["counts"][2]
        self.assertEqual(before + 1, after, "the shared total did move")
        self.assertEqual([0, 0, 0], mine.calls_this_session(),
                         "but this session claimed nothing, so it spent nothing")
        self.assertEqual(1, len(other.claimed_slots),
                         "and the session that did claim says so")

    def test_a_session_that_claimed_reports_its_own_slots(self):
        session = recorded_historical_session(root=self.root / "own", response=BODY)
        session.capture(company_id="marriott_international", url=DECLARED)
        self.assertEqual(1, len(session.claimed_slots))
        self.assertEqual([0, 0, 0], session.calls_this_session(),
                         "recorded mode spends no real call, and says so")


if __name__ == "__main__":
    unittest.main()

class TheEventDeclarationIsWhatTheRouteReads(unittest.TestCase):
    """The only check that matters for a declaration: it equals consumption.

    A dependency list can gain a class name and still be wrong in either
    direction - short, and the gate refuses a file the route needs; long, and
    a grant is spent on files nothing reads. So this does not compare against
    a fixture. It runs the frozen event route's own source discovery over the
    saved corpus, records every URL the route asks its reader for, and
    requires the declaration for that period to be that set exactly.

    The newest target period is the one where this can be measured at all:
    the current fiscal-year windows are the only ones whose 8-K bodies and
    headers are saved, which is the same fact that makes every earlier year's
    event coordinates WITHHELD.
    """

    COMPANY = "marriott_international"

    def _newest(self):
        candidates = target_period_candidates(repo_root=ROOT, company_id=self.COMPANY,
                                              count=5)
        policy = _subject_policy(_registry_row(repo_root=ROOT, company_id=self.COMPANY))
        window, ciks, reason = _window(repo_root=ROOT, company_id=self.COMPANY,
                                       candidate=candidates[0], subject_policy=policy)
        self.assertIsNone(reason, "the newest period's window must be derivable")
        return candidates[0], window, ciks

    def _urls_the_route_reads(self, window, cik):
        reader = _Sources(ROOT, self.COMPANY, cik)
        seen = []
        underlying = reader.read

        def record(url, **kwargs):
            item = underlying(url, **kwargs)
            seen.append((kwargs.get("role"), url))
            return item

        reader.read = record
        inventory = reader.read(submissions_url(cik=int(cik)),
                                role="sec_submissions_inventory",
                                media_type="application/json")
        prepared = {"company_id": self.COMPANY, "entity": cik,
                    "table_input": {"target_period": window}}
        _event_sources(repo_root=ROOT, reader=reader, prepared=prepared,
                       inventory=inventory)
        return {url for role, url in seen if role in ("fy_8k_primary", "fy_8k_header")}

    def test_the_declaration_for_a_period_is_exactly_what_the_route_reads(self):
        candidate, window, ciks = self._newest()
        self.assertEqual(1, len(ciks), "this company has one registrant")
        consumed = self._urls_the_route_reads(window, ciks[0])
        self.assertTrue(consumed, "the route reads event sources for this window")
        declared = self._declared_for(candidate["report_date"])
        self.assertEqual(sorted(consumed), sorted(declared))

    def _declared_for(self, label):
        rows = _events(self.COMPANY)["requirements"]
        return {row["source_url"] for row in rows
                if row["dependency_class"] == "FISCAL_EVENT_FILING"
                and any(str(c).startswith("period:" + label + ":")
                        for c in row["consumers"])}

    def test_each_filing_is_declared_as_a_body_and_a_header(self):
        # Two requests per accession is measured, not assumed, and a
        # declaration that named only the body would halve the plan while
        # looking complete.
        candidate, window, ciks = self._newest()
        rows = [row for row in _events(self.COMPANY)["requirements"]
                if row["dependency_class"] == "FISCAL_EVENT_FILING"]
        by_accession = {}
        for row in rows:
            by_accession.setdefault(row["accession"], set()).update(row["source_roles"])
        self.assertTrue(by_accession)
        for accession, roles in by_accession.items():
            self.assertEqual({"fy_8k_primary", "fy_8k_header"}, roles, accession)

    def test_the_consumers_are_the_metrics_that_read_them(self):
        candidate, window, ciks = self._newest()
        label = candidate["report_date"]
        rows = [row for row in _events(self.COMPANY)["requirements"]
                if row["dependency_class"] == "FISCAL_EVENT_FILING"
                and any(str(c).startswith("period:" + label + ":") for c in row["consumers"])]
        self.assertTrue(rows)
        for row in rows:
            self.assertEqual(sorted("period:" + label + ":" + metric
                                    for metric in EVENT_METRICS),
                             sorted(row["consumers"]))


class AnUnderivableWindowDeclaresNothingRatherThanNoFilings(unittest.TestCase):
    """A period nothing can be enumerated for must not read as "no sources".

    The window comes from the target year's own document - the start date is
    in its DEI context, not in the submissions row - so a year whose primary
    is not saved has no derivable window. Declaring zero filings there and
    declaring nothing there look identical in a plan and mean the opposite
    things, so the limitation is named and the period declares nothing.
    """

    COMPANY = "marriott_international"

    def test_a_period_without_its_primary_is_a_named_limitation(self):
        declaration = _events(self.COMPANY)
        blocked = [item for item in declaration["limitations"]
                   if item["kind"] == "EVENT_WINDOW_NOT_DERIVABLE"]
        self.assertTrue(blocked, "earlier years have no saved primary in this repository")
        for item in blocked:
            self.assertIn("SAVED_SOURCE_MISSING:", item["reason"])
            self.assertEqual(sorted(EVENT_METRICS),
                             sorted(item["blocks_declaration_for_metrics"]))
            declared = [row for row in declaration["requirements"]
                        if any(str(c).startswith("period:" + item["report_date"] + ":")
                               for c in row["consumers"])]
            self.assertEqual([], declared,
                             "a period with no derivable window declares nothing")

    def test_the_limitation_names_the_file_that_would_unblock_it(self):
        # The ordering it states is real: the event dependencies of a past
        # year only become listable after that year's annual primary lands.
        declaration = _events(self.COMPANY)
        blocked = [item for item in declaration["limitations"]
                   if item["kind"] == "EVENT_WINDOW_NOT_DERIVABLE"][0]
        url = blocked["reason"].split("SAVED_SOURCE_MISSING:", 1)[1]
        row = historical_dependency(repo_root=ROOT, company_id=self.COMPANY, url=url)
        self.assertEqual("ANNUAL_PERIOD_IDENTITY", row["dependency_class"])
        self.assertTrue(row["new_acquisition_required"])


class TheUnionIsOneDeclarationNotTwo(unittest.TestCase):
    """The gate has to reach the event rows, and reach each of them once.

    Before the union, every fiscal-year 8-K body and header was refused as
    ``HISTORICAL_URL_IS_NOT_A_DECLARED_DEPENDENCY`` - the class did not exist
    in the planner. After it, the other failure becomes possible: a URL both
    sides declare appearing twice, which ``historical_dependency`` refuses as
    a plan that stopped being deduplicated.
    """

    COMPANY = "marriott_international"

    def test_an_event_body_and_header_resolve_through_the_gate(self):
        frame = _frame(self.COMPANY)
        events = [row for row in frame["requirements"]
                  if row["dependency_class"] == "FISCAL_EVENT_FILING"]
        self.assertTrue(events)
        for role in ("fy_8k_primary", "fy_8k_header"):
            row = next(r for r in events if role in r["source_roles"])
            found = historical_dependency(repo_root=ROOT, company_id=self.COMPANY,
                                          url=row["source_url"])
            self.assertEqual(row["source_url"], found["source_url"])

    def test_no_url_is_declared_twice_after_the_union(self):
        for company in (self.COMPANY, "jpmorgan_chase"):
            with self.subTest(company=company):
                urls = [row["source_url"] for row
                        in _frame(company)["requirements"]]
                self.assertEqual(len(urls), len(set(urls)))

    def test_the_recorded_scope_covers_every_class_the_declaration_emits(self):
        # Where the omission shows up first. The recorded default listed four
        # classes; the declaration emitted five even before the event class,
        # so a recorded capture of a history shard was impossible and nothing
        # said so - the gap surfaced only when adding a sixth broke an
        # unrelated case. Derived from the declaration, so the next class
        # fails here.
        import inspect as _inspect
        default = _inspect.signature(recorded_historical_session)\
            .parameters["dependency_classes"].default
        company = _inspect.signature(recorded_historical_session)\
            .parameters["company_ids"].default[0]
        emitted = {row["dependency_class"] for row
                   in _frame(company)["requirements"]}
        self.assertEqual([], sorted(emitted - set(default)))

    def test_the_governance_class_is_declared_and_its_period_decides_it(self):
        """C02's second source reaches the gate, and the right one per period.

        The planner declares five classes and no governance class at all, so
        every proxy the route reads was refused as undeclared. This asserts
        that the frame now emits the class, that each row names the period
        that consumes it, and that two periods do not share a document - a
        declaration built from "the newest proxy" would name one saved filing
        for every year and the earlier periods would read as needing nothing.
        """
        from vnext.historical_governance_sources import DEPENDENCY_CLASS
        frame = _frame(self.COMPANY)
        rows = [row for row in frame["requirements"]
                if row["dependency_class"] == DEPENDENCY_CLASS]
        self.assertTrue(rows)
        self.assertEqual(len(rows), len({row["source_url"] for row in rows}))
        for row in rows:
            self.assertTrue(all(str(consumer).startswith("period:")
                                and str(consumer).endswith(":C02")
                                for consumer in row["consumers"]), row["consumers"])
            self.assertEqual("historical_governance_sources", row["declared_by"])
            self.assertIn("acquisition_kind", row)
        self.assertEqual(len(rows), len({row["consumers"][0] for row in rows}))

    def test_a_period_whose_primary_is_missing_is_a_governance_limitation(self):
        """Not every period can declare one, and the frame says which.

        The document that names the proxy is the year's own annual primary, so
        a year without it declares nothing. Reporting that as an empty set
        would make an unreachable period look satisfied.
        """
        frame = _frame(self.COMPANY)
        limitations = frame["governance_declaration_limitations"]
        self.assertTrue(limitations)
        for item in limitations:
            self.assertEqual("C02", item["metric_id"])
            self.assertIn("report_end", item)
            self.assertTrue(item["reason"])

    def test_a_url_both_sides_declare_keeps_both_sets_of_roles(self):
        # The submissions index is declared by the planner for the frame and by
        # the event declaration for the enumeration; merging must not drop
        # either side's consumers, or a row would be in scope for one purpose
        # and silently out of scope for the other.
        frame = _frame(self.COMPANY)
        shared = [row for row in frame["requirements"] if row.get("also_declared_by")]
        self.assertTrue(shared, "the two declarations overlap on the submissions index")
        for row in shared:
            self.assertIn("historical_event_sources", row["also_declared_by"])
            self.assertTrue(any(str(c).startswith("period:") for c in row["consumers"]))
            self.assertTrue(any(not str(c).startswith("period:") for c in row["consumers"]))


class ARefreshIsFinishedWhenThePlanStopsAskingForIt(unittest.TestCase):
    """The whole chain, not the gate accepting a refresh request.

    The planner marks a dependency ``SNAPSHOT_REFRESH`` when its saved bytes
    are intact and verify but disagree with the index that declares them. Up
    to here the only thing exercised was that such a row reaches a request.
    This runs the rest: capture, save, ledger row, receipt, terminal, frozen
    checkpoint replay, installation, and then a re-plan on the root the
    refresh acted on - and requires the plan to stop asking.

    **What the recorded body is.** The conflict in this repository is that
    every saved shard body sits entirely outside its own declared range: SEC
    re-partitioned the history and the saved bodies predate that. A faithful
    refresh of the *bodies* cannot be derived from saved bytes, because the
    filings the current shards hold were never saved here - the newest saved
    filing is older than the newest declared range even begins. So the
    document refreshed here is the index, and its bytes are **derived**: each
    saved shard's declared range becomes that shard's own minimum and maximum
    filing date, and its declared filing count the number of filings it holds
    (the catalog checks both since the block check counts filings too).
    Entries for shards never saved are left untouched, so the separate "not
    saved" limitation is neither hidden nor changed.

    That makes this a proof of the mechanism, not of SEC's current metadata.
    The real repair for this company is an acquisition, and it is named as
    one. What the mechanism has to show is that one refreshed document clears
    every row the conflict produced - which is the planner's own claim, that
    coherence is a property of the index and the shards together.
    """

    COMPANY = "jpmorgan_chase"
    CIK = 19617
    _chain = None

    @classmethod
    def chain(cls):
        """Run the chain once; every case reads the same recorded outcome."""
        if cls._chain is not None:
            return cls._chain
        payload, measured = cls._measure(ROOT)
        scratch = Path(tempfile.mkdtemp(prefix="issue47-refresh-"))
        atexit.register(shutil.rmtree, scratch, ignore_errors=True)
        session = recorded_historical_session(
            root=scratch / "ledger", company_ids=(cls.COMPANY,),
            response={submissions_url(cik=cls.CIK): cls._derived_index(payload, measured)})
        install_historical_source_inputs(root=session.data_root)
        before = cls._state(session.data_root)
        result = session.capture(company_id=cls.COMPANY, url=submissions_url(cik=cls.CIK))
        checkpoint, paths = checkpoint_installation(source_root=session.data_root)
        cls._chain = {"measured": measured, "before_repository": cls._state(ROOT),
                      "before": before, "result": result, "checkpoint": checkpoint,
                      "installed_paths": len(paths), "calls": session.calls_this_session(),
                      "after": cls._state(session.data_root),
                      "after_measured": cls._measure(session.data_root)[1]}
        return cls._chain

    @classmethod
    def _state(cls, root):
        frame = declared_frame(repo_root=root, company_id=cls.COMPANY)
        rows = frame["requirements"]
        return {"rows": len(rows),
                # By URL, because counting answers neither "did anything go
                # missing" nor "what arrived" - a chain that dropped one row
                # and added another keeps the count.
                "urls": sorted(r["source_url"] for r in rows),
                "by_url": {r["source_url"]: r for r in rows},
                "governance_blocked": sorted(
                    item["report_end"]
                    for item in frame["governance_declaration_limitations"]),
                "refresh": sorted(r["document_name"] for r in rows
                                  if r.get("acquisition_kind") == "SNAPSHOT_REFRESH"),
                "conflicting": sorted(
                    r["document_name"] for r in rows
                    if r.get("snapshot_conflict", {}).get("reason")
                    == "SAVED_HISTORY_INDEX_AND_BODY_ARE_NOT_A_COHERENT_SNAPSHOT")}

    @classmethod
    def _measure(cls, root):
        """What the two sides say, read from each of them."""
        index = saved_source(repo_root=root, url=submissions_url(cik=cls.CIK), accession="")
        payload = json.loads(index["raw"].decode("utf-8"))
        measured = []
        for shard in _history_index(payload, str(cls.CIK)):
            item = saved_source(repo_root=root,
                                url=submissions_file_url(file_name=shard["name"]),
                                accession="")
            if item is None:
                continue
            body = json.loads(item["raw"].decode("utf-8"))
            relevant = _filings(body, inventory_name=shard["name"])
            measured.append({
                "name": shard["name"], "declared_from": shard["filingFrom"],
                "declared_to": shard["filingTo"], "body_from": min(body["filingDate"]),
                "body_to": max(body["filingDate"]), "body_count": len(body["filingDate"]),
                "relevant_rows": len(relevant),
                "relevant_inside": sum(1 for row in relevant
                                       if shard["filingFrom"] <= row["filingDate"]
                                       <= shard["filingTo"])})
        return payload, measured

    @classmethod
    def _derived_index(cls, payload, measured, *, derive=True):
        spans = {row["name"]: row for row in measured}
        body = json.loads(json.dumps(payload))
        if derive:
            for entry in body["filings"]["files"]:
                row = spans.get(entry["name"])
                if row is not None:
                    entry["filingFrom"] = row["body_from"]
                    entry["filingTo"] = row["body_to"]
                    entry["filingCount"] = row["body_count"]
        return json.dumps(body, ensure_ascii=False).encode("utf-8")

    def test_the_conflict_is_there_before_and_on_the_root_the_refresh_acts_on(self):
        chain = self.chain()
        self.assertTrue(chain["before_repository"]["conflicting"])
        self.assertEqual(chain["before_repository"]["conflicting"],
                         chain["before"]["conflicting"],
                         "the installed root inherits the repository's conflict")
        # The index is asked for too: its declared ranges are the other half
        # of the disagreement, so refreshing a shard alone proves nothing.
        self.assertIn("CIK%010d.json" % self.CIK, chain["before"]["refresh"])

    def test_the_saved_bodies_are_wholly_outside_their_declared_ranges(self):
        # Not "a few filings drifted". Every saved shard's relevant filings
        # are outside its own declared range, which is what a re-partition
        # looks like, and is why the real repair is an acquisition.
        measured = self.chain()["measured"]
        self.assertTrue(measured)
        carrying = [row for row in measured if row["relevant_rows"]]
        self.assertTrue(carrying)
        self.assertEqual([], [row["name"] for row in carrying if row["relevant_inside"]])
        self.assertLess(max(row["body_to"] for row in measured),
                        max(row["declared_to"] for row in measured),
                        "the newest saved filing predates the newest declared range")

    def test_the_capture_reaches_a_request_and_a_checkpoint(self):
        chain = self.chain()
        self.assertEqual("SUCCEEDED", chain["result"]["status"])
        self.assertEqual([0, 0, 0], chain["calls"], "recorded, so no SEC call")
        self.assertEqual(chain["result"]["checkpoint_id"],
                         chain["checkpoint"]["checkpoint_id"])
        self.assertTrue(chain["installed_paths"],
                        "the frozen validator accepted it and named its inputs")

    def test_after_the_refresh_the_plan_asks_for_nothing(self):
        # The acceptance. Not "the gate admitted the request" - the plan, re-
        # derived from the root the refresh installed into, no longer marks a
        # single row for refresh and no longer reports a single conflict.
        chain = self.chain()
        self.assertEqual([], chain["after"]["refresh"])
        self.assertEqual([], chain["after"]["conflicting"])

    def test_the_refresh_drops_nothing_it_was_declaring(self):
        """What the row count was really guarding, said directly.

        This case used to read ``before["rows"] == after["rows"]``. Equality
        forbids two different things at once and only one of them is a fault:
        a chain that "cleared" the conflict by making the conflicting rows
        disappear, and a declaration that names more once a period stops being
        blocked. Equality also lets a swap through - drop one row, add
        another, the count holds - so it was both too strict and too loose.
        Set difference by URL answers the question it was asked.
        """
        chain = self.chain()
        dropped = sorted(set(chain["before"]["urls"]) - set(chain["after"]["urls"]))
        self.assertEqual([], dropped,
                         "a refresh repairs metadata; it must not stop declaring a "
                         "dependency, least of all the ones that carried the conflict")
        still_there = set(chain["after"]["by_url"])
        for name in chain["before"]["conflicting"]:
            with self.subTest(name):
                self.assertIn(name, [chain["after"]["by_url"][url]["document_name"]
                                     for url in still_there],
                              "the conflicting shards are still declared, they are "
                              "simply no longer in conflict")

    def test_anything_the_refresh_adds_is_a_period_it_unblocked(self):
        """Growth is allowed only where the refresh explains it.

        The governance declaration asks the route itself which document each
        pinned period's C02 would read, so a period whose selection cannot
        resolve declares nothing and records why. Repairing the metadata makes
        one of those periods resolvable, and the dependency it names becomes
        derivable for the first time - a lower bound that grows as blockers
        clear, which is the same shape the event declaration already carries.

        Measured here: exactly one row arrives, JPMorgan's FY2025 proxy, and
        the governance limitation for that period is the one that goes away.
        The FY2024 limitation stays, because its shards were never saved and
        a derived index does not invent them - so the refresh clears the
        conflict without hiding the separate missing-material problem.

        Deliberately not asserted: that an added row needs no fetch. This one
        is already saved, but a period that unblocks may name a proxy that is
        not, and that would be correct.
        """
        chain = self.chain()
        added = sorted(set(chain["after"]["urls"]) - set(chain["before"]["urls"]))
        unblocked = (set(chain["before"]["governance_blocked"])
                     - set(chain["after"]["governance_blocked"]))
        self.assertTrue(added, "this chain is only a proof if something did unblock")
        self.assertTrue(unblocked)
        for url in added:
            row = chain["after"]["by_url"][url]
            with self.subTest(row["document_name"]):
                periods = {str(c).split(":")[1] for c in row["consumers"]
                           if str(c).startswith("period:")}
                self.assertTrue(periods & unblocked,
                                "an added row must serve a period the refresh "
                                "unblocked, not appear out of nowhere")
        self.assertTrue(set(chain["after"]["governance_blocked"]),
                        "the period whose shards were never saved is still blocked, "
                        "so the refresh did not paper over the missing material")

    def test_the_refreshed_index_describes_the_bodies_rather_than_replacing_them(self):
        chain = self.chain()
        after = {row["name"]: row for row in chain["after_measured"]}
        self.assertEqual(sorted(after), sorted(row["name"] for row in chain["measured"]))
        for row in chain["measured"]:
            with self.subTest(row["name"]):
                # Same bytes on the shard side: only the index moved.
                self.assertEqual(row["body_from"], after[row["name"]]["body_from"])
                self.assertEqual(row["body_to"], after[row["name"]]["body_to"])
                self.assertEqual(row["body_from"], after[row["name"]]["declared_from"])
                self.assertEqual(row["body_to"], after[row["name"]]["declared_to"])

    def test_capturing_the_same_bytes_again_does_not_clear_the_conflict(self):
        # Load-bearing. Without it, a chain that cleared the conflict because
        # something was re-saved, re-registered or re-installed would pass
        # every case above. Same chain, same gate, same checkpoint - only the
        # body is the unchanged index, and the conflict has to survive it.
        payload, measured = self._measure(ROOT)
        scratch = Path(tempfile.mkdtemp(prefix="issue47-norefresh-"))
        self.addCleanup(shutil.rmtree, scratch, ignore_errors=True)
        session = recorded_historical_session(
            root=scratch / "ledger", company_ids=(self.COMPANY,),
            response={submissions_url(cik=self.CIK):
                      self._derived_index(payload, measured, derive=False)})
        result = session.capture(company_id=self.COMPANY,
                                 url=submissions_url(cik=self.CIK))
        self.assertEqual("SUCCEEDED", result["status"])
        after = self._state(session.data_root)
        self.assertTrue(after["conflicting"],
                        "re-saving the same index must leave the conflict standing")
        self.assertEqual(self.chain()["before_repository"]["conflicting"],
                         after["conflicting"])


class ARecordedBodyMustBeTheOneAskedFor(unittest.TestCase):
    """A chain over several documents needs several bodies, and the right one.

    The recorded session answered every URL with one body, which is all a
    single-document chain needs. A refresh is not one document - the index and
    the shards have to disagree for the check under test to mean anything - so
    a session may now carry a map. What the map must never do is answer a URL
    it was not given a body for: a fallback would hand one document's bytes to
    another's request and look like a pass.
    """

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="issue47-body-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def test_a_url_the_map_does_not_carry_is_refused_by_name(self):
        session = recorded_historical_session(root=self.root / "ledger",
                                              response={"https://data.sec.gov/other": BODY})
        with self.assertRaises(HistoricalSessionError) as caught:
            session.capture(company_id="marriott_international", url=DECLARED)
        self.assertIn("ISSUE_47_RECORDED_RESPONSE_NOT_PROVIDED", str(caught.exception))
        self.assertIn(DECLARED, str(caught.exception))

    def test_the_map_must_carry_bytes_under_string_keys(self):
        for label, response in (("empty", {}), ("not bytes", {DECLARED: "text"}),
                                ("not a url key", {1: BODY})):
            with self.subTest(label):
                with self.assertRaises(HistoricalSessionError) as caught:
                    recorded_historical_session(root=self.root / label, response=response)
                self.assertIn("ISSUE_47_RECORDED_RESPONSE", str(caught.exception))

    def test_a_single_body_still_answers_every_url(self):
        # The old form is unchanged, because every other case in this file
        # uses it and none of them should have had to move.
        session = recorded_historical_session(root=self.root / "bytes", response=BODY)
        result = session.capture(company_id="marriott_international", url=DECLARED)
        self.assertEqual("SUCCEEDED", result["status"])


# ---------------------------------------------------------------------------
# Batch acquisition, export and approval registration.
# ---------------------------------------------------------------------------

from vnext import historical_sec_session as SESSION_MODULE  # noqa: E402
from vnext import historical_source_export as EXPORT_MODULE  # noqa: E402
from vnext.historical_source_acquisition import (APPROVED_BODY_PATH,  # noqa: E402
                                                 APPROVED_BODY_SHA256,
                                                 register_approval)

_SCRIPTED_COMPANY = "marriott_international"


def _scripted_row(url, dependency_class, due=True, consumers=("period:2024-12-31:B02",)):
    return {"source_url": url, "dependency_class": dependency_class,
            "new_acquisition_required": due, "consumers": list(consumers),
            "media_type": "text/html", "accession": "", "acquisition_kind": "FIRST_ACQUISITION"}


_BASE = "https://www.sec.gov/Archives/edgar/data/1048286/"
_INDEX = "https://data.sec.gov/submissions/CIK0001048286.json"
_SHARDS = ["https://data.sec.gov/submissions/CIK0001048286-submissions-001.json",
           "https://data.sec.gov/submissions/CIK0001048286-submissions-002.json"]
_OTHER = [_BASE + "000000000000000001/a.htm", _BASE + "000000000000000002/b.htm",
          _BASE + "000000000000000003/c.htm"]


class _ScriptedPasses:
    """A real ledger under scripted frames and a scripted transport.

    Only the pass logic is under test here - which rows a pass takes, in what
    order, and when it stops - so the frame and the fetch are scripted and the
    ledger's claim, terminal and block rules are the real ones. The real chain
    has its own cases below.
    """

    def __init__(self, test, frames, statuses=None, **session_kwargs):
        root = Path(tempfile.mkdtemp(prefix="issue47-passes-"))
        test.addCleanup(shutil.rmtree, root, ignore_errors=True)
        self.root = root / "ledger"
        self.session_kwargs = session_kwargs
        self.frames = [rows if isinstance(rows, Exception) else
                       dict(requirements=rows, target_report_dates=["2024-12-31"],
                            company_id=_SCRIPTED_COMPANY) for rows in frames]
        self.statuses = statuses or {}
        self.fetched = []
        self.reclaims = []
        self.frame_calls = 0
        scripted = self
        test_case = test

        def frame(**kwargs):
            scripted.frame_calls += 1
            if isinstance(scripted.frames[0], Exception):
                raise scripted.frames.pop(0)
            chosen = scripted.frames.pop(0) if len(scripted.frames) > 1 else scripted.frames[0]
            return copy.deepcopy(chosen)

        def capture_one(session, *, company_id, url, dependency, admitted, reclaim=None):
            code = scripted.statuses.get(url, "200")
            request = {"url": url}
            if reclaim is not None:
                request["reclaimed_under_extension"] = reclaim
            scripted.reclaims.append(reclaim)
            plan = {"request": request, "scope_admission": admitted}
            path, intent = session.ledger.claim(channel="SEC",
                                                request_digest=content_hash(value=request),
                                                plan_id=content_hash(value=plan),
                                                purpose=admitted["purpose"])
            (path / "sec-plan.json").write_text(json.dumps(plan), encoding="utf-8")
            scripted.fetched.append(url)
            status = ("SUCCEEDED" if code == "200" else
                      "UNKNOWN_REMOTE_OUTCOME" if code == "0" else "FAILED_TERMINAL")
            receipt = _seal({"intent_id": intent["intent_id"], "status": status,
                             "stop_reason": "UNKNOWN_REMOTE_OUTCOME" if code == "0" else "",
                             "execution_mode": session.ledger.mode,
                             "ledger_row": {"status_code": code}}, "receipt_id")
            (path / "sec-receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
            terminal = session.ledger.finish(path=path, intent=intent, receipt=receipt)
            return receipt, terminal

        for target, replacement in (
                ("declared_frame", frame),
                ("install_historical_source_inputs", lambda **kwargs: None)):
            patcher = patch.object(SESSION_MODULE, target, replacement)
            patcher.start()
            test_case.addCleanup(patcher.stop)
        # The scripted transport writes no request log, so there is no row to
        # compare a receipt with; the real chain's cases compare them.
        patcher = patch.object(SESSION_MODULE.HistoricalCallLedger, "_log_rows",
                               lambda ledger: None)
        patcher.start()
        test_case.addCleanup(patcher.stop)
        for name, replacement in (
                ("_capture_one", capture_one),
                ("_register_if_unregistered", lambda session: None),
                ("register_checkpoint", lambda session: {"checkpoint_id": "sha256:scripted",
                                                         "ledger_sha256": "scripted"})):
            patcher = patch.object(SESSION_MODULE.HistoricalSecSession, name, replacement)
            patcher.start()
            test_case.addCleanup(patcher.stop)

    def session(self):
        return recorded_historical_session(root=self.root, response=BODY,
                                           **self.session_kwargs)


class APassTakesOneTierAndNeverClaimsAUrlTwice(unittest.TestCase):
    """The batch path keeps every per-request rule and adds only the ordering.

    ``capture`` recomputed the frame and replayed the checkpoint for every
    request - 22 to 30 seconds each, growing - so a batch path was needed. The
    risk in a batch path is that it quietly drops a rule the single capture
    enforced; these cases hold it to the ones that matter: the submissions
    index and shards first, because they change what the frame declares; no
    URL claimed twice, because zero retries is the rule; and every stop by
    name.
    """

    def test_the_index_then_the_shards_then_the_rest_each_in_its_own_pass(self):
        index = _scripted_row(_INDEX, "SUBMISSIONS_INDEX", consumers=["historical_catalog"])
        shards = [_scripted_row(url, "SUBMISSIONS_HISTORY", consumers=["historical_catalog"])
                  for url in _SHARDS]
        others = [_scripted_row(url, "ANNUAL_PERIOD_IDENTITY") for url in _OTHER[:2]]
        done = lambda row: {**row, "new_acquisition_required": False}  # noqa: E731
        scripted = _ScriptedPasses(self, frames=[
            [index, *shards, *others],
            [done(index), *shards, *others],
            [done(index), *map(done, shards), *others],
            [done(index), *map(done, shards), *map(done, others)]])
        summary = scripted.session().acquire(company_ids=[_SCRIPTED_COMPANY])
        self.assertEqual([_INDEX, *_SHARDS, *_OTHER[:2]], scripted.fetched,
                         "the index alone, then both shards together, then the rest")
        self.assertEqual(4, summary["companies"][_SCRIPTED_COMPANY]["passes"])
        self.assertIsNone(summary["stop"])

    def test_a_failed_url_is_reported_and_not_claimed_again(self):
        a, b = (_scripted_row(url, "ANNUAL_PERIOD_IDENTITY") for url in _OTHER[:2])
        scripted = _ScriptedPasses(self, frames=[[a, b]], statuses={_OTHER[0]: "404"})
        summary = scripted.session().acquire(company_ids=[_SCRIPTED_COMPANY])
        self.assertEqual([_OTHER[0], _OTHER[1]], scripted.fetched)
        company = summary["companies"][_SCRIPTED_COMPANY]
        self.assertEqual(2, company["passes"], "the second pass found nothing it may claim")
        self.assertEqual([_OTHER[0], _OTHER[1]],
                         sorted(item["source_url"] for item in company["already_claimed"]))
        # A later invocation reads the claims from the ledger, not from memory.
        later = scripted.session()
        later.acquire(company_ids=[_SCRIPTED_COMPANY])
        self.assertEqual(2, len(scripted.fetched), "a new session did not retry either")
        with self.assertRaises(HistoricalSessionError) as caught:
            later.capture(company_id=_SCRIPTED_COMPANY, url=_OTHER[0])
        self.assertIn("ISSUE_47_URL_ALREADY_CLAIMED_IN_THIS_LEDGER", str(caught.exception))

    def test_an_sec_access_refusal_stops_everything_by_name(self):
        rows = [_scripted_row(url, "ANNUAL_PERIOD_IDENTITY") for url in _OTHER]
        scripted = _ScriptedPasses(self, frames=[rows], statuses={_OTHER[1]: "429"})
        summary = scripted.session().acquire(company_ids=[_SCRIPTED_COMPANY,
                                                          "ford_motor_company"])
        self.assertEqual(_OTHER[:2], scripted.fetched)
        self.assertEqual({"company_id": _SCRIPTED_COMPANY, "reason": "SEC_ACCESS_REFUSED:429"},
                         summary["stop"])
        self.assertNotIn("ford_motor_company", summary["companies"],
                         "a fair-access refusal is not about one company")

    def test_the_cap_stops_before_the_next_socket(self):
        rows = [_scripted_row(url, "ANNUAL_PERIOD_IDENTITY") for url in _OTHER]
        scripted = _ScriptedPasses(self, frames=[rows], limits=(0, 0, 2))
        session = scripted.session()
        summary = session.acquire(company_ids=[_SCRIPTED_COMPANY])
        self.assertEqual(_OTHER[:2], scripted.fetched, "the third was never sent")
        self.assertTrue(summary["stop"]["reason"].startswith("ISSUE_47_CUMULATIVE_LIMIT_REACHED"))
        self.assertEqual([0, 0, 2], session.ledger.snapshot()["counts"])

    def test_an_unknown_outcome_stops_and_blocks_the_next_claim(self):
        rows = [_scripted_row(url, "ANNUAL_PERIOD_IDENTITY") for url in _OTHER]
        scripted = _ScriptedPasses(self, frames=[rows], statuses={_OTHER[1]: "0"})
        summary = scripted.session().acquire(company_ids=[_SCRIPTED_COMPANY])
        self.assertEqual(_OTHER[:2], scripted.fetched)
        self.assertEqual("UNKNOWN_REMOTE_OUTCOME", summary["stop"]["reason"])
        self.assertTrue(summary["cumulative"]["blocked"])
        with self.assertRaises(HistoricalSessionError) as caught:
            scripted.session().capture_pending(company_id=_SCRIPTED_COMPANY)
        self.assertIn("ISSUE_47_UNRESOLVED_TERMINAL_BLOCKS_THE_CHANNEL", str(caught.exception))

    def test_a_row_outside_every_grant_is_listed_and_never_claimed(self):
        inside = _scripted_row(_OTHER[0], "ACCESSION_INSTANCE_DISCOVERY")
        outside = _scripted_row(_OTHER[1], "FISCAL_EVENT_FILING")
        scripted = _ScriptedPasses(self, frames=[[inside, outside]],
                                   dependency_classes=("ACCESSION_INSTANCE_DISCOVERY",))
        summary = scripted.session().acquire(company_ids=[_SCRIPTED_COMPANY])
        self.assertEqual([_OTHER[0]], scripted.fetched)
        listed = summary["companies"][_SCRIPTED_COMPANY]["outside_grants"]
        self.assertEqual([_OTHER[1]], [item["source_url"] for item in listed])
        self.assertIn("ISSUE_47_DEPENDENCY_CLASS_NOT_IN_SCOPE", listed[0]["reason"])

    def test_max_captures_ends_the_invocation_by_name(self):
        rows = [_scripted_row(url, "ANNUAL_PERIOD_IDENTITY") for url in _OTHER]
        scripted = _ScriptedPasses(self, frames=[rows])
        summary = scripted.session().acquire(company_ids=[_SCRIPTED_COMPANY], max_captures=1)
        self.assertEqual(_OTHER[:1], scripted.fetched)
        self.assertEqual("MAX_CAPTURES_FOR_THIS_INVOCATION", summary["stop"]["reason"])

    def test_a_planner_failure_is_reported_and_the_next_company_goes_ahead(self):
        rows = [_scripted_row(url, "ANNUAL_PERIOD_IDENTITY") for url in _OTHER[:1]]
        scripted = _ScriptedPasses(self, frames=[RuntimeError("frame failed"), rows])
        summary = scripted.session().acquire(company_ids=["ford_motor_company",
                                                          _SCRIPTED_COMPANY])
        self.assertEqual("RuntimeError",
                         summary["companies"]["ford_motor_company"]["error"]["error_type"])
        self.assertIsNone(summary["stop"], "a planner failure before any claim is not a stop")
        self.assertEqual(_OTHER[:1], scripted.fetched)

    def test_a_url_declared_twice_in_one_frame_is_refused(self):
        row = _scripted_row(_OTHER[0], "ANNUAL_PERIOD_IDENTITY")
        scripted = _ScriptedPasses(self, frames=[[row, dict(row)]])
        with self.assertRaises(HistoricalAcquisitionError) as caught:
            scripted.session().capture_pending(company_id=_SCRIPTED_COMPANY)
        self.assertIn("HISTORICAL_URL_IS_DECLARED_MORE_THAN_ONCE", str(caught.exception))
        self.assertEqual([], scripted.fetched)


class TheRunSummaryIsWrittenWholeOrNotAtAll(unittest.TestCase):
    """The CLI's own acquire, over the scripted passes.

    Nothing exercised the CLI's ``_acquire`` before the first live run, which
    then crashed writing its summary: the ledger snapshot's request digests
    are a set, and the file had been opened before json failed, so a
    truncated summary was left beside the ledger (the capture itself and its
    checkpoint were already registered).
    """

    def _cli(self):
        spec = importlib.util.spec_from_file_location(
            "issue47_historical_sec_cli", ROOT / "tools/vnext_historical_sec.py")
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        return cli

    @staticmethod
    def _args():
        return types.SimpleNamespace(company=None, years=5, max_captures=None)

    def test_the_summary_is_whole_json_and_lists_the_claimed_digests(self):
        rows = [_scripted_row(url, "ANNUAL_PERIOD_IDENTITY") for url in _OTHER[:2]]
        session = _ScriptedPasses(self, frames=[rows]).session()
        cli = self._cli()
        with patch.object(cli, "live_historical_session", lambda **kwargs: session), \
                patch.object(cli, "_companies", lambda args: [_SCRIPTED_COMPANY]):
            _, result = cli._acquire(self._args())
        written = strict_json_file(path=Path(result["summary_path"]))
        digests = session.ledger.snapshot()["request_digests"]
        self.assertEqual(2, len(digests))
        self.assertEqual(sorted(digests), written["cumulative"]["request_digests"])
        self.assertEqual([0, 0, 2], result["cumulative_calls"])

    def test_a_value_json_cannot_write_leaves_no_file(self):
        session = _ScriptedPasses(self, frames=[[]]).session()
        cli = self._cli()
        unwritable = {"cumulative": {"counts": [0, 0, 0]}, "value": object()}
        with patch.object(cli, "live_historical_session", lambda **kwargs: session), \
                patch.object(cli, "_companies", lambda args: [_SCRIPTED_COMPANY]), \
                patch.object(type(session), "acquire", lambda self, **kwargs: unwritable):
            with self.assertRaises(TypeError) as caught:
                cli._acquire(self._args())
        self.assertIn("ISSUE_47_SUMMARY_VALUE_IS_NOT_JSON:object", str(caught.exception))
        runs = session.ledger.root / "runs"
        self.assertEqual([], sorted(runs.iterdir()) if runs.exists() else [],
                         "nothing is written when the summary cannot be serialized")


class TheRealChainReachesAFixpointWithoutRetrying(unittest.TestCase):
    """The batch path over the real planner, gate, ledger and frozen replay.

    Every response is a 404, which exercises the one thing a recorded body
    cannot: what the next pass's frame does with a period whose annual primary
    was just fetched and failed. Measured before this case existed: the event
    declaration let the reader's ``LATEST_SOURCE_REQUEST_FAILED`` escape and
    the whole frame raised, so the second pass of a real acquisition would have
    stopped at the first failed primary.
    """

    def test_every_due_url_is_claimed_once_and_the_second_pass_takes_nothing(self):
        root = Path(tempfile.mkdtemp(prefix="issue47-fixpoint-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        due = sorted(row["source_url"] for row in _rows(_SCRIPTED_COMPANY)
                     if row["new_acquisition_required"])
        session = recorded_historical_session(root=root / "ledger", response=b"missing",
                                              status=404)
        summary = session.acquire(company_ids=[_SCRIPTED_COMPANY])
        company = summary["companies"][_SCRIPTED_COMPANY]
        self.assertIsNone(summary["stop"])
        self.assertIsNone(company["error"])
        self.assertEqual(2, company["passes"])
        claimed = sorted(item["source_url"] for item in company["captured"])
        self.assertEqual(due, claimed, "each due URL exactly once")
        self.assertEqual(due, sorted(item["source_url"] for item in company["already_claimed"]))
        self.assertEqual([0, 0, len(due)], summary["cumulative"]["counts"])
        self.assertEqual(["checkpoint_id"], [item["when"] for item in summary["checkpoints"]],
                         "registered once, after the pass that captured")
        ledger = hashlib.sha256((session.data_root / "evidence/requests_log.csv")
                                .read_bytes()).hexdigest()
        checkpoint = strict_json_file(path=ROOT / ".git/ordinary-source-authority/acquired"
                                      / (ledger + ".json"))
        self.assertEqual(summary["checkpoints"][0]["checkpoint_id"], checkpoint["checkpoint_id"])
        validate_acquisition_checkpoint(session.data_root, checkpoint,
                                        strict_json_file(path=ROOT / MANIFEST_PATH))


class _FakeResponse:
    def __init__(self, body, status):
        self.body, self.status = body, status
        self.headers = {"Content-Type": "text/html"}

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class ALiveCaptureIsOneRequestAndItsCheckpointReplays(unittest.TestCase):
    """The LIVE branch, with the network replaced and nothing else.

    Every other case runs the recorded branch, which persists a body directly.
    The owner's run takes the other one - ``SecHttpClient.fetch`` - and a LIVE
    checkpoint is a different record (``real_sec_credit`` true). If either did
    not satisfy the frozen replay, the first sign would be a refusal after real
    requests had been spent. So the LIVE branch runs here over a replaced
    ``urlopen``, with the checkpoint journal redirected so that no LIVE record
    about a stub reaches the real one.
    """

    def test_one_request_per_url_no_retry_and_the_frozen_replay_accepts_it(self):
        import urllib.error
        from email.message import Message
        import sec_http
        root = Path(tempfile.mkdtemp(prefix="issue47-live-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        rows = [row for row in _rows(_SCRIPTED_COMPANY)
                if row["new_acquisition_required"]
                and row["dependency_class"] == "ACCESSION_INSTANCE_DISCOVERY"][:2]
        self.assertEqual(2, len(rows))
        opened = []

        def fake_urlopen(request, timeout):
            opened.append(request.full_url)
            if request.full_url == rows[1]["source_url"]:
                raise urllib.error.HTTPError(request.full_url, 503, "busy", Message(),
                                             __import__("io").BytesIO(b"busy"))
            return _FakeResponse(BODY, 200)

        scope = {"purposes": ["ISSUE47_HISTORICAL_SOURCE_DEPENDENCY"],
                 "company_ids": [_SCRIPTED_COMPANY],
                 "dependency_classes": ["ACCESSION_INSTANCE_DISCOVERY"],
                 "earliest_report_end": "2021-12-31", "latest_report_end": "2026-01-31"}
        scope["grants"] = [_whole_envelope(scope)]
        allowance = {"requirement_id": "issue_47_v1", "budget_root": str(root / "ledger"),
                     "maximum_additional_provider_paid_sec_calls": [0, 0, 5], "scope": scope}
        ledger = SESSION_MODULE._allowance_ledger(allowance=allowance, root=root / "ledger",
                                                  live=True)
        session = SESSION_MODULE.HistoricalSecSession(factory=SESSION_MODULE._FACTORY,
                                                      allowance=allowance, ledger=ledger)
        journal = root / "journal"
        paced = []
        real_pace = sec_http.SecHttpClient._pace_request

        def pace(client):
            paced.append(id(client))
            return real_pace(client)

        frame = {"requirements": copy.deepcopy(rows), "company_id": _SCRIPTED_COMPANY,
                 "target_report_dates": ["2021-12-31", "2022-12-31", "2023-12-31",
                                         "2024-12-31", "2025-12-31"]}
        with patch.object(sec_http, "urlopen", fake_urlopen), \
                patch.object(sec_http.SecHttpClient, "_pace_request", pace), \
                patch("vnext.continuous_sec_acquisition._journal", lambda: journal), \
                patch.object(SESSION_MODULE, "declared_frame",
                             lambda **kwargs: copy.deepcopy(frame)), \
                patch.object(socket.socket, "connect",
                             side_effect=AssertionError("a socket was opened")):
            result = session.capture_pending(company_id=_SCRIPTED_COMPANY)
        self.assertEqual([row["source_url"] for row in sorted(rows, key=lambda r: r["source_url"])],
                         opened, "one attempt per URL, the 503 included")
        self.assertEqual(["SUCCEEDED", "FAILED_TERMINAL"],
                         [item["status"] for item in sorted(
                             result["captured"], key=lambda i: i["source_url"] != rows[0]["source_url"])])
        self.assertEqual(1, len(set(paced)), "one client, so its pacing spans the requests")
        log = parse_request_log_rows_for(session.data_root)
        appended = log[-2:]
        self.assertEqual({"ISSUE47_HISTORICAL_SOURCE_DEPENDENCY"}, {r["purpose"] for r in appended})
        self.assertEqual({"0"}, {r["retry_attempt"] for r in appended})
        checkpoint = strict_json_file(path=next(journal.iterdir()))
        self.assertEqual("LIVE", checkpoint["execution_mode"])
        self.assertIs(True, checkpoint["real_sec_credit"])
        validate_acquisition_checkpoint(session.data_root, checkpoint,
                                        strict_json_file(path=ROOT / MANIFEST_PATH))
        # A LIVE ledger is exported only beside the grant that spent it.
        with patch("vnext.continuous_sec_acquisition._journal", lambda: journal):
            with self.assertRaises(HistoricalAcquisitionError) as caught:
                EXPORT_MODULE.export_acquisition(ledger_root=root / "ledger",
                                                 out_dir=root / "export",
                                                 policy_root=root / "no-policy")
            self.assertIn("ISSUE_47_EXPORT_LIVE_LEDGER_WITHOUT_ALLOWANCE",
                          str(caught.exception))
            granted = root / "granted"
            (granted / "config").mkdir(parents=True)
            (granted / POLICY_PATH).write_text(json.dumps({
                "delegation_url": "u", "delegation_body_sha256": "d",
                "delegation_record_path": "r", "budget_root": str(root / "elsewhere"),
                "maximum_additional_provider_paid_sec_calls": [0, 0, 5]}), encoding="utf-8")
            with self.assertRaises(HistoricalAcquisitionError) as caught:
                EXPORT_MODULE.export_acquisition(ledger_root=root / "ledger",
                                                 out_dir=root / "export", policy_root=granted)
            self.assertIn("ISSUE_47_EXPORT_LEDGER_IS_NOT_THE_GRANTED_ROOT",
                          str(caught.exception))


def parse_request_log_rows_for(data_root):
    from sec_http import parse_request_log_rows
    return parse_request_log_rows(
        text=(data_root / "evidence/requests_log.csv").read_text(encoding="utf-8"))


class AnExportCarriesExactlyWhatTheReplayAccepts(unittest.TestCase):
    """The acquired sources reach another checkout, and nothing else does.

    The ledger root is on the owner's machine and the journal the frozen
    reader trusts is in that checkout's ``.git``; neither is pushed. So an
    export is checked where it is made - the ledger must be registered and the
    replay must accept it - and again where it is restored, and a restore that
    reads a changed byte, a changed index or an archive the index does not
    name is refused.
    """

    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="issue47-export-"))
        atexit.register(shutil.rmtree, cls.root, ignore_errors=True)
        rows = [row for row in _rows(_SCRIPTED_COMPANY)
                if row["new_acquisition_required"]
                and row["dependency_class"] == "ACCESSION_INSTANCE_DISCOVERY"]
        cls.rows = sorted(rows, key=lambda row: row["source_url"])[:4]
        cls.session = recorded_historical_session(root=cls.root / "ledger", response=BODY)
        cls.frame = {"requirements": copy.deepcopy(cls.rows[:3]),
                     "company_id": _SCRIPTED_COMPANY,
                     "target_report_dates": ["2021-12-31", "2022-12-31", "2023-12-31",
                                             "2024-12-31", "2025-12-31"]}
        with patch.object(SESSION_MODULE, "declared_frame",
                          lambda **kwargs: copy.deepcopy(cls.frame)):
            cls.session.capture_pending(company_id=_SCRIPTED_COMPANY)
        with patch.object(EXPORT_MODULE, "CHUNK_ROWS", 2):
            cls.first = EXPORT_MODULE.export_acquisition(ledger_root=cls.root / "ledger",
                                                         out_dir=cls.root / "export")
            cls.again = EXPORT_MODULE.export_acquisition(ledger_root=cls.root / "ledger",
                                                         out_dir=cls.root / "export-again")

    def _copy(self, name):
        target = Path(tempfile.mkdtemp(prefix="issue47-export-copy-")) / name
        self.addCleanup(shutil.rmtree, target.parent, ignore_errors=True)
        shutil.copytree(self.root / "export", target)
        return target

    def test_the_export_is_grouped_and_deterministic(self):
        names = sorted(path.name for path in (self.root / "export").iterdir())
        self.assertEqual(2, self.first["row_archives"])
        self.assertEqual(sorted(names), sorted(path.name for path in
                                               (self.root / "export-again").iterdir()))
        for name in names:
            self.assertEqual((self.root / "export" / name).read_bytes(),
                             (self.root / "export-again" / name).read_bytes(), name)

    def test_an_export_replaces_only_its_own_shorter_self(self):
        """One directory serves the SEC ledger; an export never goes backwards or across approvals."""
        target = self._copy("forward")
        with patch.object(EXPORT_MODULE, "CHUNK_ROWS", 2):
            self.assertEqual("EXPORTED", EXPORT_MODULE.export_acquisition(
                ledger_root=self.root / "ledger", out_dir=target)["status"])
        index_path = target / EXPORT_MODULE.INDEX_NAME
        original = json.loads(index_path.read_text(encoding="utf-8"))
        longer = copy.deepcopy(original)
        longer["state_archive"]["members"]["ledger/claims.jsonl"]["size"] += 1
        other = {**copy.deepcopy(original), "approval": {"delegation_body_sha256": "b" * 64}}
        for label, index in (("a longer export", longer), ("another approval's", other),
                             ("unreadable", None)):
            with self.subTest(label):
                index_path.write_text("{" if index is None else json.dumps(index),
                                      encoding="utf-8")
                with self.assertRaises(HistoricalAcquisitionError) as caught:
                    EXPORT_MODULE.export_acquisition(ledger_root=self.root / "ledger",
                                                     out_dir=target)
                self.assertIn("ISSUE_47_EXPORT_WOULD_NOT_EXTEND_THE_EXPORT_THERE",
                              str(caught.exception))

    def test_a_restore_replays_and_the_unchanged_reader_accepts_the_root(self):
        target = Path(tempfile.mkdtemp(prefix="issue47-restore-")) / "restored"
        self.addCleanup(shutil.rmtree, target.parent, ignore_errors=True)
        restored = EXPORT_MODULE.restore_acquisition(export_dir=self.root / "export",
                                                     out_root=target)
        self.assertEqual("RESTORED", restored["status"])
        self.assertEqual(3, restored["rows"])
        checkpoint, paths = checkpoint_installation(source_root=Path(restored["data_root"]))
        self.assertTrue(paths, "the restored successes are installable sources")
        record = strict_json_file(path=target / "import-record.json")
        self.assertIn("not_established_here", record)
        with self.assertRaises(HistoricalAcquisitionError):
            EXPORT_MODULE.restore_acquisition(export_dir=self.root / "export",
                                              out_root=target)

    def test_a_changed_archive_byte_is_refused(self):
        copied = self._copy("flipped")
        archive = sorted(copied.glob("rows-*.tar.gz"))[0]
        data = bytearray(archive.read_bytes())
        data[len(data) // 2] ^= 0x01
        archive.write_bytes(bytes(data))
        with self.assertRaises(HistoricalAcquisitionError) as caught:
            EXPORT_MODULE.restore_acquisition(export_dir=copied,
                                              out_root=copied.parent / "out")
        self.assertIn("ISSUE_47_EXPORT_ARCHIVE_CHANGED", str(caught.exception))

    def test_a_changed_index_is_refused(self):
        copied = self._copy("index")
        index = json.loads((copied / "export.json").read_text(encoding="utf-8"))
        index["exported_row_count"] += 1
        (copied / "export.json").write_text(json.dumps(index), encoding="utf-8")
        with self.assertRaises(HistoricalAcquisitionError) as caught:
            EXPORT_MODULE.restore_acquisition(export_dir=copied,
                                              out_root=copied.parent / "out")
        self.assertIn("ISSUE_47_EXPORT_RECORD_CHANGED:export_id", str(caught.exception))

    def test_member_paths_cannot_leave_the_root(self):
        for name in ("../evidence/x", "/etc/passwd", "a/../../b", "./a"):
            with self.subTest(name):
                with self.assertRaises(HistoricalAcquisitionError):
                    EXPORT_MODULE._safe_member(name)

    def test_a_claim_log_that_is_not_its_copy_is_not_exported(self):
        """A log truncated with its last slot is not an export of what was claimed."""
        mirror = SESSION_LEDGER.mirror_path(self.root / "ledger")
        saved = mirror.read_bytes()
        mirror.write_bytes(b"".join(saved.splitlines(keepends=True)[:-1]))
        try:
            with self.assertRaises(HistoricalAcquisitionError) as caught:
                EXPORT_MODULE.export_acquisition(ledger_root=self.root / "ledger",
                                                 out_dir=self.root / "export-from-a-truncated-copy")
            self.assertIn("ISSUE_47_EXPORT_CLAIM_LOG_DIFFERS_FROM_ITS_MIRROR", str(caught.exception))
        finally:
            mirror.write_bytes(saved)

    def test_an_unregistered_ledger_is_not_exported(self):
        root = Path(tempfile.mkdtemp(prefix="issue47-unregistered-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        session = recorded_historical_session(root=root / "ledger", response=BODY)
        with patch.object(SESSION_MODULE, "declared_frame",
                          lambda **kwargs: copy.deepcopy(self.frame)):
            session.capture_pending(company_id=_SCRIPTED_COMPANY, max_captures=1,
                                    register=False)
        with self.assertRaises(HistoricalAcquisitionError) as caught:
            EXPORT_MODULE.export_acquisition(ledger_root=root / "ledger", out_dir=root / "x")
        self.assertIn("ISSUE_47_EXPORT_LEDGER_NOT_REGISTERED", str(caught.exception))
        # What a process that died before registering leaves behind. The next
        # pass registers before it plans, which is what lets it plan at all.
        with patch.object(SESSION_MODULE, "declared_frame",
                          lambda **kwargs: copy.deepcopy(self.frame)):
            healed = session.capture_pending(company_id=_SCRIPTED_COMPANY, max_captures=0)
        self.assertTrue(healed["registered_before_planning"])
        self.assertEqual("EXPORTED", EXPORT_MODULE.export_acquisition(
            ledger_root=root / "ledger", out_dir=root / "x")["status"])

    def test_a_longer_ledger_rewrites_only_the_last_group(self):
        root = Path(tempfile.mkdtemp(prefix="issue47-grow-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        _copy_ledger(self.root / "ledger", root / "ledger")
        shutil.copytree(self.root / "export", root / "export")
        before = {path.name: path.read_bytes() for path in (root / "export").glob("rows-*")}
        session = recorded_historical_session(root=root / "ledger", response=BODY)
        frame = {**self.frame, "requirements": copy.deepcopy(self.rows)}
        with patch.object(SESSION_MODULE, "declared_frame", lambda **kwargs: copy.deepcopy(frame)):
            session.capture_pending(company_id=_SCRIPTED_COMPANY)
        with patch.object(EXPORT_MODULE, "CHUNK_ROWS", 2):
            EXPORT_MODULE.export_acquisition(ledger_root=root / "ledger", out_dir=root / "export")
        after = {path.name: path.read_bytes() for path in (root / "export").glob("rows-*")}
        first = sorted(before)[0]
        self.assertEqual(before[first], after[first], "a closed group is not rewritten")
        self.assertNotIn(sorted(before)[-1], after, "the open group was replaced, not kept")
        self.assertEqual(2, len(after))

    def test_a_write_that_fails_leaves_the_export_already_there(self):
        """The first live acquisition filled the container's disk in the middle of an export.

        The export then in place had lost a row archive and its state archive
        was already replaced, so its index named what was no longer there.
        Nothing is replaced now until everything new is written.
        """
        root = Path(tempfile.mkdtemp(prefix="issue47-full-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        _copy_ledger(self.root / "ledger", root / "ledger")
        shutil.copytree(self.root / "export", root / "export")
        before = {path.name: path.read_bytes() for path in (root / "export").iterdir()}
        session = recorded_historical_session(root=root / "ledger", response=BODY)
        frame = {**self.frame, "requirements": copy.deepcopy(self.rows)}
        with patch.object(SESSION_MODULE, "declared_frame", lambda **kwargs: copy.deepcopy(frame)):
            session.capture_pending(company_id=_SCRIPTED_COMPANY)
        writes = []
        real = EXPORT_MODULE._write_temporary

        def fills_up(path, data):
            writes.append(path.name)
            if len(writes) == 2:
                with path.open("wb") as handle:
                    handle.write(data[:len(data) // 2])
                raise OSError(28, "No space left on device")
            real(path, data)

        with patch.object(EXPORT_MODULE, "CHUNK_ROWS", 2), \
                patch.object(EXPORT_MODULE, "_write_temporary", fills_up):
            with self.assertRaises(OSError):
                EXPORT_MODULE.export_acquisition(ledger_root=root / "ledger",
                                                 out_dir=root / "export")
        self.assertEqual(2, len(writes), "the failure came part way through the new files")
        after = {path.name: path.read_bytes() for path in (root / "export").iterdir()}
        self.assertEqual(before, after, "the export already there is untouched, no file left over")
        with patch.object(EXPORT_MODULE, "CHUNK_ROWS", 2):
            self.assertEqual("EXPORTED", EXPORT_MODULE.export_acquisition(
                ledger_root=root / "ledger", out_dir=root / "export")["status"])
        self.assertFalse([path for path in (root / "export").iterdir()
                          if path.name.endswith(".tmp")])


class AnApprovalIsRegisteredOnlyFromTheApprovedBytes(unittest.TestCase):
    """What the owner approved, read back from GitHub, and nothing written otherwise.

    Nothing here posts. Registration reads a comment through a reader, and a
    comment is admitted only if its bytes are the approved text pinned by
    digest, its author is the approver and it is on this issue. A refusal
    writes neither the policy nor the record.
    """

    URL = "https://github.com/wlvh/SEC_metrics/issues/47#issuecomment-5800000001"

    def _comment(self, **changes):
        comment = {"id": 5800000001, "html_url": self.URL,
                   "issue_url": "https://api.github.com/repos/wlvh/SEC_metrics/issues/47",
                   "user": {"login": "wlvh", "id": 30534800, "type": "User"},
                   "author_association": "OWNER", "created_at": "2026-09-27T00:00:00Z",
                   "updated_at": "2026-09-27T00:00:00Z", "performed_via_github_app": None,
                   "body": (ROOT / APPROVED_BODY_PATH).read_text(encoding="utf-8")}
        comment.update(changes)
        return comment

    def _tree(self):
        root = Path(tempfile.mkdtemp(prefix="issue47-register-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        target = root / APPROVED_BODY_PATH
        target.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / APPROVED_BODY_PATH, target)
        return root

    def test_the_committed_body_is_the_approved_text(self):
        body = (ROOT / APPROVED_BODY_PATH).read_bytes()
        self.assertEqual(APPROVED_BODY_SHA256, hashlib.sha256(body).hexdigest())
        proposal = strict_json_file(path=ROOT / "docs/evidence/issue47_history/"
                                    "acquisition-wiring/proposed-allowance.json")
        self.assertEqual(proposal["the_comment_body_as_text"].encode("utf-8"), body)

    def test_the_approved_comment_registers_and_the_gate_accepts_it(self):
        root = self._tree()
        comment = self._comment()
        result = register_approval(repo_root=root, comment_url=self.URL,
                                   reader=lambda path: copy.deepcopy(comment))
        self.assertEqual("APPROVAL_REGISTERED", result["status"])
        self.assertEqual([0, 0, 1354], result["limits"])
        allowance = acquisition_allowance(repo_root=root,
                                          delegation_reader=lambda path: copy.deepcopy(comment))
        self.assertIs(True, allowance["approved_delegation"]["provenance_verified_against_github"])
        again = register_approval(repo_root=root, comment_url=self.URL,
                                  reader=lambda path: copy.deepcopy(comment))
        self.assertEqual(result, again, "registering the same approval twice changes nothing")

    def test_a_body_that_differs_by_one_byte_registers_nothing(self):
        root = self._tree()
        comment = self._comment()
        comment["body"] = comment["body"].replace("1354", "1355")
        with self.assertRaises(HistoricalAcquisitionError) as caught:
            register_approval(repo_root=root, comment_url=self.URL,
                              reader=lambda path: comment)
        self.assertIn("ISSUE_47_POSTED_BODY_IS_NOT_THE_APPROVED_TEXT", str(caught.exception))
        self.assertFalse((root / POLICY_PATH).exists())

    def test_a_footer_appended_to_the_body_registers_nothing(self):
        # What this environment's posting path would do to the body, which is
        # why the owner posts it: an appended attribution line is a different
        # text, and the gate parses the body as the approval record.
        root = self._tree()
        comment = self._comment()
        comment["body"] += "\n\n---\n_Generated by [Claude Code](https://claude.ai/code)_"
        with self.assertRaises(HistoricalAcquisitionError):
            register_approval(repo_root=root, comment_url=self.URL,
                              reader=lambda path: comment)
        self.assertFalse((root / POLICY_PATH).exists())

    def test_another_author_registers_nothing(self):
        root = self._tree()
        comment = self._comment(user={"login": "someone-else", "id": 1, "type": "User"})
        with self.assertRaises(HistoricalAcquisitionError) as caught:
            register_approval(repo_root=root, comment_url=self.URL,
                              reader=lambda path: comment)
        self.assertIn("ISSUE_47_DELEGATION_AUTHOR_IS_NOT_THE_APPROVER", str(caught.exception))
        self.assertFalse((root / POLICY_PATH).exists())

    def test_the_approver_s_login_alone_is_not_the_approver(self):
        """A re-review found only the login was read: another account of that name, a bot, a non-owner."""
        for change in ({"user": {"login": "wlvh", "id": 1, "type": "User"}},
                       {"user": {"login": "wlvh", "id": 30534800, "type": "Bot"}},
                       {"author_association": "NONE"}):
            with self.subTest(change=change):
                root = self._tree()
                with self.assertRaises(HistoricalAcquisitionError) as caught:
                    register_approval(repo_root=root, comment_url=self.URL,
                                      reader=lambda path: self._comment(**change))
                self.assertIn("ISSUE_47_DELEGATION_AUTHOR_IS_NOT_THE_APPROVER", str(caught.exception))
                self.assertFalse((root / POLICY_PATH).exists())

    def test_a_comment_on_another_issue_or_repository_registers_nothing(self):
        root = self._tree()
        for url in ("https://github.com/wlvh/SEC_metrics/issues/28#issuecomment-5800000001",
                    "https://github.com/other/SEC_metrics/issues/47#issuecomment-5800000001"):
            with self.subTest(url):
                with self.assertRaises(HistoricalAcquisitionError):
                    register_approval(repo_root=root, comment_url=url,
                                      reader=lambda path: self._comment(html_url=url))
        self.assertFalse((root / POLICY_PATH).exists())

    def test_an_approval_posted_through_an_app_registers_nothing(self):
        """Measured in the executor's container, which reads and writes GitHub as the owner.

        Its GitHub API calls carry the owner's account through a GitHub App, so
        a comment it posted with curl would be authored wlvh, associated OWNER,
        unedited and without the footer this environment's posting tool adds -
        the approved bytes, accepted as the owner's approval until this check.
        A reader that drops the field is refused too, not read as "no app".
        """
        for change in ({"performed_via_github_app": {"slug": "claude", "id": 1}},
                       {"performed_via_github_app": {}}, "DROPPED"):
            with self.subTest(change=change):
                root = self._tree()
                comment = self._comment()
                if change == "DROPPED":
                    del comment["performed_via_github_app"]
                else:
                    comment.update(change)
                with self.assertRaises(HistoricalAcquisitionError) as caught:
                    register_approval(repo_root=root, comment_url=self.URL,
                                      reader=lambda path: copy.deepcopy(comment))
                self.assertIn("ISSUE_47_DELEGATION_WAS_POSTED_THROUGH_AN_APP", str(caught.exception))
                self.assertFalse((root / POLICY_PATH).exists())
                self.assertFalse((root / APPROVAL_RECORD_PATH).exists())

    def test_a_body_pasted_into_the_web_page_registers_as_the_same_approval(self):
        """A browser sends a text box's line breaks as CRLF; the approved record is unchanged."""
        root = self._tree()
        comment = self._comment()
        comment["body"] = comment["body"].replace("\n", "\r\n") + "\r\n"
        result = register_approval(repo_root=root, comment_url=self.URL,
                                   reader=lambda path: copy.deepcopy(comment))
        self.assertEqual("APPROVAL_REGISTERED", result["status"])
        self.assertEqual(APPROVED_BODY_SHA256, result["delegation_body_sha256"])
        self.assertEqual([0, 0, 1354], result["limits"])
        # The saved record is what GitHub returned, not a cleaned copy: the
        # gate compares it with a fresh read byte for byte.
        saved = strict_json_file(path=root / APPROVAL_RECORD_PATH)
        self.assertEqual(comment["body"], saved["body"])
        self.assertIsNone(saved["performed_via_github_app"])
        allowance = acquisition_allowance(repo_root=root,
                                          delegation_reader=lambda path: copy.deepcopy(comment))
        self.assertIs(True, allowance["approved_delegation"]["provenance_verified_against_github"])
        self.assertEqual([0, 0, 1354], allowance["maximum_additional_provider_paid_sec_calls"])

    def test_only_line_breaks_are_forgiven(self):
        """Leading whitespace, a changed indent, a lone CR: each a different text, each refused."""
        approved = self._comment()["body"]
        self.assertIn("\n \"", approved, "the body is indented; the indent case below needs it")
        for name, body in (("leading newline", "\n" + approved),
                           ("indent changed", approved.replace("\n \"", "\n  \"", 1)),
                           ("lone CR", approved.replace("\n", "\r", 1)),
                           ("CRLF and one byte", approved.replace("\n", "\r\n").replace(
                               "1354", "1355"))):
            with self.subTest(name):
                root = self._tree()
                comment = self._comment(body=body)
                with self.assertRaises(HistoricalAcquisitionError) as caught:
                    register_approval(repo_root=root, comment_url=self.URL,
                                      reader=lambda path: copy.deepcopy(comment))
                self.assertIn("ISSUE_47_POSTED_BODY_IS_NOT_THE_APPROVED_TEXT", str(caught.exception))
                self.assertFalse((root / POLICY_PATH).exists())

    def test_a_policy_that_already_says_something_else_is_not_overwritten(self):
        root = self._tree()
        (root / POLICY_PATH).parent.mkdir(parents=True, exist_ok=True)
        (root / POLICY_PATH).write_text("{}\n", encoding="utf-8")
        with self.assertRaises(HistoricalAcquisitionError) as caught:
            register_approval(repo_root=root, comment_url=self.URL,
                              reader=lambda path: self._comment())
        self.assertIn("ISSUE_47_ALLOWANCE_ALREADY_REGISTERED_DIFFERENTLY", str(caught.exception))
        self.assertEqual("{}\n", (root / POLICY_PATH).read_text(encoding="utf-8"))


class ALedgerCannotBeResetByDeletingIt(unittest.TestCase):
    """What an independent review found, on the SEC ledger an allowance is spent on.

    Every count used to be rebuilt from whichever slot directories existed, so
    deleting a stopped slot released the stop and deleting the root released
    the cap. Issue #28's ledger refuses both; these cases hold this one to the
    same, and to the two further gaps the review named: a stop hidden by
    rewriting a slot's self-sealed records, and a root reached through a
    symlink.
    """

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="issue47-reset-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def _state(self, ledger_root):
        session = recorded_historical_session(root=ledger_root, response=BODY)
        with session.ledger.locked():
            return session.ledger.snapshot()

    def test_a_deleted_slot_is_a_refusal_not_a_smaller_count(self):
        ledger = _Chain.copy(self.root / "ledger")
        self.assertEqual([0, 0, 1], self._state(ledger)["counts"])
        shutil.rmtree(ledger / "calls/0001")
        with self.assertRaises(HistoricalSessionError) as caught:
            self._state(ledger)
        self.assertIn("ISSUE_47_LEDGER_CLAIM_SET_CHANGED", str(caught.exception))

    def test_an_emptied_root_is_a_refusal_not_a_fresh_start(self):
        """The slots and the claim log removed together, binding and anchor kept: not [0, 0, 0]."""
        ledger = _Chain.copy(self.root / "ledger")
        shutil.rmtree(ledger / "calls")
        (ledger / "claims.jsonl").unlink()
        with self.assertRaises(HistoricalSessionError) as caught:
            self._state(ledger)
        self.assertIn("ISSUE_47_LEDGER_CLAIM_LOG_DIFFERS_FROM_ITS_MIRROR:0 in the root, 1 beside it",
                      str(caught.exception))

    def test_a_truncated_last_claim_is_a_refusal_not_a_released_slot(self):
        ledger = _Chain.copy(self.root / "ledger")
        shutil.rmtree(ledger / "calls/0001")
        log = ledger / "claims.jsonl"
        log.write_text("".join(log.read_text().splitlines(keepends=True)[:-1]))
        with self.assertRaises(HistoricalSessionError) as caught:
            self._state(ledger)
        self.assertIn("ISSUE_47_LEDGER_CLAIM_LOG_DIFFERS_FROM_ITS_MIRROR", str(caught.exception))

    def test_a_deleted_root_is_a_refusal_not_a_fresh_start(self):
        ledger = _Chain.copy(self.root / "ledger")
        shutil.rmtree(ledger)
        with self.assertRaises(HistoricalSessionError) as caught:
            self._state(ledger)
        self.assertIn("ISSUE_47_LEDGER_BINDING_MISSING_OR_RESET", str(caught.exception))

    def test_a_same_request_claimed_again_is_a_redraw(self):
        ledger = _Chain.copy(self.root / "ledger")
        session = recorded_historical_session(root=ledger, response=BODY)
        intent = strict_json_file(path=ledger / "calls/0001/intent.json")
        with session.ledger.locked():
            with self.assertRaises(HistoricalSessionError) as caught:
                session.ledger.claim(channel="SEC", request_digest=intent["request_digest"],
                                     plan_id="sha256:" + "0" * 64,
                                     purpose=intent["purpose"])
        self.assertIn("ISSUE_47_UNCHANGED_REQUEST_REDRAW_FORBIDDEN", str(caught.exception))

    def test_a_root_reached_through_a_symlink_is_refused(self):
        ledger = _Chain.copy(self.root / "ledger")
        alias = self.root / "alias"
        alias.symlink_to(ledger)
        session = recorded_historical_session(root=ledger, response=BODY)
        aliased = SESSION_MODULE._allowance_ledger(allowance=session.allowance, root=alias,
                                                   live=False)
        with self.assertRaises(HistoricalSessionError) as caught:
            with aliased.locked():
                pass
        self.assertIn("ISSUE_47_LEDGER_PATH_ALIAS", str(caught.exception))

    def test_a_stop_hidden_by_rewriting_the_slot_s_own_records_is_found(self):
        # An unknown outcome, then its receipt and terminal rewritten and
        # resealed as an ordinary failure. Both are self-sealed, so only the
        # request log row they name can tell.
        ledger = self.root / "unknown"
        session = recorded_historical_session(root=ledger, response=BODY, status=0)
        result = session.capture(company_id="marriott_international", url=DECLARED)
        self.assertEqual("UNKNOWN_REMOTE_OUTCOME", result["status"])
        slot = ledger / "calls/0001"
        receipt = strict_json_file(path=slot / "sec-receipt.json")
        forged = _seal({**{k: v for k, v in receipt.items() if k != "receipt_id"},
                        "status": "FAILED_TERMINAL", "stop_reason": ""}, "receipt_id")
        terminal = strict_json_file(path=slot / "terminal.json")
        forged_terminal = _seal({**{k: v for k, v in terminal.items() if k != "terminal_id"},
                                 "status": "FAILED_TERMINAL", "stop_reason": "",
                                 "sec_receipt_id": forged["receipt_id"]}, "terminal_id")
        (slot / "sec-receipt.json").write_text(json.dumps(forged), encoding="utf-8")
        (slot / "terminal.json").write_text(json.dumps(forged_terminal), encoding="utf-8")
        with session.ledger.locked():
            blocked = session.ledger.snapshot()["blocked"]
        self.assertEqual(["TERMINAL_DISAGREES_WITH_THE_LOGGED_ROW:UNKNOWN_REMOTE_OUTCOME/"
                          "UNKNOWN_REMOTE_OUTCOME"], [item["reason"] for item in blocked])



class TheResumeIsHandedTheBranchTipThroughGit(unittest.TestCase):
    """The resume command reads the export index at the upstream tip, fetched when it runs.

    What the 2026-09-29 loss did to the checkout: a snapshot restore reset it
    to a commit hours older than the branch. These run git against a local
    bare remote; nothing leaves the machine.
    """

    INDEX = "evidence/issue47_acquired/export.json"

    def setUp(self):
        spec = importlib.util.spec_from_file_location("issue47_sec_cli",
                                                      ROOT / "tools/vnext_historical_sec.py")
        self.cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.cli)
        self.base = Path(tempfile.mkdtemp(prefix="issue47-branch-tip-"))
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)

    def _git(self, cwd, *arguments):
        subprocess.run(["git", "-c", "user.name=issue47-test", "-c", "user.email=test@invalid",
                        "-c", "init.defaultBranch=main", *arguments],
                       cwd=cwd, check=True, capture_output=True, text=True)

    def _commit(self, clone, body):
        (clone / self.INDEX).parent.mkdir(parents=True, exist_ok=True)
        (clone / self.INDEX).write_bytes(body)
        self._git(clone, "add", self.INDEX)
        self._git(clone, "commit", "-m", "export")
        self._git(clone, "push", "-q", "origin", "HEAD:main")

    def test_a_checkout_behind_the_branch_is_handed_the_branch_s_newer_export(self):
        remote = self.base / "remote.git"
        self._git(self.base, "init", "-q", "--bare", str(remote))
        writer, stale = self.base / "writer", self.base / "stale"
        self._git(self.base, "clone", "-q", str(remote), str(writer))
        self._commit(writer, b'{"export": 1}\n')
        self._git(self.base, "clone", "-q", str(remote), str(stale))
        self._commit(writer, b'{"export": 2}\n')
        with patch.object(self.cli, "ROOT", stale):
            with self.assertRaises(HistoricalAcquisitionError) as caught:
                self.cli._branch_tip()
        self.assertIn("ISSUE_47_CHECKOUT_BEHIND_THE_BRANCH_TIP", str(caught.exception))
        self._git(stale, "merge", "-q", "--ff-only", "origin/main")
        with patch.object(self.cli, "ROOT", stale):
            tip = self.cli._branch_tip()
        self.assertEqual(b'{"export": 2}\n', tip["export_index"], "fetched, not a stale ref")
        head = subprocess.run(["git", "-C", str(writer), "rev-parse", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
        self.assertEqual(head, tip["commit"])

    def test_a_tip_with_no_export_hands_none(self):
        remote = self.base / "remote.git"
        self._git(self.base, "init", "-q", "--bare", str(remote))
        clone = self.base / "clone"
        self._git(self.base, "clone", "-q", str(remote), str(clone))
        (clone / "README").write_text("x", encoding="utf-8")
        self._git(clone, "add", "README")
        self._git(clone, "commit", "-m", "first")
        self._git(clone, "push", "-q", "-u", "origin", "HEAD:main")
        with patch.object(self.cli, "ROOT", clone):
            self.assertIsNone(self.cli._branch_tip()["export_index"])

    def test_a_checkout_with_no_upstream_is_a_refusal(self):
        alone = self.base / "alone"
        self._git(self.base, "init", "-q", str(alone))
        with patch.object(self.cli, "ROOT", alone):
            with self.assertRaises(HistoricalAcquisitionError) as caught:
                self.cli._branch_tip()
        self.assertIn("ISSUE_47_RESUME_BRANCH_UNREADABLE", str(caught.exception))


class AnApprovalMustBeReadAsWrittenAndUnedited(unittest.TestCase):
    """The approval the owner read is the one enforced, and it was not changed later.

    Both were accepted before an independent review: plain ``json.loads``
    kept the last of two duplicate keys, so a body showing one limit and
    carrying a larger one later was enforced at the larger; and a comment
    edited after it was posted still authorized.
    """

    def setUp(self):
        self.made = []
        self.addCleanup(lambda: [shutil.rmtree(p, ignore_errors=True)
                                 for pair in self.made for p in pair])

    def test_a_duplicate_key_is_a_refusal_not_the_last_value(self):
        root, budget = _grant_tree()
        self.made.append((root, budget))
        record = json.loads((root / "docs/delegation.json").read_text())
        policy = json.loads((root / POLICY_PATH).read_text())
        body = record["body"]
        doubled = body[:-1] + ', "maximum_additional_provider_paid_sec_calls": [0, 0, 8000]}'
        record["body"] = doubled
        policy["maximum_additional_provider_paid_sec_calls"] = [0, 0, 8000]
        policy["delegation_body_sha256"] = hashlib.sha256(doubled.encode()).hexdigest()
        (root / "docs/delegation.json").write_text(json.dumps(record), encoding="utf-8")
        (root / POLICY_PATH).write_text(json.dumps(policy), encoding="utf-8")
        with self.assertRaises(HistoricalAcquisitionError) as caught:
            acquisition_allowance(repo_root=root)
        self.assertIn("ISSUE_47_DELEGATION_BODY_IS_NOT_A_RECORD", str(caught.exception))

    def test_an_edited_comment_is_not_the_approval(self):
        root, budget = _grant_tree()
        self.made.append((root, budget))
        acquisition_allowance(repo_root=root)  # the unedited one is accepted
        record = json.loads((root / "docs/delegation.json").read_text())
        record["updated_at"] = "2026-09-28T00:00:00Z"
        (root / "docs/delegation.json").write_text(json.dumps(record), encoding="utf-8")
        with self.assertRaises(HistoricalAcquisitionError) as caught:
            acquisition_allowance(repo_root=root)
        self.assertIn("ISSUE_47_DELEGATION_COMMENT_WAS_EDITED", str(caught.exception))


class AStartMustBePublishedBeforeAnyRequest(unittest.TestCase):
    """The start a lost container cannot take with it.

    On 2026-09-29 the owner decided the acquisition runs in the executor's
    cloud container. A container is reclaimed with its disk, and a ledger
    that vanishes with it would let the allowance be spent again from an
    empty one; so a start is written beside the ledger and published as a
    marker comment on issue 47, and the live path refuses unless the earliest
    marker for this approval is unedited, has the owner's association and
    carries the local record. These cases are about which marker counts and
    what a missing half says, because a check that accepted the latest marker,
    an edited one or a stranger's would pass every case that only asks
    whether a marker exists.
    """

    URL = "https://github.com/wlvh/SEC_metrics/issues/47#issuecomment-5800000001"
    FOOTER = "\n---\n_Generated by [Claude Code](https://claude.ai/code)_"

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="issue47-start-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.allowance = {"requirement_id": "issue_47_v1",
                          "budget_root": str(self.root / "ledger"),
                          "delegation_url": self.URL,
                          "delegation_body_sha256": "a" * 64}
        self.next_id = 5900000000

    def _comment(self, record, *, association="OWNER", edited=False, when="2026-09-29T01:00:00Z",
                 body=None):
        """A comment as the list returns it: on issue 47, by the owner's account unless named."""
        self.next_id += 1
        return {"id": self.next_id,
                "html_url": "https://github.com/wlvh/SEC_metrics/issues/47#issuecomment-"
                            + str(self.next_id),
                "issue_url": "https://api.github.com/repos/wlvh/SEC_metrics/issues/47",
                "user": {"login": "wlvh", "id": 30534800, "type": "User"},
                "author_association": association, "created_at": when,
                "updated_at": "2026-09-29T09:00:00Z" if edited else when,
                "body": (body if body is not None
                         else SESSION_MODULE.marker_comment_body(record) + self.FOOTER)}

    @staticmethod
    def _reader(comments):
        pages = [comments[i:i + 100] for i in range(0, len(comments), 100)] or [[]]
        asked = []

        def read(path):
            asked.append(path)
            page = int(path.rsplit("page=", 1)[1])
            return copy.deepcopy(pages[page - 1] if page <= len(pages) else [])

        read.asked = asked
        return read

    def _start(self):
        """A start, with the full local record - random number included - as ``record``.

        What a start returns and prints is the marker's public view; a case
        that builds this host's marker needs the record the host keeps.
        """
        started = SESSION_MODULE.start_ledger(allowance=self.allowance, reader=self._reader([]))
        return {**started, "view": started["record"], "record": strict_json_file(
            path=SESSION_MODULE.start_record_path(self.root / "ledger"))}

    def _other_record(self):
        return {**self._start_record_shape(), "instance_nonce": "0" * 32}

    def _start_record_shape(self):
        return {"record_type": SESSION_MODULE.START_TYPE, "schema_version": 1,
                "requirement_id": "issue_47_v1", "delegation_url": self.URL,
                "delegation_body_sha256": "a" * 64, "budget_root": str(self.root / "ledger"),
                "created_at": "2026-09-29T00:00:00Z"}

    def test_a_start_writes_the_local_record_and_a_marker_that_does_not_carry_its_number(self):
        from vnext.historical_ledger_start import marker_view
        started = self._start()
        self.assertEqual(32, len(started["record"]["instance_nonce"]))
        comment = self._comment(None, body=started["marker_comment_body"] + self.FOOTER)
        published = SESSION_MODULE._marker_record(comment["body"])
        self.assertEqual(marker_view(started["record"]), published)
        self.assertEqual(published, started["view"])
        self.assertNotIn(started["record"]["instance_nonce"], started["marker_comment_body"])
        verified = SESSION_MODULE.require_published_start(branch_export_index=_tip(), allowance=self.allowance,
                                                          reader=self._reader([comment]))
        self.assertEqual(comment["html_url"], verified["marker_url"])

    def test_a_marker_copied_beside_an_empty_root_is_not_the_start(self):
        """An independent review copied a marker that carried the record back beside an empty root.

        The marker now shows the record without its random number, so what a
        new host can write from it does not match the digest it also shows.
        """
        started = self._start()
        marker = self._comment(None, body=started["marker_comment_body"])
        path = SESSION_MODULE.start_record_path(self.root / "ledger")
        path.unlink()
        shown = SESSION_MODULE._marker_record(marker["body"])
        for guess in ({k: v for k, v in shown.items() if k != "start_record_sha256"},
                      {**{k: v for k, v in shown.items() if k != "start_record_sha256"},
                       "instance_nonce": "0" * 32}):
            with self.subTest(fields=sorted(guess)):
                path.write_text(json.dumps(guess), encoding="utf-8")
                with self.assertRaises(HistoricalSessionError) as caught:
                    SESSION_MODULE.require_published_start(branch_export_index=_tip(), allowance=self.allowance,
                                                           reader=self._reader([marker]))
                self.assertIn("ISSUE_47_SEC_LEDGER_STARTED_ELSEWHERE", str(caught.exception))

    def test_a_marker_not_from_this_issue_or_account_does_not_count(self):
        record = self._start()["record"]
        for field, value in (("issue_url", "https://api.github.com/repos/wlvh/SEC_metrics/issues/28"),
                             ("user", {"login": "wlvh", "id": 1, "type": "User"}),
                             ("user", {"login": "wlvh", "id": 30534800, "type": "Bot"}),
                             ("user", None)):
            with self.subTest(field=field, value=value):
                comment = {**self._comment(record), field: value}
                with self.assertRaises(HistoricalSessionError) as caught:
                    SESSION_MODULE.require_published_start(branch_export_index=_tip(), allowance=self.allowance,
                                                           reader=self._reader([comment]))
                self.assertIn("ISSUE_47_SEC_LEDGER_START_NOT_PUBLISHED", str(caught.exception))

    def test_a_ledger_behind_its_export_on_the_branch_is_refused(self):
        """The export binds its claim log; this host's log must begin with exactly those bytes."""
        import hashlib
        record = self._start()["record"]
        marker = self._reader([self._comment(record)])
        checkout = self.root / "checkout"
        index = checkout / "evidence/issue47_acquired/export.json"
        index.parent.mkdir(parents=True)
        claims = b'{"n":1}\n{"n":2}\n'
        index.write_text(json.dumps({"execution_mode": "LIVE",
                                     "approval": {"delegation_body_sha256": "a" * 64},
                                     "state_archive": {"members": {"ledger/claims.jsonl": {
                                         "sha256": hashlib.sha256(claims).hexdigest(),
                                         "size": len(claims)}}}}), encoding="utf-8")
        ledger = self.root / "ledger"
        for held in (None, claims[:8], b'{"n":9}\n{"n":2}\n'):
            with self.subTest(held=held):
                if held is not None:
                    ledger.mkdir(exist_ok=True)
                    (ledger / "claims.jsonl").write_bytes(held)
                with self.assertRaises(HistoricalSessionError) as caught:
                    SESSION_MODULE.require_published_start(branch_export_index=_tip(checkout), allowance=self.allowance,
                                                           reader=marker, checkout=checkout)
                self.assertIn("ISSUE_47_SEC_LEDGER_BEHIND_ITS_EXPORT", str(caught.exception))
        for held in (claims, claims + b'{"n":3}\n'):
            (ledger / "claims.jsonl").write_bytes(held)
            SESSION_MODULE.require_published_start(branch_export_index=_tip(checkout), allowance=self.allowance, reader=marker,
                                                   checkout=checkout)
        index.write_text("{", encoding="utf-8")
        with self.assertRaises(HistoricalSessionError) as caught:
            SESSION_MODULE.require_published_start(branch_export_index=_tip(checkout), allowance=self.allowance, reader=marker,
                                                   checkout=checkout)
        self.assertIn("ISSUE_47_SEC_LEDGER_EXPORT_UNREADABLE", str(caught.exception))

    def test_nothing_is_requested_until_the_marker_is_on_github(self):
        self._start()
        with self.assertRaises(HistoricalSessionError) as caught:
            SESSION_MODULE.require_published_start(branch_export_index=_tip(), allowance=self.allowance,
                                                   reader=self._reader([]))
        self.assertIn("ISSUE_47_SEC_LEDGER_START_NOT_PUBLISHED", str(caught.exception))

    def test_an_unstarted_ledger_is_refused_by_name(self):
        with self.assertRaises(HistoricalSessionError) as caught:
            SESSION_MODULE.require_published_start(branch_export_index=_tip(), allowance=self.allowance,
                                                   reader=self._reader([]))
        self.assertIn("ISSUE_47_SEC_LEDGER_NOT_STARTED", str(caught.exception))

    def test_an_export_on_the_branch_blocks_a_start_the_issue_would_allow(self):
        """The marker guards a lost container, not a deleted comment; an export guards both.

        The executor acts on GitHub as the owner's account, so it can delete a
        marker comment, and the comments API shows no trace of it. Here the
        issue shows no marker at all, as after such a deletion, and the start
        is refused because the checkout carries this approval's export. An
        export of another approval, or of a recorded test ledger, does not
        block; an index nobody can read does.
        """
        checkout = self.root / "checkout"
        index = checkout / "evidence/issue47_acquired/export.json"
        index.parent.mkdir(parents=True)
        for label, content, blocks in (
                ("this approval", {"execution_mode": "LIVE",
                                   "approval": {"delegation_body_sha256": "a" * 64}}, True),
                ("damaged index", None, True),
                ("approval not a record", {"execution_mode": "LIVE", "approval": "x"}, True),
                ("another approval", {"execution_mode": "LIVE",
                                      "approval": {"delegation_body_sha256": "b" * 64}}, False),
                ("recorded test ledger", {"execution_mode": "RECORDED_TEST_ONLY",
                                          "approval": None}, False)):
            with self.subTest(label):
                index.write_text("{not json" if content is None else json.dumps(content),
                                 encoding="utf-8")
                path = SESSION_MODULE.start_record_path(self.root / "ledger")
                if blocks:
                    with self.assertRaises(HistoricalSessionError) as caught:
                        SESSION_MODULE.start_ledger(allowance=self.allowance,
                                                    reader=self._reader([]), checkout=checkout)
                    self.assertIn("ISSUE_47_SEC_LEDGER_ALREADY_EXPORTED", str(caught.exception))
                    self.assertFalse(path.exists(), "a refused start writes no record")
                else:
                    SESSION_MODULE.start_ledger(allowance=self.allowance,
                                                reader=self._reader([]), checkout=checkout)
                    self.assertTrue(path.is_file())
                    path.unlink()

    def test_a_host_that_lost_its_ledger_cannot_start_the_allowance_again(self):
        """The marker is on GitHub and the local record is gone - a new container, or a deletion."""
        published = [self._comment(self._other_record())]
        with self.assertRaises(HistoricalSessionError) as caught:
            SESSION_MODULE.require_published_start(branch_export_index=_tip(), allowance=self.allowance,
                                                   reader=self._reader(published))
        self.assertIn("ISSUE_47_SEC_LEDGER_STARTED_ELSEWHERE", str(caught.exception))
        with self.assertRaises(HistoricalSessionError) as caught:
            SESSION_MODULE.start_ledger(allowance=self.allowance, reader=self._reader(published))
        self.assertIn("ISSUE_47_SEC_LEDGER_STARTED_ELSEWHERE", str(caught.exception))
        self.assertFalse(SESSION_MODULE.start_record_path(self.root / "ledger").exists())

    def test_the_earliest_marker_decides_not_the_latest(self):
        # Two containers started; the second posted after the first. The
        # second must lose even though its own marker is on the issue.
        record = self._start()["record"]
        earlier = self._comment(self._other_record(), when="2026-09-29T01:00:00Z")
        ours = self._comment(record, when="2026-09-29T02:00:00Z")
        with self.assertRaises(HistoricalSessionError) as caught:
            SESSION_MODULE.require_published_start(branch_export_index=_tip(), allowance=self.allowance,
                                                   reader=self._reader([ours, earlier]))
        self.assertIn("ISSUE_47_SEC_LEDGER_STARTED_ELSEWHERE", str(caught.exception))

    def test_an_edited_marker_does_not_count(self):
        record = self._start()["record"]
        with self.assertRaises(HistoricalSessionError) as caught:
            SESSION_MODULE.require_published_start(branch_export_index=_tip(), 
                allowance=self.allowance, reader=self._reader([self._comment(record, edited=True)]))
        self.assertIn("ISSUE_47_SEC_LEDGER_START_MARKER_EDITED", str(caught.exception))

    def test_a_stranger_s_marker_neither_blocks_nor_stands_in(self):
        record = self._start()["record"]
        stranger_first = self._comment(self._other_record(), association="NONE",
                                       when="2026-09-29T00:30:00Z")
        ours = self._comment(record)
        SESSION_MODULE.require_published_start(branch_export_index=_tip(), allowance=self.allowance,
                                               reader=self._reader([stranger_first, ours]))
        forged = self._comment(record, association="CONTRIBUTOR")
        with self.assertRaises(HistoricalSessionError) as caught:
            SESSION_MODULE.require_published_start(branch_export_index=_tip(), allowance=self.allowance,
                                                   reader=self._reader([forged]))
        self.assertIn("ISSUE_47_SEC_LEDGER_START_NOT_PUBLISHED", str(caught.exception))

    def test_another_approval_s_marker_is_not_this_one_s(self):
        record = self._start()["record"]
        other = self._comment({**record, "delegation_body_sha256": "b" * 64})
        with self.assertRaises(HistoricalSessionError) as caught:
            SESSION_MODULE.require_published_start(branch_export_index=_tip(), allowance=self.allowance,
                                                   reader=self._reader([other]))
        self.assertIn("ISSUE_47_SEC_LEDGER_START_NOT_PUBLISHED", str(caught.exception))

    def test_markers_are_read_past_the_first_page(self):
        record = self._start()["record"]
        chatter = [self._comment(None, body="progress note %d" % index) for index in range(100)]
        reader = self._reader(chatter + [self._comment(record)])
        SESSION_MODULE.require_published_start(branch_export_index=_tip(),
                                               allowance=self.allowance, reader=reader)
        # Two scans, each past the first page: the resume markers (none here,
        # which is what lets a started host spend) and then the start markers.
        self.assertEqual(4, len(reader.asked))
        self.assertEqual(2, len(set(reader.asked)))

    def test_a_ledger_already_at_the_root_is_not_started_over(self):
        for leftover in ("root", "anchor"):
            with self.subTest(leftover):
                root = Path(tempfile.mkdtemp(prefix="issue47-start-left-"))
                self.addCleanup(shutil.rmtree, root, ignore_errors=True)
                allowance = {**self.allowance, "budget_root": str(root / "ledger")}
                if leftover == "root":
                    (root / "ledger").mkdir()
                    (root / "ledger" / "binding.json").write_text("{}", encoding="utf-8")
                else:
                    SESSION_LEDGER.anchor_path(root / "ledger").write_text("{}", encoding="utf-8")
                with self.assertRaises(HistoricalSessionError) as caught:
                    SESSION_MODULE.start_ledger(allowance=allowance, reader=self._reader([]))
                self.assertIn("ISSUE_47_SEC_LEDGER_EXISTS_WITHOUT_A_START", str(caught.exception))

    def test_the_live_path_needs_the_branch_to_say_which_extension(self):
        """A branch tip that does not name the extension files is refused before the ledger."""
        allowance = {**self.allowance, "sec_wiring_receipt_path": "unused",
                     "maximum_additional_provider_paid_sec_calls": [0, 0, 5],
                     "scope": {"purposes": ["ISSUE47_HISTORICAL_SOURCE_DEPENDENCY"]}}
        with patch.object(SESSION_MODULE, "acquisition_allowance",
                          lambda **kwargs: copy.deepcopy(allowance)), \
                patch.object(SESSION_MODULE, "verify_offline_wiring", lambda **kwargs: None), \
                patch("vnext.historical_source_acquisition.live_github_reader",
                      lambda: self._reader([])), \
                patch.object(SESSION_MODULE, "SecHttpClient",
                             side_effect=AssertionError("a transport was built")):
            with self.assertRaises(HistoricalAcquisitionError) as caught:
                live_historical_session(branch_tip=lambda: {"export_index": _tip()})
        self.assertIn("ISSUE_47_BRANCH_TIP_DOES_NOT_SAY_WHICH_EXTENSION", str(caught.exception))

    def test_the_live_path_checks_the_start_before_any_transport(self):
        """Registered and wired, not started: refused before a session, and so before a socket."""
        allowance = {**self.allowance, "sec_wiring_receipt_path": "unused",
                     "maximum_additional_provider_paid_sec_calls": [0, 0, 5],
                     "scope": {"purposes": ["ISSUE47_HISTORICAL_SOURCE_DEPENDENCY"]}}
        reader = self._reader([])
        with patch.object(SESSION_MODULE, "acquisition_allowance",
                          lambda **kwargs: copy.deepcopy(allowance)), \
                patch.object(SESSION_MODULE, "verify_offline_wiring", lambda **kwargs: None), \
                patch("vnext.historical_source_acquisition.live_github_reader", lambda: reader), \
                patch.object(SESSION_MODULE, "SecHttpClient",
                             side_effect=AssertionError("a transport was built")), \
                patch.object(SESSION_MODULE, "HistoricalSecSession",
                             side_effect=AssertionError("a session was built")):
            with self.assertRaises(HistoricalSessionError) as caught:
                live_historical_session(branch_tip=lambda: {"export_index": _tip(),
                                                          "extension_files": _NO_EXTENSION})
        self.assertIn("ISSUE_47_SEC_LEDGER_NOT_STARTED", str(caught.exception))
        # The same path with the start published builds the session.
        SESSION_MODULE.start_ledger(allowance=allowance, reader=reader)
        record = strict_json_file(path=SESSION_MODULE.start_record_path(
            Path(allowance["budget_root"])))
        published = self._reader([self._comment(record)])
        with patch.object(SESSION_MODULE, "acquisition_allowance",
                          lambda **kwargs: copy.deepcopy(allowance)), \
                patch.object(SESSION_MODULE, "verify_offline_wiring", lambda **kwargs: None), \
                patch("vnext.historical_source_acquisition.live_github_reader",
                      lambda: published), \
                patch.object(SESSION_MODULE, "SecHttpClient",
                             side_effect=AssertionError("a transport was built")):
            session = live_historical_session(branch_tip=lambda: {"export_index": _tip(),
                                                          "extension_files": _NO_EXTENSION})
        self.assertEqual(Path(allowance["budget_root"]), session.ledger.root)
        # It keeps the check for every pass, and holds the ledger to the charge
        # the check verified: none, for a ledger started here.
        self.assertEqual(0, session.ledger._pinned_reserve)
        self.assertEqual(0, session.published_check()["reserve_sec_calls"])
        self.assertTrue(session.ledger.live)


class AReceiptSaysWhichWayItsBytesCame(unittest.TestCase):
    """A LIVE receipt names the HTTPS proxy and CA bundle the request used.

    The owner accepted a run from a container whose egress proxy re-terminates
    TLS, where the client verifies the proxy's certificate rather than SEC's.
    A receipt silent about that would read as a direct fetch; a receipt that
    kept the proxy's credentials would leak them into the repository.
    """

    def test_the_live_receipt_names_the_proxy_without_credentials_and_the_bundle(self):
        root = Path(tempfile.mkdtemp(prefix="issue47-transport-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        import sec_http
        row = [row for row in _rows(_SCRIPTED_COMPANY)
               if row["new_acquisition_required"]
               and row["dependency_class"] == "ACCESSION_INSTANCE_DISCOVERY"][0]
        scope = {"purposes": ["ISSUE47_HISTORICAL_SOURCE_DEPENDENCY"],
                 "company_ids": [_SCRIPTED_COMPANY],
                 "dependency_classes": ["ACCESSION_INSTANCE_DISCOVERY"],
                 "earliest_report_end": "2021-12-31", "latest_report_end": "2026-01-31"}
        scope["grants"] = [_whole_envelope(scope)]
        allowance = {"requirement_id": "issue_47_v1", "budget_root": str(root / "ledger"),
                     "maximum_additional_provider_paid_sec_calls": [0, 0, 5], "scope": scope}
        ledger = SESSION_MODULE._allowance_ledger(allowance=allowance, root=root / "ledger",
                                                  live=True)
        session = SESSION_MODULE.HistoricalSecSession(factory=SESSION_MODULE._FACTORY,
                                                      allowance=allowance, ledger=ledger)
        bundle = root / "bundle.pem"
        bundle.write_bytes(b"not a real certificate, only its digest is recorded\n")
        frame = {"requirements": [copy.deepcopy(row)], "company_id": _SCRIPTED_COMPANY,
                 "target_report_dates": ["2021-12-31", "2022-12-31", "2023-12-31",
                                         "2024-12-31", "2025-12-31"]}
        environment = {"HTTPS_PROXY": "http://someone:secret@proxy.invalid:3128",
                       "https_proxy": "http://someone:secret@proxy.invalid:3128",
                       "SSL_CERT_FILE": str(bundle)}
        with patch.dict(os.environ, environment), \
                patch.object(sec_http, "urlopen",
                             lambda request, timeout: _FakeResponse(BODY, 200)), \
                patch("vnext.continuous_sec_acquisition._journal", lambda: root / "journal"), \
                patch.object(SESSION_MODULE, "declared_frame",
                             lambda **kwargs: copy.deepcopy(frame)), \
                patch.object(socket.socket, "connect",
                             side_effect=AssertionError("a socket was opened")):
            result = session.capture_pending(company_id=_SCRIPTED_COMPANY)
        self.assertEqual(["SUCCEEDED"], [item["status"] for item in result["captured"]])
        receipt = strict_json_file(path=root / "ledger/calls/0001/sec-receipt.json")
        self.assertEqual({"https_proxy": "http://proxy.invalid:3128",
                          "ca_bundle": {"path": str(bundle),
                                        "sha256": SESSION_MODULE.sha256_file(path=bundle)}},
                         receipt["transport"])
        self.assertNotIn("secret", json.dumps(receipt))

    def test_a_recorded_receipt_says_no_network_was_used(self):
        ledger = _Chain.copy(Path(tempfile.mkdtemp(prefix="issue47-transport-rec-")) / "ledger")
        self.addCleanup(shutil.rmtree, ledger.parent, ignore_errors=True)
        receipt = strict_json_file(path=ledger / "calls/0001/sec-receipt.json")
        self.assertEqual({"network": "NONE_RECORDED_RESPONSE"}, receipt["transport"])


from vnext import historical_sec_resume as RESUME_MODULE  # noqa: E402


class ALostHostResumesFromTheExportAndPaysForWhatItMayHaveSpent(unittest.TestCase):
    """The container that held the ledger was restored from an older snapshot mid-acquisition.

    What that left, measured on 2026-09-29: the ledger root, its start record
    and every request after the last pushed export gone; the export on the
    branch intact; a start the design refuses, because the branch carries this
    approval's export; and a live path that refuses, because the start record
    the earliest marker names is gone. Resuming was the owner's decision, and
    the owner allowed the acquisition to run again. These cases are about the
    two ways a resume could go wrong without failing: counting from less than
    was spent, and resuming a ledger that is not the one exported.
    """

    URL = "https://github.com/wlvh/SEC_metrics/issues/47#issuecomment-5800000047"
    DECISION = {"text": "allow the SEC acquisition to run", "received_at": "2026-09-29T12:35:00Z"}

    @classmethod
    def setUpClass(cls):
        import sec_http
        cls.base = Path(tempfile.mkdtemp(prefix="issue47-resume-"))
        atexit.register(shutil.rmtree, cls.base, ignore_errors=True)
        cls.root = cls.base / "ledger"
        cls.checkout = cls.base / "checkout"
        cls.checkout.mkdir()
        cls.journal = cls.base / "journal"
        rows = _rows(_SCRIPTED_COMPANY)
        cls.annual = sorted((row for row in rows if row["new_acquisition_required"]
                             and row["dependency_class"] == "ACCESSION_INSTANCE_DISCOVERY"),
                            key=lambda row: row["source_url"])[:4]
        cls.events = sorted((row for row in rows if row["new_acquisition_required"]
                             and row["dependency_class"] == "FISCAL_EVENT_FILING"),
                            key=lambda row: row["source_url"])[:2]
        assert len(cls.annual) == 4 and len(cls.events) == 2
        scope = {"purposes": ["ISSUE47_HISTORICAL_SOURCE_DEPENDENCY"],
                 "company_ids": [_SCRIPTED_COMPANY],
                 "dependency_classes": ["ACCESSION_INSTANCE_DISCOVERY", "FISCAL_EVENT_FILING"],
                 "earliest_report_end": "2021-12-31", "latest_report_end": "2026-01-31"}
        scope["grants"] = [_whole_envelope(scope)]
        cls.allowance = {"requirement_id": "issue_47_v1", "budget_root": str(cls.root),
                         "delegation_url": cls.URL, "delegation_body_sha256": "a" * 64,
                         "delegation_record_path": APPROVAL_RECORD_PATH,
                         "maximum_additional_provider_paid_sec_calls": [0, 0, 5],
                         "scope": scope}
        cls.granted = cls.base / "granted"
        (cls.granted / "config").mkdir(parents=True)
        (cls.granted / POLICY_PATH).write_text(json.dumps(
            RESUME_MODULE._expected_approval(cls.allowance)), encoding="utf-8")
        started = SESSION_MODULE.start_ledger(allowance=cls.allowance, reader=cls._reader([]),
                                              checkout=cls.checkout)
        cls.start_record = strict_json_file(path=Path(started["start_record"]))
        cls.next_id = 5950000000
        cls.start_marker = cls._comment(SESSION_MODULE.marker_comment_body(cls.start_record))
        with cls._live():
            session = cls._session()
            with patch.object(SESSION_MODULE, "declared_frame",
                              lambda **kwargs: cls._frame(cls.annual[:2])), \
                    patch.object(sec_http, "urlopen",
                                 lambda request, timeout: _FakeResponse(BODY, 200)):
                session.capture_pending(company_id=_SCRIPTED_COMPANY)
            EXPORT_MODULE.export_acquisition(ledger_root=cls.root,
                                             out_dir=cls.checkout / "evidence/issue47_acquired",
                                             policy_root=cls.granted)
        cls.exported_claims = (cls.root / "claims.jsonl").read_bytes()
        cls._lose()

    @classmethod
    def _lose(cls):
        """What the snapshot restore left: nothing of the ledger on the host."""
        shutil.rmtree(cls.root, ignore_errors=True)
        for path in (SESSION_LEDGER.anchor_path(cls.root), SESSION_LEDGER.mirror_path(cls.root),
                     SESSION_MODULE.start_record_path(cls.root),
                     SESSION_MODULE.resume_chain_path(cls.root)):
            path.unlink(missing_ok=True)

    @classmethod
    def _frame(cls, rows):
        return {"requirements": copy.deepcopy(rows), "company_id": _SCRIPTED_COMPANY,
                "target_report_dates": ["2021-12-31", "2022-12-31", "2023-12-31",
                                        "2024-12-31", "2025-12-31"]}

    @classmethod
    def _live(cls):
        """No network, and the checkpoint journal redirected away from the real one."""
        import contextlib
        stack = contextlib.ExitStack()
        stack.enter_context(patch("vnext.continuous_sec_acquisition._journal",
                                  lambda: cls.journal))
        stack.enter_context(patch.object(socket.socket, "connect",
                                         side_effect=AssertionError("a socket was opened")))
        return stack

    @classmethod
    def _session(cls):
        ledger = SESSION_MODULE._allowance_ledger(allowance=cls.allowance, root=cls.root, live=True)
        return SESSION_MODULE.HistoricalSecSession(factory=SESSION_MODULE._FACTORY,
                                                   allowance=cls.allowance, ledger=ledger)

    @classmethod
    def _comment(cls, body, *, edited=False, when="2026-09-29T01:00:00Z"):
        cls.next_id += 1
        return {"id": cls.next_id,
                "html_url": "https://github.com/wlvh/SEC_metrics/issues/47#issuecomment-"
                            + str(cls.next_id),
                "issue_url": "https://api.github.com/repos/wlvh/SEC_metrics/issues/47",
                "user": {"login": "wlvh", "id": 30534800, "type": "User"},
                "author_association": "OWNER", "created_at": when,
                "updated_at": "2026-09-29T23:00:00Z" if edited else when, "body": body}

    @staticmethod
    def _reader(comments):
        def read(path):
            page = int(path.rsplit("page=", 1)[1])
            return copy.deepcopy(comments if page == 1 else [])
        return read

    def _index(self, checkout=None):
        path = (checkout or self.checkout) / "evidence/issue47_acquired" / EXPORT_MODULE.INDEX_NAME
        return path.read_bytes() if path.is_file() else b""

    def _resume(self, comments, *, frame=None, companies=(_SCRIPTED_COMPANY,), checkout=None,
                branch_index=None):
        # The branch's tip carries what the checkout carries unless a case says
        # otherwise; the CLI reads it from the fetched upstream.
        with self._live(), patch.object(RESUME_MODULE, "declared_frame",
                                        lambda **kwargs: self._frame(
                                            self.events if frame is None else frame)):
            return RESUME_MODULE.resume_ledger(
                allowance=self.allowance, reader=self._reader(comments),
                checkout=checkout or self.checkout, in_flight_company_ids=list(companies),
                decision=dict(self.DECISION),
                branch_export_index=(self._index(checkout) if branch_index is None
                                     else branch_index),
                branch_tip_commit="0" * 40)

    def _require(self, comments, *, branch_index=None):
        return SESSION_MODULE.require_published_start(
            allowance=self.allowance, reader=self._reader(comments), checkout=self.checkout,
            branch_export_index=self._index() if branch_index is None else branch_index)

    def _export(self):
        with self._live():
            return EXPORT_MODULE.export_acquisition(
                ledger_root=self.root, out_dir=self.checkout / "evidence/issue47_acquired",
                policy_root=self.granted)

    def test_a_lost_host_resumes_the_exported_ledger_and_its_count_carries_the_reserve(self):
        import sec_http
        self.addCleanup(self._lose)
        export = self.checkout / "evidence/issue47_acquired"
        before_export = {path.name: path.read_bytes() for path in export.iterdir()}

        def put_the_export_back():
            for path in export.iterdir():
                if path.name not in before_export:
                    path.unlink()
            for name, data in before_export.items():
                (export / name).write_bytes(data)

        self.addCleanup(put_the_export_back)
        resumed = self._resume([self.start_marker])
        self.assertEqual("LEDGER_RESUMED", resumed["status"])
        self.assertEqual(2, resumed["reserve"]["reserve_sec_calls"],
                         "both due event rows are charged: the lost host could have sent them")
        # Exactly the exported ledger: the same claim log byte for byte, and
        # its copy and anchor beside the root.
        self.assertEqual(self.exported_claims, (self.root / "claims.jsonl").read_bytes())
        self.assertEqual(self.exported_claims, SESSION_LEDGER.mirror_path(self.root).read_bytes())
        self.assertEqual(2, len(list((self.root / "calls").iterdir())))
        chain = RESUME_MODULE.local_chain(self.root)
        self.assertEqual(1, len(chain))
        self.assertNotIn(chain[-1]["instance_nonce"], resumed["marker_comment_body"],
                         "the random number stays on the host")
        resume_marker = self._comment(resumed["marker_comment_body"], when="2026-09-29T13:00:00Z")
        # Until the resume is on GitHub, nothing may be requested.
        with self.assertRaises(HistoricalSessionError) as caught:
            self._require([self.start_marker])
        self.assertIn("ISSUE_47_SEC_LEDGER_RESUME_NOT_PUBLISHED", str(caught.exception))
        # ... nor until the branch's export carries the resume: a second loss
        # before that would find it only on the issue.
        with self.assertRaises(HistoricalSessionError) as caught:
            self._require([self.start_marker, resume_marker])
        self.assertIn("ISSUE_47_SEC_LEDGER_RESUME_NOT_EXPORTED", str(caught.exception))
        self.assertEqual("EXPORTED", self._export()["status"])
        verified = self._require([self.start_marker, resume_marker])
        self.assertEqual(2, verified["reserve_sec_calls"])
        # A checkout that is not the branch's tip is refused: a snapshot restore
        # can take the ledger and the checkout back together.
        with self.assertRaises(HistoricalSessionError) as caught:
            self._require([self.start_marker, resume_marker], branch_index=b"{}")
        self.assertIn("ISSUE_47_SEC_LEDGER_CHECKOUT_IS_NOT_THE_BRANCH_S_EXPORT",
                      str(caught.exception))
        session = self._session()
        with self._live():
            self.assertEqual([0, 0, 4], session.ledger.snapshot()["counts"],
                             "two exported slots and a reserve of two")
            # The cap applies to slots plus the reserve: one more request fits
            # under five, the next is refused before its socket.
            with patch.object(SESSION_MODULE, "declared_frame",
                              lambda **kwargs: self._frame(self.annual[2:])), \
                    patch.object(sec_http, "urlopen",
                                 lambda request, timeout: _FakeResponse(BODY, 200)):
                result = session.capture_pending(company_id=_SCRIPTED_COMPANY)
            self.assertEqual(1, len(result["captured"]))
            self.assertIn("ISSUE_47_CUMULATIVE_LIMIT_REACHED", result["stop"])
            self.assertEqual([0, 0, 5], session.ledger.snapshot()["counts"])
            # The export carries the resume, as its public view only.
            exported = EXPORT_MODULE.export_acquisition(ledger_root=self.root, out_dir=export,
                                                        policy_root=self.granted)
        self.assertEqual("EXPORTED", exported["status"])
        index = strict_json_file(path=export / EXPORT_MODULE.INDEX_NAME)
        self.assertIn(EXPORT_MODULE.RESUME_MEMBER, index["state_archive"]["members"])
        nonce = chain[-1]["instance_nonce"].encode()
        for path in export.iterdir():
            self.assertNotIn(nonce, path.read_bytes(), path.name)
        # A resume the chain beside the root no longer matches is refused.
        chain_path = SESSION_MODULE.resume_chain_path(self.root)
        original = chain_path.read_bytes()
        cheaper = copy.deepcopy(chain)
        cheaper[-1]["lost_segment"]["reserve_sec_calls"] = 0
        chain_path.write_bytes(RESUME_MODULE._chain_bytes(cheaper))
        with self.assertRaises(HistoricalSessionError) as caught:
            self._require([self.start_marker, resume_marker])
        self.assertIn("ISSUE_47_SEC_LEDGER_RESUMED_ELSEWHERE", str(caught.exception))
        chain_path.write_bytes(original)
        self._require([self.start_marker, resume_marker])
        # Without the chain the ledger is neither started nor resumed here: the
        # issue shows a resume of it, so the start path is fenced too.
        chain_path.unlink()
        with self.assertRaises(HistoricalSessionError) as caught:
            self._require([self.start_marker, resume_marker])
        self.assertIn("ISSUE_47_SEC_LEDGER_RESUMED_ELSEWHERE", str(caught.exception))
        # ... and a LIVE ledger with no record of how it began is not exported.
        with self._live():
            with self.assertRaises(HistoricalAcquisitionError) as caught:
                EXPORT_MODULE.export_acquisition(ledger_root=self.root, out_dir=export,
                                                 policy_root=self.granted)
        self.assertIn("ISSUE_47_EXPORT_LIVE_LEDGER_HAS_NO_START_OR_RESUME", str(caught.exception))
        # Nor can one that began from a start replace an export that carries a
        # resume (constructed: a start record beside a resumed root).
        start_path = SESSION_MODULE.start_record_path(self.root)
        start_path.write_bytes(canonical_json_bytes(value=self.start_record))
        with self._live():
            with self.assertRaises(HistoricalAcquisitionError) as caught:
                EXPORT_MODULE.export_acquisition(ledger_root=self.root, out_dir=export,
                                                 policy_root=self.granted)
        self.assertIn("ISSUE_47_EXPORT_WOULD_DROP_A_RESUME", str(caught.exception))
        start_path.unlink()
        chain_path.write_bytes(original)
        # Lost again: the second resume carries the first one's charge forward
        # and links to it.
        self._lose()
        with self.assertRaises(HistoricalSessionError) as caught:
            self._resume([self.start_marker])
        self.assertIn("ISSUE_47_SEC_LEDGER_RESUMED_SINCE_THE_EXPORT", str(caught.exception))
        second = self._resume([self.start_marker, resume_marker])
        again = RESUME_MODULE.local_chain(self.root)
        self.assertEqual(2, len(again))
        self.assertEqual(SESSION_MODULE.resume_view(chain[-1]), again[0])
        self.assertEqual(again[0]["resume_record_sha256"], again[1]["previous_resume_sha256"])
        second_marker = self._comment(second["marker_comment_body"], when="2026-09-29T14:00:00Z")
        self._export()
        verified = self._require([self.start_marker, resume_marker, second_marker])
        self.assertEqual(2 + second["reserve"]["reserve_sec_calls"], verified["reserve_sec_calls"])
        with self._live():
            self.assertEqual(3 + verified["reserve_sec_calls"],
                             self._session().ledger.snapshot()["counts"][2])

    def test_a_host_that_kept_its_start_or_its_root_does_not_resume(self):
        self.addCleanup(self._lose)
        path = SESSION_MODULE.start_record_path(self.root)
        path.write_bytes(canonical_json_bytes(value=self.start_record))
        with self.assertRaises(HistoricalSessionError) as caught:
            self._resume([self.start_marker])
        self.assertIn("ISSUE_47_SEC_LEDGER_RESUME_BESIDE_A_START_RECORD", str(caught.exception))
        path.unlink()
        self.root.mkdir()
        (self.root / "binding.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(HistoricalSessionError) as caught:
            self._resume([self.start_marker])
        self.assertIn("ISSUE_47_SEC_LEDGER_RESUME_ROOT_NOT_EMPTY", str(caught.exception))

    def test_a_resume_needs_this_approval_s_export(self):
        self.addCleanup(self._lose)
        empty = self.base / "empty-checkout"
        empty.mkdir(exist_ok=True)
        with self.assertRaises(HistoricalSessionError) as caught:
            self._resume([self.start_marker], checkout=empty)
        self.assertIn("ISSUE_47_SEC_LEDGER_NOTHING_TO_RESUME", str(caught.exception))
        other = self.base / "other-checkout"
        shutil.copytree(self.checkout, other, dirs_exist_ok=True)
        self.addCleanup(shutil.rmtree, other, ignore_errors=True)
        index_path = other / "evidence/issue47_acquired" / EXPORT_MODULE.INDEX_NAME
        index = strict_json_file(path=index_path)
        body = {key: value for key, value in index.items() if key != "export_id"}
        body["approval"] = {**body["approval"], "budget_root": str(self.base / "elsewhere")}
        index_path.write_bytes(canonical_json_bytes(value={**body,
                                                           "export_id": content_hash(value=body)}))
        with self.assertRaises(HistoricalSessionError) as caught:
            self._resume([self.start_marker], checkout=other)
        self.assertIn("ISSUE_47_SEC_LEDGER_RESUME_EXPORT_IS_FOR_ANOTHER_APPROVAL",
                      str(caught.exception))

    def test_a_resume_charges_under_the_extension_the_export_was_spent_under(self):
        """An export naming an extension resumes only under that extension, or it under-charges."""
        self.addCleanup(self._lose)
        other = self.base / "extension-checkout"
        shutil.copytree(self.checkout, other, dirs_exist_ok=True)
        self.addCleanup(shutil.rmtree, other, ignore_errors=True)
        index_path = other / "evidence/issue47_acquired" / EXPORT_MODULE.INDEX_NAME
        index = strict_json_file(path=index_path)
        named = {"extension_ordinal": 1, "delegation_url": _EXTENSION_URL,
                 "delegation_body_sha256": "b" * 64,
                 "maximum_additional_provider_paid_sec_calls": [0, 0, 7]}
        body = {key: value for key, value in index.items() if key != "export_id"}
        body["extension"] = {**named, "delegation_record_path": "docs/extension.json",
                             "extends": {}}
        index_path.write_bytes(canonical_json_bytes(value={**body,
                                                           "export_id": content_hash(value=body)}))
        with self.assertRaises(HistoricalSessionError) as caught:
            self._resume([], checkout=other)
        self.assertIn("RESUME_EXPORT_WAS_SPENT_UNDER_AN_EXTENSION_THIS_ALLOWANCE_LACKS",
                      str(caught.exception))
        # Under the same extension the check passes, and the resume goes on to
        # the next thing it needs: the start marker, absent here.
        held = self.allowance
        self.allowance = {**held, "extension": {**named, "ledger_state": {},
                                                "reclaim": [],
                                                "provenance_verified_against_github": True}}
        try:
            with self.assertRaises(HistoricalSessionError) as caught:
                self._resume([], checkout=other)
        finally:
            self.allowance = held
        self.assertIn("RESUME_WITHOUT_A_PUBLISHED_START", str(caught.exception))

    def test_a_resume_charged_under_an_extension_holds_only_under_it(self):
        self.addCleanup(self._lose)
        record = {"record_type": RESUME_MODULE.RESUME_TYPE, "requirement_id": "issue_47_v1",
                  "delegation_url": self.URL, "delegation_body_sha256": "a" * 64,
                  "budget_root": str(self.root), "instance_nonce": "0" * 32,
                  "extension": {"extension_ordinal": 1, "delegation_url": _EXTENSION_URL,
                                "delegation_body_sha256": "b" * 64,
                                "maximum_additional_provider_paid_sec_calls": [0, 0, 7]}}
        chain = SESSION_MODULE.resume_chain_path(self.root)
        chain.write_bytes(canonical_json_bytes(value=record).rstrip(b"\n") + b"\n")
        with self.assertRaises(HistoricalSessionError) as caught:
            RESUME_MODULE.require_published_resume(allowance=self.allowance,
                                                   reader=self._reader([]),
                                                   checkout=self.checkout)
        self.assertIn("RESUME_WAS_CHARGED_UNDER_ANOTHER_EXTENSION", str(caught.exception))

    def test_a_resume_needs_the_approval_s_earliest_start_marker_unedited(self):
        self.addCleanup(self._lose)
        with self.assertRaises(HistoricalSessionError) as caught:
            self._resume([])
        self.assertIn("ISSUE_47_SEC_LEDGER_RESUME_WITHOUT_A_PUBLISHED_START", str(caught.exception))
        edited = self._comment(self.start_marker["body"], edited=True)
        with self.assertRaises(HistoricalSessionError) as caught:
            self._resume([edited])
        self.assertIn("ISSUE_47_SEC_LEDGER_START_MARKER_EDITED", str(caught.exception))
        self.assertFalse(self.root.exists(), "a refused resume rebuilds nothing")

    def test_a_decision_and_the_in_flight_companies_are_required(self):
        self.addCleanup(self._lose)
        with self.assertRaises(HistoricalSessionError) as caught:
            self._resume([self.start_marker], companies=())
        self.assertIn("ISSUE_47_SEC_LEDGER_RESUME_IN_FLIGHT_COMPANIES_INVALID", str(caught.exception))
        with self.assertRaises(HistoricalSessionError) as caught:
            RESUME_MODULE.resume_ledger(allowance=self.allowance,
                                        reader=self._reader([self.start_marker]),
                                        checkout=self.checkout,
                                        in_flight_company_ids=[_SCRIPTED_COMPANY],
                                        decision={"text": " ", "received_at": "x"},
                                        branch_export_index=self._index(),
                                        branch_tip_commit="0" * 40)
        self.assertIn("ISSUE_47_SEC_LEDGER_RESUME_DECISION_MISSING", str(caught.exception))

    def _resumed_and_exported(self):
        resumed = self._resume([self.start_marker])
        marker = self._comment(resumed["marker_comment_body"], when="2026-09-29T13:00:00Z")
        self._export()
        return resumed, marker

    def test_a_running_session_stops_when_a_resume_is_published_elsewhere(self):
        """An independent review kept a resumed session claiming after another resume: it went on.

        The live path's check runs again before every pass. A second resume
        marker for this approval, from a host that also believed this one
        lost, makes the chain here not the issue's, and the pass stops before
        planning, with nothing claimed.
        """
        import sec_http
        self.addCleanup(self._lose)
        export = self.checkout / "evidence/issue47_acquired"
        before = {path.name: path.read_bytes() for path in export.iterdir()}
        self.addCleanup(lambda: ([p.unlink() for p in export.iterdir() if p.name not in before],
                                 [(export / n).write_bytes(d) for n, d in before.items()]))
        resumed, marker = self._resumed_and_exported()
        comments = [self.start_marker, marker]
        session = self._session()
        session.ledger.pin_resume_reserve(self._require(comments)["reserve_sec_calls"])
        session.published_check = lambda: self._require(comments)
        # Another host's resume of the same export: a different record.
        other = {**resumed["record"], "resume_record_sha256": "f" * 64}
        elsewhere = self._comment(RESUME_MODULE.MARKER_TITLE + "\n\n```json\n"
                                  + json.dumps(other, indent=1, sort_keys=True) + "\n```\n",
                                  when="2026-09-29T15:00:00Z")
        comments.append(elsewhere)
        with self._live(), patch.object(SESSION_MODULE, "declared_frame",
                                        lambda **kwargs: self._frame(self.annual[2:])), \
                patch.object(sec_http, "urlopen",
                             lambda request, timeout: _FakeResponse(BODY, 200)):
            result = session.capture_pending(company_id=_SCRIPTED_COMPANY)
        self.assertEqual([], result["captured"])
        self.assertIn("LIVE_PATH_REFUSED:ISSUE_47_SEC_LEDGER_RESUMED_ELSEWHERE", result["stop"])
        with self._live():
            self.assertEqual([0, 0, 4], session.ledger.snapshot()["counts"])

    def test_the_resume_guards_the_review_found_untested(self):
        """Each guard, with the one thing changed it guards."""
        self.addCleanup(self._lose)
        export = self.checkout / "evidence/issue47_acquired"
        before = {path.name: path.read_bytes() for path in export.iterdir()}
        self.addCleanup(lambda: ([p.unlink() for p in export.iterdir() if p.name not in before],
                                 [(export / n).write_bytes(d) for n, d in before.items()]))
        resumed, marker = self._resumed_and_exported()
        comments = [self.start_marker, marker]
        self._require(comments)
        chain_path = SESSION_MODULE.resume_chain_path(self.root)
        original = chain_path.read_bytes()
        with self.subTest("a resume of another start"):
            chain = RESUME_MODULE.local_chain(self.root)
            chain[-1]["resumes_start_record_sha256"] = "f" * 64
            chain_path.write_bytes(RESUME_MODULE._chain_bytes(chain))
            with self.assertRaises(HistoricalSessionError) as caught:
                self._require(comments)
            self.assertIn("ISSUE_47_SEC_LEDGER_RESUME_IS_OF_ANOTHER_START", str(caught.exception))
            chain_path.write_bytes(original)
        with self.subTest("a claim log that is not what was restored"):
            log, mirror = self.root / "claims.jsonl", SESSION_LEDGER.mirror_path(self.root)
            held = log.read_bytes()
            changed = held.replace(b'"ordinal":1', b'"ordinal":7', 1)
            self.assertNotEqual(held, changed)
            log.write_bytes(changed)
            mirror.write_bytes(changed)
            with self.assertRaises(HistoricalSessionError) as caught:
                self._require(comments)
            self.assertIn("RESUMED_LEDGER_IS_NOT_WHAT_WAS_RESTORED", str(caught.exception))
            log.write_bytes(held)
            mirror.write_bytes(held)
        with self.subTest("an edited resume marker"):
            edited = self._comment(marker["body"], edited=True, when="2026-09-29T13:00:00Z")
            with self.assertRaises(HistoricalSessionError) as caught:
                self._require([self.start_marker, edited])
            self.assertIn("ISSUE_47_SEC_LEDGER_RESUME_MARKER_EDITED", str(caught.exception))
        with self.subTest("the same marker twice, and a comment quoting it"):
            again = self._comment(marker["body"], when="2026-09-29T13:05:00Z")
            quoted = self._comment("Status: the resume is published.\n\n"
                                   + marker["body"][marker["body"].index("```json"):],
                                   when="2026-09-29T13:10:00Z")
            self.assertEqual(2, self._require([self.start_marker, marker, again,
                                               quoted])["reserve_sec_calls"])
        with self.subTest("a comment quoting a record no marker carries"):
            # A quote of the published record collapses into it by digest, so it
            # cannot show that only a marker counts. A draft that was never
            # posted as a marker has its own digest: counted, it would be a
            # second resume on the issue and stop every live start.
            block = marker["body"].split("```json\n", 1)[1].split("\n```", 1)[0]
            draft = json.loads(block)
            draft["resume_record_sha256"] = "e" * 64
            status = self._comment("Status: a draft of the resume, never posted as a marker.\n\n"
                                   "```json\n" + json.dumps(draft, indent=1, sort_keys=True)
                                   + "\n```\n", when="2026-09-29T13:15:00Z")
            self.assertEqual(2, self._require([self.start_marker, marker,
                                               status])["reserve_sec_calls"])
        with self.subTest("a second resume on the same host"):
            with self.assertRaises(HistoricalSessionError) as caught:
                self._resume(comments)
            self.assertIn("ISSUE_47_SEC_LEDGER_ALREADY_RESUMED_HERE", str(caught.exception))

    def test_a_resume_already_running_or_left_over_is_not_disturbed(self):
        """A second resume is refused before it touches the first one's staging directory."""
        self.addCleanup(self._lose)
        staging = self.root.parent / ("." + self.root.name + ".resuming")
        sentinel = self.root.parent / ("." + self.root.name + ".resuming.lock")
        staging.mkdir()
        (staging / "work").write_text("the first resume's", encoding="utf-8")
        sentinel.write_text("", encoding="utf-8")
        self.addCleanup(shutil.rmtree, staging, ignore_errors=True)
        self.addCleanup(sentinel.unlink, missing_ok=True)
        with self.assertRaises(HistoricalSessionError) as caught:
            self._resume([self.start_marker])
        self.assertIn("ISSUE_47_SEC_LEDGER_RESUME_IN_PROGRESS_OR_LEFT_OVER", str(caught.exception))
        self.assertEqual("the first resume's", (staging / "work").read_text(encoding="utf-8"))
        self.assertTrue(sentinel.exists())
        self.assertFalse(self.root.exists())

    def test_a_resume_is_from_the_export_the_branch_carries_now(self):
        """A loss can take the checkout back with it; an older export would be charged from.

        The one this was written for reset the checkout to a commit hours old.
        An independent review resumed from such a checkout: the older export
        restored, the reserve computed from it, and the claims the branch
        showed after it counted nowhere.
        """
        self.addCleanup(self._lose)
        newer = self._index().replace(b'"exported_row_count"', b'"exported_row_count" ', 1)
        self.assertNotEqual(self._index(), newer)
        for branch in (newer, b"", self._index().decode("utf-8")):
            with self.subTest(branch=repr(branch)[:20]):
                with self.assertRaises(HistoricalSessionError) as caught:
                    self._resume([self.start_marker], branch_index=branch)
                self.assertIn("ISSUE_47_SEC_LEDGER_RESUME_CHECKOUT_IS_NOT_THE_BRANCH_S_EXPORT",
                              str(caught.exception))
                self.assertFalse(self.root.exists(), "a refused resume rebuilds nothing")

    def test_the_resume_charge_cannot_shrink_while_a_session_holds_the_ledger(self):
        """An independent review deleted the chain mid-session: the count fell and captures ran past the cap.

        The live path checks the chain against the issue before the session
        exists; the ledger it builds is held to the charge that check verified,
        and a snapshot that reads another refuses.
        """
        self.addCleanup(self._lose)
        export = self.checkout / "evidence/issue47_acquired"
        before = {path.name: path.read_bytes() for path in export.iterdir()}
        self.addCleanup(lambda: ([p.unlink() for p in export.iterdir() if p.name not in before],
                                 [(export / n).write_bytes(d) for n, d in before.items()]))
        _, marker = self._resumed_and_exported()
        published = self._require([self.start_marker, marker])
        ledger = SESSION_MODULE.live_ledger(allowance=self.allowance, published=published)
        chain_path = SESSION_MODULE.resume_chain_path(self.root)
        original = chain_path.read_bytes()
        with self._live():
            self.assertEqual([0, 0, 4], ledger.snapshot()["counts"])
            for label, change in (("deleted", lambda: chain_path.unlink()),
                                  ("emptied", lambda: chain_path.write_bytes(b""))):
                with self.subTest(label):
                    change()
                    with self.assertRaises(HistoricalSessionError) as caught:
                        ledger.snapshot()
                    self.assertIn("ISSUE_47_LEDGER_RESUME_RESERVE_CHANGED", str(caught.exception))
                    chain_path.write_bytes(original)
            self.assertEqual([0, 0, 4], ledger.snapshot()["counts"])
        # A pin that is not what the chain charges is refused where it is made.
        for wrong in (0, 3, -1, "2", None):
            with self.subTest(pin=wrong):
                with self.assertRaises(HistoricalSessionError):
                    SESSION_MODULE.live_ledger(allowance=self.allowance,
                                               published={"reserve_sec_calls": wrong})

    def test_a_host_that_still_holds_its_start_may_not_spend_after_a_resume(self):
        """An independent review kept the first host alive beside a published resume: it passed.

        A host that was only unreachable still holds its start record and its
        ledger. Once the issue shows a resume of this approval, the ledger it
        started was declared lost, and it may not spend the same allowance a
        second time.
        """
        self.addCleanup(self._lose)
        resumed = self._resume([self.start_marker])
        marker = self._comment(resumed["marker_comment_body"], when="2026-09-29T13:00:00Z")
        self._lose()
        start_path = SESSION_MODULE.start_record_path(self.root)
        start_path.write_bytes(canonical_json_bytes(value=self.start_record))
        with self.assertRaises(HistoricalSessionError) as caught:
            self._require([self.start_marker, marker])
        self.assertIn("ISSUE_47_SEC_LEDGER_RESUMED_ELSEWHERE", str(caught.exception))
        # Without the resume on the issue this host is refused for another
        # reason - its ledger is behind the branch's export - not this one.
        with self.assertRaises(HistoricalSessionError) as caught:
            self._require([self.start_marker])
        self.assertNotIn("RESUMED_ELSEWHERE", str(caught.exception))

    def test_the_reserve_is_the_due_rows_and_refuses_where_a_capture_could_open_more(self):
        """What one invocation could have claimed from the exported state, or a refusal.

        A URL is claimed once and nothing is retried, so the admitted due rows
        bound what the lost host could send - unless capturing one can make
        more rows declarable, as an annual primary or an index does; then the
        rows due now are not a bound, and the reserve is refused.
        """
        claimed = {self.events[0]["source_url"]}
        outside = {**copy.deepcopy(self.events[1]), "dependency_class": "COMPANYFACTS"}
        cases = (("events", self.events, set(), 2),
                 ("one already claimed", self.events, claimed, 1),
                 ("one outside every grant", [self.events[0], outside], set(), 1))
        for label, rows, already, expected in cases:
            with self.subTest(label):
                with patch.object(RESUME_MODULE, "declared_frame",
                                  lambda **kwargs: self._frame(rows)):
                    reserve = RESUME_MODULE.lost_segment_reserve(
                        data_root=ROOT, claimed_urls=already, allowance=self.allowance,
                        company_ids=[_SCRIPTED_COMPANY])
                self.assertEqual(expected, reserve["reserve_sec_calls"])
        with patch.object(RESUME_MODULE, "declared_frame",
                          lambda **kwargs: self._frame([*self.events, self.annual[3]])):
            with self.assertRaises(HistoricalSessionError) as caught:
                RESUME_MODULE.lost_segment_reserve(data_root=ROOT, claimed_urls=set(),
                                                   allowance=self.allowance,
                                                   company_ids=[_SCRIPTED_COMPANY])
        self.assertIn("ISSUE_47_SEC_LEDGER_RESUME_RESERVE_UNBOUNDED", str(caught.exception))


from vnext import historical_sec_extension as EXTENSION_MODULE  # noqa: E402

# A branch tip carrying no extension files, as every tip does until one is registered.
_NO_EXTENSION = {path: None for path in EXTENSION_MODULE.EXTENSION_FILES}
from vnext.historical_sec_extension import (EXTENSION_POLICY_PATH,  # noqa: E402
                                            EXTENSION_TYPE, HistoricalExtensionError,
                                            acquisition_extension, extended_allowance)

_EXTENSION_URL = "https://github.com/wlvh/SEC_metrics/issues/47#issuecomment-2"


def _chain_views(root):
    """The resume chain beside ``root`` as an export carries it: each record's public view."""
    path = SESSION_MODULE.resume_chain_path(Path(root))
    if not path.exists():
        return b"", 0
    records = RESUME_MODULE.local_chain(Path(root))
    views = b"".join(canonical_json_bytes(
        value=SESSION_MODULE.resume_view(record) if "instance_nonce" in record else record
    ).rstrip(b"\n") + b"\n" for record in records)
    return views, sum(record["lost_segment"]["reserve_sec_calls"] for record in records)


def _ledger_state(root):
    """The state an extension continues from, read from a ledger's own claim log and chain."""
    claims = (Path(root) / "claims.jsonl").read_bytes()
    count = claims.count(b"\n")
    views, reserve = _chain_views(root)
    return {"export_id": "sha256:" + "e" * 64,
            "claims": {"sha256": hashlib.sha256(claims).hexdigest(), "size": len(claims)},
            "claim_count": count,
            "resumes": {"sha256": hashlib.sha256(views).hexdigest(), "size": len(views)},
            "cumulative": [0, 0, count + reserve]}


def _resume_record(root, *, restored_size, reserve, extension=None, previous=None):
    """A resume record of the ledger at ``root``, in the shape the chain holds."""
    record = {"record_type": RESUME_MODULE.RESUME_TYPE, "requirement_id": "issue_47_v1",
              "budget_root": str(Path(root)), "previous_resume_sha256": previous,
              "restored_export": {"claims": {"sha256": "c" * 64, "size": restored_size}},
              "lost_segment": {"reserve_sec_calls": reserve},
              "instance_nonce": os.urandom(16).hex()}
    if extension is not None:
        record["extension"] = extension
    return record


def _write_chain(root, records):
    """Write a chain as a host holds it: earlier records as views, its own record last."""
    lines = [SESSION_MODULE.resume_view(record) for record in records[:-1]] + records[-1:]
    SESSION_MODULE.resume_chain_path(Path(root)).write_bytes(b"".join(
        canonical_json_bytes(value=line).rstrip(b"\n") + b"\n" for line in lines))


def _recorded_scope(classes=("ACCESSION_INSTANCE_DISCOVERY", "ANNUAL_PERIOD_IDENTITY",
                             "COMPANYFACTS", "FISCAL_EVENT_FILING",
                             "GOVERNANCE_DISCLOSURE_FILING", "SUBMISSIONS_HISTORY",
                             "SUBMISSIONS_INDEX")):
    """The recorded session's own default scope, narrowed to ``classes``."""
    from datetime import date
    scope = {"purposes": ["historical_five_year_source_acquisition"],
             "company_ids": [_SCRIPTED_COMPANY], "dependency_classes": list(classes),
             "earliest_report_end": date.min.isoformat(),
             "latest_report_end": date.max.isoformat()}
    scope["grants"] = [_whole_envelope(scope)]
    return scope


def _test_extension(root, *, limits=(0, 0, 1), reclaim=(), scope=None, state=None):
    """An extension in the verified shape ``acquisition_extension`` returns, for ledger cases."""
    return {"extension_ordinal": 1, "delegation_url": _EXTENSION_URL,
            "delegation_body_sha256": "b" * 64,
            "extends": {"delegation_url": None, "delegation_body_sha256": None,
                        "ledger_state": state or _ledger_state(root)},
            "maximum_additional_provider_paid_sec_calls": list(limits),
            "scope": scope or _recorded_scope(), "reclaim": [dict(entry) for entry in reclaim],
            # Recorded: never read back from GitHub, which only the live
            # ledger requires.
            "approved_extension": {"provenance_verified_against_github": False}}


class AnExtensionRaisesTheCapOnlyForTheLedgerItNames(unittest.TestCase):
    """The owner's extension continues one ledger, and only that one, by what it adds.

    The first approval was spent to its cap. An extension could have been a
    second ledger, but the frozen checkpoint covers every row past the
    baseline, so a second ledger could not register what it fetched without
    re-counting the first. So the same ledger continues, and these cases hold
    the two things that could go wrong without failing: the cap raised for a
    ledger the extension does not name, and a raise larger than approved.
    """

    def test_the_cap_rises_by_exactly_what_the_extension_adds(self):
        rows = [_scripted_row(url, "ANNUAL_PERIOD_IDENTITY") for url in _OTHER]
        scripted = _ScriptedPasses(self, frames=[rows], limits=(0, 0, 1))
        base = scripted.session()
        summary = base.acquire(company_ids=[_SCRIPTED_COMPANY])
        self.assertEqual(_OTHER[:1], scripted.fetched)
        self.assertTrue(summary["stop"]["reason"].startswith("ISSUE_47_CUMULATIVE_LIMIT_REACHED"))
        extended = recorded_historical_session(
            root=scripted.root, response=BODY, limits=(0, 0, 1),
            extension=_test_extension(scripted.root, limits=(0, 0, 1)))
        self.assertEqual([0, 0, 2], extended.ledger.snapshot()["limits"])
        summary = extended.acquire(company_ids=[_SCRIPTED_COMPANY])
        self.assertEqual(_OTHER[:2], scripted.fetched, "one more, and not the third")
        self.assertTrue(summary["stop"]["reason"].startswith("ISSUE_47_CUMULATIVE_LIMIT_REACHED"))
        self.assertEqual([0, 0, 2], extended.ledger.snapshot()["counts"])

    def test_an_extension_of_another_ledger_or_state_is_refused(self):
        rows = [_scripted_row(url, "ANNUAL_PERIOD_IDENTITY") for url in _OTHER[:1]]
        scripted = _ScriptedPasses(self, frames=[rows], limits=(0, 0, 1))
        scripted.session().acquire(company_ids=[_SCRIPTED_COMPANY])
        state = _ledger_state(scripted.root)
        for label, changed in (
                ("another log", {**state, "claims": {**state["claims"], "sha256": "f" * 64}}),
                ("a longer log", {**state, "claims": {**state["claims"],
                                                      "size": state["claims"]["size"] + 1}}),
                ("another count", {**state, "claim_count": state["claim_count"] + 1})):
            with self.subTest(label):
                with self.assertRaises(HistoricalSessionError) as caught:
                    recorded_historical_session(
                        root=scripted.root, response=BODY, limits=(0, 0, 1),
                        extension=_test_extension(scripted.root, state=changed))
                self.assertIn("ISSUE_47_LEDGER_IS_NOT_THE_ONE_THE_EXTENSION_EXTENDS",
                              str(caught.exception))

    def test_the_ledger_grows_past_the_state_and_the_extension_still_holds(self):
        rows = [_scripted_row(url, "ANNUAL_PERIOD_IDENTITY") for url in _OTHER]
        scripted = _ScriptedPasses(self, frames=[rows], limits=(0, 0, 1))
        scripted.session().acquire(company_ids=[_SCRIPTED_COMPANY])
        extension = _test_extension(scripted.root, limits=(0, 0, 2))
        first = recorded_historical_session(root=scripted.root, response=BODY,
                                            limits=(0, 0, 1), extension=extension)
        first.acquire(company_ids=[_SCRIPTED_COMPANY], max_captures=1)
        # The claim log now extends past the state; the extension pins again.
        later = recorded_historical_session(root=scripted.root, response=BODY,
                                            limits=(0, 0, 1), extension=extension)
        later.acquire(company_ids=[_SCRIPTED_COMPANY])
        self.assertEqual(_OTHER, scripted.fetched)
        self.assertEqual([0, 0, 3], later.ledger.snapshot()["counts"])


class TheStatedSpendingIsTheLedgerAtThatState(unittest.TestCase):
    """The spending an extension states is the ledger's at that state, resumes included.

    The state binds the resume chain as the export carried it, not the
    restored claim-log length: a resume made after the state that restored
    the stated export itself has that same length, and it must stay outside
    the stated spending (the review's N1), while one the state leaves out
    that restored an earlier log is a charge the state understates.
    """

    def _spent(self):
        rows = [_scripted_row(url, "ANNUAL_PERIOD_IDENTITY") for url in _OTHER]
        scripted = _ScriptedPasses(self, frames=[rows], limits=(0, 0, 2))
        scripted.session().acquire(company_ids=[_SCRIPTED_COMPANY])
        return scripted

    def _pin(self, scripted, state):
        return recorded_historical_session(root=scripted.root, response=BODY, limits=(0, 0, 2),
                                           extension=_test_extension(scripted.root, state=state))

    def test_a_resume_before_the_state_is_in_it_and_one_after_is_not(self):
        scripted = self._spent()
        size = len((scripted.root / "claims.jsonl").read_bytes())
        first = _resume_record(scripted.root, restored_size=size - 1, reserve=3)
        _write_chain(scripted.root, [first])
        state = _ledger_state(scripted.root)
        self.assertEqual([0, 0, 5], state["cumulative"], "two claims and a charge of three")
        # A resume after the state that restored the stated export itself.
        after = _resume_record(scripted.root, restored_size=size, reserve=4, extension={},
                               previous=SESSION_MODULE.resume_view(first)[
                                   "resume_record_sha256"])
        _write_chain(scripted.root, [first, after])
        self.assertEqual([0, 0, 3], self._pin(scripted, state).ledger._limits(),
                         "the resume after the state is outside the stated spending")

    def test_a_state_that_leaves_out_an_earlier_resume_is_refused(self):
        scripted = self._spent()
        size = len((scripted.root / "claims.jsonl").read_bytes())
        state = _ledger_state(scripted.root)
        _write_chain(scripted.root, [_resume_record(scripted.root, restored_size=size - 1,
                                                    reserve=3)])
        with self.assertRaises(HistoricalSessionError) as caught:
            self._pin(scripted, state)
        self.assertIn("ISSUE_47_EXTENSION_STATE_LEAVES_OUT_AN_EARLIER_RESUME",
                      str(caught.exception))

    def test_a_chain_that_does_not_begin_with_the_stated_one_is_refused(self):
        scripted = self._spent()
        size = len((scripted.root / "claims.jsonl").read_bytes())
        _write_chain(scripted.root, [_resume_record(scripted.root, restored_size=size - 1,
                                                    reserve=3)])
        state = _ledger_state(scripted.root)
        _write_chain(scripted.root, [_resume_record(scripted.root, restored_size=size - 1,
                                                    reserve=9)])
        with self.assertRaises(HistoricalSessionError) as caught:
            self._pin(scripted, state)
        self.assertIn("ISSUE_47_LEDGER_RESUMES_ARE_NOT_THE_ONES_THE_EXTENSION_EXTENDS",
                      str(caught.exception))

    def test_a_staged_anchor_left_by_a_crash_does_not_block_the_pin(self):
        scripted = self._spent()
        state = _ledger_state(scripted.root)
        anchor = SESSION_MODULE.extension_anchor_path(scripted.root, 1)
        (anchor.parent / (anchor.name + ".0011223344556677.tmp")).write_bytes(b"")
        self.assertEqual([0, 0, 3], self._pin(scripted, state).ledger._limits())
        self.assertTrue(anchor.is_file())
        self.assertEqual([0, 0, 3], self._pin(scripted, state).ledger._limits(),
                         "the same extension pins again")


class AnExtensionMayRequestARefreshOrReplacementOnceMore(unittest.TestCase):
    """A URL the ledger already requested is requested again only as the owner said.

    Zero automatic retries is why a claimed URL is never claimed again. The
    owner's extension names two exceptions - a saved copy the planner marks
    as disagreeing with its index, and one whose last request failed - and
    only for the classes it names, once per extension. These cases hold each
    half of that: the kind, the class, the once, and that without an
    extension nothing changed.
    """

    def _refresh(self):
        row = _scripted_row(_INDEX, "SUBMISSIONS_INDEX", consumers=["historical_catalog"])
        return {**row, "acquisition_kind": "SNAPSHOT_REFRESH"}

    def test_a_refresh_is_requested_once_more_under_the_extension_and_not_again(self):
        refresh = self._refresh()
        scripted = _ScriptedPasses(self, frames=[[refresh]])
        scripted.session().acquire(company_ids=[_SCRIPTED_COMPANY])
        self.assertEqual([_INDEX], scripted.fetched)
        # Without an extension the planner still asking changes nothing.
        summary = scripted.session().acquire(company_ids=[_SCRIPTED_COMPANY])
        self.assertEqual([_INDEX], scripted.fetched)
        self.assertEqual([_INDEX], [item["source_url"] for item in
                                    summary["companies"][_SCRIPTED_COMPANY]["already_claimed"]])
        extension = _test_extension(scripted.root, limits=(0, 0, 5), reclaim=[
            {"acquisition_kind": "SNAPSHOT_REFRESH", "dependency_classes": ["SUBMISSIONS_INDEX"]}])
        extended = recorded_historical_session(root=scripted.root, response=BODY,
                                               extension=extension)
        extended.acquire(company_ids=[_SCRIPTED_COMPANY])
        self.assertEqual([_INDEX, _INDEX], scripted.fetched, "requested once more")
        self.assertEqual([None, 1], scripted.reclaims, "and marked as the extension's")
        digests = extended.ledger.snapshot()["request_digests"]
        self.assertEqual(2, len(digests), "a re-request is not the same request")
        # Once per extension: the planner still asking is not a third request.
        again = recorded_historical_session(root=scripted.root, response=BODY,
                                            extension=extension)
        summary = again.acquire(company_ids=[_SCRIPTED_COMPANY])
        self.assertEqual([_INDEX, _INDEX], scripted.fetched)
        self.assertEqual([_INDEX], [item["source_url"] for item in
                                    summary["companies"][_SCRIPTED_COMPANY]["already_claimed"]])

    def test_only_the_kinds_and_classes_the_owner_named(self):
        refresh = self._refresh()
        failed_first = _scripted_row(_OTHER[0], "FISCAL_EVENT_FILING")
        cases = (
            ("a refresh of a class not named", [refresh], {},
             [{"acquisition_kind": "SNAPSHOT_REFRESH",
               "dependency_classes": ["SUBMISSIONS_HISTORY"]}]),
            ("a failed first acquisition, not marked as a replacement", [failed_first],
             {_OTHER[0]: "404"},
             [{"acquisition_kind": "REPLACEMENT_ACQUISITION",
               "dependency_classes": ["FISCAL_EVENT_FILING"]}]),
            ("a replacement when only refreshes are named",
             [{**failed_first, "acquisition_kind": "REPLACEMENT_ACQUISITION"}],
             {_OTHER[0]: "404"},
             [{"acquisition_kind": "SNAPSHOT_REFRESH",
               "dependency_classes": ["FISCAL_EVENT_FILING"]}]))
        for label, rows, statuses, reclaim in cases:
            with self.subTest(label):
                scripted = _ScriptedPasses(self, frames=[rows], statuses=statuses)
                scripted.session().acquire(company_ids=[_SCRIPTED_COMPANY])
                extended = recorded_historical_session(
                    root=scripted.root, response=BODY,
                    extension=_test_extension(scripted.root, limits=(0, 0, 5), reclaim=reclaim))
                extended.acquire(company_ids=[_SCRIPTED_COMPANY])
                self.assertEqual(1, len(scripted.fetched), "not requested again")

    def test_a_replacement_the_owner_named_is_requested_once_more(self):
        replacement = {**_scripted_row(_OTHER[0], "FISCAL_EVENT_FILING"),
                       "acquisition_kind": "REPLACEMENT_ACQUISITION",
                       "reason": "LATEST_SOURCE_REQUEST_FAILED: " + _OTHER[0]}
        scripted = _ScriptedPasses(self, frames=[[replacement]], statuses={_OTHER[0]: "503"})
        scripted.session().acquire(company_ids=[_SCRIPTED_COMPANY])
        scripted.statuses[_OTHER[0]] = "200"
        extended = recorded_historical_session(
            root=scripted.root, response=BODY,
            extension=_test_extension(scripted.root, limits=(0, 0, 5), reclaim=[
                {"acquisition_kind": "REPLACEMENT_ACQUISITION",
                 "dependency_classes": ["FISCAL_EVENT_FILING"]}]))
        extended.acquire(company_ids=[_SCRIPTED_COMPANY])
        self.assertEqual([_OTHER[0], _OTHER[0]], scripted.fetched)

    def test_a_replacement_is_only_for_a_copy_whose_last_request_failed(self):
        """The planner calls any unreadable copy a replacement; the owner named failed requests."""
        extension_reclaim = [{"acquisition_kind": "REPLACEMENT_ACQUISITION",
                              "dependency_classes": ["FISCAL_EVENT_FILING"]}]
        for reason, again in (("SOURCE_ATTEMPT_SELECTION_CONFLICT", False),
                              ("LATEST_SOURCE_REQUEST_FAILED: " + _OTHER[0], True)):
            with self.subTest(reason[:40]):
                row = {**_scripted_row(_OTHER[0], "FISCAL_EVENT_FILING"),
                       "acquisition_kind": "REPLACEMENT_ACQUISITION", "reason": reason}
                scripted = _ScriptedPasses(self, frames=[[row]])
                scripted.session().acquire(company_ids=[_SCRIPTED_COMPANY])
                recorded_historical_session(
                    root=scripted.root, response=BODY,
                    extension=_test_extension(scripted.root, limits=(0, 0, 5),
                                              reclaim=extension_reclaim),
                ).acquire(company_ids=[_SCRIPTED_COMPANY])
                self.assertEqual(2 if again else 1, len(scripted.fetched))

    def test_a_session_holding_other_grants_than_its_ledger_s_extension_is_refused(self):
        rows = [_scripted_row(url, "ANNUAL_PERIOD_IDENTITY") for url in _OTHER]
        scripted = _ScriptedPasses(self, frames=[rows], limits=(0, 0, 1))
        scripted.session().acquire(company_ids=[_SCRIPTED_COMPANY])
        extended = recorded_historical_session(
            root=scripted.root, response=BODY, limits=(0, 0, 1),
            extension=_test_extension(scripted.root, limits=(0, 0, 1)))
        first = {key: value for key, value in extended.allowance.items()
                 if key not in ("extension", "first_approval_scope")}
        first["scope"] = extended.allowance["first_approval_scope"]
        mixed = SESSION_MODULE.HistoricalSecSession(
            factory=SESSION_MODULE._FACTORY, ledger=extended.ledger, allowance=first,
            recorded_response=BODY)
        # acquire reports a company's refusal rather than raising it.
        summary = mixed.acquire(company_ids=[_SCRIPTED_COMPANY])
        self.assertIn("ISSUE_47_LEDGER_AND_SESSION_DISAGREE_ON_THE_EXTENSION",
                      summary["companies"][_SCRIPTED_COMPANY]["error"]["error"])
        self.assertEqual(_OTHER[:1], scripted.fetched)
        with self.assertRaises(HistoricalSessionError) as caught:
            mixed.capture(company_id=_SCRIPTED_COMPANY, url=_OTHER[1])
        self.assertIn("ISSUE_47_LEDGER_AND_SESSION_DISAGREE_ON_THE_EXTENSION",
                      str(caught.exception))

    def test_after_the_extension_requests_are_held_to_its_grants(self):
        # The first approval is spent on one row; the next frame asks for two
        # more, of which the extension grants one class.
        spent = [_scripted_row(_OTHER[2], "ANNUAL_PERIOD_IDENTITY")]
        rows = [_scripted_row(_OTHER[0], "ANNUAL_PERIOD_IDENTITY"),
                _scripted_row(_OTHER[1], "FISCAL_EVENT_FILING")]
        scripted = _ScriptedPasses(self, frames=[spent, rows], limits=(0, 0, 1))
        scripted.session().acquire(company_ids=[_SCRIPTED_COMPANY])
        self.assertEqual([_OTHER[2]], scripted.fetched)
        extended = recorded_historical_session(
            root=scripted.root, response=BODY, limits=(0, 0, 1),
            extension=_test_extension(scripted.root, limits=(0, 0, 5),
                                      scope=_recorded_scope(classes=("FISCAL_EVENT_FILING",))))
        summary = extended.acquire(company_ids=[_SCRIPTED_COMPANY])
        self.assertEqual([_OTHER[2], _OTHER[1]], scripted.fetched)
        listed = summary["companies"][_SCRIPTED_COMPANY]["outside_grants"]
        self.assertEqual([_OTHER[0]], [item["source_url"] for item in listed])

    def test_a_re_request_marker_needs_the_extension_that_makes_it(self):
        root = Path(tempfile.mkdtemp(prefix="issue47-reclaim-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        session = recorded_historical_session(root=root / "ledger", response=BODY)
        admitted = {"company_id": _SCRIPTED_COMPANY, "dependency_class": "SUBMISSIONS_INDEX",
                    "grants": ["RECORDED_TEST"], "purpose": "x"}
        with session.ledger.locked():
            with self.assertRaises(HistoricalSessionError) as caught:
                session._capture_one(company_id=_SCRIPTED_COMPANY, url=_INDEX,
                                     dependency=self._refresh(), admitted=admitted, reclaim=1)
        self.assertIn("ISSUE_47_RECLAIM_WITHOUT_ITS_EXTENSION", str(caught.exception))
        self.assertEqual(0, session.ledger.snapshot()["slot_count"], "refused before a claim")

    def test_a_lost_host_s_reserve_counts_what_the_extension_let_it_request_again(self):
        refresh = {**_scripted_row(_INDEX, "SUBMISSIONS_INDEX", consumers=["historical_catalog"]),
                   "acquisition_kind": "SNAPSHOT_REFRESH"}
        event = _scripted_row(_OTHER[0], "FISCAL_EVENT_FILING")
        scope = _recorded_scope(classes=("FISCAL_EVENT_FILING", "SUBMISSIONS_INDEX"))
        allowance = {"scope": scope, "extension": {
            "extension_ordinal": 1, "ledger_state": {"claim_count": 3},
            "reclaim": [{"acquisition_kind": "SNAPSHOT_REFRESH",
                         "dependency_classes": ["SUBMISSIONS_INDEX"]}]}}
        frame = {"requirements": [refresh, event], "company_id": _SCRIPTED_COMPANY,
                 "target_report_dates": ["2024-12-31"]}
        with patch.object(RESUME_MODULE, "declared_frame", lambda **kwargs: copy.deepcopy(frame)):
            # Claimed before the extension: it may be requested again, so a
            # lost host could have - and it would open more rows, so refused.
            with self.assertRaises(HistoricalSessionError) as caught:
                RESUME_MODULE.lost_segment_reserve(
                    data_root=ROOT, claimed_urls={_INDEX: [2]}, allowance=allowance,
                    company_ids=[_SCRIPTED_COMPANY])
            self.assertIn("RESUME_RESERVE_UNBOUNDED", str(caught.exception))
            # Already requested again under the extension: done.
            reserve = RESUME_MODULE.lost_segment_reserve(
                data_root=ROOT, claimed_urls={_INDEX: [2, 4]}, allowance=allowance,
                company_ids=[_SCRIPTED_COMPANY])
        self.assertEqual(1, reserve["reserve_sec_calls"])


def _extension_tree(*, body_overrides=None, policy_overrides=None, comment_overrides=None):
    """A first approval and an extension of it, both real and internally consistent."""
    root, budget = _grant_tree()
    allowance = acquisition_allowance(repo_root=root)
    state = {"export_id": "sha256:" + "e" * 64,
             "claims": {"sha256": "c" * 64, "size": 100}, "claim_count": 3,
             "resumes": {"sha256": hashlib.sha256(b"").hexdigest(), "size": 0},
             "cumulative": [0, 0, 3]}
    scope = dict(allowance["scope"])
    approved = {"record_type": EXTENSION_TYPE, "requirement_id": "issue_47_v1",
                "extension_ordinal": 1,
                "extends": {"delegation_url": allowance["delegation_url"],
                            "delegation_body_sha256": allowance["delegation_body_sha256"],
                            "ledger_state": state},
                "maximum_additional_provider_paid_sec_calls": [0, 0, 10],
                "budget_root": allowance["budget_root"], "scope": scope,
                "reclaim": [{"acquisition_kind": "SNAPSHOT_REFRESH",
                             "dependency_classes": ["SUBMISSIONS_INDEX"]}],
                "production_authorized": False, **(body_overrides or {})}
    body = json.dumps(approved, sort_keys=True)
    comment = {"html_url": _EXTENSION_URL, "body": body, "id": 2,
               "issue_url": "https://api.github.com/repos/wlvh/SEC_metrics/issues/47",
               "user": {"login": "wlvh", "id": 30534800, "type": "User"},
               "author_association": "OWNER", "created_at": "2026-09-30T00:00:00Z",
               "updated_at": "2026-09-30T00:00:00Z", "performed_via_github_app": None,
               **(comment_overrides or {})}
    (root / "docs/extension.json").write_text(json.dumps(comment), encoding="utf-8")
    policy = {"requirement_id": "issue_47_v1", "repository": "wlvh/SEC_metrics",
              "approver_login": "wlvh", "extension_ordinal": 1,
              "delegation_url": _EXTENSION_URL,
              "delegation_body_sha256": hashlib.sha256(body.encode()).hexdigest(),
              "delegation_record_path": "docs/extension.json",
              "extends": approved["extends"] if "extends" not in (body_overrides or {})
              else {"delegation_url": allowance["delegation_url"],
                    "delegation_body_sha256": allowance["delegation_body_sha256"],
                    "ledger_state": state},
              "budget_root": allowance["budget_root"],
              "maximum_additional_provider_paid_sec_calls": [0, 0, 10],
              "scope": scope, "reclaim": approved["reclaim"] if "reclaim" not in (
                  body_overrides or {}) else [{"acquisition_kind": "SNAPSHOT_REFRESH",
                                               "dependency_classes": ["SUBMISSIONS_INDEX"]}],
              **(policy_overrides or {})}
    (root / EXTENSION_POLICY_PATH).write_text(json.dumps(policy), encoding="utf-8")
    return root, budget, allowance, comment


class AnExtensionIsVerifiedLikeTheApprovalItExtends(unittest.TestCase):
    """The same gate as the first approval, and ties to it that a copy cannot fake.

    An extension is a second comment by the owner; everything that makes the
    first one an approval - read back from GitHub, posted directly, unedited,
    restating what the policy grants - is required of it too, and it must name
    the approval and the ledger it continues.
    """

    def setUp(self):
        self.made = []
        self.addCleanup(lambda: [shutil.rmtree(p, ignore_errors=True)
                                 for group in self.made for p in group[:2]])

    def _tree(self, **overrides):
        made = _extension_tree(**overrides)
        self.made.append(made)
        return made

    def test_a_consistent_extension_is_read_and_extends_the_allowance(self):
        root, _, allowance, comment = self._tree()
        extension = acquisition_extension(repo_root=root, allowance=allowance,
                                          delegation_reader=lambda path: dict(comment))
        self.assertTrue(extension["approved_extension"]["provenance_verified_against_github"])
        effective = extended_allowance(allowance=allowance, extension=extension)
        self.assertEqual(allowance["maximum_additional_provider_paid_sec_calls"],
                         effective["maximum_additional_provider_paid_sec_calls"],
                         "the binding's limits stay the first approval's")
        self.assertEqual([0, 0, 10], effective["extension"][
            "maximum_additional_provider_paid_sec_calls"])
        self.assertEqual(allowance["delegation_url"], effective["delegation_url"])

    def test_no_extension_is_none_and_changes_nothing(self):
        root, _, allowance, _ = self._tree()
        (root / EXTENSION_POLICY_PATH).unlink()
        self.assertIsNone(acquisition_extension(repo_root=root, allowance=allowance))
        self.assertIs(allowance, extended_allowance(allowance=allowance, extension=None))

    def test_each_tie_and_each_field_refuses_by_name(self):
        cases = (
            ("the policy raises more than the comment",
             dict(policy_overrides={"maximum_additional_provider_paid_sec_calls": [0, 0, 99]}),
             "ISSUE_47_EXTENSION_WIDENS_THE_APPROVED_GRANT:maximum"),
            ("another approval extended",
             dict(policy_overrides={"extends": {"delegation_url": _EXTENSION_URL,
                                                "delegation_body_sha256": "d" * 64,
                                                "ledger_state": {
                                                    "export_id": "sha256:" + "e" * 64,
                                                    "claims": {"sha256": "c" * 64,
                                                               "size": 100},
                                                    "claim_count": 3,
                                                    "resumes": {"sha256": "d" * 64,
                                                                "size": 0},
                                                    "cumulative": [0, 0, 3]}}}),
             "ISSUE_47_EXTENSION_EXTENDS_ANOTHER_APPROVAL"),
            ("another ledger root",
             dict(policy_overrides={"budget_root": "/tmp/another-ledger-root"}),
             "ISSUE_47_EXTENSION_NAMES_ANOTHER_LEDGER_ROOT"),
            ("the first approval's own comment",
             dict(policy_overrides={"delegation_url": "https://github.com/wlvh/SEC_metrics/"
                                                      "issues/47#issuecomment-1"}),
             "ISSUE_47_EXTENSION_IS_THE_FIRST_APPROVAL_S_COMMENT"),
            ("a re-request for a first acquisition",
             dict(policy_overrides={"reclaim": [{"acquisition_kind": "FIRST_ACQUISITION",
                                                 "dependency_classes": ["SUBMISSIONS_INDEX"]}]}),
             "ISSUE_47_EXTENSION_RECLAIM_KIND_NOT_ALLOWED"),
            ("a re-request of a class outside the grants",
             dict(policy_overrides={"reclaim": [{"acquisition_kind": "SNAPSHOT_REFRESH",
                                                 "dependency_classes": ["NOT_A_CLASS"]}]}),
             "ISSUE_47_EXTENSION_RECLAIM_CLASS_OUTSIDE_THE_GRANTS"),
            ("the comment is the first approval's type",
             dict(body_overrides={"record_type": DELEGATION_TYPE}),
             "ISSUE_47_EXTENSION_RECORD_TYPE_CHANGED"),
            ("an edited comment",
             dict(comment_overrides={"updated_at": "2026-09-30T01:00:00Z"}),
             "ISSUE_47_DELEGATION_COMMENT_WAS_EDITED"),
            ("posted through an app",
             dict(comment_overrides={"performed_via_github_app": {"id": 1}}),
             "ISSUE_47_DELEGATION_WAS_POSTED_THROUGH_AN_APP"),
            ("the comment authorizes production",
             dict(body_overrides={"production_authorized": True}),
             "ISSUE_47_EXTENSION_MUST_NOT_AUTHORIZE_PRODUCTION"))
        for label, overrides, reason in cases:
            with self.subTest(label):
                root, _, allowance, _ = self._tree(**overrides)
                with self.assertRaises(HistoricalAcquisitionError) as caught:
                    acquisition_extension(repo_root=root, allowance=allowance)
                self.assertIn(reason, str(caught.exception))

    def test_a_purpose_the_binding_never_saw_is_refused(self):
        root, _, allowance, _ = self._tree()
        policy = json.loads((root / EXTENSION_POLICY_PATH).read_text())
        policy["scope"] = {**policy["scope"],
                           "purposes": [*policy["scope"]["purposes"], "another_purpose"]}
        (root / EXTENSION_POLICY_PATH).write_text(json.dumps(policy), encoding="utf-8")
        with self.assertRaises(HistoricalAcquisitionError) as caught:
            acquisition_extension(repo_root=root, allowance=allowance)
        self.assertIn("ISSUE_47_EXTENSION_ADDS_A_PURPOSE", str(caught.exception))

    def test_the_saved_record_must_be_what_github_returns(self):
        root, _, allowance, comment = self._tree()
        with self.assertRaises(HistoricalAcquisitionError) as caught:
            acquisition_extension(repo_root=root, allowance=allowance,
                                  delegation_reader=lambda path: {**comment,
                                                                  "body": comment["body"] + " "})
        self.assertIn("ISSUE_47_SAVED_EXTENSION_DIFFERS_FROM_THE_ONE_ON_GITHUB",
                      str(caught.exception))

    def test_registration_waits_for_a_pinned_body_and_takes_only_those_bytes(self):
        root, _, allowance, comment = self._tree()
        with patch.object(EXTENSION_MODULE, "EXTENSION_BODY_SHA256", None), \
                self.assertRaises(HistoricalAcquisitionError) as caught:
            EXTENSION_MODULE.register_extension(repo_root=root, comment_url=_EXTENSION_URL,
                                                reader=lambda path: dict(comment),
                                                allowance=allowance)
        self.assertIn("ISSUE_47_EXTENSION_BODY_NOT_PINNED", str(caught.exception))
        (root / EXTENSION_POLICY_PATH).unlink()
        body = comment["body"].encode("utf-8")
        (root / EXTENSION_MODULE.EXTENSION_BODY_PATH).parent.mkdir(parents=True, exist_ok=True)
        (root / EXTENSION_MODULE.EXTENSION_BODY_PATH).write_bytes(body)
        with patch.object(EXTENSION_MODULE, "EXTENSION_BODY_SHA256",
                          hashlib.sha256(body).hexdigest()):
            other = {**comment, "body": comment["body"].replace('"extension_ordinal": 1',
                                                                '"extension_ordinal": 2')}
            with self.assertRaises(HistoricalAcquisitionError) as caught:
                EXTENSION_MODULE.register_extension(
                    repo_root=root, comment_url=_EXTENSION_URL,
                    reader=lambda path: dict(other), allowance=allowance)
            self.assertIn("ISSUE_47_POSTED_EXTENSION_IS_NOT_THE_APPROVED_TEXT",
                          str(caught.exception))
            # A browser's line breaks are forgiven, as for the first approval.
            posted = {**comment, "body": comment["body"].replace("\n", "\r\n") + "\r\n"}
            result = EXTENSION_MODULE.register_extension(
                repo_root=root, comment_url=_EXTENSION_URL,
                reader=lambda path: dict(posted), allowance=allowance)
        self.assertEqual("EXTENSION_REGISTERED", result["status"])
        self.assertEqual([0, 0, 10], result["additional_limits"])


class AReplacementUnderTheExtensionReplaysThroughTheFrozenValidator(unittest.TestCase):
    """The real chain: a failed request, replaced once under the extension, and registered.

    The scripted cases stop at the ledger. Two attempts for one URL in the
    request log is a shape the first approval never produced, and whether the
    frozen checkpoint replay, the installation and the planner accept it is a
    question only the real chain answers.
    """

    def test_the_replacement_is_saved_and_the_plan_stops_asking(self):
        base = Path(tempfile.mkdtemp(prefix="issue47-replace-"))
        self.addCleanup(shutil.rmtree, base, ignore_errors=True)
        root = base / "ledger"
        failed = recorded_historical_session(root=root, response=b"", status=404,
                                             limits=(0, 0, 1))
        self.assertEqual("FAILED_TERMINAL",
                         failed.capture(company_id=_SCRIPTED_COMPANY, url=DECLARED)["status"])
        frame = declared_frame(repo_root=failed.data_root, company_id=_SCRIPTED_COMPANY)
        row = next(r for r in frame["requirements"] if r["source_url"] == DECLARED)
        self.assertEqual("REPLACEMENT_ACQUISITION", row["acquisition_kind"])
        with self.assertRaises(HistoricalSessionError) as caught:
            recorded_historical_session(root=root, response=BODY, limits=(0, 0, 1)).capture(
                company_id=_SCRIPTED_COMPANY, url=DECLARED)
        self.assertIn("ISSUE_47_URL_ALREADY_CLAIMED_IN_THIS_LEDGER", str(caught.exception))
        extension = _test_extension(root, limits=(0, 0, 1), reclaim=[
            {"acquisition_kind": "REPLACEMENT_ACQUISITION",
             "dependency_classes": [row["dependency_class"]]}])
        replaced = recorded_historical_session(root=root, response=BODY, limits=(0, 0, 1),
                                               extension=extension)
        result = replaced.capture(company_id=_SCRIPTED_COMPANY, url=DECLARED)
        self.assertEqual("SUCCEEDED", result["status"])
        plan = strict_json_file(path=root / "calls/0002/sec-plan.json")
        self.assertEqual(1, plan["request"]["reclaimed_under_extension"])
        checkpoint, _ = checkpoint_installation(source_root=replaced.data_root)
        self.assertEqual(2, len(checkpoint["captures"]))
        after = declared_frame(repo_root=replaced.data_root, company_id=_SCRIPTED_COMPANY)
        row = next(r for r in after["requirements"] if r["source_url"] == DECLARED)
        self.assertFalse(row["new_acquisition_required"], "the replacement is what is saved now")
        self.assertEqual([0, 0, 2], replaced.ledger.snapshot()["counts"])
        # Requested again under the extension already: a caller's marker for
        # it, or none, is not what the ledger allows, and nothing is claimed.
        failed_row = {**row, "acquisition_kind": "REPLACEMENT_ACQUISITION",
                      "reason": "LATEST_SOURCE_REQUEST_FAILED: " + DECLARED}
        admitted = {"company_id": _SCRIPTED_COMPANY,
                    "dependency_class": row["dependency_class"], "grants": ["RECORDED_TEST"],
                    "purpose": replaced.allowance["scope"]["purposes"][0]}
        for marker in (1, None):
            with self.subTest(marker=marker), replaced.ledger.locked():
                with self.assertRaises(HistoricalSessionError) as caught:
                    replaced._capture_one(company_id=_SCRIPTED_COMPANY, url=DECLARED,
                                          dependency=failed_row, admitted=admitted,
                                          reclaim=marker)
                self.assertIn("ISSUE_47_RECLAIM_IS_NOT_WHAT_THE_LEDGER_ALLOWS",
                              str(caught.exception))
        self.assertEqual(2, replaced.ledger.snapshot()["slot_count"])


class AnExportSaysWhichExtensionItWasSpentUnder(unittest.TestCase):
    """An export after an extension records it, and only beside the approval it extends.

    The export is what the branch carries and what a resume restores from; a
    claim past the first approval's cap is readable there only if the export
    names the extension that raised it. An extension naming another approval
    or another ledger root is refused rather than recorded beside this one.
    """

    def setUp(self):
        self.root, self.budget, self.allowance, _ = _extension_tree()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.addCleanup(shutil.rmtree, self.budget, ignore_errors=True)
        self.approval = {key: self.allowance[key] for key in (
            "delegation_url", "delegation_body_sha256", "budget_root")}

    def test_the_extension_is_recorded_beside_its_approval(self):
        recorded = EXPORT_MODULE._extension(approval=self.approval, policy_root=self.root)
        self.assertEqual(_EXTENSION_URL, recorded["delegation_url"])
        self.assertEqual([0, 0, 10], recorded["maximum_additional_provider_paid_sec_calls"])
        self.assertEqual(self.allowance["delegation_url"],
                         recorded["extends"]["delegation_url"])

    def test_an_export_without_an_extension_is_unchanged(self):
        (self.root / EXTENSION_POLICY_PATH).unlink()
        self.assertIsNone(EXPORT_MODULE._extension(approval=self.approval,
                                                   policy_root=self.root))
        self.assertIsNone(EXPORT_MODULE._extension(approval=None, policy_root=self.root))

    def test_an_extension_of_another_approval_or_root_is_refused(self):
        for label, approval in (
                ("another approval", {**self.approval, "delegation_body_sha256": "d" * 64}),
                ("another comment", {**self.approval, "delegation_url": _EXTENSION_URL}),
                ("another ledger root", {**self.approval,
                                         "budget_root": "/tmp/another-ledger-root"})):
            with self.subTest(label):
                with self.assertRaises(HistoricalAcquisitionError) as caught:
                    EXPORT_MODULE._extension(approval=approval, policy_root=self.root)
                self.assertIn("ISSUE_47_EXPORT_EXTENSION_IS_OF_ANOTHER_APPROVAL",
                              str(caught.exception))


class TheLivePathHoldsTheLedgerToTheExtensionItRead(unittest.TestCase):
    """The live ledger is pinned to the extension the live path verified, or refused.

    The scripted and recorded cases hand the extension to the recorded session;
    the live session reaches the ledger through ``live_ledger``, and a live
    path that read the extension but did not pin it would raise nothing - it
    would stop at the first approval's cap - while one that raised the cap
    without the claim-log check would raise it for any ledger at that root.
    """

    def test_the_live_ledger_is_raised_only_for_the_log_it_continues(self):
        base = Path(tempfile.mkdtemp(prefix="issue47-livepin-"))
        self.addCleanup(shutil.rmtree, base, ignore_errors=True)
        root = base / "ledger"
        purpose = "ISSUE47_HISTORICAL_SOURCE_DEPENDENCY"
        allowance = {"budget_root": str(root), "scope": {"purposes": [purpose]},
                     "maximum_additional_provider_paid_sec_calls": [0, 0, 1]}
        first = SESSION_MODULE.live_ledger(allowance=allowance,
                                           published={"reserve_sec_calls": 0})
        with first.locked():
            first.claim(channel="SEC", request_digest="sha256:" + "1" * 64,
                        plan_id="sha256:" + "2" * 64, purpose=purpose)
        state = _ledger_state(root)
        extension = {"extension_ordinal": 1, "delegation_url": _EXTENSION_URL,
                     "delegation_body_sha256": "b" * 64,
                     "maximum_additional_provider_paid_sec_calls": [0, 0, 2],
                     "ledger_state": state, "provenance_verified_against_github": True}
        published = {"reserve_sec_calls": 0}
        refusals = (
            ("not read back from GitHub",
             {**extension, "provenance_verified_against_github": False},
             "ISSUE_47_LIVE_EXTENSION_NOT_READ_BACK_FROM_GITHUB"),
            ("another claim log", {**extension, "ledger_state": {
                **state, "claims": {**state["claims"], "sha256": "f" * 64}}},
             "ISSUE_47_LEDGER_IS_NOT_THE_ONE_THE_EXTENSION_EXTENDS"),
            ("another spending stated", {**extension, "ledger_state": {
                **state, "cumulative": [0, 0, state["claim_count"] + 1]}},
             "ISSUE_47_EXTENSION_STATES_ANOTHER_SPENDING"))
        for label, stated, reason in refusals:
            with self.subTest(label):
                with self.assertRaises(HistoricalSessionError) as caught:
                    SESSION_MODULE.live_ledger(allowance={**allowance, "extension": stated},
                                               published=published)
                self.assertIn(reason, str(caught.exception))
        again = SESSION_MODULE.live_ledger(allowance={**allowance, "extension": extension},
                                           published=published)
        self.assertEqual([0, 0, 3], again.snapshot()["limits"])
        # Pinned once at this root; the same extension pins again in a new
        # process, and a different one - a larger raise - does not.
        self.assertTrue(SESSION_MODULE.extension_anchor_path(root, 1).is_file())
        SESSION_MODULE.live_ledger(allowance={**allowance, "extension": extension},
                                   published=published)
        with self.assertRaises(HistoricalSessionError) as caught:
            SESSION_MODULE.live_ledger(allowance={**allowance, "extension": {
                **extension, "maximum_additional_provider_paid_sec_calls": [0, 0, 1000]}},
                published=published)
        self.assertIn("ISSUE_47_ANOTHER_EXTENSION_WAS_PINNED_HERE", str(caught.exception))


class AnExtensionIsSpentOnlyOnceTheBranchCarriesIt(unittest.TestCase):
    """The checkout's extension files must be the branch tip's before any request under them.

    A resume reads the branch. An extension registered in a container and
    never pushed would let requests be made that a successor, reading the
    branch, cannot charge for; a branch carrying an extension the checkout
    lacks would be spent under grants the session does not hold.
    """

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="issue47-branch-extension-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def _write(self, relative, data):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def test_the_checkout_and_the_tip_must_carry_the_same_extension(self):
        policy, record = EXTENSION_MODULE.EXTENSION_FILES
        EXTENSION_MODULE.require_extension_on_branch(repo_root=self.root,
                                                     branch_files=dict(_NO_EXTENSION))
        self._write(policy, b"{}")
        self._write(record, b"{}")
        same = {policy: b"{}", record: b"{}"}
        EXTENSION_MODULE.require_extension_on_branch(repo_root=self.root, branch_files=same)
        for label, branch in (("not pushed", dict(_NO_EXTENSION)),
                              ("pushed differently", {policy: b"{} ", record: b"{}"}),
                              ("only half pushed", {policy: b"{}", record: None})):
            with self.subTest(label):
                with self.assertRaises(HistoricalAcquisitionError) as caught:
                    EXTENSION_MODULE.require_extension_on_branch(repo_root=self.root,
                                                                 branch_files=branch)
                self.assertIn("ISSUE_47_EXTENSION_NOT_ON_THE_BRANCH", str(caught.exception))
        (self.root / policy).unlink()
        (self.root / record).unlink()
        with self.assertRaises(HistoricalAcquisitionError) as caught:
            EXTENSION_MODULE.require_extension_on_branch(repo_root=self.root, branch_files=same)
        self.assertIn("ISSUE_47_EXTENSION_NOT_ON_THE_BRANCH", str(caught.exception))
        for missing in ({}, {policy: None}):
            with self.assertRaises(HistoricalAcquisitionError) as caught:
                EXTENSION_MODULE.require_extension_on_branch(repo_root=self.root,
                                                             branch_files=missing)
            self.assertIn("ISSUE_47_BRANCH_TIP_DOES_NOT_SAY_WHICH_EXTENSION",
                          str(caught.exception))


class ThePinnedBodyIsTheCommittedProposal(unittest.TestCase):
    """The digest registration checks is the body the proposal tool wrote and the owner reads."""

    def test_the_committed_body_has_the_pinned_digest_and_passes_the_gate_s_shape(self):
        body = (ROOT / EXTENSION_MODULE.EXTENSION_BODY_PATH).read_bytes()
        self.assertEqual(EXTENSION_MODULE.EXTENSION_BODY_SHA256, hashlib.sha256(body).hexdigest())
        approved = strict_json_loads(text=body.decode("utf-8"))
        self.assertEqual(EXTENSION_MODULE.EXTENSION_TYPE, approved["record_type"])
        self.assertIs(False, approved["production_authorized"])
        first = acquisition_allowance(repo_root=ROOT)
        self.assertEqual(first["delegation_url"], approved["extends"]["delegation_url"])
        self.assertEqual(first["budget_root"], approved["budget_root"])
        # The state it extends is the committed export's claim log.
        index = strict_json_file(path=ROOT / "evidence/issue47_acquired/export.json")
        state = approved["extends"]["ledger_state"]
        self.assertEqual(index["export_id"], state["export_id"])
        self.assertEqual(index["state_archive"]["members"]["ledger/claims.jsonl"],
                         state["claims"])
