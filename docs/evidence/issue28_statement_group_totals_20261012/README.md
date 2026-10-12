# Section-closing reported revenue totals

This is a public reader increment for the already-approved consolidated annual revenue scope. It is not a changed B02 definition, a first-common-label policy, a restatement policy, or an accepted company growth result. Root #28 implements the public source proof; #47 owns historical consumer opt-in, normal company migration and results reading.

The pre-patch historical consumer failed the current revenue role on Marriott FY2023/FY2024, despite saved originals. The exact consumer baseline and original statement are in `docs/evidence/issue47_b02_scope_receiving_20261011/`, including the fixed `aa062b0e` current-main source probe and `d562fd30` company receiving record. Earlier descriptions that all costs were dimensional were too broad: FY2024 has nondimensional CostsAndExpenses 21,333 million and OperatingIncomeLoss 3,767 million, as well as dimensional component costs.

## The explicit contract

`reported_revenue_scope(..., allow_statement_group_totals=True)` recognizes an empty-label approved native revenue amount only when it closes an explicit REVENUES group in the actual consolidated income statement. A unique OPERATING COSTS AND EXPENSES group closes at the empty-label same-context official CostsAndExpenses amount. The next section is the reported operating result. Existing issuer, full annual period, selected column, USD/scale, source and local scope checks remain; original XML is mandatory for this added branch. Revenue minus full expenses must agree with the reported operating result, but that arithmetic alone does not prove scope. Original component rows, group boundaries, source and XML are retained in the proof; components are not summed, so gross/net nested rows are not double counted.

Printed issuer headings may use the existing same-source cover/official DEI name proof. The terminal SEC `/MD/` marker is not asserted to be current incorporation jurisdiction. Only that proven name and the exact current three-year heading are accepted as additional introduction text; no general company-name or year-header wildcard is introduced. Original source bytes and table identities are unchanged.

The option defaults to False, and old consumers are not automatically opted in. `STATEMENT_GROUP_PROCESSING_FILES` explicitly lists the additional cover/text helper and import-time rule dependencies; a consuming caller must add them to its existing processing identity. The helper reuses the existing cover binding rather than creating a second name parser. This retains a dependency on its containing D04 source module and finite rule files; it does not consume a D04 answer or judgment. Future decoupling is not part of this increment.

## Executed evidence

- `complete-section-controls.log`: 102 required tests, 1.113 seconds, zero errors/failures/skips. Positive grouped total, default-off, empty/duplicate/missing/limited groups, extra amount, direct scope limitation, wrong period/context/scale, XML mismatch, unknown intro/period and old current/single-line paths are covered. Synthetic fixtures are not financial results.
- `final-originals.json/.log`: actual saved Marriott FY2024/FY2023 primary and XML pass the explicit contract at 25,100 and 23,713 million USD. The current-period expense/operating relation is 25,100 − 21,333 = 3,767; this is one necessary check among the source checks, not an independently computed revenue total. No company Result/Run was created by this probe.
- `macys-original-negative.json/.log`: actual Macy FY2022 current scope stays `NO_REPORTED_TOTAL_PROVEN`, zero admitted totals, 2.519 seconds. It is not reclassified as revenue zero or complete B02. The original consumer/withheld state was not rewritten.
- `current2025-default-preserved.json/.log`: current Marriott FY2025 source c372495a compared against the actual main c2267ede reader. The default proof body and scope ID remain exactly identical; an explicit opt-in can prove the reported 26,186 million USD. The previous test incorrectly expected the old default to admit that blank total; its AssertionError remains in `current2025-source-check.log`. This was a test assumption, not a changed current company result. No company result was recomputed for this comparison.

The earlier bounded failures and fixes remain in this directory. `before.log` demonstrates the missing API; source-heading failures exposed printed cover-name/year/section support. `originals-final-sections.log` is a harness MappingProxy serialization failure after scope construction; the corrected exact JSON export is separate. `final-bounded-controls.log` is a fixture with untagged explanatory rows correctly refused; the corrected tagged fixture does not relax that guard.

## Reproduction

Use read-only SOURCE_INPUTS and new OUTPUT paths, with this checkout as the program root:

```sh
PYTHONPATH=scripts:tools:. python3 tests/required_unittests.py tests.vnext.test_statement_group_totals tests.vnext.test_single_revenue_line tests.vnext.test_selected_reported_revenue_v2 tests.vnext.test_selected_revenue_scope_v1 tests.vnext.test_current_reported_revenue
PYTHONPATH=scripts:tools:. python3 docs/evidence/issue28_statement_group_totals_20261012/verify_originals.py --source-root SOURCE_INPUTS --output OUTPUT/marriott.json
PYTHONPATH=scripts:tools:. python3 docs/evidence/issue28_statement_group_totals_20261012/verify_macys.py --source-root SOURCE_INPUTS --output OUTPUT/macys.json
PYTHONPATH=scripts:tools:. python3 docs/evidence/issue28_statement_group_totals_20261012/verify_current.py --source-root SOURCE_INPUTS --output OUTPUT/current.json --baseline c2267ede8e35c202d74928efdbe3149e60669a20
```

The probes refuse network sockets and do not use a business call ledger. Actual code root is the dedicated `issue28-revenue-group-total/SEC_metrics` worktree, sources are the existing verified source-inputs under `7e99/SEC_metrics-issue47-company-verified-source-20261006`. Tests before the first commit used an uncommitted tree above e3c17f81; the consumed file hashes and actual main combination are recorded separately. They are not claimed as tests run on an already-published SHA.

## Remaining acceptance

Public source proof is ready for limited receiving review. Actual main c2267ede was normally merged into local 7df83241, with no conflict; `main-combination-corrected-selectors.log` records 163 required controls in 1.404 seconds, zero skips. The first command had one nonexistent selector (paired tests actually live in test_historical_statement_cases); its ImportError remains in main-combination-controls.log. The registration probe first lacked optional PyYAML, then used finite actual-command/selector inspection without claiming full YAML validation; both logs are retained. No financial source probe was repeated merely because unrelated main changes arrived. Historical consumer must explicitly pass the option, include its actual dependencies, then migrate the existing Marriott FY2023/FY2024 company state through normal update, preserve old failures, verify the full current/prior comparison, forbidden-calculation repeat and independent CSV/evidence reading. Macy's known negative must remain withheld. This document is not independent review, full B02 acceptance, 390 acceptance or production credit. No SEC/provider/paid calls, account operations, new budget or retry opportunities were used.
