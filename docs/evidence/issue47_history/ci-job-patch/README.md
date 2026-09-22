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

## The second one: the only red check on this PR is a cap, not a defect

`0002-raise-capacity-native-runs-cap.patch` raises `timeout-minutes` on the
`capacity-native-runs` job from 15 to 25 and on `capacity-program-native-runs`
from 20 to 30. It is here for the same reason: this session cannot push
`.github/workflows/`.

```
git apply docs/evidence/issue47_history/ci-job-patch/0002-raise-capacity-native-runs-cap.patch
```

Verified with `git apply --check` on its own and after `0001`, in both orders;
`0001` appends at the end of the file and `0002` touches line 93, so they do not
overlap. After both, the file still parses to 13 jobs and the only changed key
is that one cap.

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
