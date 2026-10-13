# Limited independent review: REQUEST_CHANGES

Reviewed patch `7e6f6a240e63000ad69c1a9354f86980eced4228` against `aa29a0ab1b3eafc7ce384f98c1b889e2477012dc`. The eight authorized product/test/workflow files match the fixed head byte for byte. Only this review directory was added; no reviewed file was changed, no development/commit/push/spawn or SEC/provider/paid call was performed, and no Issue #47 state was touched.

The explicit caller plumbing, default V1 behavior and declared processing identity pass the limited checks below. Two new permissive format branches still accept unproved source information, so this delta does not receive PASS.

## P2: A newly recognized fiscal end-date row can contradict the selected period and still pass

Location: `scripts/vnext/selected_revenue_scope_v1.py:131-134` (new fiscal-header/numeric-marker permission).

Starting with the existing `originals()` fixture, retain its correct `Year Ended December 31,` row and 2025 year column, then insert this non-native header immediately after the year/unit row and before Product revenues:

```html
<tr><td>Fiscal Year Ended December 30,</td><td>57</td></tr>
```

The exact base `_statement_scope` rejects it with `SELECTED_REVENUE_STATEMENT_LOCAL_SCOPE_UNRESOLVED`. The patch accepts `REPORTED_CONSOLIDATED_TOTAL`, `complete_scope_proven=True`, for native end `2025-12-31`. Its `end_headers` records only the earlier December 31 header. Replacing December 30 with December 31 is the legitimate positive and also passes the patch. This is a finite contradiction introduced by granting the new fiscal format permission without ensuring that this newly accepted descriptor participates in the period check: the already selected source helper scans end headers only through the chosen year-column row. See `fiscal-group-controls.log`.

The consequence is that current B01 and B03's revenue dependency can classify a source as a proven total while the accepted table explicitly describes a different end day. Keep the ordinary fiscal layout positive, but associate and validate every newly accepted fiscal end-date descriptor that governs the selected total; the contradictory row must fail, without component fallback. This finding is limited to the interaction of the new permission with its current consumer. It is not a full independent verdict on Source PR130's earlier or final date repairs.

## P2: The new expense-group permission erases arbitrary parenthetical words as though they were footnote markers

Location: `scripts/vnext/selected_revenue_scope_v1.py:138` (new expense-group permission, after `_label_key` normalization at line 126).

Insert a non-native group row before Cost of sales. `Operating expenses (1)(2):` is the intended positive. The patch additionally accepts `Operating expenses (Europe):` and `Cost of revenues (Subsidiary):`, both with `complete_scope_proven=True` and `unresolved_annotations=[]`; the exact base rejects all three by the local-scope gate. See `scope-controls.log`.

The reason is that `_label_key` removes every single alphanumeric parenthetical token, including `(Europe)` and `(Subsidiary)`, before the new labels are matched. Those words were not proved to be note markers or finite structural formatting. The later direct exclusion guard does not reject these cases. This does not demonstrate a wrong amount in the three actual originals, but it invalidates the claimed limited permission: unexplained geographic/subject qualifiers disappear from the scope decision. Recognize the permitted group labels with actual footnote-marker syntax, preserving or refusing other parenthetical words; keep the existing generic/default path stable. The existing explicit `Operating expenses of Subsidiary Beta only:` negative remains rejected by both versions.

## Verified within this review

- Required command: `PYTHONDONTWRITEBYTECODE=1 python3 tests/required_unittests.py tests.vnext.test_current_reported_revenue tests.vnext.test_selected_revenue_scope_v1 tests.vnext.test_selected_reported_revenue_v2 tests.vnext.test_ordinary_current_update tests.vnext.test_company_current_records`. Result: **107 tests, 9.199s, zero failure/error/skip**, in `required-tests.log`. This includes actual Salesforce B01/B03/B12 mixed outcomes and unchanged-input reuse. Passing this suite does not cover the two added adversarial cases.
- `ordinary_saved_result._ordinary_case` explicitly selects `reported-total-v2` for B01/B03. The shared resolver/preparer still default to `components-v1`. V2 admission and its matching observation checker remain paired, and the helper contains no exception-to-component fallback. The existing absence and conflicting-period controls pass.
- A constructed early B03 withholding with no B01 result calls the declared B01 resolver with the same explicit V2 contract, revenue validation and rules root; it assembles both required result identities. `dependency-forwarding.log` identifies that resolver/specs are mocked, so this is forwarding/assembly evidence only.
- Current `_configuration` hashes the newly used `selected_reported_revenue_v2.py` and `historical_fiscal_labels.py` for B01/B03. The required tests verify that their changed hashes invalidate those consumers, while C01 stays unchanged. The existing update tests cover source/config change processing and unchanged successful/withheld reuse.
- The company-current workflow selects the new test module both in path triggers and in the job command.
- Directed static inspection of the three saved original table spans independently confirms actual direct totals: Macy FY2025 22,621m, Pfizer FY2025 62,579m, Salesforce FY2026 41,525m. Saved source hashes and table spans match the supplied execution record. Salesforce's original navigation and finite fiscal/cost-group text were inspected. See `original-tables.log`. The recorded execution's seven product/workflow/test hashes also match this patch; its `UNCOMMITTED_CURRENT_CHANGES` identity remains accurately described.

