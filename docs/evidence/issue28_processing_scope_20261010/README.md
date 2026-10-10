# D04-only dependency changes must not repeat unrelated company calculations

Progress on #28; shared public updater and writer impact for #47. Base: actual main `c99b5d3c3180b8e8dfbac7f9182a941af4ae7705`. Read actual #28/#47 bodies and Claude receiving comments through 6093935030/6093935306; PR135/136 bodies and review/inline comments had no new review requests at this checkpoint. This increment does not reopen received PR102/106/112 or the revenue chain.

## Problem and change

Peer fixed input: [1037bbd5 original small-state reproduction](https://github.com/wlvh/SEC_metrics/blob/1037bbd5/docs/evidence/issue47_result_failure_receiving_20261010/main-g3/README.md). Main145a→bdb added D04 dependencies and dispatch inside two files whose complete hashes were all metrics' processing configuration. Identical success and stable withheld inputs then recalculated. Parent original-regression.log demonstrates the failure with the factory deliberately forbidden; it is a constructed state, not a financial result.

The D04-specific dependency list and producer dispatch now live in `ordinary_d04_saved_route.py`. Its bytes are consumed only by D04. All original D04 dependencies remain, confirmed structurally in source-equivalence.json. Common store/controller and actually used business rule hashes continue to affect every relevant route. This is no global hash exclusion or AST-based runtime fingerprint framework.

`ordinary_update_compatibility.py` recognizes only the inspected 145a→bdb D04-only pair and conversion from those exact pairs or c99 to this exact extracted generic pair. Every other configuration field and dependency must be equal, including producer, company, source root, registry, period, optional processing files and business rules. D04 is excluded. Actual revenue or presentation differences between old main versions still cause normal processing. Unknown controller/store bytes are not compatible. This does not receive PR115's broader, separate old-finance transition.

A compatible check records the current comparison separately, retaining the original Result, terminal, original success pointer, input/request history and files. An interrupted new check can recover from its committed terminal. No new business call or permission is created. Invalid sources and consumed rule changes still cannot reuse old credit.

## Actual parent verification

- `original-regression.log`: one expected failing test before implementation; new controller would enter the forbidden factory for both outcomes.
- `directed-tests.log`: 52 small configuration/controller/history controls, 0.567s, no skips.
- `combined-tests.log`: 124 controls and bounded existing full-source integration, 23.557s, no failures/errors/skips. Includes D04 full-group/unresolved controls, source/calculation change, saved/old state, reporter, stable withheld and interruption.
- `source-equivalence.json`: parent static AST checks only. The exact old145a/bdb code differs only in D04-specific branches; copied D04 dependency statements match c99. Not independent business acceptance.

`verify_company_reuse.py` uses the real user CLI and disables sockets/DNS. First runs actual detached main c99 with saved original Marriott source; repeat runs this uncommitted candidate with calculation factory forbidden; read runs another process with update forbidden. It does not substitute selection, parser, Calculator, writer or result reading. Initial main produces B04 = 2,601,000,000 USD, CIK1048286, FY2025 / 2025-01-01..2025-12-31, accession0001048286-26-000007. Candidate retains the exact original Result, CSV contents and source citations. Three JSON files give roots, IDs, measured times and actual output locations.

- Main first: 3.547191s.
- Candidate repeat: 0.506709s; no calculation or new result directory.
- Candidate independent read: 0.379633s; no update.

These executions use two explicit code roots and one isolated writable task. Candidate executions were uncommitted; not represented as executions of a later commit. Original sources and ledger are read-only and new calls are 0/0/0. Small withheld controls complement the real positive B04; no new full-company business acceptance, all old finance compatibility, model accuracy, production adoption or390 claim.

## Reproduction

Use Python3.14 with repository dependencies and TMPDIR=/private/tmp on macOS. Tests: `TMPDIR=/private/tmp PYTHONDONTWRITEBYTECODE=1 python3 tests/required_unittests.py tests.vnext.test_d04_processing_scope tests.vnext.test_current_d04_company tests.vnext.test_ordinary_current_update tests.vnext.test_selected_history_result_state tests.vnext.test_precalculated_case tests.vnext.test_company_current_records tests.vnext.test_company_parse_reuse tests.vnext.test_reporting_company_projection`.

Company driver accepts explicit `--program-root`, `--source-root`, independent `--state-root`, `--output-root`, `--mode first|repeat|read`, and repeat/read `--baseline company-first.json`. Main first was `/private/tmp/issue28-processing-main-c99-20261010`; candidate is `/Users/lyuhongwang/.codex/worktrees/issue28-processing-scope/SEC_metrics`; sources `/Users/lyuhongwang/Developer/SEC_metrics`; state `/private/tmp/issue28-processing-company-20261010`. Use a fresh state for first; never overwrite original tasks. Repeating the old state on already changed business dependencies is deliberately not universally compatible.

CI explicitly runs new small regression in the existing company workflow. Received main tests/steps are preserved. No new runtime platform, source acquisition, provider execution, Ready, merge, formal adoption, deploy or active switch. Independent review and new-head CI will be recorded by their actual scope and terminal status.
