# D04 reuses a refreshed supporting Company Facts source when the full task is unchanged

Progress on #28. Base actually read/fetched main `681b35d865af9660ad03ffbbb20ec93cd499d9cd`. This corrects the saved-response current-company path, not a new model request or a reinterpretation of old answers. It does not widen B13 reuse.

## Failure and bounded correction

The [original JPMorgan diagnostic](https://github.com/wlvh/SEC_metrics/blob/2f42a6e768395020bc581ea6d696296bc28232ef/docs/evidence/issue28_jpm_d04_source_change_20261014/README.md) retained a59.930-second failed current-company attempt with27 required saved groups. Company Facts changed from `e5a94464` to `73de8c2d`; every consumed fiscal inspection field matched apart from the body hash and derived inspection identity. Source paragraph/native/continuation units and all nonmetadata fields matched. This was a program refusal, not a disclosure-absence finding or permission to purchase a replacement answer.

New small positive first fails `UPDATE_NATIVE_ANNUAL_SELECTION_CHANGED`. The correction binds both full inspections to each side's exact company/accession/period, selected primary hash, authenticated Company Facts descriptor/proof and content identity. Only then may acquisition filepath/attempt and those two hash-provenance fields be compared separately. **Every other annual/fiscal field, complete text/native unit, source-body identity outside the supporting CF refresh and complete substantive request set must match.** No global CF hash deletion, alternate amount selection, label override, metadata-row omission or Source rewrite. CF-body refresh is recorded separately from submissions refresh.

Changed fiscal rows/labels, inspector/proof/primary mismatches, foreign CIK, changed period/path, changed disclosure/source and arbitrary other metadata still refuse. Existing same-body provenance and B13's stricter comparison remain. Current selected source authentication and old response/claim verification still run.

The company path previously compared the identical complete Source again for every saved group. A second red test shows two comparisons for two identical groups. It now compares identical parsed packets once within this operation; differing content still enters the full comparison. All required request partition and response checks remain. This is a dictionary lookup in the existing operation, not a persistent/general cache.

## Executed verification

`controls.log`: **102 required tests, 1.826s, zero failures/errors/skips**, including new fiscal/source negatives, duplicate packet control and existing current-company/complete-response/update/recovery controls. Both modules already run in the real explicit CI step; no test registry omission or new platform.

`saved-packet-equivalence.json`: actual current and old JPMorgan saved packets reach full substantive-request equality with the unchanged reference tokenizer,40.740s. One initial system-Python invocation lacked the existing tokenizer dependency; no fake metering or installation was used to pass it. The existing cached Python3.12 environment/tokenizers0.22.2 supplies the dependency.

`company-summary.json` and the three phase receipts/log capture the actual formal CLI with current code and real saved125–151 request/response groups:

- **First processing286.683s** from fresh isolated state: complete D04 result `9f48035b...`, fiscal2025,2025-01-01 through2025-12-31, actual JPMorgan accession `0001628280-26-008131`. Status `CANDIDATE_WITHHELD`, reason `D04_DEFINED_SCOPE_NO_DOUBT_DISCLOSURE`.
- **Repeat0.075759s**, calculation factory replaced by an exception: `PREVIOUS_INPUT_WITHHELD`, same result/version, no calculation or new candidate/result directory.
- **Independent process `results`/CSV0.132081s**: same result, `TEXT_QUAL`, null quantity and original context/filing/notes. Saved state and result files remain byte-identical. Current source freshness is not asserted by the saved reader.

Network/DNS and CallLedger claims are forbidden in both run and independent reader. Original packet/source/answer/ledger hashes and tested production-code hashes remain unchanged. See receipt's actual protected-file count and result volume. The first shell-background launch's PID disappeared before any result/state file was written; that empty directory/log was retained. A separately detached process then completed. This is not an unknown remote execution or a paid retry.

Testing was against main681b plus recorded uncommitted delta; `tested-tree.json` and CLI `program_version` retain that fact. A later commit does not retroactively convert these into exact-SHA remote CI. No old business Result or response was rewritten.

## Entry and boundaries

```sh
PYTHONPATH=scripts:tools:. python3 tests/required_unittests.py tests.vnext.test_d04_provenance_reuse tests.vnext.test_current_d04_company tests.vnext.test_registered_native_update.RegisteredNativeUpdateTest tests.vnext.test_ordinary_task_input tests.vnext.test_ordinary_current_update
python3 tools/vnext_company.py run --company jpmorgan_chase --source-root /absolute/original/source-inputs --metric D04 --work-dir /absolute/new/state --output-dir /absolute/new/out
python3 tools/vnext_company.py results --company jpmorgan_chase --state-root /absolute/new/state --output-root /absolute/new/read
```

Use Python with the existing pinned tokenizers0.22.2 and the actual original #28 ledger/source registration; no business key or network is needed. The receipt identifies the tested private roots and fixed responses. The formal first/repeat/read are reproduced by the original development harness; this directory holds the exact resulting reports, not supplied answers.

This restores one existing company D04 current-record/export path. It does not add a new model/company, certify all model omissions, guarantee financial health, resolve Paramount's date conflict, prove390 coordinates, or adopt production. Original D04 ten real candidates retain their status. New SEC/provider/paid **0/0/0**, original cumulative143/143/52 unchanged. Receiver independently reviews this delta and company evidence; no author Ready/merge/adoption/deployment.
