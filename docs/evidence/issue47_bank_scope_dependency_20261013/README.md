# Bank-scope history consumers track their actual scope checker

This is the same verified missing-dependency class as historical average-risk
PR211, on the already delivered A04/A09/A11 family. That candidate stays stable;
this separate short branch adds only `scope_contract.py` to
`historical_bank_scope_cases.PROCESSING_FILES` and tests to its existing module.
It does not research new companies, financial concepts or metric scope.

Current base is public PR20714b7555b, which normally contains actual main31e4.
The production scope module already exists on main; only the test-side observer
needs PR207. No PR208/209/210/213 or old installer is carried. Public ownership
of runtime/reader/controller remains unchanged.

`before.json` uses existing constructed source fixtures with the real
Spec/Calculator: all three paths actually call `validate_scope_contract` and
`scope_satisfies_contract`, but the module was absent from effective config.
New controls require declaration, retain A04's annual period and A09/A11's
filing-end instant, and reject a removed actual dependency. Small state controls
reuse the shared updater: a memory-only dependency-digest change processes once,
then stable input reuses; no source/code file is mutated. Removing the declaration
only in memory reproduces the old erroneous reuse for all three metrics.

Final candidate: **29 tests, 0.352s, zero skips**. Initial harness failures are
retained: a new class was first inserted before existing methods, then its hash
patch referenced a second Python module alias rather than the fixture's updater.
The class was moved to the end and the existing fixture module reused. Neither
production behavior nor business assertions was relaxed. The earlier fixed run
and final public-base composition have separate logs.

Only **JPMorgan A09 FY2021** runs on complete existing saved source from empty
state: **56.388877s**, **0.0072 ratio**, measurement instant
**2021-12-31** within FY2021. Original full Result ID
`sha256:f9426c8f3fbcf1ff99cf8bf39fb3228bad41bf77fe88b27dfa932c1f5e80c1c2`
remains; no current/prior period is borrowed. The saved effective declaration
contains the scope file's actual SHA, checked against bytes.

Factory/inspector/two Calculator forbidden repeat: **0.743956s**, no calculation,
no new candidate/directory, saved result bytes retained. Independent results/CSV:
**0.299915s**, state unchanged. Separate old-task read **0.577145s** preserves
**312 files** and reads its **21 rows**, retaining the original A09 identity,
value and instant. Other years and A04/A11 material are reused, not recomputed.

The real-source run started on the short publicd65 branch with the exact
production patch uncommitted; it completed during the same-byte28db commit,
which the driver records along with an explicit uncommitted-patch flag. The
later public14b merge only adds the already handed-off E01 test and logs, not
production. Financial execution is not relabeled as a fresh14b run or repeated
merely to produce a committed identity.

```bash
TMPDIR=/private/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. \
 python3 tests/required_unittests.py tests.vnext.test_historical_bank_scope_cases \
 tests.vnext.test_selected_history_result_state tests.vnext.test_processing_dependency_checks
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. python3 \
 docs/evidence/issue47_bank_scope_dependency_20261013/verify_company.py \
 --source-root /absolute/saved/source-inputs \
 --work-root /absolute/new-bank-scope-validation \
 --old-state /absolute/existing-bank-scope-task
```

Use the actual source-inputs root returned by retained PR52 restore and fresh
external outputs. No successful source/financial function is mocked; only
network and repeat calculation are forbidden. Production formulas, units,
source meaning, amendment/successor refusals and true failures remain. This is
reprocessing correctness, not new five-year financial/business acceptance.
New SEC/provider/paid calls **0/0/0**; old answers, Runs and failed states remain.
No author Ready/merge/adoption/active. Receiver and new-head CI still separate.

## Actual received-main composition

After public207/208/209/212 and historical211 were received, this existing candidate normally merged actual main628cb17b, execution merge8e0a62b3. There was no conflict and no public-code edit. Compared with main, production/test differences remain only the historical bank-scope declaration and its own tests; the state controls introduced by211 are preserved. **99 required controls /2.630s /zero skips** cover both bank families, shared state, company dispatch, source export and E01.

All42 declared processing-file hashes for the existing actual JPMorgan FY2021 A09 task equal this combination. The actual factory/inspector/two-Calculator-forbidden run therefore reuses it, **0.761995s**, with zero calculation/new candidate and seven Result files preserved. Independent read **0.300389s** preserves twenty state files and the original0.0072 ratio/2021-12-31 instant/f9426c8f identity. No fresh financial processing, other year or company is repeated. The original56.389s empty-state proof retains its own earlier version; this new check proves combination reuse/read, not a second fresh execution.

`main-628-summary.json`, `main-628-controls.log` and lossless gzip actual repeat/read receipts preserve the executed arguments and outputs. State remains at the original `bank-scope-dependency-receiving-20261013/state`; new outputs use `bank-scope-main-628-20261013`. The same commands above remain the user entry. CI on the updated head and receiver verification remain distinct; no author Ready/merge or new SEC/provider/paid call.
