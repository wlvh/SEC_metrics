# R1 current progress on main8588

The short branch starts from delivered main8588, without receiving C02 trust,
pending or version wrappers. The original PR43/worktree and all saved runs,
answers and call history remain available. Public entry docs now link the
2026-10-06 trusted-internal/run-test decision; #54/PR57 is delivered, #28 owns
public/current integration, #47 owns history. Old candidate/Ratchet descriptions
are marked historical. Pending C02 is branch-implemented, pending main, business
unaccepted. R2/R3 simplification is not declared implemented.

Actual dependency reduction: CSV fields/codec/PublicationError are owned by
csv_output and re-exported by publication. Pure catalog validation/Spec compile
and ZeroAiReleaseError move to deterministic_catalog, with legacy re-exports.
AnnualUpdateError/saved-source helpers move to annual_sources. Function bodies
and constants match their original ASTs. Ordinary projection and company output
consume the light CSV module; normal Spec/source preparation use light helpers.
These modules do not import publication/cutover/qualification. The complete
ordinary projection still has other governance dependencies; R1 does not claim
all imports have been removed. No unsafe switch, new approval or platform added.

Actual source calculation through existing
normal_zero_ai_results.resolve_ordinary_zero_ai_metric returns Marriott B01
26186000000 USD, EXACT,2025-01-01 through2025-12-31, registrant annual scope,
10-K0001048286-26-000007. Preparation0.371s, calculation1.529s, import0.332s
in the observed process. This is source/API evidence, not a complete company
Run or business acceptance of other metrics.34directed tests pass in0.471s;
CSV quote/newline/U+037E, exact columns, formula arity/unit/dimension checks and
ordinary source/Spec import isolation are preserved.

Current saved-source CLI integration now succeeds for B01. It calls the same
source preparation/Calculator, checks records and source proofs, then writes an
ordinary record with result/period/unit/Spec/source/program version, CSV and
source evidence. It does not install/re-sign a Requirement or copy a source or
rule tree. Completion is written last under a write lock; an interrupted/failed
attempt cannot advertise success. The new reader checks saved files and
coordinates without calculation. The old failed CLI attempt and old snapshots
remain intact; its failure was a recursive ancestor-code gate, not a business
result failure. Other metric native routes and full company run installation are
still legacy; this does not claim they have been simplified.

One shared Marriott preparation plus small damage/company/period/unit/incomplete
write tests and existing company orchestration/query tests: 39 tests passed in
2.442s. The saved Company Facts original independently lists 26186000000 USD,
FY2025, the exact 10-K accession and annual dates used by the result. New current
CLI succeeded with exit0 in about2s; a separate process will read its committed
output without source calculation. These are development/source results, not
formal adoption or a new full-company acceptance.

The inherited CI collection still exercises old ancestor/trust requirements;
its obsolete runs37478200850 and37478354751 were requested cancelled, without
cancelling any project capture or persistent calculation. A dedicated current
runtime check now covers the affected small tests and real source calculation.
It does not claim the old broad workflow is green. T1 will remove/partition the
retired obligations according to the current Issue instruction rather than
re-signing historical packages to make them pass.

No source was fetched and no model called. Existing business definitions,
source content, failed opportunity and budget history remain unchanged.
