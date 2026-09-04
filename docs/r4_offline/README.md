# R4 offline one-page summary

PR #30 is **Draft / reworked candidate for independent review**. The six-task
offline corpus and dormant production execution seam have passed their native
recorded, portable and recovery checks; the new benchmark passed at 21.903657x.
The previous head/closure is not an approval candidate. This page is not an
activation, merge, model-call or publication grant.

## Requirement and scope

The unactivated five-file `issue_28_v2` supersedes the unchanged activated v1.
The current proposal closure is
`sha256:ae1cd0cc3c59ae6ad7ef099d6661b5ec7604f7b385fedcbab41b2d7dd6df9bb3`.
Requirement revision 2 uses retained engine V3; old V1/V2 and R1–R3 bytes stay
immutable. All three exact owner policy comments are recorded:
[A12/A13/resources](https://github.com/wlvh/SEC_metrics/issues/28#issuecomment-5524085182)
and [A03 scope/quarter](https://github.com/wlvh/SEC_metrics/issues/28#issuecomment-5524746204),
plus [SEC contact authority](https://github.com/wlvh/SEC_metrics/issues/28#issuecomment-5536668333).
Policy comments are distinct from a future exact-head/closure activation.
Read the current proposal identity from `requirements/issue_28_v2`; it remains
NOT_ACTIVATED pending independent review and a separate owner decision.

[The current six-metric ReleasePlan](../../config/release_plans/issue_28_r4_scoped_engine_v2.json)
adds only **A03 A04 A09 A11 A12 A13** to R3, giving 30 metrics/300 planned keys;
B06/B13 are absent. [The final offline index](qualified_cases/index.json)
contains 12 production/alternate positives and all four zero-call classes:
nine scoped native Evidence PASS, three structured-primary and four zero-call
results. There were no provider executions.

[The dry-run schedule](live_plan_draft_final.json) has nine base requests and
three risk-selected stability ordinals (A03 alternate, A09 production, A12
alternate), total 12 / hard cap 24 / no reuse. The full recorded execution formed
12 native scoped Runs and three native structured Runs; its six integration
tests passed, including full-record tamper, OPEN/FROZEN recovery and new-process
portable replay with the original engine/canonical deliberately broken.

## Source-specific outcomes

| Metric | JPM production | Different-issuer alternate |
|---|---:|---:|
| A03 LCR | 1.11 | Citi 1.15, explicitly 2025Q4 |
| A04 FTE NIM | 0.025 | Citi 0.0247 |
| A09 nonperforming ratio | 0.0066 | BAC 0.0049, structured-first |
| A11 AUM, USD | 4,791,000,000,000 | BAC 2,177,708,000,000 |
| A12 total VaR, USD | 40,000,000 | BAC 34,000,000 |
| A13 international net revenue, USD | 42,758,000,000 | Citi 42,295,000,000 |

[The source/task audit](current_source_task_audit.md) supplies exact table/span
locators, legacy reconciliation, two-path/no-anchor and outside-window closure.
A03/A12 narrative is same-source checker evidence, never provider context.
A09/A11/A12 scale comes from original table markers/headers. A13 uses direct
issuer-disclosed totals, not net income; optional regional summation is not
implemented or credited. Total-VaR comparisons do not claim identical issuer
portfolio composition or model methodology.

## Resource, performance and call accounting

JPM/BAC/Citi have 124761/200229/95463 expanded cells. All pass the same unchanged
production parser in a 512 MiB/no-swap/network-none worker; production cap is
210000, other limits unchanged, no override. [Current-code parity](performance_resource_live_seam_final.json)
and [current benchmark result](performance_live_seam_results.md) distinguish
guarded parser evidence from host-side aggregate timing. The new measurement
achieved **21.903657×** after charging the one 64.286819s final fresh-process replay
to both alternatives (2812.665847s / 128.410783s). All three processes produced
the same 16-result semantic ID with egress 0/0/0. Full-process RSS peaked at
2.412GB/2.137GB/1.835GB; the 512MiB claim applies only to the parser worker,
not the complete host-side Evidence process. The previous 21.789879x receipt
and raw log remain byte-identical historical evidence.

Whole PR-B provider/paid/SEC = **0/0/2**; the two exact immutable BAC/Citi attempts
are in [the acquisition receipt](fixture_acquisition_receipt.json), retry zero.
Quota is exhausted and repeated acquisition is rejected before native fetch.

## Review boundary

Fast is now 29 entries with the original 30-second cap. Full artifact, policy,
transport, native Evidence, history and source tests are separate integrations.
Final local fast 29/29 passed in 8.744s; benchmark receipt checks 4/4 and post-benchmark
R3/R2/R1/14-mirror read-back passed. The [validation ledger](live_seam_validation_results.json)
retains commands, original-log hashes, portable-rendered traces and failures.
Twelve unchanged tests of the disabled legacy uncontrolled adapter also fail at
the exact PR base; they are explicitly BASELINE_FAILURE, not claimed PASS.
[Current rework evidence](live_seam_review_summary.md) records identities/commands and honest
intermediate failures. Historical R3/R2/R1 read-back and all 14 mirrors remain
unchanged; arbitrary owner-token financial execution stops before the opener.
No new live Run/cycle/freeze/Stage-A, R4 publication, rollback, actual token
measurement, archived response reuse or PR-C work occurred. Next owner action,
after the complete rework gates pass, is independent review and v2 activation—not live
authorization.
