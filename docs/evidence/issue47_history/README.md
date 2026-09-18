# Issue #47 historical five-year evidence

Immutable development evidence for the Issue #47 historical backfill. Nothing
here is a publication, an adoption receipt or an acquisition authorization.

## baseline-ed8bf11/

`fast-suite-v2-jobs2.json` — `tools/run_fast_tests_v2.py --jobs 2` executed on
the unmodified development baseline `ed8bf11cbab76bc3d9b766d4b96d065a6cda10e6`
before any Issue #47 change, in the Issue #47 development container
(Python 3.11.15, `tokenizers==0.22.2` from `requirements-continuous-context.txt`).

Result: 122 selected entries, 121 return code 0, 1 entry at return code 124.
The single non-zero entry is
`tests.vnext.test_table_context_qualification_guard.TableContextQualificationGuardTest.test_missing_or_excess_usage_is_terminal_and_skips_ordinal_two`,
which is the runner's fixed 30-second per-case cap, not an assertion failure:
the same case run alone in the same container passes in 28.1 seconds. This is
an inherited environment boundary of the baseline, recorded as such. The count
122 is this report's snapshot, not a required future total.

## source-plan-2026-09-18/

`historical-source-plan.json` — output of `tools/vnext_history_plan.py --years 5`
against the repository's own saved SEC bytes. Regenerate with:

```
python3 tools/vnext_history_plan.py --years 5 \
  --output docs/evidence/issue47_history/source-plan-2026-09-18/historical-source-plan.json
```

The plan reads saved request bytes only. `calls` is `{"provider":0,"paid":0,"sec":0}`
for every company and `fetch_authorized` is `false`: producing it neither spends
nor grants any SEC or model business call.

What it establishes, per company, for the five most recent annual report ends:

* the target report end dates and their exact original 10-K accessions, taken
  from saved submissions metadata — never from a filing date or a calendar year;
* each target's prior-year dependency, kept as an input of that target rather
  than as a sixth output year;
* every declared document dependency, deduplicated by URL with all consumer
  relations retained, classified as `SUBMISSIONS_INDEX`, `SUBMISSIONS_HISTORY`,
  `COMPANYFACTS`, `ANNUAL_PERIOD_IDENTITY` or `ACCESSION_INSTANCE_DISCOVERY`;
* the saved state of each dependency, and where a target's own primary HTML is
  not saved, whether that accession's own authenticated XBRL instance already
  establishes the same annual period. That alternative closes the period
  identity dependency only; `substitutes_html_text_range` is `false`.

`fiscal_year` is deliberately `null` on every candidate. A report end date is
SEC metadata; the issuer fiscal-year label belongs to that filing's own DEI
contexts and is established when the document is read.

`complete_plan_proven` is `false` wherever accession index discovery has not
yet run for a target accession. Those accessions are listed in
`accession_indexes_not_yet_discovered`; the additional instance documents behind
them are reported as not yet known rather than estimated as a number.

## pilot-2026-09-18/

`historical-period-outcomes.json` — output of `tools/vnext_history_pilot.py` over the four pilot
companies' five most recent annual report ends. Regenerate with:

```
python3 tools/vnext_history_pilot.py --company marriott_international --company ford_motor_company \
  --company salesforce --company macys --years 5 \
  --output docs/evidence/issue47_history/pilot-2026-09-18/historical-period-outcomes.json
```

Every outcome is the real one: a value with its filing identity, a source limitation naming the
exact missing document, or an implementation gap. `calls` is `{"provider":0,"paid":0,"sec":0}`.

## coverage-2026-09-18/

`coverage-matrix.json` — output of `tools/vnext_history_coverage.py`. The frame is
companies × declared metrics × requested annual report ends, fixed before any position is
filled. The declared metric count is read from the installed policy and checked against that
policy's own `declared_issue_metric_count`, so D03 and the other pending metrics stay inside the
denominator instead of being removed from it. Regenerate with:

```
python3 tools/vnext_history_coverage.py --years 5 \
  --output docs/evidence/issue47_history/coverage-2026-09-18/coverage-matrix.json
```

Each position carries exactly one status under a fixed precedence, so a later limitation never
hides an earlier one: the period is not established from metadata; the period is established but
its own original document is not saved; the period is established but resolving it stopped, split
into a source limitation and a missing implementation by the failure's own category; or the
metric's own resolved outcome. No status here is a statement about what an issuer disclosed.

### baseline-ed8bf11/source-material-v2-jobs2.json

`tools/run_fast_tests_v2.py --suite source-material --jobs 2` on this branch, which is the tier
the three Issue #47 short entries were registered into. Result: 70 selected entries, 69 at return
code 0, one at return code 124.

The three Issue #47 entries all pass well inside the tier's 240-second per-case cap:
`test_normal_history_catalog` 19.0s, `test_historical_coverage` 28.7s,
`test_historical_period_results` 72.3s.

The single non-zero entry is `tests.vnext.test_normal_zero_ai_results`. It is an inherited
boundary, not a regression from this branch:

* the entry is pre-existing — it appears at line 47 of the base branch's own runner;
* this branch changes `tools/run_fast_tests_v2.py` only by appending its own three entries, and
  does not modify `scripts/vnext/normal_zero_ai_results.py` or that test at all;
* run alone in this container it passes, `Ran 10 tests in 263.053s`, which is 23 seconds past the
  tier's fixed 240-second cap. So this is the case genuinely exceeding the cap on this machine
  rather than losing a race for CPU.

Neither the test nor the cap was changed to make this green.

## reconciled-2026-09-18/

The plan and the matrix regenerated together on one commit, after the review
that rejected "only two decisions remain". `RECONCILIATION.md` in that directory
explains, per company, why the acquisition budget is 142 and not the 122 that
was quoted on Issue #47, and why 130 is a real number that was never the whole
budget. It also states the limited pilot this asks for — 22 requests over one
additional annual year for 8 companies — and says what that pilot is predicted
to establish, in a form that can be shown wrong.

`source-plan-2026-09-18/` and `coverage-2026-09-18/` above are kept unchanged.
They are the artifacts the wrong number was read from, and deleting them would
remove the evidence of how it was produced.

## github-ci-2026-09-18/

The hosted-runner conclusions for this branch, per commit, read from the GitHub
API rather than summarised. It records which run did not finish and the measured
reason, and it is deliberately separate from `baseline-ed8bf11/`: the local
records describe this development container and are not replaced by what a
hosted runner did. On one point the two disagree, and the disagreement is stated
rather than resolved in the branch's favour.
