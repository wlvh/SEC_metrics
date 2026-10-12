# Company E01 source preflight through the existing user entry

This #28 public increment extends `tools/vnext_company.py sources` to E01, alone or with B01/B02/B03, by using the existing #47 selected-year source consumer. It does not add an event selector, metric method, acquisition controller or model call. Source readiness and content-confirmed M&A acceptance are separate.

## Fixed implementation and actual integration

Base is received main `385991307f35bfbac771913de4d2ba4156ed7c95`. The earlier local dispatch staging commit `cce66220` and received-main merge `afe970eb` are not claims of public delivery or material acceptance. `tested-worktree.json` records the tested code blobs and working-tree relationship. Tests ran before the delivery commit; they are not retrospectively attributed to its future SHA.

The two historical implementation/test files are byte-exact consumers of #47 commit [`0549162a814fe8a70b7a4bce3367495c88868734`](https://github.com/wlvh/SEC_metrics/commit/0549162a814fe8a70b7a4bce3367495c88868734), respectively Git blobs `2fe76fc0da71b33327763af89ce10265ba8e3485` and `55a61ad2fee755c5670cfb5e10cc669010593b0a`. Its [source-phase record](https://github.com/wlvh/SEC_metrics/blob/0549162a814fe8a70b7a4bce3367495c88868734/docs/evidence/issue47_e01_source_context_20261013/README.md) remains the provider's execution evidence. No peer working directory, ledger or uncommitted code was copied; only the supplied source-phase implementation and associated tests were adopted. Public changes are CLI dispatch, selected-source composition and fiscal-range routing. Legacy B01/B02/B03-only calls keep their existing preparation and return object.

`collect_historical_e01_requirements` consumes the real top-level selected annual input and binds the same event walk/request as the existing metric factory. It registers actual annual/CompanyFacts/catalog proofs, event body/header and approved EX-99 dependencies through the existing source reader. It creates no Result, Trace, answer or count. Even complete zero-candidate source preparation leaves `complete_annual_count=null`.

## Actual saved-source CLI executions

The read-only material root is the already restored `SEC_metrics-issue47-sec-ledger-resume-20261006/source-inputs`. No additional restoration or acquisition was performed. `verify_sources_entry.py` uses the formal CLI, with sockets, business claim, both calculators and withheld-Result creation forbidden. Registry, request log and request-manifest SHA256 values are checked before/after in each output. Only diagnostic outputs are written to this evidence folder.

| Actual task | Formal return | Observed source requirements | Existing request identity | Elapsed |
|---|---|---:|---|---:|
| Southwest FY2024, E01 | exit0 / SAVED_SOURCE_BYTES_AVAILABLE | 41 | `34507016c9b8…` | 13.343s |
| Paramount predecessor FY2024, E01, after public fix | exit0 / SAVED_SOURCE_BYTES_AVAILABLE | 50, including already saved EX-99 | `2aa878ef4a04…` | 25.295s |
| Salesforce FY2021, E01, after precise missing-URL propagation | exit2 / SELECTED_SOURCE_DEPENDENCIES_UNRESOLVED | 3 verified rows plus 1 exact missing URL; graph incomplete | none | 4.676s |
| Southwest FY2024, B01 + E01, after public composition fix | exit0 / SAVED_SOURCE_BYTES_AVAILABLE | 43 distinct source URLs | unchanged `34507016c9b8…` | 13.739s |

These are elapsed observations for different tasks, not a speedup ratio. Southwest/Paramount IDs agree with the provider's recorded source/request identities, but this public execution does not reassign its prior model credit. Source graph completion is not an E01 count, a successful model response, SEC freshness, a complete company Result or production adoption. The output always keeps zero new calls, false execution/acceptance/authorization and null complete count.

