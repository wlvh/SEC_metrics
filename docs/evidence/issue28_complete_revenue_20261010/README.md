# Selected revenue component admission — 2026-10-10

Base main: `f6ef7886d6630f7675c25cd42e306c373ab05769`. Source/tests were run as the explicit uncommitted tree listed in `tested-tree.json`; this is not an exact-commit execution claim. Independent receiving review and remote CI remain separate.

## Actual result and entry

Read-only original Pfizer FY2023 primary/XML and actual CompanyFacts reproduce the exact wrong Result `a6e31052ee3e389e46442777fa69c0d06c6ec43e847dd65c412c0e05509aa8f7` at 50,914,000,000 USD. The selected table has Product 50,914m + Alliance 7,582m and reported Total 58,496m. Native company/context/annual period/USD/scale, visible row/column/year/duration/unit, full income-statement context, reported sum and XML correspondence support the admission. Existing Calculator on the remaining original facts produces new Result `128c170a19b5505f3ce22e837aaea836159b4652e334aa4b5bdf298e007786da` at 58,496,000,000 USD. Old Result/Spec/facts remain unchanged; no fabricated revenue addition or later comparative substitution. `actual-calculator.json` and `actual-final-boundaries.log` are actual original/Calculator evidence, **not yet a FY2023 company entry**. Historical consumer implementation stays with #47.

The actual current FY2025 company CLI uses a nine-file source-only root (originals/log/registry, no code/catalog/answers):

```text
python tools/vnext_company.py run --company pfizer --source-root SOURCE --work-dir STATE --output-dir OUTPUT --metric B01
python tools/vnext_company.py results --company pfizer --state-root STATE --output-root READER
```

`current-company.json` records concrete temporary paths and outputs. First run 2.240s, unchanged forbidden-calculation repeat 0.082s, separate-process results read 0.116s; both run exits 0. Result remains 62,579,000,000 USD / 2025-01-01…2025-12-31 with original `536f3b12…ee1bf` identity. Seven result files unchanged on repeat. Daily CSV and evidence URLs actually read. This current source reports `NO_DEMONSTRATED_SPLIT`; it is a preservation test, not a new complete-scope proof for every revenue layout. Times describe this one run, not a cross-machine speedup.

## Public implementation and limits

`selected_revenue_scope_v1.selected_revenue_scope(primary, annual, approved_concepts, xml=None, namespace_policy=..., annual_period_reader=...)` reuses selected native income/table/date readers. An explicit total and contiguous components must share selected native subject/context, income-statement table and visible column group; reported scale, annual interval and arithmetic must agree. Components are evidence only, not new approved calculation concepts. Supplied XML must agree; absent XML is explicitly `NOT_SUPPLIED` (ordinary current source previously required primary/CompanyFacts, no hidden extra fetch dependency). Native total must also exist in the selected filing's CompanyFacts.

`admit_revenue_facts(facts, scope)` filters before Calculator; identity/value/priority are unchanged. Other filings cannot supply a replacement for the selected original, and prior periods are not overwritten. `verify_revenue_observations` rejects a component selected despite admission. No demonstrated split keeps prior behavior and grants **no new complete-scope credit**. This is a bounded correction for demonstrated income-statement splits, not a general scope resolver or proof that all old B01 results are right.

Ordinary B01 and B03 writer explicitly opt in. Shared normal producer/preparer gain `validate_revenue_scope=False` by default; B03 dependency and early dependency fallback forward the same option. Financial duration's extra unit-header descriptors are opt-in, keeping its default behavior. Update configuration names actual new/source/header dependencies, and scope assessments persist in the existing ordinary input-assessment file. Frozen B01 Spec, Calculator, selected income reader, old income preparation and historical consumer are byte-identical to base. No old binding/Run/Result is re-signed.

#47 consumes the same helper before historical Calculator selection and independently verifies the company/CSV result. Parent did not edit its consumer, state, worktree or ledger. The original diagnosis at `0dc5de75:docs/evidence/issue47_growth_reference_20261010/` remains the fixed original reference; no peer acceptance copied.

