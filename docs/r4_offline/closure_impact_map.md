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
- Retained V2 evolution harness; historical Issue #15 snapshot bytes stay fixed.

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
| `scripts/vnext/r4_source_audit.py` | deterministic source-specific audit/navigation records, never runtime discovery |
| `scripts/vnext/r4_materialization.py` | additive offline full-grid resource boundary; no legacy budget mutation |
| `tools/qualify_r4_offline.py` | offline-only reproducible qualification/audit CLI |
| `tools/audit_r4_sources.py` | offline source inventory and two-path audit CLI |
| `tools/benchmark_r4_offline_session.py` | same-input/interpreter baseline and optimized comparison |
| `tools/r4_materialization_worker.py` | if required, isolated hard-guarded full-source worker; not live authority |
| `tools/acquire_r4_fixture_filings.py` | only if inventory proves need; existing SecHttpClient; maximum two filings |
| `config/r4_fixture_matrix_v1.json` | source-specific audited successor fixture authority |
| `config/r4_fixture_acquisitions_v1.json` | two permitted future filing identities; locator metadata only, no qualification credit |
| `config/release_plans/issue_28_r4_offline_v1.json` | six-metric successor plan, offline evidence only |
| `tests/vnext/test_source_scope.py` | scope identity and full tamper matrix |
| `tests/vnext/r4_b0_fixture_support.py` | small complete-file synthetic B0 fixture, using the real A03 task/Evidence path |
| `tests/vnext/test_scoped_reader.py` | scoped transport/Candidate/Evidence replay negatives |
| `tests/vnext/test_offline_execution_session.py` | exact cache keys, mutation/crash/UNKNOWN boundaries and counters |
| `tests/vnext/test_r4_fixture_authority.py` | fixture/structured-first/classification/ReleasePlan gates |
| `tests/vnext/test_r4_offline_qualification.py` | complete offline source/task evidence integration |
| `tests/vnext/test_r4_fixture_acquisitions.py` | exact quota/source/retry/identity and pre-egress failure tests |
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

## Owner-approved PR-B continuation (policy comment 5524085182)

The owner requested the exact policy JSON be posted through the owner account;
`docs/evidence/issue_28_prb_policy_revision.json` retains the verified URL,
author, timestamps and exact body hash. This is policy-content approval only.

- B remains immutable: `requirements/issue_28_v1/**` and retained V1/V2 engines.
- Add `requirements/issue_28_v2/**` (five files), a new versioned profile engine,
  registry dispatch and revision tests. The revision stays NOT_ACTIVATED.
- Add generic source-bound composite scope support for A12 only; update
  `source_scope.py`, `scoped_reader.py`, and the existing Reader/Evidence/record
  validation paths only where successor evidence requires it. Legacy behavior
  stays unchanged. New modules/tests cover all source/span/section conflicts.
- Exact successor additions: `scripts/vnext/composite_scope.py`,
  `tests/vnext/test_composite_scope.py`; successor-only extensions may touch
  `scripts/vnext/evidence.py`, `reader.py`, `scope_contract.py`, `records.py`
  and their schemas/tests, without weakening any legacy path.
- `scripts/vnext/table_grid.py` may factor native locator checks into a shared
  internal function used by an explicit immutable session context; normal
  callers keep full validation. The context cannot skip path/hash/size drift
  or final independent disk replay, and v2 binds the implementation bytes.
- `scripts/vnext/r4_task_contracts.py`, `config/r4_task_contracts_v2.json`,
  `config/r4_numeric_normalization_v1.json`, `catalog/r4_v2/**`,
  `config/r4_fixture_matrix_v1.json`, `scripts/vnext/r4_fixture_authority.py`
  and their tests provide additive successor task/fixture authority.
- `scripts/vnext/r4_structured_sources.py` and a narrow explicit-subtype
  dispatch in `deterministic_router.py` reuse native accession-XBRL for an
  owner-pinned single-filing fixture, without inventing submissions inventory
  or changing the normal production SourceSetManifest validator.
- Add versioned R4 fixture/scope and economic-measure authority, source audit,
  qualification/replay tools and tests. If a C path needs a change it binds v2,
  never a rewritten v1; prefer additive task/policy files.
- Exact authority additions: `scripts/vnext/requirement_profile_v3.py`,
  `requirements/issue_28_v2/{CONTRACT.md,decision_register.json,invariant_profile.json,transfer_manifest.json,baseline_manifest.json}`,
  `tests/vnext/test_issue28_v2.py`, `tools/create_issue28_v2_snapshot.py`;
  only registry dispatch changes in `requirement_profile.py`.
- Exact acquisition additions: `tools/acquire_r4_fixture_filings.py`,
  `tests/vnext/test_r4_fixture_acquisitions.py` and
  `docs/evidence/issue_28_prb_policy_revision.json`.
- `resource_limits.py` may change only max_total_cells, after measuring all
  three sources, with an absolute ceiling of 250000. Worker/session/benchmark
  code and tests change to use the identical production parser without an
  override. Other resource limits and SEMANTIC_VERSIONS remain unchanged.
- Add the two planned BAC/Citi immutable requests through the native client,
  retry zero, preserving the existing ledger's exact ordered prefix. New
  request attempts and acquisition/measurement/offline evidence are additive.
- `config/sec_config.json`, `scripts/sec_http.py`, the historical producer
  inventory check and associated tests/docs have the separately approved
  automatic-contact-reading correction; no historical snapshot bytes change.

Owner-authorized SEC configuration simplification: `config/sec_config.json`
and `scripts/sec_http.py` provide a default contact, overridden by the environment.
`scripts/vnext/requirements.py` checks the frozen producer-source bindings, not
current transport bytes; current execution/freeze authority checks stay intact.
Existing identity tests and the operational docs are updated to match.

B0 is an interface baseline, not production semantic freeze, a cycle, Stage-A,
qualification/live authority or a publication. PR-B provider/paid calls are zero.
SEC is zero unless existing-source inventory demonstrates the need for up to two
new immutable 10-K acquisitions. No automatic full-document fallback, archived
response reuse, real token measurement, R4 publication or PR-C work is allowed.
