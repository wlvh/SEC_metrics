# A native historical Run, end to end

The thing this Issue had been describing instead of building. One pinned annual
period goes from a proven period selection to a frozen native Run and a public
row, through the repository's own Run store, Calculator and presentation
policy. `end-to-end.json` is the run's own output, not a summary of it.

Marriott FY2024, metric B04, entirely from saved SEC bytes. No SEC or model
request, `calls` zero at every step.

| step | result |
| --- | --- |
| 1 period selection | `sha256:9d092cd0…`, current `0001628280-25-004818`, prior `0001628280-24-004372` |
| 2 input install | binding under `issue_47_v1`, 373 execution-authority files |
| 3 native Run | `run:historical-period:8d6e4ef1…`, **SUCCESSOR_RUN**, **FROZEN**, FY2024, B04 = 2375000000 EXACT |
| 4 new-process replay | same run id, same period, same value, 13 records, separate interpreter, no network |
| 5 public row | Marriott International / 1048286 / B04 Net income / FY2024 / ANNUAL / 2024-01-01→2024-12-31 / 2375000000 USD / OK / 10-K filed 2025-02-11, 1 evidence row |

2,375,000,000 is the figure `test_values_match_independent_arithmetic_on_the_original_filings`
computes in the test file itself from the original Company Facts JSON, by
`accn + start + end`, without calling the selector under test.

## What had to be built, and what it reuses

Four new files, none of which changes a frozen byte:

* `requirement_profile_v16.py` — the engine for `issue_47_v1`, the same shape as
  the engines before it, bound to one Requirement id because that is this
  repository's convention.
* `requirements/issue_47_v1/` — the snapshot, minted from the tree by
  `tools/vnext_mint_historical_requirement.py` rather than written by hand. Its
  execution authority is the parent's 360 files plus the twelve historical
  ones and one module the parent's own list omits, so a Run of this generation
  records the code that produced it.
* `historical_run.py` — install, create, replay and authority validation for a
  pinned period, calling `run_store` directly.
* `historical_projection.py` — the public row. Same presentation policy, same
  row and evidence field sets, same `projector` helpers. One difference, and it
  is the whole reason a successor exists: the ordinary renderer re-prepares the
  company's *latest* annual input and requires the Run's fiscal label to match
  it, which no past year can satisfy.

The Run store, the Calculator, the Specs, the applicability rules, the source
readers and the presentation policy are imported unchanged. There is no second
engine.

## What running it on more than one company changed

`native-run-matrix.json` is 96 attempted positions: 16 wired metrics across six
company-periods and three companies, including two issuers whose fiscal year
does not end in December. 90 reach a frozen native Run and a public row, 45 of
those carrying a value and 45 a structural non-applicability. Every record says
`calls: {provider:0, paid:0, sec:0}`.

The six that did not are all one company, one grain, and one real defect, which
is what the matrix was built to find.

### Macy's instants, and the fourth and fifth hunks

Macy's fiscal 2025 ends **2026-01-31**. An instant metric is measured at the
period end, so its target period is `2026-01-31 -> 2026-01-31` with
`fiscal_year` 2025. `records.validate_run_coordinates` requires
`period_start.year <= fiscal_year <= period_end.year` unless `prior_label`,
which needs an instant, `fiscal_year == period_end.year - 1`, **and**
`point_in_time_fiscal_label`. That flag is decided from a hard-coded set of
requirement ids ending at `issue_28_v13`, in **two** places:
`run_store.py` and `records.py`. Neither knew `issue_47_v1`.

