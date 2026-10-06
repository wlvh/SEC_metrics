# T1: current fast feedback from main8588

This branch starts from actual main8588; no PR43/PR52 implementation or call
history is imported. It changes the current CI entry, not the preserved old
runner. Ordinary fast tests use one unittest process and class/module fixtures;
source-material tests retain the existing independent material worker. The 119
old selectors are still accounted for exactly once (76 fast,43 material).
NormalAnnualInputTest methods read full originals and now belong to material,
rather than the 30-second small-unit tier. No business assertion is removed.
This first step does not retire all legacy proof tests or simplify company run.

Same saved code/scenario: six selectors,59 tests, all pass. Original per-selector
subprocess worker:2.727s; shared process:1.016s. The final output-capture version
passes the same59 tests in0.972s. This is a local comparison, not a CI speed
promise or a result-correctness acceptance.

Direct current CLI fast layer:273 tests,80.300s, zero errors/failures/skips. That
run included repository-path restoration but preceded stdout/stderr capture.
The only later runner change captures test prints in diagnostics to preserve
JSON; final five runner regressions and59 business tests pass. The complete
273 were not rerun for this unchanged business responsibility. The final diff
and this distinction identify the actual tested tree; it is not claimed as an
exact-final-SHA273 rerun.

The first direct CLI trial correctly reported76 module-import errors because
script invocation exposes tools/ rather than repository root. The current
function now adds the repository root before loading selectors. The failure
was not suppressed. Runner regressions cover shared preparation, assertion
failure, test exception, a missing selector, explicit skip reporting, failure
exit and capture of printed diagnostics. Full fast output originally contained
one test print; capture fixes its JSON format without changing test assertions.

The initial shell background launch left no live handle or terminal; it was
confirmed absent before using a detached nohup process. No project ledger,
source capture or paid call was run or cancelled. Existing workload/production
permissions do not change. Source-material43 were not rerun: business code and
assertions are unchanged, and this batch only changes their tier placement.
Future broader checks remain necessary for actual source/runtime changes.
