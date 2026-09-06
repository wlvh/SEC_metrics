# Current R4 offline benchmark: 21.903657x PASS

The same sixteen-case workload and six exact-main terminal Runs were measured
in fresh processes using CPython 3.14.7, executable SHA-256
`87d4df53fd91304be5bac391fb204643c36b7df2023c04a0953bcbc7d4fdf634`.
All 231 current input bindings were rechecked and remained unchanged; no other
correctness worker ran during this measurement. Provider/paid/SEC=0/0/0.

Requirement closure:
`sha256:ae1cd0cc3c59ae6ad7ef099d6661b5ec7604f7b385fedcbab41b2d7dd6df9bb3`.
Workload ID: `sha256:b8fffec23be380d06e4f89a31c4ef45781e4cbd03a5616d302708d4f8229499e`.
[Receipt](performance_session_benchmark_live_seam_final.json) ID:
`sha256:227770c42164d54b025d8c83b0373011738ac89e5435c25b5a766bfc728c1f23`.
[Unchanged raw progress output](performance_session_benchmark_live_seam_final.stdout.jsonl)
records every case; the previous f415859 receipt/log remain historical bytes.

## Actual command and time

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/time -p /opt/homebrew/opt/python@3.14/bin/python3.14 tools/benchmark_r4_offline_session.py --benchmark --requirement-id issue_28_v2 --requirement-closure sha256:ae1cd0cc3c59ae6ad7ef099d6661b5ec7604f7b385fedcbab41b2d7dd6df9bb3 --output docs/r4_offline/performance_session_benchmark_live_seam_final.json
```

Return code 0; complete command real 2877.31s, user 2808.04s, system 65.27s.
There was exactly one independent final offline replay, in a distinct process.
All three processes ran under process-tree network denial with live credentials
removed. This is not an actual model/live/publication replay or token measurement.

| Process cost used by the aggregate gate | Seconds |
|---|---:|
| Unoptimized, including report/process completion | 2748.379028 |
| Optimized, including cold preparation/report/process completion | 64.123964 |
| One independent final disk replay | 64.286819 |
| Baseline plus shared final replay | 2812.665847 |
| Optimized plus shared final replay | 128.410783 |
| Aggregate ratio | 21.90365778705671469973047357x |

The inner operation-observer times were 2748.144763/63.866601/64.037074s.
They exclude report serialization and are not substituted for the larger
process costs used above. Every mode produced the same complete semantic set:
`sha256:90f4832402955fcdcf7e3c47c82aa4426ce6679952f27cd1818d236b397a9da0`.

## Native counts, without omitted verification

| Operation | Baseline | Optimized | Final replay |
|---|---:|---:|---:|
| Full source materializations / DerivedAsset builds | 112 /112 | 10 /10 | 10 /10 |
| Prior terminal Run portable replays | 96 | 6 | 6 |
| Current/parent/revision authority constructions (each kind) | 16 | 4 | 4 |
| Full DerivedAsset JSON deserializations | 192 | 16 | 16 |
| Canonicalizations | 148434 | 24257 | 24257 |
| Semantic hashes | 140757 | 23148 | 23148 |
| Execution-semantic hashes | 776 | 473 | 473 |
| Evidence checks | 143 | 26 | 26 |
| Full compact table decodes | 165 | 12 | 12 |
| XBRL fact/context parses (each kind) | 4 | 3 | 3 |
| Source-structure parses | 40 | 3 | 3 |
| Provider /paid /SEC | 0 /0 /0 | 0 /0 /0 | 0 /0 /0 |

The optimized ten materializations are six independently replayed historical
Runs plus four current source sessions, not ten builds inside one source
session. Each current session has exactly one source/asset/authority construction;
each child has zero full asset builds and zero prior-Run replays. The counts
still include native Evidence and structured-claim re-evaluation.

Host process RSS peaks were 2411839488/2137096192/1835188224 bytes. These are
whole-process observations, not a claim of a 512MiB host limit. The separate
[production-parser measurement](performance_resource_live_seam_final.json)
is the 512MiB/no-swap/network-none guard proof for each complete bank filing.

No measurement here changes activation state, creates a live grant, reuses
archived financial responses, publishes R4 or replaces independent review.
