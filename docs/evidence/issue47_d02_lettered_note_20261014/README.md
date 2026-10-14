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

## Self-review: located report status was insufficient (2026-10-14)

The first589b3f88 audit-admission change was not safe on all known sources. It treated the shared LOCAL_REPORT_RANGE_LOCATED status as sufficient proof of report ownership. Two real Lumen sources expose why this is false: the report parser skips financial captions that are not emphasized and closes the second report at Item9, beyond the statements and registrant's legal Note18. Applying the first change would remove actual litigation admissions and yield an empty remaining request pool. That intermediate output is preserved in lumen-unsafe-boundary-before.json, including the full falsely removed text. It is a program failure, not an applicable zero or business acceptance. The original589 CI remains its historical execution result and cannot establish this behavior's correctness.

| FY / raw SHA | Wrong second report range | Actual next financial caption |
| --- | --- | --- |
| 2023 /57782a31cafe37915ffb44e2204a3a0ffa6c11674dac7c0e16baf77bbf8af7ac |980..2807 (Item9) |996, CONSOLIDATED STATEMENTS OF OPERATIONS |
| 2024 /f49ba30f8fa1f0502dcbd84793679e66b0ca29dd4e7dc7378e236f54a1ea5297 |1064..3132 (Item9) |1081, CONSOLIDATED STATEMENTS OF OPERATIONS |

FY2023 subsequent financial captions1029/1059/1114 and FY2024 captions1115/1142/1196 also have document.emphasizedFalse. FY2023 real legal blocks2613/2614/2619/2625/2626/2633/2634/2642/2643/2648, and FY2024 general legal blocks2942/2943 plus incorporated captions2947..2987/2987..2995, lie inside the wrongly wide range. First audit reports953..980 and1041..1064 end at the next report title. Original accessions are0000018926-24-000016 and0000018926-25-000010. These are the exact saved originals read,0.851879/0.959824s for the source-only inspection, not a new model or company run.

The D02 admission step now refuses a report ending at a form-item fallback. Its end must be the next identified auditor or financial-statement heading before the range can exclude a candidate. Lumen's real parsed sources now return D02_AUDITOR_REPORT_CLOSING_SCOPE_NOT_PROVEN, with all document/legal text retained (changed-function checks0.032481/0.035847s). This prevents false completeness but does not finish Lumen's source processing: the public owner has confirmed responsibility for inspecting the shared report locator; no competing parser is added here. It is an implementation gap despite saved originals being available. D04 itself scans its full language source, so this D02 exclusion failure is not used to revoke unrelated original D04 records or assert a complete D04 defect.

A separate unit counterexample also showed that a differently formatted final C heading could be ignored while B was incorrectly extended to the parent end. Every candidate lettered sibling must now have the same proved format, rather than silently dropping one. The terminal-style case and real fallback problem both fail before the correction. The stable fallback test explicitly supplies a constructed wrong-reader range modeled on Lumen, so it does not require the future public parser to keep failing on an unbold financial caption.

Five affected modules now pass81tests/0.678s/zero skips. Pfizer's captured actual company bundle is rechecked with only these changed functions: complete proposal/request remains identical, includingd9f0139e/1605blocks,0.231133s. No company/source/factory reparse or model execution is repeated; original first-run21.562/read.135 proof keeps its named working-version scope. New Source/Model/SEC calls0/0/0. The current returned head and receiver's combined-source recheck/CI must be verified independently; the first589 green is not moved to it.

## Actual production regression and unused-report correction

The full registered50 production comparison maina77→c215 (normal259P1/main reception plus public265) completed but exited1:14expected FAIL_TO_OK,16SAME_OK,3OK_TO_FAIL and17both-failed. The unexpected failures areSouthwestFY2022/2023/2024, eachD02_AUDITOR_REPORT_CLOSING_SCOPE_NOT_PROVEN. Original comparison/manifest/summary are retained in production-failure; they are not changed to success.

Exact saved originals show two auditor reports at the end of Item8. Their ranges are2313..2350/2350..2369 (FY2022),2355..2383/2383..2402 (FY2023),2466..2491/2491..2510 (FY2024). Last reports close atItem9 and no report contains an ITEM8 D02 keyword admission. The original guard unnecessarily refused unused report ranges. The source client now checks closing proof only for report ranges actually used to remove admissions; an unused report returns the original proposal with no new exclusion metadata or credit. Lumen's bad fallback with actual admissions still failsclosed. Shared report locator is not modified or replaced.

Changed functions on the three already parsed real Southwest documents preserve whole proposals and full request objects (.168101/.174322/.180410s). Pfizer's captured actual company request remains identical; unused proof metadata may be reduced to genuinely used reports, which is stated rather than claiming the old complete proposal bytes unchanged. The targeted receiver-tool production comparison maina77→93a2 isCOMPLETE/exit0/3SAME_OK/0changed/0fail,explicitSUBSET. The first unused fixture did not isolate the original guard, so its passing result is not described as a red reproduction; the actual three production regressions are the decisive before evidence. The updated constructed control supplies that exact unused range. Another bad-reader fixture initially had no candidate to remove after incorporation; it now includes a genuine unincorporated legal paragraph to enter the guard, preserving the false-deletion refusal assertion.

Actualmain17569516 contains received258/259/264. Normal merge preserves lettered/auditor additions and main's repaired caption logic; only those differing code/test sections conflict, no whole-file replacement.88affected controls/.765s/zero skips pass. Running tests before resolving merge markers failed at import; no financial/source work occurred. The updated main264 tool is stronger (per-sample -I -B processes, full locators/request fields and untracked/ignored code checks), so old-tool full/targeted records retain their original scope. The final actualmain175→dad production comparison is still running under this newer tool with the samea1975/4505root; predeclared expectation19SAME_OK/14FAIL_TO_OK/0CHANGED_OK/0OK_TO_FAIL/17unverified must be checked before reception. No current financial/model/company first execution is repeated,0new SEC/provider/model calls. Remaining shared/answer/business obligations are unchanged.

## Final current-main production comparison completed

The updated accepted264 tool main175→dad has now completed all50 registered cases:COMPLETE/exit0/no problems,29SAME_OK/4FAIL_TO_OK/0CHANGED_OK/0OK_TO_FAIL/17SAME_FAIL/0CHANGED_FAIL/0NOT_COMPARED. All comparisons use the exact samea1975/4505-file source root before/after; per-sample isolated-B workers and full source locators/request fields are verified by the current tool. The four additional preparations arePfizerFY2022/2023/2025 andLumenFY2024. All29existing preparations, including the threeSouthwestyears, keep compared content and complete requests. Original result/manifest/summary are infinal-production-comparison.

The predeclared19same/14new expectation retained the prior baseline's ten note-ownership improvements. Currentmain175already containsPR259, so those ten are correctlySAME_OK now:29same+4new is the same overall33prepared scope, not a coverage change. The seventeenfailures still need source/program/answer work and are not accepted metrics. These are preparation outcomes, not1950business completion.

This final comparison is distinct from the originalc215exit1 (preservedproduction-failure) andthree-case recovery (preservedSUBSET). Root265locator is a real remaining dependency until received; old259is nowmain. Actual packet/quote/semantic answers stay unchanged and are not promoted to the new requests. The originalPf actual-company first/read record keeps its own execution version; no repeated financial/source first case or new model/SEC call. Retarget reception to actualmain with fixed public265 dependency, verify the returned headCI and receiver's repeat separately.
