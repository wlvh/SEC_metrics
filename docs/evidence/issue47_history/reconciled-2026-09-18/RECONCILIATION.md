# Why the acquisition budget is 142 and not 122

Both numbers were produced by the same tool against the same saved SEC bytes.
The difference is not drift and it is not new material: it is three corrections
to the plan itself, made after the first number was published. The first number
was quoted on Issue #47 as "122 GETs finish the five-year backfill". It was
wrong twice over — wrong in the count, and wrong in calling any count a finish
line.

Regenerate both artifacts in this directory from one commit:

```
python3 tools/vnext_history_plan.py --years 5 \
  --output docs/evidence/issue47_history/reconciled-2026-09-18/historical-source-plan.json
python3 tools/vnext_history_coverage.py --years 5 \
  --output docs/evidence/issue47_history/reconciled-2026-09-18/coverage-matrix.json
```

Neither spends a business call. `calls` is `{"provider":0,"paid":0,"sec":0}` and
`fetch_authorized` is `false` in both.

## The reconciliation, per company

| company | old | new | cause |
| --- | ---: | ---: | --- |
| marriott_international | 9 | 9 | unchanged |
| southwest_airlines | 8 | 9 | target-primary credit |
| ford_motor_company | 8 | 9 | target-primary credit |
| pfizer | 8 | 9 | target-primary credit |
| jpmorgan_chase | 57 | 70 | target-primary credit, + 11 stale shards, + 1 index |
| salesforce | 8 | 9 | target-primary credit |
| lumen_technologies | 8 | 9 | target-primary credit |
| macys | 8 | 9 | target-primary credit |
| paramount_skydance_paramount_global | 0 | 0 | unchanged |
| enphase_energy | 8 | 9 | target-primary credit |
| **total** | **122** | **142** | |

### +8, one per company: a credit that was keyed to the wrong thing

The second-most-recent year's primary HTML serves two roles at once. For Ford it
is `f-20241231.htm`: the prior-annual dependency of the 2025 target, and the
target primary of the 2024 target. Its `source_roles` in the plan say exactly
that, and always did.

A saved accession's own XBRL instance can stand in for the prior-annual role,
because that role supplies a date range and its adjacency. It cannot stand in
for a target primary, because a target establishes an issuer fiscal-year label
and `inspect_fiscal_year_labels` refuses an extracted instance with
`FISCAL_LABEL_FULL_DOCUMENT_REQUIRED`. That refusal is correct: Salesforce and
Macy's both end a year on 2026-01-31 and label it 2026 and 2025 respectively, so
no rule over dates can recover the label.

The old plan granted the credit whenever the instance satisfied the *dependency
class* `ANNUAL_PERIOD_IDENTITY`, which both roles share. So one document per
company was credited away and left the budget. The credit is now keyed to the
*source role*, and a document also needed as a target primary stays required.

This is the same defect that was retracted in prose on Issue #47 and pinned as
`test_an_accession_instance_cannot_establish_an_issuer_fiscal_label`. What was
not done at the time was re-deriving the number the defect had produced, which
is why a corrected claim and a stale budget were published together.

Marriott is absent from this list because its 2024 document is already saved;
Paramount has one reachable target and therefore no second year.

### +11 stale JPMorgan shards, and +1 index

A submissions shard whose saved body holds filings outside the range the saved
index declares for it is a stale snapshot. Its bytes are present and they
verify. The plan derived `new_acquisition_required` from saved status alone, so
all 11 of JPMorgan's conflicting shards read as material already held, while the
catalog they feed stayed incoherent and blocked every JPMorgan period.

Coherence belongs to the index and the shards together, so the index is
refreshed with them in one pass and the alignment re-checked afterwards.
Requirements now carry an `acquisition_kind`, and the three cases are stated
separately rather than collapsed into one boolean:

* `FIRST_ACQUISITION` — 130 documents, never saved;
* `REPLACEMENT_ACQUISITION` — 0 here, saved bytes that do not verify;
* `SNAPSHOT_REFRESH` — 12, saved bytes that verify but are stale.

**130 is therefore a real number that was never the whole budget.** It is the
first-acquisition subtotal (8 companies at 9 each, JPMorgan 58, Paramount 0).
Quoting it as the plan silently drops the twelve refreshes.

## 142 is a floor, not a total

`further_requests_pending_index_discovery` is `true` for 8 of the 10 companies.
Every one of those accession indexes can declare further instance documents that
the plan cannot enumerate until the index itself is read. The plan reports the
undiscovered accessions by name in `accession_indexes_not_yet_discovered`
instead of estimating what is behind them, and `complete_plan_proven` is `false`
wherever that is so.

## The acquisition this asks for now

Not 142, and not a five-year budget. A **22-request pilot** over the
second-most-recent annual year for 8 companies, drawn entirely from the plan
above, excluding JPMorgan and Paramount:

| company | target year | requests |
| --- | --- | ---: |
| marriott_international | 2024-12-31 | 1 |
| southwest_airlines | 2024-12-31 | 3 |
| ford_motor_company | 2024-12-31 | 3 |
| pfizer | 2024-12-31 | 3 |
| salesforce | 2025-01-31 | 3 |
| lumen_technologies | 2024-12-31 | 3 |
| macys | 2025-02-01 | 3 |
| enphase_energy | 2024-12-31 | 3 |
| **total** | | **22** |

JPMorgan is excluded because its second year is not blocked by one document: the
12-request snapshot refresh has to land first and be re-checked before anything
about JPMorgan's periods can be planned. Paramount has one reachable target.

What the pilot is predicted to establish, stated so it can be falsified: those 8
companies' second annual year becomes an established target, and its 16 wired
metrics each produce a real resolved outcome — a value, a structural
non-applicability, or a withheld result naming its own reason — instead of a
source gap. That is 128 positions. It leaves 184 positions in those same
company-years blocked by the 23 metrics that have no historical route at all,
which no acquisition can fix.

The 22 figure is itself a floor for the same reason 142 is: seven of the eight
batches include an accession index that has not been read, and reading it can
declare further documents for that year.

No acquisition is authorized by this document. It states what would be
requested, under which permission, if one is granted.
