# PR #29 authority rework audit

## Rejected candidate and reproduced defects

The owner rejected head `3973ef94d950093270df27110a17c317075cf413` and closure
`sha256:5b14c4d8d4cfa2381adc6f48568d538818110bd82c206f59209bf96ab3789549`.
They must not be offered for transition approval.

At that exact source, temporary register mutations followed by outer file
rebinding incorrectly accepted: removed R4 metric, hard cap 25, target 11–19,
removed zero-call class, context 200001 and 1x improvement. The legacy helper
accepted a real R3 manifest with the wrong Requirement and with bogus hashes.
Changing only a temporary root catalog invalidated the successor parent load.
The earlier fast/helper tests did not cover these authority boundaries.
The expanded matrix also reproduced removal of the AI-selector prohibition
and coordinated addition of a non-approved positive fixture class; V1 now
rejects both, even after all outer snapshot bindings are updated.

The first complete publication regression also rejected adding successor
parameters to the legacy `prepare_publication_bundle` signature. Its existing
negative test is unchanged: the fix restores that exact public signature and
adds `prepare_successor_publication_bundle`, sharing the internal verifier.
Neither public entrypoint accepts caller ledger/provider/validation overrides.

## Defect-to-test ledger

| Review item | Reworked mechanism | Evidence |
|---|---|---|
| Artifact downgrade | Distinct successor subtype plus required generation and full triple; generation is content/audit bound | Real Run build/freeze/replay, full ReleasePlan file round-trip, full recorded publication bundle; each rejects removal of 1/2/3 identity fields or generation |
| Legacy identity | Exact selected-historical hashes; old Issue #15 ReleasePlan remains its own subtype | Actual R3 wrong-Requirement/bogus-hash negatives; all `config/release_plans/issue_15_*.json` remain loadable |
| Engine/revision evolution | Retained V1/V2 engines, explicit dependencies and prior revision closure | V2 adds R5 policy and approves pending meaning; independent R4/R5 instances of scope, calls, source and predecessor; old V1 artifacts retain old closure |
| Semantic transfer | Exact source record/path/value hash for each leaf obligation, with typed target | 477/477 unique fragments; D-24 false cannot be redirected to an unrelated false artifact-identity flag |
| Stable bounds | Small closed typed validators enforce bounds; policy content is not mirrored wholesale | Rebound policy mutation matrix, each required SourceScopeManifest field, missing/weak test policy; explicit owner provider tip positive |
| Approval provenance | Recorded Issue text or original parent Decision, original author/time, content hash | Identifier-comment substitution fails; separate exact-head activation validates approval text/head/closure and grants no live execution |
| Historical parent independence | Reconstruct parent from recorded hash map and frozen snapshot bytes | Live Issue #15 adapter is instrumented to throw; parent still loads, R1–R3/14 mirrors survive root drift, old execution rejects drift and a new revision uses its own inputs |

## Transfer interpretation

There are 189 `CARRY_FORWARD`, 278 `HISTORICAL_ONLY`, and 10 `SUPERSEDED`
fragments. A count alone is not the proof: the evaluator independently walks
every effective parent choice leaf and compares the complete source-key set.

- D-01's 11 transport/endpoint/timeout/payload/filing-egress/privacy-claim fields
  map to `S-PROVIDER-TRANSPORT`, with original parent approval provenance.
- D-24's two dependency-call-graph/honest-sandbox claims map to
  `S-SECURITY-BOUNDARY`, not artifact identity.
- D-26's 25 leaf obligations map to `S-TEST-POLICY`, preserving its exact fast
  command, timeouts, test-class boundaries and `FAST_LOCAL_ONLY` semantics.
- General result/evidence/scope/coverage/compatibility obligations are carried
  by immutable references in `S-INHERITED-SEMANTICS`; they are not collapsed
  into unrelated booleans or copied into Python.
- Lodging-specific grants, attestation/sample/ordinal/prompt history and method
  terms remain historical. Full-document admission, successor retry allowance
  and old family-sampling/response-reuse policies are explicitly replaced.
- PR #22 failed cycles, full-document plans, responses, terminals and old grants
  remain five separate historical material classes with no credit/reuse.

## Exact targeted commands

Run with `PYTHONDONTWRITEBYTECODE=1`; unittest commands also use
`PYTHONPATH=scripts`. Tests write only system temporary fixtures.

```bash
python3 tools/run_fast_tests.py --jobs 4
python3 -m unittest -v tests.vnext.test_issue28_requirement_transition
python3 -m unittest -v tests.vnext.test_issue28_rework
python3 -m unittest -v tests.vnext.test_record_schemas tests.vnext.test_requirement_baseline tests.vnext.test_replay
python3 -m unittest -v tests.vnext.test_issue15_authority
python3 -m unittest -v tests.vnext.test_source_strategy_registry
python3 -m unittest -v tests.vnext.test_publication
python3 -m unittest -v tests.vnext.test_ratchet_release.RatchetReleaseTest.test_formal_active_r3_keeps_exact_r2_predecessor
python3 -m unittest -v tests.vnext.test_table_context_qualification_guard
python3 tools/check_provider_egress.py --output /tmp/pr29_rework_provider_graph.json
python3 tools/check_vnext_semantics.py --output /tmp/pr29_rework_semantic.json
python3 tools/check_no_company_literals.py --output /tmp/pr29_rework_scalability.csv
python3 tools/check_capability_contract_alignment.py --base-ref origin/main
git diff --check origin/main...HEAD
git diff --name-only origin/main...HEAD -- requirements/issue_15_v1 requirements/ai_first_v3_3_1 outputs artifacts evidence config catalog
git status --short
git diff --stat origin/main...HEAD
```

Historical content-addressed artifacts are never reformatted for a whitespace
gate. No live provider, paid endpoint or SEC request is part of these checks.
Local/CI fast PASS is not full acceptance or transition activation.
