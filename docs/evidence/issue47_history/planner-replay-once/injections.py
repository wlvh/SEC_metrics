"""Undo each part of the replay-once block and require the case written for it to fail.

Usage: python3 injections.py <out.json>

Each injection edits one file in place (exactly one match, must compile), runs
tests.vnext.test_historical_plan_replay with a fresh bytecode prefix, and
restores the bytes. Zero calls. The ones in REDUNDANT take out a part of the
key that no case should fail without, and the whole module must pass there.

It edits the checkout it lives in, so nothing else may import from or read
that checkout while it runs: the first run overlapped a measurement that
hashes the planner's own file when a plan ends, and the edits showed up as a
difference between frames that was not there.
"""
import json
import os
import py_compile
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PLAN = "scripts/vnext/normal_history_plan.py"
FRAME = "scripts/vnext/historical_source_acquisition.py"
MODULE = "tests.vnext.test_historical_plan_replay"
INJECTIONS = {
    "KEY_WITHOUT_THE_EVIDENCE_ENTRIES": (
        PLAN, """            tuple(sorted(set(entries))))""", """            ())""",
        "test_another_capture_rewritten_with_its_time_put_back_is_replayed_again"),
    "ENTRIES_WITHOUT_THE_CHANGE_TIME": (
        PLAN, """                            status.st_mtime_ns, status.st_ctime_ns))""",
        """                            status.st_mtime_ns))""",
        "test_another_capture_rewritten_with_its_time_put_back_is_replayed_again"),
    "ENTRIES_WITHOUT_DIRECTORIES": (
        PLAN, """        for path in [Path(directory)] + [Path(directory) / name
                                         for name in directories + names]:""",
        """        for path in [Path(directory) / name for name in names]:""",
        "test_a_directory_beside_another_capture_is_replayed_again"),
    "KEY_WITHOUT_THE_REGISTRY": (
        PLAN, """            content("config/company_registry.csv"),
""", "",
        "test_a_registry_change_is_replayed_again"),
    "REGISTRY_READ_THROUGH_ITS_ALIASES": (
        PLAN, """            content("config/company_registry.csv"),""",
        """            sha256_file(path=root / "config/company_registry.csv"),""",
        "test_a_symlinked_config_directory_is_refused_as_the_replay_refuses"),
    "KEY_WITHOUT_THE_CODE_MANIFEST": (
        PLAN, """            sha256_file(path=ROOT / MANIFEST_PATH),
""", "",
        "test_the_code_manifest_is_part_of_the_state"),
    "KEY_WITHOUT_THE_CHECKPOINT_AND_BASELINE": (
        PLAN, """            content_hash(value=checkpoint), content_hash(value=baseline),
""", "",
        "test_another_input_is_another_state"),
    "THE_SHARED_ANSWER_IS_HANDED_OUT": (
        PLAN, """        return copy.deepcopy(memo["answer"])""",
        """        return memo["answer"]""",
        "test_the_answer_is_a_copy"),
    "THE_KEY_IS_SET_BEFORE_THE_REPLAY": (
        PLAN, """            memo.update(key=None, answer=None)
            answer = frozen(data_root, checkpoint, baseline)""",
        """            memo.update(key=key, answer=None)
            answer = frozen(data_root, checkpoint, baseline)""",
        "test_a_refused_replay_is_not_remembered"),
    "THE_FROZEN_REPLAY_IS_NOT_PUT_BACK_ON_FAILURE": (
        PLAN, """    try:
        authority._validate_checkpoint = _replayed_once(current)
        yield
    finally:
        authority._validate_checkpoint = current""",
        """    authority._validate_checkpoint = _replayed_once(current)
    yield
    authority._validate_checkpoint = current""",
        "test_the_block_puts_the_frozen_replay_back"),
    "A_NESTED_BLOCK_STARTS_ITS_OWN_MEMO": (
        PLAN, """    if getattr(current, "replayed_once", False) is True:
        _need(current.thread == threading.get_ident(),
              "HISTORY_PLAN_CHECKPOINT_BLOCK_OPEN_IN_ANOTHER_THREAD")
        yield
        return
""", "",
        "test_a_block_inside_another_keeps_the_outer_memo"),
    "A_BLOCK_IS_SHARED_ACROSS_THREADS": (
        PLAN, """        _need(current.thread == threading.get_ident(),
              "HISTORY_PLAN_CHECKPOINT_BLOCK_OPEN_IN_ANOTHER_THREAD")
""", "",
        "test_a_block_is_for_one_thread"),
    "THE_FRAME_HAS_NO_BLOCK": (
        FRAME, """    with checkpoint_replayed_once():
        return _declared_frame(""",
        """    if checkpoint_replayed_once:
        return _declared_frame(""",
        "test_one_replay_per_frame_and_the_same_frame"),
    "THE_PLAN_HAS_NO_BLOCK": (
        PLAN, """    with checkpoint_replayed_once():
        return _plan_historical_sources(""",
        """    if checkpoint_replayed_once:
        return _plan_historical_sources(""",
        "test_a_plan_alone_replays_once"),
}
# Parts of the key no case is expected to fail without, run so that the claim
# is a measurement: a second link, a rewrite or a replacement also moves the
# change time, which a case does fail without.
REDUNDANT = {
    "ENTRIES_WITHOUT_THE_LINK_COUNT": (
        PLAN, """status.st_nlink, status.st_dev""", """status.st_dev""",
        "test_a_second_link_to_another_capture_is_replayed_again"),
}


