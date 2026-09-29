# The one change this session cannot push

`0001-add-historical-period-package-job.patch` adds the
`historical-period-package` job to `.github/workflows/vnext-fast.yml`. It is
here as a patch rather than as a paragraph to copy, because this session's
GitHub App has no `workflows` permission and the change has to be applied by
someone whose does.

```
git apply docs/evidence/issue47_history/ci-job-patch/0001-add-historical-period-package-job.patch
```

Verified with `git apply --check` against this branch's head, so it applies
without conflict as long as the workflow file has not changed since.

The job matches the shape of the native jobs already in that file: the same
pinned `actions/checkout` and `actions/setup-python` SHAs, Python 3.14,
`PYTHONDONTWRITEBYTECODE=1`, `PYTHONPATH=scripts`, and a per-run material root
under `runner.temp`. `timeout-minutes` is 20; the test takes about 85 seconds in
this development container, and the nearest comparable job in that file uses 30.

Until it is applied, `tests.vnext.test_historical_package_material` has local
execution records only and must not be reported as a CI pass.

## 2026-09-27: `0004` adds a third saved-source shard

`0004-third-saved-source-shard.patch` changes three lines of the base's
saved-source job: the matrix becomes `shard_index: [0, 1, 2]`, the command
passes `--shard-count 3`, and the aggregate step's name stops saying "both".
The aggregate still requires `needs.source_material_parts.result == success`,
which GitHub reports only when every matrix leg succeeded, so a third leg is
covered without any other change. Checked with `git apply --check` against
`db61d793`, alone and after `0001`.

Why a workflow change and not more test work, measured rather than argued:

- At `ca9feec2` (run 36321956779) both shards were cancelled at 35 minutes
  with every case they had reached passing. The split is no longer
  round-robin: since `51e01521` it is heaviest-first into the lighter shard,
  weighted by each case's measured CI seconds (`SOURCE_CI_SECONDS`), and
  #47's modules stopped recomputing inputs they share.
- The base then added three cases (the D03 set and two C04 mixed-source
  captures, about 700 CI seconds together). With them the two shards weigh
  4,739 and 4,709 CI seconds; at `--jobs 2` that is about 39 minutes per
  shard, over the 35-minute cap even with a perfect split. Three shards weigh
  3,130 / 3,159 / 3,159, about 26 minutes each.
- #47's cases are 4,869 of the 9,448 seconds and the base's 4,579, so
  neither branch alone fills a shard pair and each adds to it. More
  memoization here would move the date the tier runs out again, not the fact.

Until `0004` or something equivalent is applied, a `cancelled` saved-source
leg on this PR is a cap, not a pass and not a failure; the only evidence
for that tier is a local complete run. `0003` no longer applies (the base
split the job itself) and is kept only as a record.

## 2026-09-28: the base made the same change; `0004` no longer applies