## Boundaries and resources

The earlier failed logs remain unchanged. The parent three-company CLI/repeat/independent-reader execution was read, not rerun. The old 20-coordinate material suite was not rerun or relabelled. Source PR130's final associated-date change still lacks its separately requested limited independent coverage; neither this test suite nor this report turns the historical REQUEST_CHANGES into a source-level PASS. No company content, old held result, all-39 scope, business adoption, Ready/merge/deploy/active or actual model correctness is granted here.

Review start: 2026-10-10 01:40:23 UTC (09:40:23 Asia/Shanghai). Review end: 2026-10-10 01:45:50 UTC. Conservative tools: 44 total through final verification (17 visible wrappers plus 27 nested calls); ordinary messages: 2 including the final report. Both remain under the 80-tool/90-minute/3-message cumulative limits, leaving the final message and remaining tools available for one bounded repair review.


## One bounded P2 repair review: PASS_LIMITED_REPAIR

Repair head `71ab18de112b193e15c70f2381006c73c42abd09`, base `7e6f6a240e63000ad69c1a9354f86980eced4228`. Only the actual differences in `selected_reported_revenue_v2.py`, `selected_revenue_scope_v1.py`, and `test_current_reported_revenue.py` were reopened. The original report above is preserved byte for byte as the prefix; its REQUEST_CHANGES remains the historical verdict on the old head. The already reviewed caller/default/dependency wiring is reused, not newly claimed as a full source review.

Both reported P2 cases now close in this bounded delta. The period check iterates header rows before the selected total rather than stopping at the chosen year row; a common year-ended descriptor also associates its newly permitted numeric marker row. The exact December 30 + 57 original reproduction rejects with `SELECTED_REPORTED_REVENUE_VISIBLE_END_DAY_CONFLICT`; December 31 + 57 succeeds, retaining the correct fiscal descriptor among `end_headers`. The expense-group branch matches its raw visible text after removing only numeric parenthetical markers. Both original named qualifiers `(Europe)` and `(Subsidiary)` reject with `SELECTED_REVENUE_STATEMENT_LOCAL_SCOPE_UNRESOLVED`, while both `(1)(2)` group-label positives succeed. See `repair-exact-and-association.log`.

The same directed log additionally checks a late comparative fiscal-header row with 2024 and 2025 dates in separate columns and the selected native total in the right-hand 2025 column. Both the repair base and repair head correctly accept the selected 2025 total; the new scan does not make that earlier comparison-column date govern the current column. Code inspection confirms that the optional cost-group fix does not change the old `_label_key` or default `adjacent_heading=False` path. No further actionable finding was established within these repair differences.

The required five-module command ran again against the fixed repair bytes: **109 tests in 9.826s, zero failures/errors/skips**, including the actual Salesforce mixed B01/B03/B12 integration and unchanged-result reuse. See `repair-required-tests.log`. This is actual independent test execution, not a copy of the parent 109-test log. The original 107-test evidence remains unchanged.

The parent P2 actual resume record was inspected. It accurately says `UNCOMMITTED_P2_REPAIR`; the selected revenue-scope file matches this repair, but its reported-revenue file predates the final numeric-marker association. The parent record therefore supports its declared earlier actual processing/reuse/reading, not a full final-SHA company replay. This review did not rerun the three-company CLI, old 20-coordinate material suite, or all Source PR130 changes. Source PR130's separately unreviewed final associated-date increment does not receive an independent full PASS from this result. No business content acceptance, historical hold release, Ready/merge/adoption/deployment/active or real SEC/provider/paid execution is authorized.

This repair review started 2026-10-10 01:51:55 UTC (09:51:55 Asia/Shanghai) and completed 2026-10-10 01:54:38 UTC. Original cumulative start remains 2026-10-10 01:40:23 UTC. Conservative cumulative tools through final verification: **62** (24 visible wrappers plus 38 nested calls; 18 tools in this repair turn). Cumulative ordinary messages: **3**, including the final repair report. The 80-tool/90-minute/3-message cap was not reset. This concludes the single bounded repair follow-up; no further ordinary-message allowance remains.
