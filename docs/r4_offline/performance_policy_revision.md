# R4 resource-policy continuation: bounded handoff

The current complete evidence is **production-parser resource parity**, not
aggregate R4 performance acceptance. A03's alternate positive still requires an
owner decision about source-bound entity/average proof and quarter-period
policy. The six-task optimized workload, >=10x aggregate gate and independent
full R4 final disk replay remain **NOT_RUN**. No additional SEC, provider or paid
call was made by the performance work. The integrator separately accounts for
the two approved SEC acquisitions.

## Production parser is no longer overridden

[Initial three-source measurement](performance_resource_measurement_initial.json)
used the explicitly temporary 250,000-cell research worker limit. Its observed
maximum was BAC's 200,229 expanded cells. The integrator selected 210,000: the
smallest 10,000-rounded limit covering that maximum, with 9,771 cells / 4.879913%
headroom, below the owner ceiling of 250,000. Only `max_total_cells` changed;
every other `ResourceLimits` field remains unchanged.

The worker no longer imports `dataclasses`, assigns `table_grid.RESOURCE_LIMITS`,
or accepts any resource override. It checks that the production parser uses the
production object. The session's optional guarded mode is named
`GUARDED_PRODUCTION_PARSER`; it does not select different parser semantics.

[Final production-parity receipt](performance_resource_production_parity.json):
`sha256:a3d6df6eba8bbe325096b822b22100ffde173d4be2c2771d6eae43ea53fd198d`.

| Source | Raw / expanded cells | Tables | Worker wall | Cgroup peak bytes |
|---|---:|---:|---:|---:|
| JPM FY2025 | 60,348 / 124,761 | 679 | 3.192876 s | 320,176,128 |
| BAC FY2025 | 78,980 / 200,229 | 369 | 4.675080 s | 381,923,328 |
| Citi FY2025 | 54,404 / 95,463 | 330 | 2.817996 s | 257,294,336 |

All three use the same pinned CPython 3.12.11 image, network none, a read-only
root/source mount, 512 MiB cgroup memory, no swap, PID limit 32 and wall guard
120 seconds. Every complete DerivedAsset ID, canonical asset hash/size, ordered
table/grid hash set and census matches the initial measurement. The new receipt
binds the exact native parser/worker code and explicitly records no override.
Host JSON import/RSS is measured separately from the isolated parser cgroup;
the receipt does not claim that all surrounding host Python work has a cgroup.

Reproduce each source with `tools/benchmark_r4_offline_session.py --source
<recorded source_path> --sha256 <recorded source_sha256> --size <recorded
source_size> --output <temporary output>`, using the exact three input bindings
in the production-parity receipt. This command records materialization only and
does not falsely return aggregate R4 performance PASS.

## Session and historical boundaries

The session now observes actual native operations and rejects a child that
rebuilds a full source, DerivedAsset or Requirement, or replays a full prior Run
even if the callback claims success. UNKNOWN, PENDING, FAILED, CRASHED and
REUSED_SUCCESS remain terminal. Exact file path/hash/size and directory-entry
pins detect drift, including restoration after a detected change.

The prior-Run set replays six distinct main Runs once, keeps only small terminal
summaries and exact file identities, and checks all pinned source/control bytes
on later access. No provider response is cached or reused. The source-group
interface permits one aggregate fresh-disk callback for several source
sessions. Its small unit test is not the real R4 independent final replay.

[Component diagnostics](performance_session_component_diagnostics.json) record
six native portable Run replays + six later pin checks in 13.158142 seconds,
with current manifest bytes independently matched to base main
`c45338567700e3048f4cf32d251369e4521e9444`. They also retain the intermediate
legacy-A03 context measurement: 4.823098-second cold context setup and
0.005841-second warm native Evidence, byte-identical to the native checker.
Those component timings are not a same-workload aggregate improvement claim.

## Bounded verification

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_offline_execution_session tests.vnext.test_table_stage_c_financial_materialization
```

rc 0; **22/22 PASS**, 5.447 seconds. This includes actual 210,000-cell parsing,
210,001-cell failure, unchanged remaining limits, no public/worker override,
actual child rebuild rejection, immutable history pins and the aggregate
interface callback. The historical JPM receipt/tool remains untouched. Its
test reverses only the exact authorized cap integer and twelve inserted
locator-factoring lines *in memory*, then demands the original full source
hashes; all other source bytes and the active R3 mirrors remain bound.

Earlier `performance.md` and materialization receipts remain historical records
of the first, blocked B0 phase. This new record does not rewrite them or grant
any current/successor qualification, transition activation or live credit.
