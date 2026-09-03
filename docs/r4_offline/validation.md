# PR-B initial bounded implementation validation (3404f5d)

The results below record the earlier pre-acquisition implementation, not the
current continuation. See [current summary](README.md) for the two new SEC
attempts, approved A03/A12/A13/resource policy and its separate validation.

These are implementation/audit results, not completed R4 offline qualification.
The owner escalation is in `owner_decision_request.md`. No timeout was raised,
historical receipt regenerated, or negative fixture relabeled as positive.

## Actual final local runs

All commands ran in the PR-B worktree with `PYTHONDONTWRITEBYTECODE=1`.
Unittest commands also used `PYTHONPATH=scripts`. Wall time was measured by
`/usr/bin/time -p`; stdout/stderr were captured by the execution host.

| Exact command | rc | Result | Wall |
|---|---:|---|---:|
| `python3 -m unittest -v tests.vnext.test_source_scope tests.vnext.test_scoped_reader tests.vnext.test_offline_execution_session tests.vnext.test_r4_offline_qualification` | 0 | 39/39 PASS | 4.02s |
| `python3 -m unittest -q tests.vnext.test_reader_input_manifest tests.vnext.test_evidence_checker tests.vnext.test_record_schemas tests.vnext.test_source_strategy_registry tests.vnext.test_replay` | 0 | 82/82 PASS | 47.67s |
| `python3 tools/run_fast_tests.py --jobs 4` | 0 | 23/23 PASS; runner8.362s, cap30s unchanged | 8.40s |
| `python3 -m unittest -q tests.vnext.test_issue28_requirement_transition.Issue28HistoricalReadBackIntegrationTest` | 0 | R1/R2/R3 native read-back, R3 PASSED index, exact predecessor and14mirrors PASS | 39.38s |
| `python3 tools/check_provider_egress.py --output <external-audit-dir>/final-provider-gate.json` | 0 | PASS; allowed callsites unchanged;110files | 0.65s |
| `python3 tools/check_vnext_semantics.py --output <external-audit-dir>/final-semantic-gate.json` | 0 | PASS | 0.42s |

Unittest stdout was empty; stderr ended in `OK`. Fast stdout was `PASSED` JSON
with every per-entry return code0. Static scans reported PASS. Those results
are not a live grant or a six-task qualification result.

Provider gate ID:
`sha256:974824579f525a70a5318736971d741bd4453378785a22f4f99b4eb5d3172813`.
The historical read-back required only the existing ignored zero-byte
`outputs/active_publication.json.lock`; it is not committed.

## Exact plan and authority

The real `build_successor_release_plan` produced
`config/release_plans/issue_28_r4_offline_v1.json`. The real
`load_release_plan_artifact` reopened it with rc0. Assertions required exact
added set `[A03,A04,A09,A11,A12,A13]`, 300 cumulative planned keys, and absence
of B06/B13 from the cumulative metric set. Its parent is `issue_15_lodging_r3`.
No active plan index or publication pointer was changed.

`git diff --exit-code c45338567700e3048f4cf32d251369e4521e9444 -- requirements scripts/vnext/requirement_profile_v1.py scripts/vnext/requirement_profile_v2.py scripts/vnext/canonical.py scripts/vnext/reader_input.py scripts/vnext/evidence.py scripts/vnext/resource_limits.py catalog artifacts outputs evidence config/company_registry.csv config/metric_applicability.yaml config/provider_model_runtime.json config/source_strategy_registry.json config/table_qualification_matrix.json config/issue_15_release_plan.json config/release_plans/issue_15_lodging_r3.json config/release_plans/issue_15_zero_ai_r1.json config/release_plans/issue_15_zero_ai_r2.json REPORT_十公司财务指标.md README_RUN.md`

returned0 with empty output. All historical evidence and all v1 execution-
authority inputs remain byte-identical. `git diff --check` returned0; immutable
artifact generic whitespace is N/A because those bytes were not changed.

Issue #28 body was re-read from GitHub after its single PR-B status comment:
8,597 bytes, SHA-256
`d3ece2313923faa1e8f30177550675c47c3df442c9d3d880d33db5a98d8dfd6f`, exactly
the frozen policy evidence. The PR#29 activation receipt revalidates with its
original ID. No Requirement revision was created or activated.

## Explicitly unmet gates

The existing-source inventory, real native Candidate/Evidence diagnostic,
structured-route ambiguity replay and guarded full materialization have their
own exact commands/results in `source_audit_summary.md` and `performance.md`.
They do not replace all six production/alternate fixture certificates,
A09/A13 no-anchor closure, full out-of-window closure, aggregate >=10x benchmark,
or final independent complete R4 disk replay. Those gates remain BLOCKED / NOT_RUN.

Provider/paid/SEC accounting is0/0/0. The native SEC preflight failed at
`SEC_CONTACT_EMAIL_REQUIRED` before any opener; the 981-row ledger remains
byte-identical and both conditional filing slots are unconsumed.
