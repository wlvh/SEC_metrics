"""One derivation per state of the files it reads, while a batch builds Runs.

Purpose: creating one historical Run derives the same two things many times.
``historical_run.replay_case`` runs when the Run is created, whenever the open
Run is validated, when it is frozen and whenever the frozen Run is loaded, and
every run of it loads the Requirement snapshot again
(``requirements.load_requirement_snapshot``, which validates every parent
generation's transfer and decision chain) and prepares the pinned period's
input again (``historical_results.prepare_historical_run_input``, whose annual
input, ``historical_annual_input.prepare_historical_annual_input``, parses the
filing and inspects its fiscal-year labels). A profiled B03 creation on the
export-restored root spent 330 of its 405 seconds in fourteen snapshot loads
and ten preparations, which could only differ from one another if a file they
read had changed in between. The text routes add two more: each rebuild of
a text case admits the filing's text again
(``historical_text_input.prepare_historical_business_text_input``, ten times in
a D01 creation), and D01's successor chain (``historical_risk_results``)
prepares the text document again for every derivation of the candidate - 27
parses of the same bytes in one creation, 180 of its 240 profiled seconds.

Inside this block those five functions answer once per value of their
arguments and state of what they read, which is taken to be:

* the tree the call names - the snapshot's repository root, or ``repo_root``;
  D01's preparation names none, and is handed the filing's bytes, which are
  keyed by their SHA-256 -
* the runtime tree whose code and installed policies they compare against
  (``ROOT``), apart from ``.git/objects``, whose content reaches nothing except
  through the refs and the index, which are in the key,
* and the process environment.

Each tree is fingerprinted by every entry's path, type, size, modification and
change times, inode, device and link count; a file cannot be rewritten without
moving its change time. The first call for a state runs the frozen function;
later calls get a deep copy of its answer.

The key is only as good as the claim that nothing else is read, so the claim
is checked on every answer that is kept: while the frozen function runs, an
audit hook records every file it opens, every directory it lists and every
process it starts, and an answer that opened anything outside those trees and
the interpreter's library paths (the standard library, site-packages and the
bytecode prefix - not the whole installation prefix, which on a system
interpreter is ``/usr``), opened anything by a relative path (the working
directory is not in the key), or started a process, is returned but not
remembered. Nor is an answer kept when, during its computation, another of
these functions was called for a tree outside this one's key or a tree it
could not name - whether that inner call was answered, derived or not keyed.
A tree that holds a symbolic link is not fingerprinted - the key would not see
the link's target - so the call goes to the frozen function, and so do calls
whose arguments are not plain data, calls that raise, calls made from inside
the same function's own computation (the snapshot loader's parent
generations), and calls whose tree could not be walked (below). An answer that
cannot be copied is returned and not kept.

What the hook cannot see: an existence or ``stat`` check raises no audit event,
and an answer that depended on the clock would be answered from its first
call. Each function's answer is compared with a second frozen call in the
cases; the reads were measured for every route a batch creates. That a file
cannot be rewritten without moving its change time assumes the filesystem
records change times finely; on the host this was built on (Linux ext4), none
of 2000 same-size rewrites right after a ``stat`` kept the change time.

Other processes do write these trees while a batch runs: every worker
registers its data root's checkpoint in the runtime tree's journal (under
``.git``, which is in the key). A registration moves the fingerprint, so it
costs a derivation, never an answer from a state the function did not see; an
entry removed while the walk reads it (a writer's temporary file) makes the
walk fail, and the call then goes to the frozen function. A change made to a
tree while its key is being read can still go unseen, as in the planner's
block.

What changes: nothing outside the block. Inside it, every ``vnext`` module
binding of the five functions is swapped for its memo, and put back on the way
out whatever happens, including bindings made by modules first imported inside
the block. A block inside another keeps the outer memo. A block is for one
thread.

Call relationships: batch drivers open this block together with
``historical_run_replay.run_checks_replay_once``; the separate process that
reads the frozen Runs back opens its own. No rule module opens it.
"""
import contextlib
import copy
import hashlib
import os
import site
import stat
import sys
import sysconfig
import threading
from pathlib import Path

from .normal_history_catalog import _need
from .normal_source_authority import ROOT

MEMOIZED = (("vnext.requirements", "load_requirement_snapshot"),
            ("vnext.historical_results", "prepare_historical_run_input"),
            ("vnext.historical_annual_input", "prepare_historical_annual_input"),
            ("vnext.historical_text_input", "prepare_historical_business_text_input"),
            ("vnext.historical_risk_results", "prepare_text_sources"))
