# Issue #47's acquisition chain, exercised before it is authorized

`tools/vnext_historical_sec.py capture` used to refuse with
`ISSUE_47_SEC_EXECUTION_NOT_WIRED` **even when an allowance existed**, because
the execution path did not exist. It was the plainest counter-example to a
sentence this issue had written and withdrawn - "no wiring work left that is
not blocked on material or allowance" - and connecting an allowance check, a
cumulative count, a request, an immutable save and a source installation needs
no grant at all.

It refuses now for the other reason:

```
$ python3 tools/vnext_historical_sec.py capture --company marriott_international \
    --url https://www.sec.gov/Archives/edgar/data/1048286/000162828021002433/index.json
{"calls": [0, 0, 0],
 "reason": "ISSUE_47_SEC_ALLOWANCE_NOT_GRANTED:config/issue47_historical_calls_v1.json:needs
            requirement_id,delegation_url,delegation_body_sha256,budget_root,
            maximum_additional_provider_paid_sec_calls,scope,sec_wiring_receipt_path",
 "status": "REFUSED"}
```

That is the whole point of the change. A refusal that names a missing grant is
a different statement from one that names a missing implementation, and only
the first one is true today.

## Why a new session rather than Issue #28's

`SecAcquisitionSession._check` asserts `requirement_id == issue_28_v14`,
`limits == [240, 240, 80]`, Issue #28's budget root and Issue #28's own offline
wiring receipt; `live_ledger` calls `load_delegation`, which refuses any other
requirement by name. Running Issue #47's fetches through it would draw on Issue
#28's allowance, which this issue's text forbids. `continuous_call_ledger.py`,
`continuous_sec_acquisition.py` and `continuous_call_policy.py` are all in the
approved call policy's `rule_paths`, so none of them can be widened either.

**Capability is reusable, authorization is not.** So the transport
(`SecHttpClient`), the attempt primitives, the source-installation shape and
the provenance validator are the existing ones; the allowance, the cumulative
count and the ledger are new.

## What guarantees the sources this produces

`scripts/vnext/historical_sec_session.py` is not a rule file, and the reason it
does not need to be is that the checkpoint it writes is replayed by
`continuous_sec_acquisition.validate_acquisition_checkpoint`, which is frozen
under `issue_28_v14` and cannot be edited from this issue. That validator
re-reads the ledger prefix, every capture's row binding and every successful
capture's immutable attempt. The provenance claim therefore does not rest on
this module's bytes.

Measured end to end: the unmodified downstream
(`ordinary_source_authority.checkpoint_installation` and
`verify_ordinary_source_proofs`) finds the checkpoint, names the two dependency
paths to carry, and accepts the proof.

**What the shared checkpoint does not say** is which issue's allowance paid for
a row: its record carries mode and captures, not an issue. So a checkpoint in
the shared journal is not Issue #47 credit by itself. Attribution lives in this
issue's own ledger slots, which name `issue_47_v1`, and in the attribution
record written beside them.

## What the fault injections found

Four injections were run against the suite; two of them found real gaps.

| injection | caught? |
|---|---|
| count only successful slots | yes - the failure case |
| drop the early unresolved-terminal check | yes - found a real bug first (see below) |
| skip the frozen validator in `register_checkpoint` | **no, until two cases were added** |
| enroll in the journal before validating | yes, by the added case |

The third is the one worth recording. Replacing the
`validate_acquisition_checkpoint` call with `pass` left all sixteen cases
green, because they exercised the validator **directly**. Proving the validator
works is not proving this session calls it, and the module's central claim had
no case defending it. `TheSessionActuallyRoutesThroughTheFrozenValidator` now
wraps the real validator, requires exactly one call over this session's own
installed root and the record it returns, and separately requires that a
refused replay enrolls nothing.

The second injection is not hypothetical either: the early
`require_unblocked()` call exists because writing the case revealed that an
unresolved terminal did **not** stop a capture. The already-saved short circuit
returns before the claim, so a session whose previous slot had no terminal
would happily answer "already saved, no call needed" against a ledger whose
count it could not account for - the answer that looks harmless is exactly the
one that slipped through.

## Regenerating the receipt

