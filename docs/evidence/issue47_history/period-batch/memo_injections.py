"""Undo each part of the derivation memo and require the case written for it to fail.

Usage: python3 memo_injections.py <tree> <out.json>

<tree> is a copy of the runtime tree's scripts/, tests/, catalog/, config/ and
requirements/ - not the runtime tree itself: each injection edits
scripts/vnext/historical_derivation_memo.py in place (exactly one match, must
compile), runs the memo's fast cases with a fresh bytecode prefix, and puts
the bytes back, so nothing else may import from or read <tree> while it runs.
The class that calls the five real functions needs saved sources and is not
run here; each injection is aimed at a mechanism a fast case exercises.

Zero calls.
"""
import json
import os
import py_compile
import subprocess
import sys
import tempfile
import time
from pathlib import Path

TARGET = "scripts/vnext/historical_derivation_memo.py"
CASES = ["tests.vnext.test_historical_derivation_memo.OneAnswerPerTreeState",
         "tests.vnext.test_historical_derivation_memo.TheKeyAndTheCheckHoldAtTheirEdges",
         "tests.vnext.test_historical_derivation_memo.TheBlockSwapsTheFiveFunctions"]
INJECTIONS = {
    "THE_CHANGE_TIME_IS_LEFT_OUT": (
        """                rows.append((entry.path, status.st_mode, status.st_size, status.st_mtime_ns,
                             status.st_ctime_ns, status.st_ino, status.st_dev, status.st_nlink))""",
        """                rows.append((entry.path, status.st_mode, status.st_size, status.st_mtime_ns,
                             status.st_ino, status.st_dev, status.st_nlink))""",
        "test_a_file_rewritten_in_place_is_derived_again"),
    "THE_RUNTIME_TREE_IS_LEFT_OUT": (
        """    trees = {named: (), runtime: (os.path.join(runtime, ".git", "objects"),)}""",
        """    trees = {named: ()}""",
        "test_the_runtime_tree_is_in_the_key"),
    "THE_ENVIRONMENT_IS_LEFT_OUT": (
        """    environment = hashlib.sha256(repr(sorted(os.environ.items())).encode("utf-8")).hexdigest()""",
        """    environment = "" """,
        "test_the_environment_is_in_the_key"),
    "A_LINK_IS_FINGERPRINTED_LIKE_A_FILE": (
        """                if stat.S_ISLNK(status.st_mode):
                    return None
""", "",
        "test_a_tree_holding_a_link_is_not_keyed"),
    "READS_ARE_NOT_CHECKED": (
        """        if frame["stray"]:
            report.append""",
        """        if False:
            report.append""",
        "test_an_answer_that_read_outside_its_key_is_not_remembered"),
    "LISTINGS_ARE_NOT_CHECKED": (
        """_EVENTS_OPENING = {"open", "os.listdir", "os.scandir"}""",
        """_EVENTS_OPENING = {"open"}""",
        "test_a_listing_outside_its_key_is_not_remembered"),
    "PROCESSES_ARE_NOT_CHECKED": (
        """    if event in _EVENTS_STARTING:
        for frame in frames:
            frame["stray"].append(event)
        return
""", "",
        "test_an_answer_that_started_a_process_is_not_remembered"),
    "A_REFUSAL_IS_REMEMBERED": (
        """        try:
            answer = frozen(**keywords)
        finally:""",
        """        try:
            try:
                answer = frozen(**keywords)
            except Exception as error:
                answers[key] = error
                raise
        finally:""",
        "test_a_refusal_is_not_remembered"),
    "THE_SHARED_ANSWER_IS_HANDED_OUT": (
        """            return copy.deepcopy(answers[key])""",
        """            return answers[key]""",
        "test_the_answer_is_a_copy"),
    "THE_FIRST_ANSWER_IS_KEPT_UNCOPIED": (
        """            kept = copy.deepcopy(answer)""",
        """            kept = answer""",
        "test_the_answer_is_a_copy"),
    "ANY_ARGUMENT_IS_KEYED_BY_ITS_REPR": (
        """        return (type(value).__name__, tuple(_plain(item) for item in value))
    raise _NotPlain()""",
        """        return (type(value).__name__, tuple(_plain(item) for item in value))
    return ("repr", repr(value))""",
        "test_arguments_that_are_not_plain_data_go_to_the_frozen_function"),
    "A_RECURSIVE_CALL_IS_KEYED": (
        """        if arguments or computing:""",
        """        if arguments:""",
        "test_a_call_inside_its_own_computation_goes_to_the_frozen_function"),
    "A_FOREIGN_ANSWER_IS_NOT_CHECKED": (
        """        for frame in getattr(_local, "frames", None) or ():
            if named is None or not all(_within(tree, frame["allowed"])
                                        for tree in (named, runtime)):
                frame["stray"].append("memo:" + name + ":" + (named or "UNNAMED_TREE"))
""", "",
        "test_an_answer_handed_out_for_a_foreign_tree_spoils_the_outer_answer"),
    "NOTHING_IS_EVER_FORGOTTEN": (
        """        while len(answers) >= MAX_ENTRIES:
            answers.pop(next(iter(answers)))
""", "",
        "test_a_forgotten_state_is_derived_again_not_answered_wrong"),
    "BYTES_ARE_KEYED_BY_THEIR_LENGTH": (
        """        return ("bytes", len(value), hashlib.sha256(value).hexdigest())""",
        """        return ("bytes", len(value))""",
        "test_bytes_are_keyed_by_their_content"),
    "THE_TEXT_PREPARATION_NAMES_NO_TREE": (
        """    if name == "prepare_text_sources":
        return runtime
""", "",
        "test_a_preparation_handed_its_bytes_is_keyed_on_the_runtime_tree"),
    "A_SNAPSHOT_COPY_IS_KEYED_BY_ITS_PARENT": (
        """        if not isinstance(snapshot, (str, os.PathLike)) or Path(snapshot).parent.name != "requirements":""",
        """        if not isinstance(snapshot, (str, os.PathLike)):""",
        "test_the_snapshot_s_tree_is_its_repository_root"),
    # The edges an independent review found no case for, or found reachable.
    "A_FAILED_WALK_FAILS_THE_CALL": (
        """        except OSError as error:""",
        """        except ZeroDivisionError as error:""",
        "test_a_walk_that_fails_goes_to_the_frozen_function"),
    "AN_UNCOPYABLE_ANSWER_FAILS_THE_CALL": (
        """        except (TypeError, copy.Error) as error:""",
        """        except ZeroDivisionError as error:""",
        "test_an_answer_that_cannot_be_copied_is_returned_and_not_kept"),
    "ALL_OF_GIT_IS_LEFT_OUT": (
        """    trees = {named: (), runtime: (os.path.join(runtime, ".git", "objects"),)}""",
        """    trees = {named: (), runtime: (os.path.join(runtime, ".git"),)}""",
        "test_the_runtime_git_directory_is_keyed_apart_from_its_objects"),
    "SCALARS_LOSE_THEIR_TYPE": (
        """        return (type(value).__name__, value)""",
        """        return ("scalar", value)""",
        "test_true_and_one_are_two_arguments"),
    "A_DICT_WITH_OTHER_KEYS_IS_KEYED": (
        """        if not all(type(key) is str for key in value):
            raise _NotPlain()
""", "",
        "test_a_dict_whose_keys_are_not_text_goes_to_the_frozen_function"),
    "A_PATH_IS_KEYED_WITHOUT_ITS_TARGET": (
        """        return ("path", os.path.abspath(path), os.path.realpath(path))""",
        """        return ("path", os.path.abspath(path))""",
        "test_a_path_through_a_retargeted_link_is_another_argument"),
    "A_DESCRIPTOR_IS_READ_AS_A_PATH": (
        """    if target is None or type(target) is int:""",
        """    if target is None:""",
        "test_a_file_read_through_a_descriptor_opened_in_the_key_is_remembered"),
    "A_RELATIVE_READ_IS_RESOLVED_HERE": (
        """    if not os.path.isabs(raw):
        for frame in frames:  # relative to a working directory the key does not hold
            frame["stray"].append("relative:" + raw)
        return
""", "",
        "test_a_relative_read_is_not_remembered"),
    "AN_UNKEYED_NESTED_CALL_SPOILS_NOTHING": (
        """        for frame in getattr(_local, "frames", None) or ():
            if named is None or not all(_within(tree, frame["allowed"])
                                        for tree in (named, runtime)):
                frame["stray"].append("memo:" + name + ":" + (named or "UNNAMED_TREE"))
        # The memo's own walk""",
        """        # The memo's own walk""",
        "test_a_nested_call_on_a_foreign_tree_it_cannot_key_spoils_the_outer_answer"),
    "THE_WHOLE_PREFIX_IS_THE_INTERPRETER_S": (
        """    paths = sysconfig.get_paths()
    found = {paths[name] for name in ("stdlib", "platstdlib", "purelib", "platlib",
                                      "include", "platinclude") if paths.get(name)}""",
        """    found = {sys.prefix, sys.base_prefix, sys.exec_prefix, sys.base_exec_prefix}
    found.update(value for value in sysconfig.get_paths().values() if value)""",
        "test_the_interpreter_s_trees_are_its_library_paths_not_its_prefix"),
    "A_LATE_IMPORT_KEEPS_THE_MEMO": (
        """        # A module first imported inside the block bound the memo.
        for namespace, name, key in _bindings(memos):
            namespace[name] = frozen[key]""", "",
        "test_a_module_imported_inside_the_block_gets_the_frozen_function_back"),
    "NOTHING_IS_PUT_BACK_AFTER_A_FAILURE": (
        """        yield
    finally:
        for namespace, name, key in swapped:""",
        """        yield
    except BaseException:
        raise
    else:
        for namespace, name, key in swapped:""",
        "test_everything_is_put_back_after_a_failure"),
    "A_NESTED_BLOCK_STARTS_ITS_OWN": (
        """    if getattr(current, "derived_once_per_state", False) is True:""",
        """    if False:""",
        "test_a_block_inside_another_keeps_the_outer_memo"),
    "A_BLOCK_IS_SHARED_ACROSS_THREADS": (
        """        _need(current.thread == threading.get_ident(),
              "HISTORICAL_DERIVATION_MEMO_OPEN_IN_ANOTHER_THREAD")
""", "",
        "test_a_block_is_for_one_thread"),
}


def run(tree):
    env = {**os.environ, "PYTHONPYCACHEPREFIX": tempfile.mkdtemp()}
    started = time.time()
    done = subprocess.run([sys.executable, "-m", "unittest", *CASES], cwd=tree, env=env,
                          capture_output=True, text=True, timeout=1800)
    return done, int(time.time() - started)


def main(tree, out):
    tree = Path(tree).resolve()
    target = tree / TARGET
    original = target.read_bytes()
    results = {}
    control, seconds = run(tree)
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
            done, seconds = run(tree)
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
    main(sys.argv[1], sys.argv[2])
