# R4 release implementation performance measurement

The complete current 16-case workload passes at **21.308919×** aggregate local
wall-time improvement. This measurement binds Requirement `sha256:5b7a386b7c95f8b9542a2251a94ec8d98876e7c833d49132364c77024b27ff9e` and
receipt `sha256:c1f44bff2a093046cd0d86fc4986dd62da5507a37174dda52e51aa5fac0fb7d3`. Full values and deterministic counts are
in [the receipt](performance_session_benchmark_release_seam_final.json) and
[streamed progress](performance_session_benchmark_release_seam_final.stdout.jsonl).

```bash
PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/opt/python@3.14/bin/python3.14 tools/benchmark_r4_offline_session.py --benchmark --requirement-id issue_28_v2 --requirement-closure sha256:5b7a386b7c95f8b9542a2251a94ec8d98876e7c833d49132364c77024b27ff9e --output docs/r4_offline/performance_session_benchmark_release_seam_final.json
```

Return code0. Three separate processes used the same interpreter, inputs and
16 results: nine scoped extraction, three structured primary and four zero-call
classes, with six prior terminal Runs. Their semantic result-set ID is
`sha256:0550b6b3a674c65ab5d9fa7c8c250ee5dfffd10c00bf44454727e2b9323c23e1`.

| Process | Wall seconds | Peak RSS bytes | PID |
|---|---:|---:|---:|
| baseline | 2740.179226 | 2710355968 | 54023 |
| optimized | 65.929364 | 1773305856 | 55627 |
| independent-replay | 65.749230 | 1859780608 | 55677 |

The one fresh independent replay is charged to both alternatives:
`2805.928456 / 131.678594 = 21.30891871460899711611440809`.
The external clock guard passed with a wall-minus-monotonic difference of
0.063607s. The earlier
sleep-interrupted attempt was stopped and remains invalid evidence.

| Operation | Baseline | Optimized | Fresh replay |
|---|---:|---:|---:|
| source_materializations | 112 | 10 | 10 |
| derived_asset_builds | 112 | 10 | 10 |
| requirement_builds | 16 | 4 | 4 |
| revision_requirement_builds | 16 | 4 | 4 |
| parent_authority_builds | 16 | 4 | 4 |
| portable_prior_run_loads | 96 | 6 | 6 |
| canonicalizations | 148434 | 24257 | 24257 |
| semantic_hashes | 140757 | 23148 | 23148 |
| provider_calls | 0 | 0 | 0 |
| paid_model_calls | 0 | 0 | 0 |
| sec_calls | 0 | 0 | 0 |

The optimized workload has four process-local sessions, including the fixture
classification source session. Every session prepares its full source/asset/
Requirement once; every child records zero full source/asset/parent rebuilds
and zero prior-Run loads. Whole-workload materialization counts also include
the six independently loaded historical Runs. There is no persistent cache.

Full host-process RSS above is distinct from the guarded parser worker limit.
JPM/BAC/Citi parser measurements use512MiB/no-swap/network-none and the same
production limit210000, with no runtime override; their expanded counts are
124761/200229/95463. [Per-source parity](performance_resource_release_seam_final.json)
retains exact DerivedAsset IDs, canonical bytes and grid identities.

Provider/paid/SEC is0/0/0. Credit is `NONE_OFFLINE_BENCHMARK`. This performance
replay neither executes live qualification nor publishes R4; the separate
recorded release rehearsal supplies the projection/rollback implementation proof.
