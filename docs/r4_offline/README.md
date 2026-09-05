# R4 PR-B review summary

PR #30 contains the dormant R4 execution and release implementation. Required
local gates pass, including the complete recorded publication rehearsal and
the current 21.308919× aggregate benchmark. PR30 stays **Draft** and
`issue_28_v2` stays **NOT_ACTIVATED** pending independent review. Final Git
head/tree and GitHub CI are recorded in the PR body.

The current proposal closure is `sha256:5b7a386b7c95f8b9542a2251a94ec8d98876e7c833d49132364c77024b27ff9e`. It binds 181 execution files and
retains activated v1, the historical engines and R1–R3 bytes. The
[current review report](release_seam_review_summary.md),
[validation ledger](release_seam_validation_results.json) and
[complete changed-file list](release_seam_changed_files.txt) identify this
candidate; the earlier `summary.md` and `live_seam_review_summary.md` retain
historical results for their own rejected heads.

The six-metric successor ReleasePlan loads Specs from `catalog/r4_v2`.
Registry/applicability yields six JPM production values and 54 unique native
`N_A_STRUCTURAL` Runs with no source or model evidence: 60 new coordinates,
300 cumulative vNext coordinates and 381 public matrix rows. Alternate/stability
Runs stay qualification evidence. The existing Issue15 Projector API is unchanged.

| Metric | JPM production | Different-issuer alternate |
|---|---:|---:|
| A03 LCR | 1.11 | Citi 1.15, disclosed 2025Q4 |
| A04 FTE NIM | 0.025 | Citi 0.0247 |
| A09 nonperforming ratio | 0.0066 | BAC 0.0049, structured |
| A11 AUM, USD | 4,791,000,000,000 | BAC 2,177,708,000,000 |
| A12 total VaR, USD | 40,000,000 | BAC 34,000,000 |
| A13 international net revenue, USD | 42,758,000,000 | Citi 42,295,000,000 |

[Source/task evidence](current_source_task_audit.md) and the
[current 16-case index](qualified_cases/index.json) preserve the approved
A03/A12 composite scope, A09/A11 unit/scale and A13 direct international net
revenue semantics. Four strict legacy anchors and two native backfills pass
compatibility. [The current draft](live_plan_draft_release_seam_final.json)
still has nine base requests plus three risk-selected stability ordinals;
three structured positives and four zero-call classes receive zero model calls.

The [recorded release rehearsal](release_seam_rehearsal_evidence.json) passed
all seven integration tests: 12 scoped executions, three structured Runs,
native 6+54 composition, immutable cold read-back, temporary R4→R3→R4,
two transaction crash recoveries and 14 mirrors. Its qualification/publication
credit is `NONE_RECORDED_REHEARSAL`; the real active remains exact R3.
The committed [PR-C CLI sequence](pr_c_release_entrypoints.md) covers staging,
validation, publication, read-back, rollback/restore and active-terminal.
Real execution and switches still require the separate future owner receipts.

The [complete benchmark](performance_session_benchmark_release_seam_final.json)
uses the same 16 cases, six prior terminal Runs and interpreter in three
independent processes. Including one fresh replay in both alternatives gives
2805.928456s / 131.678594s =
**21.308919×**. [Measurements and counters](performance_release_seam_results.md)
include full-process RSS. The 512 MiB/no-swap claim applies to the guarded
parser worker; [all three source measurements](performance_resource_release_seam_final.json)
use production `max_total_cells=210000` with no override. The sleep-interrupted
attempt is explicitly invalid and retained in the validation ledger.

Local fast passes 32/32 at the original 30-second per-entry cap. Targeted
regressions pass 226/226, the additional cold/substitution suite 2/2 and full
historical regressions 231/231; these counts overlap and are not summed.
Twelve unchanged `test_ai_reader_contract` failures remain disclosed baseline
debt. [Preservation proof](release_seam_preservation.json) records 2,396
unchanged historical files and zero ledger additions in this rework.
Provider/paid/SEC = **0/0/0 this rework**, **0/0/2 for all PR-B**; the two
previous immutable BAC/Citi acquisitions remain the only new filings.
