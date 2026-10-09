# Historical structural applicability at the actual company entry

Actual main `f6ef7886d6630f7675c25cd42e306c373ab05769`; no production change. This consumes the existing B01/B02/B04/B05 trait policy for JPMorgan FY2021–FY2025. These twenty positions are explicitly N_A_STRUCTURAL under the installed non-financial metric applicability; the bank's own revenue/net income disclosures are not absent, and the result is not a numerical zero or extraction failure.

The actual same company CLI saved all twenty metadata outcomes, repeated the same range with preparation factory forbidden, then independently read CSV. Original twenty-five bank performance results (200 result/pointer/check files) were preserved. First run 1289.948s, unchanged repeat 37.337s, independent read 0.894s, all exits 0. Final 380 files were unchanged on repeat/read. Source amount selection and deterministic amount graph were forbidden in both runs; repeat preparation calls zero. The code-object guard uses identity (`frame.f_code is a`), not recursive code-object hashing. Network socket connection forbidden. No new SEC/provider/paid calls.

These costs are honest observations under this tracing driver, not a speed target achieved. Avoiding amounts still leaves expensive annual preparation/ordinary input verification. The shared runtime/source owner has received the concrete paths, driver and timings; a second historical controller/cache is not introduced here. Unchanged inputs remain semantically reused, but reuse does not currently imply negligible preparation/check cost.

Use the previously restored PR52 `source-inputs` root; source restoration is offline. Reviewers should use their own new state/output directories rather than changing the original task:

```bash
python tools/vnext_company.py run --company jpmorgan_chase --period fiscal-years --fiscal-year-start 2021 --fiscal-year-end 2025 --metric B01 --metric B02 --metric B04 --metric B05 --source-root SOURCE_INPUTS --work-dir NEW_STATE --output-dir NEW_OUTPUT
python tools/vnext_company.py results --company jpmorgan_chase --state-root NEW_STATE --output-root NEW_READER
```

`actual-company.json`, `actual-company.log` and the actual `verify_company.py` retain the original concrete source/state/output paths and per-position Result identity. This is one consumer check of installed scope and saved results; it does not extend bank metric research or stand for 1950 business completion.
