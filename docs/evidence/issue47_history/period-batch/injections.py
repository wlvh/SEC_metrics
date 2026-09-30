"""Undo each part of the Run-creation replay block and require the case written for it to fail.

Usage: python3 injections.py <tree> <out.json>

Each injection edits <tree>/scripts/vnext/historical_run_replay.py in place
(exactly one match, must compile), runs tests.vnext.test_historical_run_replay
there with a fresh bytecode prefix, and restores the bytes. Zero calls.

<tree> is a clone of the repository with its own ``.git`` - the cases register
recorded checkpoints in that tree's trust journal - and never the runtime tree
a batch or a cold read starts from: while an injection is in place, anything
that imports the block from <tree> loads the injected code. (The first two
runs were made in the runtime tree; an independent review caught that, and the
experiments whose numbers the README cites had finished before them.)
"""
import json
import os
import py_compile
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = None  # set from the command line
BLOCK = "scripts/vnext/historical_run_replay.py"
MODULE = "tests.vnext.test_historical_run_replay"
INJECTIONS = {
    "ONE_STATE_AT_A_TIME": (
        """        if key not in answers:
            answer = frozen(data_root, checkpoint, baseline)""",
        """        if key not in answers:
            answers.clear()
            answer = frozen(data_root, checkpoint, baseline)""",
        "test_two_roots_in_turn_are_replayed_once_each"),
    "KEYED_ON_THE_ROOT_NOT_ITS_STATE": (
        """        key = _replay_state(data_root, checkpoint, baseline)""",
        """        key = str(data_root)""",
        "test_a_change_under_a_remembered_root_is_replayed_again"),
    "THE_SHARED_ANSWER_IS_HANDED_OUT": (
        """        return copy.deepcopy(answers[key])""",
        """        return answers[key]""",
        "test_the_answer_is_a_copy"),
    "A_REFUSAL_IS_REMEMBERED": (
        """            answer = frozen(data_root, checkpoint, baseline)
            counter.append(1)""",
        """            try:
                answer = frozen(data_root, checkpoint, baseline)
            except Exception as error:
                answers[key] = error
                raise
            counter.append(1)""",
        "test_a_refused_replay_is_not_remembered"),
    "NOTHING_IS_EVER_FORGOTTEN": (
        """            while len(answers) >= MAX_STATES:
                answers.pop(next(iter(answers)))
""", "",
        "test_a_forgotten_state_is_replayed_again_not_answered_wrong"),
    "A_BOOL_INDEX_IS_REMEMBERED_AS_AN_INT": (
        """        if not (type(row_index) is int and type(row) is dict""",
        """        if not (type(row) is dict""",
        "test_a_call_the_frozen_helper_refuses_is_still_refused"),
    "A_TEXT_SUBCLASS_IS_REMEMBERED_AS_TEXT": (
        """                and all(type(key) is str and type(value) is str for key, value in row.items())):""",
        """                ):""",
        "test_a_call_the_frozen_helper_refuses_is_still_refused"),
    "THE_PREFIX_MEMO_IS_UNBOUNDED": (
        """            _keep(prefixes, HELPER_ENTRIES["request_log_prefix_bytes"], key, found)""",
        """            prefixes[key] = found""",
        "test_each_helper_keeps_a_bounded_number_of_answers"),
    "THE_PARSE_MEMO_IS_UNBOUNDED": (
        """            _keep(parsed, HELPER_ENTRIES["parse_request_log_rows"], text,
                  [dict(row) for row in rows])""",
        """            parsed[text] = [dict(row) for row in rows]""",
        "test_each_helper_keeps_a_bounded_number_of_answers"),
    "THE_ID_MEMO_IS_UNBOUNDED": (
        """            _keep(ids, HELPER_ENTRIES["request_log_attempt_id"], key, found)""",
        """            ids[key] = found""",
        "test_each_helper_keeps_a_bounded_number_of_answers"),
    "PARSED_ROWS_ARE_SHARED": (
        """        return [dict(row) for row in rows]

    def request_log_attempt_id""",
        """        return rows

    def request_log_attempt_id""",
        "test_parsed_rows_are_fresh_each_time"),
    "A_PREFIX_KEYED_ON_ITS_COUNT_ALONE": (
        """        key = (text, row_count)""",
        """        key = (len(text), row_count)""",
        "test_two_logs_never_share_an_answer"),
    "A_PARSE_KEYED_ON_THE_LENGTH": (
        """        rows = parsed.get(text)
        if rows is None:
            rows = frozen["parse_request_log_rows"](text=text)
            _keep(parsed, HELPER_ENTRIES["parse_request_log_rows"], text,""",
        """        rows = parsed.get(len(text))
        if rows is None:
            rows = frozen["parse_request_log_rows"](text=text)
            _keep(parsed, HELPER_ENTRIES["parse_request_log_rows"], len(text),""",
        "test_two_logs_never_share_an_answer"),
    "A_LATE_IMPORT_KEEPS_THE_MEMO": (
        """        # A module first imported inside the block bound the memoized helper.
        for namespace, helper in _bindings(memos):
            namespace[helper] = frozen[helper]""", "",
        "test_a_module_imported_inside_the_block_gets_the_frozen_helper_back"),
    "NOTHING_IS_PUT_BACK_AFTER_A_FAILURE": (
        """        yield
    finally:
        authority._validate_checkpoint = current""",
        """        yield
    except BaseException:
        raise
    else:
        authority._validate_checkpoint = current""",
        "test_everything_is_put_back_after_a_failure"),
    "A_NESTED_BLOCK_STARTS_ITS_OWN": (
        """    if getattr(current, "replayed_per_state", False) is True:""",
        """    if False:""",
        "test_a_block_inside_another_keeps_the_outer_memo"),
    "A_BLOCK_IS_SHARED_ACROSS_THREADS": (
        """        _need(current.thread == threading.get_ident(),
              "HISTORICAL_RUN_REPLAY_BLOCK_OPEN_IN_ANOTHER_THREAD")
""", "",
        "test_a_block_is_for_one_thread"),
    "IT_OPENS_INSIDE_THE_PLANNER_S_BLOCK": (
        """    _need(not getattr(current, "replayed_once", False),
          "HISTORICAL_RUN_REPLAY_BLOCK_INSIDE_THE_PLANNER_BLOCK")
""", "",
        "test_it_does_not_open_inside_the_planner_s_block"),
}


