# Company history dispatch consumes the selected statement dependencies

This public glue consumes fixed provider `b0c9798c0be3ed1d1516b5ec67a45f34665b6de1`, whose only parent is public PR234 `014155a4`. The provider tree `2ef30e64` was read directly, including its metric-specific function, typed property checks, retained assessment and primary record. No unrelated historical development branch is received. The provider owns `historical_statement_cases`; this delta only changes its two existing public company dispatch uses and their import.

`company_local._run_saved_history` now calls `processing_files_for_statement_metric(m)` at the B07 and generic statement positions. B04/B07 receive their actual new source-property/parser/policy dependencies; B05 and other generic statement metrics retain exactly the old set. Case factories, fiscal-year selection, shared controller, Calculator, saved result and CSV behavior remain. The ordinary latest-year Company Facts entry is separate and is not claimed as integrated by this historical change.

## Actual regression and controls

The formal `tools/vnext_company.py run --period fiscal-years --metric B04 --metric B05 --metric B07` dispatch control passes through the real argument/parser/routing code and captures the batch writer's actual arguments. Only the batch writer returns an explicitly constructed dispatch response; no financial factory runs. The first test harness omitted its required status and raised KeyError (`before-controls.log`); that harness shape was corrected before the actual negative. `before-dispatch-controls.log` then reproduces the missing9 extra dependency entries at the real public dispatch. This is a dependency-routing failure, not a business result.

`after-controls.log` has four LOCAL_PATH_ALIAS errors because the local default temporary directory is reached through macOS `/var` symlinks; its other controls run. The final command uses actual nonlinked `/private/tmp` and retains the production path check, rather than changing code or expected behavior to swallow these errors. `final-controls.log`: **156 affected controls /9.939s /zero errors/failures/skips**.

The added small update-state control uses actual declared code file hashes with explicit constructed financial records: changing `statement_metric_amendment.py` reprocesses only B04/B07; B05 keeps its original result. Following identical checks forbid result creation. It tests controller/configuration behavior, not an actual amount. Existing company, fiscal range, storage/recovery and historical property controls remain.

```sh
TMPDIR=/private/tmp PYTHONPATH=scripts:. python3 tests/required_unittests.py tests.vnext.test_statement_metric_dispatch tests.vnext.test_company_local tests.vnext.test_company_fiscal_range tests.vnext.test_company_current_records tests.vnext.test_historical_statement_cases tests.vnext.test_statement_metric_amendment tests.test_selector_registry
python3 tools/vnext_company.py run --company paramount_skydance_paramount_global --source-root /absolute/restored/source-inputs --period fiscal-years --fiscal-year-start 2024 --fiscal-year-end 2024 --metric B04 --metric B07 --work-dir /absolute/company-task --output-dir /absolute/new-output
```

The second command is the actual consumer's next business verification. #47 has its existing task and independently frozen original operands, and will execute processing/forbidden-repeat/independent CSV on this fixed glue. This public routing control does not replace those observations or claim their completion. No SEC/provider/paid calls, source/ledger/old Result edits, model or scope change. No author Ready/merge/adoption/deployment. New-head CI and receiver review remain separate.
