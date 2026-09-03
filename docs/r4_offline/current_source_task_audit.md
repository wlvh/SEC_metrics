# R4 current offline source/task audit

This is offline implementation evidence, not a qualification cycle, semantic
freeze, Stage-A, publication or live grant. The exact source declarations and
audited recipes are in `config/r4_fixture_matrix_v1.json`; the generated
`qualified_cases/index.json` binds the current proposal closure and complete
artifact set. `issue_28_v2` remains **NOT_ACTIVATED** pending separate review.
Old `source_audit_evidence.json` and `a03_alternate_scope_blocker.json` record
the genuine pre-policy failures; they have not been rewritten as successes.

## Six production/alternate pairs

Original table/row/column locators below are zero-based within their table.
Every production source is JPMorgan FY2025. Alternates use a different issuer,
accession, source SHA, full DerivedAsset and original layout. Existing B06/B13
contracts are not members of the R4 matrix or plan.

| Metric | JPM production | Other-issuer alternate | Route and scope |
|---|---|---|---|
| A03 | `table_000065 r28c6`, 111% → **1.11** | Citi `table_000075 r4c3`, 115% → **1.15** | Firm-average LCR. Citi is explicitly **2025Q4**, not an annual average; owner-authorized same-source entity/average/quarter proof. |
| A04 | `table_000100 r10c3`, 2.50% → **0.025** | Citi `table_000084 r7c3`, 2.47% → **0.0247** | FY2025 fully taxable-equivalent NIM; reconciliation below. |
| A09 | `table_000222 r4c3`, 0.66% → **0.0066** | BAC `table_000219 r23c3`, 0.49% → **0.0049** | **NO_INDEPENDENT_LEGACY_ANCHOR**. JPM actual structured ambiguity permits a scoped offline request. BAC direct structured success does not. |
| A11 | `table_000149 r9c3`, 4,791 billion → **4,791,000,000,000 USD** | BAC `table_000069 r35c16`, 2,177,708 million → **2,177,708,000,000 USD** | End-of-year total assets under management. Scale is proven by the exact original same-table header; client assets and beginning balances are excluded. |
| A12 | `table_000280 r20c4`, 40 million → **40,000,000 USD** | BAC `table_000147 r23c16`, 34 million → **34,000,000 USD** | 95% / one-day VaR, with approved same-source scope proof. BAC comprehensive market-based total is separated from its 32 million trading-only component and 99% columns. |
| A13 | `table_000640 r6c6`, **42,758,000,000 USD** | Citi `table_000122 r4c3`, **42,295,000,000 USD** | **NO_INDEPENDENT_LEGACY_ANCHOR**. Both are directly disclosed FY2025 consolidated international net revenue and resolve natively before AI fallback. |

The four JPM anchors are exactly 1.11, 0.025, 4,791,000,000,000 USD and
40,000,000 USD. Alternate references are labelled `AUDITED_ALTERNATE_REFERENCE`,
not falsely attributed to the JPM legacy anchor. The A09/A13 references explicitly
deny an independent legacy anchor. A positive fixture class is necessary but
not sufficient for future provider eligibility: **9 scoped positives + 3
structured positives** do not imply 12 authorized model calls. PR-B makes none.

## A04 economic bridge, not a word-based alias

Both disclosures use a full-year FTE net-interest numerator divided by the
same full-year average interest-earning-asset denominator. The common convention
is evidenced by the amounts and denominator, not by calling every occurrence of
“managed” or “taxable equivalent” interchangeable.

| FY2025, millions USD | JPM | Citi |
|---|---:|---:|
| Reported net interest income | 95,443 | 59,792 |
| Taxable-equivalent adjustment | 425 | 106 |
| FTE net interest income | 95,868 | 59,898 |
| Average interest-earning assets | 3,834,359 | 2,426,751 |
| FTE numerator / denominator × 100 | 2.5002353718% | 2.4682383978% |
| Disclosed rounded net yield / NIM | 2.50% | 2.47% |

JPM's FTE NII, average-asset denominator and managed net yield are in original
table 100; tables 659/663 independently repeat the annual net yield. Citi's FTE
NII/NIM are in table 84, with average interest-earning assets in table 86
`r31c4`; its native full-duration, no-dimension `InterestIncomeExpenseNet` fact
provides 59,792 million reported NII. The original Citi narrative at byte ranges
5463881–5464860 and 5469315–5470021 independently describes the annual FTE NII
and NIM, and 16141729–16142424 defines the tax-equivalent adjustment. Citi's
separate “All Other managed basis” divestiture presentation is **not** used as
the basis bridge. All old MetricSpecs remain byte-identical; only the successor
task/spec authority binds these source-specific supported aliases.

## A12 total VaR versus a trading-only component

The unchanged legacy producer explicitly selects **Total VaR average**, not a
trading-desk subtotal. JPM's original table 280 already distinguishes CIB
trading VaR **34 million** from the anchored **40 million Total VaR**: CIB total
37 + Other VaR 12 − inter-portfolio diversification 9 = 40. Its total includes
credit-portfolio, CCB, AWM and Corporate risk beyond trading positions.

