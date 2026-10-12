# Historical average-risk scope dependency before result reuse

Public PR207 supplies the shared test-side processing observer. Its receiving
feedback identified a current A13 omission. Historical A03 and A12 have the
same actually called scope checker but declare their own processing paths;
their effective configurations did not include `scope_contract.py` either.
`before.json` records real Spec/Calculator calls on explicitly constructed
source controls. The values in that diagnostic are controls, not bank evidence.
Current A13 belongs to the public owner; this patch changes only the historical
average-risk declaration and its existing historical tests.

## Minimal change and dependency

Add `scripts/vnext/scope_contract.py` to the existing
`historical_average_risk_cases.PROCESSING_FILES`. Do not change source selection,
measurement dates, wording, monetary values, Spec, Calculator, controller or
writer. Changes in this transitive program now enter the shared reuse decision.
A03/A12 real functions consume that checker, so this is not an unused file list.

Candidate starts directly at fixed public PR207
`d65ca72c024f4ed2a14670d7afaaba30fd5a86a1`, which normally includes actual
main31e4. Production needs only the already-existing scope module; the new
regression uses PR207's one shared test helper. No PR208/209/210 capability or
old history installer is carried in this candidate. Before PR207 enters main,
test acceptance explicitly uses this combination; an isolated helper check is
not company-wide acceptance.

## Actually executed controls

- Both constructed historical A03/A12 preparations call the real Spec and
  Calculator. The shared observer confirms the actual scope validation calls
  are declared. Removing the called dependency makes that check fail.
- A small constructed state test uses the actual common updater with clearly
  labeled source/saving substitutes: stable success reuses, one in-memory
  dependency-digest change calls the factory once, and the next same-input
  check reuses the new version. It does not edit source or program files.
- `removed-dependency-negative.log` removes the path only in memory and
  reproduces the old erroneous reuse for both metrics. Expected test failures
  are retained, not converted into financial successes.
- Final thin candidate: **32 tests, 0.337s**, zero failures/errors/skips.
  Existing period/quarter, unit, missing-year, stable-withheld and partial-failure
  assertions are kept. Initial 31-test run and added-state 32-test run remain.

## Real source and company consumer

No existing five-year bank material was reread or re-fetched. Use the restored
read-only source root returned by retained PR52's `restore`; the complete
original export is already in Git. The existing saved-source consumer performs
its normal parsing and calculation on the requested original.

Exactly one affected consumer runs from **empty state**: JPMorgan A03 FY2021,
first **69.507633s**. It returns **1.11 ratio**, actual quarterly average
**2021-10-01 through 2021-12-31**, within annual container FY2021; it is not
annualized. Original accession **0000019617-22-000272** and full Result ID
`sha256:bd89a186f692b5704837942015f259fa2671ada46be47a7a948f6cb3ff123c11`
match the previously accepted source result. The saved effective configuration
contains the real scope file's SHA, checked against its bytes.

Repeat forbidding the historical factory, inspector and both numerical
Calculator entries: **0.743514s**, no calculation/no new directory, **6 Result
files** unchanged. Independent results/CSV: **0.307938s**, **17 state files**
unchanged. Separate old-task read: **0.414745s**, all **163 files** unchanged,
12 rows still include 10 original values and two actual missing-FY2026 states.
The old task is not used as proof of new calculation.

The fresh execution used the earlier receiving combination with this exact
historical production patch uncommitted, explicitly recorded as such. After
extracting the three files onto PR207 only, the actual production SHA and all
effective A03 processing hashes equal the fresh execution. A further forbidden
repeat on this thin candidate is **0.507s**, followed by independent read
**0.177s** preserving **19 state files**. Financial calculation is not repeated
merely to produce a new commit ID. `execution-identity.json` records the exact
boundary; new logs/documents change no production bytes.

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. python3 tests/required_unittests.py \
  tests.vnext.test_historical_average_risk_cases \
  tests.vnext.test_selected_history_result_state \
  tests.vnext.test_processing_dependency_checks

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. python3 \
  docs/evidence/issue47_average_scope_dependency_20261013/verify_company.py \
  --source-root /absolute/saved/source-inputs \
  --work-root /absolute/new-average-scope-validation \
  --old-state /absolute/existing-average-task
```

Use actual saved inputs and fresh external output directories. The verifier
forbids sockets and repeat calculation, never mocks a successful financial
factory. Other years and real A12 values are reused rather than recomputed.
No new SEC/provider/paid calls, old Run/answer modification, author merge,
formal adoption or active switch. Full historical business, source completion
and other known metric failures remain incomplete.
