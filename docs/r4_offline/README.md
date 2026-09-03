# R4 offline one-page summary — A03 alternate scope blocked

## Current continuation after owner policy comment 5524085182

The A12/A13/resource policy comment was posted by explicit owner delegation and
is retained in `docs/evidence/issue_28_prb_policy_revision.json`. Native SEC
preflight passed. Both approved BAC/Citi filings were acquired with HTTP 200,
one attempt each and retry zero: [acquisition receipt](fixture_acquisition_receipt.json).
The ledger grew from 981 to 983 rows, preserving its exact old prefix;
provider/paid/SEC accounting is **0/0/2**, with no filing slots remaining.

All three complete sources passed the 512 MiB/no-swap/network-none worker.
Expanded counts are JPM 124761, BAC 200229 and Citi 95463. The production cap is
now 210000 (smallest 10000-rounded sufficient value, 4.88% headroom); the worker
no longer overrides it. All other production resource limits are unchanged.

Fresh sources exposed a new [A03 alternate scope blocker](a03_alternate_scope_blocker.md).
Root independently repeated both exhaustive source censuses and the native Citi
probe: numeric value 1.15 is verified, but Candidate remains REVIEW_REQUIRED and
system_approval_eligible is false. The approved A12-only composite policy does
not permit A03's entity/average narrative or silently change its averaging period.

**PR-B remains incomplete.** The unactivated `issue_28_v2` snapshot has not yet
been generated; full v2/composite tests, six production/alternate fixture pairs,
the aggregate >=10x benchmark and independent full R4 replay are not passed.
Current bounded fast tests pass 23/23 (8.464s); full R3/R2/R1 read-back, R3 PASSED
index and 14 mirrors pass (39.087s). No old snapshot, retained V1/V2 engine,
publication, freeze/cycle/Stage-A or historical receipt bytes changed.

## Initial v1 diagnostic baseline (commit 3404f5d; historical context)

**PR-B is not complete.** B0 and bounded transport/session/audit work are
implemented; the user-defined A12 no-auto-positive and A13 no-anchor/economic-basis
escalations stop further feature expansion. This is not live qualification.

Base main is `c45338567700e3048f4cf32d251369e4521e9444`, tree
`0b8ccaf6b6b708b2c07b8f4ce1d5dd178638493a`. Requirement `issue_28_v1` remains
at `sha256:08994b0aa3324511ce655958fbe3c48fdcd873fa2d63a9bfe4de573046d519ac`.
The unchanged [activation receipt](../evidence/issue_28_transition_activation.json)
is persisted in PR-B. No revised Requirement was created or activated.

## Implemented and tested

- [B0](B0_interface_baseline.md) was tested and committed as `2c0d2e2` before
  the three source/transport/performance tracks started.
- Strict SourceScopeManifest and scoped plan/request/attempt loaders bind full
  source/asset/task/Requirement identities, original table order/grid hashes,
  native Candidate/Evidence, references and complete declared audit census.
  Four-file disk artifact sets are exact; self-rebinding cannot change pinned
  scope IDs. Native single-table scope/locator rules remain enforced.
- Process-local session shares immutable bytes, rejects source/authority drift,
  UNKNOWN, crash and reuse terminals, and exposes native operation observers.
- Exact successor [R4 ReleasePlan](../../config/release_plans/issue_28_r4_offline_v1.json)
  adds only A03/A04/A09/A11/A12/A13; parent is R3, cumulative scope is 30 metrics /
  300 planned keys. B06/B13 are absent. Plan content ID:
  `sha256:60d8811c2577144ad04151a8fdb843f1ca1c19f226c904af4cac7678723357b4`.
  This is planning evidence, not migration/publication or qualified results.

## Real source findings

| Task | Native JPM probe | Remaining gate |
|---|---|---|
| A03 | Evidence PASS, normalized `1.11` | Full production/alternate fixture certificate pending |
| A04 | Evidence PASS, normalized `0.025` | Full production/alternate fixture certificate pending |
| A09 | `0.66` plus separate percent sign; current declared ratio gives `0.66`, percent gives `0.0066` but violates downstream reported-unit binding | Unit binding and no-anchor closure incomplete |
| A11 | Raw `4,791`, separate billion header; native normalized value is `4791` | Header-scale implementation gap; not reconciled to `4791000000000 USD` |
| A12 | Raw `40`, separate million header; native result is REVIEW_REQUIRED / auto=false | **No holding-period alias in any of 679 tables; no auto-certified positive under retained D-32** |
| A13 | Actual structured adapter finds multiple geographic measures | **Economic basis (revenue/assets/specific risk exposure) is not uniquely defined; no scalar invented** |

See [source audit](source_audit_summary.md), [machine evidence](source_audit_evidence.json)
and [exhaustive A12 coverage](jpm_a12_scope_coverage.json). A09/A13 ran the real
accession XBRL adapter first; neither table fallback nor the stronger two-source /
two-navigation / out-of-window closure is claimed complete.

## Performance evidence and limits

The complete JPM native asset is
`sha256:694e176416c50b28974e8fa9844bd0d8e6ee772bd3915b2819aa708bab288110`
(679 tables, 124,761 cells). An additive read-only/network-none 512 MiB worker
uses the existing parser in an explicitly offline research boundary; legacy
resource limits remain unchanged. The observed worker/host wall time is
3.118114 / 5.109096 seconds and cgroup peak is 304,685,056 bytes. Native
parse/build/canonicalization/semantic-hash counts are `1/1/683/681`.

[Performance evidence](performance.md) inventories six prior FROZEN Runs and
separately records one successful existing portable Run replay. The aggregate
unoptimized-versus-optimized R4 benchmark, **>=10x gate**, and final independent
complete R4 disk replay are **NOT_RUN**, not PASS. The small B0 final-replay
test is not substituted for the missing full R4 replay.

## Preserved boundaries / next owner gate

Provider/paid/SEC calls are `0/0/0`; new immutable SEC attempt IDs are `[]`.
BAC/Citi source insufficiency is proven. Both acquisition slots remain unused:
the original preflight returned `SEC_CONTACT_EMAIL_REQUIRED` before any opener or
ledger mutation ([historical preflight](source_acquisition_preflight.json)).
Contact now loads automatically from repository config; no acquisition was run.
The exact
future filing identities are recorded as metadata only, not reused bodies.

Historical R1–R3 / Issue #15 bytes, retained V1/V2 engine and all nine execution-
authority files/semantic versions remain unchanged. No production freeze,
cycle, Stage-A, R4 publication, rollback/restore, model token measurement,
archived response reuse, or PR-C work occurred. PR remains Draft; Issue #28
remains open and its recorded body is unchanged.

Owner decisions are limited to the listed escalation boundaries: whether/how
A12 may obtain a permitted, source-bound scope proof without violating the
retained single-table rule, and which A13 geographic economic measure is the
product target. Unit/header reconciliation remains an implementation obligation;
it is not presented as permission to change the economic values or weaken
Evidence. See [decision request](owner_decision_request.md).
