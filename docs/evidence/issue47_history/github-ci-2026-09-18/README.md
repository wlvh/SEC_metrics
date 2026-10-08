# GitHub Actions facts for this branch, per commit

Observed 2026-09-18 through the GitHub API, not summarised from memory. The
local records in `baseline-ed8bf11/` are kept as they are: they describe this
development container, and they are not superseded by what a hosted runner did.

Nothing here says "CI is green". A conclusion belongs to a named commit, and two
of the commits below have a run that never finished.

## `vNext fast suite`, by commit

| commit | run | conclusion | note |
| --- | ---: | --- | --- |
| `da25fc5` | 125 | cancelled | |
| `2e4463e` | 126 | success | |
| `316417d` | 127 | cancelled | |
| `04a0d87` | 128 | success | |
| `768586f` | 129 | cancelled | 13 jobs: 12 success, 1 cancelled |
| `159f60a` | 130 | in progress at the time of writing | 3 of 14 checks complete |

`Metrics reference tables` is success on every one of these commits, including
`159f60a`.

## The one job that does not finish, and why it is not this branch's

`vNext capacity native Runs` runs `tests.vnext.test_capacity_run_material` and
`tests.vnext.test_capacity_numeric_run` under `timeout-minutes: 15`. Two
adjacent commits of this branch, same tests, same workflow:

| commit | step 5 duration | job outcome |
| --- | ---: | --- |
| `04a0d87` | 11m19s | success |
| `768586f` | 14m41s | cancelled at the 15-minute job cap |

The cancel is the job's own fixed cap expiring, not a newer push superseding the
run and not an assertion failing: the job reached 15m13s from its own start. The
work takes 11 to 15 minutes against a 15-minute cap, so which side of the cap it
lands on is decided by runner speed.

This branch touches nothing that job reads. `git diff --name-only ed8bf11..HEAD`
matches no file containing `capacity`, `b13` or `workflows`. It is the same
class of finding as the two local overruns already recorded in
`baseline-ed8bf11/`: a fixed time cap on a workload that has grown into it. The
cap is not this branch's to raise, and no test was changed to avoid it.

## What did finish, and what it covers

`vNext saved-source material` — the tier the three Issue #47 entries are
registered into — is **success** on both `04a0d87` (30m39s) and `768586f`
(30m48s), inside its own `timeout-minutes: 35`.

That is worth stating precisely, because it contradicts the local record rather
than confirming it: in this development container
`tests.vnext.test_normal_zero_ai_results` exceeds the runner's 240-second
per-case cap, and on the hosted runner the same tier passes. The local overrun
is real and is kept; it is a property of this container, not of the branch.

The historical-period material job described at the end of `TESTING.md` is still
not registered in `.github/workflows/vnext-fast.yml`. This session's GitHub App
has no `workflows` permission, so that change has to be applied by someone who
does; the job body is written out verbatim there for that purpose.