Salesforce's exact missing original is `https://www.sec.gov/Archives/edgar/data/1108524/000110852420000008/crm-20200225.htm`. The existing reader's URL now appears in the limitation and unresolved set; no guessed media type, proof or complete event inventory is fabricated. Known-URL count includes this named blocker, not only rows already read. This incomplete graph is not a final acquisition budget.

## Failures preserved and minimal corrections

`before-controls.log` records the original CLI rejection and absent public wrapper. The first Paramount composition (`paramount-formal-sources.json/.log`) exposed a public bug: replacing the registered primary CIK with the selected annual reporter hid the primary catalog required to prove the predecessor. The new small regression fails before removal (`predecessor-context-before.log`). The plan retains its registry identity; only its document reader uses the selected reporter. Provider code remains unchanged. Actual after output restores both catalogs and the existing incorporated-source request.

The first mixed formal call failed at `COMPONENT_SOURCE_OBSERVATION_CHANGED`. `mixed-source-proof-comparison.json` independently compares actual annual preparation with the recorded E01 preflight: the sole discrepancy was the CompanyFacts proof's contextual accession (selected annual accession versus empty); URL, bytes and request identity matched. The public composer accepts only this contextual difference for the exact selected reporter's aggregate CompanyFacts URL, preserving the actual component proofs. Filing documents gain no such exception; different source bytes/request observations still reject. `southwest-mixed-formal-sources-after.json` is the final actual mixed-entry evidence.

An initial range-routing assertion failed because `/var` and resolved `/private/var` paths differ on macOS; `final-required-controls.log` preserves it. The test now checks the resolved source-root interface, without changing any business expectation. Initial imported fixture tests ran redundantly through module-level class discovery; the final test imports the fixture module and reuses preparation, avoiding duplicate suite execution. The old logs are retained as their actual scopes, not added to a claimed final count.

`final-combined-controls.log`: **102 required source/range/E01/incorporated-source/response-contract tests, 3.259s, zero skips**. They preserve the original E01 controls and add nonempty source routing, source-only empty count, predecessor catalog identity, exact missing/unresolved handling, event-only preparation, mixed component retention, CompanyFacts sharing and nonsharing counterexamples. Constructed tests are labeled and do not establish model accuracy. Full saved-source positive runs preceded the final diagnostic URL/CompanyFacts-only composition changes where those branches are unused; their unchanged responsibility is reused. The mixed run exercised those final changes. No old D04/company cold-read chains or historical full surveys were repeated.

The new public tests are explicitly selected by the current-company workflow and appended to the existing fast list. Public reception/remote CI are separate from these local results.

## Reproduce

```sh
PYTHONPATH=scripts python3 tests/required_unittests.py tests.vnext.test_selected_source_requirements tests.vnext.test_company_fiscal_range tests.vnext.test_company_event_source_preflight tests.vnext.test_historical_e01_company_case tests.vnext.test_historical_e01_incorporated_input tests.vnext.test_historical_ma_confirmation
PYTHONPATH=scripts:. python3 docs/evidence/issue28_company_event_source_preflight_20261013/verify_sources_entry.py --source-root /absolute/saved/source-inputs --company southwest_airlines --report-end 2024-12-31 --metric B01 --metric E01 --output /absolute/new-read-only-proof.json
python3 tools/vnext_company.py sources --company paramount_skydance_paramount_global --source-root /absolute/saved/source-inputs --report-end 2024-12-31 --metric E01
```

Diagnostic output must be new. Original source root is read-only. No business key/call context is needed. Fiscal-year-range dispatch uses the existing issuer-label reader; finite routing tests prove that interface, while the material runs above pin report-end explicitly. This is not a claim of a complete new five-year business execution.

New provider/paid/SEC calls **0/0/0**. No old response/result/ledger identity is rewritten; no Ready, merge, adoption, deployment or active operation. Online E01 source completion, model execution and accepted content-confirmed company counts remain responsibilities, with their existing permission boundaries. #28 next public work follows the receiver's concrete update-dependency and revenue-policy feedback, independently of source-only readiness.
