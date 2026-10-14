# B05 original-component property and duplicate annual disclosure

Progress on #28; shared with #47. Base actually read main `cb27e5d1108237bf535567ce83c92b647e6bcb3d`. This adds the B05 source-property seam needed by the existing Part III historical consumer. It does not create a B05 company result, change the free-cash-flow formula, clear annual continuity, or reopen any failed model request.

The initial local B05 role-only patch is `bd988580`: its legitimate clean property passes, but the actual Paramount FY2024 amendment contains a reported operating-cash-flow amount and is still refused by the additional-disclosure guard. That refusal is retained. The [peer's fixed source investigation](https://github.com/wlvh/SEC_metrics/blob/a4517b07a02bddcba0db2c3f55bb5d4579bef02e/docs/evidence/issue47_partiii_statement_consumer_20261013/b05-source-relationship/README.md) is reference material, not injected runtime operands or company acceptance.

## Implemented relation

`inspect_statement_metric_amendment(scope, raw, *, metric_id='B05', original_raw=...)` verifies original raw identity before rereading its approved CFO concept, exact CIK, full original annual interval, no dimensions, official taxonomy and USD unit. The native amount must lie in the original issuer's consolidated cash-flow statement, under the actual year column and unit caption, with an unqualified total CFO row. A continuing/discontinued subtotal, foreign unit, changed amount, missing period/title, or ambiguous native value does not establish the relation.

For one unadjusted first-person reported CFO highlight, the immediate bullet-list introduction must explicitly bind the Company's same fiscal year; the amount, currency/scale and role must match that original total. Local period/subject qualifiers, quoted claims, adjusted/subset amounts and unknown context remain unresolved. Both introduction and statement spans/cells are retained. This is a deliberately finite source relationship, not a general English classifier; it never inserts an amendment amount into the Calculator or uses an adjusted compensation target.

The original required component roles are CFO and capex. Unknown additional capex or CFO table disclosures remain refused. B04/B07's existing clean outputs and default income/instant callers retain their behavior. Omitting `original_raw` does not waive the relation check. No Scope is rewritten or relabelled as blanket financial approval.

## Actually executed

- `before-api.log` records the new complete positive failing before implementation because the optional original input was unsupported. The actual saved-source refusal is retained in the existing private diagnostic and described above.
- `controls.log`: **158 tests, 1.577 seconds, zero failures/errors/skips**, using the required-test runner. Covers the new nonempty duplicate relation and changed amount/unit/sign/subtotal, wrong claimant/year, local period/subject, quotation and raw changes; retains component correction, table amount, flag, note, identity, original income, selected-income, historical-statement and update/recovery controls.
- `earlier-command-error.log` preserves an invocation mistake (`tests.vnext.test_selector_registry` does not exist). Corrected to `tests.test_selector_registry`; it is not reported as a production regression or a passing check.
- `actual-properties.json/log`: **13.631 seconds** through actual saved source selection, original/amendment loading, full Scope reconstruction and both existing source proofs. Original scope `2aad479a...` and further-review status are unchanged. B04/B07 still pass; B05 now obtains one duplicate relation: amendment block539, explicit issuer/year introduction525, original full-year native ordinal379, **752,000,000 USD**. Source/raw/header/log/registry checks pass. The original protected source root is read-only; network, DNS, Calculator and claim are forbidden.
- Receipt records local tested base, dirty-tree status, actual code/root/source-root and API SHA256 `c2f382689306a08ebf569a47975417dbb3242f897055842534326c78287448b0`. Testing occurred before this commit; publication of the same source tree does not turn it into an exact-SHA CI run. Raw answer files and all call counts remain unchanged.
- `actual-selector.json` confirms the existing fast whole-module selector really loads both new test methods; no parallel CI framework or duplicate selector was added.

```sh
PYTHONPATH=scripts:tools:. python3.12 tests/required_unittests.py tests.vnext.test_statement_metric_amendment tests.vnext.test_income_amendment_paragraph_dispatch tests.vnext.test_instant_amendment_paragraph_api tests.vnext.test_historical_statement_cases tests.vnext.test_selected_income_source_v1 tests.vnext.test_amendment_note_layout tests.vnext.test_ordinary_current_update tests.test_selector_registry
PYTHONPATH=scripts:tools:. python3.12 docs/evidence/issue28_b05_statement_repeat_20261014/verify_saved_properties.py --source-root /absolute/restored/source-inputs --company paramount_skydance_paramount_global --fiscal-year 2024 --receipt /absolute/new/property.json
```

Restore the two original filings through existing #47 source recovery; no supplied reference number or precomputed Result is needed. The private absolute root in the executed receipt identifies that run's material, not a portable prerequisite.

## Consumer and acceptance boundary

#28 owns this public source helper; #47 owns the historical consumer. The consumer must pass the actual original bytes, retain the original Scope and property separately, include the changed helper's processing dependency, and then continue approved original CFO/capex selection, continuity, formula, saving, forbidden-factory repeat and independent company `results`/CSV. The known original values **752 minus263 equals489 million** are a source reference only; **adjusted STIP560** is not an operand. Those company-level steps are not proved here and remain the next integration work.

Receiver independently reviews this finite new relation. No author independent-review claim, no business adoption, no Ready/merge/deployment. New SEC/provider/paid calls **0/0/0**; original ledger limits and failed-request opportunities unchanged. Existing unaffected long chains are reused, not rerun.

## Limited return: local qualifiers after a dash

After publication of34cbd7, Root executed three explicit negative cases. The initial relation incorrectly accepted `—for2023`, `—for a subsidiary`, and an added exclusion after a comparative aside. `after-dash-before.log` records all three failures. Therefore the original17 successful CI checks do not prove this missing branch, and #47 was directly notified to hold new B05 company acceptance of that head.

The return no longer discards arbitrary dash text. It supports only a **closed comparative aside to an earlier year**, followed by a separate activity with no amount/measure/entity/period qualification. Direct local-year/subject qualifiers and exclusion clauses remain unresolved. The rule has no company/CIK/hash or expected amount special case; it retains the complete original CFO/table/unit/period relationship. No general English interpreter or additional model sampling is added.

`after-dash-controls.log`: the same158 required tests now pass1.610s, zero failures/errors/skips; the three previously missed negatives are subcases of the existing method. `after-dash-properties.json/log` re-executes the affected actual source-property path in13.427s with API SHA256 `4ccfb320d9df9b218afed465a82fd304eb9a658c74f07d70cad077ec44ee4c4f`: Paramount's **explicit2024 list and closed comparison to2023** still pass, original Scope2aad/further-review and B04/B07 are unchanged. It remains source-property evidence, not company or production acceptance. Original first logs/receipts are preserved.

This return is locally committed; at the time of recording, GitHub connector calls failed with transport errors and `gh` write returned HTTP401. No credential/account change or false remote-head claim was made. The public PR remains34cbd7 until an actual authorized append succeeds; receiver and consumer need the returned fixed head, not a copied declaration that it was published.

## Completing the original receiver return: qualifier scope is symmetric

Root actually read inline4267961035/4267974707/4269388537 and peer6165704807. The previous dash fix did not finish the original request: `We reported adjusted performance, including generating net operating cash flow of $42 million.` still passed. This was Root's missed part of the same repair, not a new business choice. `whole-clause-before.log` preserves that failure and a continuing-operations prefix counterexample.

The two **existing** qualifier families now both inspect prefix plus suffix through sentence end. No new word family or framework is added. The exact streaming-segment-after-dash example is retained as well. `whole-clause-controls.log`:158 required tests pass1.631s, zero failures/errors/skips. `whole-clause-return.json` records the actual original-source rerun13.720s/API7d42f7f6: Scope2aad/further-review and all three properties are identical (B04ec50b170, B05937fed7d, B0722614d1b). The full private rerun receipt is retained; unchanged source-proof payloads are referenced from the earlier full receipt rather than copied again. The existing driver reproduces it with the same saved originals, no network/DNS/Calculator/claim.

Receiver must personally recheck the returned increment and actual752m relation. No prior receiver171/489-test run or old17CI green is presented as Root's new execution. #47's separate PR280 retains its consumer responsibility and acceptance hold until the returned public helper is consumed. This remains no new company result, call or production permission.

### Current-main reception (2026-10-14)

Read historical feedback6166121301 and merged actual main `ccd9d7c2721e2f8c2116d0ca784178b96571e21f` normally into this candidate, without conflicts or history rewriting. This cleans the consumer stack; it introduces no new B05 behavior beyond the returned whole-clause fix. The same eight affected suites passed **158 tests in1.725s, zero skips**, recorded in `current-main-controls.log`. Original-source752m checks and Scope/property identities from the unchanged patch remain applicable and were not rerun. Historical full489m/company-repeat/CSV checks in6166121301 are peer execution, not a new Root execution. New merge-head CI is separate from the prior head's result.
