"""Creating and reading Runs replays the acquisition checkpoint once per state.

historical_run_replay.run_checks_replay_once() keeps one frozen replay's answer
per ledger state for as long as the block is open, keyed by the planner's own
_replay_state, and answers the replay's three pure log helpers once per
argument value. These cases are about how that could go wrong without
failing: answering one root with another root's answer, forgetting a root a
batch keeps coming back to, remembering a refusal, handing out an answer or
parsed rows a caller can change, answering a call the frozen helper refuses,
and leaving anything replaced once the block is over.

They run over two recorded roots - the baseline corpus plus recorded
captures registered in the checkpoint journal, one root with two captures and
another with one - so every check takes the checkpoint path. Zero calls.
"""
import atexit
import shutil
import socket
import sys
import tempfile
import threading
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import sec_http
from vnext import continuous_sec_acquisition as acquisition
from vnext import historical_run_replay as memo
from vnext import normal_history_plan as plan
from vnext import ordinary_source_authority as authority
from vnext.canonical import canonical_json_bytes, strict_json_file
from vnext.historical_sec_session import recorded_historical_session
from vnext.historical_source_acquisition import declared_frame
from vnext.normal_history_catalog import HistoryCatalogError
from vnext.normal_source_authority import MANIFEST_PATH, ROOT

COMPANY = "marriott_international"
FROZEN_VALIDATE = authority._validate_checkpoint
FROZEN_HELPERS = {name: getattr(sec_http, name) for name in memo.HELPERS}


def _body(name):
    return ('{"directory": {"item": [], "name": "' + name + '"}}').encode()


def _no_network():
    return patch.object(socket.socket, "connect", side_effect=AssertionError("a socket was opened"))


def _counted(counter):
    real = acquisition.validate_acquisition_checkpoint

    def replay(*arguments, **keywords):
        counter.append(1)
        return real(*arguments, **keywords)
    return patch.object(acquisition, "validate_acquisition_checkpoint", replay)


def _answer_bytes(answer):
    raw, old_ids, admitted = answer
    return raw, canonical_json_bytes(value={"old_ids": sorted(old_ids), "admitted": admitted})


