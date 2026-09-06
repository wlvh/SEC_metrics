# Full offline execution benchmark method

This document defines the measurement method. It is not a performance PASS;
the content-addressed benchmark receipt records the actual result.

## Same real workload, two execution strategies

The workload is derived from the strict R4 fixture matrix and the complete
qualified-case index. It includes the actual mixture of scoped extraction,
native structured-primary results and zero-call classifications. No fake Reader
request is created for a structured or zero-call case. All case IDs must be
unique, and their metric union must be the exact six R4 metrics.

The baseline uses the ordinary uncached APIs once per actual fixture: native
prior-terminal validation, Requirement loading, full-source construction and
the native kind-specific disk artifact replay. The repeated six-Run prior gate
models the existing qualification phase gate's pre-session all-Run scan. The
six inputs are byte-checked against main `c45338567700e3048f4cf32d251369e4521e9444`,
not PR #22. There are no invented duplicate fixtures, sleeps or dummy workloads.

The optimized strategy replays that prior history once, then checks its exact
source/control file pins at each child boundary. It groups real cases by
source and uses the normal production parser once per source session. A
factory-owned native XBRL parse is reused for structured claims, but native
claim evaluation still runs for each task. Full local tables remain Evidence
authority; the immutable Evidence/scoped contexts call the same native
locator, scope, numeric and constraint logic as the uncached APIs.

Cold Requirement, table materialization, XML parsing, transport certification
and scope certification are inside the optimized timing. Source/asset/authority
construction, prior-Run replay, XML fact/context parse and full-asset JSON decode
inside a child cause failure. The bytes-only B0 ownership interface has exactly
one setup-only full-asset JSON decode after the one native grid construction.
The Evidence factory derives and verifies the full Reader manifest/transport
on that private graph; no temporary second graph is decoded first. Native
grid construction, canonical-byte ownership deserialization and compact
transport round-trip are distinct, counted cold operations, never renamed
as zero work. Independent final replay reconstructs them afresh from disk.

## One independent final disk replay

Baseline, optimized and final replay each run in a fresh process with the same
Python executable. The final process receives only pinned disk inputs and
reconstructs fresh source/Requirement/native contexts. It never receives the
optimized process's cached source or parsed objects. All three processes must
produce the same exact semantic result-set hash.

There is exactly **one** final replay process. Its measured time is charged
equally to both alternatives:

```text
baseline aggregate  = baseline process time  + final replay process time
optimized aggregate = optimized process time + final replay process time
improvement         = baseline aggregate / optimized aggregate
```

This includes the mandatory final work in the optimized denominator without
performing a second redundant final replay for the comparison. The requirement
is improvement >=10. A lower result is retained as `BELOW_REQUIRED_10X` and the
command fails; it is not discarded or relabelled as acceptance.

## Measurement and safety

Native operation-entry counters cover full-source/table construction, actual
full JSON asset decodes, Requirement/parent builds, prior Run replay, XML fact
and context parses, native claim evaluation, source-structure scans, canonical
serialization, semantic hashes and provider/SEC entrypoints. Per-source cold
and per-child counters are separate from the aggregate counts. Wall time is
measured around complete fresh subprocesses; each reports actual peak RSS.
The exact interpreter executable SHA, version and platform must also agree.
The current V3 revision engine and retained V1 parent engine have separate
construction counters; one cold construction of each layer is not mislabeled
as a second construction of the complete chain. Each source session pins the
entire already-loaded revision/parent/foundation chain and retained engine
dependencies, with no additional parent-loader call.

The macOS process-tree sandbox denies networking, a process audit hook rejects
network attempts, and provider/SEC entry observations must remain zero.
Credentials are not forwarded. No production freeze, cycle, Stage-A, Run,
publication or rollback receipt is created. The independent 512 MiB/no-swap
production-parser measurements remain separate resource evidence; the whole
host-side benchmark reports its own RSS and does not claim a cgroup it lacks.

Runtime/config/catalog/Requirement bytes, actual artifact files and immutable
source references are pinned before execution and rechecked afterward. Any
input change aborts rather than silently refreshing the benchmark authority.
All results retain `NONE_OFFLINE_BENCHMARK` qualification credit.

The full command is:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 tools/benchmark_r4_offline_session.py \
  --benchmark --requirement-id issue_28_v2 \
  --requirement-closure <exact-current-proposal-closure> \
  --output /tmp/r4_offline_session_benchmark.json
```