Macy's ten duration metrics passed in the same case, because `2025 <= 2025 <=
2026` holds for a year running `2025-02-02 -> 2026-01-31`. Three Marriott
periods and Salesforce passed on every metric, because their labels and their
period ends share a calendar year. So this was invisible until a non-calendar
issuer was run, and invisible even then for ten of its sixteen metrics.

`records.py` also has to join the re-recorded set, for the same reason
`run_store.py` did: the parent binds its unpatched bytes, so a patched one makes
the inherited authority entry stale and the snapshot stops loading. Three files
now differ from what `issue_28_v13` records rather than two.

### The estimate has now been wrong twice, in the same direction

Two hunks were estimated from reading. Building the first Run found a third.
Running six company-periods found a fourth and a fifth, in a second and third
file. The pattern is worth stating plainly: every increase came from executing
something, and none from re-reading the code.

## One module the authority does not name

`tools/vnext_authority_closure.py` walks the import graph outward from the
Python modules an execution authority names. For `issue_28_v13` the answer is
one file: `scripts/vnext/requirement_profile.py` is in the authority and imports
`requirement_profile_v10` through `v14` at module scope, and `v11` is the only
one of the five the list omits. Anything assembled strictly from that authority
cannot import `requirement_profile`, so it cannot load a Requirement, so it
cannot replay a Run.

`issue_47_v1` names it. `issue_28_v13`'s manifest is untouched and its closure
hash is unchanged; a Requirement names the code its own Runs execute, and this
one does. Thirty further modules are reachable only through function-local
imports on routes a historical Run never takes, and are reported separately
rather than folded into the same number.

This was found by trying to build a delivery from the authority alone, not by
reading the list.

## The registration, and its exact cost

`0001-register-issue47-v1.patch` holds the only edits to frozen-authority
files: **six hunks in three files**.

1. `requirement_profile.PROFILE_ENGINES` — one generation entry, registered as
   a module path string so a retained runtime never imports it.
2. `run_store._validate_records` — one `elif` on the Run's own
   `requirement_id`, dispatching authority validation to `historical_run`.
3. `run_store._replay_structured_result` — one `elif` in the same shape,
   dispatching the structured replay.
4. `run_store._validate_run_authority`'s frozen-replay branch — the same `elif`
   once more.
5. `run_store.create_run` — `issue_47_v1` added to the set that decides
   `point_in_time_fiscal_label`.
6. `records._validate_record_semantics` — the same id added to the second copy
   of that set, which validates the manifest record itself.

The third was not in the earlier estimate. It was found by building the Run:
without it the replay falls through to the generic structured path, which
demands an `accession` and `entity` on the calculation target that the shared
`calculate_observation_metric` does not set. The fifth and sixth were not in any
estimate either, and neither appears at all until a non-calendar fiscal year is
run — see Macy's above. That is what an estimate misses and an execution
finds.

Verified with `git apply --check` against this branch's head.

### Both halves, measured in the same tree

With all six hunks applied to an isolated runtime copy:

* the new chain runs — steps 1 to 5 above;
* an **existing `issue_28_v13` package**, installed before any seam edit, still
  loads `issue_28_v11`, `v12` and `v13`, still passes
  `load_run_requirement_snapshot` for `v13`, and still replays its historical
  inputs. All five probes OK.

So registering the successor does not invalidate packages installed before it.

### The one thing that is not free

`issue_47_v1`'s execution authority has to record `requirement_profile.py`,
`run_store.py` and `records.py` **as the patch leaves them**, because those are
the bytes its Runs execute. `issue_28_v13`'s manifest is untouched and its closure hash is
unchanged at `sha256:047e4d40…`, which the minting tool prints on every run.
The consequence, which the tool also prints:

> a data root therefore satisfies one of the two Requirements, not both

That is not a workaround, it is what an execution authority means. It does mean
the snapshot in this branch, minted before the patch, is **not** the snapshot to
ship: it must be re-minted in the same change that applies the registration.
`tools/vnext_mint_historical_requirement.py --check` fails when the two are out
of step, so this cannot be forgotten silently.

## A delivery that does not need the checkout

`portable-delivery.json` is `tools/vnext_historical_delivery.py`'s own output.
It assembles `runtime/` from the Requirement's execution authority plus every
`requirements/` snapshot, puts the installed `data/` and the frozen `run/`
beside it, and replays from that directory alone:

```
python3 tools/vnext_historical_delivery.py \
  --runtime-root <tree with the registration patch> \
  --data-root <installed data root> --run-dir <frozen run> \
  --delivery /tmp/delivery --output portable-delivery.json