def run():
    env = {**os.environ, "PYTHONPYCACHEPREFIX": tempfile.mkdtemp()}
    started = time.time()
    done = subprocess.run([sys.executable, "-m", "unittest", MODULE], cwd=REPO, env=env,
                          capture_output=True, text=True, timeout=3600)
    return done, int(time.time() - started)


def main(out):
    target = REPO / BLOCK
    original = target.read_bytes()
    results = {}
    control, seconds = run()
    if control.returncode != 0:
        raise SystemExit("CONTROL_FAILED:\n" + control.stderr[-3000:])
    results["CONTROL"] = {"returncode": 0, "seconds": seconds}
    try:
        for name, (old, new, expected) in INJECTIONS.items():
            text = original.decode("utf-8")
            if text.count(old) != 1:
                raise SystemExit("INJECTION_DOES_NOT_MATCH_ONCE:" + name)
            target.write_bytes(text.replace(old, new).encode("utf-8"))
            py_compile.compile(str(target), doraise=True, cfile=tempfile.mktemp())
            done, seconds = run()
            target.write_bytes(original)
            failed = sorted({line.split(" ")[1] for line in done.stderr.splitlines()
                             if line.startswith(("FAIL: ", "ERROR: "))})
            results[name] = {"returncode": done.returncode, "seconds": seconds,
                             "failed_cases": failed, "expected_case": expected,
                             "caught_by_the_case_written_for_it": expected in failed}
            print(name, results[name]["caught_by_the_case_written_for_it"], failed, flush=True)
    finally:
        target.write_bytes(original)
    if target.read_bytes() != original:
        raise SystemExit("TARGET_NOT_RESTORED")
    results["all_caught"] = all(results[name]["caught_by_the_case_written_for_it"]
                                for name in INJECTIONS)
    Path(out).write_text(json.dumps(results, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"all_caught": results["all_caught"]}), flush=True)


if __name__ == "__main__":
    REPO = Path(sys.argv[1]).resolve()
    main(sys.argv[2])
