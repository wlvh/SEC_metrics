# Exact bounded independent review of selected source preflight

Verdict: LIMITED_CHANGES_REQUESTED. One P2 error-path omission was reproduced in the new selected-source entry. The tested missing-source, final-failed-GET and native-prior alternatives did not falsely return source availability. This conclusion does not accept the full PR, business results, budgets, acquisition, model calls or production.

Base: `f6ef7886d6630f7675c25cd42e306c373ab05769`.
Patch: `0215ec9d0d8dd7f0bc4f964bc6639aabd4cc29a2`.
Directory: `/Users/lyuhongwang/.codex/worktrees/issue28-selected-source-preflight/SEC_metrics`.
Start: 2026-10-09 22:54:54 UTC. End: 2026-10-09T22:58:48.695549+00:00.
Tool calls including orchestration and nested calls: 30 total = 11 functions.exec calls + 17 exec_command calls + 2 clock calls. Ordinary outgoing messages: 1 final, 0 interim/questions; 0 collaboration-message calls. The delegated input message is separate.

## Finding

[P2] Return a structured metadata limitation when a saved submissions object lacks its required shape.

Location: `scripts/vnext/selected_source_requirements.py:138-151`, especially the two `except ValueError` clauses at lines 141 and 150. The new `sources` path calls the existing metadata resolver before protecting its required dictionary shape. A successfully saved and request-bound JSON body `{"cik":1048286}` reaches `_history_index` and raises `KeyError('filings')`; `{"cik":1048286,"filings":{"recent":{},"files":[]}}` raises `KeyError('filingDate')` in `block_last_days`. Neither exception is a ValueError, so the public `tools.vnext_company.main(['sources', ...])` propagates the exception with empty stdout. The result therefore has neither a source URL/limitation nor the promised structured unresolved state/exit2. These are source schema failures, not missing financial disclosure or business rejection.

The two cases were run through the actual in-process public main, with native recorded body/header/request persistence; no metadata resolver, source proof checker or parser was substituted. Source bytes were unchanged before/after each invocation. The external-process traceback/exit1 consequence is inferred from its ordinary top-level `sys.exit(main())`; a separate malformed-input CLI subprocess was not run.

Recommended bounded repair: protect/validate the metadata structure before resolution, or normalize the expected structural exceptions at this selected preflight boundary, including its fallback discovery branch. Preserve an unresolved source-integrity limitation and the selected submissions dependency; keep graph completeness false. Add the two small cases to the existing module and require JSON plus exit2. Do not change the historical resolver's selection semantics or reinterpret this as business-source acceptance.

Evidence: `small-counterexamples.log`, its final two JSON records include full exception paths and empty stdout.

## Personally executed validation

- The requested command ran once on the exact checked-out patch, with `PYTHONDONTWRITEBYTECODE=1`: `python3 tests/required_unittests.py tests.vnext.test_selected_source_requirements tests.vnext.test_dei_release_selection tests.vnext.test_company_online tests.vnext.test_history_company_dispatch`. 48 passed in 3.066s; 0 skips/errors/failures. Log: `required-tests.log`.
- Four extra intended negative cases stayed unresolved without writes: missing declared prior native; complete but nonadjacent prior native; two fully annual 371day native records with conflicting raw FY labels; missing declared history frontier. HTTP/socket, SEC fetch, Calculator and both full preparation entry points were forbidden during discovery. The first conflict probe accidentally constructed a 367day interval and was rejected on duration before the intended conflict branch; that diagnostic is retained, and the corrected 371day probe explicitly reached `SELECTED_SOURCE_PRIOR_NATIVE_PERIOD_CONFLICT`.
- The two malformed metadata schema cases described above reproduced the P2 omission. These are constructed small materials, not real-company or numeric acceptance.
- All five scoped product/test/workflow/document files matched both their `tested-tree.json` SHA-256 values and `git show` bytes at the patch commit. Log: `hash-verification.log`.

## Static review and read-only evidence inspection

The new command dispatch is separate from `run`/`acquire`, and its reviewed execution path only calls metadata selection, saved-source/proof reads, directory enumeration and the finite original-DEI parser. It does not invoke annual preparation, Calculator, HTTP, a ledger or runtime installation. B01 excludes unused prior bodies; B02 requests prior bodies under the existing continuous-subject policy. The native alternative only attaches to `MISSING_SAVED_SOURCE`, requires the saved index and every declared native source, checks equal DEI period records and exact day adjacency, and does not excuse a failed GET, target or amendment. The output labels the DEI year as raw original data and keeps final consumer FY resolution, freshness, amendment meaning, business acceptance, fetch authority and production false. The workflow paths and test selection include the new module.

The existing metadata resolver still loads its own actual catalog dependencies, including prior metadata where its selection algorithm needs them; this review did not redesign that shared dependency contract. Reporting-registrant switching and both catalog sets were traced statically; no constructed predecessor-company or real predecessor-material run was added.

README, tested-tree, driver source and saved CLI JSON/logs were inspected, without reopening the peer data tree. Earlier Marriott/Macy/Salesforce logs bind the preceding program hash `9a66c423...`, as README states. The final Macy log binds the patch program hash `b9aef444...` and preserves raw FY2023/2023-01-29 to 2024-02-03. These are read-log observations, not personally rerun real-company results. The committed existing final test log reports 48 in 3.070s; the independent rerun above is separate.

## Scope and unchanged-state checks

Only this independent-review directory was written. No product/tests changed; no spawn, commit/push, network, real SEC/model, tar, or peer #47 worktree/ledger/state access occurred. The initially supplied repository/user boundaries were read with the exact patch/base scope. Live Issue #28 and GitHub CI were not fetched because this review expressly prohibits network.

Not covered: the real three-company/material batch; financial quantities, amended financial meaning, business/39metric acceptance, final issuer FY consumer comparison, online acquisition/grants/counters, original run/acquire consumers and the unmerged PR122 routing change, all other workflow jobs, live GitHub CI, real SEC/model results, release/adoption/active and production. No claim of coverage or authorization is made for them.