class RunChecksReplayOncePerState(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.base = Path(tempfile.mkdtemp(prefix="issue47-run-replay-"))
        atexit.register(shutil.rmtree, cls.base, ignore_errors=True)
        with _no_network():
            frame = declared_frame(repo_root=Path(__file__).resolve().parents[2],
                                   company_id=COMPANY)
            urls = sorted(row["source_url"] for row in frame["requirements"]
                          if row["new_acquisition_required"]
                          and row["dependency_class"] == "ACCESSION_INSTANCE_DISCOVERY")[:3]
            roots = []
            for name, taken in (("first", urls[:2]), ("second", urls[2:])):
                session = recorded_historical_session(
                    root=cls.base / name,
                    response={url: _body(name + "-" + str(index))
                              for index, url in enumerate(taken)})
                proofs = []
                for url in taken:
                    result = session.capture(company_id=COMPANY, url=url)
                    assert result["status"] == "SUCCEEDED", result["status"]
                    proofs.append(result["receipt"]["proof"])
                roots.append((session.data_root, proofs))
        (cls.first, cls.first_proofs), (cls.second, cls.second_proofs) = roots
        cls.baseline = strict_json_file(path=ROOT / MANIFEST_PATH)

    def tearDown(self):
        self.assertIs(FROZEN_VALIDATE, authority._validate_checkpoint,
                      "the frozen replay must be back in its module after every case")
        for name, function in FROZEN_HELPERS.items():
            self.assertIs(function, getattr(sec_http, name))

    def _verify(self, root, proofs):
        authority.verify_ordinary_source_proofs(data_root=root, proofs=proofs)

    def test_two_roots_in_turn_are_replayed_once_each(self):
        """A batch alternates between the root it installs from and the one it
        installs into; a memo of one state would replay both every time."""
        replays = []
        with _no_network(), _counted(replays), memo.run_checks_replay_once():
            for _ in range(3):
                self._verify(self.first, self.first_proofs)
                self._verify(self.second, self.second_proofs)
        self.assertEqual(2, len(replays))

    def test_the_answer_is_the_frozen_replay_s(self):
        checkpoint = authority._trusted_checkpoint(self.first)
        frozen = FROZEN_VALIDATE(self.first, checkpoint, self.baseline)
        with _no_network(), memo.run_checks_replay_once():
            once = authority._validate_checkpoint(self.first, checkpoint, self.baseline)
            again = authority._validate_checkpoint(self.first, checkpoint, self.baseline)
        self.assertEqual(_answer_bytes(frozen), _answer_bytes(once))
        self.assertEqual(_answer_bytes(frozen), _answer_bytes(again))

    def test_one_root_s_answer_never_answers_another(self):
        first = authority._trusted_checkpoint(self.first)
        second = authority._trusted_checkpoint(self.second)
        with _no_network(), memo.run_checks_replay_once():
            a = authority._validate_checkpoint(self.first, first, self.baseline)
            b = authority._validate_checkpoint(self.second, second, self.baseline)
        self.assertNotEqual(_answer_bytes(a), _answer_bytes(b))
        self.assertEqual(_answer_bytes(FROZEN_VALIDATE(self.second, second, self.baseline)),
                         _answer_bytes(b))

    def test_a_change_under_a_remembered_root_is_replayed_again(self):
        attempt = self.first / self.first_proofs[0]["request_repo_relative_path"]
        link = self.base / "a-second-link"
        replays = []
        with _no_network(), _counted(replays), memo.run_checks_replay_once():
            self._verify(self.first, self.first_proofs[1:])
            self._verify(self.second, self.second_proofs)
            try:
                os_link(attempt, link)
                with self.assertRaises(Exception):
                    self._verify(self.first, self.first_proofs[1:])
            finally:
                link.unlink()
            self.assertEqual(3, len(replays))

    def test_a_refused_replay_is_not_remembered(self):
        replays = []
        checkpoint = authority._trusted_checkpoint(self.first)

        def refuse(*arguments, **keywords):
            replays.append(1)
            raise HistoryCatalogError("REFUSED_FOR_THE_CASE")
        with _no_network(), memo.run_checks_replay_once():
            with patch.object(acquisition, "validate_acquisition_checkpoint", refuse):
                for _ in range(2):
                    with self.assertRaises(HistoryCatalogError):
                        authority._validate_checkpoint(self.first, checkpoint, self.baseline)
        self.assertEqual(2, len(replays))

    def test_the_answer_is_a_copy(self):
        checkpoint = authority._trusted_checkpoint(self.first)
        with _no_network(), memo.run_checks_replay_once():
            answer = authority._validate_checkpoint(self.first, checkpoint, self.baseline)
            answer[2].clear()
            again = authority._validate_checkpoint(self.first, checkpoint, self.baseline)
        self.assertTrue(again[2])

    def test_a_forgotten_state_is_replayed_again_not_answered_wrong(self):
        replays = []
        with _no_network(), _counted(replays), patch.object(memo, "MAX_STATES", 1), \
                memo.run_checks_replay_once():
            self._verify(self.first, self.first_proofs)
            self._verify(self.second, self.second_proofs)
            self._verify(self.first, self.first_proofs)
        self.assertEqual(3, len(replays))

    def test_everything_is_put_back_after_a_failure(self):
        with self.assertRaises(RuntimeError):
            with memo.run_checks_replay_once():
                self.assertIsNot(FROZEN_VALIDATE, authority._validate_checkpoint)
                self.assertIsNot(FROZEN_HELPERS["parse_request_log_rows"],
                                 sec_http.parse_request_log_rows)
                raise RuntimeError("fails inside the block")
        # tearDown checks every replaced function is back.

    def test_a_module_imported_inside_the_block_gets_the_frozen_helper_back(self):
        probe = types.ModuleType("vnext._run_replay_probe")
        sys.modules[probe.__name__] = probe
        try:
            with memo.run_checks_replay_once():
                # What ``from sec_http import parse_request_log_rows`` does at
                # the top of a module first imported inside the block.
                probe.parse_request_log_rows = sec_http.parse_request_log_rows
                self.assertIsNot(FROZEN_HELPERS["parse_request_log_rows"],
                                 probe.parse_request_log_rows)
            self.assertIs(FROZEN_HELPERS["parse_request_log_rows"], probe.parse_request_log_rows)
        finally:
            del sys.modules[probe.__name__]

    def test_a_block_inside_another_keeps_the_outer_memo(self):
        replays = []
        with _no_network(), _counted(replays), memo.run_checks_replay_once():
            self._verify(self.first, self.first_proofs)
            with memo.run_checks_replay_once():
                self._verify(self.first, self.first_proofs)
            self.assertIsNot(FROZEN_VALIDATE, authority._validate_checkpoint)
            self._verify(self.first, self.first_proofs)
        self.assertEqual(1, len(replays))

    def test_a_block_is_for_one_thread(self):
        failures = []

        def other():
            try:
                with memo.run_checks_replay_once():
                    pass
            except HistoryCatalogError as error:
                failures.append(str(error))
        with memo.run_checks_replay_once():
            thread = threading.Thread(target=other)
            thread.start()
            thread.join()
        self.assertEqual(["HISTORICAL_RUN_REPLAY_BLOCK_OPEN_IN_ANOTHER_THREAD"], failures)

    def test_it_does_not_open_inside_the_planner_s_block(self):
        with plan.checkpoint_replayed_once():
            with self.assertRaises(HistoryCatalogError) as refused:
                with memo.run_checks_replay_once():
                    pass
        self.assertIn("INSIDE_THE_PLANNER_BLOCK", str(refused.exception))


class TheLogHelpersAnswerOncePerArgument(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.text = (Path(__file__).resolve().parents[2]
                    / "evidence/requests_log.csv").read_text(encoding="utf-8")

    def test_the_same_answers_as_the_frozen_helpers(self):
        frozen_rows = FROZEN_HELPERS["parse_request_log_rows"](text=self.text)
        with memo.run_checks_replay_once():
            for _ in range(2):
                rows = sec_http.parse_request_log_rows(text=self.text)
                self.assertEqual(frozen_rows, rows)
                self.assertEqual(
                    [FROZEN_HELPERS["request_log_attempt_id"](row_index=index, row=row)
                     for index, row in enumerate(frozen_rows[:40])],
                    [sec_http.request_log_attempt_id(row_index=index, row=row)
                     for index, row in enumerate(rows[:40])])
                self.assertEqual(
                    FROZEN_HELPERS["request_log_prefix_bytes"](text=self.text, row_count=7),
                    sec_http.request_log_prefix_bytes(text=self.text, row_count=7))

    def test_two_logs_never_share_an_answer(self):
        """A log of the same length differing in one cell: every helper answers
        it on its own, as the frozen helper does."""
        rows = FROZEN_HELPERS["parse_request_log_rows"](text=self.text)
        cell = rows[3]["status_code"]
        changed = self.text.replace("," + cell + ",", "," + str(9 - int(cell[0])) + cell[1:] + ",", 1)
        self.assertEqual(len(self.text), len(changed))
        self.assertNotEqual(self.text, changed)
        with memo.run_checks_replay_once():
            for text in (self.text, changed, self.text):
                parsed = sec_http.parse_request_log_rows(text=text)
                self.assertEqual(FROZEN_HELPERS["parse_request_log_rows"](text=text), parsed)
                self.assertEqual(
                    FROZEN_HELPERS["request_log_prefix_bytes"](text=text, row_count=len(parsed)),
                    sec_http.request_log_prefix_bytes(text=text, row_count=len(parsed)))
                self.assertEqual(
                    [FROZEN_HELPERS["request_log_attempt_id"](row_index=index, row=row)
                     for index, row in enumerate(parsed)],
                    [sec_http.request_log_attempt_id(row_index=index, row=row)
                     for index, row in enumerate(parsed)])

    def test_parsed_rows_are_fresh_each_time(self):
        with memo.run_checks_replay_once():
            first = sec_http.parse_request_log_rows(text=self.text)
            first[0]["source_url"] = "changed"
            first.pop()
            second = sec_http.parse_request_log_rows(text=self.text)
            # The second call is answered from memory. Changing only the first
            # answer - the frozen parse's own rows, never the remembered ones -
            # could not see the remembered rows handed out as they are.
            second[0]["source_url"] = "changed again"
            second.pop()
            third = sec_http.parse_request_log_rows(text=self.text)
        frozen = FROZEN_HELPERS["parse_request_log_rows"](text=self.text)
        self.assertEqual(frozen, third)

    def test_each_helper_keeps_a_bounded_number_of_answers(self):
        """Unbounded, the prefixes alone grow with the square of the captures.
        The oldest answer is dropped and computed again when asked for."""
        calls = {name: 0 for name in memo.HELPERS}

        def counting(name):
            real = FROZEN_HELPERS[name]

            def helper(**keywords):
                calls[name] += 1
                return real(**keywords)
            helper.__module__ = "sec_http"
            return helper
        logs = [FROZEN_HELPERS["request_log_prefix_bytes"](text=self.text, row_count=count).decode()
                for count in range(1, memo.HELPER_ENTRIES["parse_request_log_rows"] + 2)]
        with patch.multiple(sec_http, **{name: counting(name) for name in memo.HELPERS}):
            with memo.run_checks_replay_once():
                bound = memo.HELPER_ENTRIES["request_log_prefix_bytes"]
                for count in range(1, bound + 3):
                    sec_http.request_log_prefix_bytes(text=self.text, row_count=count)
                sec_http.request_log_prefix_bytes(text=self.text, row_count=bound + 2)
                self.assertEqual(bound + 2, calls["request_log_prefix_bytes"], "still held")
                sec_http.request_log_prefix_bytes(text=self.text, row_count=1)
                self.assertEqual(bound + 3, calls["request_log_prefix_bytes"], "dropped")
                for text in logs + [logs[-1]]:
                    sec_http.parse_request_log_rows(text=text)
                self.assertEqual(len(logs), calls["parse_request_log_rows"])
                sec_http.parse_request_log_rows(text=logs[0])
                self.assertEqual(len(logs) + 1, calls["parse_request_log_rows"])
                rows = [{key: str(value) for key, value in row.items()} for row in
                        FROZEN_HELPERS["parse_request_log_rows"](text=self.text)[:3]]
                with patch.dict(memo.HELPER_ENTRIES, {"request_log_attempt_id": 2}):
                    for index, row in enumerate(rows):
                        sec_http.request_log_attempt_id(row_index=index, row=row)
                    sec_http.request_log_attempt_id(row_index=2, row=rows[2])
                    self.assertEqual(3, calls["request_log_attempt_id"], "still held")
                    sec_http.request_log_attempt_id(row_index=0, row=rows[0])
                    self.assertEqual(4, calls["request_log_attempt_id"], "dropped")

    def test_a_call_the_frozen_helper_refuses_is_still_refused(self):
        rows = FROZEN_HELPERS["parse_request_log_rows"](text=self.text)
        text_row = {key: str(value) for key, value in rows[1].items()}

        class Text(str):
            pass
        with memo.run_checks_replay_once():
            # Remembered for index 1 first, then asked with True: equal and
            # hashing alike, but the frozen helper refuses a bool index.
            sec_http.request_log_attempt_id(row_index=1, row=text_row)
            with self.assertRaises(ValueError):
                sec_http.request_log_attempt_id(row_index=True, row=text_row)
            with self.assertRaises(ValueError):
                sec_http.request_log_attempt_id(
                    row_index=1, row={key: Text(value) for key, value in text_row.items()})
            with self.assertRaises(ValueError):
                sec_http.request_log_prefix_bytes(text=self.text, row_count=-1)
            with self.assertRaises(ValueError):
                sec_http.request_log_prefix_bytes(text=self.text, row_count=-1)


def os_link(source, target):
    import os
    os.link(source, target)


if __name__ == "__main__":
    unittest.main()
