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
import atexit
import hashlib
import json
import shutil
import socket
import tempfile
import unittest

from vnext.canonical import content_hash, strict_json_file
from vnext.continuous_sec_acquisition import validate_acquisition_checkpoint
from vnext.historical_sec_session import (HistoricalSessionError,
                                          unclassified_verification_cases,
                                          install_historical_source_inputs,
                                          live_historical_session,
                                          recorded_historical_session,
                                          verify_offline_wiring)
from vnext.historical_source_acquisition import (POLICY_PATH, DELEGATION_TYPE,
                                                 TRUSTED_APPROVER, TRUSTED_REPOSITORY,
                                                 HistoricalAcquisitionError,
                                                 acquisition_allowance,
                                                 declared_dependencies,
                                                 declared_frame,
                                                 historical_dependency,
                                                 request_is_in_scope)
from vnext.normal_source_authority import MANIFEST_PATH, ROOT

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
        shutil.copytree(cls.root / "ledger", destination)
        return destination


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

    def test_live_refuses_while_issue_47_has_no_allowance_of_its_own(self):
        self.assertFalse((ROOT / POLICY_PATH).exists(),
                         "this case describes the current state; update it with the grant")
        with self.assertRaises(HistoricalAcquisitionError) as caught:
            live_historical_session()
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

    RECEIPT = "docs/evidence/issue47_history/acquisition-wiring/offline-wiring-receipt.json"

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

    def test_the_presentation_path_under_config_is_excluded(self):
        # It is installed from current bound code in the candidate runtime, and
        # it is under config/, so "copy the data directories" is not a
        # substitute for reading the parent's exclusion.
        root = Path(tempfile.mkdtemp(prefix="issue47-install-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        install_historical_source_inputs(root=root / "source-inputs")
        self.assertTrue((root / "source-inputs/config/company_registry.csv").is_file())
        self.assertFalse(
            (root / "source-inputs/config/ordinary_public_projection_v1.json").is_file(),
            "the parent's presentation path must not be installed as a source input")

    def test_an_unowned_existing_root_is_refused(self):
        root = Path(tempfile.mkdtemp(prefix="issue47-unowned-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        (root / "source-inputs").mkdir()
        with self.assertRaises(HistoricalSessionError) as caught:
            install_historical_source_inputs(root=root / "source-inputs")
        self.assertIn("ISSUE_47_SOURCE_ROOT_UNOWNED", str(caught.exception))


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
                                    "SUBMISSIONS_INDEX"],
             "earliest_report_end": "2000-01-01",
             "latest_report_end": "2099-12-31", **(scope_overrides or {})}
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
               "user": {"login": login}}
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
        row = declared_dependencies(repo_root=ROOT,
                                    company_id="marriott_international")[0]
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

        def both(slot):
            receipt = strict_json_file(path=slot / "sec-receipt.json")
            changed = {k: v for k, v in receipt.items() if k != "receipt_id"}
            changed["status"] = "FAILED_TERMINAL"
            resealed = _seal(changed, "receipt_id")
            (slot / "sec-receipt.json").write_text(json.dumps(resealed), encoding="utf-8")
            bound = {**failed, "sec_receipt_id": resealed["receipt_id"]}
            (slot / "terminal.json").write_text(
                json.dumps(_seal(bound, "terminal_id")), encoding="utf-8")

        ledger = _Chain.copy(self.root / "known-failure")
        both(ledger / "calls/0001")
        session = recorded_historical_session(root=ledger, response=BODY)
        session.ledger.require_unblocked()

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
        rows = declared_dependencies(repo_root=ROOT,
                                     company_id="marriott_international")
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
        rows = declared_dependencies(repo_root=ROOT,
                                     company_id="marriott_international")
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

    RECEIPT = "docs/evidence/issue47_history/acquisition-wiring/offline-wiring-receipt.json"

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
        return {"scope": {"purposes": ["p"], "company_ids": [company],
                          "dependency_classes": sorted({r["dependency_class"] for r in rows}),
                          "earliest_report_end": "2000-01-01",
                          "latest_report_end": "2099-12-31"}}

    def _admit(self, frame, company, row, allowance=None):
        return request_is_in_scope(allowance=allowance or self._allowance(frame, company),
                                   company_id=company, dependency=row, purpose="p",
                                   frame_report_dates=frame["target_report_dates"])

    def test_every_row_the_planner_declares_is_admissible(self):
        # Load-bearing and deliberately not a fixture: these are the rows the
        # production planner emits today.
        for company in ("marriott_international", "jpmorgan_chase"):
            with self.subTest(company=company):
                frame = declared_frame(repo_root=ROOT, company_id=company)
                self.assertTrue(frame["requirements"])
                for row in frame["requirements"]:
                    self._admit(frame, company, row)

    def test_a_frame_level_dependency_is_admitted_on_the_frame_window(self):
        frame = declared_frame(repo_root=ROOT, company_id="jpmorgan_chase")
        shards = [r for r in frame["requirements"]
                  if not any(str(c).startswith("period:") for c in r.get("consumers", []))]
        self.assertTrue(shards, "the declaration carries frame-level dependencies")
        admitted = self._admit(frame, "jpmorgan_chase", shards[0])
        self.assertEqual("FRAME_TARGET_WINDOW", admitted["period_basis"])
        self.assertEqual(frame["target_report_dates"], admitted["periods"])

    def test_a_row_that_names_periods_is_admitted_on_those(self):
        frame = declared_frame(repo_root=ROOT, company_id="marriott_international")
        named = [r for r in frame["requirements"]
                 if any(str(c).startswith("period:") for c in r.get("consumers", []))]
        admitted = self._admit(frame, "marriott_international", named[0])
        self.assertEqual("PERIOD_CONSUMERS", admitted["period_basis"])

    def test_the_refresh_rows_the_planner_actually_marks_are_admissible(self):
        # Not a hand-edited row this time: JPMorgan's shards are the real
        # SNAPSHOT_REFRESH population, and they are what the previous gate
        # refused.
        frame = declared_frame(repo_root=ROOT, company_id="jpmorgan_chase")
        refresh = [r for r in frame["requirements"]
                   if r.get("acquisition_kind") == "SNAPSHOT_REFRESH"]
        self.assertTrue(refresh, "the planner marks refreshes for this company")
        for row in refresh:
            self._admit(frame, "jpmorgan_chase", row)

    def test_wrong_company_class_and_window_are_still_refused(self):
        frame = declared_frame(repo_root=ROOT, company_id="jpmorgan_chase")
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
                     "user": {"login": "wlvh"}, "body": '{"record_type": "SOMETHING_ELSE"}'}
        with self.assertRaises(HistoricalAcquisitionError) as caught:
            acquisition_allowance(repo_root=root, delegation_reader=lambda path: elsewhere)
        self.assertIn("ISSUE_47_SAVED_DELEGATION_DIFFERS_FROM_THE_ONE_ON_GITHUB",
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


class EveryVerificationCaseMustBeClassified(unittest.TestCase):
    """A selector list with no coverage check drifts, and drift is invisible.

    The receipt attested a run of eight classes that was never revisited when
    sixteen new cases arrived, so it excluded every regression that round added
    - thirteen of which do not read the receipt at all.
    """

    def test_no_test_class_is_left_out_of_both_sets(self):
        self.assertEqual([], unclassified_verification_cases())

    def test_the_excluded_set_is_only_what_reads_the_receipt(self):
        from vnext.historical_sec_session import RECEIPT_DEPENDENT_SELECTORS
        names = {s.rsplit(".", 1)[1] for s in RECEIPT_DEPENDENT_SELECTORS}
        self.assertEqual({"AGrantMustBindToAWiringReceiptThatIsStillTrue",
                          "DeletingEvidenceMustNotReduceTheCheck"}, names)

    def test_this_round_s_regressions_are_in_the_builder_s_run(self):
        from vnext.historical_sec_session import VERIFICATION_SELECTORS
        names = {s.rsplit(".", 1)[1] for s in VERIFICATION_SELECTORS}
        for required in ("AnAllowanceMustBeVerifiedNotMerelyPresent",
                         "ATerminalFileIsNotAnOutcome",
                         "BelongingToTheTaskIsNotNeedingAFetch"):
            self.assertIn(required, names)


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