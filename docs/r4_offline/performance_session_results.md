# R4 offline session performance: PASS

Historical measurement at rejected candidate `f415859`. The receipt and raw
progress stream remain byte-identical. Current rework results are tracked in
[the live-seam review summary](live_seam_review_summary.md); this older 21.79x
measurement does not validate a later Requirement closure.

The actual same-input comparison achieved **21.789879× aggregate improvement**.
It replayed all 16 certified cases, including nine scoped extractions, three
native structured successes and four zero-call classes. There were no provider,
paid-model or SEC calls in this benchmark, and no qualification credit.

## Exact evidence

- Requirement: `issue_28_v2`, closure `sha256:1fd51438196661964d51a8b37d270d05804ac04fd178f599a18f84a80a4d567a` (`NOT_ACTIVATED`).
- Qualified-case index: `sha256:c14d191b0666e467ae809298d2411e95fe21bb73f072e646c7183d088b7356c2`.
- Workload: `sha256:c6f9c189cd8d453c8220d396ea46cefa00a3314aaceadb8fb497310878286743`, with 223 exact file bindings and six terminal Runs byte-verified against main `c45338567700e3048f4cf32d251369e4521e9444`.
- [Complete receipt](performance_session_benchmark.json): `sha256:190390eef384cebdb76e4f8e2b93e018005287cea96f61453e309c3a1b0b6eee`.
- Exact receipt-file SHA-256: `ca00f20c1e0475c184c2a1f325aa8e9653dac8e7e4f0628514b0b7dbf0a4bb81`.
- [Actual streamed output](performance_session_benchmark.stdout.jsonl): all 48 completion events, per-fixture timings and final status.
- Driver: `tools/benchmark_r4_offline_session.py`, SHA-256 `03cd6141122c6a647b52a871c19419ad5a8821af822e2ba0e65156a285f65994` (30,203 bytes). There was no external timing wrapper.

The executed command returned **rc=0**:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 tools/benchmark_r4_offline_session.py \
  --benchmark --requirement-id issue_28_v2 \
  --requirement-closure sha256:1fd51438196661964d51a8b37d270d05804ac04fd178f599a18f84a80a4d567a \
  --output /tmp/r4_offline_session_benchmark_final.json
```

The process-tree network-deny sandbox, credential-filtered environment and
native operation observer were active. The 3,600-second worker guard was not
changed, and the baseline was not interrupted or restarted. The actual
subprocess commands and exact interpreter binary SHA/version/platform are in
the receipt. No non-progress stderr or failure output was observed.

## Timings and exact replay

| Measured component | Seconds |
| --- | ---: |
| Unoptimized process | 2,782.458871 |
| Optimized process, including cold preparation | 65.164900 |
| One fresh independent final disk replay | 65.537831 |
| Baseline aggregate, including the shared final replay | 2,847.996702 |
| Optimized aggregate, including the shared final replay | 130.702731 |
| Aggregate improvement | 21.789879× |

The final replay cost is charged to **both** alternatives, not omitted from
optimized time. The three measured process times sum to 2,913.161602 seconds;
the outer measurement harness's small preflight/reporting overhead is not
presented as a separately measured CLI duration.

Worker PIDs were distinct: baseline `61735`, optimized `64342`, final `64456`.
All three produced the same 16-result semantic set:
`sha256:d3f5e700b3d65b8627af49d06d457c9b896929ad92b02ce29518fb2d6b07830a`.
There was exactly **one** final full R4 disk replay. It reconstructed its own
source, Requirement and native verification contexts from pinned disk inputs;
no Python object was passed from the optimized process.

## Native operation counts

| Actual native work | Baseline | Optimized | Final replay |
| --- | ---: | ---: | ---: |
| Full source materializations / DerivedAsset builds | 112 / 112 | 10 / 10 | 10 / 10 |
| Portable prior-Run replays | 96 | 6 | 6 |
| Current V3 / retained V1 / recorded historical-parent constructions | 16 / 16 / 16 | 4 / 4 / 4 | 4 / 4 / 4 |
| Full DerivedAsset JSON deserializations | 192 | 16 | 16 |
| Canonicalizations | 148,290 | 24,239 | 24,239 |
| Content semantic hashes | 140,709 | 23,136 | 23,136 |
| Execution-semantic hashes | 776 | 473 | 473 |
| Native Evidence checks | 143 | 26 | 26 |
| Full compact-table decodes | 165 | 12 | 12 |
| XML fact / context parses | 4 / 4 | 3 / 3 | 3 / 3 |
| Native structured claim re-evaluations | 4 | 4 | 4 |
| Full source-structure parses | 40 | 3 | 3 |
| Provider / paid / SEC calls | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |

The aggregate `10` source/asset builds are **six independent historical Run
replays plus four current source sessions**, not ten builds inside a current
R4 session. The 16 asset deserializations similarly include 12 reads performed
by the native historical Run verifier and four current-source ownership
deserializations. Historical responses were read only to verify those old
terminals; they were not cached or reused as R4 answers.

Each current source session performed exactly one native full source/asset
construction, one canonical-byte ownership deserialization, and one
construction of each current/parent Requirement layer. Every optimized/final
child had **zero** full source/asset/Requirement construction, prior-Run replay,
full asset JSON deserialize and XML fact/context parse. Native Reader/Evidence
and structured claim logic still ran for the appropriate case kind. Cached
objects were process-local and pinned by exact path/hash/size and content IDs.

The source-session `OPEN` state in each worker report is the local state before
the outer independent-final-replay gate. These are in-memory offline source
sessions, not open financial Runs; all worker processes exited. The aggregate
receipt, not that pre-final local state, records the final verified result.

## Why A12 dominated the baseline

JPM A12 had 88 audited locators and eight out-of-window candidates. BAC A12 had
156 audited locators and 100 out-of-window candidates over 369 original tables
and 200,229 expanded cells. Their actual cold case times were 477.877782 and
1,213.495370 seconds. Each also executed ten full source-structure parses.

The ordinary path in `source_scope.py::_validate_audit_closure` resolves every
audited locator through `table_grid.py::resolve_cell`, which revalidates the
complete asset. `composite_scope.py::_composite` rebuilds source structure when
there is no verified offline context. This is finite real validation work,
not a sleep, duplicate invented fixture, stuck process or weakened timeout.
The optimized contexts certify the immutable full inputs once and use the same
native locator/Evidence logic afterward. Warm A12 case times were 0.194379 and
0.193417 seconds, but those component times are **not** the aggregate gate;
all cold setup and independent final replay costs are included above.

## Resource evidence is a separate boundary

Whole host-process peak RSS was 2,334,113,792 bytes for baseline,
1,735,196,672 for optimized and 1,853,308,928 for final replay. The complete
host-side scope/Evidence benchmark **does not claim a 512 MiB ceiling**.

The separate [current production-parser parity receipt](performance_resource_final_parity.json)
uses the pinned Python 3.12.11 Linux worker with 512 MiB/no-swap/network-none
guards. JPM/BAC/Citi peaks were 327,294,976 / 383,307,776 / 257,863,680 bytes;
all full asset bytes matched the earlier measurements, with production cap
210,000 and no override. Earlier immutable measurements remain unchanged.
The benchmark's `0/0/0` accounting must not be confused with the whole PR's two
separately authorized SEC acquisitions.

Receipt/log/current-input consistency is independently checked by:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest -v \
  tests.vnext.test_offline_execution_session.RecordedOfflineBenchmarkTest
```

This check validates recorded evidence; it does not execute a second final
full R4 replay or turn the unactivated Requirement proposal into live authority.
