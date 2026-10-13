# PR251 receiving: damaged D02 input remains local to that metric in the existing Ford task

Consumed published [PR251](https://github.com/wlvh/SEC_metrics/pull/251) head52916c891b44b46e299ee7f2a77bf28de0ba5de7, which contains actualmaine16 and PR249's exact corrected note core. Public package/factory/controller code is unchanged by this consumer. The public fresh-task test is reused; this check exercises the historical side's existing Ford five-year statement/D01 task and all of its old results.

The original task starts with553 files/45 result versions. A new external controlled answer directory contains only a byte-identical copy of original call0009's semantic request, deliberately no terminal. It is explicitly a constructed damaged package, not a corrupted original reply or a new financial conclusion. Original SEC sources and the complete answer set remain read-only.

The same company CLI requests FY2025 D02+B04:

- First5.227s/exit2: D02 records `INPUT_OR_EXECUTION_FAILED`/CanonicalError and the precise missing terminal path, with no Result. B04 is processed normally and yields−8,162,000,000 USD/PASS/actual2025 full year, Result89f9cc9d…66e2e7. Only this selected financial coordinate is processed under the changed shared configuration; other years/metrics are not recalculated.
- Same scope0.716s/exit2: actual statement/source/finish/Calculator functions are forbidden. B04 is `NO_SOURCE_CONTENT_CHANGE`, same full ID, calculation/new-candidate flags false. The package error remains isolated to D02.
- Independent results/CSV0.501s/exit0: 26 rows retain the25 historical coordinates plus D02's explicit no-result state. B04's value and D02's blank value both appear; all569 state files are unchanged by reading.

All270 old result files remain byte-identical throughout; the normal B04 candidate/checks and D02 failure checks grow task553→569 files. `actual.json` retains execution paths/versions, full selected rows and original errors. The observed program marker is52916 with the normal dirty-worktree indicator; it is not asserted as a clean-tree run or an old-result re-signing. Earlier source/old-file evidence and the public damaged-package cases are not rerun as a full five-year batch.

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. python3 \
  docs/evidence/issue47_d02_package_existing_task_20261013/verify.py \
  --state-root /absolute/existing-ford-review-task \
  --original-call-root /absolute/separate-read-only-call0009 \
  --output-root /absolute/new-package-review-output
```

The verifier reads the registered source root from the task; only the requested FY2025 coordinate may normally process when its relevant configuration differs. Use a review task and a new output directory. The damaged input is created separately rather than removing anything from the original package. No private public-developer worktree is changed, and no Source/ledger/model response/old Run or failure is edited. New SEC/provider/model calls0/0/0. This proves partial-failure isolation and existing-task read/reuse, not full D02 semantic correctness, new model acceptance or1950 completion; receiver/main acceptance and remote CI remain separate.
