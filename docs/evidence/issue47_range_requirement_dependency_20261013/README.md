# Historical income reuse tracks the fiscal-range requirement reader

Receiver [PR219/6135192423](https://github.com/wlvh/SEC_metrics/pull/219#issuecomment-6135192423) found that historical B01/B02 execute `normal_source_requirements._Requirements.require` while resolving issuer fiscal years, but its code version was absent from the effective reuse configuration. The public owner explicitly delegated this remaining consumer declaration to #47. This patch adds one path to `historical_statement_cases.INCOME_PROCESSING_FILES`; paired B02 inherits it. General B04/B05/B07 statement declarations, public `company_fiscal_range`, controller/store/renderer, basic dependency set and runner/CI files are unchanged. No calculation, period, source selection or acceptance rule changes.

## Regression and affected behavior

An existing small saved-source fixture actually runs fiscal-range discovery and records calls to the requirement reader. Before the patch, both income declarations fail the shared dependency guard. Constructed state controls change only this dependency's digest in memory: before the patch B01/B02 incorrectly reuse; after the patch each processes once then reuses. B04/B05/B07 retain zero processing under that unrelated digest change. These state substitutes are explicitly controls, not financial results.

`before-corrected.log` retains four genuine failures. The first harness used the wrong `_configuration` signature and passed the pre-existing duplicate income tuple directly instead of the company entry's deduplicated declaration; those harness errors are retained separately in `before.log`. After correcting the harness without changing production, the four missing-dependency failures remain. The final one-line production repair passes **115 tests /2.709s /zero failures, errors or skips** across historical statement, selected-result state, history dispatch and fiscal range (`after.log`). No source file or old receipt is changed to make a test pass.

## Actual same-company migration, repeat and independent CSV

The existing Salesforce source-export consumer's FY2026 B01 is reused as the real affected case. It selects issuer FY2026, actual2025-02-01→2026-01-31, original accession `0001108524-26-000060`. One normal same-task update takes **13.085619s**, processes B01 once and records nine actual `_Requirements.require` callbacks for label/source roles. It returns **41,525,000,000 USD** and original full ID `sha256:8cecba16403adcd8197747cecd1bbb27cb8cb851b4eb236eed2ad74f895ff60d`. The normal saved configuration includes the requirement reader digest `01ca6ccbfdb5dfbaa1bc1d4410fd00271aece87189c80bbd1351edca96f7528a`. All14 prior result files remain; the new normal version raises the set to21. Old identities/configurations are not edited by hand.

A real-function profile forbids the historical business factory and both Calculators on repeat, retaining their actual function/source metadata. The repeat takes **0.473793s**, returns NO_SOURCE_CONTENT_CHANGE/calculationfalse and invokes the requirement reader zero times. All21 result files remain, with only normal check journals38→40. Independent `results`/CSV takes **0.062185s**, preserves all40 state files, the amount, actual annual dates, USD and full original ID. No other company/year/metric is processed. The financial first phase uses a narrow requirement-call observer, not a costly full-module profile or mocked business operands.

`verification.json` is the primary record. First/repeat/read `.json.gz` preserve exact commands/stdout; CSV and evidence remain readable. Source registration, the original full request ledger/manifest and original body/header files stay unchanged. Socket entry is forbidden throughout. New SEC/provider/model calls are0; no native Run, formal acceptance, adoption or active change is created. This closes one program reuse defect, not the whole historical-source or1950-position goal.

## Reproduce with existing material

Use this candidate's code, the project Python dependencies, and the same previously created Salesforce task/source root. Sources are read-only and each output directory must be new:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. python3 \
  docs/evidence/issue47_range_requirement_dependency_20261013/consumer.py first \
  --state /your/existing/salesforce-state --output /your/new/requirement-first
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. python3 \
  docs/evidence/issue47_range_requirement_dependency_20261013/consumer.py repeat \
  --state /your/existing/salesforce-state --output /your/new/requirement-repeat
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. python3 \
  docs/evidence/issue47_range_requirement_dependency_20261013/consumer.py read \
  --state /your/existing/salesforce-state --output /your/new/requirement-read
```

For a separate empty business review, use the existing company command with the already committed/restored full PR52 sources: `tools/vnext_company.py run --company salesforce --period fiscal-years --fiscal-year-start 2026 --fiscal-year-end 2026 --metric B01 --source-root <actual source-inputs> --work-dir <new state> --output-dir <new runs>`. This patch's real evidence is **migration of an existing task**, not a claim that we repeated the previously completed empty-task export test. No new input package or acquisition is needed.

The two modified test files already appear individually in `.github/workflows/company-current-records.yml` pull-request paths and its direct history test commands. No unused selector append, new runner or new CI platform is introduced. New-head remote execution and receiver recheck remain separate from local115-test results; the author keeps Draft and does not merge/Ready/deploy.
