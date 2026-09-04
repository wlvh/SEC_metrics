# PR-B R4 offline implementation — review evidence

> Historical offline report for rejected review head `f4158590336f65c44ba0916ada1b50af922ad44e`.
> These measurements and old identities remain historical evidence, not current
> rework acceptance. The new production seam is under validation; PR30 stays
> Draft and `issue_28_v2` is NOT_ACTIVATED. See `live_seam_rework_plan.md` and
> `live_seam_validation_attempts.json` for the rework boundary and failed probes.

This report concerns PR #30 only. Active publication remains R3. Offline
fixtures, synthetic Candidates and benchmark history earn no live qualification,
publication or archived-response reuse credit. PR stays Draft until independent
review; there is no PR-C execution or merge authorization.

## Identity and owner policy

- Base main: `c45338567700e3048f4cf32d251369e4521e9444`, tree
  `0b8ccaf6b6b708b2c07b8f4ce1d5dd178638493a`.
- Proposal: `issue_28_v2`, state **NOT_ACTIVATED**, engine `PROFILE_DRIVEN_V3`.
- Closure: `sha256:1fd51438196661964d51a8b37d270d05804ac04fd178f599a18f84a80a4d567a`.
- Parent/supersedes: activated `issue_28_v1`, closure
  `sha256:08994b0aa3324511ce655958fbe3c48fdcd873fa2d63a9bfe4de573046d519ac`.
