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
