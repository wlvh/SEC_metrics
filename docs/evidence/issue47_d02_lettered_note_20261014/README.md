# D02: lettered note scope and bounded auditor admissions

This is an independent follow-up to PR259's incorporated-note migration, not an expansion of the candidate under review. Required production dependency: PR259 head9934615fdb92025288fb07567077ef995d58467c, already combined with actual mainc25872ee. Local baseline206cd02c has that same tree. PR260's indentation repair is independent and is not required by these explicit Note16 headings. Public controller/store/renderer/model IO/runner are unchanged.

## Actual gaps and implementation

Saved Pfizer FY2022/FY2023/FY2025 Item3 says that certain proceedings are discussed in Note16A. The existing navigation locates the wider parent Note16, then the ordinary selection refuses D02_REFERENCED_LETTERED_SUBNOTE_NOT_MIGRATED. Each original has A. Legal Proceedings, four A1–A4 nested headings, then B. Guarantees and Indemnifications, C, D and E. Their original caption formatting is shared. A1–A4 cannot end A.

The same D02 core now selects a unique requested letter from a consecutively labelled A… list with nonempty matching original caption formatting. Missing, duplicate, out-of-order, gapped or incompatible sibling structure stays refused. B uses C as its end; the last proven letter uses the already bounded parent end. No company/year title or number special case is used. Parent metadata is retained for ownership; the actual A range supplies the full disclosure text. Unincorporated parent text stays in the complete Item8 request when inside Item8.

After locating A, the three real requests exposed a separate consistency gap: four litigation-related critical-audit-matter blocks from the independent auditor remained keyword admissions, while the existing Item8 request correctly excludes the bounded independent report. The source step now removes only those admissions inside the already proved report range. The raw document, Item8 checked range, original report evidence and D03 are unchanged. This does not shrink the request or relax its outside-pool assertion. Unproved auditor endings still reject in the same request boundary. The old defaultFalse remains unchanged.

## Tests and saved-source verification

Four new methods remain in the existing, actually executed TextResultV2SourceTest. They cover A1/A2 retention, B/last-C boundaries, whole Item8 remaining text, duplicate/missing/gapped/different-format/empty-format refusal, real audit-text eligibility, and an explicitly constructed unproved-boundary control. Existing company saved-answer, partial-answer and semantic-contract negatives remain. Five affected modules pass80tests/0.678s/zero skips:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. python3 -m unittest -v \
  tests.vnext.test_text_results_v2 \
  tests.vnext.test_text_business_candidates \
  tests.vnext.test_text_coverage \
  tests.vnext.test_d02_reviewed_source \
  tests.vnext.test_d02_company_saved
```

The positive lettered fixture and audit admission fixture each fail before their respective fix. A test setup initially used defaultFalse for the unproved-report control and hit the earlier note-ownership guard; it was corrected to enter the intended boundary. This is a constructed fixture setup error, not a source/business conclusion. Final logs and the two real before-fix failures are retained here.

Only the three named saved primary documents were initially parsed (1.114/1.090/1.075s approximately). Subsequent changed functions reused these parsed originals rather than rerunning whole sources or a census. Source-controls.json records exact identities and timings:

| FY | Accession | Full A range | Complete remaining Item8 blocks | New request prefix |
| --- | --- | --- | ---: | --- |
| 2022 | 0000078003-23-000024 | 3439..3574 | 1569 | ca9943d6 |
| 2023 | 0000078003-24-000039 | 3888..4038 | 1647 | 02e26d84 |
| 2025 | 0000078003-26-000026 | 3821..3937 | 1605 | d9f0139e |

The range end is exclusive. Each retains A1–A4 and the B heading in the remaining complete Item8 pool, and preserves D03. No additional model extraction, response trimming or third method trial occurs.

## Actual same-company run and read

One new, uncached Pfizer FY2025 company task enters the real source factory and returns its full source bundle once:21.562301s/exit2. No Calculator, result-finishing, provider or network call is allowed. The final nonempty-format refusal refinement leaves this actual captured bundle's complete proposal/request byte-identical; changed-functions verification0.233823s in final-helper-control.json, with no factory/company/source reparse.

The current complete1605-block request is sha256:d9f0139e01c3cb098770574234ad2fcc2165965112d09374d3a08c3666d5f031. The original same-company/FY2025 call0017 is sha256:9a3d41a9eeb77cae4192d426bf7b064c7f1000f5ea57a24f9c8763e22d1cf78d with1359blocks. Seven original request/answer/terminal/wire members are restored byte-for-byte from the already spent35-call archive, without copying a ledger. Requests/source IDs differ; no old response is accepted under the new request.

The CLI accurately reports INPUT_OR_EXECUTION_FAILED, error_category MODEL_RESPONSE_REQUIRED, and D02_COMPLETE_SAVED_REVIEW_SET_MISSING with the full new ID. There is no Result or accepted D02 value. Independent results0.134687s/exit0 exports the same precise missing-answer/null state, preserving all7task files, all7answer files and original source registry/ledger/manifest hashes. The CSVs and company-observation.json are here. This is source preparation and a concrete model dependency, not stable business withholding, zero-computation reuse or complete D02 delivery; a repeat was not run to create a false reuse claim.

Use the same company CLI on this branch with the existing restored SEC source root and separate original call0017 answer root. Source recovery is the existing saved-source procedure in docs/historical_company_usage.md; no additional GET is needed for these originals. The original archive is committed under retained PR52/bcc0c0bc at evidence/issue47_model_calls/9a368413797ddef1/model-ledger.tar.gz, SHA970c98e67b7c7b8c1b55eae6b9dd602917cec45af8c193ec1ac9a5d941acf9a0. Reuse the existing seven-member restoration procedure with prefix root/calls/0017/ instead of0009; preserve terminal/answer bytes and refuse existing outputs.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. python3 tools/vnext_company.py run \
  --company pfizer --period fiscal-years --fiscal-year-start 2025 --fiscal-year-end 2025 \
  --metric D02 --source-root /your/restored/source-inputs \
  --saved-legal-reviews /your/original-answers/call0017 \
  --work-dir /your/new/pfizer-d02/state --output-dir /your/new/pfizer-d02/run
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. python3 tools/vnext_company.py results \
  --company pfizer --state-root /your/new/pfizer-d02/state \
  --output-root /your/new/pfizer-d02/read
```

Original wrong tax selections, overlong quotes, failed responses and spent call ownership remain. A complete matching response and legal-content review are still needed before business delivery. New SEC/provider/model0/0/0; no Ready/merge/adoption/deployment/active. Receiver combination/source recheck and new-head CI remain separate. Progress on #47.