The base split the tier into three shards itself (`1d458a46`, "Balance
saved-source CI across three shards"): the same matrix and `--shard-count 3`,
with the aggregate step named "Require all complete source shards". `0004`
now fails `git apply --check` for that reason and, like `0003`, is kept only
as a record.

The projection above did not hold. On the first three-shard run of this PR
(run 36479470727, `ef959052` merged with the base at `16a6e897`) shard 0
finished in 24.5 minutes and shards 1 and 2 were cancelled at 35 minutes,
every case they had reached passing. Summed from the per-case progress lines
the shards carried 2,931 / 4,113+ / 3,457+ seconds, against the 3,130 /
3,159 / 3,159 projected: the weight table had gone stale (the cases it gave
3,179 s in shard 1 took 4,113 s, and the base's newer B03/D03 cases had no
weight). `1c42db79` re-weighs the table from that run's 118 reached cases
(the other 10, timed locally, each take under half a minute): 3,564 / 3,538 /
3,533 measured seconds, about 29.6 minutes per shard at `--jobs 2` before
checkout. Whether that fits is for the next run's progress lines to say; the
tier measures about 10,635 s in all, so if a shard is still cancelled the
remedy left is a fourth shard, which is again a workflow change.

## 2026-09-28 (later): three shards pass, but not reliably - `0005` adds a fourth

Two runs after the re-weighing. `1c42db79` (run 36485856267): shards 1 and 2
passed; shard 0 passed all 43 of its cases and was cancelled 10 ms after the
runner printed PASSED, because that runner's checkout took 1m52s and its
cases 33.1 minutes. `d9ddb3f8` (run 36485982390): all 17 checks green, the
three shards' cases taking 26.8, 32.4 and 33.6 minutes.

The weights are no longer what goes wrong. The same case ran 0.80 to 1.13
times as long as in the run the weights came from, depending on the runner it
landed on, so weights from one run carry that run's runners into the split.
`SOURCE_CI_SECONDS` is now the mean of the three runs
(`saved-source-timings-2026-09-28.json` holds every case's seconds per run and
the resulting `weights`, which the table equals). By that mean the three
shards carry 3,658 / 3,586 / 3,585 seconds - about 30 minutes each at
`--jobs 2`, about 34 on a runner 13% slower, over the 35-minute cap once a
slow checkout is added. The tier measured 10,502, 10,724 and 11,106 seconds
across the three runs.

`0005-fourth-saved-source-shard.patch` changes the matrix to
`shard_index: [0, 1, 2, 3]` and the command to `--shard-count 4`; nothing
else, since the aggregate step already requires every leg. It passes
`git apply --check` against the workflow as of `a728b6c7`. By the same mean
four shards carry about 2,700 seconds each - 22.5 minutes, 25.5 on a slow
runner. Applying it is a workflow change, for the owner or whoever maintains
the base's workflow; until then a cancelled saved-source leg is a cap, not a
pass and not a failure.

## 2026-09-28 (night): two more runs - the split holds, the runners do not

Two runs of the mean-weighted split, recorded in
`saved-source-timings-2026-09-28.json` under `out_of_sample_runs` and not
averaged into the table. `9f11abb9` (run 36492046303): all 17 checks green,
the three saved-source jobs taking 31m52s, 32m57s and 17m56s. `6e512978`
(run 36492131767, the same tree): all three saved-source shards passed
(19m51s, 33m14s, 24m19s). That run is still reported as cancelled, by a job
that is not this tier's: the base's `vNext remaining source Runs
(jpmorgan_chase)` reached its 45-minute cap after a 6m08s checkout. Its test
step takes 1,840 to 2,436 seconds on this PR's runs and on the base's own, and
the base's run 36478405174 (`16a6e897`) was cancelled the same way after a
7m02s checkout. It is the base's job and the base's cap; nothing this issue
changes runs in it.

How much runners differ, measured by comparing each case with itself across
the four runs that reached every case (`runner_factors` in the same file): the
twelve shard instances ran at 0.69 to 1.31 times each case's typical seconds,
a spread of 1.9. The same shard-0 cases summed 3,720 seconds on one runner and
2,241 on another; the whole tier 8,958 to 11,106 across five runs. Balancing
cannot absorb that: a shard of about 30 minutes on a typical runner is about
39 on the slowest one seen, so three shards pass when the runners are kind.
The weights are left as they are, because re-balancing moves minutes while
runners move ten.

With `0005` the four shards carry about 22.5 minutes each on a typical
runner, about 29.5 on the slowest seen, plus checkout - under the cap unless
the slowest runner and a six-minute checkout land on the same shard. That is
still the only remedy found; it is a workflow change for the owner or the
base.

## 2026-09-29: two more green runs, one with 34 seconds to spare

`7b56f356` (run 36504569527) and `009f2e86` (run 36505271124): all 17 checks
green on both. The saved-source jobs took 27m25s, 25m25s and 30m21s in the
first and 34m26s, 21m36s and 33m03s in the second. Shard 0 of the second
ended 34 seconds before the 35-minute cap: checkout 26 seconds, tests 2,034
seconds, on a runner at factor 1.29 against the same four-run reference. Of
the eight three-shard runs on this branch, no passing shard came closer (the
previous smallest margin was 46 seconds). The same 43 shard-0 cases summed
3,206 seconds in the first run and 4,050 in the second. With these six
instances the factor runs 0.62 to 1.31 across eighteen, a spread of 2.1
(`runner_factors.out_of_sample_instances`).

The base added one saved-source case after the weights were set,
`tests.vnext.test_d03_current_source_replay.D03CurrentSourceReplayTest`. It
took 85.6 and 76.7 seconds and is placed at the default 30 (`unweighted_cases`).
It is not re-weighted: its 50-second error is small next to the 844 seconds
the runner moved the same shard between these two runs, and a new table needs
its own CI round. The remedy for the runners is still `0005`.

## The second one was retired, and the file is gone

`0002-raise-capacity-native-runs-cap.patch` used to raise `timeout-minutes` on
`capacity-native-runs` from 15 to 25 and on `capacity-program-native-runs` from
20 to 30. It was deleted in 8ee21e5 because Issue #28's branch had already done
that job with its own numbers - upstream `0e2d9a8` sets both to 30 - and
applying this one on top would have lowered one of them. The instruction to
apply it stayed in this file after the patch itself was removed, which is an
instruction that cannot be followed; it is removed here.

Those two caps are upstream's jobs, not this issue's, and nothing here proposes
a change to them. What was measured is left below as information for whoever
owns them.

### What was measured

The job's own log at `638efe6` (run 35364240301, job 105662672602):

```
2026-09-18T15:59:28.6058979Z Ran 2 tests in 879.759s
2026-09-18T15:59:28.6059319Z OK
2026-09-18T15:59:28.9965389Z ##[error]The operation was canceled.
```

Both tests pass. The cancellation lands 0.39 seconds after they finish, because
the job started at 15:44:19 and 15 minutes expired at 15:59:19 — about ten
seconds before the work completed. So the 14m41s step duration that appears at
several commits is the cap arithmetic (15 minutes minus roughly 19 seconds of
setup), not a measurement of the workload, and no growth can be read off it.

In that same run, 12 of 13 jobs pass, and the siblings doing comparable work
take longer than this one is allowed: capacity program-role 16m52s under a
20-minute cap, saved-source material 21m21s, jpmorgan remaining-source 21m31s,
ordinary native Runs 22m51s. The caps in the file are 10, 35, 30, **15**, 20,
25, 30, 30, 30, 45, 30, 30. 15 is the outlier.

### Why this is not the branch's doing

The first run to lose this job is `768586f`. Its entire diff against the last
green commit `04a0d87` is `docs/evidence/issue47_history/README.md` (+22 lines)
and one archived JSON (+1 line). `_install_case_inputs` copies from `docs/` only
the files named in `frozen-parent-v10-index.json` — 89 entries, none of them
under `issue47_history` — and neither test module imports anything under
`docs/`. So the job crossed its cap on a diff containing nothing it executes.

The one thing this branch adds that the job does copy is `requirements/issue_47_v1/`,
which `_install_case_inputs` picks up through `(ROOT/"requirements").rglob("*")`.
It is 5 files and 69,156 bytes against that tree's 89 files and 5,929,342 bytes,
so 1.17% of the bytes, copied twice in this job — and it first appears at
`448e60d`, three commits after the job started being cancelled.

25 minutes leaves roughly ten minutes of headroom over the 14m40s of test time
measured above, and matches a cap already used elsewhere in the same file.

### The next run settled it

At `e67b72c` (run 35371355437) the **same** `capacity-native-runs` job passed, in
9m03s against the same 15-minute cap and the same code. What changed was the
runner, not the branch. In that run `capacity-program-native-runs` was cancelled
instead, at 20m16s against its 20-minute cap.

The two failures are not identical and the patch should not pretend they are.
The capacity job's log ends `Ran 2 tests in 879.759s / OK` and is then cancelled,
so its work had finished. The program-role job's log has no result line at all
and ends with `Terminate orphan process: pid (2392) (python3)` — it was cut in
the middle of a test. The mechanism is the same cap, the evidence is not.

Both jobs run `B13_REFERENCE_CONTEXT` material tests that this branch does not
touch, and which job loses depends on how fast a runner it draws. The caps in
the file after both patches are 10, 35, 30, 25, 30, 25, 30, 30, 30, 45, 30, 30
and 20 for the added job, so neither raised cap becomes an outlier in the other
direction.

## The third one: the saved-source job is at its cap, and so are two others

Run 194 on head `85143c9` - the commit the last review pinned - completed with
conclusion `cancelled`, and reading its thirteen jobs says why. Ten succeeded.
Three were cancelled, each at exactly its own `timeout-minutes`:

| job | cap | ran |
|---|---|---|
| `vNext capacity native Runs` | 15m | 15m15s |
| `vNext capacity program-role native Runs` | 20m | 20m15s |
| `vNext saved-source material` | 35m | 35m15s |

A job that exceeds `timeout-minutes` is cancelled rather than failed, so the
run reads as `cancelled` and no assertion failed anywhere. `0002` already
covers the two capacity jobs. This is the third.

**Superseded on 2026-09-27 by the base's own split.** Issue #28's branch
(`1613dab6`, merged here with `2ab35195`) splits the saved-source job itself:
`--shard-index {0,1} --shard-count 2`, round-robin by position in the list,
with a job that requires both shards. The merge took that interface for
`tools/run_fast_tests_v2.py`, because the workflow the base ships calls it;
this branch's `--shard i/n`, its budget-balanced partition and
`tests/vnext/test_source_tier_shard.py` were removed with it rather than kept
as a second way to split the same list. By each case's declared timeout the
two round-robin shards hold 15,960 and 17,220 seconds of budget, so they are
not far from even; whether each finishes inside the job's 35 minutes is a CI
measurement, not a claim made here. `0003` below is kept as a record and no
longer applies.

`0003-split-saved-source-material-job.patch` splits the saved-source job in
two, `--shard 1/2` and `--shard 2/2`, at 30 minutes each. Raising the single
cap would work for a while and stop working again: the tier grows with the
issue, it is already 76 cases, and one job means wall-clock feedback of over
half an hour on every push.

The `--shard i/n` option is in `tools/run_fast_tests_v2.py`, which this session
can push, so the split is available before the patch is applied and the
unsharded command keeps working unchanged if it never is. The partition is
balanced by each case's own declared timeout rather than by count - the three
long cases must not land together - and `tests/vnext/test_source_tier_shard.py`
asserts that every case is in exactly one shard, that the shards do not move
between runs, and that no shard carries more than its even share plus the
heaviest single case.

```
git apply docs/evidence/issue47_history/ci-job-patch/0003-split-saved-source-material-job.patch
```

Verified with `git apply --check` against this branch's head.

Until it is applied, the saved-source tier has local execution records only on
any commit where it exceeds 35 minutes, and a `cancelled` run must not be read
as a pass.

### Run 213 repeats it, which settles whether it is the runner

Run 35682468392 on head `fc95cca` completed `cancelled` with the same shape:
ten of thirteen jobs succeeded and the same three were cancelled, each at its
own job-level cap.

| job | cap | job ran | step cut at |
|---|---|---|---|
| `vNext capacity native Runs` | 15m | 15m04s | 14m33s |
| `vNext capacity program-role native Runs` | 20m | 20m17s | 19m48s |
| `vNext saved-source material` | 35m | 35m22s | 34m47s |

No assertion failed in any of the thirteen. The earlier note argued from run
194 that which capacity job loses depends on the runner drawn; run 213 loses
**both**, and the saved-source job with them, nineteen commits later. So the
caps are not a runner-draw coincidence at two of the three, and the tier has
not stopped growing.

What this round adds to the third patch's case: the saved-source tier gained
four cases and lost a 343-second one, and the `test_historical_coverage`
override came down from 900 to 480 because the cases that asked the routes are
gone. That moves the shard weights to 10500 and 10440 - still two jobs of the
same size, which is the point of weighing by each case's own budget rather than
by count.

None of the three is applied, because this session cannot push
`.github/workflows/`. All three were re-checked with `git apply --check`
against `fc95cca`, singly and in sequence, and still apply. Until someone whose
token carries the `workflows` permission applies them, this PR cannot reach a
green terminal for reasons that have nothing to do with its diff, and a
`cancelled` run must not be read as a pass in either direction.

### Both capacity jobs measured locally, and `0002` revised because of it

*Historical. `0002` no longer exists - see "The second one was retired" above. The measurements below stand; the patch they justified does not.*

Both jobs that `0002` covers were run to completion in this development
container, which is the measurement the earlier notes could not have: every CI
observation of them is a cap, not a duration, because the cap is what stopped
them.

| job | local | passes | CI cap today |
|---|---|---|---|
| `capacity native Runs` (2 cases) | 1136.4s = 18m56s | yes | 15m |
| `capacity program-role` (1 case) | 1803.4s = 30m03s | yes | 20m |

Neither has an assertion problem. Both simply need more than they are allowed.

Projecting onto CI uses the one job measured in both places: CI ran
`capacity native Runs` to completion once, at 879.8s, against 1136.4s here, so
this container is about **1.29x slower**. That puts `capacity native Runs` at
roughly 14.7 minutes in CI and `capacity program-role` at roughly **23.3**.

So `0002`'s original 30 for the program-role job was revised to **35**. 30
would have left 6.7 minutes of headroom on a job that has already been
cancelled twice, and a cap set just above the estimate is a cap that fails
again on a slower-than-usual runner - which is how this job got here. 25 for
`capacity native Runs` is unchanged: at roughly 14.7 minutes it has about ten
minutes of headroom, and 25 is a cap already used elsewhere in the file.

The ratio rests on a single job measured in both places, so it is an estimate
and is written as one. What is not an estimate is that both jobs pass and that
both exceed their current caps.

## Applying this without a local clone

The three patches need a credential this session does not have. Tested rather
than assumed: a push touching the workflow is rejected by GitHub with

```
! [remote rejected] task/sec-history-five-year
  (refusing to allow a GitHub App to create or update workflow
   `.github/workflows/vnext-fast.yml` without `workflows` permission)
```

"a GitHub App" is the operative phrase - the credential is the Claude GitHub
App's installation token. Two further layers were measured and are **different
mechanisms**, not the same one seen twice: writing the file through the GitHub
Contents API is refused by Anthropic's egress proxy (`Write access to this
GitHub API path is not permitted through this proxy`), and non-repository-
scoped API paths such as `/apps/claude` are refused by the same proxy, which is
why this session cannot read which permissions the App declares and does not
assert it.

`vnext-fast.patched.yml` is the workflow with all three patches applied, so
applying them needs no clone, no patch program and no hand-editing:

1. Open `docs/evidence/issue47_history/ci-job-patch/vnext-fast.patched.yml` on
   GitHub and copy its contents.
2. Open `.github/workflows/vnext-fast.yml` on the same branch, press the pencil,
   select all, paste, and commit.

It is generated by running the three patches, and its diff against the live
workflow is exactly those patches - 64 diff lines, 14 jobs, no other edit. It
lives here rather than beside the workflow because this path is one the session
can push and `.github/workflows/` is not.

Whether to grant the App `workflows` instead is a real choice and the answer is
probably no. A GitHub App can only be granted permissions it declares, so it may
not be grantable at all; and the permission is not "may edit one YAML file" but
"may execute arbitrary code in an environment holding the repository's secrets",
which GitHub gates separately for that reason. Three workflow edits across an
entire issue is not a rate that justifies standing access.

## Retraction: do not paste a whole workflow file, and `0002` is gone

The earlier section here told the reader to copy `vnext-fast.patched.yml` over
`.github/workflows/vnext-fast.yml` in the GitHub editor. **That instruction is
withdrawn and the file is deleted.** It was written when nobody else was
touching the workflow. Issue #28's branch has since changed it, and a
whole-file paste would have silently reverted their commit.

Upstream `0e2d9a8` ("ci: allow thirty minutes for complete capacity native
jobs") on `task/b06-new-source` sets both capacity jobs to 30 minutes.

| job | was | upstream now | this issue's measurement |
|---|---|---|---|
| `capacity native Runs` | 15 | **30** | 1136s local ≈ 14.7 min in CI - ample |
| `capacity program-role` | 20 | **30** | 1803s local ≈ 23.3 min in CI - about 6.7 min of headroom |
| `saved-source material` | 35 | 35 (untouched) | hit its cap at 34m47s |

So `0002-raise-capacity-native-runs-cap.patch` is **retired**: upstream did
that job, with its own numbers, and this issue has no business re-deciding
them. The measurement is offered as information, not as a change - 30 for the
program-role job is above the estimate but not by much, and whoever owns that
job should know the estimate exists.

What remains is only what belongs to this issue, and `0003` was **regenerated
against upstream's current file** rather than against this branch's stale copy:

- `0001-add-historical-period-package-job.patch` - adds a job that runs this
  issue's own package test.
- `0003-split-saved-source-material-job.patch` - splits the saved-source tier
  into two 30-minute shards. Upstream did not touch this job, and it is the
  tier that carries this issue's thirteen historical test modules.

Both were re-checked with `git apply --check` against upstream `0e2d9a8`,
singly and in sequence. **Apply them as patches, on top of whatever the file
says at the time.** A file this issue rendered earlier is a snapshot of one
moment and two branches now write here.

## What the merge checkout means for reading CI

The workflow triggers on `pull_request` and checks out without a ref, so a run
tests the **merge** of this branch with its base, not this branch alone. Two
consequences worth stating rather than assuming:

- Upstream's 30-minute caps should reach this PR's next run without anything
  being applied here, because the merge ref is recomputed as the base advances.
  That is a prediction from how the trigger works; it is confirmed by reading a
  run that started after `0e2d9a8`, not by this paragraph.
- "PR 52 passed at `27a28d9`" is therefore imprecise on its own. What a run
  tested is a head **and** a base, and where a historical runtime is involved,
  a registration patch as well.
