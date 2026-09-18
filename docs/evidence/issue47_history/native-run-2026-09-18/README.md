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
| 2 input install | binding under `issue_47_v1`, 372 execution-authority files |
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
  ones, so a Run of this generation records the code that produced it.
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

## The registration, and its exact cost

`0001-register-issue47-v1.patch` holds the only edits to frozen-authority
files: **three hunks in two files**.

1. `requirement_profile.PROFILE_ENGINES` — one generation entry, registered as
   a module path string so a retained runtime never imports it.
2. `run_store._validate_records` — one `elif` on the Run's own
   `requirement_id`, dispatching authority validation to `historical_run`.
3. `run_store._replay_structured_result` — one `elif` in the same shape,
   dispatching the structured replay.

The third was not in the earlier estimate. It was found by building the Run:
without it the replay falls through to the generic structured path, which
demands an `accession` and `entity` on the calculation target that the shared
`calculate_observation_metric` does not set. That is what an estimate misses
and an execution finds.

Verified with `git apply --check` against this branch's head.

### Both halves, measured in the same tree

With all three hunks applied to an isolated runtime copy:

* the new chain runs — steps 1 to 5 above;
* an **existing `issue_28_v13` package**, installed before any seam edit, still
  loads `issue_28_v11`, `v12` and `v13`, still passes
  `load_run_requirement_snapshot` for `v13`, and still replays its historical
  inputs. All five probes OK.

So registering the successor does not invalidate packages installed before it.

### The one thing that is not free

`issue_47_v1`'s execution authority has to record `requirement_profile.py` and
`run_store.py` **as the patch leaves them**, because those are the bytes its
Runs execute. `issue_28_v13`'s manifest is untouched and its closure hash is
unchanged at `sha256:047e4d40…`, which the minting tool prints on every run.
The consequence, which the tool also prints:

> a data root therefore satisfies one of the two Requirements, not both

That is not a workaround, it is what an execution authority means. It does mean
the snapshot in this branch, minted before the patch, is **not** the snapshot to
ship: it must be re-minted in the same change that applies the registration.
`tools/vnext_mint_historical_requirement.py --check` fails when the two are out
of step, so this cannot be forgotten silently.

## What this still does not establish

* One company, one year, one metric. The other fifteen wired metrics and the
  remaining four pinned years are not run here.
* `issue_28_v14` compatibility is untested, as in the earlier seam measurement:
  a v13 data root has never carried v15's engine.
* Nothing is adopted, activated, published or merged. Every record says
  `production_authorized: false`, and the row is a `FROZEN_CANDIDATE`.
