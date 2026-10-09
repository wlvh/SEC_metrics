# B03 contract-revenue deduction: segment total and visible columns

Base main9493ed0e. Fixed peer source diagnosis was read from
origin/task/sec-history-five-year at0918862a (the stored f59dc4f7 diagnostic
is earlier content), historical-income-receiving-2026-10-08. The peer's
removal-of-aggregate diagnostic was not adopted as an input.

Two narrow defects are corrected. The actual four amortization facts contain
one consolidated fee deduction, two individual operating segments, and an
overlapping operating-segments total. The old function rejects that last
scope. The new check allows one total only when its same-product scope is
OperatingSegmentsMember and its amount equals the distinct individual
segments; the segment sum must not exceed the consolidated amount. It is
never added again. Every original fact must still map to a gross/deduction/net
row relation and the correct visible year.

Allowing the aggregate alone still failed real sources (aggregate-only.json).
Actual 2021/22 use paired empty td display:none, and 2023 uses self-closing
empty td display:none. The inherited table grid counts them as visible columns,
shifting the total underneath the next year. A private revenue-table index
ignores only explicitly display:none empty leaf cells, preserving original
bytes, native fact order, normal spacers and all nonempty/child-bearing cells.
There is no global table_grid/financial_structured change or source rewrite.
The native fact and request references retain the original raw-byte positions.

The read-only reproducer validates the precise saved request/body bindings,
then derives all four facts directly from each actual source. The original
fixed function rejects all three; final-saved.json keeps all four gross-to-net
proofs each. FY2021:55+20=75m; FY2022:60+29=89m; FY2023:65+22=87m, below the
consolidated88m. The87/88 difference is retained, not rounded away or converted
into an extra add-back. All unit/context/entity checks and raw bytes remain.
No historical Result/Run is changed, and this does not prove complete annual
D&A: fulfillment-cost and lease expense questions still belong to the
consumer's existing B03 limitation. The three historical B03 results remain
withheld pending that distinct issue; this delivers the revenue relation.

The synthetic regressions cover duplicates, unresolved total/scope, wrong
net relation, invisible empty cell layouts, visible spacers and nonempty
hidden cells. Initial test fixture omitted native contextref and was corrected
without changing the business guard; small-after.log preserves that failure.
The first source logging attempt failed on mappingproxy JSON serialization;
saved-first.stderr is retained. No source or business object was mutated.
Final module tests include actual current Marriott458m + excluded135m and
Salesforce withheld/subtotal safeguards. The newly appended fast selector has
no runner-body change; existing company-current executes this module.

Zero SEC/model requests, source-root writes, old-results re-signing, or full
historical reruns. Tested worktree is main9493ed0e with the named code/test/
selector differences; commit identity and limited review are recorded through
Git rather than describing dirty runs as committed-head runs.

## Limited review and targeted style correction

Review2bec3464 reports NEEDS_FIX/P2: duplicate display declarations or a
comment containing display:none could make a visible empty spacer be removed.
The report is retained unchanged. The correction only skips a single clear
display:none declaration, refuses comment ambiguity, and keeps conflicting/
duplicate declarations as original cells. Three reported variants are added
to the existing finite regression. It does not implement CSS precedence or
prove general CSS rendering. The final original-source triples are rechecked
in style-fix-saved.json; complete historical B03 credit remains unassigned.
