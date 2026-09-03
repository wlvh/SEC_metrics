# R4 offline materialization and session status

Status: **MATERIALIZATION VERIFIED; AGGREGATE PERFORMANCE NOT RUN**.
The source/task audit reached the owner-escalation condition: the retained task
semantics do not auto-certify every R4 positive. The >=10x benchmark, optimized
six-task workload and final independent R4 disk replay therefore remain NOT_RUN.
A small synthetic session test or one successful materialization is not their
substitute. No source/task semantics or native Evidence checks were weakened.

## Complete JPM source, bounded offline worker

Reproduce (the output may be written outside the checkout):

```bash
PYTHONDONTWRITEBYTECODE=1 python3 tools/benchmark_r4_offline_session.py \
  --source evidence/request_attempts/4d/4d9febdbc2038dcdca8726053286df4cbbfd48885051cbd781efcc3becb66a23/jpm-20251231.htm \
  --sha256 4d9febdbc2038dcdca8726053286df4cbbfd48885051cbd781efcc3becb66a23 \
  --size 12927325 \
  --output /tmp/r4_performance_materialization_final.json
```

rc 0. The recorded output is [performance_materialization.json](performance_materialization.json),
receipt `sha256:452594ab065a39f6b907327faa8b0a1c9f844baf7bd3ae3d8f1ccf381a226064`.
It binds parser/worker source bytes and an inventory of six distinct existing
FROZEN Runs from the ten-Run R3 cycle, selected from the base's eighteen FROZEN
Runs. Inventory is explicitly not full Run replay and gives no new credit.

| Observed item | Value |
|---|---|
| Full source | 12,927,325 bytes |
| Full native DerivedAsset | 679 tables; 124,761 expanded cells |
| DerivedAsset ID | `sha256:694e176416c50b28974e8fa9844bd0d8e6ee772bd3915b2819aa708bab288110` |
| Canonical asset | 22,174,348 bytes; SHA-256 `b10c09730d894910ff4ff849c1b2928e1149d1223975d1d98e6f0801a2a8a341` |
| Child / host wall time | 3.118114 / 5.109096 seconds |
| Cgroup / child RSS / host RSS peaks | 304685056 / 297115648 / 375980032 bytes |
| Actual parse / DerivedAsset build calls | 1 / 1 |
| Actual canonicalization / semantic-hash calls | 683 / 681 |
| Actual Requirement / parent / prior-Run / Evidence calls | 0 / 0 / 0 / 0 in this materialization-only worker |
| Provider / paid / SEC | 0 / 0 / 0 |

The already-installed pinned image is
`sha256:6bb4a52297019add65df37d3abcd37819ea4e247adeaff276d03343b05b94b17`
(CPython 3.12.11). `--pull=never`, `--network none`, read-only root and source
bind mount, cgroup 512 MiB / swap 0, PID limit 32 and a 120-second parent wall
guard are mandatory. The worker checks its real cgroup, root mount and network
state before parsing. This host's kernel exposes inactive tunnel devices even
with `--network none`; the receipt records them, no non-loopback active
interface, and an empty IPv4 routing table.

The historical parser algorithm is unchanged. Only the isolated worker sets a
fixed offline research cell ceiling of 250,000; other parser budgets remain
unchanged. The production `max_total_cells` remains 100,000. No caller can raise
the worker ceiling. A resource failure remains a failure, not a fallback. This
does **not** authorize an R4 live resource policy or activate a Requirement
revision. The full asset is not a selected/renumbered asset, and it is returned
as ephemeral data, not stored as a persistent cache.

Counters observe the original Python entrypoints. CPython 3.12+ uses local
`sys.monitoring` entry events, not a replacement hash/Evidence implementation.
Older interpreters use a clearly labelled profiling fallback. The initial
all-call profiler was discarded for wall-time measurement because profiling
every cell helper distorted costs; the recorded run uses selective events.

## Existing historical Run smoke

The existing `load_portable_qualification_run(run_dir, repo_root)` was called
on R3 Run
`run:qualification:table:36a092a14fecca373f018991292c72b12fab63dd3acc5c8127b2c47acee8aea9`,
under cycle
`0c4569437b1bac3ad353394c8d8b1f59b1a1ee7c229c8fa5ee51a22269b6a448`.
rc 0, 2.081063 seconds, twelve records and FROZEN status. Actual observed calls:
portable prior-Run load 1; source parse 1; DerivedAsset build 1; native Evidence
1; canonicalization 248; semantic hash 203; execution-semantics hash 3;
provider/paid/SEC 0/0/0. This is one historical smoke, not the six-Run baseline.

A diagnostic call to current-root `replay_frozen_results` instead failed with
`SHARED_PROTECTED_CLOSURE_DRIFT`, because it tries to rebuild the historical
qualification freeze against current code. No freeze was rebuilt and no check
was bypassed. The existing immutable/portable historical loader is the correct
read-back boundary and passed unchanged.

## Session / guard tests

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_offline_execution_session
```

rc 0, 11 tests PASS, 0.976 seconds. These test one preparation across six
synthetic children, exactly one final callback receiving disk locators, exact
path/hash/size and same-size drift, symlink rejection, UNKNOWN/PENDING/FAILED/
CRASHED/reused-success stop, exception stop, no retry, actual deep operation
counts, absent-image no-pull behavior, and rejection of a worker merely
self-declaring PASS without its source/asset/code/guard binding. The original
production resource policy, native Evidence, usage/reservation/crash-recovery
code and all historical bytes remain untouched.

The provider call-graph gate also passed. Its output was directed to
`/tmp/r4_performance_provider_gate.json`, not a tracked historical receipt.

## Remaining gate (not implemented or claimed complete)

After the owner resolves the auto-positive semantic blocker, measure the same
actual six-task source/fixture workload and interpreter with >=6 prior terminal
Runs; retain all native checks; compare baseline and optimized aggregate local
wall time; require >=10x; and perform one independent final disk replay. B0's
callback/counting seam is not proof that this real workload has passed.