## Validation and original failures

- Initial small run: 20 tests, one failure because constructed traits were incorrectly a mapping instead of the actual `non_financial` trait list. Corrected the test input, not expected business result; original log preserved.
- `directed-tests.log`: 87 tests passed (9.848s), including current state/repeat/failure/reader and real Marriott company source tests.
- `final-directed-tests.log`: 89 passed (7.948s), zero skip, after same-filing and missing-component controls and assessment persistence.
- `scope-boundary-tests.log`: final 24 scope/selected-source tests passed (0.177s), including additional visible quarter/annual and native/visible unit conflicts.
- `source-and-producer-tests.log`: 53 actual tests passed, plus a loader ERROR for nonexistent `test_normal_run_inputs`; 54 attempted / 47.147s. This command **failed**, not all green. Passed duration, successor and separate-rule-root material tests are retained and not needlessly repeated.
- First actual probe exposed bare MILLIONS unsupported by old column-period reader; opt-in descriptor adaptation passed actual table and keeps default reader's rejection in a regression.
- First company driver overapplied a source-only read guard to a legitimate CSV **write**; driver failed after actual calculation, original log retained. Corrected isolated driver permits output writes and blocks network; final actual CLI/reader evidence above. No production error suppressed.
- Wrong year, missing part, inconsistent sum, XML quantity conflict, absent original CompanyFacts total, later-filing substitute, native/visible scale conflict, wrong annual/quarter relation and component re-selection refuse; standalone complete contract-revenue behavior and prior periods retain old choice. Ordinary dispatch and processing-dependency tests cover B01/B03. Existing period/identity/source errors remain checked.

`company-current-records.yml` actually executes the new scope tests. No full-company long material suite repeated solely for a new SHA. No SEC/provider/paid request; no merge/Ready/adoption/deploy/active change. New response/model/company acceptance is not claimed.

## Limited P2 repair and actual CI regression

Original independent review of 83eaa is CHANGES_REQUIRED (23 tools, 2 messages); preserved under independent-review. It found explicit segment/excluded-subsidiary statements being overruled by table/context arithmetic. The new delta binds the real consolidated income-statement title, caption, following issuer line and unexplained non-native table annotations. An unfamiliar local scope statement rejects with a concrete scope reason; it is not demoted to no-split success. No company-name pass list or generic English parser. Actual Pfizer23 source still gives new128c/58.496bn, now with original title and scope spans in p2-actual-calculator.json; original actual-calculator.json remains the83e execution evidence.

The original83e company-current run37991300980 and main run37991300953 failed, not green. Logs show Salesforce B01 became WITHHELD and B03 got a wrong general income reason; a separate assertion identified unused reported_monetary_literal in B01 processing files. Python3.14.7 reproduced the exact original SELECTED_REVENUE_VISIBLE_UNIT_UNRESOLVED. Full-split-only proofs are now executed only on demonstrated splits (no split grants no extra proof); in-millions headers accepted; real unused B01 dependency removed, actual new structure reader dependency added. No business expected strings changed, no skip or timeout increase.

Python3.14 targeted regressions:49 tests/10.695s passed, including actual Salesforce mixed current outcome and B03-source tests; Salesforce41.525bn/FY2026/wholeFY restored, B03 named scope limitation retained, other metric and repeat state preserved. p2-final-tests63/.414s cover reported source/state checks; initial P2 test command had one expected-reason precedence failure, preserved, corrected by checking duration before scope annotation classification. No claim these local tests are remote success. Final title/context increment still needs independent limited confirmation.

Final current-company revalidation after actual processing files changed uses the same nine-file source and same task (p2-current-company.json): prior seven result files preserve hashes; one necessary changed-program version then forbidden-factory repeat and independent results retain original62579m. All calls remain0/0/0. No large D04/Ford/restore material replayed.