```

45.2 MB: 13.8 MB of runtime, 31.5 MB of installed data, 24 KB of Run. The replay
runs in a separate interpreter under `-I`, from working directory `/`, with only
`PATH` and `PYTHONDONTWRITEBYTECODE` in the environment and no network. Result:
Marriott FY2024 B04 = 2,375,000,000 EXACT, the row renders with its hash, and

```
"vnext_modules_outside_the_delivery": [],
"sys_path_entries_outside_the_delivery": [],
"depends_on_no_checkout": true
```

All 99 `vnext` modules that get loaded resolve inside the delivery. That is the
claim checked rather than asserted.

### This retracts an earlier conclusion of this branch

`51b024b` recorded that "a self-contained package is not unimplemented, it is
forbidden by an existing invariant", reading `B06_EXTERNAL_CANDIDATE_ROOT_REQUIRED`
as a prohibition. It is not one: `_external` refuses the data root *overlapping*
the code root, and siblings do not overlap. The correction is this working
delivery rather than a third paragraph about it.

### Four files no authority names

The delivery needs four files beyond the execution authority, and the report
lists them rather than absorbing them:

```
docs/evidence/issue_28_r4_label_policy.json
docs/evidence/issue_28_annual_candidate_policy.json
docs/evidence/issue_28_annual_runtime_policy.json
docs/evidence/issue_28_annual_repair_policy.json
```

`requirement_profile_v4` through `v7` read them at a runtime-root-relative path
while a Requirement is loaded, so a delivery assembled from the authority alone
stops on the first load with a missing-file error. They are policy inputs a Run
is validated against. A broader scan finds 32 repository-relative data paths
that authority-named modules reference and no authority names; these four are
the ones the Requirement-load chain actually reaches, and the rest are not
claimed to be reached.

### The event archive could not tell pinned from latest, and now can

`event-native-runs.json` below uses `2025-12-31` for all six metrics, and that
is also this company's latest annual period. A route that quietly answered from
the latest filing would have produced exactly the same six rows, so that archive
on its own does not separate the two behaviours. The component-level case in
`tests/vnext/test_historical_period_results.py` does separate them, but nothing
at the Run and row level did.

`pinned-versus-latest.json` closes that. C01 is run natively at `2024-12-31`,
which is **not** the latest period, beside the same metric at `2025-12-31`:

| requested | Run | value | row fiscal year | row period |
| --- | --- | ---: | ---: | --- |
| 2025-12-31 (latest) | `…5ef4b5f594c0` | 3 EXACT | 2025 | 2025-01-01 → 2025-12-31 |
| 2024-12-31 | `…8bae5b812eff` | none, `HISTORICAL_ZERO_AI_SOURCE_ROUTE_UNRESOLVED` | 2024 | 2024-01-01 → 2024-12-31 |

Different Run identities, different windows, different outcomes. A route reading
the latest filing would have answered 2024 with the same 3.

What this is evidence of, stated narrowly: **period isolation and missing-source
handling** — the request was not replaced wholesale by the latest year's success,
and the pinned period and its limitation both reach the public row. It is *not*
an FY2024 event count, because no count was produced; and it does not generalise
to every historical route. A positive historical result still needs a year whose
8-K material is saved.

### The event metrics do reach a Run and a row

`event-native-runs.json`. When the event route was committed it was proven only
through `prepare_historical_run_input`, and that was said at the time rather than
glossed. It is now proven through the whole chain — installation, a frozen
native Run, and a rendered public row — for all six metrics on Marriott's pinned
2025 window, in 527 seconds with `calls` zero throughout:

| metric | Run value | row value | row period | evidence rows |
| --- | ---: | ---: | --- | ---: |
| C01 | 3 | 3 | 2025-01-01 → 2025-12-31 | 3 |
| E01 | 0 | 0 | 2025-01-01 → 2025-12-31 | 1 |
| E02 | 0 | 0 | 2025-01-01 → 2025-12-31 | 1 |
| E03 | 3 | 3 | 2025-01-01 → 2025-12-31 | 3 |
| E04 | 0 | 0 | 2025-01-01 → 2025-12-31 | 1 |
| E05 | 0 | 0 | 2025-01-01 → 2025-12-31 | 1 |

Every row carries the pinned year, not the company's latest one, and the Run
value and the row value agree — which is the pair that the B01 defect broke
without either half looking wrong on its own.

## The text Run: eight changes, and the prediction was half right

The section that used to sit here called `prepare_text_contexts` the "likely
seventh" hunk and said only building it would decide. Building it decided, and
it corrected the prediction twice over.

**The first obstacle was mine, not the store's.** `historical_run.validate_run_authority`
compares a Run's computation graph against the records the rebuilt input
produces. A text case computes its result inside the Run factory, so those
records cannot contain it and the comparison always failed with
`HISTORICAL_RUN_COMPLETE_COMPUTATION_GRAPH_CHANGED` — before `run_store` was
reached at all. The authority now re-derives the candidate, the evidence check
and the review unit from the data root and requires byte equality with the
Run's, which anchors the chain one record higher rather than lowering it:
`run_store` binds the observations to that same unit and the trace and result to
those observations.

**The store then needed two changes, not one.** `prepare_text_contexts` is
selected by a requirement-id chain, and so is `text_handlers` fifteen lines
below it. Falling through the second produced
`build_text_evidence() got an unexpected keyword argument 'source_filings'`,
because the default handler is D01's and takes a different signature.

So the registration is now **eight changes in three files** (the diff shows
seven hunks: the two `run_store` text changes are adjacent enough to merge).
With them applied, Marriott's pinned 2025 D02 reaches a **FROZEN** native Run,
`EXACT`, `TEXT_V1`, ten text items, `calls` zero.

### The negatives, and which layer actually answered each one

A negative that records only "it was refused" proves less than it reads. Three
rounds of tampering with this Run make the point, and all three are kept because
the difference between them is the finding:

| round | cases reaching the layer they meant to test |
| --- | --- |
| tamper after freezing | **0 of 5** — every one answered by `records_file_hash` |
| tamper while OPEN | **3 of 6** — three answered by record-schema validation |
| substitute another year's genuine records | **3 of 3 so far** |

`tools/vnext_refusal_layer.py` classifies a refusal to the layer that produced
it — frozen-file seal, record schema, record graph, Requirement authority, text
protocol — and each case declares which layer it meant to reach. A case blocked
earlier is recorded as `inner_check_not_covered`: not a pass, not evidence the
inner check is broken, just untested by that input.

The first round is retained as a **frozen-file integrity test**, which is what
it actually is. It does not support any claim about text semantics.

What the rounds that did reach their layer establish: deleting the candidate or
the evidence check is refused by `HISTORICAL_RUN_TEXT_DERIVATION_CHANGED` naming
the record, deleting an observation by the store's own
`Text reviewed observation exact set differs`, and a genuine record from another
pinned year — internally consistent by construction, so nothing is decided by a
hand-computed hash — is refused on meaning: a foreign review-unit binding, an
absent execution trace, a candidate that does not re-derive.

### It does not reach a public row, and that is the next piece

`render_historical_run` refuses it with `HISTORICAL_PROJECTION_TEXT_ROUTE_NOT_WIRED`,
which is exactly what this branch predicted when the text input was committed.
The row needs the renderer's text branch, ported from
`ordinary_projection`'s `text_payload` arm the way the source-derived evidence
arm was. Until that exists, D02 is a Run and not a published position, and the
coverage frame is not moved.

`historical_text_input.py` proves the D02 *result* for a pinned period, and this
branch's claim that the text metrics were blocked on a missing capability was
wrong for the same reason the event claim was: the machinery is period-driven
and only the input preparation assumed "latest". But a result is not a Run, and
reading `run_store` before building the rest turned up where the next cost sits:

```python
if manifest.get("requirement_id") == "issue_28_v14":
    from .capacity_run import prepare_text_contexts as prepare_text_run_contexts
elif manifest.get("requirement_id") == "issue_28_v13":
    from .normal_run_v3 import prepare_text_contexts as prepare_text_run_contexts
elif manifest.get("requirement_id") == "issue_28_v12":
    from .normal_run_v2 import prepare_text_contexts as prepare_text_run_contexts
else:
    from .text_run_validation import prepare_text_run_contexts
```

A historical TEXT Run falls into the `else`. Whether that generic path suits a
binding this branch produces is not settled by reading it, so this is recorded
as the likely **seventh** hunk rather than asserted as one — the pattern all day
has been that only building it decides. What is already clear is that the
observation replay beneath it (`text_review_replay`) dispatches on nothing at
all, so the text protocol itself needs no new registration.

## What this still does not establish

* Three companies, six company-periods, sixteen metrics. The other seven
  companies and the remaining pinned years are not run here, and no metric
  outside the wired sixteen has a historical route at all.
* `issue_28_v14` compatibility is untested, as in the earlier seam measurement:
  a v13 data root has never carried v15's engine.
* Nothing is adopted, activated, published or merged. Every record says
  `production_authorized: false`, and the row is a `FROZEN_CANDIDATE`.
