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

## The acquisition budget is an argument about the smaller half

142 versus 122 is a real correction, but both numbers answer a question that
covers 41% of the frame. Counted from the same artifact:

```
python3 - <<'EOF'
import json
b = json.load(open("docs/evidence/issue47_history/reconciled-2026-09-18/coverage-matrix.json"))
wired = set(b["wired_historical_metric_ids"])
on_wired = [p for p in b["positions"] if p["metric_id"] in wired]
print(len(on_wired), len(b["positions"]) - len(on_wired))
EOF
```

| | positions | share |
| --- | ---: | ---: |
| on one of the 16 metrics that have a historical route | 800 | 41% |
| on one of the other 23 declared metrics | **1,150** | **59%** |
| | **1,950** | |

**No number of SEC requests reaches those 1,150.** They are blocked on a route
that does not exist yet, not on a document nobody has fetched. Within the 800
that acquisition can reach: 146 already carry a verified outcome, 624 are
missing the target filing's own original document, and 144 sit in a period that
saved submissions metadata does not yet establish. (Those do not sum to 800
because a position can be missing more than one thing at once — which is the
reason the matrix reports independent dimensions instead of one status.)

So "how many GETs finish the backfill" is not answerable as asked. Acquisition
finishes a part of the 800. Finishing the frame also needs 23 more historical
routes, and each of those is implementation, not budget.

The matrix's `native_run_wired` dimension reads 0 for every position, which is
now out of date rather than wrong: it measures what this branch's coverage tool
knows about, and the tool predates the native Run chain. Native Runs are counted
in `../native-run-2026-09-18/native-run-matrix.json` instead.

### And "23 routes to implement" is three different costs

Saying the remaining 1,150 need 23 routes is true and not useful, because those
23 do not cost the same thing. Split by the route class the ordinary
presentation policy already assigns each metric:

| what the 23 are | metrics | positions | what it would take |
| --- | ---: | ---: | --- |
| structured family — `XBRL`, `DIM_XBRL`, `STD_XBRL`, `DERIVED` | 4 | 200 | extends the machinery the wired 16 already use |
| text — `MDA`, `10-K`, `8K_ITEM`, `PROXY` | 18 | 900 | one capability that does not exist at all |
| not in the presentation policy | 1 (`D03`) | 50 | no current route either, so not a historical gap |

The 4 are `A13`, `B06`, `C03`, `C04`; the 18 are `A03 A04 A09 A11 A12 B10 B11
B13 C01 C02 D01 D02 D04 E01 E02 E03 E04 E05`.

#### Correction: the 18 are not one capability

The first version of this section said the 900 sit behind **one** missing
thing, on the strength of `render_historical_run` refusing anything that is not
`STRUCTURED`. That refusal is real, but it is the last gate, not the only one,
and the claim was wrong about what is behind it. The 18 are served by five
different module families, each of which would need its own historical
successor exactly as `historical_results`, `historical_zero_ai_results` and
`historical_accession_results` are three successors and not one:

| module family | metrics | positions |
| --- | --- | ---: |
| `ordinary_text_input` + `text_results_v2` | C02, D02 | 100 |
| `financial_results` | A03, A04, A09, A11, A12 | 250 |
| `normal_zero_ai_results` (event windows) | C01, E01–E05 | 300 |
| `capacity_text_results` + `capacity_*_input` | B13, D04 | 100 |
| `normal_lodging_results` | B10, B11 | 100 |
| `normal_text_projection_v2` and others | D01 | 50 |

`ordinary_text_input.prepare_current_business_text_input` also refuses every
metric except C02 and D02 outright, so even that family is narrower than its
name.

The event-window group is worse than an implementation gap, and this is the
part worth carrying into any plan. `historical_zero_ai_results` already exists
as `normal_zero_ai_results`'s successor, and it refuses event windows on
purpose, in its own words: each is defined relative to the current period, and
answering one from today's latest filing would be a wrong answer. So C01 and
E01–E05 raise a question about what a historical event window *means* before
they raise one about how to compute it. Wiring them is not the work; deciding
what they claim is.

Priced honestly: 200 positions extend existing machinery, 400 need three new
successors of a familiar shape, 300 need a semantic decision first, and 50
(`D01`) plus 50 (`D03`) are their own cases.

```
python3 - <<'EOF'
import json
b = json.load(open("docs/evidence/issue47_history/reconciled-2026-09-18/coverage-matrix.json"))
p = json.load(open("config/ordinary_public_projection_v1.json"))["metrics"]
wired = set(b["wired_historical_metric_ids"])
STRUCTURED = {"DIM_XBRL", "STD_XBRL", "XBRL", "DERIVED"}
for m in sorted(set(b["declared_metric_ids"]) - wired):
    print(m, p.get(m, {}).get("projection", {}).get("source_class", "<absent>"))
EOF
```

## What EXACT means in the coverage matrix, and what it does not

The matrix stops at the metric result. It never renders a public row, so an
`EXACT` position is a **resolved** value, not a publishable one. That gap is not
theoretical: B01 and B03 were counted `EXACT` here while the historical renderer
still refused to build a row from the very same Runs, because it had only one of
the two evidence arms the ordinary renderer has. Reading the matrix alone, there
was nothing to see — the counts were correct about what they measured.

The refusal was found by building the native Run matrix, not by reading either
artifact. The matrix now carries `public_row_rendering_not_measured: true` so
the limitation travels with the numbers, and rows are counted separately in
`../native-run-2026-09-18/native-run-matrix.json`.

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
