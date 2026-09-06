# PR30 live-scoped execution seam — offline rework evidence

> Historical report for rejected head `19847e1f3f2d666b131422cd93f0c1230ef4c19e`.
> See [the current release review](release_seam_review_summary.md) for the new candidate.

This report records completed offline rework against the unactivated `issue_28_v2` proposal.
PR30 remains Draft. Policy-content approval is not transition activation,
live execution permission or publication authority. Exact final Git identities
and the completed validation ledger are reported in the PR body.

## Policy and immutable boundaries

The third owner policy comment is
[APPROVE_SEC_CONTACT_AUTHORITY](https://github.com/wlvh/SEC_metrics/issues/28#issuecomment-5536668333),
author `github:wlvh`, created/updated `2026-09-04T06:33:01Z`, original-body SHA-256
`a4cbf288a968a3e829f703bc89b2ba7c8e54be78eb66c5c476e6a28bbe898de8`.
The [capture](../evidence/issue_28_sec_contact_authority.json) records authorized
agent posting and frozen repository-config bytes. `S-SEC-CONTACT-AUTHORITY`
preserves explicit-environment precedence, invalid-override failure without
fallback and public User-Agent/audit visibility. All execution grants are false.
Historical policy loading reads the frozen configuration evidence; current
execution separately verifies the actual repository configuration.

Current proposal closure:
`sha256:ae1cd0cc3c59ae6ad7ef099d6661b5ec7604f7b385fedcbab41b2d7dd6df9bb3`.
It binds 104 execution files, retained V3 engine dependencies and the original
622 parent fragments (619 CARRY_FORWARD, three scoped SUPERSEDED). Activated
v1, retained V1/V2 engines, Issue15 and R1–R3 bytes remain unchanged.

## Production-capable, currently dormant composition

1. `live_scoped_reader.py` creates a private repository-bound request from the
   immutable SEC attempt, full source/DerivedAsset/ReaderInputManifest, exact
   task/Spec, SourceScopeManifest and rebuilt scoped envelope. Raw bytes and
   existing OFFLINE_ONLY plans cannot enter as live capabilities.
2. `r4_live_plan.py` creates only an explicitly unapproved draft shape.
   `r4_live_authority.py` separately owns pending-live/recorded plan subtypes,
   exact head/tree/implementation ancestry, immutable R3/R2/R1 and root pins,
   actual owner-comment verification and private per-entry capabilities.
3. `ai_adapter.py` exact-type dispatch preserves the legacy full Reader path.
   The successor path obtains effective S-PROVIDER-TRANSPORT from the bound
   Requirement and rebuilds source/request/envelope at the reservation-owned
   socket boundary. The R4 context ceiling remains 200000; a larger provider
   technical capacity does not enlarge that policy limit.
4. Native invocation control retains exclusive reservation ownership, usage
   validation, retry zero, UNKNOWN terminal behavior and no cross-execution
   response reuse. Original wire bytes are journaled before durable terminal
   acceptance. The source-bound response context enriches only approved
   A03/A12 dimensions, then uses the existing Candidate/check_evidence path.
5. `r4_run_store.py` persists native scoped Candidate/Evidence/Review/Result
   graphs and all request/invocation/acceptance/authorization/terminal bindings.
   `r4_structured_run.py` uses native XBRL claims/Observation/Calculator, without
   fabricating AI Evidence or Review for deterministic facts.
6. `r4_live_qualification.py` enforces the ordered execution prefix and exact
   aggregate terminal set. Failed, UNKNOWN or incomplete prior entries stop
   subsequent work. Owned OPEN/FROZEN Run crash gaps recover the same terminal
   without a second transport send or extra credit. Independent disk replay
   uses the copied execution closure, not mutable original-checkout imports.

`tools/vnext_r4_qualification.py` is the future frozen CLI. This rework ran only
its `draft` command and isolated recorded tests, never `plan` or `execute`.
The code does not acquire SEC sources or switch publication. Future exact-head
live authorization is separate and has not been requested or issued.

## Six-metric ReleasePlan and twelve-call draft

The new additive [ReleasePlan](../../config/release_plans/issue_28_r4_scoped_engine_v2.json)
has content ID `sha256:d1394f0adbf63e79cf9fa081c352e087a5c95bc53e2f138613610b4b61b38a9a`.
It extends exact `issue_15_lodging_r3` with A03/A04/A09/A11/A12/A13 only:
30 cumulative metrics / 300 planned keys; B06/B13 are absent. The old
`issue_28_r4_offline_v2` plan is preserved as the rejected earlier candidate's
historical proposal, not current execution or publication authority.

The [current draft](live_plan_draft_final.json) ID is
`sha256:a36a6bdb0c92391480c734c8b6ca478773e54796f04688ae2ddd07502339d727`.
It has no exact-head live grant and no qualification/publication credit.

| Ordinals | Fixture / selection | Planned calls |
|---|---|---:|
| 1–2 | A03 production / alternate | 2 |
| 3–4 | A04 production / alternate | 2 |
| 5 | A09 production | 1 |
| 6–7 | A11 production / alternate | 2 |
| 8–9 | A12 production / alternate | 2 |
| 10 | A03 alternate: disclosed-quarter + composite-scope risk | 1 |
| 11 | A09 production: no independent anchor + separate-percent unit | 1 |
| 12 | A12 alternate: mixed table/narrative scope + header scale | 1 |
| — | A09 alternate, A13 production and alternate: structured primary | 0 |
| — | NEGATIVE_EXPECTED, NOT_APPLICABLE, QUALITATIVE_ONLY, AMBIGUOUS_EXCLUDED | 0 |

Base=9, stability=3, total=12, hard cap=24, response reuse=false. Stability
selection uses a deterministic risk-coverage algorithm, not issuer branching
or calls fabricated from structured successes. The current 16-case index is
`sha256:68483a5f1550d6d05880323449d775c1dda7de7910bd6f845487c6957abbf369`.
All six metric values, original locators and approved periods remain unchanged;
see [the source/task audit](current_source_task_audit.md).

## Resource parity and performance boundary

[Current-code resource parity](performance_resource_live_seam_final.json)
preserves the previous receipts. JPM/BAC/Citi retain exactly 679/369/330 tables,
124761/200229/95463 expanded cells and byte-identical full native assets.
Current worker times are 3.351139/4.815198/2.839319 seconds; cgroup peaks are
312340480/383119360/258043904 bytes. All pass 512 MiB/no-swap/network-none/read-only
guards with production cap210000, no runtime override and other limits unchanged.
These resource observations are not an aggregate performance benchmark.

The historical f415859 benchmark remains byte-identical and historical.
The new complete sixteen-case baseline/optimized benchmark and its one final
fresh-process offline replay passed at **21.90365778705671469973047357x**.
The fair aggregate costs are 2812.665847s / 128.410783s, including one 64.286819s
final replay in both denominators. Receipt ID:
`sha256:227770c42164d54b025d8c83b0373011738ac89e5435c25b5a766bfc728c1f23`.
[The full measurement report](performance_live_seam_results.md) records the
231 bound inputs, same interpreter, exact process times, RSS and native counts.
The full recorded live-shaped/portable integration is a separate correctness
gate and is not a measurement of actual provider accuracy or live usage.

## Validation status

Final performance and correctness validation passed:
35 v2/contact/recovery/controlled-wire checks, 85 source/scope/fixture/session
checks, 66 successor seam checks, eight SEC identity checks, fast29/29 (8.744s),
provider call-graph, semantic and scalability. Thirteen complete historical,
transition and publication modules have 231 unique passing tests after the
document/fixture corrections below. The full fifteen-Run recorded integration
passed all six methods in 1456.807s: execution, 12 scoped and six structured
full-record mutations, independent portable replay, and both OPEN/FROZEN crash
gaps for scoped and structured Runs. Its [actual recorded summary](recorded_execution_summary_final.json)
has ID `sha256:770f9f3ce021a2272486dd8585173df88050b9617c99fcd331d1355c2d195489`.
It is a test summary, not a persisted live qualification graph or reuse grant.
Correctness timings under concurrency are not aggregate benchmark results.
Post-benchmark receipt checks 4/4 passed in 3.430s without another replay;
R3 receipt/index, exact R2/R1 and all 14 mirrors passed again in 37.913s.
[The validation ledger](live_seam_validation_results.json), ID
`sha256:a6bfdf5e6a4b29e3403452505646b4b881685429e8c9724e3318258445e47508`,
contains exact commands, return codes, timings and original-log hashes.
Only host-specific paths are normalized in the displayed log text; raw failures
are retained locally and never reclassified as passes.

The unchanged legacy `test_ai_reader_contract` has twelve failures against
both this checkout and exact base c453385: its old tests call the deliberately
disabled `build_approved_transport_adapter()` without a WB-3 execution context.
Both source test bytes and the base failure are independently checked. These
are **BASELINE_FAILURE**, not PASS or a PR30 regression; the controlled WB-3
and successor transport coverage is reported separately. An initial full-context
test harness also blocked Docker's local Unix IPC; the corrected sandbox permits
only the observed Docker socket while keeping IP egress denied. Failed attempts
are retained in the final validation ledger, not silently discarded.

Two narrow maintenance fixes were required by full legacy publication tests:
SOP's completed PR-A table now names its three full `issue_28_v1` paths instead
of unclassified basenames; the legacy-terminal synthetic fixture preserves its
foundation-bound scalability bytes and obtains its complete artifact directory
set from source policy. Neither production provenance/semantic validators nor
historical receipts were relaxed or re-signed. The test's directory stubs are
explicitly synthetic/no-credit, and the final legacy terminal round-trip passed.

Rework provider/paid/SEC=0/0/0; whole PR-B=0/0/2. BAC/Citi attempts are not
reacquired. R3 remains active, no historical response/cycle gains credit, and
there is no live cycle, production freeze, Stage-A, rollback or R4 publication.
The [preservation receipt](live_seam_preservation.json) verifies 2396 protected
regular files, zero forbidden-path diff, the unchanged 983-row SEC ledger and
absence of a current R4 runtime namespace in the implementation checkout.
