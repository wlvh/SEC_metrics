# PR30 production execution seam rework

Owner review rejects head `f4158590336f65c44ba0916ada1b50af922ad44e`, tree
`d8726fe5103e4546e88acabe8545f2506f22b560` and v2 closure
`sha256:1fd51438196661964d51a8b37d270d05804ac04fd178f599a18f84a80a4d567a`
as final approval candidates. The completed offline evidence remains evidence
at that historical candidate; none is promoted to a live grant.

## Reproduced gap and execution boundary

`S-DELIVERY-SEPARATION` prohibits production-Python changes in PR-C. The
existing scoped request/attempt path is offline-only; the socket-adjacent
adapter reconstructs only the legacy full Reader and Issue #15 transport
policy. PR-B must therefore supply a distinct, dormant R4 live-shaped path,
not relabel the existing offline plan or defer implementation to PR-C.

The production path will be repository-owned pending-live plan -> exact-head
owner authorization -> exact-type live scoped request -> invocation-control
reservation/usage -> native source-bound Candidate/Evidence -> audited
Review/Result -> successor Run disk replay. Recorded tests exercise this
same composition with no provider socket; production remains blocked without
a future valid owner receipt. No actual live plan/cycle/freeze/Stage-A or R4
publication is created by this rework.

## Pre-edit closure impact map

- A (immutable history): R1–R3 artifacts, active/previous/root mirrors,
  Issue #15/ai_first snapshots, old requests/ledger bytes and PR22 archive
  remain unchanged. The acquisition quota is already exhausted.
- B (retained authority): `issue_28_v1`, retained V1/V2 profile engines,
  old task/fixture catalogs and core canonical versions remain unchanged.
- C (new candidate execution closure): extend the unactivated v2 proposal to
  bind all new live-path modules and relevant dependencies, including
  `ai_adapter.py`, invocation control, source-bound acceptance and successor
  Run/replay code. Do not weaken execution-authority checks or re-sign v1.
- D (additive implementation): `scripts/vnext/live_scoped_reader.py`,
  `r4_live_plan.py`, `r4_live_authority.py`, `r4_live_qualification.py`,
  `r4_run_store.py` and `tools/vnext_r4_qualification.py`, with their targeted
  tests and portable-copy canary. Names may be consolidated when existing
  primitives supply the same boundary without a duplicate verifier.
- Narrow shared-path edits: `ai_adapter.py`, `records.py`, `run_store.py`,
  `replay.py`, `workflow.py`, `invocation_control.py` only as needed for
  explicit successor dispatch. Preserve legacy schemas/public APIs and the
  sole reservation-owner provider opener. Update the real egress call-graph
  gate and its tests to enumerate any new approved repository factory.
- Proposal/provenance: `requirement_profile_v3.py`,
  `tools/create_issue28_v2_snapshot.py` and the five v2 files may be updated
  while NOT_ACTIVATED. Add the owner SEC-contact comment capture and typed
  Decision only after its actual URL/author/time/body hash is available.
- Evidence: retain the rejected candidate's benchmark/receipts as historical;
  regenerate only closure-dependent offline artifacts for the new candidate.
  Run one new complete same-workload benchmark and one new independent final
  offline disk replay, clearly separate from live qualification/publication.
- Documentation/tests: update the current PR-B summary, architecture,
  capability, user behavior, testing/SOP/PR checklist and strict negative
  suites. No fast timeout increase or historical artifact reformatting.

## Required plan and verification shape

Nine eligible scoped base calls plus three deterministic risk-based stability
entries form twelve planned calls, with no response reuse and hard cap 24.
Structured-primary and all four zero-call classes receive zero provider plan
entries. The dry-run artifact is explicitly not the final PR-C live plan.

Verify raw/offline plan relabeling, owner receipt/head/plan substitution,
Requirement/source/scope/task/Spec/asset/request/envelope drift, composite proof
or unproven dimension omission, zero-call insertion, count/usage violations,
UNKNOWN no-retry, reservation/crash terminals and no reusable success after
Evidence failure. A portable isolated repository must run the same recorded
live-shaped path without relying on the original source checkout.

This rework has provider/paid/SEC authorization **0/0/0**. PR30 stays Draft;
v2 activation, Ready/merge, PR-C and real provider execution are not authorized.
