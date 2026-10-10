# Explicit visible auditor source candidate — 2026-10-10

This branch adds a development source inspection. It does not change the structured-only C04 contract, manufacture AuditorName facts, create a Result, or give no-auditor-change credit.

## Actual execution

Base main `f51d8c3d27f3169b9cdb3a246295830882240c1f`; tests executed against the modified worktree at `/Users/lyuhongwang/.codex/worktrees/issue28-visible-auditor-source/SEC_metrics`, not yet a committed patch SHA. Source root is the existing read-only saved corpus; paths, hashes and exact UTF-8 spans are in the JSON. New SourceReference values in this inspection are explicitly development references, not historic request or Result re-signatures. No SEC/provider/paid request was issued.

Ford2020 exact original SHA `526fb5776b965a871eb0ae49ec307a51a93166e9ee7199413a33af40d9e0bd35` produces one bounded financial audit-report candidate: Ford Motor Company, December 31 2020, `/s/ PricewaterhouseCoopers LLP`, February 4 2021. The native registrant is `Ford Motor Co`; a finite terminal Co/Company lexical equivalence is used and both source strings remain saved. Inspection 1.878s; independent rebuild from original bytes 1.869s. This is an independent source rebuild by the executor, not a second agent's business acceptance.

Marriott2020 original `0001628280-21-002433` and amendment `0001628280-21-006440` each retain two separate report scopes and two EY signatures. The financial report cannot inherit the preceding ICFR signature. Both remain UNRESOLVED: native registrant `MARRIOTT INTERNATIONAL INC /MD/` does not strictly correspond to visible `Marriott International, Inc.` under this limited adapter. The amendment additionally retains TEXT_AMENDMENT_SOURCE_SET_REQUIRED. No broad name-equivalence rule is invented to force these through. Their original signatures/spans are retained for the explicit next source/subject decision.

Small response/source tests: 25 tests, no skips; exact log is targeted-tests.log. Counterexamples include other auditee/opinion subject/period, hidden or report-external signature, multiple financial reports/signatures, malformed namespace, rehashed locator mutation, missing name, legal-name alias, truncation and amendment. Existing text-reader default regression remains included. The new CI step explicitly selects these tests.

## Responsibility and limits

Shared change: `text_coverage.build_text_document` and `verify_text_document` gain optional `dei_release=YEAR_ONLY`. Default return shape/identity is unchanged. The explicit source adapter selects the existing YEAR_QUARTER_OR_DATE policy; fake namespaces still reject. No C04 default, old Spec/Run/Result, calculation, source fetching, event census or consumer code is modified.

The report candidate is deliberately not semantic business acceptance. Standard-layout coverage is finite; unsupported layouts/name relationships and conflicts remain unresolved. The current structured-only C04 input contract does not yet consume visible audit-report signatures. A successor source-policy/acceptance decision and actual company consumer validation remain necessary before a visible report can repair a withheld C04 result. Do not treat the candidate as a new correct company result.

Peer original reading was fixed at `b5bcbc1a2f0b3b1120c5c9e2ed6eec38881c77f9`; after the later fetch origin/task/sec-history-five-year was `bcc0c0bc0293ba6b6ffc58b1f4e9034dbb52a786`. The former exact reading remains an available Git object; the latter is the actual fetched branch tip, not falsely claimed to contain the newer reading. Peer consumer/state is not modified.

## Limited independent review

Exact patch `22a6f601` received PASS for the four assigned source/test/workflow files, 25 small tests and full default-object equality controls. Reviewer did not rerun the real saved corpus, source driver or company chain. See independent-review/conclusion.md. Source signatures are unchanged after this review; tested-tree.json binds the actual code hashes. This remains source-only credit, not C04 business acceptance.
