"""One checkpoint replay per ledger state while Runs are created and read back.

Purpose: a historical Run checks each of its saved sources through the frozen
``ordinary_source_authority.verify_ordinary_source_proofs``, and on a root an
acquisition filled every one of those checks replays the whole acquisition
checkpoint. Installing, creating, freezing, rendering and cold-reading one Run
made dozens of whole replays - the targeted round spent about half an hour per
position at 288 captures - and one replay grows with the square of the
captures, so a full-frame batch after the acquisition would not finish.

The planner has the same problem and a block for it
(``normal_history_plan.checkpoint_replayed_once``): one frame is computed over
one root, so it keeps the one answer for the one state. A batch works on two
roots at once - the source root it installs from and the data root it
installs into - and alternates between them, so a memo that holds one state
would replay both for every position. This block keeps an answer for each
state it has replayed, keyed by the planner's own ``_replay_state``, so what
counts as "the same state" is one definition with one set of cases.

A replay itself also repeats work that depends on nothing but the request
log's text: per capture it parses the whole log again, recomputes every row's
attempt id, and cuts two prefixes of the log. Those three helpers
(``sec_http.parse_request_log_rows``, ``request_log_attempt_id`` and
``request_log_prefix_bytes``) are pure functions of their arguments, so inside
the block each is answered once per argument value: the first call runs the
frozen function, later calls with equal arguments get its answer, parsed rows
as fresh copies. Only calls whose arguments have exactly the types the frozen
function accepts are remembered; anything else goes to the frozen function,
which refuses it as before. A call that raises is never remembered. Each
helper keeps a bounded number of answers, oldest dropped first: a replay cuts
the prefix before and after each capture, so the next capture's "before" is
the last one's "after", and a few recent prefixes are all it asks for again.
Unbounded, the prefixes alone grow with the square of the captures - about
208 MB per process at 328 captures, measured in review.

Every proof is still checked by the frozen code against the replay's answer,
and the first replay of every state in a process is the frozen replay itself.

What changes: nothing outside the block. Inside it, the frozen verifier's
replay (``ordinary_source_authority._validate_checkpoint``, looked up in its
own module at call time) and every module binding of the three helpers are
swapped for their memoized versions, and put back on the way out whatever
happens - including the bindings of modules first imported inside the block,
which took the memoized helper from sec_http and would otherwise keep it.
A block inside another keeps the outer memo. A block is for one thread. This
block refuses to open inside the planner's; the planner's, opened inside this
one, would wrap this memo and so answer the same.

Call relationships: batch drivers open this block around installing,
creating, freezing and rendering, and a separate process opens its own around
reading the frozen Runs back. No rule module opens it.
"""
import contextlib
import copy
import sys
import threading

import sec_http

from .normal_history_catalog import _need
from .normal_history_plan import _replay_state

HELPERS = ("parse_request_log_rows", "request_log_attempt_id", "request_log_prefix_bytes")
# Answers held per process; a batch process touches its source root and one
# data root at a time, so a handful covers it. Past this, the oldest state is
# replayed again when it comes back - slower, never different.
MAX_STATES = 8
# Answers each log helper holds. Past this the oldest is computed again.
HELPER_ENTRIES = {"parse_request_log_rows": 4, "request_log_attempt_id": 65536,
                  "request_log_prefix_bytes": 4}


def _keep(store, bound, key, value):
    store[key] = value
    while len(store) > bound:
        store.pop(next(iter(store)))


def _frozen_helpers():
    return {name: getattr(sec_http, name) for name in HELPERS}


def _helper_memos(frozen):
    parsed, ids, prefixes = {}, {}, {}

    def parse_request_log_rows(*, text):
        if type(text) is not str:
            return frozen["parse_request_log_rows"](text=text)
        rows = parsed.get(text)
        if rows is None:
            rows = frozen["parse_request_log_rows"](text=text)
            _keep(parsed, HELPER_ENTRIES["parse_request_log_rows"], text,
                  [dict(row) for row in rows])
            return rows
        return [dict(row) for row in rows]

    def request_log_attempt_id(*, row_index, row):
        if not (type(row_index) is int and type(row) is dict
                and all(type(key) is str and type(value) is str for key, value in row.items())):
            return frozen["request_log_attempt_id"](row_index=row_index, row=row)
        key = (row_index, tuple(row.items()))
        found = ids.get(key)
        if found is None:
            found = frozen["request_log_attempt_id"](row_index=row_index, row=row)
            _keep(ids, HELPER_ENTRIES["request_log_attempt_id"], key, found)
        return found

    def request_log_prefix_bytes(*, text, row_count):
        if not (type(text) is str and type(row_count) is int):
            return frozen["request_log_prefix_bytes"](text=text, row_count=row_count)
        key = (text, row_count)
        found = prefixes.get(key)
        if found is None:
            found = frozen["request_log_prefix_bytes"](text=text, row_count=row_count)
            _keep(prefixes, HELPER_ENTRIES["request_log_prefix_bytes"], key, found)
        return found

    return {"parse_request_log_rows": parse_request_log_rows,
            "request_log_attempt_id": request_log_attempt_id,
            "request_log_prefix_bytes": request_log_prefix_bytes}


def _replayed_per_state(frozen, counter):
    answers = {}

    def validate(data_root, checkpoint, baseline):
        key = _replay_state(data_root, checkpoint, baseline)
        if key not in answers:
            answer = frozen(data_root, checkpoint, baseline)
            counter.append(1)
            while len(answers) >= MAX_STATES:
                answers.pop(next(iter(answers)))
            answers[key] = answer
        return copy.deepcopy(answers[key])
    validate.replayed_per_state = True
    validate.thread = threading.get_ident()
    return validate


def _bindings(frozen):
    """Every module namespace that binds one of the frozen helpers by name."""
    found = []
    for module in list(sys.modules.values()):
        name = getattr(module, "__name__", None)
        if not isinstance(name, str) or not (name == "sec_http" or name.startswith("vnext.")):
            continue
        namespace = vars(module)
        for helper, function in frozen.items():
            if namespace.get(helper) is function:
                found.append((namespace, helper))
    return found


@contextlib.contextmanager
def run_checks_replay_once(*, replays=None):
    """Answer checkpoint replays and the replay's log helpers once per value.

    ``replays``, when given, is a list that receives one item per frozen
    replay actually run, so a caller can report how many there were.
    """
    from . import ordinary_source_authority as authority
    current = authority._validate_checkpoint
    if getattr(current, "replayed_per_state", False) is True:
        _need(current.thread == threading.get_ident(),
              "HISTORICAL_RUN_REPLAY_BLOCK_OPEN_IN_ANOTHER_THREAD")
        yield
        return
    _need(not getattr(current, "replayed_once", False),
          "HISTORICAL_RUN_REPLAY_BLOCK_INSIDE_THE_PLANNER_BLOCK")
    frozen = _frozen_helpers()
    _need(all(getattr(function, "__module__", None) == "sec_http" for function in frozen.values()),
          "HISTORICAL_RUN_REPLAY_HELPERS_ALREADY_REPLACED")
    memos = _helper_memos(frozen)
    swapped = []
    try:
        authority._validate_checkpoint = _replayed_per_state(
            current, replays if replays is not None else [])
        for namespace, helper in _bindings(frozen):
            namespace[helper] = memos[helper]
            swapped.append((namespace, helper))
        yield
    finally:
        authority._validate_checkpoint = current
        for namespace, helper in swapped:
            namespace[helper] = frozen[helper]
        # A module first imported inside the block bound the memoized helper.
        for namespace, helper in _bindings(memos):
            namespace[helper] = frozen[helper]
