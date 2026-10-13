# Additive feature declarations actually reach the workflow entry

The workflow's `run_foundation_ci.py` partition previously consumed only the
inherited selector list. `run_fast_tests_v2` successfully loaded the new
feature JSON declarations, but that alone did not make this different entry
execute them. The defect affects both fast and source-material declarations;
green checks on PR238/239/241 did not independently certify their new feature
modules. Their separately executed local tests and actual-source evidence
remain valid with their original scope.

The finite fix consumes v2's already validated feature declarations in the
existing foundation partition. Baseline order/retired selectors remain; new
selectors append in their declared tier. Whole coverage, no duplicate and no
cross-tier overlap checks include both baseline and features. The unchanged
runner still rejects failure, empty execution and unexpected skips. This does
not replace the runner or reintroduce retired proof checks.

`before-controls.log` reproduces the missing tier membership and duplicate
coverage checks. `final-cli-controls.log` executes 17 registry/runner controls,
0.007 s, zero failures/errors/skips. A two-case isolated module is actually
loaded by the CLI: both baseline and newly declared test execute, rather than
only asserting selector strings. Failure/skip and source-worker dispatch
controls remain. `after-controls.log` preserves an initial wrong test module
name; the real existing registry tests are `tests.test_selector_registry`.

Actual workflow command, Python 3.12.14/tokenizers 0.22.2:

```sh
TMPDIR=/private/tmp PYTHONPATH=scripts:tools:. \
  /private/tmp/issue28-d03-tokenizers-20261013/bin/python \
  tools/run_foundation_ci.py --suite fast
```

`fast.json` / `fast.exit`: exit0/PASSED, 87 fast selectors including the
main's 13 additive declarations, 392 tests, zero failures/errors/skips. In-
process tests took 73.715410 s; runner duration75.561210 s includes collection.
`selected-fast.json` and `selected-source.json` record the real CLI's two
lists: source-material has44 selectors. Source declarations enter that tier;
this author did not rerun all44 large original-source suites. Remote execution
and reception are separate from the local fast result.

The initial detached-shell launcher PID39741 disappeared and produced no
completion receipt. Its empty `detached-launch-fast.*` files are not a pass or
a verified live wait. The actual run used a persistent tool session73402 with
nohup and a completion receipt; it completed normally. No business/model
request, ledger or shared long-running operation was restarted.

Production changes are limited to `tools/run_foundation_ci.py`, plus its
existing tests. `run_fast_tests_v2.py`, workflows, test content outside those
runner controls and required-check settings remain unchanged. Source tests
continue through their existing worker/timeouts. No new provider/paid/SEC
calls or business/production acceptance follows from this CI repair.

Normal reception of actual main293e495f (received PR239/241) is local38599d1f.
The affected31 registry/runner/new-feature controls pass0.356s, zero skips.
`combined-fast.json` / `.exit` execute the actual workflow entry on this
combination: exit0, 89 fast selectors, 15 additive declarations, 406 tests,
zero failures/errors/skips. Both `test_saved_legal_review` and
`test_known_history_partial_scope` are in the actual executed selector list.
Tests73.612954s; runner74.861808s. This new execution closes the concrete
coverage gap for those two received modules; it does not reassign their
original green checks as if they had run these tests earlier. Main has not
yet received this runner change; reception remains a separate action.
