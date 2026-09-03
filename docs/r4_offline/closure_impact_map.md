# PR-B closure-impact map

Recorded before production/config edits. Base is main
`c45338567700e3048f4cf32d251369e4521e9444`, tree
`0b8ccaf6b6b708b2c07b8f4ce1d5dd178638493a`.
The active Requirement is `issue_28_v1`, closure
`sha256:08994b0aa3324511ce655958fbe3c48fdcd873fa2d63a9bfe4de573046d519ac`.
The separately validated transition receipt is persisted at
`docs/evidence/issue_28_transition_activation.json`; it is merge-governance
evidence, not a runtime/live grant.

## A — immutable historical authority and evidence: no changes

- `requirements/ai_first_v3_3_1/**`, `requirements/issue_15_v1/**`.
- Existing `config/release_plans/issue_15_*.json` and their pointer.
- Existing `artifacts/vnext/**`, `outputs/publications/**`, ratchet and switch
  receipts, freeze/cycle/Stage-A objects, and publication/rollback machinery.
- `outputs/active_publication.json` and the 14 active R3 root/public mirrors.
- Existing immutable SEC request-attempt bytes and the ordered old ledger prefix.
- PR #22 archive: historical development only; no response reuse or credit.

## B — retained successor policy: no changes

- All five files in `requirements/issue_28_v1/**`.
- `scripts/vnext/requirement_profile_v1.py` and its retained interpretation.
- Retained V2 evolution harness and the historical Issue #15 adapter.

## C — issue_28_v1 current execution authority: no planned changes

| Bound path / identity | Plan |
|---|---|
| `catalog/company_traits.yaml` | unchanged |
| `catalog/deterministic_metrics.json` | unchanged |
| `catalog/event_routes.json` | unchanged |
| `catalog/table_task_contracts.json` | unchanged; B06/B13 remain future R5 only |
| `catalog/zero_ai_public_projection.json` | unchanged |
| `config/company_registry.csv` | unchanged; qualification-issuer exception only |
| `config/metric_applicability.yaml` | unchanged |
| `config/provider_model_runtime.json` | unchanged |
| `config/source_strategy_registry.json` | unchanged |
| `scripts/vnext/canonical.py::SEMANTIC_VERSIONS` | unchanged |

No C edit or semantic-version change may be hidden by rebinding v1. If one is
needed, first propose a same-Issue revision with `supersedes_requirement`, retain
v1 read-back and record the new closure as NOT ACTIVATED. Requirement revision
and engine-generation numbers are independent. Implementation/tests alone do
not activate a revision.

`config/table_qualification_matrix.json` is not in C, but is preserved because
its existing loader pins historical Issue #15 semantics. The successor receives
a distinct file and entrypoint; it never reinterprets the historical eight tasks.

## D — planned additive successor implementation and evidence

| Planned changed path | Purpose / boundary |
|---|---|
| `scripts/vnext/source_scope.py` | strict content-addressed scope records; full source/asset/task authority |
| `scripts/vnext/scoped_reader.py` | separate scoped request/response entrypoints; legacy Reader untouched |
| `scripts/vnext/offline_execution_session.py` | process-local exact-object reuse and deterministic counters |
| `scripts/vnext/r4_fixture_authority.py` | separate versioned R4 fixture/scope loader; six metrics only |
| `scripts/vnext/r4_offline_qualification.py` | synthetic Candidates through existing Evidence, never a second verifier |
| `tools/qualify_r4_offline.py` | offline-only reproducible qualification/audit CLI |
| `tools/benchmark_r4_offline_session.py` | same-input/interpreter baseline and optimized comparison |
| `tools/acquire_r4_fixture_filings.py` | only if inventory proves need; existing SecHttpClient; maximum two filings |
| `config/r4_fixture_matrix_v1.json` | source-specific audited successor fixture authority |
| `config/release_plans/issue_28_r4_offline_v1.json` | six-metric successor plan, offline evidence only |
| `tests/vnext/test_source_scope.py` | scope identity and full tamper matrix |
| `tests/vnext/test_scoped_reader.py` | scoped transport/Candidate/Evidence replay negatives |
| `tests/vnext/test_offline_execution_session.py` | exact cache keys, mutation/crash/UNKNOWN boundaries and counters |
| `tests/vnext/test_r4_fixture_authority.py` | fixture/structured-first/classification/ReleasePlan gates |
| `tests/vnext/test_r4_offline_qualification.py` | complete offline source/task evidence integration |
| `tests/fixtures/vnext/r4_offline/**` | synthetic fixtures and audited source-specific manifests, not live credit |
| `docs/r4_offline/**` | B0 interfaces, inventory, audit/reconciliation, benchmark evidence and one-page summary |
| `docs/evidence/issue_28_transition_activation.json` | exact PR #29 activation receipt, unchanged content identity |
| `evidence/request_attempts/<new-content-hashes>/**` | conditional new BAC/Citi immutable attempts only; no old bytes edited |
| `evidence/r4_fixture_inputs/**` | conditional new working source/headers for the existing acquisition mechanism |
| `evidence/requests_log.csv` | conditional legal append only; exact old ordered prefix remains unchanged |
| `evidence/requests_log_manifest.json` | conditional existing-client ledger append manifest, not historical receipt re-signing |
| `AGENTS.md`, `architecture.md`, `interact.md`, `TESTING.md`, `SOP.md`, `capability_contract.json` | additive documentation/anchors for actually implemented offline behavior |
| `tools/run_fast_tests.py` | add short deterministic B0 smoke only; no timeout increase or old-case removal |

The map must be extended before editing an unlisted path. Existing ReaderInputManifest,
`build_reader_payload`, Evidence, legacy Run/publication schemas, provider opener,
and canonical/runtime semantics remain unchanged. New modules reuse those
implementations through explicit successor entrypoints.

## Evidence boundaries

B0 is an interface baseline, not production semantic freeze, a cycle, Stage-A,
qualification/live authority or a publication. PR-B provider/paid calls are zero.
SEC is zero unless existing-source inventory demonstrates the need for up to two
new immutable 10-K acquisitions. No automatic full-document fallback, archived
response reuse, real token measurement, R4 publication or PR-C work is allowed.
