# B06 independent initial implementation review

Scope: read-only review of source admission and native Run wiring; semantic mutation tests use only the previously reviewed PR42 Southwest FY2025 material, accession `0000092380-26-000004`. No new samples were solved; no SEC/provider calls; no production source files changed. Mutations are explicitly TEST_ONLY and receive no SEC source credit.

Reproduction script: `/tmp/b06_independent_initial_review.py`
Initial result record: `/tmp/b06_independent_initial_review_results.json`
Run from repository: `PYTHONPATH=scripts python3 /tmp/b06_independent_initial_review.py`
Initial reviewed b06_disclosure.py SHA256: `be42d7056e1f2837f377019d91bf7ccca574033c2ff74398502d7039bccee812`.

The unaltered PR42 material was ACCEPTED. Four counterexamples also returned ACCEPTED and were reported to the implementer before new-sample native acceptance:

1. Append `The amounts in the debt table exclude all finance leases.` after the existing inclusion sentence in both XML and primary HTML; rebuild proposal and raw identity. Numeric inputs remain unchanged, but the explicit source conflict is accepted because the original negative matcher requires finance leases to precede the negation.
2. Insert `<tr><td>Debt, noncurrent</td><td>99</td></tr>` in the actual primary balance sheet before Total current liabilities; rebuild proposal. Known label recognition alone assigns inclusion, without reconciling value or duplicate liability rows.
3. Add same-subject, same-period USD instant custom `luv:TaxFinancingLoan=99000000` to valid XML and rebuild identities. The new project is explicitly discovered but excluded solely because its name contains `tax`.
4. Add same-subject, same-period USD instant custom `luv:EmergencyCreditFacility=99000000`. It is completely absent from inventory because the financing matcher omits credit/facility.

Additional code-review findings (reported, not claimed as executed exploits):

- replay trusted its sealed selected object without comparing filing identity, fiscal label and amendment state to the pinned submissions and DEI originals. Content hashing cannot replace rebuilding those facts.
- portable fallback called a helper requiring ROOT/.git before reaching the frozen checkpoint; no-Git exports could never use that fallback.

Minimal repairs agreed by implementer: bidirectional subject/negation relationship checks; reconcile balance-sheet financing lines and detect unexplained/duplicate lines; restrict nature exclusions to supported standard concepts and include financing facilities; reconstruct selected metadata from pinned source bytes on cold replay; allow trusted installed checkpoint on no-Git portable replay.

Initial results must remain historical after repairs. Re-run the script into a distinct result file to preserve first/final performance.

## Follow-up: source numeric-sign binding

A further bounded check on the PR42 Salesforce primary document changed both visible `535` cells to `(535)` while XML stayed unchanged. The original whitespace/punctuation-stripping comparison wrongly accepted this conflict. Its initial independent result is `/tmp/b06_primary_sign_initial_results.json`; reproduction is `/tmp/b06_primary_sign_review.py`.

After repair, the comparison removes whitespace only and preserves parentheses, signs, decimal points and punctuation. Independent recheck `/tmp/b06_primary_sign_repaired_results.json` shows unaltered Salesforce ACCEPTED and primary-only parentheses REJECTED with `PRIMARY_NOTE_SOURCE_CONFLICT_OR_MISSING`.

The new scope scan also discovered an unresolved supplier-finance obligation in the original PR42 Southwest document. Retaining that gap is correct and does not invalidate historical v3 semantics. Inclusive-mode semantic tests use an explicitly TEST_ONLY derivative zeroing that item; they are not two-real-filing native acceptance evidence.
