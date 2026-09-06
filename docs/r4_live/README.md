# R4 pending live plan — PR-C

Status: **awaiting separate owner live authorization**. No provider/paid/SEC
calls, live Run/cycle, production freeze/Stage-A or publication were performed.

- Merged PR-B: `75002a861555c91aeadd72260d98707225d96f49`, tree `a1fa189d5a99194e1ebe6fbd495df48dcb3d5594`.
- Requirement: `issue_28_v2`, closure `sha256:5b7a386b7c95f8b9542a2251a94ec8d98876e7c833d49132364c77024b27ff9e`.
- Transition receipt: `sha256:2ef83cc98563975a536120b302c7b6427a89e8fa773de1276a83445f451bd108`; [owner approval](https://github.com/wlvh/SEC_metrics/pull/30#issuecomment-5556855154).
- Plan: `sha256:215277ae679bde123e51cf3ce839445e9ef152c5a9f5d0c72f74a2b6618658bd`; [complete entry bindings](pending_plan_review.json).
- Plan was generated on `c11911b6f9a0ac4b0cc9952fbf49828dac6145a2`; later PR-C commits only persist evidence/docs. The eventual live authorization must bind the then-current PR-C head and this plan ID.
- Provider transport: `deepseek` / `deepseek-v4-flash` / `chat_completions`; automatic retries **0**, response reuse **false**.

Nine base scoped requests + three risk-selected stability requests = **12**;
target12–18, hard maximum24. Estimates below are the native conservative byte
upper bound for the exact provider envelope; they are not measured model usage.
Window orders are zero-based, inclusive and preserve original table IDs/grids.

| # | Metric | FY2025 filing | Disclosed period | Role | Window orders | Token upper bound | Reference |
|---|---|---|---|---|---|---:|---|
| 1 | A03 | JPM | FY2025 | BASE | 64–64 | 35972 | INDEPENDENT_LEGACY_ANCHOR: 1.11 ratio |
| 2 | A03 | Citi | 2025Q4 | BASE | 74–74 | 14065 | AUDITED_ALTERNATE_REFERENCE: 1.15 ratio |
| 3 | A04 | JPM | FY2025 | BASE | 99–99 | 17451 | INDEPENDENT_LEGACY_ANCHOR: 0.025 ratio |
| 4 | A04 | Citi | FY2025 | BASE | 83–83 | 19172 | AUDITED_ALTERNATE_REFERENCE: 0.0247 ratio |
| 5 | A09 | JPM | FY2025 | BASE | 221–221 | 13464 | NO_INDEPENDENT_LEGACY_ANCHOR: 0.0066 ratio |
| 6 | A11 | JPM | FY2025 | BASE | 148–148 | 18311 | INDEPENDENT_LEGACY_ANCHOR: 4791000000000 USD |
| 7 | A11 | BAC | FY2025 | BASE | 68–68 | 26197 | AUDITED_ALTERNATE_REFERENCE: 2177708000000 USD |
| 8 | A12 | JPM | FY2025 | BASE | 279–279 | 24883 | INDEPENDENT_LEGACY_ANCHOR: 40000000 USD |
| 9 | A12 | BAC | FY2025 | BASE | 146–146 | 26276 | AUDITED_ALTERNATE_REFERENCE: 34000000 USD |
| 10 | A03 | Citi | 2025Q4 | STABILITY | 74–74 | 14065 | AUDITED_ALTERNATE_REFERENCE: 1.15 ratio |
| 11 | A09 | JPM | FY2025 | STABILITY | 221–221 | 13464 | NO_INDEPENDENT_LEGACY_ANCHOR: 0.0066 ratio |
| 12 | A12 | BAC | FY2025 | STABILITY | 146–146 | 26276 | AUDITED_ALTERNATE_REFERENCE: 34000000 USD |

A09 alternate (BAC), A13 production (JPM) and A13 alternate (Citi) use the
structured-primary route and require zero model calls. NEGATIVE_EXPECTED,
NOT_APPLICABLE, QUALITATIVE_ONLY and AMBIGUOUS_EXCLUDED also require zero calls.
The three stability entries use fresh responses for Citi A03, JPM A09 and BAC
A12; they provide qualification evidence only.

All entries use existing immutable SEC attempts: JPM `0001628280-26-008131`,
BAC `0000070858-26-000157`, Citi `0000831001-26-000011` (exact source URLs,
accessions, hashes, task/Spec and scope identities are in the JSON review).
A03/A12 keep their approved source-bound narrative scope proof. A09 and A13
retain no-independent-anchor controls; A13 means international net revenue.

Post-merge verification passed: unchanged Requirement/execution authority,
fast32/32, active R3/exact R2/R1 and14 mirrors. The approved head is the merge's
second parent and the merge tree equals the reviewed tree. The full PR-B
benchmark was not repeated for an identical merge tree.

Only the committed CLI `python3 tools/vnext_r4_qualification.py plan` prepared
this pending plan. Summary estimates use the existing repository envelope
builder/estimator and reproduce every plan-bound request SHA. Production Python,
Requirement snapshot and active R3 bytes are unchanged in PR-C.