`offline-wiring-receipt.json` is produced by **running** the chain, not by
describing it:

```
python3 tools/vnext_historical_sec.py wiring-receipt --output <new file>
```

A live session verifies it through the allowance's `sec_wiring_receipt_path`
and re-hashes every file it names, so **regenerate it after changing any of
them** - the two modules, the test module or the CLI. That includes the test
module on purpose: the receipt's `fault_injections_caught` claim rests on those
cases, so weakening them must invalidate it. This is the same discipline as
`tools/vnext_mint_historical_requirement.py`, and the same failure mode if it
is skipped - evidence describing a version that is no longer the one that would
run.

## What this is not

No SEC request has been made. Every record here is `RECORDED_TEST_ONLY` with
`real_sec_credit: false` and `production_authorized: false`, and the recorded
constructor refuses any configured budget root so a test can never write where
a granted count is kept. The acquisition plan's scope, ceiling and counting
rules are unchanged, and Issue #28's allowance is neither read nor borrowed.

## Four defects an external review named, all reproduced before being fixed

The previous section ended with "the chain is wired, only the grant is
missing". That was too early. A review of `2293330` named four defects; each
was reproduced against the tree first, because a review is a lead and a
reproduction is a fact.

### 1. The allowance checked that fields existed, not that a grant held

`live_historical_session` verified only that `delegation_url` and
`delegation_body_sha256` were non-empty. Nothing read the body those fields
describe, and nothing compared the request against an approved scope.

Reproduced: a policy carrying `delegation_url = "NOT-A-URL-AT-ALL"` and
`delegation_body_sha256 = "NOT-A-DIGEST"` **built a LIVE session and passed
the pre-request check**. A digest nothing is hashed against is decoration.

Now: shapes are typed (64-hex digest, an issue-comment URL, three non-negative
limits, a scope carrying companies, dependency classes and a period window);
the approved body named by `delegation_record_path` is read and re-hashed
against the declared digest; and the body must restate the limits, budget root
and scope, so the policy file cannot grant more than the approval did - it is a
pointer to an approval, not a second place one can be written. Every capture
then passes `request_is_in_scope`, over the company, the dependency class and
the target periods the dependency serves.

### 2. A terminal file was treated as an outcome

`snapshot()` asked only whether `terminal.json` existed. But `capture` writes a
terminal for an unknown outcome too, so the one case the rule exists for was
the one it stopped catching.

| what the previous slot held | did the next claim proceed? |
|---|---|
| no terminal file | blocked, as intended |
| a known failure, sealed | proceeded, as intended - failures count |
| **a sealed `UNKNOWN_REMOTE_OUTCOME`** | **proceeded** |
| **a terminal whose content was `{}`** | **proceeded** |

Now four states are distinguished and named in the refusal: `TERMINAL_ABSENT`,
`TERMINAL_RECORD_DAMAGED`, `TERMINAL_BOUND_TO_ANOTHER_INTENT`,
`OUTCOME_NOT_KNOWN:<status>`. Only a well-formed terminal for this intent
recording a known outcome resolves the slot.

### 3. Belonging to the task and needing a fetch were one field

Reproduced, both directions:

- A declared dependency that was already saved was refused as **"not a declared
  dependency"**, because admission searched only the outstanding rows - so the
  reuse branch behind the gate was unreachable.
- A row the planner marks `SNAPSHOT_REFRESH` carries `VERIFIED_SAVED_SOURCE`
  **and** `new_acquisition_required` - intact bytes that disagree with the
  index they were declared under. `capture` read only the first field and
  returned `EXISTING_VERIFIED_SOURCE_REUSED`, so **the refresh never reached a
  request**.

Now `declared_dependencies` answers "does this belong to the task" and
`new_acquisition_required` answers "is a fetch due", and they are asked
separately.

### 4. The wiring receipt could pass on flags it wrote about itself

Two problems. `verify_offline_wiring` iterated whatever the receipt listed, so
a receipt carrying `evidence: {}` **was accepted** - the loop ran zero times.
And the builder wrote `frozen_validator_routing_verified: true` and
`fault_injections_caught: true` unconditionally, having run neither: a file
hash proves which version a test file is, never that the version was executed
and passed.

