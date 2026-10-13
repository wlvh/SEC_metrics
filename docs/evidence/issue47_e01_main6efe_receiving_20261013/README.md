# Main6efe receiving: saved E01 is readable, unrelated code changes invalidate reuse

PR244 has been received at merge4a37; actual main6efe also contains PR238/240/242/243. The receiver's 50-position comparison is reused: 49 positions unchanged, one Pfizer FY2023 disposition changes to a saved withholding. The source relationship was reversed in its prose; [PR244 correction6143084668](https://github.com/wlvh/SEC_metrics/pull/244#issuecomment-6143084668) points to the submitted originals: header2.02 versus visible body2.01. The annual M&A count remains unproved.

PR244's 16 remote checks are all successful. Actual company-history job115168616499 executes both new methods individually as `... ok`; its E01 step is 74 tests/0.310s/zero skips. The local real company first/repeat/read results remain in PR244's one original record; neither the receiver survey nor those financial/source preparations were rerun here.

## Affected main combination check

Using the original newly created Pfizer FY2023 task and its registered source root, actual main6efe independently reads the saved withheld result/CSV in 0.297s; all 17 state files are unchanged. Source/factory and Calculator code objects and network access are forbidden. The old seven result files are not rewritten, and their original program version is not relabelled.

The same-input `run` under that guard takes0.673s and attempts to enter the factory. The guard raises `FACTORY_OR_CALCULATOR_FORBIDDEN_FOR_SAVED_INPUT_REUSE`, so the report is `INPUT_OR_EXECUTION_FAILED` rather than reuse. **This error is a constructed no-computation control, not a new financial-report conclusion.** It establishes that the controller tried to process again; it does not establish a new natural source/parser failure or paid call. All seven old result files remain byte-identical. The ordinary attempt journal grows17→19 files.

`configuration-delta.json` identifies precisely three changed base processing-file digests:

- `d02_text_results_v3.py`: PR240's D02 page-header helper, unused by this E01 consumer.
- `ordinary_current_update.py` and `ordinary_saved_result.py`: PR238's current B04/B07 dispatch/registration changes.

The actual historical E01 producer, its source input and original result are unchanged. The public dependency/controller owner has this counterexample; this branch contains evidence only and does not add a historical controller, writer, compatibility platform or renderer.

Public owner follow-up separates the observed three-file digest difference from the actual cause: the unused D02 dependency is confirmed by an isolated red/green control; ordinary_current_update already has a checking-version exclusion, so its changed digest is not itself a reprocessing trigger. The unused B04/B07 registration change in ordinary_saved_result remains a separate finite compatibility/responsibility check. This record does not claim all three files caused the failure or request that every writer change be ignored. The original failed control and configuration-delta bytes remain unchanged; corrected public code and actual old-task reuse still need consumer verification.

After the constructed failed attempt, another independent read takes0.046s with all19 state files unchanged. It honestly shows that latest controlled execution failure/NO_CURRENT_RESULT; the old files are still present. This second read is not falsely described as continuing to present the old withheld result as the current conclusion. `read-after-control.json` records its limited scope.

## Reproduce without new calls

First create the saved task using PR244's existing [parameterized verifier](../issue47_e01_item_conflict_state_20261013/verify_company.py) on its published db403009 code and the previously restored source inputs. Then use actual main6efe:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. python3 \
  docs/evidence/issue47_e01_main6efe_receiving_20261013/verify.py \
  --state-root /absolute/pr244-output/state \
  --output-root /absolute/new-main-receiving-output
```

The driver obtains `source_root` from the task, retains the constructed guard failure and old result bytes, and writes the normal controlled attempt to that review task. Use a review task, not a production task. `actual.json` retains the real paths/observed output; the parameterized command is the portable reproduction. No original Source, SEC ledger, model response, failure or Run is edited. New SEC/provider/model calls0/0/0.

The D02 numbered-subsection prerequisite is a separate scoped PR245, not folded into this evidence. Public D02 factory/CLI work and public reuse correction remain with #28; historical side supplies this actual consumer and receives the same correction. Goal remains the complete five-year target, not these two states.
