# R4 repository-derived call schedule: draft shape only

This report is not a pending-live plan, exact-head owner grant, activation
receipt, qualification cycle or execution credit. It describes the algorithm
and observed shape of the existing 16-case corpus. The rework must regenerate
closure-dependent evidence before the final native draft validation; the
rejected `f415859` candidate is not revived by this report.

## Membership and order

Every certified scoped positive appears once, sorted by metric, production
before alternate, and fixture ID. Structured-primary successes and all four
zero-call classes never enter the call list. This produces nine base calls.

| Ordinal | Fixture | Phase | Fixture execution ordinal |
|---:|---|---|---:|
| 1 | `r4_a03_production` | BASE | 1 |
| 2 | `r4_a03_alternate` | BASE | 1 |
| 3 | `r4_a04_production` | BASE | 1 |
| 4 | `r4_a04_alternate` | BASE | 1 |
| 5 | `r4_a09_production` | BASE | 1 |
| 6 | `r4_a11_production` | BASE | 1 |
| 7 | `r4_a11_alternate` | BASE | 1 |
| 8 | `r4_a12_production` | BASE | 1 |
| 9 | `r4_a12_alternate` | BASE | 1 |
| 10 | `r4_a03_alternate` | STABILITY | 2 |
| 11 | `r4_a09_production` | STABILITY | 2 |
| 12 | `r4_a12_alternate` | STABILITY | 2 |

The three structured positives (A09 alternate and both A13 cases) have **zero**
planned calls. `NEGATIVE_EXPECTED`, `NOT_APPLICABLE`, `QUALITATIVE_ONLY` and
`AMBIGUOUS_EXCLUDED` also have zero. Twelve planned calls remain inside the
Requirement's 12–18 target range and hard cap 24. These are not actual calls.

## Deterministic stability selection

`R4_MARGINAL_RISK_COVERAGE_V1` selects three distinct base fixtures using only
actual recipe/certificate features, never issuer/source identity branches.
At each step it lexicographically maximizes newly covered risks in this order:

1. An alternate disclosed-period proof.
2. Explicit `NO_INDEPENDENT_LEGACY_ANCHOR` status.
3. Mixed native-table and composite-narrative scope disambiguation.
4. A composite scope proof.
5. A distinct numeric normalization mechanism/factor/reported/canonical unit.

An equal score selects the lowest base ordinal. The current certificates
therefore select ordinal 10 for the A03 alternate's real quarter/composite
boundary; ordinal 11 for A09 production's no-anchor and separate-percent-marker
boundary; and ordinal 12 for A12 alternate's mixed scope and million-header
normalization. The billion-header variant remains covered by its base A11
call; this report does not claim that every numerical scale is separately
stability-repeated.

Every stability entry requires a fresh execution and fresh raw response. It
does not reuse the base response or an archived response. Its distinct
ordinal and content-addressed draft entry ID must be carried into the future
pending plan/invocation namespace. No provider response is supplied by the
draft itself.

Each entry also binds the separate fixture-company authority: exact source,
company/CIK, financial profile/traits and source proof hash/offsets. The target
period is resolved per fixture, never per issuer branch. Citi A03 uses its
certified disclosed-quarter proof; all other scoped entries must match their
source's native DEI fiscal default. This prevents the same Citi source from
silently turning the A03 quarter average into FY2025 while allowing Citi's
separate A04/A13 annual tasks to retain FY2025.

## API and validation boundary

- `derive_r4_repository_schedule(repo_root, requirement_id)` reads current
  Requirement, exact fixture membership, corpus file IDs/SHA/size and risk
  shape without full source replay. Its subtype is
  `R4_REPOSITORY_CALL_SCHEDULE_INPUTS`, with native validation explicitly
  `NOT_RUN_BY_SHAPE_INSPECTION`; it is not a draft validation or live grant.
- `prepare_r4_draft_plan_context(...)` verifies the existing 16-case corpus
  once through the ordinary native offline path. Each source is materialized
  exactly once by the pinned, read-only Docker worker under 512 MiB,
  network-none and no-swap guards; the resulting immutable bytes are adopted
  by one source-local native context. This is eligibility
  validation, not the performance benchmark's final independent disk replay.
  Its private process-local context retains only canonical shape bytes and
  exact immutable file pins, not source graphs or reusable responses.
- `build_r4_draft_plan(...)`, `validate_r4_draft_plan(...)` and
  `load_r4_draft_plan(...)` emit or rebuild `R4_CALL_SCHEDULE_DRAFT`. Validation
  rechecks pinned files and reconstructs exact membership, order, count,
  identities and stability choices. A changed count, zero/structured entry,
  risk choice, reuse flag, head/grant field or record subtype fails.

The draft has `exact_head=null`, `owner_authorization=NOT_ISSUED`,
`provider_paid_sec_authorized=false`, and no qualification/publication credit.
A distinct repository-owned pending-live factory must build the genuine live
scoped request/envelope identities and bind the reviewed implementation commit
and tree. A later owner receipt binds the actual execution head/tree and the
exact pending-plan ID; the implementation commit must remain its ancestor with
no intervening production Python changes and no execution-authority byte drift.
This allows evidence-only PR-C commits without pretending that a plan can contain
the hash of the commit that will subsequently contain that plan. The factory
consumes C's guarded private live-request
session; it must not reuse the draft verifier as a production resource bypass.
It cannot authorize execution by changing an offline
plan's mode field or by relabelling this draft.

No source/fixture value, acquisition, current corpus artifact or historical
Requirement/publication byte is changed by this module or report.
