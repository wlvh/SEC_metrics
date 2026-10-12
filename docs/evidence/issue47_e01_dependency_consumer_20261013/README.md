# E01 content-consumer coverage for the shared dependency check

This closes the route-specific validation gap identified in PR207's receiving
comment6130757933: its E01 probe used ordinary zero-AI counting and did not
execute the delivered content-confirmation consumer. No production logic,
request contract, model trial, controller or second checker is added.

One method in the already-required historical E01 test module uses PR207's
shared test-side observer. Constructed no-matching-response, successor-window
and missing-attachment cases retain their precise null/refusal reasons. The
existing complete-candidate-walk zero control calls the same content adapter
and actual Calculator; it is explicitly a control, not financial evidence.
Removing the actually called confirmation module from the declaration causes
the guard to fail. Final thin PR207-only composition: **27 tests, 0.163s,
zero skips**. The later thin log keeps its separately measured duration.

Actual saved-source factory check: **Southwest FY2024**, **28.275445s**,
**33 executed modules**, all declared. Complete six-candidate request
`sha256:34507016c9b8da8e5bf9eb47b884f05e160758a43a3394593892d3ab6df283a5`
is exactly equal as a JSON object to the existing committed
`docs/evidence/issue47_e01_subsections_20261012/saved-request.json`.
No original source is reread manually and no model response is issued. Result
`sha256:29806686aff92f5d5fd3dfb1fcda8351c698d400a77551f03fede5a03b2a29d0`
remains null, reason **E01_CONTENT_RESPONSE_NOT_AVAILABLE_FOR_REQUEST**.
This exact input has no corresponding semantic response; no partial annual
count or old V1 answer is used. Existing company save/repeat/independent-read
proof is reused from the above original record; it is not repeated or credited
as a new financial success.

The actual full-source trace ran on the existing receiving combination385472,
before the new test method was added. The final short branch starts at fixed
PR207d65 plus only the historical test and this evidence. E01 production did
not change. `actual-source-summary.json` preserves function-level traces and
exact request equality while referencing the existing full request, rather
than duplicating it into a new review package. The initial diagnostic guessed
an unregistered short company ID and failed before any case preparation;
registered `paramount_skydance_paramount_global` was used in the controls.

```bash
TMPDIR=/private/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. \
  python3 tests/required_unittests.py tests.vnext.test_historical_e01_company_case \
  tests.vnext.test_processing_dependency_checks
```

For a real-source guard use the existing restored source-inputs root, the
actual `prepare_historical_e01_year_case` and `PROCESSING_FILES` with the shared
`processing_calls` / `assert_processing_calls`; no preparation-success mock.
Current Source/Spec/Request/Calculator semantics and all existing negative
assertions remain. Source/frame acceptance and a complete content-confirmed
annual count are not established by a dependency check. New SEC/provider/paid
calls **0/0/0**, no new qualification/adoption or old answer/Run modification.
This is offered for the existing public test integration, without expanding
PR211 or introducing another historical runner.
