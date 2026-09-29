"""A frame replays the acquisition checkpoint once per ledger state, not once per check.

The frozen proof verifier replays the whole checkpoint on every call. The
planner, the event declaration and the governance declaration call it once per
saved dependency, and the governance declaration's annual inputs again per
period. On the acquisition's own root that made one frame take hours and the
next one longer (docs/evidence/issue47_history/planner-replay-once/). These
cases are about the ways a memo of that replay could go wrong without failing:
answering from a state that is no longer the one on disk - including a change
to one capture's file while another capture's proof is checked, which the
per-proof check does not see - remembering a refusal or a state that moved
during the replay, handing out an answer a caller can change, leaving the
frozen module altered once the block is over, and sharing a memo across
threads.

They run over a recorded root - the baseline corpus plus two recorded
captures with different bodies, registered in the checkpoint journal - so
every saved dependency takes the checkpoint path, as it does on the
acquisition's root. Zero calls.
"""
import atexit
import copy
import json
import os
import shutil
import socket
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from vnext import continuous_sec_acquisition as acquisition
from vnext import normal_history_plan as plan
from vnext import normal_source_authority
from vnext import ordinary_source_authority as authority
from vnext.canonical import canonical_json_bytes, strict_json_file
from vnext.historical_sec_session import recorded_historical_session
from vnext.historical_source_acquisition import declared_frame
from vnext.normal_history_catalog import HistoryCatalogError

COMPANY = "marriott_international"
FROZEN_VALIDATE = authority._validate_checkpoint


def _body(name):
    return json.dumps({"directory": {"item": [], "name": name}}).encode()


def _counted(counter, during=None):
    real = acquisition.validate_acquisition_checkpoint

    def replay(*arguments, **keywords):
        counter.append(1)
        answer = real(*arguments, **keywords)
        if during is not None:
            during()
        return answer
    return patch.object(acquisition, "validate_acquisition_checkpoint", replay)


def _no_network():
    return patch.object(socket.socket, "connect", side_effect=AssertionError("a socket was opened"))


