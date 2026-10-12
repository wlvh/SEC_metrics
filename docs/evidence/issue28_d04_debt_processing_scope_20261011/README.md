# Saved D04 does not reprocess after an unused debt-note change

Fixed starting main:9829c0217cb8b18060f69f4a5c9a47afe5c5c6cf, already received
PR167/172/170/173. Existing implementation and receiver validation are reused.
This scope is only unnecessary debt-note invalidation of saved D04, following
the actual historical consumer report in PR147/6914fa18 and PR171/98816222.
It does not claim historical parsed-input comparison is complete.

The first regression changes only the reported version of the debt-note helper
while using actual current configuration; D04 should stay the same and B06
must change. Separate necessary D04 review/source/annual dependency changes
must continue invalidating D04. No runtime source is edited, no source or
ledger request is made, and these program tests are not model/business results.

## Result and scope

The regression first failed: changing only the declared version of
`b06_note_carrying.py` changed D04 configuration. Necessary D04 review/source
changes passed their invalidation control. [before.log](before.log) retains
the original failure; it is not an unknown model failure.

The minimal fix extends the already received PR172's twenty debt-only file
exclusion to saved D04. The zero-AI/lodging handling remains in its original
condition; no D04 dependency is added through the zero-AI producer. B06 keeps
all its debt paths. Capacity source equivalence, D04 semantic review, annual
selection, source/record checks and caller-declared historical processing
dependencies stay effective. This does not exclude whole normal modules,
remove all hashes, add compatibility hash pairs or redefine D04.

[controls.log](controls.log) records57 update/recovery/current-D04/completeness/
history-state checks in0.642s, zero skips/failures/errors. Missing groups,
undecided findings, failed neighbours, different periods and real processing
changes remain protected. The new tests execute in the existing required
ordinary-current-update module; the only workflow change is a trigger for
the executable evidence directory, not new CI machinery.

## Actual user entrance

Code root:
`/Users/lyuhongwang/.codex/worktrees/issue28-d04-debt-processing-scope/SEC_metrics`.
Read-only original source:
`/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/source-inputs`.
Tests/runs used main9829c021 with the recorded uncommitted controller change;
publication SHA is recorded separately. Source and rules are not fabricated.

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp \
PYTHONPATH=/path/to/tokenizers-0.22.2:scripts:tools:. \
python3 docs/evidence/issue28_d04_debt_processing_scope_20261011/verify_company.py
```

The script uses formal `run --source-root --metric D04` to recheck the existing
complete MarriottFY2025 source and original real responses115–118, aggregate,
calculate and save. Ledger claim and sockets fail if invoked; no responses
are relabelled as new calls. First57.994s produces originalResult
`e523b7a9b36b787596d7de5100746a3c23b44ca336b4791d64c7df9ef7555371`,
`CANDIDATE_WITHHELD/null`, with the defined-scope-no-doubt public `TEXT_QUAL`
meaning unchanged. It is not a financial-health guarantee or new company
model result.

Only after that completed check, the isolated program's unused debt-note
helper gets an appended test comment. The same formal task runs again with
calculation factory and result writer forbidden. It returns
`PREVIOUS_INPUT_WITHHELD` in0.076s without preparing/replaying responses,
without a second result directory, and with the original six files/27,762B
unchanged. The debt file is restored in a finally block. A separate subprocess
`results` completes in0.424s, same full2025/source/CSV/state, no reprocessing.
All81 protected ledger/original-response/source files remain byte-identical.
The new ordinary check/CLI logs are allowed to grow.

[actual-company.json](actual-company.json) gives exact roots/commands/Result,
timing and protected hashes. First and repeat are the same scenario, not a
ratio formed from different machines or metrics. Source replay is genuine;
only forbidden external actions and the repeat factory are intercepted.

Cloud receivers without the private complete D04 material can run the57
controls and review the committed actual execution record; this limitation
must not be described as personally repeating the company chain. Use saved
materials only; do not request new responses or source GETs for this review.

The updated controller itself may cause one normal upgrade/reprocessing
check for old ordinary tasks. It does not rewrite old Results or suppress
actual input/configuration/source failures. Historical source selection and
its declared catalog dependency remain owned by the historical consumer.
The existing historical parsed-input optimization is not completed here.
No new model method, purpose, retry, SEC/provider/paid call, Ready, merge,
adoption, deployment, active change or full390 claim.
