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
