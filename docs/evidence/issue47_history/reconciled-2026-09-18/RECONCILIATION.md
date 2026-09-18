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
| on one of the **22** metrics that have a historical route | 1,100 | 56% |
| on one of the other 17 declared metrics | **850** | **44%** |
| | **1,950** | |

These were 16 and 800 against 1,150 when this section was first written. The six
8-K event metrics moved 300 positions across the line, and the section below on
what the remaining families cost explains why that move was cheap: they were
held out by a constant and a comment, not by missing machinery. Real exact
values rose from 67 to 103 and verified outcomes from 146 to 182 in the same
regeneration, with no new request.

**No number of SEC requests reaches those 850.** They are blocked on a route
that does not exist yet, not on a document nobody has fetched. Within the 1,100
that acquisition can reach, 182 already carry a verified outcome; the rest are
missing the target filing's own original document or sit in a period saved
submissions metadata does not establish. (Those do not sum, because a position
can be missing more than one thing at once — which is why the matrix reports
independent dimensions rather than one status.)

So "how many GETs finish the backfill" is not answerable as asked. Acquisition
finishes a part of the 800. Finishing the frame also needs 23 more historical
routes, and each of those is implementation, not budget.

The matrix's `native_run_wired` dimension reads 0 for every position, which is
now out of date rather than wrong: it measures what this branch's coverage tool
knows about, and the tool predates the native Run chain. Native Runs are counted
in `../native-run-2026-09-18/native-run-matrix.json` instead.

### "17 routes to implement" is seven families, and one was neither

Saying the remaining positions need one route per metric prices them as if
they were alike. They are not. Grouped by the module family that implements each
metric today — which is what a historical successor has to be written against —
the original 23 fell into eight, and the largest of those eight is now wired:

| implementation family | metrics | positions |
| --- | --- | ---: |
| `financial_*` (bank measures) | A03, A04, A09, A11, A12, A13 | 300 |
| ~~`normal_zero_ai_results` / `deterministic_router` (event windows)~~ **WIRED** | C01, E01–E05 | ~~300~~ |
| `normal_text_input_v2` / `normal_text_projection_v2` | C02, D01, D02 | 150 |
| `governance_*` | C03, C04 | 100 |
| `capacity_*` | B13, D04 | 100 |
| `normal_lodging_results` / `lodging_table_source` | B10, B11 | 100 |
| `b06_*` / `normal_*_debt_results` | B06 | 50 |
| `r6_*` / `continuous_semantic_calls` | D03 | 50 |

Each family needs its own historical successor, in exactly the way
`historical_results`, `historical_zero_ai_results` and
`historical_accession_results` are three successors and not one. There is no
single change that moves more than 300 positions.

#### The event family looks closest to wired, and its stated blocker does not survive inspection

C01 and E01–E05 have Spec documents in `catalog/ordinary_zero_ai/` alongside the
wired sixteen, their applicability is `{"all": [], "none": []}` so no company is
excluded, and `historical_zero_ai_results` already exists as
`normal_zero_ai_results`'s successor. The only thing holding them out is
`SUPPORTED_METRICS = ("B01", "B03")`.

That module's own docstring — which this branch wrote — says event windows are
refused because each is "defined relative to the current period". On reading
`_event_sources`, that is not right. The window it discovers 8-K filings in is
`prepared["table_input"]["target_period"]`'s `period_start`..`period_end`, and
`historical_annual_input` pins exactly that field to the selected period. The
window follows the pinned year, not today.

What that leaves is a different and untested question: whether **completeness**
of 8-K discovery can be proven over a past window. The route builds a
`fy_8k_item_inventory` source set from the submissions index and its history
shards, and a stale or missing shard means the set cannot be shown to be
complete — which is precisely the JPMorgan defect the 12 snapshot-refresh
requests in the plan exist to fix.

#### Settled by running it: they are wired

That is what happened. C01 and E01–E05 now resolve EXACT and PUBLISHED on
Marriott's pinned 2025 window from 10 saved 8-K filings with zero calls, and the
component rebuilds to the same `component_id`. The pinned 2023 window fails with
`SAVED_SOURCE_MISSING` naming `d427456d8k.htm` — an acquisition gap of exactly
the shape every other historical route reports, not a completeness-proof
problem and not a definitional one.

`_event_sources`, `project_event_result`, `_compiled_event_spec` and
`calculate_observation_metric` are imported unchanged. The whole change was
`SUPPORTED_METRICS`, the branch that calls them, and deleting a wrong sentence.

The wired set is 22 metrics, the frame moves from 800 reachable positions to
1,100, exact values from 67 to 103 and verified outcomes from 146 to 182, all
without a request. Four earlier versions of this analysis reasoned from a
partial reading and were wrong; this one was settled by running it.

#### Two earlier versions of this section were wrong

The first said the 900 text positions sit behind one missing capability,
reasoning from `render_historical_run` refusing anything that is not
`STRUCTURED`. That refusal is real but it is the last gate, not the only one.
The second said four metrics were cheap extensions of the wired machinery and
that C03 and C04 had no implementation at all; both came from grepping only
`*results*.py`, and A13 belongs to the `financial_*` family while C03 and C04
are implemented in `governance_*`. The table above is built from every module
under `scripts/vnext/` that names each metric:

```
python3 - <<'EOF'
import json, re
from pathlib import Path
b = json.load(open("docs/evidence/issue47_history/reconciled-2026-09-18/coverage-matrix.json"))
wired = set(b["wired_historical_metric_ids"])
mods = {p.name: p.read_text(errors="replace") for p in Path("scripts/vnext").glob("*.py")}
for m in b["declared_metric_ids"]:
    if m in wired:
        continue
    owners = sorted(n for n, t in mods.items()
                    if re.search(r'["\']%s["\']' % m, t) and not n.startswith("historical_"))
    print(m, owners[:3])
EOF
```

### Which family to wire next is a material question, not a code question

The event family was worth wiring because the 8-K documents for the most recent
pinned year were already saved: Marriott's 2025 window had ten of them, and 36
positions became EXACT the moment the route existed. That is the test to apply
to the next family, and it is cheap to run before writing any code.

Governance (`C03`, `C04`, 100 positions, applicable to every company) fails it.
The saved submissions indexes list **82** `DEF 14A` filings; **10** have their
accession material saved, and every one of those ten was filed in 2026:

```
python3 - <<'EOF'
import json, glob, os
saved = {m.rsplit("_", 1)[-1] for m in os.listdir("evidence/accession_materials")}
listed = hit = 0
for path in glob.glob("evidence/submissions/CIK*.json"):
    recent = (json.load(open(path)).get("filings", {}) or {}).get("recent", {}) or {}
    for form, acc in zip(recent.get("form", []), recent.get("accessionNumber", [])):
        if form == "DEF 14A":
            listed += 1
            hit += acc.replace("-", "") in saved
print(listed, hit)
EOF
```

So a historical governance route would resolve the most recent period and report
a named source gap for every earlier one — roughly ten real positions out of a
hundred, against thirty-six for the same effort on events. The 72 unsaved
proxies are a concrete acquisition ask rather than a vague one, and they belong
in the plan before the route does.

This is recorded because the same check decides the remaining families, and it
costs nothing to run first.

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
