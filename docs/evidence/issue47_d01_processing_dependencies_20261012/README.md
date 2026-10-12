# Historical D01 processing dependencies: receiving follow-up

This addresses [receiver feedback6127504212](https://github.com/wlvh/SEC_metrics/pull/200#issuecomment-6127504212)
and the historical part of [6127226798](https://github.com/wlvh/SEC_metrics/issues/28#issuecomment-6127226798).
Base is actual main `f29d1797565ea30fa04ab29972e58e9098937d81`, which already
contains PR198/200/201. The receiver's fifty-position D01 comparison is reused;
it was not repeated by this patch.

The historical D01 adapter declared its direct readers but omitted
`scope_contract.py`, `states.py` and `text_results_v2.py`, which the existing
source/review calculation actually uses. Those three paths now participate in
the existing ordinary controller's processing fingerprint. No shared module,
controller, renderer, source rule or test runner is rewritten. This is a
bounded declared-dependency correction; a repository-wide execution/dependency
check belongs to the public test owner and is not claimed here.

## Actual checks

- The small ordinary-state regression changes one of each of the three
  digests in memory. All three initially return stale
  `NO_SOURCE_CONTENT_CHANGE` (three failed subtests). With the declaration
  repaired, each invokes its controlled factory once, retains the old saved
  version, then reuses the new version with no additional factory call.
  Constructed state substitutes are explicitly labeled and are not financial
  conclusions.
- 54 required D01/source/period/controller controls passed in0.587s, zero
  skips/errors/failures. The changed state and historical test paths already
  trigger the existing company workflow and their complete modules execute.
- One existing actual Enphase FY2021 task was normally migrated at commit
  `a93b183f0be0225e4d4db09b594c1223031cd8ab`:17.631s. This is a necessary
  processing-configuration migration, not a new-source or first-ever result.
  It returns the same68 ordered source headings, exact text hash
  `8b66471154344b88f8a7e94a0184d90f284e65850c089f0abcbfe8f49909a483`
  and complete Result ID
  `sha256:e3dd15bbe689462ab075d5f24ac0d88f03b9037f9cb86f747e40e568ede99b0c`.
- Factory/candidate/two-calculator-forbidden repeat:0.745s, zero factory calls.
- Explicit memory-only change control:15.732s. A different digest for the
  now-declared scope module triggers the real factory; its first used scope
  function raises `CONSTRUCTED_CONTROL_D01_USED_SCOPE_FILE_CHANGED`. This
  injected failure is labeled as a control, not a genuine financial-source
  failure. Twelve existing immutable result files remain exact.
- With the control removed, ordinary same-input repeat:0.758s, zero factory
  calls; independent results/CSV:0.307s, all37 state files unchanged.
- Sixteen prior result/check files remain exact. Ledger, manifest and target
  registry hashes remain exact; new SEC/provider/paid/model calls=0.

The driver uses function-call observation, so its timings include that
instrumentation and are not a claim of runtime performance improvement.
Phase JSON, CSV, original-failure and after-control records are preserved.
`verify_company.py` uses only the ordinary CLI and explicit in-memory
patches; no repository file is fault-injected or manually restored.

Reproduction uses an already restored, read-only PR52 source-input root and
an existing D01 task that still has the earlier dependency declaration:
```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. python3 \
 docs/evidence/issue47_d01_processing_dependencies_20261012/verify_company.py \
 --source-root /saved/sec/source-inputs --state-root /external/existing-d01/state \
 --output-root /new/dependency-review
```
On an already migrated task the first phase will reuse; this driver deliberately
requires a migration/fresh calculation. Use the original saved task version
or a new task if repeating that phase is necessary, rather than forcing state.
Saved-source restoration and ordinary run/results arguments are in
[historical usage](../../historical_company_usage.md).

The same PR updates the usage guide as requested by receiver6127507449:
its available main version includes received D01 quarter-release support and
Marriott B02 FY2024/FY2025. PR199/202/203 remain separately identified pending
dependencies for other Marriott years. Multi-span headings, amendment/successor
support, source acquisition and full historical business acceptance remain
unfinished. No extra guide PR, fifty-year replay, model trial or publication.

## Received current entry combination

Main advanced to `2f756660f26438faf368ae760728e1442ecd1c41` (receiver received
PR135). This branch normally merged that main. The guide now records the
received current D01 route rather than leaving it as pending. The source
factory, heading semantics and three-path patch are unchanged; previous real
phase evidence is reused. Current/historical/controller affected short controls
passed143 in9.277s with zero skips/errors/failures (`main-combination.log`).
The actual main combination also repeats with all factories/calculators
forbidden and reads the existing68-title result in a separate process; these
outputs are retained, not represented as new
financial processing or the receiver's own fifty-position comparison.