Now the evidence set must equal `REQUIRED_WIRING_EVIDENCE` exactly, so removing
a file removes the grant rather than the check; the receipt carries a
`verification_run` block that is the measured outcome of running the suite in a
subprocess; and fault injections, which require editing the source and
re-running and so cannot be performed by any single process, are recorded in
`fault-injections.json` - which the receipt hashes - rather than asserted as a
boolean. The builder deliberately excludes the class that verifies this
receipt, and names the exclusion, because including it would make the evidence
circular.

### What the frozen validator proves, stated narrowly

Reusing `validate_acquisition_checkpoint` was right and the two cases that
require this session to route through it are kept. But it proves that the
saved original, the request row, the immutable attempt and the source proof
agree with each other. It does **not** prove that a grant is valid, that a
request is in scope, that the cumulative count is intact, that an unknown
outcome stops the channel, or that a stale snapshot gets refreshed. All four
defects above sat in exactly that gap, so "the source check rests on frozen
code" never implied this module's own bytes needed no discipline.

### Still open: the event class is not in the declaration

`plan_historical_sources` declares four dependency classes -
`ACCESSION_INSTANCE_DISCOVERY`, `ANNUAL_PERIOD_IDENTITY`, `COMPANYFACTS`,
`SUBMISSIONS_INDEX`. **None of them is the event window's 8-K bodies and
headers**, which the acquisition plan sizes at 485 filings and 970 attempts.
So the one worked example here, a Marriott accession index, does not show that
the event class is reachable through this gate - it is not.

That file is a `NEW_RULE_FILE` of `issue_47_v1`, so extending it moves the
Requirement closure and the 343 frozen Runs of the last batch stop being
evidence for the version that would then run. The fix is a successor
declaration that unions the planner's rows with the event dependencies, in a
file that is not closure-bound, and it is not written yet.

## The next review found that the previous round's fix broke the legitimate path

The sharpest finding first, because it is the pattern rather than the bug: the
scope gate added to close finding 1 **refused most of the real declaration**,
and the case written to prove the refresh fix did not catch it.

`request_is_in_scope` required every dependency to carry a `period:` consumer.
Measured against the production planner's own rows:

| dependency class | consumers the planner emits | old gate |
|---|---|---|
| annual primary, accession index | `period:2025-12-31` | passed |
| submissions index | `historical_catalog` | **refused** |
| history shards | `historical_catalog` | **refused** |
| Company Facts | `A05`, `B02`, … | **refused** |

For JPMorgan that is **71 of 75 rows, including all 69 history shards and all
12 `SNAPSHOT_REFRESH` rows** - the exact population the refresh fix existed
for. So the previous round's "refresh now reaches a request" was true of the
branch and false of the system.

The refresh case missed it because it took a Marriott row that needed
acquiring and **edited** it into a refresh, keeping the annual row's period
tag. A hand-made row cannot show that the real ones pass.

The fix is not to drop the window check but to name the right window. A
dependency that serves named periods is checked against those; one that makes
the targets discoverable at all - an index, a shard, Company Facts - is
checked against the frame's own target window, and the admission record says
which basis it used. All 91 real rows across both companies now pass, and
wrong company, wrong class, wrong window and wrong purpose still refuse.

`TheScopeGateMustPassTheRealDeclaration` iterates the planner's live output
rather than a fixture, so this class of mistake fails here rather than in
production.

## Three further findings, each reproduced

**A grant was still two local files agreeing with each other.** Reading the
body and re-hashing it stopped "only one file changed", but both files came
from the same tree, so an approval could be written by the executor and
confirmed by the executor's other file; the URL check accepted any
repository's issue comment. Now the policy declares `repository` and
`approver_login`, the URL must be a comment on **this** repository's issue 47,
the comment's `id`, `issue_url` and author must agree, and the live path
supplies a reader that fetches the comment from GitHub and requires the saved
record to match it byte for byte. An offline read returns
`provenance_verified_against_github: false` rather than silently looking the
same.

