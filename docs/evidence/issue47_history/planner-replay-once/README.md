# One checkpoint replay per ledger state, not one per check

## What was slow, measured

The acquisition driver restarted at 19:57Z with one plan per company was still
planning Ford's first pass half an hour later. A bounded profile of the same
frame on the root restored from the export at 288 captures (zero calls,
`cProfile` for 300 seconds) finished 7 saved-dependency checks in 300 seconds:

- `normal_history_plan._saved_state` -> the frozen
  `ordinary_source_authority.verify_ordinary_source_proofs` ->
  `_validate_checkpoint` -> the frozen
  `continuous_sec_acquisition.validate_acquisition_checkpoint`: 296 of the 300
  seconds, 42 seconds a call;
- inside one replay, every capture's request binding is checked again against
  the whole request log (`batch_workflow.validate_request_attempt_binding`
  parses the log and computes every row's attempt id each time), so one replay
  grows with the square of the captures;
- the planner, the event declaration and the governance declaration all check
  each saved dependency through `_saved_state`, and the governance
  declaration's annual inputs check again per period (measured on a recorded
  root: once the planner's checks were memoized, 1 replay came from them and 9
  from three periods' inputs).

So a frame's cost grew with the cube of the captures. At 288 captures the
frozen path replayed 65 times for Ford's frame (2,181 seconds) and 57 times for
Macy's (1,961 seconds). Near the cap a single replay is estimated at a quarter
of an hour. The driver was stopped at 20:27Z while Ford's pass was still
planning: slots, claim log and export all at 368, nothing claimed since the
restart.

## The change

`normal_history_plan.checkpoint_replayed_once()` is a block. Inside it the
frozen verifier's replay - which it looks up in its own module at call time -
is the same frozen function behind a memo keyed on the state that replay
reads:

- the request log, its manifest and the registry, read the way the replay
  reads them (`resolve_repository_file`, which refuses a symlinked component)
  and taken by content, and the code tree's baseline manifest, the checkpoint
  and the baseline by content;
- every directory and every entry under the root's `evidence/` by its own
  status: kind, size, link count, device, inode, and modification and change
  times.

A replay that raises is not remembered; the answer is handed out as a copy; the frozen function is put back on the way out whatever
happens; a block inside another keeps the outer memo; a block is for one
thread, and one entered from another thread while a block is open is refused.
Every proof is still checked by the frozen code against the replay's answer.
`plan_historical_sources` and `historical_source_acquisition.declared_frame`
run inside the block.

What the key cannot see is a change that leaves all of the above as it was;
the change time is set by the kernel on every write, link or time change, so an
ordinary writer cannot do that. One direction differs from the frozen code on
purpose: a symlinked request-log manifest makes the key refuse where the frozen
replay would read through it.

The planner is now also in the SEC wiring receipt's evidence set
(`historical_sec_session.REQUIRED_WIRING_EVIDENCE`). It is a rule file, bound
by the Requirement closure, but the live path checks the receipt and not the
closure, and a weakened memo would weaken every saved-source check a frame
makes without the live path noticing.

## Independent review

A separate agent with a fresh context (same model family, not a human)
reviewed the first version before any request: PASS_WITH_FINDINGS
(`review.md`). What it found, and what changed:

1. **Medium - the real-root comparison recorded frames that differ.** The
   first measurement overlapped the first injection run, which rewrote the
   planner in the shared checkout; the planner hashes its own file when a plan
   ends, so the frozen frames carried an injected planner's hash. The reviewer
   reproduced both frozen hashes exactly by substituting only that hash into a
   fresh memo frame. `measure.py` now hashes the code files before and after
   each company and refuses a company whose files moved, and records every
   differing field instead of two hashes; the injections are run only while
   nothing else reads the checkout.
2. **Medium - the memo lived in a file the live path's receipt did not pin.**
   The planner is now in the evidence set.
3. **Low - the key missed state the frozen replay checks**: a second hard
   link, a same-size rewrite with its modification time put back, a directory
   named like a header sidecar, a symlinked `config/`. Each is now in the key
   (link count, change time, directories, the registry read through
   `resolve_repository_file`), and each has a case over the two-capture root
   that changes capture A while checking capture B's proof - which B's own
   proof check cannot see. The change time, the directories and the registry
   read are each the part a case fails without (`injections.py`). The link
   count is not: a second link also moves the file's change time, so the case
   still passes with the link count taken out, and so would one for the
   device, inode, size, kind or modification time. They stay in the key
   because they are what the frozen replay itself checks about a saved file;
   the change time is what makes a missed one visible.
   The review also suggested reading the state again after each replay and
   storing the answer only if it had not moved. That was built and then
   removed: its injection was caught by no case, and none can be written,
   because the change time of anything under `evidence/` only moves forward -
   the state an answer is stored under is never seen again once a file there
   changes - and a change to a content-keyed file outside it (the registry, the
   code manifest) makes the frozen replay refuse, which stores nothing.
4. **Low - two key components were untested** (the registry and the code
   manifest) and the fingerprint's only case changed the checked proof's own
   file, where the per-proof check refuses regardless. Both components have
   cases now, and the fingerprint cases change another capture's file.
5. **Low - not thread-safe.** Guarded: a block entered from another thread
   while one is open is refused.

The reviewer's answers to the rest: the memo cannot admit an undeclared URL or
move the per-request gate; the SEC session's own registration still calls the
frozen validator directly, once, outside the block, as do the export and the
restore; the only divergence possible is a saved row reading as verified, or a
governance period being declared instead of recorded as a limitation, for a
change a non-cooperating writer makes during one frame.

## Not fixed here: the same replay when a Run is created

Creating a historical Run checks each saved source through the same frozen
verifier, and so replays the same checkpoint. The batch installs a fresh data
root for every position, and `checkpoint_installation` copies every captured
attempt into it, so each position pays at least two whole replays (the
creator's and the separate-process cold read's) even inside a block. The
targeted round spent about half an hour per Macy's position; after the
acquisition, a full-frame batch of that shape would not finish.

Measured so far (`run-creation/`, zero calls): one frozen replay at 288
captures takes 26.1 seconds; its quadratic parts are all pure functions of the
request log's text - parsing the log (12.7 of 40.9 profiled seconds), the
ledger prefix per capture (11.6), every row's attempt id per capture (10.1),
the manifest check that parses again (7.4). A prototype that memoizes those
helpers for one block returns the same answer in 11.2 seconds. That is not
enough by itself: at the cap it would still be about a minute per replay. The
next step is to install every metric of one period into one data root, so the
period pays a handful of replays instead of two per position; that has to be
shown to give the same Runs before a batch uses it.

## Verification

- `tests/vnext/test_historical_plan_replay.py` over a recorded root (the
  baseline corpus plus two registered captures with different bodies): 15
  cases.
- `measure.py` on the root restored from the export at 288 captures, both
  companies at the same time in separate processes, nothing else reading the
  checkout, the six code files hashed before and after each company and
  unchanged throughout (`measured.json`; the hashes it records are the ones
  committed with this change):

  | company | requirements | verified saved | frozen: replays, seconds | block: replays, seconds | frames |
  |---|---|---|---|---|---|
  | Ford | 273 | 49 | 65, 1905 | 1, 138 | identical, 0 fields differ |
  | Macy's | 157 | 41 | 57, 1650 | 1, 104 | identical, 0 fields differ |

- `injections.py` -> `injections.json`: fourteen injections, each undoing one
  part, plus one that takes out the link count, which no case should fail
  without. Every one of the fourteen was caught by the case written for it, and
  the link count was caught by none, as it should be (`all_caught`,
  `redundant_parts_not_caught`). Each injection rewrites the planner in the tree
  it runs in, and the acquisition this change unblocked read the checkout and
  checked the planner against the SEC wiring receipt, so they ran in a separate
  clone of the checkout at `338cb049` - the planner, its cases and this script
  byte-identical to the checkout's - while the acquisition went on, not in the
  checkout itself. `injections-first-version.json` is the run against the first
  version, kept as what it was: it overlapped the first measurement (finding 1
  above), and its one miss is the post-replay recheck that was since removed.

Zero SEC or provider calls.
