# A03 alternate-layout scope gate

Status: `NO_AUTO_CERTIFIED_ALTERNATE_UNDER_CURRENT_A03_SCOPE`.
This is a new-source audit, not qualification credit or an execution grant.
Machine evidence: [a03_alternate_scope_blocker.json](a03_alternate_scope_blocker.json).
Blocker ID: `sha256:143f064cd0babe66cf2bf8a8a0d1645c0961083fcf96cb7032965007e83c83c9`.

The two authorized acquisitions are now real immutable HTTP-200/retry-zero
observations; no third filing or extra SEC request was made. Their full native
DerivedAssets were used, not filtered tables or archived PR #22 responses.

| Source | Full source / asset | Exhaustive finding |
|---|---|---|
| BAC FY2025 | SHA `c8725c7963d19cd6a2f3c1d0034b2a1068b4490124be6b6600a4db23be5ed134`; 369 tables; asset `sha256:5417fee3903f636a6aeae3eda65a262c551fa4e355316a3273f3276262e08519` | The only table labels containing LCR or Liquidity Coverage Ratio are glossary table 351, row 51. There is no numeric LCR table target. The consolidated average LCR, 112 percent, is in original non-table bytes `3449928..3451080`. |
| Citi FY2025 | SHA `12f5818d577a8b8022e25851849e8d6d453f05ab4f89d906f185593547fb67fe`; 330 tables; asset `sha256:20b20f8b98999c1002a8040c006f603f94faa06529cc0b4004f214f16ffac196` | All LCR table-label hits are TOC table 41 and numeric table 75. Table 75, row 4 column 3 contains `115`; `%` is column 5. Its exact source span is `5107406..5116689`. It has no table/caption label proving both firm scope and average aggregation. |

The unchanged A03 exact aliases are `entity_scope: Firm` and
`aggregation: average`. Every original table caption and origin-cell raw text
was checked with the existing bounded matcher. `complete_scope_tables=[]` for
both full sources, including non-target regulatory-ratio and glossary tables.
Citi's unrelated table 329 contains the only `Firm` hit, but no average/LCR
target; it cannot supply another table's scope evidence.

For Citi the real native Reader/Evidence path returned:

```text
Candidate: REVIEW_REQUIRED
Evidence:  PASS
normalized liquidity_coverage_ratio: 1.15
normalized_scope: {}
system_approval_eligible: false
Evidence ID: sha256:99a70f312783556ea9bafb4d4fc4a47110721af4ba9125f9c07d2d9b2b545b5f
```

`PASS` here proves the raw numeric locator, not automatic scope certification.
The full native Candidate and Evidence record are retained in the JSON. No
scope label was invented, copied into a caption, or borrowed across tables.

## Exact period evidence

BAC's paragraph explicitly says the three months ended December 31, 2025.
Citi's post-table paragraph at bytes `5116934..5117332` calls its LCR an average
and compares it with the quarter ended September 30, 2025; its pre-table HQLA
paragraph at `5103861..5104862` identifies consolidated Citigroup and the fourth
quarter. This is quarter-average evidence, not proof of an annual average.
The diagnostic Candidate reused the current `FY2025` task label solely to
exercise the existing checker; that label was not certified as the disclosure's
averaging horizon. A03's MetricSpec has no explicit averaging-period field,
while the historical financial matrix uses a January–December target window.
Any future alternate fixture must declare its real period rather than quietly
replace quarter-average with annual-average semantics.

## Reproduction and minimal policy question

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_r4_fixture_authority.R4FixtureAuthorityTest.test_a03_alternate_scope_absence_is_exhaustive_on_both_fresh_sources
```

The native full-source probe was executed with `source_authority`,
`audit_scope_alias_coverage`, `index_source_structure`, and `_native_probe`
from the submitted modules; exact inputs and native probe recipe are in the
JSON. Its command returned 0 in 13.345 seconds. The captured zero return means
the diagnostic ran, not that this fixture passed its positive gate.

The smallest viable additional policy is an **A03-specific** permission to
prove entity scope and average aggregation from exact same-source,
deterministically table-associated narrative, retaining Citi's numeric table
cell. It also needs an explicit treatment of the disclosed quarter-average
period for an alternate qualification fixture. Alternatively, the owner must
change the alternate-source requirement. The A12-only composite grant does not
authorize this; no A03 proof mechanism or alias was loosened here.