**A terminal named a receipt that nothing read.** A sealed terminal naming a
missing receipt, or one belonging to another request, left the channel
unblocked and the next claim succeeded. The frozen source validator would
refuse such a ledger, but only after the next request had gone out, and this
check exists to run before it. Five more states are now named:
`RECEIPT_ABSENT`, `RECEIPT_RECORD_DAMAGED`, `TERMINAL_NAMES_ANOTHER_RECEIPT`,
`RECEIPT_BOUND_TO_ANOTHER_INTENT`, `RECEIPT_AND_TERMINAL_DISAGREE`.

**The receipt attested a run that excluded every regression of the round that
produced it.** The selector list named eight classes and was never revisited
when sixteen cases arrived, thirteen of which do not read the receipt at all.
The list now holds fifteen classes, the two that read the receipt are named
with their reason, and `unclassified_verification_cases()` makes a class that
belongs to neither set a failure - it caught four of this round's own new
classes immediately. The receipt went from **18 tests over 8 classes to 48
over 15**.

The CLI also reported the ledger's running total in the same `calls` field
that carries a single invocation's count on success. They are now `calls` and
`cumulative_calls`, because a caller that adds up the first must not add the
second.

## Injections, re-run against the current tree

| injection | caught by |
|---|---|
| require a `period:` consumer on every row | 4 of the 5 scope cases |
| drop the fetched-vs-saved body comparison | the locally-written-pair case |
| stop reading the receipt a terminal names | all three receipt-binding cases |
| leave a new test class out of both selector sets | the classification case |

## A test-hygiene defect that masqueraded as 21 code failures

Mid-round the suite reported 21 errors on an unchanged tree. The cause was
`No space left on device`: every recorded session installs a full baseline
corpus, and the shared fixture never removed its temporary root, so repeated
runs filled the disk. The fixtures now register their own cleanup. Recording
it because the failure looked like a code regression and was not - and because
a leaking fixture will eventually be blamed for a defect it did not cause.

## The approval authority now comes from outside the file being verified

The previous round read `repository` and `approver_login` out of the same
policy it was checking, so the file chose its own authority. One-sided cases
were tested and refused; the case where both sides move was not.

Measured against that version:

| what moved | old result |
|---|---|
| the comment's author alone | refused, correctly |
| **the author *and* `approver_login` together** | **accepted** |
| the comment URL alone | refused, correctly |
| **the URL, the issue and `repository` together** | **accepted** |

`TRUSTED_REPOSITORY` is now a constant in the module, with the approver being
its owner - the shape Issue #28's frozen `validate_comment` already uses,
where the repository is bound from outside the record and the comment's author
must be that repository's owner. The allowance may restate the anchor; it may
not choose it. Both "together" cases now refuse by name, the legitimate grant
still passes, and a case asserts the constant agrees with the repository named
in the already-committed call policy, so the constant is not its own only
witness. Borrowing that repository identity is not borrowing that issue's
grant.

## A per-invocation count is not a difference in a shared total

The CLI reported one call for this invocation whenever the ledger's SEC total
had grown between two reads taken around a capture. Those reads are not inside
the capture's lock, so this interleaving attributed another process's request
to us: read total, another process completes a request, we refuse before
claiming, read total again, report one call.

The session now records the slots it claims and reports from those.
`calls` is what this session claimed; `cumulative_calls` is the ledger's
total, which a caller must not add to anything. A case drives the interleaving
directly - two sessions on one ledger, the other one captures, ours refuses -
and requires ours to report zero while the shared total has provably moved.

## The test machinery left the business module, and the artifact became one command

Six times in this issue the receipt went stale, and each time the cause was
the same shape: producing it was a sequence a person had to get right. Two
selector lists lived inside `scripts/vnext/historical_sec_session.py` and had
to be edited whenever the suite gained a class; the builder ran through the
acquisition CLI into a file outside the checkout; that file was copied to its
committed path by hand; and the commits had to be ordered so the copy landed
after the last edit to anything it hashed. 200 of that module's 894 lines were
`importlib`, `inspect`, `unittest` and `subprocess` - a business module that
could not honestly be said to load in a runtime with no test package, while
the check that gates a live grant sat in the same file.

Three things had to become true, and each is asserted rather than described.

