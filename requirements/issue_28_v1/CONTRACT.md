# Issue #28 successor Requirement contract

## 1. Outcome

This Requirement governs the remaining vNext delivery after the verified R1–R3
baseline. It separates historical authority, implementation/offline
qualification, and live qualification/publication so later Ratchets do not
rewrite or reinterpret already published evidence.

## 2. Authority

- Requirement ID: `issue_28_v1`.
- Parent Requirement: `issue_15_v1` at its exact frozen closure.
- `decision_register.json` is the only policy-content authority in this
  snapshot.
- `invariant_profile.json` selects a closed set of typed evaluators; it does
  not contain policy values, arbitrary JSON paths, expressions, or branches.
- GitHub Issue #28 is a tracking and review surface. Runtime does not read its
  live body, and this file is not required to be byte-equal to that body.

## 3. Historical plane

- `requirements/ai_first_v3_3_1/**` and
  `requirements/issue_15_v1/**` remain byte-immutable historical authority.
- R1, R2, and R3 Runs, ReleasePlans, PublicationManifests, bundles, receipts,
  rollback/restore evidence, and root mirrors retain their historical schema
  and interpretation.
- PR #22 state at `archive/pr22-r4-development-62678e3` is historical R4
  development only. It has no current/successor qualification credit and its
  responses are not reusable.

## 4. Successor artifact identity

Historical artifacts keep `requirement_hashes` and are interpreted only by a
historical adapter; their bytes are never rewritten. Every successor `RUN`,
`RELEASE_PLAN`, and `PUBLICATION_MANIFEST` must carry all of:

- `requirement_id`;
- `requirement_closure_hash`;
- `requirement_hashes`.

The three values must resolve to one profile-driven Requirement. Missing or
forged successor identity fails closed and cannot select legacy mode.

## 5. Carried safety boundaries

The typed invariants mechanically retain immutable source identity, exact
locator/raw value/unit/period/scope recovery, mechanical Evidence and Review,
dense result keys and compatibility, actual usage/context ceilings, retry
zero, UNKNOWN no-retry, publication predecessor safety, immutable read-back,
rollback, and restore.

## 6. Superseded process constraints

This Requirement supersedes full-filing provider input, the financial
task-by-source Cartesian product, one phase blocked by all eight financial
tasks, B06/B13 in R4, per-child full closure replay/rebuild, full Decision
choice mirrors in Python, owner micro-approval for ordinary implementation,
all remaining Ratchets in one PR, and Issue-body/Contract byte equality.

The successor scope authority is one continuous table window, or at most two,
bound to the complete local source. It forbids semantic selector families and
automatic full-document fallback. Only positive production/alternate-layout
fixtures may create provider calls.

## 7. Delivery separation

- PR-A contains only this transition, generic validation, compatibility, and
  tamper tests.
- PR-B may implement R4 and offline qualification only after PR-A merges.
- PR-C starts from merged implementation and may contain live evidence but no
  production Python changes.
- PR-D independently generalizes `SourceScopeManifest` generation as WB-7.
- PR-E delivers R5 (`B06`, `B13`, `C03`, `C04`) after the required B06/B13
  economic-meaning decision.
- PR-F delivers R6 qualitative, legal, risk, and `CLOSED_WORLD` coverage.
- PR-G delivers Rf: all 39 metrics migrated and every frozen legacy semantic
  producer proven production-unreachable.
- A single PR introduces at most one new production Ratchet.
- R5 B06/B13 economic meaning requires a later explicit owner decision.
- Issues #15 and #24 remain open through PR-A review. Only after PR-A merges
  may they close as `SUPERSEDED_BY_ISSUE_28`, never as completed delivery.

## 8. PR-A prohibition

PR-A must not implement R4 routing, scope extraction, fixture execution,
Issue #24 performance work, SEC acquisition, freeze, cycle, qualification,
publication, or response reuse. Provider/paid/SEC execution remains `0/0/0`.

## 9. Transition completion

The transition is merge-eligible only after exact parent closure, five-file
snapshot closure, complete transfer classification, typed invariant
evaluation, R1–R3 historical read-back, explicit/legacy artifact identity
tests, tamper negatives, clean fast CI, immutable parent diff, and zero-egress
evidence pass. Owner approval must bind the exact PR head and computed
`issue_28_v1` closure hash.
