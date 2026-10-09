# B12 ordinary CSV: explicit RPO limitation

Base main9493ed0e. This display-only change adds the existing approved
RPO != ARR / cRPO != ARR limitation and says it is not a churn rate.
The actual current renderer reads ordinary_public_projection_v1.json; no
special_projection_notes function exists in this base. Only B12.notes differs
in parsed JSON. The old catalog/zero_ai_public_projection.json already has the
RPO/cRPO distinction; old Spec, formula, Result and Trace are not changed.

The genuine Salesforce source table says Current35.1 / Noncurrent37.3 /
Total72.4 as of January31,2026, versus Total63.4 as of January31,2025.
The selected native RevenueRemainingPerformanceObligation fact has USD,
scale9,contextc-4,no dimensions,raw72.4. HTMLid f-524 (not ordinal541, which
belongs to native parsed order). Original file:
evidence/accession_materials/salesforce_1108524_000110852426000060/crm-20260131.htm.
This direct table read supports72400000000 USD/asof2026-01-31; other five-year
values remain receiving-owner evidence, not an author rerun.

before.log preserves the missing-limitation failure. after.log runs10 tests
in4.866s,zero skips: actual saved B12 writer/CSV and cold read, no repeated
extraction, unchanged Result and all expected records, unchanged USD/asof
and FY2026. Adjacent B01 prepared-case period/subject/Spec failures and normal
save remain. No SEC/model request or historical root modification.

Saved old CSV files remain their original rows; new rendering uses this
ordinary display config. The update configuration already hashes that config,
so receiving the display version can trigger one normal processing version;
it does not rewrite old rows or automatically rerender old results during a
read. No independent review is claimed for this wording-only change. It grants
neither all B12 business acceptance nor formal publication.
Tests were run on main9493ed0e plus the stated config and test changes; Git
records the product commit separately rather than calling the dirty test a
committed-SHA test. Existing test module is already in company-current CI.
