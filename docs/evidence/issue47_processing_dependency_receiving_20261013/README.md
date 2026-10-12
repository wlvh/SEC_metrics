# Historical consumer of the shared processing-dependency check

This is an offline consumer verification of public PR207, composed with actual
main `8876b2e06c509ccc4e39df5e9675cc7dd097a221` (including received PR204) and
PR205/206. It adds one test to the existing historical D01 module; no second
checker, controller, runtime audit or test runner is introduced.

The test calls the real selected-year Candidate, Evidence, Review and Calculator
on constructed two-heading and 65-heading sources. Ordered text and the two
renderer identities are checked. The common PR207 observer finds no undeclared
called processing module. Removing either actually called `scope_contract.py`
or `states.py` from the historical declaration makes the same check fail.
These constructed sources are controls, not financial business acceptance.
Existing PR204 covers version-change reprocessing, stable reuse and old-result
preservation; those real company executions are reused without repetition.

The first harness incorrectly expected `text_results_v2.py` to execute in the
65-heading case. Actual D01 code uses the renderer in `text_results.py`; the
unused-call assertion was removed, while renderer identity and all observed
module assertions remain. `initial-harness-assumption.log` preserves the failed
24-test run. `targeted.log` records 24 tests, 0.837 seconds, zero failures,
errors or skips on the actual composed code.

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. python3 tests/required_unittests.py \
  tests.vnext.test_historical_risk_heading_case \
  tests.vnext.test_selected_history_result_state \
  tests.vnext.test_processing_dependency_checks
```

The two adjacent workflow/list conflicts were resolved exactly as authorized by
the public owner: preserve cover-DEI and single-segment selectors, add the
shared dependency fast/material selectors, retain the explicit workflow step,
and change no runner function or timeout. PR207's imported original failure logs
contain two trailing whitespace lines; these original logs were not rewritten.

## Separately confirmed receiving defect

The PR206 review `discussion_r4250924956` was actually read and independently
reproduced. `probe_wrong_column.py` uses the existing small single-segment
fixture: one annual header covers two columns, revenue occupies column 1,
while cost and net income occupy column 2. Current common scope code returns
`complete_scope_proven=true`. Sharing a year header does not prove a complete
statement in the revenue column. The raw constructed input and outcome are
saved here. The public owner repairs the shared reader; historical code does
not implement a competing selector. The known defect must be fixed before
receiving affected PR205/206, despite earlier original-source acceptance.

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. python3 \
  docs/evidence/issue47_processing_dependency_receiving_20261013/probe_wrong_column.py
```

Original sources, model answers, failures and old results remain unchanged.
New SEC/provider/paid calls: 0/0/0. This verification does not complete D01 for
all years, the historical model chain or Issue47's full five-year objective.
