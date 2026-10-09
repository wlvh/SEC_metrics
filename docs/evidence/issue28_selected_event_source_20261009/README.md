# Selected event source interface for ordinary and historical consumers

Base: main `3d6030b1bc5e1e7b22833a0101fbeb8f88341498`. These tests run from
this short branch, not the original PR43 checkout. Product changes are
`selected_event_source_v1.py` and the narrow optional arguments/raw-blob merge
in `normal_zero_ai_results.py`. Test/evidence edits do not create live credit.

## What a consumer can do

`read_selected_event_sources(data_root=..., rules_root=..., prepared=...,
period=..., registered_union=False, history_validator=None)` reads the saved
submissions index, overlapping blocks, each event body and header. It reuses
the existing event walk, item adapter, source-set construction and acquired
header census. It returns neutral claims, source references/records, request
proofs and actual filing/window relationships. It does not select an annual
filing, approve amendments, match a metric, calculate, save a Result/Run or
confirm E01. An empty result is not independent non-disclosure evidence.

`data_root` needs company registry, the request log/manifest and exact saved
body/header paths, including its acquired-header census. `rules_root` supplies
the existing company registration and event projection. No code, catalog,
model answer, Result or old journal is copied into the source-only package.
Both registries must agree for the selected company. For predecessor-only
periods leave the union false; a caller must select the approved registered
union and its window explicitly, never infer a financial combination.

The optional history validator receives keyword arguments `shard`, `body`,
`rows`, `shards`, `period`. `body` is the complete JSON just read, including
forms not retained in `rows`. The historical consumer can adapt its existing
`block_last_days`/`history_block_coherence` here; a non-None conflict blocks
collection. Default ordinary validation remains `history_body_alignment`.
The consumer must include this interface, the ordinary event walk, its
validator and related config/catalogs in its processing dependencies. This
interface does not claim that the original ordinary history check proves the
historical block count. Historical selection/admission/CSV remains #47-owned.

## Narrow correction found by the new two-registrant control

The original union rejected identical HTML bytes stored under two different
request paths because the content-addressed RAW_BLOB records differed in
`storage_uri`. Both readers had already verified the bytes. The merge now
retains one RAW_BLOB locator only if all its other fields agree; distinct
SourceReferences and both exact request proofs remain. Other record or media
conflicts are still rejected. No row, locator, identity or original file is
rewritten. `original-union-collision.log` reproduces the original main refusal
and the fixed two-claim/six-proof outcome on the same small recorded inputs.
The first reproduction driver had a signature mismatch, not a product failure;
its traceback is retained in `original-union-driver-first.log`. The corrected
`verify_original_union.py` removes only the new optional keyword before invoking
the untouched original union. This is a correctness correction in the shared event helper,
not permission to ignore different source bytes or registrants.

## Executed evidence and limits

- `small-tests.log`: six small event-source cases plus the 35 existing update
  and per-metric producer cases; 41 passed in 0.332s, zero skips. Recorded
  body/header/ledger reading is real. Cases include nonempty and registered
  union inputs, complete history-body delivery/conflict, missing/corrupt bytes,
  repeated legacy GETs, latest failure, wrong registrant/window/registry.
- `saved-event-comparison.json`: actual saved Marriott FY2025 inputs, 10 event
  filings, 20 claims and 21 proofs. Original main walk and selected source-only
  walk returned exactly equal claims, manifests, filings and request proofs.
  Original preparation plus walk 1.050s; selected walk plus proof verification
  0.944s. These operations have different responsibilities; no speedup ratio.
  Direct reading of original headers found three Item 5.02 accessions, listed
  in the JSON. This confirms that particular item count, not all item meanings
  or the content-confirmed E01 target.
- `verify_saved_events.py` reproduces the comparison with only isolated writes.
  Its original function comes from fixed main above. Source ledger unchanged.
- Existing ordinary event calculation/save/CSV/reentry/read integration is in
  `current-event-integration.log`: five tests passed in 14.334s, zero skips.
  This includes real saved-source calculation/CSV and forbidden-factory
  reentry, with nonzero Marriott and zero Pfizer Item 5.02 controls.
- `event-boundary-tests.log`: final seven event-source tests passed in 0.078s;
  adds the conflicting-media negative control for the narrow blob merge.

The shared module is already in ordinary processing identity, so its change
must trigger the relevant current update. New explicit consumers must declare
the new module and callback code/config. Old frozen snapshots and saved Runs
are unchanged and remain tied to their saved program; no new old-native
Requirement execution, byte re-signing or old response re-labelling is claimed.
No full five-year material batch, 390-coordinate acceptance or production
permission is supplied by this source interface.

## Reused controller result, not a new controller repair

#47's `eecbf805` event reentry failure used an old `ordinary_current_update`
that still called the ambiguous legacy selector. Main already contained
`24155225`'s explicit latest-attempt verifier. Read-only checking the supplied
FY2025 E02 manifest from main verified all 23 proofs, including ten headers
with four GET rows each, in 1.448s. #47 then received that main file and reported
successful same-task reprocessing and forbidden-factory reentry in
`0918862a`; that result is execution-side evidence, not a parent financial
rerun. The old failures remain. No competing controller was written here.

Original business ledger unchanged: 195 claim rows, SHA256
`6023bf1790b31d5895dad3ef824b3d102d56b0381140f6b79463d8e97964f6eb`.
New SEC/provider/paid calls 0/0/0. No merge, Ready, adoption or deployment.

## Gap-day increment after the first limited review

The first review at `820461a0` is NEEDS_FIX, retained in full. Its small
counterexample shows that a block containing a cross-year gap-day event is
skipped before the complete-body callback. Empty acquired census can then
return a smaller source set; a captured header census instead raises the
existing supplement gap. Neither result creates business credit here.

The explicit successor now also accepts `history_last_days(payload=..., shards=...)`.
A historical consumer can pass its existing `block_last_days` function. It
returns every original shard name and effective ISO date; missing names,
invalid dates or shortening declared coverage are rejected. A complete-body
validator is required with that strategy. The walk selects blocks using those
effective ends and passes that exact `last_day` into the body validator.
The declared shard, full body, issuer and actual task period are preserved.
No caller changes the yearly window to avoid the problem. Without the new
strategy the original declared filingTo selection/check remain unchanged.
This is an explicit program/config dependency, not an arbitrary date answer
or a new source acquisition permission.

`gap-regression-before.log` records the missing optional interface in the
first patch (TypeError); the semantic omission itself is the independent
`history-gap-counterexample.log`. `gap-regression-after.log` contains eight
passing small tests in 0.097s, including the actual catalog algorithm selecting
the Jan1 block and sending the same Jan1 boundary to complete-body coherence.
The conflict, missing-boundary and missing-validator negatives still fail.
Earlier Marriott material and current event save/CSV/read results are reused:
their declared ordinary overlap policy and other responsibilities are unchanged.
The new gap responsibility is not claimed from those old material tests.

The gap-only followup review at `35b9329d` passed. The original NEEDS_FIX
remains the prefix of the same conclusion. Cumulative agent tools 47/messages
3, no original-material rerun. Main `ae8a13c8` was received at `b306f154`; all
three reviewed source/test files are byte-identical to `35b9329d`. The new
combined small test terminal is in `main-receiving-small-tests.log`. Neither
main reception nor the source interface review grants a full company result.
