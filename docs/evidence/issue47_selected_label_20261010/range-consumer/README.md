# Historical consumer of the public fiscal-range entry

Actual code combination `4cc51f1d9586b576c954b95779f68a1ca64ade20` combines fixed public PR128/`5511d77b` (base PR126/`3de509ac`) with the already tested `db240817` combination of PR127's selected-label seam and PR118/119/120 revenue admission. Only the two independent additions to the known-defect register conflicted; both Pfizer's exact old result and Macy's two exact FY2023 results are retained. No public controller, reader, source selector or caller was reimplemented. This branch is a consumer combination, not a new feature PR or a change to main.

## Actual entry, repeat and independent read

On the fixed combination, one Salesforce FY2026 B01 position used saved sources and the actual company CLI in a new state. First run 6.235s, value **41,525,000,000 USD**, actual annual dates **2025-02-01–2026-01-31**, result `8cecba16403adcd8197747cecd1bbb27cb8cb851b4eb236eed2ad74f895ff60d`, matching the already checked original/reference. Preceding full fiscal-year search and HTTP were forbidden; the selected business case still rebuilt and checked annual input and native observations. Raw DEI FY2025 and issuer-defined FY2026 remain separate. This single affected processing run does not redo the old five-year pilot.

Unchanged repeat with fiscal-range discovery, annual business factory and Calculator forbidden: **0.848s**, `NO_SOURCE_CONTENT_CHANGE`, no calculation or new result. Another process read/exported in **0.484s**; value, USD, FY2026 and both dates matched. Ten result/shared-input/pointer/completed-check files remained byte-identical. The ordinary latest execution report may change; it is not an immutable business result.

The saved Salesforce revenue assessment remains `NO_DEMONSTRATED_SPLIT`, with `complete_scope_proven=false`. Original amount matching and this routing test are not a new proof of all revenue component relationships. The selector's existing source-scope boundary is reported without enlarging its credit.

Requesting FY2026–FY2027 against the same saved sources took **3.568s**: FY2026 reused its success without its business factory; FY2027 was `INPUT_OR_EXECUTION_FAILED`, precisely `FISCAL_YEAR_MISSING_OR_AMBIGUOUS`, with no current result. Independent read **0.404s** preserved FY2026's value and exported FY2027's missing-year row. All ten previous protected files remain. This is a real absent year in the saved catalog, not a fabricated financial conclusion. `missing-year-raw.json` preserves the exact report and reason.

## Default read of old results

The same default reader consumed the existing Macy pilot state in **0.536s**, with discovery/calculation forbidden. It contains 22 current rows: the original twenty statement coordinates plus two later saved balance positions. Only the exact FY2023 B01 `5f17ec97…` and B02 `db609edd…` are `WITHHELD_KNOWN_DEFECT` with empty current values. All **469** files in that old state stayed byte-identical. FY2022 is a source-scope investigation, not a diagnosed wrong result; this check neither clears that investigation nor adds a hold based on later comparatives. No old numeric result is overwritten.

77 directed range/selected-label/revenue/dispatch/state tests passed in **2.100s**, zero skips. Existing source-missing, competing-year, metadata-error, lazy-factory and local-state controls are reused; no second history runner. This combination changes only B01/B02-only range dispatch. Mixed families retain the already delivered dispatch; this record does not claim that every mixed family uses the new range planner. The old twenty/five-year companies and unrelated current mode are not recalculated.

## Reproduce from obtainable code and input

Use `origin/task/issue47-fiscal-range-consumer-20261010`; the tested product tree is `4cc51f1d`, with subsequent evidence-only commits. The source restoration tool remains on retained PR52's `origin/task/sec-history-five-year`, not on main: in that separate checkout, run `python3 tools/vnext_historical_sec.py restore --export evidence/issue47_acquired --out NEW_SOURCE_PACKAGE`, then use its returned actual `source-inputs` root. No source GET is required. The source root is read-only; use new state and output directories outside both checkouts and source roots.

```sh
python3 tools/vnext_company.py run --company salesforce \
  --source-root SOURCE_INPUTS --period fiscal-years \
  --fiscal-year-start 2026 --fiscal-year-end 2026 --metric B01 \
  --work-dir NEW_STATE --output-dir NEW_OUTPUT
python3 tools/vnext_company.py results --company salesforce \
  --state-root NEW_STATE --output-root NEW_READER_OUTPUT
python3 -m unittest -v tests.vnext.test_company_fiscal_range \
  tests.vnext.test_selected_historical_fiscal_label \
  tests.vnext.test_selected_revenue_scope_v1 \
  tests.vnext.test_history_company_dispatch \
  tests.vnext.test_selected_history_result_state
```

Actual commands, roots, stdout, timing, CSV rows and protected-file digests are in the adjacent JSON/logs; the two verification drivers are ordinary consumer checks of the existing CLI, not a replacement controller. They reference the recorded local development roots and must be pointed at a newly created equivalent state when used elsewhere.

Main observed `f6ef7886` still has the delivered saved-source historical families; PR126/127/128 and PR118/119/120 remain candidates. This composition does not deliver online historical discovery/capture, missing attachment/image acquisition, every indicator, general amendment/subject handling or the full 1,950-position target. Zero SEC/provider/paid calls; no old Run, model response, ledger, main, Ready, merge, adoption or active pointer changed. A CLI's `FLOW_COMPLETED` is a processing status, not formal business acceptance.


## Corrected public range received

Subsequent code combination `c98695f5` receives public128 fixed `8540e29a` / product `6f5cb7e4`, including the historical assertion-sentence fix, the public immutable-year snapshot, finite negative/positive discovery controls and the removal of duplicate imported fixture loading. The original two review failures remain. The same limited reviewer confirmed the corrected difference; this technical conclusion does not authorize merge. Historical scope source/tests match PR127’s final product byte-for-byte. The merge was automatic and did not replace the income admission or old exact defect entries.

70 distinct directed tests pass in1.473s/zero skip. Count falls from the preceding81 executions because the public owner removed unintended imported fixture loading and added actual affected scope/year tests; it is not a reduced business assertion to claim a faster green. No old company amount is rerun for this correction. Another process reads the existing SalesforceFY2026 success plus FY2027 missing-year row in.431s, preserving all24 state files; original value/dates/null status remain. Existing first/run/forbidden-repeat receipts retain their original code version rather than receiving retrospective new-code credit. New source/processing changes will be handled only through the shared updater, without editing old completed-check identities.
