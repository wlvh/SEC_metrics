# Historical E01: preserve a completed item conflict through company save/reuse/read

The existing Pfizer FY2023 rejection is `EVENT_ITEM_HEADED_BUT_NOT_LISTED:0001193125-23-294930:2.01`. The saved header lists 2.02/7.01/9.01, while the visible original heads 2.01/7.01/9.01. The historical reader already detects this conflict correctly. Previously its exception escaped the company factory, so this completed source check could not be saved as a stable withheld result. This change does not resolve the item disagreement or establish a complete annual M&A count.

Only `historical_e01_company_case` changes production behavior: it receives this one typed conflict after the existing complete event walk, preserves the original reason/category and both source records, and returns `E01_ITEM_METADATA_BODY_CONFLICT` with a null result and no model request. The source graph remains incomplete. Other missing-source, ambiguous-item and integrity failures retain their original exceptions. No item is relabelled, no old answer is used, and no partial count or zero is published.

The public controller, writer, reader and CSV path are unchanged. The historical consumer still uses their ordinary completed-check reuse. Its existing processing dependency already includes the changed module; a real processing/source change can cause reprocessing, while an unchanged input can reuse the completed withholding. This does not migrate or recalculate all other E01 years.

## Actual saved-source company result

`actual-company.json` retains the actual execution metadata: main `293e495f` with this consumer change uncommitted at execution, not a retrospectively relabelled committed run. `code-bytes.json` records the two implementation/test file hashes. No existing task or old result was changed.

- Fresh Pfizer FY2023 E01 through the normal fiscal-years company CLI: 12.206 seconds, exit 2, `CANDIDATE_WITHHELD`, null, actual 2023-01-01 to 2023-12-31 and CIK 78003. Result `cd0f882f…7553`; the full original conflict is saved in `input-assessments.json`.
- Same input: 0.690 seconds, exit 2, `PREVIOUS_INPUT_WITHHELD`. Actual factory, candidate/request builder, Calculator and withheld-result writer functions were forbidden by their function code objects. Zero processing and no second result; all seven result files remain byte-identical.
- Independent `results`/CSV: 0.298 seconds, exit 0. The null/withheld reason, fiscal year, actual dates, CIK and full Result ID are retained; all 17 state files remain unchanged. Source registry, request ledger and manifest hashes remain unchanged.

`conflicting-originals.json` contains the two original SourceReferences, raw-asset locations/SHA values, saved header item lines and visible body heading. These are the same previously acquired originals, not newly fetched sources. Their bytes were rechecked, with no new SEC/provider/model request.

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. python3 \
  tests/required_unittests.py \
  tests.vnext.test_historical_e01_company_case \
  tests.vnext.test_historical_e01_incorporated_input \
  tests.vnext.test_historical_ma_confirmation \
  tests.vnext.test_explicit_e01_company

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. python3 \
  docs/evidence/issue47_e01_item_conflict_state_20261013/verify_company.py \
  --source-root /absolute/restored/source-inputs \
  --output-root /absolute/new-review-output
```

Restore the committed SEC inputs using the existing [historical usage guide](../../historical_company_usage.md); sources are read-only and this driver requires a new output directory. The normal company commands and their actual arguments are retained in `actual-company.json`; the driver is a consumer verification command, not another pipeline or runner.

## Retained assertions and reception boundary

61 related short tests pass in 0.060 seconds, with zero skips. `before.log` retains the new regression's failure on the original consumer; `controls.log` retains the corrected result. The new tests distinguish this exact typed completed conflict from other parser/integrity errors. Existing missing sources, incorporated attachments, successor windows, mechanical response contracts and complete-walk zero controls remain. Constructed controls have no model/business acceptance credit.

The already existing company workflow triggers on the production module and this test file, and directly runs `tests.vnext.test_historical_e01_company_case` at its E01 step. No new selector platform, public runner or CI policy is introduced. Remote execution and receiver verification must be checked on the published head separately.

Remaining business work: reconcile this original source disagreement under the approved E01 rules and obtain the appropriate matching semantic response where required. Salesforce's missing original, Southwest's unmatched request, Paramount's incorporated-source response and the rest of the five-year target are unchanged. A readable withheld result is delivery of the completed failure state, not delivery of the annual count. New calls 0/0/0; no new Run, restored call opportunity, merge, Ready, formal adoption, deployment or active switch.