**The business module loads where there is no test package.** It now holds
`execute_recorded_chain` (the chain), `seal_wiring_receipt` (the record) and
`verify_offline_wiring` (the gate), and imports none of `unittest`,
`importlib`, `inspect` or `subprocess` - asserted over the module's whole
parse tree, including function-local imports, not by grepping for the words,
because the module still names the suite file (it hashes it) and still
explains in prose what used to live there.
`TheBusinessModuleLoadsWhereNoTestPackageExists` runs a child whose `sys.path`
has the repository root removed and `scripts/` added, requires `import tests`
to fail there, and then requires the gate to verify the committed receipt
anyway.

**An ordinary new test requires no edit to any list.** `declared_cases()` in
`tools/vnext_historical_wiring.py` reads the suite module and returns the
`TestCase` subclasses it declares - inherited ones do not count, or the
receipt's accounting would disagree with what ran. The one hand-written list
left is `RECEIPT_DEPENDENT`, and it is checked against what the classes do:
a class is excluded exactly when its source names the installed receipt. That
check fails in both directions - a class parked in the exclusion without
reading the receipt stops running and nothing notices, and a class that does
read it, left in phase one, makes the artifact unrebuildable after any change,
because phase one runs before the new receipt is installed.

**From a fixed candidate to a usable artifact is one determinate operation.**
`python3 tools/vnext_historical_wiring.py` drives the chain, reads the suite,
runs everything that does not read the receipt, seals, installs at the
committed path, then runs the receipt-dependent classes against the installed
file. A failure anywhere restores what was installed before, byte for byte,
and exits non-zero, so a failed run releases nothing. That is not only
asserted in three cases; it was observed on the first real run of this tool,
which failed phase two on a defect in one of the new cases and left the
committed receipt byte-identical to `HEAD`. `--check` answers the cheaper
question - is the installed artifact still true of this tree, and does it
still account for the suite as it stands - without rebuilding.

What the verifier gained rather than lost. It used to compare the receipt's
selectors against a literal list in the same module, which is both the reason
an ordinary test was an edit to business code and something unavailable in a
runtime with no test package. It now checks the accounting as a property of
the record: `classes_run` and `classes_excluded` must partition
`classes_declared`, with no overlap and a non-empty run. A green run that
covered nine of twenty-one classes - the defect the previous version shipped -
is refused by name. The collector that produced those three sets is itself in
`REQUIRED_WIRING_EVIDENCE`, so a builder weakened to declare less changes its
own bytes and the grant falls with it; and the collector is cross-checked in
the suite against a second, independent derivation that parses the test file
rather than introspecting the imported module.

What this does not fix. A receipt is still a record of a run, so a builder
corrupted and then re-run produces a smaller receipt that is self-consistent;
what the hashes establish is that the artifact on disk corresponds to this
builder and this suite, which is the same property `mint` has and not a
stronger one. The candidate-identity check is unchanged: editing any hashed
file still invalidates the receipt. What changed is that restoring it is one
command instead of five steps, so the discipline is enforceable rather than
remembered.

## Correction: failing safely is not the same as never having exposed it

The section above says a failed run "restores what was installed before, byte
for byte", and offers as evidence that the tool's first real run failed phase
two and left the committed receipt byte-identical to `HEAD`. That observation
is true and the restore did work. **It is not the property the build needed**,
and an external review measured the difference.

The order was: write the new receipt to the installed path, run phase two,
restore the old bytes on failure. So between the write and the verdict there
is a window in which the new receipt is installed and has not finished being
checked - and `verify_offline_wiring` has no way to know that, because it
checks file hashes and the recorded phase-one run, not whether a phase two is
still in flight. Three states, measured:

| state | observed |
|---|---|
| both phases pass | build succeeds; gate and `--check` accept |
| phase two returns a failure | **the gate and `--check` accepted the new receipt before the failure was returned**; the old file was then restored |
| the phase-two process is killed before the restore can run | **the unchecked receipt stays installed; the gate accepts it and `--check` returns `OFFLINE_WIRING_CURRENT`** |

The three cases written for the restore could not see any of this: they look
at the installed file *after* the run, and a restore makes the end state
identical either way.