class AFrameReplaysTheCheckpointOncePerLedgerState(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.base = Path(tempfile.mkdtemp(prefix="issue47-plan-replay-"))
        atexit.register(shutil.rmtree, cls.base, ignore_errors=True)
        with _no_network():
            frame = declared_frame(repo_root=Path(__file__).resolve().parents[2],
                                   company_id=COMPANY)
            urls = sorted(row["source_url"] for row in frame["requirements"]
                          if row["new_acquisition_required"]
                          and row["dependency_class"] == "ACCESSION_INSTANCE_DISCOVERY")[:2]
            session = recorded_historical_session(
                root=cls.base / "ledger",
                response={urls[0]: _body("recorded-capture-a"),
                          urls[1]: _body("recorded-capture-b")})
            proofs = []
            for url in urls:
                result = session.capture(company_id=COMPANY, url=url)
                assert result["status"] == "SUCCEEDED", result["status"]
                proofs.append(result["receipt"]["proof"])
        cls.data_root = session.data_root
        cls.proof_a, cls.proof_b = proofs
        assert cls.proof_a["request_repo_relative_path"] != cls.proof_b["request_repo_relative_path"]

    def tearDown(self):
        self.assertIs(FROZEN_VALIDATE, authority._validate_checkpoint,
                      "the frozen replay must be back in its module after every case")

    def _frame(self, *, frozen=False):
        replays = []
        with _no_network(), _counted(replays):
            if frozen:
                # The frozen behaviour: the block installs the replay itself.
                with patch.object(plan, "_replayed_once", lambda replay: replay):
                    frame = declared_frame(repo_root=self.data_root, company_id=COMPANY)
            else:
                frame = declared_frame(repo_root=self.data_root, company_id=COMPANY)
        return frame, len(replays)

    def test_one_replay_per_frame_and_the_same_frame(self):
        frame, replays = self._frame()
        self.assertEqual(1, replays)
        frozen, frozen_replays = self._frame(frozen=True)
        # Without the memo every check replays - once per saved dependency and
        # again per period for the governance declaration's inputs - and the
        # frame produced is the same, byte for byte.
        saved = sum(1 for row in frame["requirements"]
                    if row["saved_status"] == "VERIFIED_SAVED_SOURCE")
        self.assertGreaterEqual(frozen_replays, saved)
        self.assertGreater(frozen_replays, 1)
        self.assertEqual(canonical_json_bytes(value=frozen), canonical_json_bytes(value=frame))

    def test_a_plan_alone_replays_once(self):
        """The planner's own entry carries the block, not only the frame's."""
        replays = []
        with _no_network(), _counted(replays):
            plan.plan_historical_sources(repo_root=self.data_root, company_id=COMPANY)
        self.assertEqual(1, len(replays))

    def _verify_b(self):
        authority.verify_ordinary_source_proofs(data_root=self.data_root, proofs=[self.proof_b])

    def _changed(self, change, restore, *, refused=True):
        """Check B, change something, check B again, restore it, check B once more.

        B's own proof check does not read A's files, so only the replay - run
        again because the state moved - can refuse a change made to them.
        """
        replays = []
        with _no_network(), _counted(replays), plan.checkpoint_replayed_once():
            self._verify_b()
            self._verify_b()
            self.assertEqual(1, len(replays))
            change()
            try:
                if refused:
                    with self.assertRaises(Exception):
                        self._verify_b()
                else:
                    self._verify_b()
                self.assertEqual(2, len(replays))
            finally:
                restore()
            self._verify_b()
            self.assertEqual(3, len(replays))

    def test_another_capture_rewritten_with_its_time_put_back_is_replayed_again(self):
        attempt = self.data_root / self.proof_a["request_repo_relative_path"]
        original, status = attempt.read_bytes(), attempt.stat()
        rewritten = original.replace(b"capture-a", b"capture-A")
        self.assertEqual(len(original), len(rewritten))

        def change():
            os.chmod(attempt, 0o644)
            attempt.write_bytes(rewritten)
            os.chmod(attempt, status.st_mode & 0o777)
            os.utime(attempt, ns=(status.st_atime_ns, status.st_mtime_ns))

        def restore():
            os.chmod(attempt, 0o644)
            attempt.write_bytes(original)
            os.chmod(attempt, status.st_mode & 0o777)
            os.utime(attempt, ns=(status.st_atime_ns, status.st_mtime_ns))
        self._changed(change, restore)

    def test_a_second_link_to_another_capture_is_replayed_again(self):
        attempt = self.data_root / self.proof_a["request_repo_relative_path"]
        link = self.base / "a-second-link"
        self._changed(lambda: os.link(attempt, link), lambda: link.unlink())

    def test_a_directory_beside_another_capture_is_replayed_again(self):
        attempt = self.data_root / self.proof_a["request_repo_relative_path"]
        extra = attempt.parent / (attempt.name + "." + "0" * 64 + ".headers.json")
        self._changed(lambda: extra.mkdir(), lambda: extra.rmdir())

    def test_a_registry_change_is_replayed_again(self):
        registry = self.data_root / "config/company_registry.csv"
        original, status = registry.read_bytes(), registry.stat()

        def write(content):
            os.chmod(registry, 0o644)
            registry.write_bytes(content)
            os.chmod(registry, status.st_mode & 0o777)
        self._changed(lambda: write(original + b"\n"), lambda: write(original))

    def test_a_symlinked_config_directory_is_refused_as_the_replay_refuses(self):
        config = self.data_root / "config"
        moved = self.data_root / "config-real"

        def change():
            config.rename(moved)
            shutil.copytree(moved, self.base / "config-copy")
            config.symlink_to(self.base / "config-copy", target_is_directory=True)

        def restore():
            config.unlink()
            moved.rename(config)
            shutil.rmtree(self.base / "config-copy")
        replays = []
        with _no_network(), _counted(replays), plan.checkpoint_replayed_once():
            self._verify_b()
            change()
            try:
                with self.assertRaises(Exception):
                    self._verify_b()
            finally:
                restore()
            self._verify_b()

    def test_the_code_manifest_is_part_of_the_state(self):
        key = plan._replay_state(self.data_root, {"a": 1}, {"b": 2})
        with patch.object(normal_source_authority, "MANIFEST_PATH",
                          "config/company_registry.csv"):
            self.assertNotEqual(key, plan._replay_state(self.data_root, {"a": 1}, {"b": 2}))

    def test_a_state_that_moves_during_the_replay_is_replayed_again(self):
        attempt = self.data_root / self.proof_a["request_repo_relative_path"]
        status = attempt.stat()
        moved = []

        def touch_once():
            if not moved:
                moved.append(1)
                os.utime(attempt, ns=(status.st_atime_ns, status.st_mtime_ns + 1))
        replays = []
        try:
            with _no_network(), _counted(replays, during=touch_once), \
                    plan.checkpoint_replayed_once():
                self._verify_b()
                self._verify_b()
        finally:
            os.utime(attempt, ns=(status.st_atime_ns, status.st_mtime_ns))
        # The first answer was stored under the state read before the file
        # moved; that state is not seen again, so the second check replayed.
        self.assertEqual(2, len(replays))

    def test_a_refused_replay_is_not_remembered(self):
        replays = []
        with _no_network(), _counted(replays), plan.checkpoint_replayed_once(), \
                patch.object(acquisition, "sha256_bytes", side_effect=RuntimeError("refused")):
            for _ in range(2):
                with self.assertRaisesRegex(RuntimeError, "refused"):
                    self._verify_b()
        self.assertEqual(2, len(replays))

    def test_the_answer_is_a_copy(self):
        checkpoint = authority._trusted_checkpoint(self.data_root)
        baseline = strict_json_file(path=authority.ROOT / authority.MANIFEST_PATH)
        validate = plan._replayed_once(FROZEN_VALIDATE)
        with _no_network():
            first = validate(self.data_root, checkpoint, baseline)
            kept = copy.deepcopy(first)
            first[2].clear()
            first[1].clear()
            second = validate(self.data_root, checkpoint, baseline)
        self.assertEqual(kept, second)

    def test_the_block_puts_the_frozen_replay_back(self):
        with self.assertRaisesRegex(RuntimeError, "inside"):
            with plan.checkpoint_replayed_once():
                self.assertIsNot(FROZEN_VALIDATE, authority._validate_checkpoint)
                raise RuntimeError("inside")
        self.assertIs(FROZEN_VALIDATE, authority._validate_checkpoint)

    def test_a_block_inside_another_keeps_the_outer_memo(self):
        replays = []
        with _no_network(), _counted(replays), plan.checkpoint_replayed_once():
            outer = authority._validate_checkpoint
            self._verify_b()
            with plan.checkpoint_replayed_once():
                self.assertIs(outer, authority._validate_checkpoint)
                self._verify_b()
            self.assertIs(outer, authority._validate_checkpoint)
        self.assertEqual(1, len(replays))

    def test_a_block_is_for_one_thread(self):
        refused = []

        def other():
            try:
                with plan.checkpoint_replayed_once():
                    pass
            except HistoryCatalogError as error:
                refused.append(str(error))
        with plan.checkpoint_replayed_once():
            worker = threading.Thread(target=other)
            worker.start()
            worker.join()
        self.assertEqual(["HISTORY_PLAN_CHECKPOINT_BLOCK_OPEN_IN_ANOTHER_THREAD"], refused)

    def test_another_input_is_another_state(self):
        key = plan._replay_state(self.data_root, {"a": 1}, {"b": 2})
        self.assertNotEqual(key, plan._replay_state(self.data_root, {"a": 2}, {"b": 2}))
        self.assertNotEqual(key, plan._replay_state(self.data_root, {"a": 1}, {"b": 3}))
        self.assertEqual(key, plan._replay_state(self.data_root, {"a": 1}, {"b": 2}))


if __name__ == "__main__":
    unittest.main()
