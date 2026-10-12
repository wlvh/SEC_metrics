# PR167 reception repair: target filing in saved history blocks

Receiver feedback [6108436313](https://github.com/wlvh/SEC_metrics/pull/167#issuecomment-6108436313) found seven historical B03 executions failing because `_exact_filing_source_set` received only the main submissions document, while their target annual filings were in saved history blocks. The receiver's other 182 tests, ten-company current 30-result comparison, 25 historical positives and named business limitations are reused under their original tested combination; they are not rerun or claimed as this repair's new evidence.

Actual main `e24a5271` is normally merged into the existing candidate. The two conflicts preserve both C04 and income factories/dependencies and all main workflow selectors/trigger paths/limits, plus the candidate's required two-module step. This remains PR167's shared income/history slice, not the independent link-amendment/B07 or source-planner development branch.

`before.log` reproduces the exact recent-only error on real JPM FY2021 `0000019617-22-000272` and Salesforce FY2022 `0001108524-22-000013`, using unchanged saved originals and no network. The fix uses the already received `historical_filing_inventory.filing_inventory` with the existing selected loaded inventories, counts, declared ranges, registrant checks and request-proved reader. That helper and frozen `zero_ai_r2` are unchanged.

The historical producer keeps the main submissions source for company identity and adds the actual holding block only when it differs. The shared calculation accepts an optional `filing_inventory_source` for its exact SourceSet; it validates the same company, raw hash, selected reporting CIK and loaded source URL before reading amounts. Default is None: current callers and recent-held years use the original inventory object and unchanged SourceSet. No monetary operand, new source acquisition, fee permission, period policy, revenue/D&A rule or Calculator is introduced. The actual historical helper is declared as a processing dependency.

73 affected tests pass in 0.403 seconds, zero errors/failures/skips (`affected-controls.log`). The constructed controls check historical/main separation, block proof/record retention, wrong company/hash/unselected URL/CIK rejection before amounts, exact-source selection versus the unchanged default, existing metadata ambiguity/range/registrant refusals and company/state/current consumer behavior. Constructed controls are not financial evidence.

Actual same company CLI, fresh external state, forbidden-factory/shared-calculation/Calculator repeat and separate-process `results`/CSV are in `actual-company.json` and `actual-company.log`:

| Consumer | Fresh | Forbidden repeat | Independent read | Outcome |
|---|---:|---:|---:|---|
| JPM FY2021–FY2024 | 180.143s | 11.130s | 0.580s | Four `N_A_STRUCTURAL`, original full calendar-year dates, `TRAIT_NOT_APPLICABLE` |
| Salesforce FY2021–FY2023 | 21.186s | 2.279s | 0.564s | Three `WITHHELD`, `B03_DEPRECIATION_AMORTIZATION_SCOPE_UNPROVEN` |
| Marriott FY2024 recent neighbor | 6.294s | 1.052s | 0.527s | Original ratio 0.1653386454183266932270916335 and complete Result ID 9cf2d114… unchanged |

All seven returned coordinates have moved past the metadata execution error. Salesforce still has competing direct D&A candidates without a proved full-scope resolution (`DIRECT_CANDIDATES_CONFLICT_AND_NOTHING_IN_THE_FILING_RESOLVES_IT`); no value is released. Its actual periods remain 2020-02-01→2021-01-31, 2021-02-01→2022-01-31 and 2022-02-01→2023-01-31. FY2021 here is the receiver's specific regression coordinate, not an expansion of the latest-five-year product scope.

The saved request-proved reference bytes identify exactly one holding inventory for each target: JPM `-034`, `-026`, `-017`, `-007` history blocks respectively; Salesforce `-001` for all three; Marriott's original main document. `actual-company.json` records each target accession, actual source URLs/hash/reference IDs and metadata holding source. This small metadata inspection reads the already saved reference bytes; it does not repeat annual extraction or create another inventory selector.

All repeats report calculation=false/new_candidate=false, including stable Salesforce withholding. JPM 28 result files/63 state files, Salesforce 21/45 and Marriott 7/18 remain unchanged by the appropriate repeat/read checks. Source registry, actual request log and manifest hashes are unchanged. JPM timing includes its existing complete loaded-history/request-proof checks; this is not a claim of one-minute full-source processing.

Actual current-mode neighbor after this shared API repair is also checked (`current-consumer.json`, `.log`): Marriott B01 fresh 2.943s returns original 26,186,000,000 USD/FY2025 and `e279b28d…`; writer/shared-calculation/Calculator forbidden repeat 0.737s, independent read 0.422s; seven result and 18 state files preserved. The initial evidence guard named a nonexistent writer function and failed before execution (`initial-current-writer-guard.log`); it was corrected to the existing `save_calculated_case`, with the unused first output directory retained. No production check changed and no financial execution was repeated.

Portable replay uses the already restored source input from the [parent primary record](../README.md), and a new external output root:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. python3 tests/required_unittests.py tests.vnext.test_selected_income_calculation tests.vnext.test_historical_b03_case tests.vnext.test_historical_filing_inventory_small tests.vnext.test_history_company_dispatch tests.vnext.test_selected_history_result_state tests.vnext.test_current_reported_revenue
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. python3 docs/evidence/issue47_selected_income_consumer_20261011/inventory-feedback/verify_company.py --source-root /restored/source-inputs --output-root /new/review-output
```

The actual tests/CLI ran on main-combined local `5b46a5a1` with these code/test edits uncommitted; manifest `program_version` retains that diagnosis. Subsequent publication records the matching committed bytes, not a retrospective claim that the executions ran on a different public SHA. The receiver will personally recheck the returned seven coordinates and compare unaffected results. New-head CI is read separately. No source/old result/Run/answer/ledger rewrite or real SEC/provider/paid call; no author Ready/merge/adoption/deployment/active action. Original amendments/successors, older Marriott D&A, Salesforce scope and full five-year obligations remain.

After local source commit `d4b88ad3`, the capability-contract alignment checker against actual main e24 exits 0 (`alignment-postcommit.log`). This is structural checking, not business acceptance. Its two possible output artifacts were saved before checking and restored afterward; no source/result artifact is rewritten. This final log/README addition changes no production/test/workflow byte and does not repeat the completed financial checks.
