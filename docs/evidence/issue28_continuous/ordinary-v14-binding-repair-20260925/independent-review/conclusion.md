verdict: BLOCKED_SCOPED_ORDINARY_V14_BINDING
patch_sha: 5c307e55932a8c65dbd05ba8ce44d93b66b7c980
scope: Issue #28 current ordinary V14 execution binding, V15 parent identity, related wiring receipts and directed evidence only.

## Finding

- **P2 — current provider wiring receipt names an obsolete requirement closure.** `docs/evidence/issue28_continuous/b13-170-source-audit/offline-wiring.json:4` retains `sha256:c26a3552...`, while the patched V15 snapshot loads as `sha256:1f110dbc...`. The same receipt now describes itself as the current V15 closure and binds the new execution-authority hash. `scripts/vnext/continuous_call_wiring.py:10-22` checks the execution-authority hash and evidence but does not compare the receipt's declared `requirement_closure_hash`, so `validate_wiring_receipt()` passes this contradictory receipt. This is an evidence/identity mismatch, not proof that a provider call was made or that the runtime byte gate failed. Minimal repair: make the receipt's closure claim match the current loaded requirement and, if the field is intended to be an authority claim, reject mismatches in the receipt validator. Rebind only affected unfrozen V15 files and rerun the shortest no-network wiring check. Do not change historical calls or receipts.

## Verified within scope

- `normal_run_v3.REQUIREMENT_ID` remains `issue_28_v13`, with generation `PROFILE_DRIVEN_V14`; the shared `_binding()` code did not change in this patch. The v13 manifest changes only the current ledger file binding from 16070 bytes/`735accb3...` to 21018 bytes/`50ff87a4...`.
- The patched v13 loads as `sha256:ecaef229...`. V15's baseline parent and transfer parent both equal that identity, and the five parent-file bindings load. The new transfer mismatch test is effective; the two named directed test modules ran 8 tests, all passing. Both current execution-authority checks passed. The seven changed code/config/receipt input blobs in committed SHA match the hashes recorded in the author's earlier `after-uncommitted.json`; that log properly says its long tests ran on an uncommitted tree.
- The patch does not edit old Run packages, original call ledger, or shared normal-run code. The no-call 190 script and saved output report read-only selection of original ordinal 190 with unchanged 143/143/49 counts; I inspected these artifacts but did not independently replay the full old response or credit a complete B13 company.
- GitHub job `107690969253` is `cancelled`: it ran 14:58:28–15:33:43 UTC, while the material-test step ran 15:09:43–15:33:41 UTC. The README's separate roughly 35-minute job and roughly 24-minute test-step descriptions match those timestamps. The material test has no passing terminal result. `git diff --check` passed.

`targeted.log` is my 8-test execution. `authority.log` is my current loader/authority/receipt check demonstrating the mismatch. I did not rerun the author's 359/367-second update tests, complete saved-source materials, historical-package cold reads, or any paid/SEC request; their supplied logs remain execution-party evidence, not independent reruns.
