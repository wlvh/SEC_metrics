# Issue #28 v6: bounded ordinary B10 label repair

The owner's supplemental instruction explicitly permits deterministic label
representation repair and the local engineering needed for PR38. The immutable
issue_28_v5 parent and its failed one-shot retain their old identity and raw-only
meaning. The new ordinary policy does not borrow R4 authorization or restore PR34.

Reuse the existing exact same-cell raw_text/text comparator. text is generated
only by HTML entity decoding and whitespace folding; no model string is globally
stripped, case-folded, searched for elsewhere or used to replace source raw bytes.
Footnote digits, business labels, case, punctuation and unknown aliases remain
significant. Caption comparison remains raw-only.

The bounded row/group/column provenance check additionally closes inherited
misassociation: geography labels belong to the value's source row; population
and operating labels identify the nearest preceding single-nonempty-cell group
heading in the label column; the value column is covered by its task-role and
actual fiscal-year headers and carries the declared source unit. Unsupported
layouts fail closed. No table ID, row number, year, number or company-specific
answer is embedded in this validator. This narrows the existing factual tests,
without changing target metric definitions, aliases or the Reader contract.
Controller acceptance, workflow Evidence and independent Run replay must select
this policy from the bound new Requirement and reconstruct the same Evidence ID.

The fixed owner delegation comment owns one repair budget root. Original 1/1/0
is retained; at most two new reviewed repair executions give cumulative <=3/3/0.
Every execution has retry=0 and the existing payload/resource/actual usage limits.
Each new stage binds corrected code, unmodified-response regression and negative
cases, independent review and the exact input/request. Permanent ordinal slots
cannot reset across heads, stages, input plans or directories. The second slot
requires a known first-repair failure, a different corrected runtime tree and
new regression/review tied to that failure; UNKNOWN/uncertain counts stop calls.
No same-code reroll, old-response success credit, historical rewrite or merge is
authorized. Final owner review controls merge; formal R3 remains unchanged.
