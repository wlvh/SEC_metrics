# Single-segment revenue: explicit public source qualification

The receiver's historical B02 queue includes Enphase FY2024. Its consolidated
income statement reports `1,330,383` thousand USD net revenue in a native
segment context, while the statement's company-level cost and net income use
an undimensional context. The old reader drops the revenue before statement
scope inspection. Matching note totals alone do not resolve that scope.

#28 read #47's fixed original-table/context record at
[`b69b0dae`](https://github.com/wlvh/SEC_metrics/blob/b69b0dae581409c2e3414f251c14f66cc94ad140/docs/evidence/issue47_b02_scope_receiving_20261011/enphase-scope-followup/README.md),
then independently read the saved full original and XML. In addition to the
previously supplied narrative, the original has official current-year
`NumberOfOperatingSegments=1` (ordinal31) and `NumberOfReportableSegments=1`
(ordinal30), both in undimensional context `c-1`. No English classification
rules or manually supplied scope assertion are used by the new path.

## Actual change and limits

`reported_revenue_scope(..., allow_single_segment_revenue=True)` explicitly
requests the new source route. The default is false. The existing
`native_income_reports` remains nondimensional; a separate narrow helper
shares its byte/entity/period/namespace/unit checks and returns candidates
only for the supported, caller-approved revenue concepts.

Qualification requires both official full-year count facts to be one,
consistent scalar count units, a unique same-period business-segment member,
one official `StatementBusinessSegmentsAxis`, no typed/additional dimension,
and the `ReportableSegmentMember` QName. Issuer-specific `segment` units must
bind to that same member namespace. Those checks produce candidates, not
complete-revenue credit.

The scope reader then requires the complete consolidated statement, its sole
top-line revenue cell, matching visible year/scale/unit, undimensional
company cost and income in the same visible year group, and matching
independent XML with its own segment-count proof. Original native dimensions
remain in the evidence. Neither a member name, equal note total nor a
one-segment count alone grants acceptance. Three finite statement section
captions are recognized on this explicit path; numeric/unresolved annotations
and scope limitations are not erased.

The Calculator still receives the existing selected undimensional
CompanyFacts claim. Admission only filters the original claims by the proved
reported total; it does not create a dimensional operand, change the MetricSpec
`dimension_policy=NONE`, compute a replacement sum or change original claim
identity. A regression verifies that the original fact list is unchanged.

The same FY2024 paired task also needs the separately selected FY2023
original. Its undimensional complete statement uses `Net revenues`, which
the existing explicit single-line route did not recognize. After a failing
regression, that route now recognizes `Net revenue(s)` with the same sole-row,
whole statement, entity/period/unit and XML constraints. Geographic qualifiers
remain excluded. This is not enabled when the single-line option is omitted.

No historical/current consumer is silently enabled. #47 owns the historical
thin call and company recovery/repeat/read. Its existing
`INCOME_PROCESSING_FILES` already names both changed public files and the
namespace, metadata, duration and visible-table dependencies. No new reader
configuration platform is required. Current callers retain the prior default.

## Actual execution

Code root:
`/Users/lyuhongwang/.codex/worktrees/issue28-revenue-group-total/SEC_metrics`.
Its previous completed PR196 branch was clean and retained; the new short
branch starts from actual main
`8030f851e467c456bb9c9267280a45e2c515d05e`.
Source root is the already saved, read-only acquisition:
`/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs`.
Tests ran on the base plus this working-tree patch; the subsequent commit
does not retroactively make them committed-SHA executions.

- `before.log`: the newly added tests fail on the unchanged public API.
- `first-repair.log`: the first repair still could not qualify XML-style
  count names lowercased by the existing metadata parser. The repair uses the
  same local-name comparison as the existing native reader and retains the
  original official namespace and metadata.
- `original-first-error.log`: real-source execution then exposed a previously
  unassigned nonnumeric `Other income, net` section row. That finite caption
  is now recognized; its untagged numeric or limited-scope variants still
  fail. The source was not changed or shortened.
- `final-targeted.log`: **238 controls in 9.789s**, zero errors, failures or
  skips, using `tests/required_unittests.py`. Includes existing default/source
  admission, source calculations, historical B03/statement consumers and
  current company save/reentry/independent-read behavior.
- `original.json` / `original.log`: socket connections forbidden, real
  original HTML and separate XML read through `_Sources.auditor_filing`.
  Original `0001463101-25-000024/enph-20241231.htm`, CIK1463101,
  actual 2024-01-01..2024-12-31. HTML SHA256
  `275bc6e2e21fc31a5eab74232ee05f3572c1f36573608d5bd84e3e6eaec79bfe`,
  XML `48b84800d21a642a655e50eae7a21e410ce0fe22a34619c11b73f54183657ca4`.
  New complete source proof is `1330383000 USD`, native ordinal157/context
  `c-6`; source dimensions retained. Cost701245000/context `c-1` and
  net income102658000/context `c-1` occupy the same 2024 header group.
  Separate XML matches. Old/default proof body and ID match actual main
  exactly. This three-path source probe took **6.515591s**, not a company
  calculation or a production performance benchmark.

Run the targeted controls from this checkout with:

```sh
PYTHONPATH=scripts:tools:. python3 tests/required_unittests.py \
 tests.vnext.test_single_segment_revenue tests.vnext.test_selected_income_source_v1 \
 tests.vnext.test_selected_reported_revenue_v2 tests.vnext.test_selected_revenue_scope_v1 \
 tests.vnext.test_statement_group_totals tests.vnext.test_single_revenue_line \
 tests.vnext.test_current_reported_revenue tests.vnext.test_selected_income_calculation \
 tests.vnext.test_historical_statement_cases tests.vnext.test_historical_b03_case \
 tests.vnext.test_company_current_records
```

`verify_original.py --source-root <existing-saved-source-root> --output
<isolated-json> --baseline 8030f851e467c456bb9c9267280a45e2c515d05e`
with `PYTHONPATH=scripts:tools:.` reproduces the saved-source proof. It reads
the fixed baseline function from Git for comparison; it is a development
probe, not a runtime requirement or installer.

Covered negatives include multiple/missing/conflicting/wrong-period segment
counts, monetary count units, another issuer's segment unit, geography/product
or extra dimensions, multiple member identities, fake axis namespaces,
incomplete/limited statements, another revenue line, XML count/value changes,
and nonboolean options. Unknown source relationships stay unproved.

## Not yet proven

This patch does not create an Enphase company B02 Result or prove both annual
operands. The chosen consumer still must perform complete own-filing/prior
scope checks, normal saving, forbidden-calculation repeat and independent CSV
reading. Older originals without these native count facts may need a
different evidenced path; they are not reclassified as inapplicable.
Remote CI and independent receiver verification apply to the actual published
head, separately from these local tests. Existing original/failed records,
responses and ledgers are not rewritten.

New SEC/provider/paid calls: **0/0/0**. No model, endpoint, business definition,
adoption, merge or production operation changes.

## Paired-original follow-up

`prior-caption-before.log` is the actual failing regression before the
explicit net-caption change. `prior-original-first-error.log` retains the
real prior-source section-caption rejection. Its actual unassigned rows were
`Other income (expense), net` and `Net income per share:`; bounded punctuation
variants are recognized, while numeric and limited-scope variants stay errors.
`pair-targeted.log` then passes **240 controls in 10.061s**, zero skips/errors.

`prior-original.json` records the actual prior original
`0001463101-24-000024/enph-20231231.htm`, actual 2023-01-01..2023-12-31:
the old explicit single-line route could not prove scope; the new route proves
the original undimensional **2290786000 USD** with its own XML (4.589438s).
The current original was rechecked by the same probe (6.568720s); the small
new cost-scale regression ensures same-caption cost/income units cannot
disagree with the dimensional revenue. The earlier current proof is retained
and not represented as having been rerun at a future commit.

To run the necessary pair, add `--prior-output <new-prior-json>` to the
source probe. The two proved source amounts still are not a company Result;
the historical owner must deliver its own normal factory/save/repeat/CSV.

## Public interface combination

Actual main subsequently advanced to `f29d1797` with received PR198/200/201.
Those changes were normally merged; no peer development branch was imported.
PR202's public `9452631f` was then normally merged at
`bde2f5ad032c7be4d2ba6cac3400da02180456b0`. The shared signature and validation
retain both `dei_release` and `allow_single_segment_revenue`; both test
selectors, workflow commands and trigger paths remain. No ours/theirs
selection discarded either interface. A joint-option regression verifies
quarter-release DEI and single-segment qualification together.

`combination.log`: **281 controls, 9.771s**, zero skips/errors/failures, at that
combination plus the stated added test and generated log. The following
evidence commit preserves those production bytes. `combination-original.log`
rechecks the real two originals after that merge (6.350847s current,
4.411855s prior), both scope proofs and XML still match. No original source,
old company state or ledger was written. The temporary exact source-proof
JSONs are outside the repository; the prior committed proof and current
original proof remain sufficient for reproduction.

The Git network fetches during preparation returned actual HTTPS timeout
errors. GitHub's API separately supplied the current main and PR202 head,
and locally available immutable commit objects matched those fixed public
SHAs/tree before use. This is not presented as a successful fresh Git fetch.
The new candidate includes PR202 as a required compatible public interface;
the receiving order is PR202 then this source patch, or the same proved
combination. PR199 remains a separate Marriott caption dependency, not an
Enphase requirement or an imported unrelated feature.

Before publication, main received PR135 at `2f756660f26438faf368ae760728e1442ecd1c41`.
That main was normally merged into this branch, preserving its current D01
producer, controller parameters, fixed shallow-checkout test fixture and
workflow checks. Tested commit `b4f5f64cd23083c7d44c54b7d9cff97672b5118b`
had only the newly generated log untracked. `main-135-combination.log` reports
**336 required controls in 10.370s**, zero failures/errors/skips, including
current company records, selected-period update/recovery and current D01.
No source-helper production bytes changed in that main merge, so the proven
two-original source checks are reused. The following documentation/log commit
does not represent a new execution. The published candidate's tree is checked
against the local delivery tree; remote CI is followed at its actual head.