BAC's original table 147 has the corresponding issuer-total distinction:
trading-positions VaR **32 million** + fair-value-option portfolio 7 − portfolio
diversification 5 = **34 million Total market-based portfolio**. Selecting 32
would narrow the total-VaR scope that the JPM anchor already uses. Both selected
cells retain the original FY2025 average, 95% confidence, one-day holding period
and million-USD unit. BAC's table introduction explicitly states average
statistics for 2025/2024.

This is comparability of the **disclosed issuer-total VaR metric**, not a claim
that the issuers have identical portfolios or VaR methodologies. Those source
differences remain visible in the original table and scope evidence; the
alternate does not standardize or silently equate their risk models.

## No-anchor closure and original-source navigation

Each positive recipe records two independently derived navigation paths with
concrete original table/header/source-span or native fact/context evidence.
Structured target dates come from the immutable source's native DEI fiscal
year/period and shared entity context, not fixed calendar-date literals. The
reported document end, full duration, CIK, 10-K type and requested FY label must
agree; absent/ambiguous metadata or a quarter/FY relabel fails closed. A native
non-calendar fiscal-year test proves that the implementation does not synthesize
January 1 or December 31.
All original tables remain in the full DerivedAsset. The original table census
lists audited candidate locators and dispositions; windows contain complete,
continuous original tables, and every enumerated outside candidate has a closed
disposition. Replaying an output index cannot change those execution-bound
input coordinates, windows, references, numeric headers or composite recipes.

- **JPM A09:** the real accession-XBRL inventory is evaluated first. Its 65
  candidate claims do not provide a unique approved direct firmwide ratio;
  the actual result is `STRUCTURED_SOURCE_AMBIGUOUS`, not a fabricated failure.
  Independent full-document navigation separates wholesale, wealth and
  criticized real-estate ratios from original table 222's firmwide ratio.
- **BAC A09:** native inline fact `f-2363`, context `c-25`, full issuer / no
  dimensions, `FinancingReceivableExcludingAccruedInterestNonaccrualPercentPastDue`,
  scale −2, resolves 0.0049. Independent original Credit Quality table 219
  has the same 0.49% in the nonperforming column; 0.55% is the prior year and
  0.18% columns are accruing-past-due measures. The exact inline fact is at
  bytes 7180546–7180737. No synthetic table or AI request is invented.
- **JPM A13:** native `us-gaap:Revenues`, context `c-2126`, sole geography
  `jpm:TotalInternationalMember`, full 2025 duration and USD agrees with the
  original consolidated table's 42,758 million. EMEA 24,478 + Asia-Pacific
  14,065 + Latin America/Caribbean 4,215 reconciles that disclosed total, but
  a regional sum is not the selected route. “North America” is never equated
  to U.S. merely because a narrative says it is substantially U.S.
- **Citi A13:** native `us-gaap:Revenues`, context `c-174`, sole geography
  `c:InternationalMember`, full 2025 duration and USD agrees with the original
  table's 42,295 million. Segment international revenues, geographical
  percentages, international cards/loans, assets, net income, global totals
  and prior years are excluded. Global minus North America is not used.

The structured-positive artifact is explicitly a native deterministic claim
and original-source audit, **not** a Reader/Evidence certificate or an AI
attempt. Per-native-claim dispositions preserve the entire selected adapter
inventory. Scoped positives use the existing native Candidate/Evidence path;
the raw table value, scope and period must reconcile exactly with their pinned
certificate on response replay. No second semantic verifier repairs a failed
native Candidate.

A13 regional-sum status is **NOT_IMPLEMENTED / NOT_NEEDED_BY_CURRENT_CASES**.
The owner policy conditionally permits a future sum only with all of its
disjoint-region/context/global-minus-U.S. proofs. This implementation selects
direct disclosed international totals only; both current issuers provide one.
Without a unique direct total, a nonempty native inventory remains ambiguous
(or unavailable if there are no native facts), and no regional sum is
fabricated. Neither the current fixtures nor the summary claim that a regional
aggregation branch has been implemented or tested.

## Zero-call classes and acquisition boundary

The matrix also retains `NEGATIVE_EXPECTED` (bank-subsidiary LCR masquerading as
firm), `NOT_APPLICABLE` (non-financial Marriott), `QUALITATIVE_ONLY` (BAC LCR
has no numeric original-table target), and `AMBIGUOUS_EXCLUDED` (synthetic
unresolved current/prior-period claims). Rejected or REVIEW_REQUIRED native
Evidence remains non-auto-eligible; no provider plan is emitted for any of
these classes.

Pre-acquisition inventory remains the 981-row historical proof that BAC/Citi
bytes were absent. The separate acquisition receipt pins **two** fresh immutable
10-K attempts, ledger 981→983; all quota is consumed. Whole-PR accounting is
provider/paid/SEC **0/0/2**, whereas each local generator/replay has **0/0/0**.
No archive response/cycle is reused, no actual token measurement occurs, and
active R3 and exact R2/R1 publication history are untouched.