**The fix is the order, and it deletes code rather than adding it.** The
receipt is now written to a candidate path beside the installed one; phase two
is told, by name, to check that candidate; only a pass reaches the installed
path, through the repository's existing `atomic_write_bytes`. There is no
backup and no restore, because there is nothing to undo: a failure or a kill
leaves the previous bytes, or no file where there was none, without any code
having to run to make that true. The candidate is removed in a `finally`, and
a stray one is inert - a grant names the installed path and nothing else.

Two things moved with it. The receipt-dependent cases no longer hard-code the
installed path; they ask `_receipt_under_check()`, which reads
`ISSUE_47_WIRING_RECEIPT_PATH` and falls back to the installed path for
standalone runs, so phase two checks the file this run produced rather than
the one the previous run left. And the rule that decides which classes are
receipt-dependent now matches either spelling - asking for the receipt under
check, or naming the installed file - with its tokens assembled outside any
class body, because the first version spelled them inside the class doing the
scanning and flagged itself.

The injection is recorded as `INSTALL_FIRST_AND_RESTORE_AFTERWARDS`, with the
three cases that **passed** under it named alongside the one that caught it.
Which cases cannot tell the difference is the whole point of the one that can.

## Scope of the "no test package" claim, narrowed

The same review narrowed a claim in the section above. What
`TheBusinessModuleLoadsWhereNoTestPackageExists` proves is that the module
loads and the gate answers when `tests` cannot be imported and no test
framework runs. It does **not** prove the module is independent of the test
sources on disk: `REQUIRED_WIRING_EVIDENCE` names the suite file, the builder
and the fault-injection record, and `verify_offline_wiring` refuses when any
of them is missing, because it re-hashes each one.

So the accurate statement is: **the dependency on an importable test package
and an executable test framework is gone; the dependency on the test sources
as read-only evidence remains, deliberately.** That is what binds a grant to a
specific suite. Shrinking a delivery bundle until it holds no test file would
remove the binding, not improve it, and is not being attempted.

## The event class the planner never declared

`plan_historical_sources` declares four dependency classes - the submissions
index, its history shards, Company Facts, and the two documents per annual
accession. It declares no event class, so every fiscal-year 8-K body and
header the zero-AI route reads for C01 and E01-E05 was refused by the gate as
`HISTORICAL_URL_IS_NOT_A_DECLARED_DEPENDENCY`. No grant could unblock those
coordinates while that held, whatever its scope said.

`scripts/vnext/historical_event_sources.py` declares them, and
`declared_frame` takes the union. It is a separate module because the planner
is a `NEW_RULE_FILE` of `issue_47_v1`: changing its bytes moves the
Requirement closure, and the previous batch's 343 frozen Runs are evidence
about the version that produced them. Being outside the closure is not being
outside the checks - the rows carry the planner's fields, are classified by
the planner's own `_saved_state`, go through the same scope gate, and the
module's bytes are in `REQUIRED_WIRING_EVIDENCE`.

**The acceptance is not that a class name appeared in a list.** A dependency
list can gain a name and be wrong in either direction: short, and the gate
refuses a file the route needs; long, and a grant is spent on files nothing
reads. So the case runs the frozen route's own source discovery over the
saved corpus with a recording reader and requires the declaration for that
period to be exactly the set of URLs the route asked for. Measured on
Marriott's newest period: 20 read, 20 declared, zero either way.

Measured across all ten companies: **354 event rows over 177 accessions, 60
rows still needing a fetch**, two requests per accession - which is measured,
not assumed, from 186 saved accession directories of which 151 hold both a
body and a header and none holds a header alone.

**Paramount is the corroboration worth naming.** Its 18 outstanding rows are
9 predecessor 8-K bodies and their 9 headers - the same nine this repository
recorded independently during the successor-event wiring round, by a
different path (31 predecessor filings in the window, 9 with no saved body).
Two derivations agreeing on the same nine is worth more than either alone.

**Why this is smaller than the plan's 970, and why that is not a correction
downward.** The event window comes from the target year's own document: the
fiscal year's start date is in its DEI context, not in the submissions row.
So a year whose annual primary is not saved has no derivable window, and the
module declares nothing for it rather than declaring zero filings - the two
read identically in a plan and mean opposite things. 31 of the frame's 50
periods are in that state, each with a named limitation pointing at the
annual primary that would unblock it. The declaration is therefore a floor
that grows as class A lands, not a replacement for the plan's estimate.
Deriving the window any other way would mean writing a second copy of a rule
the route already owns, which is the drift this module exists to avoid.

