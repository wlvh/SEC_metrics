# Additive implementation handoff

Only these repository files were written by this subtask:

- scripts/vnext/b06_disclosure_v2.py
- tests/vnext/test_b06_disclosure_v2.py

Historical b06_disclosure.py, source admission, frozen Requirement/Spec and Run evidence remain unchanged. The implementer was first the independent reviewer; findings are preserved in FINDINGS.md. This implementation still needs separate independent review and native integration by the parent.

New resolver: debt_equity_new_source_v2. Intended Spec path: catalog/r5/B06_new_source_v2.md. verify() requires the new resolver. propose() reuses the deterministic v1 proposal because source identity and model selection did not change. The returned proof preserves every v1 field and appends successor_content_checks with content identity, XML/primary numeric reports, alternate measurement explanations and narrative inventory.

Checks:

1. Every consumed numerator/denominator concept, lease components/payments/interest and the two previously exempted debt concepts are parsed in both XML and primary. Subject, instant period, scalar context, actual USD unit, sign, scale and precision are compared with the native parser and precision_choice.
2. A non-consumed LongTermDebt in the inclusive mode is only explained by a summed, explicitly identified future-principal maturity schedule. DebtInstrumentCarryingAmount in the separate-lease mode is only explained by its explicitly named principal column and summed instrument rows. They are not blindly equated to B06's carrying amount.
3. Required full DebtDisclosureTextBlock and LesseeLeasesPolicyTextBlock narratives receive a bounded monetary-balance scan. Explicit outside-debt-table balances, conflicting totals, unknown positive balances, ambiguous periods and unsupported amount syntax reject. Named carrying totals and source-derived credit-agreement groups reconcile automatically. Historical issuance and non-balance borrowing mentions are not keyword-only rejections. No-amounts claims need explicit scope, and cannot erase known positive named members.

Real positive content cases: both PR43 historical originals, plus the existing Salesforce FY2026 source. The latter's 6.0b aggregate is derived from the source-named group and the two table members of 4.0b and 2.0b; no company/CIK/hash/answer condition was added to production code. Its 6.1b contradictory claim is rejected.

Validation: original 13 short tests and six native-material tests passed before implementation. The new full 10-test suite passed in 50.587s; subsequent narrative edits were covered by five tests in 28.741s and three further affected tests in 18.221s. Those logs and exact final file hashes are retained in implementation-summary.json. To include in the fast runner without changing its 30-second per-entry ceiling, select individual test methods; this full module exceeds 30 seconds.

Limits: this is a finite disclosure grammar, not a general reader for every borrowing statement or all notes in an annual report. Current monetary assertion recognition uses the documented lexical and date grammar; unsupported detected statements return explicit ValueError codes for caller status mapping. A different narrative, source scope, balance classification or debt measurement is not thereby proven complete. It does not provide zero-human complete ten-company B06 capability, source fetching, annual automation, new qualification or formal publication. No v2 native Run or production state was created by this subtask. Parent must integrate the new Spec/Requirement and native recomputation, map errors to product statuses, and independently review the residual scope before claiming broader capability.

All calls: provider / paid / SEC = 0 / 0 / 0. Mutated semantic examples are TEST_ONLY and were never admitted as real SEC sources or frozen as real Runs.