# A period's creations touch one data root and one runtime tree; a handful of
# states covers them. Past this the oldest is derived again - slower, never
# different.
MAX_ENTRIES = 16
_EVENTS_OPENING = {"open", "os.listdir", "os.scandir"}
_EVENTS_STARTING = {"subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.spawn",
                    "os.fork", "os.forkpty"}
_local = threading.local()
_hook = []


class _NotPlain(Exception):
    """An argument this memo does not key; the frozen function answers it."""


def _plain(value):
    """A hashable, type-tagged copy of an argument, or _NotPlain."""
    if value is None or type(value) in (str, bool, int):
        return (type(value).__name__, value)
    if type(value) is bytes:
        return ("bytes", len(value), hashlib.sha256(value).hexdigest())
    if isinstance(value, os.PathLike):
        path = os.fspath(value)
        if type(path) is not str:
            raise _NotPlain()
        return ("path", os.path.abspath(path), os.path.realpath(path))
    if type(value) is dict:
        if not all(type(key) is str for key in value):
            raise _NotPlain()
        return ("dict", tuple(sorted((key, _plain(item)) for key, item in value.items())))
    if type(value) in (list, tuple):
        return (type(value).__name__, tuple(_plain(item) for item in value))
    raise _NotPlain()


def _fingerprint(root, skip=()):
    """Every entry's identity and stat under ``root``, or None if it holds a link."""
    rows = []
    stack = [root]
    while stack:
        directory = stack.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                if entry.path in skip:
                    continue
                status = entry.stat(follow_symlinks=False)
                if stat.S_ISLNK(status.st_mode):
                    return None
                rows.append((entry.path, status.st_mode, status.st_size, status.st_mtime_ns,
                             status.st_ctime_ns, status.st_ino, status.st_dev, status.st_nlink))
                if stat.S_ISDIR(status.st_mode):
                    stack.append(entry.path)
    rows.sort()
    return hashlib.sha256(repr(rows).encode("utf-8")).hexdigest()


def _within(path, trees):
    return any(path == tree or path.startswith(tree.rstrip(os.sep) + os.sep) for tree in trees)


def _interpreter_trees():
    """Where the interpreter's own library code lives, not its whole prefix."""
    paths = sysconfig.get_paths()
    found = {paths[name] for name in ("stdlib", "platstdlib", "purelib", "platlib",
                                      "include", "platinclude") if paths.get(name)}
    found.update(site.getsitepackages())
    if getattr(sys, "pycache_prefix", None):
        found.add(sys.pycache_prefix)
    return tuple(sorted(os.path.realpath(path) for path in found))


def _audit(event, arguments):
    frames = getattr(_local, "frames", None)
    if not frames:
        return
    if event in _EVENTS_STARTING:
        for frame in frames:
            frame["stray"].append(event)
        return
    if event not in _EVENTS_OPENING:
        return
    target = arguments[0] if arguments else "."
    if target is None or type(target) is int:
        return  # an open file descriptor; its path was checked when it was opened
    raw = os.fsdecode(target)
    if not os.path.isabs(raw):
        for frame in frames:  # relative to a working directory the key does not hold
            frame["stray"].append("relative:" + raw)
        return
    path = os.path.realpath(raw)
    for frame in frames:
        if not _within(path, frame["allowed"]):
            frame["stray"].append(path)


def _install_hook():
    if not _hook:
        sys.addaudithook(_audit)
        _hook.append(_audit)


def _trees_of(name, keywords, runtime):
    """The tree a call names, or None when this memo cannot identify it."""
    if name == "prepare_text_sources":
        return runtime
    if name == "load_requirement_snapshot":
        snapshot = keywords.get("snapshot_dir")
        if not isinstance(snapshot, (str, os.PathLike)) or Path(snapshot).parent.name != "requirements":
            return None
        named = Path(snapshot).parent.parent
    else:
        named = keywords.get("repo_root")
        if not isinstance(named, (str, os.PathLike)):
            return None
    return os.path.realpath(os.fspath(named))


def _state(named, runtime):
    """The key's state part, or None when a tree cannot be fingerprinted."""
    trees = {named: (), runtime: (os.path.join(runtime, ".git", "objects"),)}
    parts = []
    for tree in sorted(trees):
        found = _fingerprint(tree, skip=trees[tree])
        if found is None:
            return None
        parts.append((tree, found))
    environment = hashlib.sha256(repr(sorted(os.environ.items())).encode("utf-8")).hexdigest()
    return tuple(parts), environment