Two injections, both caught: dropping the header row from each filing, and
skipping an underivable window without recording the limitation. A third
thing the round found on its own: `recorded_historical_session` listed four
dependency classes in its default scope while the declaration emitted five,
so a recorded capture of a history shard was impossible and nothing said so.
It surfaced only because adding a sixth class broke an unrelated case, so the
default is now checked against the classes the declaration actually emits.

**No authorization changes.** `FISCAL_EVENT_FILING` is in no approved scope,
`config/issue47_historical_calls_v1.json` still does not exist, and `capture`
still refuses with `ISSUE_47_SEC_ALLOWANCE_NOT_GRANTED`.

## Grants: the approval's text and the gate's execution scope describe one set

The review of `0b7f1c9c` found the proposal saying two things. The plan's
text left JPMorgan's event windows out; the proposed scope was a cross product
- ten companies, seven dependency classes, one window - so the gate would have
admitted a JPMorgan event filing the text said was not covered. The scope now
carries **grants**: one per measured class and company group, and a request is
in scope only when one grant covers its company, its class and every period
it serves (`request_is_in_scope`). The envelope is checked to be nothing but
the grants' union (`_typed_grants`), so an envelope cannot be wider than what
the grants name.

| grant | companies | classes | window |
|---|---|---|---|
| `A_ANNUAL_CHAIN` | all ten | annual identity, accession discovery | frame |
| `A_JPMORGAN_METADATA` | JPMorgan | submissions index, history | frame |
| `B_EVENT_WINDOWS` | the nine others | fiscal event filings | frame |
| `B_JPMORGAN_FY2025_KNOWN_HEADER` | JPMorgan | fiscal event filings | 2025-12-31 only |
| `G_GOVERNANCE_PROXIES` | the nine others | governance filings | frame |
| `G_JPMORGAN_FY2024_PROXY` | JPMorgan | governance filings | 2024-12-31 only |

`COMPANYFACTS` is in no grant, because no class of the plan counts a Company
Facts request.

**The two failed headers.** The ledger holds exactly three URLs whose latest
GET failed. Two are event headers the declaration marks as needing a fetch,
and each blocks every event metric of its window (and C04 for Salesforce):
JPMorgan's `0000019617-25-000332.hdr.sgml` (FY2025) and Salesforce's
`0001108524-25-000083.hdr.sgml` (FY2026). Neither was in class B, which had
been counted from saved metadata for the earlier years' windows. Both are now
in class B by name, one attempt each: cap 1,352 → **1,354**. JPMorgan's header
enters through its own one-period grant; its FY2021–FY2024 event windows are
in no grant, because they cannot be enumerated until class A lands and have no
measured basis. The third failed URL is a `companyconcept` request no #47
route reads.

**Measured, not argued** (`proposed-allowance.json`, `execution_scope_census`):
every row the ten companies' declarations mark as needing a fetch, asked of the
proposed scope exactly as the gate asks it — A_ANNUAL_CHAIN 81,
A_JPMORGAN_METADATA 69, B_EVENT_WINDOWS 59, B_JPMORGAN_FY2025_KNOWN_HEADER 1,
G_GOVERNANCE_PROXIES 2; **refused: none**. The event and governance
declarations are floors that grow as class A lands (a year with no saved annual
primary declares no window), which is why the plan's class totals are larger
than today's declared rows; a JPMorgan earlier-year event row declared later
would be refused by name, `ISSUE_47_REQUEST_OUTSIDE_EVERY_GRANT`.

**The ledger path.** Proposed: `/Users/lyuhongwang/.local/state/sec_metrics/
issue47-historical-sec-v1` — beside Issue #28's root on the same host, so it
persists with the user's state rather than with a checkout, and is plainly a
different ledger. The gate refuses a relative path, a path with `..`, #28's
root or anything inside it, and anything inside the repository checkout
(`_typed_budget_root`): a ledger that is reset with the code is not a cap. The
owner confirms or replaces it when posting the comment; the proposal remains a
proposal until then (`provenance_verified_against_github` is `null`), and no
real request is sent before it.
