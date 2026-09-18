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
