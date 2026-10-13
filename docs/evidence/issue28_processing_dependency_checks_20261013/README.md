# Processing dependencies: actual code changes cannot reuse an unchecked result

Responds to receiver [6127226798](https://github.com/wlvh/SEC_metrics/issues/28#issuecomment-6127226798).
Actual base main: `2f756660f26438faf368ae760728e1442ecd1c41`.
Code root: `/Users/lyuhongwang/.codex/worktrees/issue28-b06-text-dependency/SEC_metrics`.
Saved source root: `/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs`.
This new short branch reuses the clean, completed PR198 worktree. Original
branches, programs, sources, responses and ledger files are retained.

## Reproduced cause and actual change

The existing configuration omitted files actually called by business
preparation. `b04-before-trace.json` independently observes `text_coverage`,
`text_results_v2`, `normal_governance_input` and `paired_measure_v1` in actual
B04 preparation, despite none being hashed. The paired check's scope is
broader than the receiver's first table: the CompanyFacts component factory
executes it while preparing B04 as well. `b01-before-trace.json` independently
observes its missing shared readers, `historical_dei` and `constraints`.

The existing configuration now names the actual shared annual readers,
CompanyFacts comparison guard and B01/B03 source dependencies. Current B06
and current D01 declarations add their specific actual helpers. Historical
D01's separate declaration remains #47's PR204; this branch does not edit it.
No business definition, count/permission rule, old result or source is changed.

`tests/vnext/processing_dependency_checks.py` provides one reusable **test-side**
function-call observer and compares actual executed `scripts/vnext` modules
with effective configuration plus explicit consumer declarations. It restores
existing profilers, includes nested calls and fails on undeclared modules.
Only the two existing check-before-reuse files are explicit exceptions:
`ordinary_current_update` and `request_bindings`. Unknown files are not exempt.
It is not runtime file-access auditing, recursive import inference, a new
approval store or a fallback that ignores hashes.

## Executed checks

- `before-small.log`: mechanical guard and update behavior fail before repair.
- `after-small.log`: six small tests exercise real offset/comparison code,
  complete constructed D01 candidate/evidence/review/result, explicit consumer
  declarations, a deliberately removed used dependency, and profiler recovery.
  No imported TestCase is unintentionally run twice.
- `material.log`: the same shared observer executes two real saved annual
  B01/B04 factories using the existing repository material/independent-input
  boundary: 14.432s, passed. This is a material-layer selector, not a fast
  whole-company installation or a cached prior green result.
- `after-real-trace.json`: independently read saved acquired source, B01
  1,472,985,000 USD / 38 executed modules and B04 172,133,000 USD / 25 modules,
  no undeclared module in either actual path after repair.
- `final-targeted.log`: 142 required controls in 8.877s, zero skip/error/failure,
  including target registry, isolated D04 changes, current B06/D01 and ordinary
  update/company state behavior.

The prior D01 test required exact equality to an earlier intentionally limited
configuration. `prior-default-expectation-failure.log` retains the four actual
failures. The updated test still compares all non-version business fields,
every preexisting processing digest and no removed dependency; only the named
new source dependencies may differ. It keeps omitted/None producer defaults
and period/registry/source context unchanged, without pretending the missing
old dependency set was complete.

## Actual company entry and recovery

`verify_company.py` uses the formal company CLI with read-only acquired source
and one fresh isolated Enphase B04 state. Initial uncached `first.json` completed
in 2.763829s with actual FY2025 2025-01-01..2025-12-31, 172,133,000 USD,
result `c1fa7ca38cf3908865d26ea99265bbdb9ac7626fa2e1586d63541657a310f2cf`.
Then the test changes only the parser version observed by the real configuration.
The final failure injection is at the actual factory entry, so it proves code
changes do not bypass processing and failed processing preserves old success.
It does **not** claim that an in-memory parser patch is a changed installed file.
Real parser execution is separately proved by the two observers above.

Three retained first probe logs show test-injection mistakes rather than false
passes: replacing a module attribute did not replace a reader's imported
function reference; subsequent parser-code probes still did not establish the
intended CLI failure. Those attempts actually recalculated and their original
state/result directories remain. The corrected probe safely resumes that
state and reports its scope explicitly; it does not delete failed attempts or
mislabel the resumed first check as uncached.

`company.json`: resumed check 0.191834s, no calculation; changed parser-version
plus factory-entry failure 0.131830s; real recovery 2.776480s; factory-forbidden
repeat 0.133666s, no calculation; independent `results`/CSV read 0.113545s.
All 42 preexisting result files remain after the controlled failure. The old
successful source/value/period/result identity remains readable. Current
failure does not serve it as a newly passed source check. New calls 0/0/0.
Only test version selection and failure injection are substituted; preparation,
calculation, save and independent reading run their real implementation.

Run small checks with `PYTHONPATH=scripts:tools:. python3 tests/required_unittests.py
tests.vnext.test_processing_dependency_checks`; material checks with the same
runner and `tests.vnext.test_processing_dependency_material`. The documented
CLI driver accepts `--source-root`, a new `--state-root`, `--output-root` and
`--receipt`; `--resume` is only for its retained local development state.

## Coverage boundary

The reusable guard is wired into quick/current CI; the real-factory selector
is wired into the existing material layer. This first bounded sample is not
an exhaustive proof of every function or branch of 39 indicators. Other
consumers can apply the same helper to their existing material tests, without
another controller/checker or no-progress repeated company runs. Supported
actual branches, not imported-but-unused modules, are the observation unit;
non-Python policy/config files retain the existing explicit declarations.

Tests used the stated base plus this working-tree change. The subsequent
commit records the tested bytes; its future SHA was not claimed at execution
time. Remote head/tree equality and CI are tracked separately. No new SEC,
provider or paid calls; no old ledger/root reset, frozen-run signing, adoption,
Ready, merge, deployment or active switch.


## Returned receiving increment: actual A13 and current main

Actual feedback6130757933 was read. The same observer on the complete saved JPM A13 factory reproduces precisely the missing scope_contract module: validate_scope_contract, scope_satisfies_contract and scope_contract_hash really execute; a13-before.log is red28.511s. Add scope_contract to current_geography_case.PROCESSING_FILES only. a13-after.log28.482s verifies the complete real factory and a deliberately removed effective dependency must still fail. No factory/parser success mock or invented result.

The configuration control also proves this relevant scope rule change changes A13 configuration while unrelated B01 remains reusable. Current main31e4 is normally merged: only two adjacent workflow/runner append sections conflict, resolved as a union preserving cover/single-segment/processing fast selectors, processing source material, and every explicit step. Function bodies and timeouts unchanged; Python AST and Ruby YAML actually checked. a13-main-controls.log:88 tests0.944s, zero skip; a13-main-material.log:2 tests44.846s, combining the existing EnphaseB01/B04 factories with real JPM A13. Original source/CLI B04 evidence is reused only for unchanged responsibilities; no repeat of the large company chain.

Historical average-risk declarations/tests are owned by the historical agent; no parallel core or edits to its workspace. The receiver's trace of other current metrics is read evidence, not a claim this author independently repeated all of it. E01 was not covered by that receiver probe. This increment does not turn module coverage into complete business acceptance. Actual tested main-merge HEAD is e56ba5aa with only output logs/docs uncommitted; subsequent evidence commit preserves those production/test bytes. New public head/tree are in the PR reply; old8ef green does not certify the new head. 0/0/0 new business calls; no body write to project receivingIssue153.

## E01 receiving scope completed with the existing content consumer

Consumed the exact stable test file from peer ed28dd3dfd3152479ab20bff7741927e769c556c, only one new method and pathlib import. Local copied file hash568e9cf90e3c5a64f12fc119ba4c8dde3a938018 is identical. The explicit required company-history CI step already runs the complete module; the generic fast-selector list does not include it. No new runner, selector or production change. e01-receiving-controls.log: public executor independently ran27 required tests0.156s, zero skips. The real content-confirmation adapter is observed for missing answer/attachment/successor conditions and existing constructed complete-walk zero; removing the called confirmation dependency causes a failure. This resolves the receiver's wrong-entry validation gap, not a new E01 business result.

The [peer source record](https://github.com/wlvh/SEC_metrics/blob/ed28dd3dfd3152479ab20bff7741927e769c556c/docs/evidence/issue47_e01_dependency_consumer_20261013/README.md) was actually read: SouthwestFY2024 factory28.275s,33 executed modules declared, six-candidate request exactly matches original34507016,29806686 remains null for absent matching answer. That material execution belongs to the historical executor; it was not repeated or relabelled as public execution. Existing save/repeat/read evidence is reused at its original scope. All public production, configs and earlier material/CLI files remain byte-identical to fixed207d65. Tests ran on local5e137990 plus this one test difference before the evidence commit; no future commit/CI success is asserted.