def run():
    env = {**os.environ, "PYTHONPYCACHEPREFIX": tempfile.mkdtemp()}
    started = time.time()
    done = subprocess.run([sys.executable, "-m", "unittest", MODULE], cwd=REPO, env=env,
                          capture_output=True, text=True, timeout=3600)
    return done, int(time.time() - started)


def main(out):
    originals = {path: (REPO / path).read_bytes() for path in (PLAN, FRAME)}
    results = {}
    control, seconds = run()
    if control.returncode != 0:
        raise SystemExit("CONTROL_FAILED:\n" + control.stderr[-3000:])
    results["CONTROL"] = {"returncode": 0, "seconds": seconds}
    try:
        for name, (relative, old, new, expected) in {**INJECTIONS, **REDUNDANT}.items():
            target = REPO / relative
            text = originals[relative].decode("utf-8")
            if text.count(old) != 1:
                raise SystemExit("INJECTION_DOES_NOT_MATCH_ONCE:" + name)
            target.write_bytes(text.replace(old, new).encode("utf-8"))
            py_compile.compile(str(target), doraise=True, cfile=tempfile.mktemp())
            done, seconds = run()
            target.write_bytes(originals[relative])
            failed = sorted({line.split(" ")[1] for line in done.stderr.splitlines()
                             if line.startswith(("FAIL: ", "ERROR: "))})
            results[name] = {"file": relative, "returncode": done.returncode,
                             "seconds": seconds, "failed_cases": failed,
                             "expected_case": expected,
                             "caught_by_the_case_written_for_it": expected in failed,
                             "expected_to_be_caught": name not in REDUNDANT}
            print(name, results[name]["caught_by_the_case_written_for_it"], failed, flush=True)
    finally:
        for relative, raw in originals.items():
            (REPO / relative).write_bytes(raw)
    for relative, raw in originals.items():
        if (REPO / relative).read_bytes() != raw:
            raise SystemExit("TARGET_NOT_RESTORED:" + relative)
    results["all_caught"] = all(results[name]["caught_by_the_case_written_for_it"]
                                for name in INJECTIONS)
    results["redundant_parts_not_caught"] = not any(
        results[name]["returncode"] != 0 for name in REDUNDANT)
    Path(out).write_text(json.dumps(results, indent=1, sort_keys=True) + "\n",
                         encoding="utf-8")
    print(json.dumps({key: results[key] for key in ("all_caught", "redundant_parts_not_caught")}),
          flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
