# Historical consumer reproduction of receiver feedback6103171116

Actualmain672b46b6 plus fixedpublic128/4dcc8816 is combined in an isolated historical branch; only company-current-records workflow path conflict is joined, retaining both C03 and source/range triggers. No code in the public dispatcher/reader/controller is repaired by this branch. Two added tests enter the actual company_local.run_local historical dispatcher while replacing only run_saved_company; no source preparation, financial calculation, state, ledger or network is used.

The dependency containment test requests B02 alone and compares its declared processing files with received PAIRED_REVENUE_PROCESSING_FILES. It fails because historical_paired_revenue.py is missing. The selection-combination test compares the actual controller identity fields (factory module/qualname/sourcefile plus declared dependencies) for each B01/B02 alone versus mixed withB04. Both subcases fail because pure selection returns a company_fiscal_range producer whereas mixed selection returns historical_statement_cases and different dependencies. Two tests/.401s, threefailures, zeroerror/skip. This reproduces the receiver's precise paths; it is not a fresh financial acceptance or a new controller.

consumer-tests.patch records the original two failing methods. After direct ownership alignment, #47 implements only company_local._run_saved_history and this existing test module; #28 retains public helpers/controller/runner and receives the patch in original PR128. Product commit5f2d8249 removes the pure-income-only early return, wraps B01/B02 in the same public range factory under every selection, and declares each metric's received processing dependencies plus range dependencies. B02 keeps PAIRED_REVENUE_PROCESSING_FILES. B04/B05/lodging/bank/event/current-mode factories and dependencies remain. Main152's source-admission rules/claims/paired formula and old successful/withheld results remain.

repair.patch applies both source and final tests to actualmain672b46b6+PR128/4dcc8816. The final 89 controls run in1.340s with zero failure/error/skip. Existing wrong source/period/scope and state assertions remain. Eight old mixed-selection tests expected the bare income factory and are updated for the now-shared range wrapper, while retaining exact adjacent-family factories/dependencies. One constructed control invokes the actual wrapper, verifies that it delegates the chosen period to the original statement case, and discovers once for the two income metrics. It is explicitly not a financial reference. Initial test-command error (nonexistent test_historical_paired_revenue) and macOS resolved-temp-path assertion were corrected, not counted as passes.

Actual same-company CLI on the existing Macy FY2023 task performs one related version transition in20.499s. B01 remains23,866,000,000USD, 2023-01-29..2024-02-03 (53weeks), Result77805235; B02 remains the precise complete-check WITHHELD/null HISTORICAL_PAIRED_REVENUE_SCOPE_UNRESOLVED Result3e8862c3, without borrowing the later restated prior; B04 keeps Resultc57ef63f. Only these affected coordinates process. Original result/input files and other saved pointers are preserved.

All subsequent selections prohibit actual range discovery, statement factories and both numeric calculators: B01+B02 alone1.960s, B01+B02+B04 again2.343s, B01 alone1.157s, B02 alone1.387s. Successful items return NO_SOURCE_CONTENT_CHANGE; held B02 returns PREVIOUS_INPUT_WITHHELD. No calculation, new candidate or result/input/current/completed-file mutation occurs. Independent CLI results0.662s keeps every state-file hash, exports23 rows, and preserves the previously recorded FY2027 SOURCE_UNAVAILABLE failure alongside the20 prior financial positions and two balance positions. The source request ledger and company registry remain unchanged.

actual-company.json contains all completed subprocess arguments/stdout/stderr/timings and CSV rows. The initial verification driver reached the read hash check but then mistakenly expected the old WITHHELD_KNOWN_DEFECT CSV label. Actual new scope-unresolved business result correctly renders WITHHELD; the completed output was checked offline, and the copyable driver assertion was corrected. The original failure log is retained in actual-company-initial-driver.log; no financial first-run was repeated to repair this harness error. A second stale22-row assumption was corrected to preserve the real previously recorded missing-year row. This is a precise receiving repair, not new revenue-scope acceptance or full five-year processing.

Reproduce the source/tests on the fixed combined tree with git apply repair.patch, then run:

```bash
PYTHONPATH=scripts:tools:. python3 -m unittest -v \
  tests.vnext.test_history_company_dispatch tests.vnext.test_company_fiscal_range \
  tests.vnext.test_selected_history_result_state tests.vnext.test_historical_statement_cases \
  tests.vnext.test_paired_measure_contradiction
PYTHONPATH=scripts:tools:. python3 verify_actual_company.py \
  --state-root /existing/macys/state --output-root /new/macys/range-repair
```

The actual-source driver is for an existing protected Macy task with the already checked references. Fresh-source restoration and the receiver's original fresh-task Macy/Salesforce results remain in PR128's prior records; they are not re-executed for this repair. The receiver still personally rechecks its returned source-edit and alternating-selection reproductions. No remote CI or receiver approval is claimed by these local results.

No new runner/platform, realSEC/provider/paid, result rewriting, Ready/merge/adoption/active. Current public157 import repair and CI140 receive their own priorities. The historicalB06 selected-source WIP is separate and is not falsely labeled a delivered company capability.
