# PR-B owner escalation — no policy choice applied

This document proposes no approved policy and does not create or activate a
Requirement revision. Current `issue_28_v1` remains byte-immutable.

## 1. A12 production positive cannot auto-certify under the retained locator rule

The existing immutable JPM FY2025 source contains the numeric VaR table, but
all 679 native tables lack a holding-period alias from the current MetricSpec.
The exhaustive check uses every allowed confidence and holding-period alias,
not a guessed selector or one preferred combination. Scope exists in external
narrative, not a currently permitted same-target-table locator.

The owner-approved transition explicitly carried D-32
`single_table_locator_invariant=true`. Two continuous source windows do not
silently supersede that policy. Copying prose into a caption/grid, fabricating
an alias, or returning REVIEW_REQUIRED as an auto-certified positive is not
permitted. This meets the START_PR_B escalation condition: a R4 task has no
auto-certified positive.

**Decision needed:** define a permitted evidence policy for this actual source,
or explicitly change the production-source/scope requirement. If an exact
source-span proof is desired, it needs an explicit successor policy describing
source SHA/span identity, target-table association and tamper invariants; it
will not be introduced as an unreviewed bypass of the native checker.

## 2. A13 lacks one economic measure for no-anchor reconciliation

The method defines geographic exposure as revenue, assets **or** risk exposure
by geography. The current direct-numeric USD Spec constrains geography to
international but does not select the economic measure. The real structured
adapter finds legitimate current-period facts in multiple measure families;
using one number would make a product-semantic choice, not an implementation
detail. Two navigation paths agreeing on a selected number cannot authorize
that selection.

**Decision needed:** specify the economic measure, geography aggregation,
period and unit target to carry into the R4 no-anchor closure. No revenue,
asset, loan, deposit or risk scalar is chosen in this PR.

## Ordinary implementation work is not escalated as a new economic decision

A09 percentage-in-a-separate-cell and A11/A12 amount-scale-in-a-header require
proper, source-bound unit normalization. The approved canonical anchors are
not being changed. There is no permission to alter the value cell or claim a
different reported unit to pass the existing downstream equality gate.

If the eventual fix must change any v1 execution-authority input or semantic
runtime version, the implementation will include an unactivated same-Issue
revision proposal with `supersedes_requirement` and preserved v1 read-back.
Neither this request, code nor tests will activate it.

## External prerequisite, not additional spending authority

The original missing SEC contact prerequisite is resolved: the client reads
`config/sec_config.json.contact_email` automatically, with an optional explicit
`SEC_CONTACT_EMAIL` override. No acquisition was run. This does not increase
the two-filing quota or authorize any provider/paid-model call.
