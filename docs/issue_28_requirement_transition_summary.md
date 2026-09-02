# PR #29 reworked Requirement transition summary

Status: `REWORKED_DRAFT_REVIEW_PENDING` / `NOT_ACTIVATED`.
This summary is not an approval request, activation receipt, or live grant.

## Identity

| Field | Value |
|---|---|
| Issue / Requirement | `#28` / `issue_28_v1` |
| Exact merged baseline | `e0cd1da793a9851ac853ce3cf62467d199fb192e` |
| Baseline tree | `801ea0206c67d87a216e13a8d49974acbd8d7af0` |
| Reworked closure | `sha256:08994b0aa3324511ce655958fbe3c48fdcd873fa2d63a9bfe4de573046d519ac` |
| Retained engine | `PROFILE_DRIVEN_V1` → `scripts/vnext/requirement_profile_v1.py` |
| Parent closure | `sha256:e4b1d8141196fae9bb5da904692fd0d495ec69b89101b8304e12f6cb2640b7c7` |
| Active / predecessor | R3 `publication_4f2542…` / R2 `publication_fe01e2…` |

The exact head/tree are in the live PR body; embedding the commit's own SHA
inside itself would be self-referential. The rejected head
`3973ef94d950093270df27110a17c317075cf413` and rejected closure
`sha256:5b14c4d8d4cfa2381adc6f48568d538818110bd82c206f59209bf96ab3789549`
are no longer approval candidates.

## Rework delivered

- Independent `SUCCESSOR_RUN`, `SUCCESSOR_RELEASE_PLAN`, and
  `SUCCESSOR_PUBLICATION_MANIFEST` subtypes require immutable generation and
  all three Requirement identity fields. Real builders, schemas, loaders,
  freeze/replay and full publication read-back reject missing/partial identity.
- Legacy Run/Publication hashes equal the selected historical Requirement.
  Historical `ISSUE_15_RELEASE_PLAN` keeps its original ID/closure schema.
- The mutable module is only a version registry. V1 stays available; V2 adds
  one typed product-meaning extension without changing V1. Evolution tests add
  an R5 scope, resolve its pending meaning Decision, and retain old R4 closure.
- All 477 parent choice leaf obligations have exactly one disposition:
  189 carry-forward, 278 historical-only, 10 superseded. D-01 transport,
  D-24 honest security boundary and D-26 fast policy retain their real meaning.
- V1 enforces the R4 exact set, live-call/context/performance bounds, zero-call
  fixture classes, two positive classes only, selector prohibitions,
  SourceScopeManifest bindings, and non-weakenable test policy.
- Recorded Issue-body policy and exact parent approvals replace the incorrect
  identifier-comment provenance. Candidate validation, exact-head activation,
  and live authorization remain separate. No activation receipt is issued.
- Parent loading reconstructs recorded hashes plus immutable snapshot bytes,
  without invoking the Issue #15 live-root adapter. Current successor execution
  independently validates its own inputs.

## Boundaries retained

The five-file snapshot remains intact. Issue #15/ai_first bytes, R1–R3 bundles,
receipts, active pointer, 14 root mirrors, config/catalog, provider boundary,
freeze/cycle/Stage-A and SEC ledger are unchanged. PR #22 archive remains
`archive/pr22-r4-development-62678e3` →
`62678e304778970c8d2bc69db45a6b9fc969d01f`, qualification credit `NONE`, response
reuse `NOT_AUTHORIZED`.

No PR-B, R4 business implementation, actual qualification/publication,
provider/paid/SEC call, Issue closure, Ready transition, or merge is performed.
Full artifact tests use temporary recorded fixtures only; formal successor
publication remains fail-closed. Issues #15 and #24 remain open.

See `docs/issue_28_pr29_rework_audit.md` for the defect-to-test ledger and exact
commands; the PR body records the final head, timings, return codes and CI URL.
