# Numeric note references on reported revenue totals

User's latest #28 instruction and the fixed #47 evidence handoff9d4247ed
identify an implementation boundary, not a revenue definition decision.
Ford FY2024/2023 complete consolidated income statements label their reported
total `Total revenues (Note 4)`. The shared label normalization leaves this
numeric note reference in place, so current V2 and V1 scope admission both
skip the row. A separate full-scope counterexample shows old normalization
also removes `(Europe)`/`(Subsidiary)` and falsely accepts a restricted label.

This one bounded class preserves known single-letter/number footnote markers,
adds the explicit numeric `Note N` reference, and retains words that qualify
scope. Native total, complete statement, original entity/period/unit/table
and supplied XML proof must still pass. No generic removal of parentheses,
component sum used as an answer, forced complete_scope_proven or old success
fallback. Implementation and actual company validation continue here.
