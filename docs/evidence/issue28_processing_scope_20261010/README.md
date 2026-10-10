# D04-only dependency changes must not repeat unrelated company calculations

Progress on #28; shared public updater and writer impact for #47. Base: actual main `c99b5d3c3180b8e8dfbac7f9182a941af4ae7705`. Read actual #28/#47 bodies and Claude receiving comments through 6093935030/6093935306; PR135/136 bodies and review/inline comments had no new review requests at this checkpoint. This increment does not reopen received PR102/106/112 or the revenue chain.

## Problem and change

Peer fixed input: [1037bbd5 original small-state reproduction](https://github.com/wlvh/SEC_metrics/blob/1037bbd5/docs/evidence/issue47_result_failure_receiving_20261010/main-g3/README.md). Main145a→bdb added D04 dependencies and dispatch inside two files whose complete hashes were all metrics' processing configuration. Identical success and stable withheld inputs then recalculated. Parent original-regression.log demonstrates the failure with the factory deliberately forbidden; it is a constructed state, not a financial result.

The D04-specific dependency list and producer dispatch now live in `ordinary_d04_saved_route.py`. Its bytes are consumed only by D04. All original D04 dependencies remain, confirmed structurally in source-equivalence.json. Common store/controller and actually used business rule hashes continue to affect every relevant route. This is no global hash exclusion or AST-based runtime fingerprint framework.

`ordinary_update_compatibility.py` recognizes only the inspected 145a→bdb D04-only pair and conversion from those exact pairs or c99 to this exact extracted generic pair. Every other configuration field and dependency must be equal, including producer, company, source root, registry, period, optional processing files and business rules. D04 is excluded. Actual revenue or presentation differences between old main versions still cause normal processing. Unknown controller/store bytes are not compatible. This does not receive PR115's broader, separate old-finance transition.

A compatible check records the current comparison separately, retaining the original Result, terminal, original success pointer, input/request history and files. An interrupted new check can recover from its committed terminal. No new business call or permission is created. Invalid sources and consumed rule changes still cannot reuse old credit.

## Actual parent verification

- `original-regression.log`: one expected failing test before implementation; new controller would enter the forbidden factory for both outcomes.
- `directed-tests.log`: 52 test executions (46 unique IDs; six imported historical tests repeated), 0.567s, no skips.
- `combined-tests.log`: 124 test executions (118 unique IDs; six imported historical tests repeated) and bounded existing full-source integration, 23.557s, no failures/errors/skips. Includes D04 full-group/unresolved controls, source/calculation change, saved/old state, reporter, stable withheld and interruption.
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


## Limited independent review and receiving

[Independent conclusion](independent-review/结论.md): PASS for exact21004b59 six-file increment. Actual old Git configuration reconstruction, 41 original D04 dependencies preserved, source/business/unknown transitions refused, 57 test executions /51 unique IDs (six imported history tests duplicated), and16 small interruption/source/correctness controls.32 tool nodes,3 messages, UTC05:37:44..05:46:10,505.924s. Reviewer read the saved small records, did not rerun company or big sources; no full CI/business/production credit. Original conclusions and failures remain.

The duplicate executions were then removed by importing the history test module rather than exposing its TestCase class to unittest discovery. This changes test loading only; product source bytes remain exact21004b59. Subsequent log records five new tests plus the original history tests exactly once, not57 unique new tests. No unchanged financial source/company rerun.

Historical consumer [fixed0cb17d83](https://github.com/wlvh/SEC_metrics/blob/0cb17d83/docs/evidence/issue47_result_failure_receiving_20261010/main-g3/README.md) was actually read by the parent: actualmainMarriottFY25B04 first3.917s; public candidate same history factory/Calculator forbidden repeat.893s, independentresults.521s, eight result/success-pointer files and original Result/value/date/CIK retained.61 history controls.534s were read as peer execution evidence, not re-executed or independent business acceptance. Its oldA03 RPO/PR115 differences remain outside this transition.

committed-code-correspondence.json confirms the executed uncommitted controller/store/compatibility bytes exactly match product21004b59. It does not claim execution occurred after commit. All subsequent evidence-only changes retain these product bytes. New-head CI is recorded separately from previous head.


## Actual main f51 receiving alignment

Latest receiving instruction6098982022 was read from the server, not treated as proof of receipt or merge permission. The candidate normally merged actualmainf51, preserving B02, single reported revenue, reporter/null Trace, D04 and compact CSV code. The one conflict joined both required company workflow steps (D04-scope and single-revenue), without ours/theirs or dropping a trigger. Raw inherited main evidence logs have whitespace retained; owned production/test/workflow diff check passes.

First combined test run97/10.667s failed three finite migration/recovery checks: controller bytes changed by the actual B01/B03 dependency added in main, but the finite bridge still named only the old extracted pair. Repair adds the actualmain/extracted pairs and the precise old extracted bridge identity. All other source/period/producer/registry/business fields still compare; absence of the new consumed fiscal-definition dependency prevents B01 from inheriting old credit. Unknown bridge bytes and unknown business changes remain refused. It does not create generic source-code similarity comparison or waive changed revenue semantics.

Repaired affected suite98/10.138s has zero failures/errors/skips, including paired comparison, reported/single revenue, D04 full groups, updater recovery and reporter controls. Actual original MarriottFY2025 B04 task, with calculation forbidden, reuses2,601,000,000USD/1048286/full2025/originalc87ee735 ResultID in.511s; seven result/success files unchanged. Separate process results read0.438s does not update or rewrite the original. It is not a rerun of the original financial calculation or fullcompany acceptance. These executions test the recorded uncommitted merge bytes, not a later commit; tested-tree.json pins their relationship.

Company-registry row scope is a separate new successor after this receiving repair; PR145's source-discovery comparison remains independent. Current B06 source increment is retained on its own unmerged branch and is not imported here. Original limited review210 and main reviews are reused; the newly extended finite bridge still needs limited difference review before receiving. No provider/paid/SEC calls, merge/Ready/business adoption or deployment.


Limited independent increment review for exact7fcb4e70 passed:41required tests/no skips, four independent small-state controls, per-commit actual Git configuration reconstruction and819 counterexample assertions. Actualmainf51→merged B01/B03/B04/B10 configurations can reuse; old832→merged B01/B03 require processing for changed revenue/source dependencies, B04/B10 may reuse. Both workflow step/path sets remain. Reviewer30tools/3messages/523.251s ended; no company or large-original rerun. See main-f51-alignment/independent-review/conclusion.md. The evidence-only follow-up keeps all reviewed source bytes; new-head CI is observed separately.
