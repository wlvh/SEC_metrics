# Historical B03 consumes the already-received link-only amendment proof

Independent successor development; PR167 remains unchanged. Main116's source classifier already permits ORIGINAL_STATEMENT_VALUES for a link-only 10-K/A with unchanged original Item15, exact cover/note/signature and unchanged fiscal window. B03 was unconditionally stopped by the new historical adapter before consuming that existing proof. The policy's excluded metrics do not include B03. This is a consumer gap, not a new source or policy decision.

The historical source adapter now calls the exact existing historical_statement_cases._statement_amendment_checks. Every amendment must pass the shared original-value check; PartIII event-only, financial correction, unresolved scope, period change or pending further review still refuses before calculation. Successor financial periods remain IMPLEMENTATION_GAP. No classifier/policy/current selector/Calculator/controller/writer is rewritten. The exact scope and original/amended proofs enter the selected input and ordinary assessment; no-amendment inputs do not get an empty scope field added to their binding. Actual new read dependencies are named.

Twenty source/amendment/selected-coordinate controls pass0.019s,0skip. They include the existing actual amendment consumer logic and explicitly constructed event-only/period/issue/further-review and second-amendment refusal. Constructed controls are not financial statements.

Actual Southwest FY2025 uses original10-K0000092380-26-000004 (primarySHA4f687048...) and amended10-K/A0000092380-26-000006 (SHA17bc6e90...). Its existing source classification and scopeID17be3f58 exactly match the already read PR116 reference: only Exhibit3.2 hyperlink/certification correction, ORIGINAL_STATEMENT_VALUES retained. It does not license event/governance interpretation or all amendments.

The same company CLI starts a new empty external task. First7.564s returns B03=0.07084060863058119231728610626 ratio, fiscal2025 and actual2025-01-01..2025-12-31, CIK92380. Revenue28063m, operating income428m, D&A1560m match complete primary/XML native annual facts. The full consolidated income table33 labels those amounts, and cash-flow table36 reports the same1560m D&A, with impairment8m separately listed. The surrounding source explains software depreciation318m is included in the reported D&A line; no software/accelerated depreciation/impairment/pension-cost amount is added again. Formula is the installed (Operating income + D&A)/revenue; it is not the company's projected adjusted EBITDAR, which separately adds rent and adjusts special items. Source reading/source SHA/native ordinals are saved adjacent. The first source-reading export attempted a nonexistent block_index field; the original error is retained and only field selection was corrected, no source/expected value modified.

Factory/selected computation/Calculator-forbidden repeat1.252s reuses the same resultada97035 without new calculation or directory. Independent CLI read0.587s exports the same period/value/source and keeps18statefiles byte-identical;7 result files unchanged. Both new task and reading use the public controller/writer, no historical-only storage or manual operands. The source-bound D&A helper's complete_depreciation_scope_proven remains false: its mechanical KEEP is not a global semantic certificate. This targeted original-table review supports this reported quantity; other years/companies require their own source relation.

Review commands, after this successor code is available alongside its exact public prerequisites:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. python3 tests/required_unittests.py \
 tests.vnext.test_historical_b03_case tests.vnext.test_historical_statement_cases.HistoricalStatementAmendmentTest \
 tests.vnext.test_selected_income_calculation
python3 tools/vnext_company.py run --company southwest_airlines --period fiscal-years \
 --fiscal-year-start 2025 --fiscal-year-end 2025 --metric B03 \
 --source-root /your/restored/source-inputs --work-dir /your/new/southwest-b03-state \
 --output-dir /your/new/southwest-b03-runs
python3 tools/vnext_company.py results --company southwest_airlines \
 --state-root /your/new/southwest-b03-state --output-root /your/new/southwest-b03-read
```

Prerequisite: PR167 selected income core (currently developing on fixed166+mainb529); consume the public owner's repaired166/current configuration/CI before reception. This successor is kept on a separate short branch, not appended to the candidate under review and not yet proposed as another deeper PR. No claim of main delivery, five-year B03, original3Marriott D&A completion, successor/PartIII amendment support, online source discovery/completion or1950-target acceptance. Original failures/Run/results/source ledger remain.0 new SEC/provider/paid calls, no Ready/merge/adoption/deployment/active action.
