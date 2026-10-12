# Fiscal-range sources retain the exact pending source observations

This public #28 correction consumes the fixed [#47 probe b5421410](https://github.com/wlvh/SEC_metrics/blob/b5421410ec1407bfa764e924818b1158ddd39f0c/docs/evidence/issue47_history_pending_sources_20261013/README.md). Base is actual main385. No new label collector, selector, source plan/controller, source ledger or acquisition grant is created. The existing `_Requirements` and fiscal-label loop already know the required URLs/outcomes; this increment retains them in the same formal `sources` response.

## Actual failure and correction

The public `sources --fiscal-year-start/end --metric B01` was reproduced with the existing small saved HTTP/ledger fixture, using its real registration, source and label readers. Latest503, missing annual primary and missing CompanyFacts each return exit2, but the old response discards the observed URL/status into generic `LABEL_SOURCE_MISSING`. `before-exact-url-controls.log` reproduces the absent exact URL; `before-controls.log` also preserves the absent proposed pending field. The fixture is isolated and constructed, not a real SEC execution.

The existing label candidate keeps the two actual source observations. A failed/missing input retains its exact source URL, saved status and original error. A recorded failed request additionally retains its existing attempt/timestamp/HTTP status/error; it is SOURCE_ACCESS_FAILED. A source without a saved request is SOURCE_UNAVAILABLE. Blocked source integrity is distinct. Missing/incoherent label evidence still prevents fiscal-year resolution and full-graph credit; it never guesses a label from report-end year or reuses a previous successful GET.

The same response now carries `known_source_requirements`, `pending_source_requirements` and `complete_known_source_graph`. The known set combines actual label dependencies with any resolved task's existing source preflight; shared URLs keep their roles, proofs and prior-native alternative rules. This pending list is a read-only input to future source completion, not permission to GET. An unresolved fiscal label can still hide additional task dependencies: `complete_known_source_graph=false` is retained, so the list is not a final acquisition budget or complete empty scope.

Content inconsistency with already saved inputs remains an error rather than a missing GET. A control using mismatched CompanyFacts CIK leaves the range unresolved with no invented pending acquisition. Existing metadata/issuer-label ambiguity, target company/period and old range/current dispatch boundaries remain.

## Formal entry and actual outcomes

The provider probe's three constructed source executions were run on this public code, changing only its diagnostic output directory. `latest503.json`, `missing-primary.json`, `missing-companyfacts.json` preserve the complete actual responses. All are exit2 / FISCAL_RANGE_UNRESOLVED, expose the exact pending URL, preserve each fixture's source tree bytes and create no calculation or request. Each has one precise pending dependency and an incomplete graph. No source/ledger row is removed or renumbered in production; only the fixture's explicit failure setup edits its own temporary log before the readonly operation.

`final-controls.log`: **53 required source/range/fiscal-label controls /3.052s /zero skips**, including full formal dispatch for all three failures, no erroneous GET for content inconsistency, complete positive graph/empty pending, valid unrelated-registry changes, noncalendar labels, missing candidates and ambiguous scope.

`salesforce-formal-range.json`: actual previously saved source root, formal `sources --company salesforce --fiscal-year-start 2026 --fiscal-year-end 2026 --metric B01`, with network, claims and calculation forbidden. **3.168s**, exit0/FISCAL_RANGE_RESOLVED, six known sources, no pending, complete known graph. **Issuer FY2026**, **raw DEI2025**, **2025-02-01..2026-01-31** are preserved. This newly executed source-range observation is separate from #47's prior13fb package/financial result evidence; no old reading is relabeled as this execution. It is not a new financial result, online SEC freshness or five-year company acceptance.

The source root is the existing `SEC_metrics-issue47-sec-ledger-resume-20261006/source-inputs`; no source export/recovery or GET was performed. Daily source readiness continues to carry false metric/fetch/production flags and zero calls. Old records, current company state and the real call ledger are untouched.

## Reproduce and reception

```sh
PYTHONPATH=scripts python3 tests/required_unittests.py tests.vnext.test_company_fiscal_range tests.vnext.test_selected_source_requirements tests.vnext.test_selected_historical_fiscal_label
python3 tools/vnext_company.py sources --company salesforce --source-root /absolute/saved/source-inputs --fiscal-year-start 2026 --fiscal-year-end 2026 --metric B01
```

Tests ran on main385 plus the working-tree difference; `tested-worktree.json` identifies those initial code blobs and the actual roots. Commit/tree and remote CI are separate. Existing required workflow/fast entries already execute this module. The initial correction was independent of PR218's E01 extension, not a condition for receiving it.

For final reception this successor explicitly consumes fixed PR218 `b215ca0b` (same local50da7168 tree). The only merge conflict was the adjacent import block, resolved retaining both APIs. The range composer reuses PR218's existing exact-CompanyFacts context matcher rather than adding a second checker. This keeps the selected aggregate's contextual accession difference while rejecting changed source bytes or a filing identity difference. Provider historical files and prior-source behavior remain fixed.

`combined-218-controls.log`: **63 related controls /3.380s /zero skips**, both source failures and E01/annual routing retained. `southwest-mixed-range.json`: actual complete saved originals through the formal fiscal-year-range entry with B01+E01, network/claims/calculation forbidden; **16.897s**, exit0,45 known sources, zero pending, complete source graph. Original six-item request34507016 is unchanged, count remains null. Extra label-window sources remain explicit; no clipping to maintain an old URL count. New support is source dependency observation, not a financial/M&A result. Earlier Salesforce positive remains valid for its unchanged annual responsibility. The final combined tested blobs are in `combined-tested-worktree.json`.

Suggested reception is PR218 then this finite successor. This PR does not change PR218's already tested content or block receiving it, and does not pull a whole peer branch. No unrelated development, source/response payload or new financial calculation is imported.

New provider/paid/SEC **0/0/0**. No key/account/new company/scope/model/production permission. No author Ready/merge/adoption/deployment/active. Complete online acquisition/processing and390/automatic-update goals remain incomplete; this closes the already known failure-state seam only.
