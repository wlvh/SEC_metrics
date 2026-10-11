# Remaining Lumen years after the delivered FY2022 consumer

Existing PR165 code `fc876d29` (same actual9ee tree), unchanged model/source/budget. The same existing task adds the other four requested FY2021–2025 years, rather than repeating FY2022. One mixed company command takes47.907s; both FY2022 results report zero calculation and retain their IDs/files. FY2021 B01=19687000000USD is complete. FY2021 B02 remains held because original FY2020 statement scope is not yet supported. FY2023–2025 B01 fail before calculation and B02 save accurate scope withholding. Seven completed results and three unresolved input failures are separate; the ten readable rows do not establish five-year business completion.

A first repeat incorrectly applied a stable-result-only factory guard to an input failure. Its original AssertionError observation is retained; the guard error does not replace the underlying source problem. The corrected observation counts actual producer calls and allows only the three still-failed B01 inputs to recheck their source. Completed successful/withheld results must bypass preparation/calculation; failed input attempts are eligible for normal processing. The later accurate failure and read checks preserve all saved results without editing old check records. See the corrected receipt when appended below; do not call the original24.312s a zero-work five-year repeat.

Source-only diagnosis uses the unchanged public reader, preserves its exception and captures the actual `_statement_scope` unknown-cell proofs. No original quote is trimmed or treated as an approved caption in this evidence. Four exact statement variants are the implementation gap:

| Original source | Table / cell | Exact unknown heading |
|---|---|---|
| FY2020 accession0000018926-21-000017 | table000035 r12c0 / r19c0 | OTHER (EXPENSE) INCOME / BASIC AND DILUTED LOSS PER COMMON SHARE |
| FY2023 accession0000018926-24-000016 | table000030 r22c0 | BASIC AND DILUTED (LOSS) EARNINGS PER COMMON SHARE |
| FY2024 accession0000018926-25-000010 | table000030 r22c0 | BASIC AND DILUTED LOSS PER COMMON SHARE |
| FY2025 accession0000018926-26-000014 | table000028 r22c0 / r25c0 | BASIC AND DILUTED LOSS PER SHARE OF COMMON STOCK / WEIGHTED AVERAGE COMMON STOCK OUTSTANDING |

Each diagnostic JSON supplies full source SHA, actual filing/period and cell byte-span/hash. FY2020 is only the prior input for FY2021, not a sixth output year. The public owner #28 maintains the same scope core; this evidence is delivered to it for a finite source-header repair with qualifier/unknown-text negative controls, not an unrestricted vocabulary or separate reader. The initial diagnostic stack observer accidentally captured the unittest mock frame and raised KeyError; its log is retained, and the corrected observer finds the actual `_statement_scope` frame. It does not modify the production behavior or count as a new model method trial.

Reproduce a source-only failure on the original PR165 code with already restored sources:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. python3 \
 docs/evidence/issue47_b01_scope_consumer_20261011/remaining-years/diagnose_scope_year.py \
 --year 2023 --source-root /your/saved/source-inputs --output-file /your/new/diagnostic2023.json
```

After the shared repair, this prior-version failure driver need not be rerun to fabricate a failure. The original source/reference and exact exception remain here. No new GET/model/provider/paid call, no old result/Run alteration, no acceptance/Ready/merge/adoption/active action. PR165's accepted-for-review FY2022 product scope/head stays stable; subsequent business correction is a separate finite shared-core increment, with historical consumption of that same implementation.