- Exact policy comments: [A12/A13/resources](https://github.com/wlvh/SEC_metrics/issues/28#issuecomment-5524085182)
  and [A03 scope/disclosed quarter](https://github.com/wlvh/SEC_metrics/issues/28#issuecomment-5524746204).
  Captures retain real `wlvh` author, UTC time, full body and SHA; authorized
  agent posting is explicit. Neither is a v2 activation or live grant.
- Issue #28 body remains byte-identical to the frozen v1 evidence (SHA-256
  `d3ece2313923faa1e8f30177550675c47c3df442c9d3d880d33db5a98d8dfd6f`).

The five-file revision binds 54 current execution inputs. All 622 parent
semantic fragments have exactly one disposition: 619 CARRY_FORWARD and three
SUPERSEDED fields belonging to the unconditional D-32 scope obligation. Its
default same-table rule remains, with only the approved A03/A12 dimensions
excepted. V1/V2 engines and old snapshot bytes are not changed. Test-only
revision evolution proves the Requirement number can advance without changing
engine generation, while old v2 artifacts retain their original closure.

## Exact R4 plan and corpus

`config/release_plans/issue_28_r4_offline_v2.json` was built, persisted and loaded
by the real successor ReleasePlan entrypoints. Its content ID is
`sha256:c8ff936b7f7274cf0eff2cbb75852da2bfe053f81524cba51dd7d9f23d395098`.
It adds **A03 A04 A09 A11 A12 A13** to the exact R3 predecessor plan, resulting
in 30 cumulative metrics / 300 planned keys. B06/B13 are absent. It is a plan,
not migrated results or permission to publish.

The final [16-case index](qualified_cases/index.json), ID
`sha256:c14d191b0666e467ae809298d2411e95fe21bb73f072e646c7183d088b7356c2`,
binds 46 case artifacts and the same v2 closure. It records nine scoped native
Evidence PASS results, three structured-primary successes and four zero-call
classifications. [The source/task audit](current_source_task_audit.md) gives all
12 production/alternate values, original locators, source identities, legacy
reconciliation, no-anchor navigation and outside-window dispositions.

- A03 Citi is **2025Q4**, never an annual average. Approved entity/aggregation
  scope comes from exact associated same-source spans.
- A09 ratio is source-bound to the separate percent marker. Native structured
  ambiguity occurs for JPM; BAC's direct 0.0049 resolves before AI fallback.
- A11/A12 scale comes from original same-table headers. BAC A12 total VaR 34m
  is distinguished from its 32m trading component; it does not assert identical
  issuer portfolio composition or VaR methodology.
- A13 is direct consolidated international **net revenue**, not net income.
  Both selected issuers have direct totals. The optional regional-sum branch
  is **NOT_IMPLEMENTED / NOT_NEEDED_BY_CURRENT_CASES**; no sum credit is claimed.
- All four zero-call classes are present: NEGATIVE_EXPECTED, NOT_APPLICABLE,
  QUALITATIVE_ONLY and AMBIGUOUS_EXCLUDED. Structured positives also remain
  zero-provider: positive classification alone never grants a call.

SourceScope binds the full original asset, task/closure, original ordered
table/grid identities, one or two continuous windows, checked target/reference,
token estimate, navigation/material-layout proof and all declared outside
candidates. Complete-artifact negatives reject identity deletion/partial fields,
reordering/overlap/range drift, source/task/asset drift, altered references or
recipes, native-valid wrong cells, span/section/quarter drift, competing scope
conflicts and malformed/rebound attempt/index data. Audit answers and narrative
spans never enter the table-only provider payload.

## Acquisitions and resource parity

Whole PR-B provider/paid/SEC accounting is **0/0/2**. Both permitted native
acquisitions are already complete; every subsequent offline command is 0/0/0.
The exact old 981-row ledger is a prefix of the current 983-row ledger.

| Filing | Exact accession | Immutable native attempt |
|---|---|---|
| BAC FY2025 | `0000070858-26-000157` | `request:attempt:e531f356a6a06facbfbf9d3dc506144e80c80d3a0e46909772f80d420727eed6` |
| Citi FY2025 | `0000831001-26-000011` | `request:attempt:2ca17e95050d85613ce264edcd8d1c05bd0aa8e39f00adcfa3d786e925defa95` |

Both are HTTP 200 / retry zero; [acquisition receipt](fixture_acquisition_receipt.json)
pins body/header/ledger identity. The configured native preflight works without
an export; the contact is not repeated in this report. The actual acquisition
entrypoint now rejects the consumed source before native fetch/socket.

Production `max_total_cells=210000` is the smallest 10000-rounded limit above
the measured maximum 200229, with 4.88% headroom; the approved ceiling is 250000.
All other limits are unchanged, cap passes/cap+1 fails, and there is no caller
or worker override. [Final production parity](performance_resource_final_parity.json)
preserves all three complete asset byte identities under 512 MiB/no-swap/
network-none; measurements and entry counters are separate from host-side
aggregate performance and do not claim a host cgroup.

| Source | Raw / expanded cells | Tables | Final cgroup peak bytes |
|---|---:|---:|---:|
| JPM | 60348 / 124761 | 679 | 327294976 |
| BAC | 78980 / 200229 | 369 | 383307776 |
| Citi | 54404 / 95463 | 330 | 257863680 |

## Aggregate benchmark and final independent disk replay

Status: **PASSED**, measured aggregate improvement **21.789879×**. This is the
whole 16-case workload, not the earlier component diagnostic.

The [method](performance_benchmark_method.md) compares the same unique real
16-case inputs/interpreter, with six exact base-main prior terminal Runs. The
session constructs each source/asset/authority once, and full prior Run/source/
asset/authority construction is zero per child. A private canonical-byte graph
is deserialized once at setup; that real work is counted, not renamed away.
Baseline and optimized results must match one fresh-process independent disk
replay; that replay's measured cost is included equally in both denominators.
No general or persistent cache is used.

```bash
PYTHONDONTWRITEBYTECODE=1 python3 tools/qualify_r4_offline.py --write
PYTHONDONTWRITEBYTECODE=1 python3 tools/benchmark_r4_offline_session.py \
  --benchmark --requirement-id issue_28_v2 \
  --requirement-closure sha256:1fd51438196661964d51a8b37d270d05804ac04fd178f599a18f84a80a4d567a \
  --output docs/r4_offline/performance_session_final.json
```

The generator is offline fixture construction, not a final replay. The final
benchmark command returned rc0 and performed exactly one final fresh disk
replay; it was not rerun to improve the measured time. The content-addressed
[receipt](performance_session_benchmark.json) is
`sha256:190390eef384cebdb76e4f8e2b93e018005287cea96f61453e309c3a1b0b6eee`;
its exact stdout and full counter analysis are retained beside it.

| Measured component | Seconds |
|---|---:|
| Unoptimized process | 2782.458871 |
| Optimized process | 65.164900 |
| One independent final disk replay | 65.537831 |
| Baseline aggregate including final replay | 2847.996702 |
| Optimized aggregate including final replay | 130.702731 |

The three distinct processes produced the identical semantic result-set ID
`sha256:d3f5e700b3d65b8627af49d06d457c9b896929ad92b02ce29518fb2d6b07830a`.
Each optimized/final current-source session constructs the source/asset,
ownership graph and each Requirement layer once; every child has zero full
source/asset/Requirement construction, prior-Run replay, asset deserialization
or XBRL parse. Whole-process peak RSS is 2334113792 / 1735196672 / 1853308928
bytes. This does not enlarge the separate 512 MiB parser-worker claim.

## Validation record

All commands run with `PYTHONDONTWRITEBYTECODE=1`; unittest commands additionally
set `PYTHONPATH=scripts`. Empty stdout plus unittest `OK` is a test PASS, not a
live grant. Detailed final validation and exact-head GitHub CI are recorded on
PR #30 after the final commit; the report never self-references its own Git SHA.

The final source/recipe generation returned rc0 in **61.53s**. Source/task tests
returned **20/20 PASS, 17.600s**. Legacy authority/router/Evidence/schema/Reader/
locator/SEC identity tests returned **75/75 PASS, 77.757s**. Final v2 plus
source/fixture integration returned **34/34 PASS,26.461s**; the two real
public-entrypoint financial/quota negatives are included, with opener/fetch/
socket counts zero. The recorded benchmark receipt/log check returned **2/2
PASS,0.059s** and did not execute another replay. Full transition/rework/
publication regression returned **101/101 PASS,893.688s**, with no failures,
errors or skips. Final R3/R2/R1 and14-mirror read-back returned **1/1
PASS,38.706s**. Fast returned **24/24 PASS,8.570s**, with the unchanged 30s
per-entry cap.

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_issue28_requirement_transition tests.vnext.test_issue28_rework tests.vnext.test_publication
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_issue15_authority tests.vnext.test_source_strategy_registry tests.vnext.test_deterministic_router tests.vnext.test_evidence_checker tests.vnext.test_record_schemas tests.vnext.test_reader_input_manifest tests.vnext.test_table_grid_locator tests.vnext.test_sec_identity
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_issue28_v2 tests.vnext.test_source_scope tests.vnext.test_scoped_reader tests.vnext.test_composite_scope tests.vnext.test_offline_execution_session tests.vnext.test_table_stage_c_financial_materialization
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_r4_fixture_authority tests.vnext.test_r4_offline_qualification
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_issue28_v2.Issue28V2OfflineGovernanceTest
PYTHONDONTWRITEBYTECODE=1 python3 tools/run_fast_tests.py --jobs 4
PYTHONDONTWRITEBYTECODE=1 python3 tools/check_provider_egress.py --output docs/r4_offline/provider_egress_gate.json
PYTHONDONTWRITEBYTECODE=1 python3 tools/check_vnext_semantics.py --output docs/r4_offline/semantic_audit.json
PYTHONDONTWRITEBYTECODE=1 python3 tools/check_no_company_literals.py --output docs/r4_offline/scalability_audit.csv
```

All three static commands returned rc0 / PASS. Final provider gate
`sha256:ac546e0973915737bfe6a708681d041512d76cc532aff9b586905b39e1fe351d`
scans 119 files and retains the same sole opener/call-graph contract. Their
outputs are new offline audit files; historical semantic/scalability receipts
were not rewritten. [History preservation](history_preservation.json) records
zero protected-path changes and exact ledger-prefix evidence. The only changed
immutable request-attempt paths are the two new bodies and their two headers;
there are no modified/deleted old attempts.

Earlier diagnostic failures are not hidden: publication tests found two
hardcoded fiscal dates, now replaced by native DEI/context-derived dates; a
test-only V2 evolution destination collided with the new real v2 and now uses
an unused revision ID without overwriting history. A too-early corpus test saw
the prior index during regeneration; it was rerun after final generation.
Three guessed module names were invocation errors, not test PASS. These do not
authorize changing native gates, R1–R3 artifacts or any freeze.

## Preserved history and final gate

R3 remains `publication_4f2542a2e74de50e2e005d787a7edd57cbf587697593e4f3b74a59a81a684cc8`,
with exact R2 `publication_fe01e227848d6a4212318b4942742d06b0a2861df55e0b268df2062a441c438f`.
Formal historical integration replays R3/R2/R1, R3 PASSED index and all 14 root
mirrors. The arbitrary-nonempty-token financial probe rejects at
`TABLE_QUALIFICATION_NOT_AUTHORIZED`, instrumented provider/socket counts zero.

No historical R1–R3 / issue15 / issue28v1 / retained V1/V2 bytes, publication
pointer, root mirror, cycle/freeze/Stage-A or archived response was modified.
There are zero financial Runs and no added formal runtime paths in the worktree.
Ordinary source/config/catalog/test/docs diff-check must pass. Generic whitespace
in immutable evidence is N/A; those bytes are checked by hashes/read-back, not
reformatted. PR22 archive remains historical-only with no response reuse.

PR #30 stays Draft; Issue #28 stays open; v2 activation, Ready, merge and PR-C
remain separate owner/reviewer actions after complete offline evidence.
