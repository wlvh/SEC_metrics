# Historical receipt of the bounded prior-year caption repair

Public PR210 **255251cf746b9016805ff63de5728f43cefaf3a6** is based on the
column correction PR209. This historical receiving branch combines actual
main31e4, fixed PR207 d65, PR208's saved-source export, and PR209/210. It adds
no income selector, classifier, controller or runner. Actual executed source
is **ffb2b12e00e99e86a98bcdb5583bf1791b1ae471**. All adjacent public runner additions were kept once;
no function or timeout changed. PR211 average-risk candidate stays separate.

## Actual affected consumer

The existing Enphase B02 task had FY2021 as a stable `CANDIDATE_WITHHELD`,
result `sha256:49953cb7b5040dbf84ce37b8563ed63ccf71ffe57035e8f73117402b0706be11`,
and correct FY2022/FY2023 results. The earlier absence of `current-result.json`
is not evidence that this withheld Result never existed: its completed check
and saved Result remain. No old failure or receipt was overwritten.

With the changed real processing dependency, only **FY2021** was processed
normally, taking **13.823714s**. Both selected years use their own originals:
current **0001463101-22-000016 / 1,382,049,000 USD**, prior
**0001463101-21-000016 / 774,425,000 USD**. Growth is
**0.7846131000419666203957775123 ratio**, actual annual measurement
**2021-01-01 through 2021-12-31**, new Result
`sha256:bfd848c7987b907dbfe0d736587b7350049804594fcbf965d0f21ebf3282ab86`.
The original operands, complete scope identities and CSV evidence are stored.
Public PR210's original table108/header/XML reading is reused, not repeated.

Forbid both historical factories, the paired scope reader and both Calculator
entries: repeat **0.676918s**, zero calculation and no new Result directory.
Independent `results` process/CSV takes **0.348022s**, all **59 state files**
unchanged. All **33 prior result/check files** remain byte-identical. Crucially,
all **30 unselected FY2022/FY2023 files** remain byte-identical; their values and
full IDs are retained, and both rows say `requested_in_latest_execution=False`:
FY2022 **0.6865197977785158123916011661**, FY2023
**−0.01718984423299109810871813881**. No current conclusion is borrowed from
another year. FY2024/FY2025's already checked results are not recomputed.

## Scope and runnable verification

`controls.log`: **114 tests / 0.842s / zero failure, error or skip**. Existing
finite caption negatives, cross-column refusal/legitimate span, source/period/
unit/comparability, historical dispatch and partial-result state checks execute.
Root's completed fresh FY2021 company run is reused rather than repeated here;
this step verifies migration of the existing withheld task and subset behavior.

```bash
TMPDIR=/private/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. \
  python3 tests/required_unittests.py tests.vnext.test_income_section_captions \
  tests.vnext.test_single_segment_revenue tests.vnext.test_historical_statement_cases \
  tests.vnext.test_history_company_dispatch tests.vnext.test_selected_history_result_state

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. python3 \
  docs/evidence/issue47_enphase_b02_consumer_20261013/caption-followup/verify_company.py \
  --source-root /absolute/saved/source-inputs \
  --state-root /absolute/existing-enphase-three-year-task \
  --output-root /absolute/new-caption-validation
```

The saved-source recovery and original four-year references are in the parent
PR206 record and retained PR52 export; use the actual returned `source-inputs`
root. The provided migration verifier expects the existing FY2021–FY2023 task;
use Root PR210's verifier for an empty new task. Output directories must be new,
original sources/ledger read only. No successful source/financial function is
mocked; only sockets and repeat computation are forbidden.

This closes the specific FY2021 parser gap in a branch combination. It does not
claim a newly executed single-task five-year collection, full 39-metric business
acceptance or online source completion. Main31e4 still lacks PR209/210. Receiver
must independently recheck the focused repairs before main reception. New
SEC/provider/paid calls **0/0/0**; no author Ready/merge/adoption/active.
