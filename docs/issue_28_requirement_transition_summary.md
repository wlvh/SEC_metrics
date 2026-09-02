# Issue #28 Requirement transition summary

## Approval object

| Field | Candidate value |
|---|---|
| Issue | `#28` |
| Requirement | `issue_28_v1` |
| Exact merged baseline | `e0cd1da793a9851ac853ce3cf62467d199fb192e` |
| Baseline tree | `801ea0206c67d87a216e13a8d49974acbd8d7af0` |
| Parent Requirement | `issue_15_v1` |
| Parent closure | `sha256:e4b1d8141196fae9bb5da904692fd0d495ec69b89101b8304e12f6cb2640b7c7` |
| Candidate successor closure | `sha256:5b14c4d8d4cfa2381adc6f48568d538818110bd82c206f59209bf96ab3789549` |
| Active / predecessor | R3 `publication_4f2542…` / R2 `publication_fe01e2…` |
| PR #22 archive | `archive/pr22-r4-development-62678e3` → `62678e304778970c8d2bc69db45a6b9fc969d01f` |

The exact PR head is deliberately not embedded in a file inside that same
commit. The owner approval must copy the live GitHub PR head and the closure
above; both values are re-read immediately before merge.

## What changes

- Add the five-file `requirements/issue_28_v1` snapshot.
- Keep the two historical adapters and add generation-based profile dispatch,
  so a future profile snapshot does not require another Issue-specific branch.
- Resolve Decision chains generically and execute ten closed typed invariant
  kinds. The profile contains only Decision references; policy values remain
  solely in the Decision Register.
- Classify all 18 effective parent policies exactly once: 14
  `CARRY_FORWARD`, 3 `SUPERSEDED`, and 1 Decision-level `HISTORICAL_ONLY`;
  five PR #22 evidence classes are separately `HISTORICAL_ONLY`.
- Require successor Run identity to contain Requirement ID, closure and file
  hashes together; preserve legacy hash-only Run/Publication bytes.

## What does not change

- `requirements/issue_15_v1/**`, R1–R3 bundles/receipts, active R3, exact R2,
  root mirrors, provider runtime, source routing, freeze, cycle and Stage-A.
- No R4 scope extraction, fixture execution, Issue #24 performance
  implementation, provider call, paid call or SEC request occurs in PR-A.
- PR #22 archive has qualification/current-execution credit `NONE` and response
  reuse `NOT_AUTHORIZED`.
- Issues #15 and #24 stay open until PR-A merges; their later terminal label is
  `SUPERSEDED_BY_ISSUE_28`, not completed.

## Required owner decision

```text
APPROVE_REQUIREMENT_TRANSITION

Issue: #28
PR-A exact head: <copy current GitHub head>
Requirement ID: issue_28_v1
Requirement closure: sha256:5b14c4d8d4cfa2381adc6f48568d538818110bd82c206f59209bf96ab3789549

Approved scope:
- successor Requirement transition
- historical R1–R3 compatibility
- generic invariant validation

Provider / paid / SEC execution remains unauthorized.
```
