# Issue 28 financial route implementation handoff

All new work here is offline: provider / paid / SEC = 0 / 0 / 0. No old quota,
raw response, failure, frozen Requirement, or production pointer was modified.
The component statuses below are not native Run or production acceptance.

## Callable interfaces

- `financial_duration.inspect_financial_duration(...)`: source hash, proposed
  origin, task terms, reported percent and claimed dates -> exact source
  measurement interval, or unresolved/rejected. Replayer is
  `validate_financial_duration_receipt`. Month-end arithmetic was independently
  found defective, reproduced through the public API, repaired and retested.
  Non-month-end inferred durations remain unsupported; no fiscal-year fallback.
- `financial_candidates.inspect_financial_candidates(...)`: normal full source
  plus catalog task and native filing period -> all literal-led candidate cells,
  original labels/headers, prior periods, scope/unit gaps and ambiguity. Does
  not read fixture recipes, expected values, or prefilled table numbers.
- `financial_relationships.inspect_nim_relationships(...)`: current source plus
  expected CIK and native fiscal interval -> source-named NIM relationships.
  Supports same-table reported + FTE adjustment = managed NII, complete average
  earning assets and net yield; or an explicit source NIM definition, annual
  named-subject narrative and corroborating average-balance/interest/rate total.
  It retains the disclosed rate, not the calculated proxy. Exact task name,
  kind, units and approved tax-basis aliases are checked.
- `financial_candidates.inspect_nim_candidate_evidence(...)`: recomputes and
  binds the discovery and relationship to one exact source cell.
- `financial_balance_scope.inspect_aum_balance(...)`: source CIK, complete
  total-AUM scope, instant at the disclosed end date, USD scale, and repeated
  disclosures. Same-number client assets/average/partial AUM cannot substitute.
- `financial_balance_scope.inspect_total_var(...)`: total VaR, annual average
  statistical window, 95% confidence and one-day risk holding period. Reconciles
  named components and diversification offset; trading components are separate.
  All in-section holding/confidence paragraphs are classified, and unclassified
  competing paragraphs stop the component. The risk holding period is never
  used as the statistic's measurement period.
- `financial_candidates.inspect_balance_candidate_evidence(...)`: binds those
  A11/A12 source scope components back to automatically found candidate cells.
- `financial_structured.prepare_saved_inline_source_set(repo_root, company_id)`:
  normal saved-input selection + verified request ledger -> real native
  SourceSet with ordinary inline HTML. The submissions ledger accession is
  empty because it is a dataset; a new explicit dataset identity is used for
  the native SourceReference schema, without claiming a filing accession.
- `financial_structured.inspect_inline_financial_claims(...)`: native SourceSet,
  Reference, bytes, CIK, period and metric A09/A13. Native fact ordinals are bound
  to original native raw cells. Source labels interpret geography, not opaque
  member spelling. Source XML unit declarations and table scale are checked.
  Ordinary SourceSets require their original submissions inventory; retained
  alternate fixture SourceSets remain explicitly without production credit.

## Verified actual materials

JPM full source has 679 original tables. Automatic discovery found A03=12,
A04=12, A09=3, A11=12, A12=64 and A13=34 numeric candidates. These counts are
search leads, not accepted results or completeness proof.

- A03: source footnote (b) gives October 1–December 31, 2025 for 111%. The
  original annual-window claim is rejected. An old Citi-only exception is not
  silently extended into a new execution authority.
- A04: original JPM/Citi disclose 2.50% / 2.47%; source-named relationships
  reconstruct the FTE numerator and full average earning-asset denominator,
  exact scope names, tax basis, annual interval, amount unit and source precision.
- A11: three complete total AUM disclosures agree at 4,791 billion USD and
  December 31, 2025 as an instant. This does not certify whole-issuer scope by
  itself; that remains a native acceptance obligation.
- A12: 37 + 12 - 9 = 40 million USD total VaR is separate from its 34 million
  trading component. Approved Spec `catalog/r4_v2/A12_trading_exposure.md`
  required_claims is **95% / one_day**. Requirement v3 decision
  `S-A12-COMPOSITE-SCOPE` has the same APPROVED required_scope; owner evidence is
  Issue 28 comment 5524085182. 99% and ten-day are alternative recognized scope
  values and regulatory VaR is explicitly forbidden, not the target.
- A13: JPM normal SourceSet resolves 42,758,000,000 USD; Citi existing fixture
  resolves 42,295,000,000 USD. Both use real native Revenue facts with one
  geography dimension, full duration, original International labels and a
  revenue-column definition. Citi's GB fact is tied to its actual U.K. detail
  footnote referenced by the International row; no old recipe is used to drop it.
- A09: BAC existing fixture resolves 0.0049 with its original nonperforming
  column, percentage-of-outstanding-loans row, native pure unit/scale and
  no-dimension end-date context. JPM has 66 native raw nonaccrual/nonperforming
  fact dispositions, all outside the target full-company ratio; it returns an
  actual STRUCTURED_SOURCE_AMBIGUOUS route. Planning fallback does not authorize
  a provider call. The first broad native-name probe met unrelated nil/dash
  values; target context/units are now classified before numerical adaptation.

## Remaining acceptance boundary

A04/A11/A12 explicitly retain `whole_issuer_scope_status =
REQUIRES_NATIVE_SCOPE_ACCEPTANCE`. Named source relationships, repeated values
and same CIK do not independently prove that every table is whole-company.
Native Evidence, Run, release, qualification and activation remain separate.
No components were put into shared records, Calculator or run_store; the main
agent owns that integration and the unified documentation/source-policy entry.

## Evidence files in this folder

- `source-probe.json`: independently parsed original cells, full source hashes,
  archive equality and raw nine-response wire observations.
- `handoff.json`: file identities, test results and entrypoint summary.
- `month-end-first-reproduction.log`: real public-API failure before repair.
- `financial-structured-first-test-mutation-miss.log`: a failed test whose
  first mutation missed the actual header; corrected by source-table binding.
- `normal-input-probes.json`: independent fiscal year 0000 / malformed CIK
  findings in the main agent's original input adapter.
- `normal-input-fix-verification.json`: both now reject as SOURCE_INTEGRITY_ERROR.
- `all-financial-tests.log`: latest complete combined test run.

The original PR34 final archive was actually opened: 420 members, CRC pass,
SHA-256 `9faefa12c7e81b197c9e1ce97b2738197f9189ea9744d8f587fa720f039032c0`.
The three current source blobs exactly equal the archived blobs. The last nine
wire responses total 58,936 input + 1,017 output tokens; native 4 accepted / 5
failed history remains unchanged. No current qualification credit is inferred.
