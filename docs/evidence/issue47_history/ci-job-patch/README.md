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
`capacity-native-runs` job from 15 to 25. It is here for the same reason: this
session cannot push `.github/workflows/`.

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