def _memo(name, frozen, runtime, report):
    answers = {}
    computing = []

    def memoized(*arguments, **keywords):
        if arguments or computing:
            return frozen(*arguments, **keywords)
        try:
            key_arguments = _plain(keywords)
        except _NotPlain:
            return frozen(**keywords)
        named = _trees_of(name, keywords, runtime)
        # Called inside another of these functions' computation, this is a
        # read of the tree it names, keyed or not: the outer answer is kept
        # only if that tree is inside the outer key.
        for frame in getattr(_local, "frames", None) or ():
            if named is None or not all(_within(tree, frame["allowed"])
                                        for tree in (named, runtime)):
                frame["stray"].append("memo:" + name + ":" + (named or "UNNAMED_TREE"))
        # The memo's own walk is not a read by the function being computed
        # around it; what that computation depends on is checked below.
        frames = _local.__dict__.setdefault("frames", [])
        suspended, frames[:] = list(frames), []
        failed = None
        try:
            state = None if named is None else _state(named, runtime)
        except OSError as error:
            # An entry removed while it was read (another process's temporary
            # file), or a named tree that does not exist: nothing to key, and
            # the frozen function gives its own answer or refusal.
            state, failed = None, type(error).__name__
        finally:
            frames[:] = suspended
        if state is None:
            report.append({"function": name, "outcome": "NOT_KEYED",
                           **({"walk_failed": failed} if failed else {})})
            return frozen(**keywords)
        allowed = (named, runtime)
        key = (key_arguments, state)
        if key in answers:
            report.append({"function": name, "outcome": "ANSWERED"})
            return copy.deepcopy(answers[key])
        frame = {"allowed": allowed + _interpreter_trees(), "stray": []}
        frames.append(frame)
        computing.append(1)
        try:
            answer = frozen(**keywords)
        finally:
            computing.pop()
            frames.pop()
        if frame["stray"]:
            report.append({"function": name, "outcome": "COMPUTED_NOT_REMEMBERED",
                           "read_outside_the_key": sorted(set(frame["stray"]))[:20]})
            return answer
        try:
            kept = copy.deepcopy(answer)
        except (TypeError, copy.Error) as error:
            report.append({"function": name, "outcome": "COMPUTED_NOT_REMEMBERED",
                           "answer_not_copyable": type(error).__name__})
            return answer
        while len(answers) >= MAX_ENTRIES:
            answers.pop(next(iter(answers)))
        answers[key] = kept
        report.append({"function": name, "outcome": "COMPUTED"})
        return answer
    memoized.derived_once_per_state = True
    memoized.thread = threading.get_ident()
    return memoized


def _frozen_functions():
    found = {}
    for module_name, name in MEMOIZED:
        module = sys.modules.get(module_name)
        if module is None:
            __import__(module_name)
            module = sys.modules[module_name]
        found[(module_name, name)] = getattr(module, name)
    return found


def _bindings(functions):
    """Every ``vnext`` module namespace binding one of ``functions``: (namespace, name, key)."""
    found = []
    for module in list(sys.modules.values()):
        module_name = getattr(module, "__name__", None)
        if not isinstance(module_name, str) or not module_name.startswith("vnext."):
            continue
        namespace = vars(module)
        for key, function in functions.items():
            if namespace.get(key[1]) is function:
                found.append((namespace, key[1], key))
    return found


@contextlib.contextmanager
def derived_once_per_state(*, report=None):
    """Answer the snapshot load and the four preparations once per state.

    ``report``, when given, is a list that receives one item per call the
    memo handled: ``COMPUTED`` (frozen, remembered), ``ANSWERED`` (a copy of a
    remembered answer), ``COMPUTED_NOT_REMEMBERED`` (frozen, and it read
    outside its key) or ``NOT_KEYED`` (frozen; a tree could not be
    fingerprinted).
    """
    frozen = _frozen_functions()
    current = next(iter(frozen.values()))
    if getattr(current, "derived_once_per_state", False) is True:
        _need(current.thread == threading.get_ident(),
              "HISTORICAL_DERIVATION_MEMO_OPEN_IN_ANOTHER_THREAD")
        yield
        return
    _need(not any(getattr(function, "derived_once_per_state", False)
                  for function in frozen.values()),
          "HISTORICAL_DERIVATION_MEMO_PARTLY_OPEN")
    _install_hook()
    runtime = os.path.realpath(os.fspath(ROOT))
    memos = {key: _memo(key[1], function, runtime, report if report is not None else [])
             for key, function in frozen.items()}
    swapped = []
    try:
        for namespace, name, key in _bindings(frozen):
            namespace[name] = memos[key]
            swapped.append((namespace, name, key))
        yield
    finally:
        for namespace, name, key in swapped:
            namespace[name] = frozen[key]
        # A module first imported inside the block bound the memo.
        for namespace, name, key in _bindings(memos):
            namespace[name] = frozen[key]
