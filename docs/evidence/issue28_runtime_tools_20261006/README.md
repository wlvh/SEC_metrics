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

Known incomplete integration: existing full native CLI rejects the changed
helper imports through a recursive old ancestor byte check. No check was
suppressed or old frozen snapshot rewritten; partial binding refresh was
reverted. The CLI is not reported successful. Native installed dependency
compatibility/new trusted path remains to finish before calling this first R1
delivery complete. Attempts to use the financial numeric renderer for B01 were
also correctly rejected as outside that renderer's metric scope; no fabricated
Run or fake CSV result was retained.

No source was fetched and no model called. Existing business definitions,
source content, failed opportunity and budget history remain unchanged.
