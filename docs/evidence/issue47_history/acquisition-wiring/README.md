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
